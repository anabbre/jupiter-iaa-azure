# langgraph_agent/state.py
"""
Define el estado del grafo - aquí agregarás más campos según necesites
"""

from typing import TypedDict, List, Optional, Annotated, Dict, Any
from operator import add
from dataclasses import dataclass 

@dataclass
class DocumentScore:
    """Documento con score de relevancia"""
    content: str
    metadata: Dict[str, Any]
    relevance_score: float
    source: str
    line_number: Optional[int] = None
class AgentState(TypedDict):
    """Estado compartido entre todos los nodos del grafo"""
    # Input
    question: str

    # Retrieval
    raw_documents: List[DocumentScore]
    documents: List[str]
    documents_metadata: List[Dict[str, Any]]

    # Generation
    answer: str

    # Metadata (útil para debugging y expansión futura)
    messages: Annotated[List[str], add]  # Historial de mensajes

