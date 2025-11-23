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
from config.logger_config import logger, get_request_id, set_request_id
import argparse

# Config 
load_dotenv()
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
MANIFEST_PATH = os.getenv("EXAMPLES_MANIFEST", "data/docs/examples/manifest.yaml")

TEXT_EXTS = {".tf", ".md", ".txt", ".yaml", ".yml", ".tfvars", ".sh"}
splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)


# Helpers 
def load_manifest(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        logger.error(f"❌ No se encontró el manifiesto en {p}", source="qdrant", manifest_path=str(p))
        sys.exit(1)
    with open(p, "r", encoding="utf-8") as f:
        logger.info(f"✅ Manifiesto cargado: {p}", source="qdrant", manifest_path=str(p))
        return yaml.safe_load(f)


def collect_chunks_from_text(base: Path, section: str) -> List[dict]:
    docs = []
    files_processed = 0 # Archivos procesados
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
    logger.info(f"📁 Carpeta '{section}': {files_processed} archivos procesados, {len(docs)} chunks extraídos", source="qdrant", base_path=str(base), files_count=files_processed, chunks_count=len(docs))
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
        pg.metadata["ref"] = f"{pdf_path}?page={page_num}"
        docs.extend(splitter.split_documents([pg]))
    logger.info(f"📁 PDF '{pdf_path.name}': {len(pages)} páginas, {len(docs)} chunks extraídos", source="qdrant", pdf_path=str(pdf_path), pages_count=len(pages), chunks_count=len(docs))
    return docs


# Main 
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=str, default=None,
                        help="Ruta al manifest.yaml (override de EXAMPLES_MANIFEST)")
    args = parser.parse_args()

    manifest_path = args.manifest or MANIFEST_PATH
    logger.info("🚀 Inicio de indexación", source="qdrant", qdrant_url=QDRANT_URL, manifest_path=str(manifest_path))
    
    logger.info(f"QDRANT_URL={QDRANT_URL}")
    manifest = load_manifest(manifest_path)

    collection_name = manifest["collection"]
    model_name = manifest.get("embeddings_model", "intfloat/multilingual-e5-small")
    examples = manifest.get("examples", [])
    if not examples:
        logger.info("⚠️ Manifiesto sin ejemplos.", source="qdrant")
        return
    logger.info(f"ℹ️ Cargando modelo de embeddings: {model_name}", source="qdrant", model_name=model_name)
    model = SentenceTransformer(model_name)
    logger.info(f"🔧 Conectando a Qdrant: {QDRANT_URL}", source="qdrant", qdrant_url=QDRANT_URL)
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

    # crea colección si no existe
    existing = [c.name for c in client.get_collections().collections]
    if collection_name not in existing:
        logger.info(f"📁 Creando colección '{collection_name}'…", source="qdrant", collection_name=collection_name, embedding_dim=model.get_sentence_embedding_dimension())
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=model.get_sentence_embedding_dimension(),
                distance=Distance.COSINE,
            ),
        )
    else:
        logger.info(f"ℹ️ Colección '{collection_name}' ya existe", source="qdrant", collection_name=collection_name)

    points: List[PointStruct] = []

    for ex in examples:
        ex_id = ex["id"]
        name = ex.get("name", ex_id)
        path = Path(ex["path"])
        tags = ex.get("tags", [])
        section = str(path)

        if not path.exists():
            logger.warning(f"[{ex_id}] Ruta inexistente: {path}", source="qdrant", example_id=ex_id, path=str(path))
            continue

        if path.is_file() and path.suffix.lower() == ".pdf":
            logger.info(f"-- [{ex_id}] Indexando PDF: {path}", source="qdrant", example_id=ex_id, example_name=name, path=str(path))
            docs = collect_chunks_from_pdf(path, section)
        elif path.is_dir():
            logger.info(f"-- [{ex_id}] Indexando carpeta: {path}", source="qdrant", example_id=ex_id, example_name=name, path=str(path))
            docs = collect_chunks_from_text(path, section)
        else:
            logger.info(f"-- ⚠️ [{ex_id}] Tipo no reconocido: {path}")
            continue

        if not docs:
            logger.info(f"⚠️ [{ex_id}] Sin contenido legible.", source="qdrant", example_id=ex_id, path=str(path))
            continue

        logger.info(f"ℹ️ [{ex_id}] Generando embeddings ({len(docs)} chunks)…", source="qdrant", example_id=ex_id, chunks_count=len(docs))
        vectors = model.encode(
            [d.page_content for d in docs],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

        for i, d in enumerate(docs):
            meta = d.metadata or {}
            points.append(
                PointStruct(
                    id=uuid.uuid4().hex,
                    vector=vectors[i].tolist(),
                    payload={
                        # lo que LangChain leerá como Document.page_content
                        "page_content": d.page_content,
                        # y su metadata asociada
                        "metadata": {
                            "type": "terraform_example",
                            "ex_id": ex_id,
                            "name": name,
                            "tags": tags,
                            "section": str(Path(path).as_posix()),
                            "source": str(Path(path).name),
                            "path": str(path),
                            "page": meta.get("page"),
                            "doc_type": meta.get("doc_type"),  
                            "ref": meta.get("ref"),            
                        },
                    },
                )
            )

        logger.info(f"[{ex_id}] ✅ {len(docs)} chunks preparados", source="qdrant", example_id=ex_id, chunks_count=len(docs), total_points=len(points))

    if not points:
        logger.info("⚠️ No se generaron puntos. Nada que subir.", source="qdrant")
        return

    logger.info(f"⚙️ Subiendo {len(points)} puntos a Qdrant…", source="qdrant", points_count=len(points), collection_name=collection_name)
    client.upsert(collection_name=collection_name, points=points)
    logger.info(f"✅ Indexación completada con éxito. {len(points)} puntos indexados en '{collection_name}'", source="qdrant", points_count=len(points), collection_name=collection_name)



if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.exception(f"❌ Error inesperado: {e}", source="qdrant", error_type=type(e).__name__)
        sys.exit(1)