import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.api.schemas import QueryRequest, QueryResponse, HealthResponse, SourceInfo
from src.Agent.graph import Agent

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

# Inicializar el agente LangGraph
agent = Agent()

# Thread pool para operaciones síncronas
executor = ThreadPoolExecutor(max_workers=5)


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
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            executor,
            agent.invoke,
            input_data
        )

        # Construir sources desde los metadatos
        sources = []
        for doc_meta in result.get("documents_metadata", []):
            metadata = doc_meta.get("metadata", {})
            sources.append(SourceInfo(
                title=metadata.get("source", "Unknown"),
                url=metadata.get("url", ""),
                section=metadata.get("section", ""),
                subsection=metadata.get("subsection", ""),
                score=metadata.get("score", 0.0)
            ))

        return QueryResponse(
            answer=result.get("answer", "No se pudo generar respuesta"),
            sources=sources,
            question=request.question
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# comando para lanzar la api
# uvicorn src.api.api:app --port 8008 --reload

