# logger_config.py
import os
import sys
import json
import logging
import uuid
from loguru import logger
from contextvars import ContextVar

# logs/
# ├── app.json              # TODO (mezcla)
# ├── api.json              # Requests/responses de FastAPI
# ├── agent.json            # Ejecuciones del grafo
# ├── ui.json               # Acciones en Gradio
# ├── pdf_extractor.json    # Procesamiento de PDFs
# ├── pdf_schema.json       # Esquemas de PDF
# ├── qdrant.json           # Indexación en Qdrant
# ├── errors.json           # Solo errores
# └── performance.json      # Tiempos de ejecución


# Variables de contexto para rastrear requests
request_id_var: ContextVar[str] = ContextVar('request_id', default=None)
user_session_var: ContextVar[str] = ContextVar('user_session', default=None)

# Crear carpeta logs si no existe
os.makedirs("logs", exist_ok=True)

# ====== Funciones Auxiliares ==========
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

# Función para serializar logs en JSON personalizado
def serialize(record):
    # Estructura
    log_record = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "message": record["message"],
        "module": record["module"],
        "function": record["function"],
        "line": record["line"],
        "request_id": get_request_id(),
        "session_id": get_session_id(),
        "extra": record["extra"]
    }
    if record["exception"]:
        exc = record["exception"]
        log_record["exception"] = {
            "type": exc.type.__name__,
            "value": str(exc.value),
            "traceback": "".join(exc.traceback.format())
        }
    return json.dumps(log_record, ensure_ascii=False)

# Patch para añadir campo 'serialized' con JSON
def patching(record):
    # agrega el campo serializado
    record["extra"]["serialized"] = serialize(record)

# ======== Inicializar logger global ========= 
logger.remove()  # Elimina la configuración por defecto
logger = logger.patch(patching)

# handler para consola
logger.add(sys.stderr, level="DEBUG", format="{extra[serialized]}")

# ============ ARCHIVOS DE LOGS ============
# Log general (TODO)
logger.add(
    "logs/app.json",
    format="{extra[serialized]}\n",
    level="DEBUG",
    rotation="20 MB",
    retention="7 days"
)

# Log solo de errores
logger.add(
    "logs/errors.json",
    format="{extra[serialized]}\n",
    level="ERROR",
    rotation="20 MB",
    retention="7 days"
)

# Log API (requests/responses)
logger.add(
    "logs/api.json",
    format="{extra[serialized]}\n",
    level="INFO",
    filter=lambda record: record["extra"].get("source") == "api",
    rotation="20 MB",
    retention="7 days"
)

# Log LangGraph
logger.add(
    "logs/agent.json",
    format="{extra[serialized]}\n",
    level="DEBUG",
    filter=lambda record: record["extra"].get("source") == "agent",
    rotation="20 MB",
    retention="7 days"
)

# Log de PDF Extractor
logger.add(
    "logs/pdf_extractor.json",
    format="{extra[serialized]}\n",
    level="DEBUG",
    filter=lambda record: record["extra"].get("source") == "pdf_extractor",
    rotation="20 MB",
    retention="7 days"
)

# Log UI/Gradio
logger.add(
    "logs/ui.json",
    format="{extra[serialized]}\n",
    level="DEBUG",
    filter=lambda record: record["extra"].get("source") == "ui",
    rotation="20 MB",
    retention="7 days"
)

# Log de PDF Schema
logger.add(
    "logs/pdf_schema.json",
    format="{extra[serialized]}\n",
    level="DEBUG",
    filter=lambda record: record["extra"].get("source") == "pdf_schema",
    rotation="20 MB",
    retention="7 days"
)

# Log de Qdrant Indexing
logger.add(
    "logs/qdrant.json",
    format="{extra[serialized]}\n",
    level="DEBUG",
    filter=lambda record: record["extra"].get("source") == "qdrant",
    rotation="20 MB",
    retention="7 days"
)

# Log timing
logger.add(
    "logs/performance.json",
    format="{extra[serialized]}\n",
    level="INFO",
    filter=lambda record: "process_time" in record["extra"] or "duration" in record["extra"],
    rotation="20 MB",
    retention="7 days"
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
            level = getattr(logger, level)
        except AttributeError:
            level = logger.info
        
        # Loguear con contexto
        level(
            record.getMessage(),
            logger_name=record.name,
            filename=record.filename,
            funcName=record.funcName,
            lineno=record.lineno,
            source="api"
        )

# Configurar logging del stdlib para capturar FastAPI/Uvicorn
logging.basicConfig(handlers=[InterceptHandler()], level=logging.DEBUG, force=True)

# Nombres de loggers a interceptar
LOGGERS_TO_INTERCEPT = [
    "uvicorn",
    "uvicorn.access",
    "uvicorn.error",
    "fastapi",
    "starlette",
]

# Interceptor a loggers específicos
for logger_name in LOGGERS_TO_INTERCEPT:
    logging_logger = logging.getLogger(logger_name)
    logging_logger.handlers = [InterceptHandler()]
    logging_logger.setLevel(logging.DEBUG)
    
