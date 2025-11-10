import logging
from typing import List, Dict, Any

from src.services.vector_store import qdrant_vector_store

logger = logging.getLogger(__name__)


def search_examples(query: str, k: int = 3) -> List[Dict[str, Any]]:
    """
    Busca en Qdrant y devuelve metadatos normalizados para el API/UI.
    """
    try:
        results = qdrant_vector_store.similarity_search(query, k=k)

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
                "score": float(meta.get("score", 0.0)) if isinstance(meta.get("score"), (int, float)) else None,
                "doc_type": meta.get("doc_type", ""),   # para priorizar en UI
                "ref": meta.get("ref", ""),             # útil para links en UI
            })

        logger.info(f"📄 {len(formatted)} resultados para '{query}' - "
                    f"{[(f['section'], f['pages']) for f in formatted]}")
        return formatted

    except Exception as e:
        logger.error(f"❌ Error en búsqueda Qdrant: {e}")
        return []
