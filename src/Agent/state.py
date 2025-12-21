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
    collection: str = ""  # De qué colección viene


class AgentState(TypedDict):
    """Estado compartido entre todos los nodos del grafo"""
    # Input
    question: str
    k_docs: int                     # Número de documentos a recuperar
    threshold: float                 # Umbral de relevancia
    
    # Intent Classification 
    intent: str                         # Intent primario: explanation, code_template, full_example
    intents: List[str]                  # Todos los intents detectados
    is_multi_intent: bool               # Si tiene múltiples intenciones
    target_collections: List[str]       # Colecciones donde buscar
    response_action: str                # Acción: generate_answer, return_template, hybrid_response
    intent_scores: Dict[str, float]     # Scores de cada intent
    
    # Retrieval
    raw_documents: List[DocumentScore]
    documents: List[str]
    documents_metadata: List[Dict[str, Any]]

    # Generation
    answer: str
    template_code: Optional[str]        # Código template (si aplica)
    explanation: Optional[str]          # Explicación (si aplica)

    # Metadata
    messages: Annotated[List[str], add]
    
