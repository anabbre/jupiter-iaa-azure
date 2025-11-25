# logger_config.py
import os
import sys
import json
import logging
import uuid
import traceback
from loguru import logger
from contextvars import ContextVar

# Estructura de carpetas:
# Estructura de carpetas:
# logs/
# ├── errors.txt             # Errores globales
# ├── performance.txt        # Performance global
# ├── api/
# │   └── api.txt            # Requests/responses de FastAPI
# ├── qdrant/
# │   └── qdrant.txt         # Proceso de indexación de documentos
# ├── search/
# │   └── search.txt         # Búsquedas en Qdrant
# ├── ui/
# │   └── ui.txt             # Búsquedas en Qdrant




# Variables de contexto para rastrear requests
request_id_var: ContextVar[str] = ContextVar('request_id', default=None)
user_session_var: ContextVar[str] = ContextVar('user_session', default=None)

# Crear carpeta logs si no existe
os.makedirs("logs", exist_ok=True)
os.makedirs("logs/api", exist_ok=True)
os.makedirs("logs/qdrant", exist_ok=True)
os.makedirs("logs/agent", exist_ok=True)
os.makedirs("logs/search", exist_ok=True)
os.makedirs("logs/ui", exist_ok=True)

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

# Formato para consola (con colores)
LOG_FORMAT = (
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

# # Función para serializar logs en JSON personalizado
# def serialize(record):
#     # Función auxiliar para convertir objetos no serializables a string como los docs PDFs
#     def default_handler(obj):
#         # Si es un objeto Document o similar, conviértelo a string
#         if hasattr(obj, '__dict__'):
#             return str(obj)
#         return str(obj)
#     # Estructura
#     log_record = {
#         "timestamp": record["time"].isoformat(),
#         "level": record["level"].name,
#         "message": record["message"],
#         "module": record["module"],
#         "function": record["function"],
#         "line": record["line"],
#         "request_id": get_request_id(),
#         "session_id": get_session_id(),
#         "extra": record["extra"]
#     }
#     if record["exception"]:
#         exc = record["exception"]
#         log_record["exception"] = {
#             "type": exc.type.__name__,
#             "value": str(exc.value),
#             "traceback": "".join(traceback.format_exception(exc.type, exc.value, exc.traceback))
#         }
#     return json.dumps(log_record, ensure_ascii=False, default=default_handler)

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
    format=LOG_FORMAT,
    colorize=True
)

# ============ ARCHIVOS DE LOGS ============
# Log solo de errores
logger.add(
    "logs/errors.txt",
    format=FILE_FORMAT + "\n",
    level="ERROR",
    rotation="20 MB",
    retention="7 days"
)

# Log global de performance
logger.add(
    "logs/performance.txt",
    format=FILE_FORMAT + "\n",
    level="INFO",
    filter=lambda record: "process_time" in record["extra"] or "duration" in record["extra"],
    rotation="20 MB",
    retention="7 days"
)

# Log API (requests/responses)
logger.add(
    "logs/api/api.txt",
    format=FILE_FORMAT + "\n",
    level="INFO",
    filter=lambda record: record["extra"].get("source") == "api",
    rotation="20 MB",
    retention="7 days"
)

# Log LangGraph
logger.add(
    "logs/agent/agent.txt",
    format=FILE_FORMAT + "\n",
    level="INFO",
    filter=lambda record: record["extra"].get("source") == "agent",
    rotation="20 MB",
    retention="7 days"
)


# Log UI/Gradio
logger.add(
    "logs/ui/ui.txt",
    format=FILE_FORMAT + "\n",
    level="INFO",
    filter=lambda record: record["extra"].get("source") == "ui",
    rotation="20 MB",
    retention="7 days"
)


# Log de Qdrant Indexing
logger.add(
    "logs/qdrant/qdrant.txt",
    format=FILE_FORMAT + "\n",
    level="DEBUG",  # DEBUG para capturar todo el proceso
    filter=lambda record: record["extra"].get("source") == "indexer",
    rotation="50 MB",  # Más grande porque indexación genera muchos logs
    retention="7 days",
    compression="zip"
)

# Search Logs
logger.add(
    "logs/search/search.txt",
    format=FILE_FORMAT + "\n",
    level="INFO",
    filter=lambda record: record["extra"].get("source") == "search",
    rotation="20 MB",
    retention="7 days",
    compression="zip"
)
# Recuperar logs FastAPI
class InterceptHandler(logging.Handler):
    """
    Intercepta logs de FastAPI, Uvicorn, etc
    y los eredirijo a loguru
    """
    def emit(self, record):
        # Obtener correspondencia de nivel 
        level = record.levelname.lower()
        
        try:
            try:
                level = getattr(logger, level)
            except AttributeError:
                level = logger.info
            
            # Quitar llaves para evitar conflictos de formato 
            message = record.getMessage()
            message = message.replace("{", "{{").replace("}", "}}")
            
            # Loguear con contexto
            level(
                record.getMessage(),
                logger_name=record.name,
                filename=record.filename,
                funcName=record.funcName,
                lineno=record.lineno,
                source="api"
            )
        except Exception:
            pass

# Configurar logging del stdlib para capturar FastAPI/Uvicorn
logging.basicConfig(handlers=[InterceptHandler()], level=logging.DEBUG, force=True)

# Nombres de loggers a interceptar
LOGGERS_TO_INTERCEPT = [
    "uvicorn",           # Servidor ASGI
    "uvicorn.access",    # Logs de acceso (GET /query, etc.)
    "uvicorn.error",     # Errores del servidor
    "fastapi",           # Framework
    "starlette",         # Base de FastAPI
]

# Interceptor a loggers específicos
for logger_name in LOGGERS_TO_INTERCEPT:
    logging_logger = logging.getLogger(logger_name)
    logging_logger.handlers = [InterceptHandler()]
    logging_logger.setLevel(logging.DEBUG)
    
# ✅ Silenciar completamente httpx/httpcore (peticiones HTTP internas a Qdrant)
for noisy_logger in ["httpx", "httpcore", "httpcore.connection", "httpcore.http11"]:
    logging.getLogger(noisy_logger).setLevel(logging.CRITICAL)  # Solo críticos
    logging.getLogger(noisy_logger).propagate = False  # No propagar
