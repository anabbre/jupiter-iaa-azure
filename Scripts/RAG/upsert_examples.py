"""
Lee el JSONL generado por Scripts/RAG/index_examples.py y hace upsert en Qdrant
usando el embeddings_model y el cliente/VectorStore que ya tienes en src/services.
No toca PDFs ni otras colecciones.
"""

from pathlib import Path
import json
import os
import time
from typing import Dict, Any, List

from src.services.embeddings import embeddings_model
from config.config import SETTINGS
from config.logger_config import logger, get_request_id, set_request_id

# Usamos directamente las clases de LangChain para Qdrant,
# igual que en tu vector_store.py, pero sin modificar ese archivo.
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient


INPUT_JSONL = Path("data/index/examples_terraform.jsonl")

# Carga de registros JSONL 
def load_records(jsonl_path: Path) -> List[Dict[str, Any]]:
    if not jsonl_path.exists():
        raise FileNotFoundError(f"No existe el JSONL de entrada: {jsonl_path}")
    records: List[Dict[str, Any]] = []
    start_time = time.time()
    try:
        with jsonl_path.open("r", encoding="utf-8") as f:
            for idx, line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as e:
                    logger.warning(f"⚠️ Línea {idx} inválida en JSONL, omitida",source="qdrant",line_num=idx, error=str(e))
                    continue
        load_duration = time.time() - start_time 
        logger.info(f"✅ Cargadas {len(records)} registros de {jsonl_path.name}",source="qdrant",duration=load_duration,total_records=len(records),file=str(jsonl_path))
        return records
    except Exception as e:
        logger.error(f"❌ Error al cargar JSONL",source="qdrant",file=str(jsonl_path),error_detail=str(e))


def get_qdrant_client() -> QdrantClient:
    # Soporta URL y opcional API key está en SETTINGS
    try: 
        kwargs = {"url": SETTINGS.QDRANT_URL}
        if hasattr(SETTINGS, "QDRANT_API_KEY") and SETTINGS.QDRANT_API_KEY:
            kwargs["api_key"] = SETTINGS.QDRANT_API_KEY
        return QdrantClient(**kwargs)
    except Exception as e:
        logger.error(f"❌ Error al crear cliente Qdrant",source="qdrant",url=SETTINGS.QDRANT_URL,error_detail=str(e))


def upsert_examples(
    jsonl_path: Path = INPUT_JSONL,
    collection_name: str = "examples_terraform",
) -> None:
    logger.info(f"🚀 Inicio de upsert a colección '{collection_name}'", source="qdrant", collection=collection_name)
    records = load_records(jsonl_path)
    if not records:
        logger.warning("⚠️  No hay registros para indexar.", source="qdrant")
        return
    
    
    # Preparamos textos y metadatos
    texts: List[str] = []
    metadatas: List[Dict[str, Any]] = []
    ids: List[str] = []

    for r in records:
        txt = r.get("text", "")
        if not txt.strip():
            continue

        texts.append(txt)

        meta = {
            # Campos útiles para la UI y para trazabilidad
            "path": r.get("path"),
            "collection": r.get("collection"),
            "language": r.get("language"),
            "example_dir": r.get("example_dir"),
            "hash": r.get("hash"),
            "chunk_id": r.get("chunk_id"),
        }
        # Mezclamos los metadatos específicos del manifest (provider, topic, …)
        if isinstance(r.get("metadata"), dict):
            meta.update(r["metadata"])
        metadatas.append(meta)

        # ID estable (path + chunk_id + hash corto)
        h = (r.get("hash") or "")[:8]
        ids.append(f"{r.get('path')}:::{r.get('chunk_id')}::{h}")

    logger.info(f"ℹ️ Preparados {len(texts)} chunks para indexar", source="qdrant", chunks_count=len(texts))
    # Cliente y VectorStore 
    qclient = get_qdrant_client()
    vstore = QdrantVectorStore(
        client=qclient,
        collection_name=collection_name,
        embedding=embeddings_model,
    )

    # Upsert
    logger.info(f"🔧 Indexando {len(texts)} chunks en Qdrant (colección: {collection_name})…", source="qdrant", chunks_count=len(texts), collection=collection_name)
    vstore.add_texts(texts=texts, metadatas=metadatas, ids=ids)
    logger.info(f"✅ Upsert completado. {len(texts)} chunks indexados en '{collection_name}'", source="qdrant", chunks_count=len(texts), collection=collection_name)


if __name__ == "__main__":
    # Permite override por variable de entorno si lo necesita en CI
    col = os.getenv("EXAMPLES_COLLECTION_NAME", "examples_terraform")
    try:
        upsert_examples(INPUT_JSONL, col)
    except Exception as e:
        logger.error(f"❌ Error durante upsert: {e}", source="qdrant")
        raise