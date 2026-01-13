"""
Indexador MULTI-COLECCIÓN en Qdrant (AWS)

"""

import os
import sys
import yaml
import uuid
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from sentence_transformers import SentenceTransformer
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
import argparse


# --- CONFIGURACIÓN DE LOGS ---
def setup_logger(name: str = "index_examples") -> logging.Logger:
    logs_dir = Path("logs/app")
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "index_examples.log"

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    return logger


logger = setup_logger()

# --- CONFIGURACIÓN DE CONEXIÓN ---
load_dotenv()

# Usamos os.getenv para leer la variable de ECS
# Si no encuentra la variable (en local), usa localhost
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")

QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
S3_BASE_URL = "https://jupiter-iaa-docs.s3.eu-west-1.amazonaws.com/"

BOOK_COLLECTION_NAME = "terraform_book"

# --- DETECCIÓN DE RUTAS ---
if os.path.exists("/app/data/docs/examples/manifest.yaml"):
    # Entorno AWS
    MANIFEST_PATH = "/app/data/docs/examples/manifest.yaml"
    BOOK_DIR = Path("/app/data/optimized_chunks/Libro-TF")
    logger.info("🌐 Entorno detectado: AWS ECS")
else:
    # Entorno Local
    MANIFEST_PATH = os.getenv("EXAMPLES_MANIFEST", "data/docs/examples/manifest.yaml")
    BOOK_DIR = Path("data/optimized_chunks/Libro-TF")
    logger.info("💻 Entorno detectado: Local")

TEXT_EXTS = {".tf", ".md", ".txt", ".yaml", ".yml", ".tfvars", ".sh"}
splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)


