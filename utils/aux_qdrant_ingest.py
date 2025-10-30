from langchain_core.documents import Document
from uuid import uuid4
from typing import Union
from ingest import index_documents
from config.project_config import SETTINGS


async def ingest_document(filename: str, content: Union[str, bytes]) -> dict:
    """
    Ingresa un único documento en Qdrant, reutilizando la lógica de index_documents().
    """

    # 1️⃣ Asegurarse de que sea texto
    if isinstance(content, bytes):
        try:
            text = content.decode("utf-8", errors="ignore")
        except Exception:
            raise ValueError("No se pudo decodificar el contenido del archivo.")
    else:
        text = content

    # 2️⃣ Crear el documento LangChain
    doc = Document(
        page_content=text,
        metadata={
            "filename": filename,
            "source": f"upload/{filename}",
        },
    )

    # 3️⃣ Indexarlo en Qdrant (sin recrear la colección)
    index_documents([doc], recreate_collection=False)

    # 4️⃣ Respuesta
    return {
        "status": "ok",
        "filename": filename,
        "chunks_ingested": 1,
        "collection": SETTINGS.qdrant_collection,
    }
