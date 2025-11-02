# langgraph_agent/nodes/retrieval.py
"""
Nodo de recuperación de documentos
"""
from src.Agent.state import AgentState
from src.services.vector_store import qdrant_vector_store, n_docs


def retrieve_documents(state: AgentState) -> AgentState:
    """
    Busca documentos relevantes en la DB vectorial

    Args:
        state: Estado actual del grafo

    Returns:
        Estado actualizado con documentos recuperados
    """
    question = state["question"]

    # Buscar documentos similares
    docs = qdrant_vector_store.similarity_search(question, k=n_docs)

    # Actualizar estado
    state["documents"] = [doc.page_content for doc in docs]


    state["documents_metadata"] = [
        {
            "metadata": doc.metadata,  # Metadata del documento (página, fuente, etc.)
        }
        for doc in docs
    ]

    state["messages"].append(f"📚 Recuperados {len(docs)} documentos")

    return state

