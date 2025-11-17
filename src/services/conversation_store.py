import os
from loguru import logger
from config.logger_config import get_request_id, get_session_id

# Crear carpeta si no existe
os.makedirs("logs/conversations", exist_ok=True)

# Configurar handler específico para conversaciones
conversation_logger = logger.bind(source="conversation")

# Agregar handler para conversaciones
conversation_logger.add(
    "logs/conversations/conversations.json",
    format="{extra[serialized]}\n",
    level="INFO",
    filter=lambda record: record["extra"].get("source") == "conversation",
    rotation="50 MB",
    retention="30 days"
)


def log_query(question: str, k_docs: int, threshold: float) -> None:
    """
    Registra una pregunta
    
    Args:
        question: Pregunta del usuario
        k_docs: Número de documentos
        threshold: Threshold de similitud
    """
    conversation_logger.info(
        f"❓ Pregunta",
        type="query",
        question=question,
        k_docs=k_docs,
        threshold=threshold
    )


def log_response(
    question: str,
    answer: str,
    is_valid: bool,
    sources_count: int,
    response_time_ms: float
) -> None:
    """
    Registra una respuesta
    
    Args:
        question: Pregunta original
        answer: Respuesta generada
        is_valid: Si fue válida (pasó validación de calidad)
        sources_count: Cantidad de fuentes usadas
        response_time_ms: Tiempo de respuesta en ms
    """
    conversation_logger.info(
        f"✅ Respuesta" if is_valid else f"❌ Respuesta rechazada",
        type="response",
        question=question,
        answer=answer,
        is_valid=is_valid,
        sources_count=sources_count,
        response_time_ms=response_time_ms
    )


def log_error(question: str, error_type: str, error_message: str) -> None:
    """
    Registra un error
    
    Args:
        question: Pregunta que causó error
        error_type: Tipo de error
        error_message: Mensaje del error
    """
    conversation_logger.error(
        f"❌ Error en consulta",
        type="error",
        question=question,
        error_type=error_type,
        error_message=error_message
    )