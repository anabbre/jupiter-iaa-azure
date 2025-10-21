from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Modelo para la petición de consulta"""

    question: str = Field(..., description="Pregunta para el agente RAG")
    k_docs: Optional[int] = Field(default=3, description="Número de documentos a recuperar")
    temperature: Optional[float] = Field(default=0.0, description="Temperatura del LLM")


class SourceInfo(BaseModel):
    """Información de una fuente consultada"""

    title: str
    url: Optional[str] = ""
    section: Optional[str] = ""
    subsection: Optional[str] = ""
    score: float


class QueryResponse(BaseModel):
    """Modelo para la respuesta del agente"""

    answer: str = Field(..., description="Respuesta generada por el agente")
    sources: List[SourceInfo] = Field(..., description="Fuentes consultadas")
    timestamp: datetime = Field(default_factory=datetime.now)
    question: str = Field(..., description="Pregunta original")


class HealthResponse(BaseModel):
    """Modelo para el health check"""

    status: str
    message: str
    vector_db_status: str
    documents_count: Optional[int] = None
