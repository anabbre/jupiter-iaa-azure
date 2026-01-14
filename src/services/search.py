import os
import sys
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from config.logger_config import logger, get_request_id
load_dotenv()

# Configuración
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
MANIFEST_PATH = os.getenv("EXAMPLES_MANIFEST", "data/docs/examples/manifest.yaml")
EMBEDDINGS_MODEL = None  # Se carga lazy



def load_manifest() -> Dict[str, Any]:
    """Carga el manifest con configuración de la colección"""
    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = yaml.safe_load(f)
            logger.info("✅ Manifest cargado", source="search", manifest_path=MANIFEST_PATH)
            return manifest
    except Exception as e:
        logger.error(f"❌ Error cargando manifest: {e}", source="search", manifest_path=MANIFEST_PATH, error_type=type(e).__name__)
        raise


def get_qdrant_client() -> QdrantClient:
    """Obtiene cliente de Qdrant"""
    try:
        kwargs = {"url": QDRANT_URL}
        if QDRANT_API_KEY:
            kwargs["api_key"] = QDRANT_API_KEY
        
        client = QdrantClient(**kwargs)
        
        # Diagnóstico: imprimir métodos disponibles
        available_methods = [m for m in dir(client) if 'search' in m.lower() or 'query' in m.lower()]
        logger.info("✅ Conexión Qdrant establecida", source="search", 
                   url=QDRANT_URL, available_search_methods=available_methods)
        
        return client
    except Exception as e:
        logger.error(f"❌ Error conectando Qdrant: {e}", source="search", 
                    url=QDRANT_URL, error_type=type(e).__name__)
        raise


def get_embeddings_model(model_name: str = None) -> SentenceTransformer:
    """Obtiene modelo de embeddings"""
    global EMBEDDINGS_MODEL
    
    if EMBEDDINGS_MODEL is not None:
        return EMBEDDINGS_MODEL
    
    try:
        if model_name is None:
            manifest = load_manifest()
            model_name = manifest.get("embeddings_model", "intfloat/multilingual-e5-small")
        
        logger.info("🔄 Cargando modelo de embeddings", source="search", model_name=model_name)
        EMBEDDINGS_MODEL = SentenceTransformer(model_name)
        logger.info("✅ Modelo de embeddings cargado", source="search", model_name=model_name)
        
        return EMBEDDINGS_MODEL
    except Exception as e:
        logger.error(f"❌ Error cargando modelo: {e}", source="search", 
                    model_name=model_name, error_type=type(e).__name__)
        raise


def search_in_qdrant(client: QdrantClient, collection: str, embedding: list, k: int) -> list:
    """
    Busca en Qdrant usando el método disponible (auto-detección)
    
    Prueba múltiples métodos en orden:
    1. query_points (API 1.16+)
    2. search (API 1.6-1.15)
    3. similarity_search (legacy)
    """
    logger.debug("🔍 Detectando método de búsqueda disponible", source="search")
    
    # Método 1: query_points 
    if hasattr(client, 'query_points'):
        try:
            logger.debug("Intentando con query_points()", source="search")
            result = client.query_points(
                collection_name=collection,
                query=embedding,
                limit=k,
                with_payload=True
            )
            logger.debug("✅ Usando query_points", source="search")
            return result.points
        except Exception as e:
            logger.debug(f"query_points() falló: {e}", source="search")
    
    # Método 2: search 
    if hasattr(client, 'search'):
        try:
            logger.debug("Intentando con search()", source="search")
            results = client.search(
                collection_name=collection,
                query_vector=embedding,
                limit=k,
                with_payload=True
            )
            logger.debug("✅ Usando search", source="search")
            return results
        except Exception as e:
            logger.warning(f"search() falló: {e}", source="search")
    
    # Método 3: fallback
    if hasattr(client, 'scroll'):
        try:
            logger.warning("⚠️ Usando scroll() como fallback (puede ser lento)", source="search")
            results, _ = client.scroll(
                collection_name=collection,
                limit=k,
                with_payload=True,
                with_vectors=False
            )
            logger.debug("✅ Usando scroll (sin scoring)", source="search")
            # Nota: scroll no tiene scores, así que los agregamos ficticios
            for r in results:
                r.score = 0.5  # Score ficticio
            return results
        except Exception as e:
            logger.error(f"scroll() también falló: {e}", source="search")
    
    raise RuntimeError(
        f"No se pudo encontrar un método de búsqueda válido. "
        f"Métodos disponibles: {[m for m in dir(client) if not m.startswith('_')]}"
    )


