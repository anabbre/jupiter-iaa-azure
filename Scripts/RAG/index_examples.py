"""
Indexador de ejemplos y documentos PDF en Qdrant
------------------------------------------------
Lee el manifiesto (manifest.yaml), genera embeddings y sube los puntos a Qdrant.
Compatible con ejemplos Terraform (textos) y PDFs como el libro de Terraform.
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


# Logging
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

    fh = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3)
    fh.setLevel(logging.INFO)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger


logger = setup_logger()

# Config
load_dotenv()
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

# DETECCIÓN DE ENTORNO PARA RUTAS
if os.path.exists("/app/data/docs/examples/manifest.yaml"):
    # Ruta dentro del contenedor AWS
    MANIFEST_PATH = "/app/data/docs/examples/manifest.yaml"
    logger.info("🌐 Entorno detectado: AWS ECS")
else:
    # Ruta en en ordenador en local
    MANIFEST_PATH = os.getenv("EXAMPLES_MANIFEST", "docs/examples/manifest.yaml")
    logger.info("💻 Entorno detectado: Local")

TEXT_EXTS = {".tf", ".md", ".txt", ".yaml", ".yml", ".tfvars", ".sh"}
splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)


# Helpers
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
                # para ejemplos no hay página; ref = ruta del archivo
                d.metadata["ref"] = str(p)
                docs.append(d)
    return docs


def collect_chunks_from_pdf(pdf_path: Path, section: str) -> List[dict]:
    loader = PyPDFLoader(str(pdf_path))
    pages = loader.load()
    docs = []
    for pg in pages:
        pg.metadata["source"] = str(pdf_path)
        pg.metadata["section"] = section
        pg.metadata["doc_type"] = "book"
        # Qdrant/loader devuelve page base 0; la dejamos base 1
        page_num = int(pg.metadata.get("page", 0)) + 1
        pg.metadata["page"] = page_num
        # ref clicable con ancla de página
        pg.metadata["ref"] = f"{pdf_path}#page={page_num}"
        docs.extend(splitter.split_documents([pg]))
    return docs


# Main
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=str,
        default=None,
        help="Ruta al manifest.yaml (override de EXAMPLES_MANIFEST)",
    )
    args = parser.parse_args()

    manifest_path = args.manifest or MANIFEST_PATH
    logger.info("🚀 Inicio de indexación")
    logger.info(f"QDRANT_URL={QDRANT_URL}")
    manifest = load_manifest(manifest_path)

    collection_name = manifest["collection"]
    model_name = manifest.get("embeddings_model", "intfloat/multilingual-e5-small")
    examples = manifest.get("examples", [])
    if not examples:
        logger.warning("Manifiesto sin ejemplos.")
        return

    model = SentenceTransformer(model_name)
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

    # crea colección si no existe
    existing = [c.name for c in client.get_collections().collections]
    if collection_name not in existing:
        logger.info(f"Creando colección '{collection_name}'…")
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=model.get_sentence_embedding_dimension(),
                distance=Distance.COSINE,
            ),
        )

    points: List[PointStruct] = []

    for ex in examples:
        ex_id = ex["id"]
        name = ex.get("name", ex_id)
        filename = ex["path"]  # Ej: "example_frontdoor.md"
        tags = ex.get(
            "tags", []
        )  # <--- FIJAR AQUÍ: Definimos tags para que no de NameError

        # 1. DETERMINAR RUTAS SEGÚN ENTORNO
        if os.path.exists("/app/data/docs/examples"):
            base_docs = Path("/app/data/docs/examples")
            base_terraform = Path("/app/data/terraform")
        else:
            base_docs = Path("data/docs/examples")
            base_terraform = Path("data/terraform")

        path_md = base_docs / filename

        # Lógica robusta para la carpeta de código (Prueba nombre exacto y con prefijo)
        # Intentamos '01-storage-static-website' (basado en ex_id[2:] + name)
        # ex_id[2:] quita el 'ex' y deja el '01', '02'...
        folder_name = f"{ex_id[2:]}-{name}"
        path_code = base_terraform / folder_name

        # Si no existe así, probamos solo con el name
        if not path_code.exists():
            path_code = base_terraform / name

        # 2. PROCESAR EL ARCHIVO MD (Explicación)
        docs = []
        if path_md.exists():
            logger.info(f"[{ex_id}] Indexando explicación: {path_md}")
            loader = TextLoader(str(path_md), encoding="utf-8")
            docs.extend(splitter.split_documents(loader.load()))

        # 3. PROCESAR LA CARPETA TERRAFORM (Código)
        if path_code.exists() and path_code.is_dir():
            logger.info(f"[{ex_id}] Indexando código en: {path_code}")
            docs.extend(collect_chunks_from_text(path_code, str(path_code)))

        if not docs:
            logger.warning(
                f"[{ex_id}] No se encontró ni MD ni código en {path_md} o {path_code}"
            )
            continue

        logger.info(f"[{ex_id}] Generando embeddings ({len(docs)} chunks)…")
        vectors = model.encode(
            [d.page_content for d in docs],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

        for i, d in enumerate(docs):
            meta = d.metadata or {}
            # Definimos 'path' para que se use en la metadata de abajo
            current_path = meta.get("source", str(path_md))

            points.append(
                PointStruct(
                    id=uuid.uuid4().hex,
                    vector=vectors[i].tolist(),
                    payload={
                        "page_content": d.page_content,
                        "metadata": {
                            "type": "terraform_example",
                            "ex_id": ex_id,
                            "name": name,
                            "tags": tags,  # <--- Ahora esta variable SÍ existe
                            "section": str(Path(current_path).as_posix()),
                            "source": str(Path(current_path).name),
                            "path": str(current_path),
                            "page": meta.get("page"),
                            "doc_type": meta.get("doc_type", "example"),
                            "ref": meta.get("ref", str(current_path)),
                        },
                    },
                )
            )

        logger.info(f"[{ex_id}] ✅ {len(docs)} chunks preparados")

    if not points:
        logger.warning("No se generaron puntos. Nada que subir.")
        return

    logger.info(f"Subiendo {len(points)} puntos a Qdrant…")
    client.upsert(collection_name=collection_name, points=points)
    logger.info("✅ Indexación completada con éxito.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.exception(f"❌ Error inesperado: {e}")
        sys.exit(1)
