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
# logs/
# ├── errors.json              # Errores globales
# ├── performance.json         # Performance global
# ├── api/
# │   └── api.json
# ├── agent/
# │   └── agent.json
# ├── ui/
# │   └── ui.json
# ├── pdf/
# │   ├── extractor.json
# │   └── schema.json
# └── qdrant/
#     └── qdrant.json


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
    # Función auxiliar para convertir objetos no serializables a string como los docs PDFs
    def default_handler(obj):
        # Si es un objeto Document o similar, conviértelo a string
        if hasattr(obj, '__dict__'):
            return str(obj)
        return str(obj)
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
    print(f"{log_record['timestamp']} | {log_record['level']} | {log_record['module']}:{log_record['function']}:{log_record['line']} | {log_record['message']}")
    if record["exception"]:
        exc = record["exception"]
        log_record["exception"] = {
            "type": exc.type.__name__,
            "value": str(exc.value),
            "traceback": "".join(traceback.format_exception(exc.type, exc.value, exc.traceback))
        }
    return json.dumps(log_record, ensure_ascii=False, default=default_handler)

def serialize_visual(record):
    """
    Serializa el registro de log en un formato visual y legible.
    """
    log_record = [
        f"[{record['time'].strftime('%Y-%m-%d %H:%M:%S')}] [{record['level'].name}]",
        f"Module: {record['module']} | Function: {record['function']} | Line: {record['line']}",
        f"Request ID: {get_request_id()} | Session ID: {get_session_id()}",
        f"Message: {record['message']}"
    ]

    if record["exception"]:
        exc = record["exception"]
        log_record.append("Exception:")
        log_record.append(f"  Type: {exc.type.__name__}")
        log_record.append(f"  Value: {exc.value}")
        log_record.append("  Traceback:")
        log_record.append("    " + "\n    ".join(traceback.format_exception(exc.type, exc.value, exc.traceback)))

    if record["extra"]:
        log_record.append("Extra:")
        for key, value in record["extra"].items():
            log_record.append(f"  {key}: {value}")

    return "\n".join(log_record)

def serialize_compact(record):
    """
    Serializa el registro de log en un formato compacto y legible en una o dos líneas.
    """
    log_record = (
        f"[{record['time'].strftime('%Y-%m-%d %H:%M:%S')}] [{record['level'].name}] "
        f"Module: {record['module']} | Function: {record['function']} | Line: {record['line']} | "
        f"Request ID: {get_request_id()} | Session ID: {get_session_id()} | "
        f"Message: {record['message']}"
    )

    if record["exception"]:
        exc = record["exception"]
        traceback_str = " ".join(traceback.format_exception(exc.type, exc.value, exc.traceback)).replace("\n", " ")
        log_record += (
            f" | Exception: Type: {exc.type.__name__}, Value: {exc.value}, Traceback: {traceback_str}"
        )

    if record["extra"]:
        extra_data = ", ".join([f"{key}: {value}" for key, value in record["extra"].items()])
        log_record += f" | Extra: {extra_data}"

    return log_record

# Patch para añadir campo 'serialized' con JSON
def patching(record):
    # agrega el campo serializado
    record["extra"]["serialized"] = serialize(record)

# Patch para añadir campo 'serialized' con formato visual

def patching_visual(record):
    """
    Agrega el campo serializado con formato visual.
    """
    record["extra"]["serialized"] = serialize_visual(record)

# Patch para añadir campo 'serialized' con formato compacto

def patching_compact(record):
    """
    Agrega el campo serializado con formato compacto.
    """
    record["extra"]["serialized"] = serialize_compact(record)

# Reemplazar el logger global con el nuevo formato compacto
logger.remove()  # Elimina la configuración por defecto
logger = logger.patch(patching_compact)

# handler para consola con formato compacto
logger.add(sys.stderr, level="DEBUG", format="{extra[serialized]}")

# ============ ARCHIVOS DE LOGS CON FORMATO COMPACTO ============

# Log solo de errores
logger.add(
    "logs/errors.log",
    format="{extra[serialized]}",
    level="ERROR",
    rotation="20 MB",
    retention="7 days"
)

# Log timing
logger.add(
    "logs/performance.log",
    format="{extra[serialized]}",
    level="INFO",
    filter=lambda record: "process_time" in record["extra"] or "duration" in record["extra"],
    rotation="20 MB",
    retention="7 days"
)

# Log API (requests/responses)
logger.add(
    "logs/api/api.log",
    format="{extra[serialized]}",
    level="INFO",
    filter=lambda record: record["extra"].get("source") == "api",
    rotation="20 MB",
    retention="7 days"
)

# Log LangGraph
logger.add(
    "logs/agent/agent.log",
    format="{extra[serialized]}",
    level="INFO",
    filter=lambda record: record["extra"].get("source") == "agent",
    rotation="20 MB",
    retention="7 days"
)

# Log UI/Gradio
logger.add(
    "logs/ui/ui.log",
    format="{extra[serialized]}",
    level="INFO",
    filter=lambda record: record["extra"].get("source") == "ui",
    rotation="20 MB",
    retention="7 days"
)

# Log de PDF Extractor
logger.add(
    "logs/pdf/extractor.log",
    format="{extra[serialized]}",
    level="INFO",
    filter=lambda record: record["extra"].get("source") == "pdf_extractor",
    rotation="20 MB",
    retention="7 days"
)

# Log de PDF Schema
logger.add(
    "logs/pdf/pdf_schema.log",
    format="{extra[serialized]}",
    level="INFO",
    filter=lambda record: record["extra"].get("source") == "pdf_schema",
    rotation="20 MB",
    retention="7 days"
)

# Log de Qdrant Indexing
logger.add(
    "logs/qdrant/qdrant.log",
    format="{extra[serialized]}",
    level="INFO",
    filter=lambda record: record["extra"].get("source") == "qdrant",
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