def search_examples(
    query: str,
    k: int = 5,
    threshold: float = 0.7,
    include_content: bool = True,
    collections: List[str] = None
) -> List[Dict[str, Any]]:
    """Búsqueda principal en Qdrant con auto-detección de API"""
    request_id = get_request_id()
    if collections is None:
        collections = ["terraform_book", "examples_terraform"]
    logger.info("🔍 search_examples iniciado", source="search", query=query[:50], k=k, threshold=threshold, collections=collections, request_id=request_id)
    results = search_all_collections(
        query=query,
        collections=collections,
        k_per_collection=k,
        threshold=threshold
    )
    
    # Añadir rank si include_content es True (compatibilidad)
    for i, hit in enumerate(results, 1):
        hit["rank"] = i
        if not include_content and "content" in hit:
            del hit["content"]
    
    logger.info("✅ search_examples completado", source="search", total_results=len(results), request_id=request_id)
    return results


def search_all_collections(  
    query: str,
    collections: List[str],
    k_per_collection: int = 5,
    threshold: float = 0.5
) -> List[Dict[str, Any]]:
    """
    Busca en TODAS las colecciones y fusiona resultados ordenados por score.
    
    Args:
        query: Consulta del usuario
        collections: Lista de colecciones donde buscar
        k_per_collection: Número de resultados por colección
        threshold: Score mínimo para incluir un resultado
    
    Returns:
        Lista fusionada de resultados ordenados por score
    """
    import time
    request_id = get_request_id()
    start_time = time.time()
    request_id = get_request_id()
    logger.info("🔍 Búsqueda multi-colección iniciada", source="search", query=query[:50], collections=collections, k_per_collection=k_per_collection, request_id=request_id)
    
    try:
        # Validar scope
        from src.services.relevance_filter import is_query_in_scope
        is_valid, reason = is_query_in_scope(query, min_keywords=0)
        if not is_valid:
            logger.warning("⚠️ Query fuera de scope",
                          source="search",
                          reason=reason,
                          request_id=request_id)
            return []
        
        # Configuración
        manifest = load_manifest()
        model_name = manifest.get("embeddings_model", "intfloat/multilingual-e5-small")
        
        # Cliente y modelo
        client = get_qdrant_client()
        model = get_embeddings_model(model_name)
        
        # Generar embedding
        query_with_prefix = f"query: {query}"
        embedding = model.encode(query_with_prefix)
        embedding_list = embedding.tolist() if hasattr(embedding, 'tolist') else list(embedding)
        
        logger.info("✅ Embedding generado",
                   source="search",
                   embedding_dim=len(embedding_list),
                   request_id=request_id)
        
        # Buscar en cada colección
        all_results = []
        
        for collection in collections:
            try:
                logger.info(f"🔎 Buscando en {collection}",
                           source="search",
                           collection=collection,
                           request_id=request_id)
                
                results = search_in_qdrant(client, collection, embedding_list, k_per_collection)
                
                # Procesar resultados de esta colección
                filtered_count = 0
                for result in results:
                    score = float(result.score) if hasattr(result, 'score') else 0.0
                    
                    if score < threshold:
                        filtered_count += 1
                        continue
                    
                    payload = result.payload
                    metadata = payload.get("metadata", {})
                    
                    hit = {
                        "score": score,
                        "name": metadata.get("name", metadata.get("source", "N/A")),
                        "section": metadata.get("section", ""),
                        "pages": metadata.get("pages", "-"),
                        "path": metadata.get("path", metadata.get("file_path", "N/A")),
                        "doc_type": metadata.get("doc_type", "unknown"),
                        "tags": metadata.get("tags", []),
                        "metadata": metadata,
                        "collection": collection,
                        "content": payload.get("page_content", "")
                    }
                    
                    all_results.append(hit)
                
                logger.info(f"✅ {collection}: {len(results)} resultados, {filtered_count} filtrados por threshold", source="search", collection=collection, results_raw=len(results), filtered_by_threshold=filtered_count, request_id=request_id)
                
            except Exception as e:
                logger.warning(f"⚠️ Error en colección {collection}: {e}", source="search", request_id=request_id)
                continue
        
        # Ordenar por score (mayor primero)
        all_results.sort(key=lambda x: x["score"], reverse=True)
        
        # Limitar total de resultados
        max_total = k_per_collection * len(collections)
        all_results = all_results[:max_total]
        
        duration = time.time() - start_time
        logger.info("✅ Búsqueda multi-colección completada", source="search", total_results=len(all_results), collections_searched=len(collections), duration_ms=round(duration * 1000, 2), top_score=all_results[0]["score"] if all_results else 0.0, request_id=request_id)
        
        return all_results
        
    except Exception as e:
        logger.error(f"❌ Error en búsqueda multi-colección: {e}", source="search", error_type=type(e).__name__, request_id=request_id)
        return []

