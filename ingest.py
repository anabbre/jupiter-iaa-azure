from pathlib import Path
from typing import List
import os
import re
import json
import shutil

# API moderna de LangChain (>=0.2)
from langchain.schema import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

from dotenv import load_dotenv
load_dotenv()

# -------- Config --------
BASE_DIR = Path("knowledge-base-terraform")
DB_DIR = "src/rag/vector_db"
EMB_MODEL = "text-embedding-3-small"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

IDX_RE = re.compile(r"^(\d{3,})_")  # captura "000_" del nombre

# -------- Carga de docs + metadatos (1:1 por índice) --------
def load_docs_with_metadata(base: Path) -> List[Document]:
    docs: List[Document] = []

    # Recorre solo subdirectorios (cdktf, cli, cloud-docs, internals, etc.)
    for section_dir in sorted([p for p in base.iterdir() if p.is_dir()]):
        # JSON de la sección (uno por carpeta)
        json_files = list(section_dir.glob("*.json"))
        if not json_files:
            print(f"[AVISO] No hay JSON en {section_dir}, salto.")
            continue

        json_path = json_files[0]
        with json_path.open("r", encoding="utf-8") as f:
            meta_list = json.load(f)  # lista en el mismo orden en que generaste los .txt

        # Carpeta con los .txt (puede tener subcarpetas; usamos rglob)
        text_root = section_dir / "text_files"
        if not text_root.exists():
            print(f"[AVISO] No hay text_files en {section_dir}, salto.")
            continue

        txt_paths = sorted(text_root.rglob("*.txt"))  # soporta subcarpetas
        if not txt_paths:
            print(f"[AVISO] Sin .txt en {text_root}, salto.")
            continue

        for txt in txt_paths:
            m = IDX_RE.match(txt.name)
            if not m:
                print(f"[AVISO] No pude extraer índice de {txt.name}, salto.")
                continue

            idx = int(m.group(1))
            if not (0 <= idx < len(meta_list)):
                print(f"[AVISO] Índice {idx} fuera de rango para {txt.name} en {section_dir}.")
                continue

            meta = meta_list[idx]
            content = txt.read_text(encoding="utf-8")

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

        print(f"[OK] {section_dir.name}: {len(txt_paths)} txt ↔ {len(meta_list)} metas (usados: {min(len(txt_paths), len(meta_list))})")

    return docs

# -------- Build index --------
def build_index():
    docs = load_docs_with_metadata(BASE_DIR)
    print(f"Documentos base: {len(docs)}")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP
    )
    chunks = splitter.split_documents(docs)
    print(f"Total de chunks: {len(chunks)}")

    embeddings = OpenAIEmbeddings(model=EMB_MODEL)

    # Limpia el directorio de la DB para evitar residuos de versiones
    if os.path.exists(DB_DIR):
        shutil.rmtree(DB_DIR)

    # Usa SIEMPRE el wrapper moderno de Chroma
    vs = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=DB_DIR
    )

    try:
        count = vs._collection.count()  # puede cambiar en futuras versiones
    except Exception:
        count = "desconocido"
    print(f"Vectorstore creado en {DB_DIR} con {count} embeddings.")

if __name__ == "__main__":
    build_index()
