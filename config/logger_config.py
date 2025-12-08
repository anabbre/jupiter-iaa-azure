# logger_config.py
import os
import sys
import json
import logging
import uuid
import traceback
from loguru import logger
from contextvars import ContextVar




# Variables de contexto para rastrear requests
request_id_var: ContextVar[str] = ContextVar('request_id', default=None)
user_session_var: ContextVar[str] = ContextVar('user_session', default=None)
# Funciones auxiliares para manejar IDs de request y sesión
def get_request_id():
    # Obtiene o crea un ID de peticion
    req_id = request_id_var.get()
    if not req_id:
        req_id = str(uuid.uuid4())[:8]
        request_id_var.set(req_id)
    return req_id
def set_request_id(req_id: str):
    # Establece el id de lla peticion
    request_id_var.set(req_id)
def get_session_id():
    # Obtiene el Id de la request
    return user_session_var.get() or "anonymous"
def set_session_id(session_id: str):
    # Establece Id sesion
    user_session_var.set(session_id)


# ESTRUCTURA DE CARPETAS
# logs/
# ├── errors.log
# ├── performance.log
# ├── api/
# │   └── api.log
# ├── qdrant/
# │   └── qdrant.log
# ├── search/
# │   └── search.log
# ├── agent/
# │   └── agent.log
# └── ui/
#     └── ui.log

# Asegurar que las carpetas de logs existen
LOG_DIRS = [
    "logs",
    "logs/api",
    "logs/qdrant",
    "logs/search",
    "logs/agent",
]

for log_dir in LOG_DIRS:
    os.makedirs(log_dir, exist_ok=True)

# Formato para consola (con colores)
CONSOLE_FORMAT  = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{module}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<yellow>req_id={extra[request_id]}</yellow> | "
    "<level>{message}</level>"
)

# Formato para archivos (sin colores)
FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
    "{level: <8} | "
    "{module}:{function}:{line} | "
    "req_id={extra[request_id]} | "
    "{message}"
)



# Función para formatear el extra como key=value
def format_extra(record):
    """Convierte el dict 'extra' a formato key=value legible"""
    extra = record["extra"]
    
    # Excluir campos internos de loguru
    excluded = {'request_id', 'session_id', 'serialized'}
    
    # Crear string key=value
    parts = []
    for key, value in extra.items():
        if key not in excluded and value is not None:
            # Si el valor es muy largo, truncarlo
            str_value = str(value)
            if len(str_value) > 100:
                str_value = str_value[:97] + "..."
            parts.append(f"{key}={str_value}")
    
    if parts:
        return " | " + " ".join(parts)
    return ""

# Patch para añadir campo 'serialized' con JSON
def patching(record):
    # agrega el campo serializado
    record["extra"]["request_id"] = get_request_id()
    record["extra"]["session_id"] = get_session_id()
    
    # Añadir extras formateados al mensaje
    extra_str = format_extra(record)
    if extra_str:
        record["message"] = record["message"] + extra_str

# Logger configuration
logger.remove()  # Elimina la configuración por defecto
logger = logger.patch(patching)

# Handler para consola (stderr) - CON COLORES
logger.add(
    sys.stderr,
    level="DEBUG",
    format=CONSOLE_FORMAT,
    colorize=True,
)
# ===============================
# LOGS EN ARCHIVOS
# ===============================

# Log solo de errores
logger.add(
    "logs/errors.log",
    format=FILE_FORMAT,
    level="ERROR",
    rotation="20 MB",
    retention="7 days",
    compression="zip",
)

# Performance (logs con process_time o duration)
logger.add(
    "logs/performance.log",
    format=FILE_FORMAT,
    level="INFO",
    filter=lambda r: "process_time" in r["extra"] or "duration" in r["extra"],
    rotation="20 MB",
    retention="7 days",
)
# API (FastAPI requests/responses)
logger.add(
    "logs/api/api.log",
    format=FILE_FORMAT,
    level="INFO",
    filter=lambda r: r["extra"].get("source") == "api",
    rotation="20 MB",
    retention="7 days",
)

# Qdrant (indexación y vector store)
logger.add(
    "logs/qdrant/qdrant.log",
    format=FILE_FORMAT,
    level="DEBUG",
    filter=lambda r: r["extra"].get("source") == "qdrant",
    rotation="50 MB",
    retention="7 days",
    compression="zip",
)

# Search (búsquedas semánticas)
logger.add(
    "logs/search/search.log",
    format=FILE_FORMAT,
    level="INFO",
    filter=lambda r: r["extra"].get("source") == "search",
    rotation="20 MB",
    retention="7 days",
    compression="zip",
)

AGENT_SOURCES = {
    "agent",
    "decision", 
    "generation",
    "intent_classifier",
    "retrieval",
    "validate_scope",
}
# Agent (nodos del agente LangGraph)
logger.add(
    "logs/agent/agent.log",
    format=FILE_FORMAT,
    level="DEBUG",
    filter=lambda r: r["extra"].get("source") in AGENT_SOURCES,
    rotation="30 MB",
    retention="7 days",
    compression="zip",
)
# UI (Gradio interface)
logger.add(
    "logs/ui/ui.log",
    format=FILE_FORMAT,
    level="INFO",
    filter=lambda r: r["extra"].get("source") == "ui",
    rotation="20 MB",
    retention="7 days",
)

# Recuperar logs FastAPI
class InterceptHandler(logging.Handler):
    """Redirige logs de stdlib (FastAPI, Uvicorn) a Loguru."""
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        # Escapar llaves para evitar conflictos de formato
        message = record.getMessage().replace("{", "{{").replace("}", "}}")
        logger.opt(depth=depth, exception=record.exc_info).bind(source="api").log(
            level, message
        )


# Configurar interceptor
logging.basicConfig(handlers=[InterceptHandler()], level=logging.DEBUG, force=True)

LOGGERS_TO_INTERCEPT = [
    "uvicorn",
    "uvicorn.access",
    "uvicorn.error",
    "fastapi",
    "starlette",
]

for logger_name in LOGGERS_TO_INTERCEPT:
    logging_logger = logging.getLogger(logger_name)
    logging_logger.handlers = [InterceptHandler()]
    logging_logger.setLevel(logging.DEBUG)

# Silenciar loggers ruidosos
NOISY_LOGGERS = [
    "httpx",
    "httpcore",
    "httpcore.connection",
    "httpcore.http11",
]

for noisy in NOISY_LOGGERS:
    logging.getLogger(noisy).setLevel(logging.CRITICAL)
    logging.getLogger(noisy).propagate = False







