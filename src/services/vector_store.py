from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from src.services.embeddings import embeddings_model
from config.logger_config import logger, get_request_id, set_request_id
from src.config import SETTINGS
import os
import time

start_time = time.time()
request_id = f"qdrant_init_{int(time.time())}"
set_request_id(request_id)

logger.info("ℹ️ Inicializando Qdrant Vector Store",request_id=request_id,source="data_processing")
try: 
    # Cliente de Qdrant - usar variable de entorno para la URL
    qdrant_url = SETTINGS.QDRANT_URL
    qdrant_client = QdrantClient(url=qdrant_url)

    # Verificar si la colección existe
    collection_name = SETTINGS.QDRANT_COLLECTION_NAME
    
    logger.info(" - Configuración de Qdrant cargada",url=qdrant_url,collection_name=collection_name,request_id=request_id,source="data_processing")

    try:
        # Intentar obtener info de la colección
        collections = qdrant_client.get_collections()
        collection_exists = any(c.name == collection_name for c in collections.collections)

        if not collection_exists:
            collection_info = qdrant_client.get_collection(collection_name=collection_name)
            logger.info("✅ Colección encontrada y verificada",collection_name=collection_name,vectors_count=collection_info.points_count,vector_size=collection_info.config.params.vectors.size if collection_info.config.params.vectors else "N/A",request_id=request_id,source="data_processing")
        else:
            available_collections = [c.name for c in collections.collections]
            logger.info(f"⚠️ Colección no encontrada",collection_solicitada=collection_name,colecciones_disponibles=available_collections,request_id=request_id,source="data_processing")
    except Exception as e:
        logger.error("❌ Error verificando colecciones",error=str(e),tipo_error=type(e).__name__,request_id=request_id,source="data_processing")

    ### LANGCHAIN - Sin validación al iniciar
    qdrant_vector_store = QdrantVectorStore(
        client=qdrant_client,
        collection_name=collection_name,
        embedding=embeddings_model
    )
    logger.info("✅ QdrantVectorStore inicializado exitosamente",collection_name=collection_name,request_id=request_id,source="data_processing")
    n_docs = SETTINGS.K_DOCS or 3
    logger.info("✅ Parámetros configurados",documentos_a_recuperar=n_docs,request_id=request_id,source="data_processing")
    duration = time.time() - start_time
    logger.info("✅ Inicialización de Qdrant Vector Store completada",collection_name=collection_name,documentos_a_recuperar=n_docs,duration=f"{duration:.3f}s",request_id=request_id,source="data_processing",process_time=f"{duration:.3f}s")

except Exception as e:
    duration = time.time() - start_time
    
    logger.error("❌ Error crítico en inicialización de Qdrant",error=str(e),tipo_error=type(e).__name__,url=SETTINGS.QDRANT_URL if 'SETTINGS' in locals() else "N/A",collection_name=SETTINGS.QDRANT_COLLECTION_NAME if 'SETTINGS' in locals() else "N/A",duration=f"{duration:.3f}s",request_id=request_id,source="data_processing",process_time=f"{duration:.3f}s")
    raise

__all__ = [
    'qdrant_client',
    'qdrant_vector_store',
    'collection_name',
    'n_docs'
]