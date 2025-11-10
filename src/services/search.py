import logging
from typing import List, Dict, Any

from src.services.vector_store import qdrant_vector_store, threshold

logger = logging.getLogger(__name__)


def search_examples(query: str, k: int = 3, threshold: float = threshold) -> List[Dict[str, Any]]:
    """
    Busca en Qdrant y devuelve metadatos normalizados para el API/UI.
    """
    try:

        results = qdrant_vector_store.similarity_search_with_score(query, k=k)
        filtered_results = [(doc, score) for doc, score in results if score >= threshold]
        logger.debug(f"🔍 {len(filtered_results)}/{len(results)} resultados sobre umbral {threshold} "
                 f"para consulta '{query}'") if len(results) > 0 else logger.debug(f"🔍 No se encontraron resultados para '{query}'")

        # Imprimir score de cada resultado
        for doc, score in filtered_results:
            meta = doc.metadata or {}
            path = meta.get("path", "N/A")
            doc_type = meta.get("doc_type", "unknown")

        # Prioriza 'example' sobre 'book', luego por score descendente
        def _doc_type(meta: Dict[str, Any]) -> int:
            if (meta or {}).get("doc_type") == "example":
                return 0
            elif (meta or {}).get("doc_type") == "book":
                return 1
            else:
                return 2

        final_results = sorted(
            filtered_results,
            key=lambda pair: (
                _doc_type(pair[0].metadata or {}),
                -pair[1]  # score descendente
            )
        )

        formatted: List[Dict[str, Any]] = []
        logger.debug("Resultados finales ordenados (priorizando doc_type='example'):") if len(final_results) > 0 else None
        for i, (doc, score) in enumerate(final_results, 1):
            meta = doc.metadata or {}
            path = meta.get("path", "N/A")
            doc_type = meta.get("doc_type", "unknown")
            logger.debug(f"  score={score} | path={path} | doc_type={doc_type}")

        formatted: List[Dict[str, Any]] = []
        for i, (doc, score) in enumerate(final_results, 1):
            meta = doc.metadata or {}
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
                "score": float(score),
                "doc_type": meta.get("doc_type", ""),   # para priorizar en UI
                "ref": meta.get("ref", ""),             # útil para links en UI
            })

        logger.info(f"📄 {len(formatted)} resultados para '{query}' - "
                    f"{[(f['section'], f['pages']) for f in formatted]}")
        return formatted

    except Exception as e:
        logger.error(f"❌ Error en búsqueda Qdrant: {e}")
        return []
