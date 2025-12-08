"""
Lee el JSONL generado por Scripts/RAG/index_examples.py y hace upsert en Qdrant
usando el embeddings_model y el cliente/VectorStore que ya tienes en src/services.
No toca PDFs ni otras colecciones.
"""

from pathlib import Path
import json
import os
from typing import Dict, Any, List

from src.services.embeddings import embeddings_model
from src.config import SETTINGS

# Usamos directamente las clases de LangChain para Qdrant,
# igual que en tu vector_store.py, pero sin modificar ese archivo.
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient


INPUT_JSONL = Path("data/index/examples_terraform.jsonl")

def load_records(jsonl_path: Path) -> List[Dict[str, Any]]:
    if not jsonl_path.exists():
        raise FileNotFoundError(f"No existe el JSONL de entrada: {jsonl_path}")
    records: List[Dict[str, Any]] = []
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def get_qdrant_client() -> QdrantClient:
    # Soporta URL y opcional API key está en SETTINGS
    kwargs = {"url": SETTINGS.QDRANT_URL}
    if hasattr(SETTINGS, "QDRANT_API_KEY") and SETTINGS.QDRANT_API_KEY:
        kwargs["api_key"] = SETTINGS.QDRANT_API_KEY
    return QdrantClient(**kwargs)


def upsert_examples(
    jsonl_path: Path = INPUT_JSONL,
    collection_name: str = "examples_terraform",
) -> None:
    records = load_records(jsonl_path)
    if not records:
        print("⚠️  No hay registros para indexar.")
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

    # Cliente y VectorStore 
    qclient = get_qdrant_client()
    vstore = QdrantVectorStore(
        client=qclient,
        collection_name=collection_name,
        embedding=embeddings_model,
    )

    # Upsert
    print(f"🔧 Indexando {len(texts)} chunks en Qdrant (colección: {collection_name})…")
    vstore.add_texts(texts=texts, metadatas=metadatas, ids=ids)
    print("✅ Upsert completado.")


if __name__ == "__main__":
    # Permite override por variable de entorno si lo necesita en CI
    col = os.getenv("EXAMPLES_COLLECTION_NAME", "examples_terraform")
    upsert_examples(INPUT_JSONL, col)
