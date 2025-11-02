from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from src.services.embeddings import embeddings_model_langchain
import os
import logging

logger = logging.getLogger(__name__)

# Cliente de Qdrant - usar variable de entorno para la URL
qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
qdrant_client = QdrantClient(url=qdrant_url)

# Verificar si la colección existe
collection_name = "Terraform_Book_Index"

try:
    # Intentar obtener info de la colección
    collections = qdrant_client.get_collections()
    collection_exists = any(c.name == collection_name for c in collections.collections)

    if not collection_exists:
        logger.warning(f"Collection '{collection_name}' does not exist in Qdrant. Please run the indexing script first.")
    else:
        logger.info(f"Collection '{collection_name}' found in Qdrant")
except Exception as e:
    logger.warning(f"Could not verify collection existence: {e}")

### LANGCHAIN - Sin validación al iniciar
qdrant_vector_store = QdrantVectorStore(
    client=qdrant_client,
    collection_name=collection_name,
    embedding=embeddings_model_langchain
)

n_docs = 3
