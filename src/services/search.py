from typing import List, Dict, Any
import time
from src.services.vector_store import qdrant_vector_store
from config.logger_config import logger, get_request_id, set_request_id



def search_examples(query: str, k: int = 3, threshold: float = 0.0) -> List[Dict[str, Any]]:
    """
    Busca en Qdrant y devuelve metadatos normalizados para el API/UI.
    """
    request_id = get_request_id()
    start_time = time.time()
    
    logger.info("ℹ️ Iniciando búsqueda en Qdrant",source="qdrant",request_id=request_id,query=query,k=k,threshold=threshold,query_length=len(query) )
    try:
        search_start = time.time()
        results = qdrant_vector_store.similarity_search(query, k=k)
        search_duration = time.time() - search_start# Tiempo duracion de la busqueda
        # Prioriza 'example' frente a 'pdf' y, dentro, por score si lo hubiera
        def _doc_type(meta: Dict[str, Any]) -> int:
            return 0 if (meta or {}).get("doc_type") == "example" else 1

        results = sorted(
            results,
            key=lambda d: (
                _doc_type(d.metadata or {}),
                - (d.metadata or {}).get("score", 0.0),
            ),
        )

        formatted: List[Dict[str, Any]] = []
        for i, doc in enumerate(results, 1):
            try:
                meta = doc.metadata or {}
                score = float(meta.get("score", 0.0)) if isinstance(meta.get("score"), (int, float)) else 0.0

                # Filtro por threshold
                if threshold > 0.0 and score < threshold:
                    logger.info(f"Resultado filtrado por threshold",source="qdrant",request_id=request_id,score=score,threshold=threshold)
                    continue

                # path con alias posibles 
                path = (
                    meta.get("path")
                    or meta.get("doc_path")
                    or meta.get("source")
                    or meta.get("file")
                    or ""
                )

                # section: si no viene, infiere del penúltimo directorio del path
                section = meta.get("section", "")
                if not section and path:
                    parts = path.strip("/").split("/")
                    if len(parts) >= 2:
                        section = parts[-2]  # p.ej. "06-static-site+https"

                formatted.append({
                    "rank": i,
                    "section": meta.get("section", "") or meta.get("path", ""),
                    "pages": str(meta.get("page")) if meta.get("page") is not None else "-",
                    "path": meta.get("path", ""),
                    "name": meta.get("name", ""),
                    "tags": meta.get("tags", []),
                    "preview": doc.page_content[:200] + "..." if doc.page_content else "",
                    "score": float(meta.get("score", 0.0)) if isinstance(meta.get("score"), (int, float)) else None,
                    "doc_type": meta.get("doc_type", ""),   # para priorizar en UI
                    "ref": meta.get("ref", ""),             # útil para links en UI
                })
            except Exception as doc_error:
                logger.warning("❌ Error procesando documento individual",source="qdrant",request_id=request_id,doc_rank=i,error=str(doc_error),tipo_error=type(doc_error).__name__)
                continue
        total_duration = time.time() - start_time
        # Resumen resultados
        results_summary = [
            {
                "rank": f["rank"],
                "section": f["section"],
                "pages": f["pages"],
                "score": f["score"]
            }
            for f in formatted
        ]
        logger.info("Búsqueda en Qdrant completada exitosamente",source="qdrant",request_id=request_id,query=query,total_results=len(formatted),duration=f"{total_duration:.3f}s" ,threshold=threshold,search_duration=f"{search_duration:.3f}s",process_time=f"{total_duration:.3f}s",results_summary=results_summary,status="success")
        
        return formatted

    except Exception as e:
        logger.error(f"❌ Error en búsqueda Qdrant: {e}")
        return []