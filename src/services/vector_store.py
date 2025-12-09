import os
import logging
from typing import List, Optional, Dict, Any
from langchain_core.documents import Document
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse
from langchain_qdrant import QdrantVectorStore

from config.config import SETTINGS  # ✅ Ruta correcta
from src.services.embeddings import embeddings_model
from config.logger_config import logger

qdrant_url = SETTINGS.QDRANT_URL
collection_name = SETTINGS.QDRANT_COLLECTION_NAME or "jupiter_examples"

# Dimensión del embedding que se usa (e5-small => 384)
EMB_DIM = 384  

qdrant_client = QdrantClient(url=qdrant_url)
logger.info(f"ℹ️ Cliente Qdrant inicializado", source="qdrant", url=qdrant_url)
COLLECTIONS = {
    "docs": "terraform_book",
    "examples": "examples_terraform",
    "default": collection_name,
}
def ensure_collection(collection_name: str ) -> bool:
    """
    Crea la colección si no existe.
    """
    target = collection_name 
    
    try:
        qdrant_client.get_collection(target)
        logger.info(f"✅ Colección encontrada", source="qdrant", collection=target)
        return True
    except UnexpectedResponse:
        logger.info(f"⚠️ Colección no existe, creando...", source="qdrant", collection=target)
        try:
            qdrant_client.create_collection(
                collection_name=target,
                vectors_config=models.VectorParams(
                    size=EMB_DIM,
                    distance=models.Distance.COSINE
                ),
            )
            logger.info(f"✅ Colección creada",source="qdrant",collection=target,embedding_dim=EMB_DIM)
            return True
        except Exception as e:
            logger.error(f"❌ Error creando colección", source="qdrant", collection=target, error=str(e))
            return False

def delete_collection(collection_name: str ) -> bool:
    """
    Elimina una colección de Qdrant.
    """
    target = collection_name 
    try:
        qdrant_client.get_collection(target)
        qdrant_client.delete_collection(target)
        logger.info("✅ Colección eliminada", source="qdrant", collection=target)
        return True
    except UnexpectedResponse:
        logger.warning("⚠️ Colección no existe", source="qdrant", collection=target)
        return False
    except Exception as e:
        logger.error("❌ Error eliminando colección", source="qdrant", collection=target, error=str(e))
        return False
def get_collection_info(collection_name: str) -> Optional[Dict[str, Any]]:
    """
    Obtiene información de una colección.
    
    Returns:
        Dict con info de la colección o None si no existe
    """
    target = collection_name 
    
    try:
        info = qdrant_client.get_collection(target)
        return {
            "name": target,
            "points_count": info.points_count,
            "vectors_count": info.vectors_count,
            "status": info.status.value if info.status else "unknown"
        }
    except UnexpectedResponse:
        return None
    except Exception as e:
        logger.error("❌ Error obteniendo info", source="qdrant", collection=target, error=str(e))
        return None


def add_documents_to_collection(
    documents: List[Document],
    collection_name: str
) -> int:
    """
    Añade documentos a una colección de Qdrant.
    """
    target = collection_name 
    
    if not documents:
        logger.warning("⚠️ No hay documentos para añadir", source="qdrant", collection=target)
        return 0
    
    try:
        # Asegurar que la colección existe
        ensure_collection(target)
        # Crear vector store temporal para la colección destino
        target_store = QdrantVectorStore(
            client=qdrant_client,
            collection_name=target,
            embedding=embeddings_model,
            content_payload_key="page_content",
            metadata_payload_key="metadata",
        )
        # Añadir documentos
        target_store.add_documents(documents)
        logger.info("✅ Documentos añadidos",source="qdrant",collection=target,count=len(documents))
        return len(documents)
    except Exception as e:
        logger.error("❌ Error añadiendo documentos",source="qdrant",collection=target,error=str(e))
        raise

def get_vector_store(collection_name: str) -> QdrantVectorStore:
    """
    Obtiene un QdrantVectorStore para una colección específica.
    """
    target = collection_name 
    ensure_collection(target)
    
    return QdrantVectorStore(
        client=qdrant_client,
        collection_name=target,
        embedding=embeddings_model,
        content_payload_key="page_content",
        metadata_payload_key="metadata",
    )

def list_collections() -> List[str]:
    """Lista todas las colecciones en Qdrant."""
    try:
        collections = qdrant_client.get_collections()
        return [c.name for c in collections.collections]
    except Exception as e:
        logger.error("❌ Error listando colecciones", source="qdrant", error=str(e))
        return []

logger.info("⚙️ Verificando colecciones de Qdrant...", source="qdrant")
for key, name in COLLECTIONS.items():
    ensure_collection(name)
    
vector_store = get_vector_store(COLLECTIONS["docs"])
logger.info("✅ Vector store por defecto inicializado",source="qdrant",collection=COLLECTIONS["docs"],)
K_DOCS_DEFAULT = SETTINGS.K_DOCS or 3