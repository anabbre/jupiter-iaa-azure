# ingest_fixed.py
import os
import re
import json
import shutil
from pathlib import Path
from typing import List
from uuid import uuid4

from dotenv import load_dotenv
load_dotenv()

# API moderna de LangChain (>=0.2)
from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore
from qdrant_client.models import VectorParams, Distance
from config.project_config import SETTINGS

# -------- Config --------
BASE_DIR = Path(r"knowledge-base-terraform")


IDX_RE = re.compile(r"^(\d{3,})_")  # captura "000_" del nombre

# -------- Carga de docs + metadatos (1:1 por índice) --------
def load_docs_with_metadata(base: Path) -> List[Document]:
    docs: List[Document] = []

    # Recorre solo subdirectorios (cdktf, cli, cloud-docs, internals, etc.)
    for section_dir in sorted([p for p in base.iterdir() if p.is_dir()]):
        # Procesa todos los JSON en el subdirectorio
        json_files = sorted(section_dir.glob("*.json"))
        for json_path in json_files:
            with json_path.open("r", encoding="utf-8") as f:
                try:
                    meta_list = json.load(f)
                except Exception as e:
                    print(f"[ERROR] No se pudo cargar {json_path}: {e}")
                    continue
                # Cada entrada en meta_list se convierte en Document
                for idx, meta in enumerate(meta_list):
                    content = meta.get("content", "")
                    docs.append(
                        Document(
                            page_content=content,
                            metadata={
                                "source": str(json_path),
                                "url": meta.get("url", ""),
                                "title": meta.get("title", ""),
                                "meta_description": meta.get("meta_description", ""),
                                "section": meta.get("section", ""),
                                "subsection": meta.get("subsection", ""),
                                "word_count": meta.get("word_count", 0),
                            }
                        )
                    )

        # Procesa todos los .txt en la subcarpeta text_files
        text_root = section_dir / "text_files"
        if text_root.exists():
            txt_paths = sorted(text_root.rglob("*.txt"))
            for txt in txt_paths:
                content = txt.read_text(encoding="utf-8")
                # Intenta encontrar metadatos en un JSON con el mismo nombre base
                meta = {}
                json_base = txt.with_suffix('.json')
                if json_base.exists():
                    try:
                        with json_base.open("r", encoding="utf-8") as f:
                            meta_list = json.load(f)
                            if isinstance(meta_list, list) and meta_list:
                                meta = meta_list[0]
                            elif isinstance(meta_list, dict):
                                meta = meta_list
                    except Exception as e:
                        print(f"[ERROR] No se pudo cargar metadatos de {json_base}: {e}")
                docs.append(
                    Document(
                        page_content=content,
                        metadata={
                            "source": str(txt),
                            "url": meta.get("url", ""),
                            "title": meta.get("title", ""),
                            "meta_description": meta.get("meta_description", ""),
                            "section": meta.get("section", ""),
                            "subsection": meta.get("subsection", ""),
                            "word_count": meta.get("word_count", 0),
                        }
                    )
                )
        print(f"[OK] {section_dir.name}: {len(json_files)} json, {len(txt_paths) if text_root.exists() else 0} txt procesados.")
    return docs

# -------- Build index --------

# --- Función reutilizable para indexar documentos ---
def index_documents(documents: List[Document], recreate_collection: bool = False):
    qdrant_client = SETTINGS.qdrant_client

    if recreate_collection:
        try:
            qdrant_client.get_collection(SETTINGS.qdrant_collection)
            qdrant_client.delete_collection(SETTINGS.qdrant_collection)
        except Exception:
            pass
        qdrant_client.create_collection(
            collection_name=SETTINGS.qdrant_collection,
            vectors_config=VectorParams(size=3072, distance=Distance.COSINE),
        )

    vector_store = QdrantVectorStore(
        client=qdrant_client,
        collection_name=SETTINGS.qdrant_collection,
        embedding=SETTINGS.embeddings_model
    )

    for document in documents:
        doc_id = str(uuid4())
        vector_store.add_documents(documents=[document], ids=[doc_id])

    print(f"Subidos {len(documents)} documentos a Qdrant en la colección '{SETTINGS.qdrant_collection}'.")

# --- Ingesta inicial: reindexa todo ---
def ingest_initial_documents():
    docs = load_docs_with_metadata(BASE_DIR)
    print(f"Documentos base: {len(docs)}")
    index_documents(docs, recreate_collection=True)

# --- Ingesta incremental: agrega uno o varios documentos ---
def ingest_new_documents(new_docs: List[Document]):
    index_documents(new_docs, recreate_collection=False)

if __name__ == "__main__":
    # Por defecto, ejecuta la ingesta inicial
    ingest_initial_documents()