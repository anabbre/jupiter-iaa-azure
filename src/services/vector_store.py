# import logging
# import os

# from qdrant_client import QdrantClient, models
# from qdrant_client.http.exceptions import UnexpectedResponse
# from langchain_qdrant import QdrantVectorStore

# from src.services.embeddings import embeddings_model
# from src.config import SETTINGS
# from config.logger_config import logger


# qdrant_url = SETTINGS.QDRANT_URL
# collection_name = SETTINGS.QDRANT_COLLECTION_NAME or "jupiter_examples"

# # Dimensión del embedding que se usa (e5-small => 384)
# # Se toma de env por si algún usuario cambia el modelo
# EMB_DIM = 384

# qdrant_client = QdrantClient(url=qdrant_url)
# logger.info(f"ℹ️ Cliente Qdrant inicializado", source="qdrant", url=qdrant_url)
# def ensure_collection():
#     """Crea la colección si no existe (evita 404 al arrancar con volumen vacío)."""
#     try:
#         qdrant_client.get_collection(collection_name)
#         logger.info(f"✅ Colección '{collection_name}' encontrada en Qdrant", source="qdrant", collection=collection_name)
#     except UnexpectedResponse as e:
#         logger.info(f"⚠️ Colección '{collection_name}' no existe. Creando...", source="qdrant", collection=collection_name, error=str(e))
#         qdrant_client.create_collection(
#             collection_name=collection_name,
#             vectors_config=models.VectorParams(
#                 size=EMB_DIM,
#                 distance=models.Distance.COSINE
#             ),
#         )
#         logger.info(f"Colección '{collection_name}' creada exitosamente", source="qdrant", collection=collection_name, embedding_dim=EMB_DIM, distance_metric="COSINE")

# # Garantiza la colección antes de usar el VectorStore
# logger.info("⚙️ Verificando/creando colección de Qdrant", source="qdrant", collection=collection_name)
# ensure_collection()

# qdrant_vector_store = QdrantVectorStore(
#     client=qdrant_client,
#     collection_name=collection_name,
#     embedding=embeddings_model,
#     content_payload_key="page_content",   # match con el indexador
#     metadata_payload_key="metadata",      # match con el indexador
# )

# logger.info(f"✅ QdrantVectorStore inicializado", source="qdrant", collection=collection_name)

# # Número de docs por defecto para retrieval
# n_docs = SETTINGS.K_DOCS or 3