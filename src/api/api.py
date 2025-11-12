import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from config.logger_config import logger, get_request_id, set_request_id
from src.api.schemas import QueryRequest, QueryResponse, HealthResponse, SourceInfo
from src.Agent.graph import Agent
import time

# FastAPI App
app = FastAPI(
    title="Terraform RAG Assistant API",
    description="API para consultar documentación de Terraform usando RAG",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


logger.info("🚀 Inicializando aplicación FastAPI", source="api", app_name="Terraform RAG Assistant API")

# Inicializar el agente LangGraph
agent = Agent()
# Thread pool para operaciones síncronas
executor = ThreadPoolExecutor(max_workers=5)
logger.info("ℹ️ ThreadPoolExecutor inicializado", source="api", max_workers=5)


@app.get("/", response_model=HealthResponse)
async def root():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        message="Terraform RAG Assistant API is running",
        vector_db_status="connected",
        documents_count=None
    )


@app.post("/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest):
    """Endpoint principal para consultas al agente RAG"""
    request_id = get_request_id()
    start_time = time.time()
    
    logger.info("Query request received",source="api",request_id=request_id,endpoint="/query",question_length=len(request.question) if request.question else 0)
    
    try:
        # Preparar datos de entrada para el agente
        input_data = {
            "question": request.question,
            "documents": [],
            "documents_metadata": [],
            "answer": "",
            "messages": []
        }

        # Ejecutar el agente en un thread pool para no bloquear
        logger.info("Ejecutando agente en thread pool",source="api",request_id=request_id,executor_type="ThreadPoolExecutor")
        agent_start_time = time.time()
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            executor,
            agent.invoke,
            input_data
        )
        agent_duration = time.time() - agent_start_time
        logger.info("✅ Agente ejecutado exitosamente",source="api",request_id=request_id,agent_duration=f"{agent_duration:.3f}s",result_keys=list(result.keys()) if isinstance(result, dict) else None,status="success"
        )
        # Construir sources desde los metadatos
        sources = []
        for doc_meta in result.get("documents_metadata", []):
            try:
                metadata = doc_meta.get("metadata", {})
                sources.append(SourceInfo(
                    section=metadata.get("source", "Unknown"),
                    pages=metadata.get("original_pages_range", ""),
                ))
            except Exception as e:
                logger.warning("⚠️ Error procesando metadato de documento",source="api",request_id=request_id,error=str(e),tipo_error=type(e).__name__)
        answer = result.get("answer", "No se pudo generar respuesta")
        total_duration = time.time() - start_time
        logger.info("✅ Query completada exitosamente",source="api",request_id=request_id,total_duration=f"{total_duration:.3f}s",agent_duration=f"{agent_duration:.3f}s",sources_count=len(sources),answer_length=len(answer) if answer else 0,process_time=f"{total_duration:.3f}s",status="completed")
        return QueryResponse(
            answer=result.get("answer", "No se pudo generar respuesta"),
            sources=sources,
            question=request.question
        )

    except Exception as e:
        duration = time.time() - start_time
        logger.error("❌ Error al procesar query",source="api",request_id=request_id,error=str(e),tipo_error=type(e).__name__,duration=f"{duration:.3f}s",process_time=f"{duration:.3f}s",status="failed")
        raise HTTPException(status_code=500, detail=str(e))



# comando para lanzar la api
# uvicorn src.api.api:app --port 8008 --reload

