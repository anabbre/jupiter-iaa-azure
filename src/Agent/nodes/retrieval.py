"""
Nodo de recuperación de documentos
"""

from src.Agent.state import AgentState
from src.services.vector_store import qdrant_vector_store, n_docs


def retrieve_documents(state: AgentState) -> AgentState:
    """
    Busca documentos relevantes en la DB vectorial.

    Args:
        state: Estado actual del grafo

    Returns:
        Estado actualizado con documentos recuperados
    """
    question = state["question"]

    # Traer documentos + score
    results = qdrant_vector_store.similarity_search_with_score(question, k=n_docs)
    docs = [doc for doc, _ in results]
    scores = [float(score) for _, score in results]

    # Contenido y metadatos "raw"
    state["documents"] = [d.page_content for d in docs]
    state["documents_metadata"] = [d.metadata or {} for d in docs]
    state["scores"] = scores

    state["messages"].append(f"📚 Recuperados {len(docs)} documentos")
    return state