def search_with_metadata(
    query: str,
    k: int = 5,
    threshold: float = 0.0
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Búsqueda con metadata"""
    import time
    
    start_time = time.time()
    
    try:
        hits = search_examples(query, k=k, threshold=threshold)
        duration = time.time() - start_time
        
        metadata = {
            "query": query,
            "k": k,
            "threshold": threshold,
            "duration_seconds": round(duration, 3),
            "results_count": len(hits),
            "max_score": max([h["score"] for h in hits]) if hits else 0.0,
            "min_score": min([h["score"] for h in hits]) if hits else 0.0,
            "avg_score": sum([h["score"] for h in hits]) / len(hits) if hits else 0.0
        }
        
        logger.info("📊 Search metadata", source="search", **metadata)
        
        return hits, metadata
    
    except Exception as e:
        logger.error(f"❌ Error en search_with_metadata: {e}", 
                    source="search", error_type=type(e).__name__)
        raise


def main_cli():
    """Punto de entrada CLI"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Buscar documentos en Qdrant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
            Ejemplos de uso:
            # Búsqueda básica
            python -m src.services.search "How to create storage account"
            
            # Con más resultados
            python -m src.services.search "How to create storage account" --k 10
            
            # Con threshold personalizado
            python -m src.services.search "How to create storage account" --k 10 --threshold 0.85
            
            # Ver solo los primeros 500 caracteres del contenido
            python -m src.services.search "How to create storage account" --preview 500
                    """
    )
    
    parser.add_argument("query", help="Consulta de búsqueda")
    parser.add_argument("-k", "--k", type=int, default=5, 
                       help="Número de resultados (default: 5)")
    parser.add_argument("-t", "--threshold", type=float, default=0.7,
                       help="Score mínimo (0.0-1.0, default: 0.7)")
    parser.add_argument("--preview", type=int, default=800,
                       help="Caracteres de preview del contenido (default: 800, 0=completo)")
    parser.add_argument("--no-content", action="store_true",
                       help="No mostrar contenido, solo metadata")
    
    args = parser.parse_args()
    
    logger.info("🔍 CLI search iniciado", source="search", query=args.query, top_k=args.k, threshold=args.threshold)
    
    try:
        results = search_examples(
            query=args.query, 
            k=args.k, 
            threshold=args.threshold,
            include_content=not args.no_content
        )
        
        print("\n" + "="*80)
        print(f"📊 Resultados para: {args.query}")
        print(f"🔍 Parámetros: k={args.k}, threshold={args.threshold}")
        print("="*80 + "\n")
        
        if not results:
            from src.services.relevance_filter import get_rejection_message
            print(get_rejection_message(args.query))
            print()
            return
        
        for hit in results:
            print(f"\n{'='*80}")
            print(f"🔹 Resultado {hit['rank']} - Score: {hit['score']:.4f}")
            print(f"{'='*80}")
            print(f"📄 Nombre: {hit['name']}")
            print(f"📁 Path: {hit['path']}")
            print(f"🏷️  Type: {hit['doc_type']}")
            if hit.get('tags'):
                print(f"🔖 Tags: {', '.join(hit['tags'])}")
            
            # Mostrar contenido si está disponible y no se desactivó
            if not args.no_content:
                content = hit.get('content', '')
                if content:
                    print(f"\n📝 CONTENIDO:")
                    print("-"*80)
                    
                    # Aplicar preview si se especificó
                    if args.preview > 0 and len(content) > args.preview:
                        print(content[:args.preview])
                        print(f"\n... [+{len(content)-args.preview} caracteres más]")
                        print(f"    💡 Usa --preview 0 para ver contenido completo")
                    else:
                        print(content)
                    
                    print("-"*80)
                else:
                    print(f"\n⚠️  Sin contenido disponible")
            print()
        
        print("="*80)
        print(f"✅ Total: {len(results)} resultados")
        
        # Estadísticas
        scores = [h['score'] for h in results]
        print(f"📈 Scores: min={min(scores):.4f}, max={max(scores):.4f}, avg={sum(scores)/len(scores):.4f}")
        
        # Verificar si hay contenidos
        if not args.no_content:
            with_content = sum(1 for h in results if h.get('content'))
            print(f"📝 Documentos con contenido: {with_content}/{len(results)}")
        
        print("="*80 + "\n")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        print("\nTraceback completo:")
        traceback.print_exc()
        logger.error(f"Error en CLI search: {e}", source="search", error_type=type(e).__name__)
        sys.exit(2)


if __name__ == "__main__":
    main_cli()
