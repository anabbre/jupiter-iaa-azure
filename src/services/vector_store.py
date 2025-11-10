import logging
import os

from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse
from langchain_qdrant import QdrantVectorStore

from src.services.embeddings import embeddings_model
from src.config import SETTINGS

logger = logging.getLogger(__name__)

qdrant_url = SETTINGS.QDRANT_URL
collection_name = SETTINGS.QDRANT_COLLECTION_NAME or "jupiter_examples"

# Dimensión del embedding que se usa (e5-small => 384)
# Se toma de env por si algún usuario cambia el modelo
EMB_DIM = int(os.getenv("EMBEDDING_DIM", "384"))

qdrant_client = QdrantClient(url=qdrant_url)

def ensure_collection():
    """Crea la colección si no existe (evita 404 al arrancar con volumen vacío)."""
    try:
        qdrant_client.get_collection(collection_name)
        logger.info(f"Qdrant: colección '{collection_name}' encontrada.")
    except UnexpectedResponse:
        logger.warning(f"Qdrant: colección '{collection_name}' no existe. Creando...")
        qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=EMB_DIM,
                distance=models.Distance.COSINE
            ),
        )
        logger.info(f"Qdrant: colección '{collection_name}' creada.")

# Garantiza la colección antes de usar el VectorStore
ensure_collection()

qdrant_vector_store = QdrantVectorStore(
    client=qdrant_client,
    collection_name=collection_name,
    embedding=embeddings_model,
    content_payload_key="page_content",   # match con el indexador
    metadata_payload_key="metadata",      # match con el indexador
)

# Número de docs por defecto para retrieval
n_docs = SETTINGS.K_DOCS or 3

