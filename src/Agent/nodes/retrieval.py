# langgraph_agent/nodes/retrieval.py
"""
Nodo de recuperación de documentos
"""
from src.Agent.state import AgentState
from src.services.vector_store import qdrant_vector_store, n_docs
from config.logger_config import logger, get_request_id, set_request_id

def retrieve_documents(state: AgentState) -> AgentState:
    """
    Busca documentos relevantes en la DB vectorial

    Args:
        state: Estado actual del grafo

    Returns:
        Estado actualizado con documentos recuperados
    """
    
    question = state["question"]
    try: 
        # Buscar documentos similares
        docs = qdrant_vector_store.similarity_search(question, k=n_docs)

        # Actualizar estado
        state["documents"] = [doc.page_content for doc in docs]
        logger.info(" - Búsqueda completada",source="agent")

        state["documents_metadata"] = [
            {
                "metadata": doc.metadata,  # Metadata del documento (página, fuente, etc.)
            }
            for doc in docs
        ]

        state["messages"].append(f"📚 Recuperados {len(docs)} documentos")
        logger.info("✅ Estado actualizado exitosamente",source="agent")
        return state
    except Exception as e:
        logger.error(f"❌ Error durante la recuperación de documentos", source="agent",error=str(e),tipo_error=type(e).__name__)
        state["messages"].append(f"❌ Error en recuperación: {str(e)}",source="agent")
        raise