# --- FUNCIONES AUXILIARES ---
def load_manifest(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        logger.error(f"No se encontró el manifiesto en {p}")
        sys.exit(1)
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def collect_chunks_from_text(base: Path, section: str) -> List[dict]:
    docs = []
    for p in base.rglob("*"):
        if p.suffix.lower() in TEXT_EXTS:
            loader = TextLoader(str(p), encoding="utf-8")
            for d in splitter.split_documents(loader.load()):
                d.metadata["source"] = str(p)
                d.metadata["section"] = section
                d.metadata["doc_type"] = "example"
                d.metadata["ref"] = str(p)
                docs.append(d)
    return docs


def collect_chunks_from_pdf(pdf_path: Path, section: str) -> List[dict]:
    loader = PyPDFLoader(str(pdf_path))
    try:
        pages = loader.load()
    except Exception as e:
        logger.error(f"❌ Error crítico leyendo PDF {pdf_path}: {e}")
        return []  # Saltamos este archivo y devolvemos lista vacía para seguir vivo
    docs = []
    for pg in pages:
        pg.metadata["source"] = str(pdf_path)
        pg.metadata["section"] = section
        pg.metadata["doc_type"] = "book"
        page_num = int(pg.metadata.get("page", 0)) + 1
        pg.metadata["page"] = page_num
        pg.metadata["ref"] = f"{pdf_path}#page={page_num}"
        docs.extend(splitter.split_documents([pg]))
    return docs


def generate_s3_url(local_path: str, page: int = None) -> str:
    rel_path = Path(local_path).as_posix()
    if "data/" in rel_path:
        clean_path = rel_path[rel_path.find("data/") :]
        web_url = f"{S3_BASE_URL}{clean_path}"
    else:
        web_url = rel_path
    if page:
        return f"{web_url}#page={page}"
    return web_url


def ensure_collection(client, name, vector_size):
    logger.info(f"🧹 RECREANDO colección (Borrado + Creación): '{name}'")
    client.recreate_collection(
        collection_name=name,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )


# --- MAIN ---
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=str, default=None)
    args = parser.parse_args()

    manifest_path = args.manifest or MANIFEST_PATH
    logger.info("🚀 Inicio de indexación MULTI-COLECCIÓN")
    logger.info(f"QDRANT_URL={QDRANT_URL}")

    manifest = load_manifest(manifest_path)

    # Colección 1: Ejemplos
    examples_collection = manifest["collection"]
    # Colección 2: Libro
    book_collection = BOOK_COLLECTION_NAME

    model_name = manifest.get("embeddings_model", "intfloat/multilingual-e5-small")
    examples = manifest.get("examples", [])

    model = SentenceTransformer(model_name)
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

    # 1. Asegurar que AMBAS colecciones existen
    vector_size = model.get_sentence_embedding_dimension()
    ensure_collection(client, examples_collection, vector_size)
    ensure_collection(client, book_collection, vector_size)

    # ==========================================
    # PARTE 1: EJEMPLOS -> 'jupiter_examples'
    # ==========================================
    logger.info(f"--- Procesando EJEMPLOS para '{examples_collection}' ---")
    points_examples: List[PointStruct] = []

    for ex in examples:
        ex_id = ex["id"]
        name = ex.get("name", ex_id)
        filename = ex["path"]
        tags = ex.get("tags", [])

        if os.path.exists("/app/data/docs/examples"):
            base_docs = Path("/app/data/docs/examples")
            base_terraform = Path("/app/data/terraform")
        else:
            base_docs = Path("data/docs/examples")
            base_terraform = Path("data/terraform")

        path_md = base_docs / filename
        folder_name = f"{ex_id[2:]}-{name}"
        path_code = base_terraform / folder_name
        if not path_code.exists():
            path_code = base_terraform / name

        docs = []
        if path_md.exists():
            loader = TextLoader(str(path_md), encoding="utf-8")
            docs.extend(splitter.split_documents(loader.load()))

        if path_code.exists() and path_code.is_dir():
            docs.extend(collect_chunks_from_text(path_code, str(path_code)))

        if not docs:
            continue

        vectors = model.encode(
            [d.page_content for d in docs],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

        for i, d in enumerate(docs):
            meta = d.metadata or {}
            current_path = meta.get("source", str(path_md))
            page_num = meta.get("page")
            final_url = generate_s3_url(current_path, page_num)

            points_examples.append(
                PointStruct(
                    id=uuid.uuid4().hex,
                    vector=vectors[i].tolist(),
                    payload={
                        "page_content": d.page_content,
                        "metadata": {
                            "type": "terraform_example",
                            "status": "active",
                            "ex_id": ex_id,
                            "name": name,
                            "tags": tags,
                            "section": str(Path(current_path).as_posix()),
                            "source": str(Path(current_path).name),
                            "path": str(current_path),
                            "url": final_url.split("#")[0],
                            "page": page_num,
                            "doc_type": meta.get("doc_type", "example"),
                            "ref": final_url,
                        },
                    },
                )
            )

    if points_examples:
        logger.info(
            f"⬆️ Subiendo {len(points_examples)} puntos a '{examples_collection}'..."
        )
        client.upsert(collection_name=examples_collection, points=points_examples)
    else:
        logger.warning("No hay ejemplos para subir.")

    # ==========================================
    # PARTE 2: LIBRO -> 'terraform_book'
    # ==========================================
    logger.info(f"--- Procesando LIBRO para '{book_collection}' ---")
    points_book: List[PointStruct] = []

    if BOOK_DIR.exists():
        pdf_files = sorted(list(BOOK_DIR.glob("*.pdf")))
        logger.info(f"📚 Capítulos encontrados: {len(pdf_files)}")

        for pdf in pdf_files:
            logger.info(f"   📖 {pdf.name}")
            pdf_docs = collect_chunks_from_pdf(pdf, section="Libro Terraform")

            if not pdf_docs:
                continue

            pdf_vectors = model.encode(
                [d.page_content for d in pdf_docs],
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )

            for i, d in enumerate(pdf_docs):
                meta = d.metadata or {}
                current_path = meta.get("source", str(pdf))
                page_num = meta.get("page")
                final_url = generate_s3_url(current_path, page_num)

                points_book.append(
                    PointStruct(
                        id=uuid.uuid4().hex,
                        vector=pdf_vectors[i].tolist(),
                        payload={
                            "page_content": d.page_content,
                            "metadata": {
                                "type": "book",
                                "status": "active",
                                "name": pdf.name,
                                "tags": ["libro", "teoria"],
                                "section": "Libro Terraform",
                                "source": pdf.name,
                                "path": str(current_path),
                                "url": final_url.split("#")[0],
                                "page": page_num,
                                "doc_type": "book",
                                "ref": final_url,
                            },
                        },
                    )
                )
    else:
        logger.warning(f"⚠️ No se encontró la carpeta: {BOOK_DIR}")

    if points_book:
        # Subida por lotes para el libro (que es grande)
        logger.info(f"⬆️ Subiendo {len(points_book)} puntos a '{book_collection}'...")
        batch_size = 100
        for i in range(0, len(points_book), batch_size):
            batch = points_book[i : i + batch_size]
            client.upsert(collection_name=book_collection, points=batch)
            logger.info(f"   📦 Lote {i} subido.")
    else:
        logger.warning("No hay contenido del libro para subir.")

    logger.info("✅ Indexación Multi-Colección finalizada.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.exception(f"❌ Error: {e}")
        sys.exit(1)
