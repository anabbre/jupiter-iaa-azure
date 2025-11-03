# langgraph_agent/state.py
"""
Define el estado del grafo - aquí agregarás más campos según necesites
"""
from typing import TypedDict, List, Optional, Annotated, Dict, Any
from operator import add

class AgentState(TypedDict):
    """Estado compartido entre todos los nodos del grafo"""
    # Input
    question: str

    # Retrieval
    documents: List[str]
    documents_metadata: List[Dict[str, Any]]

    # Generation
    answer: str

    # Metadata (útil para debugging y expansión futura)
    messages: Annotated[List[str], add]  # Historial de mensajes

