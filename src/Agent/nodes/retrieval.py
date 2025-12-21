
from src.Agent.state import AgentState, DocumentScore
from src.services.search import search_examples  # ← Tu search.py
from config.logger_config import logger


def retrieve_documents(state: AgentState) -> AgentState:
    """
    Busca documentos usando search_examples() 
    (la función de búsqueda de tu API actual)
    
    Args:
        state: Estado actual del grafo
    
    Returns:
        Estado actualizado con documentos crudos (sin filtrar)
    """
    question = state["question"]
    k = 10  
    
    try:
        logger.info(" - Iniciando búsqueda con search_examples",source="retrieval",question=question[:100],k=k)
        
        hits = search_examples(
            question, 
            k=k, 
            threshold=0.0
        )
        # Ordenar los hits por score descendente y quedarse con los k_docs mejores
        hits = sorted(hits, key=lambda x: x.get("score", 0), reverse=True)[:state["k_docs"]]

        logger.info(f"✅ search_examples retornó {len(hits)} resultados",source="retrieval",hits_count=len(hits))
        
        # Convertir hits a DocumentScore (para LangGraph)
        raw_documents = []
        for rank, hit in enumerate(hits, 1):
            # Enriquecer metadata con un campo "ref" clicable si es posible
            md = hit.get("metadata", {}) or {}
            path = md.get("file_path") or hit.get("path") or ""
            pages = md.get("pages") or md.get("page")
            # Heurística: construir un enlace local o GitHub si hay base URL configurada
            base_url = SETTINGS.API_URL  # URL base para visor local
            ref = ""
            if path:
                # Si hay páginas, añadir query para el visor
                # Normalizar path a ruta relativa (desde /data/docs/)
                rel_path = ""
                if "data/" in path.replace("\\", "/"):
                    # Extraer desde data/docs/ en adelante
                    rel_path = path.replace("\\", "/").split("data/", 1)[-1]
                    rel_path = f"viewer/{rel_path.replace('/', '%2F')}"
                else:
                    rel_path = path.replace("\\", "/")
                if pages:
                    ref = f"https://digtvbg.com/files/LINUX/Brikman%20Y.%20Terraform.%20Up%20and%20Running.%20Writing...as%20Code%203ed%202022.pdf#page={pages}"
                else:
                    ref = f"{base_url.rstrip('/')}/{rel_path}"

            # Guardar ref en metadata
            if ref:
                try:
                    md["ref"] = ref
                except Exception:
                    pass

            doc_score = DocumentScore(
                content=hit.get("content", ""),
                metadata=hit.get("metadata", {}),
                relevance_score=float(hit.get("score", 0.0)),  # Score de Qdrant
                source=hit.get("path", "unknown"),
                collection=hit.get("collection", ""),
            )
            raw_documents.append(doc_score)
            
            logger.debug(f"Documento {rank} convertido a DocumentScore",source="retrieval",score=doc_score.relevance_score,source_file=doc_score.source)
        
        logger.info(f"✅ Búsqueda completada",source="retrieval",documents_found=len(raw_documents),scores=[f"{d.relevance_score:.3f}" for d in raw_documents[:5]])
        
        # Actualizar estado
        state["raw_documents"] = raw_documents
        state["documents"] = [doc.content for doc in raw_documents]
        state["documents_metadata"] = [{"metadata": doc.metadata, "source": doc.source, "score": doc.relevance_score} for doc in raw_documents]
        state["messages"].append(
            f"📚 Recuperados {len(raw_documents)} documentos crudos"
        )
        
        return state
        
    except Exception as e:
        logger.error(f"❌ Error durante la recuperación de documentos",source="retrieval",error=str(e),error_type=type(e).__name__,question=question[:100])
        state["messages"].append(f"❌ Error en recuperación: {str(e)}")
        state["raw_documents"] = []
        return state