import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models import QueryRequest, QueryResponse, HealthResponse, SourceInfo
from agent import RAGAgent

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

# Inicializar el agente
rag_agent = RAGAgent()

# Thread pool para operaciones síncronas
executor = ThreadPoolExecutor(max_workers=5)


@app.get("/", response_model=HealthResponse)
async def root():
    """Health check endpoint"""
    db_info = rag_agent.get_db_info()

    return HealthResponse(
        status="healthy",
        message="Terraform RAG Assistant API is running",
        vector_db_status=db_info["status"],
        documents_count=db_info.get("count")
    )


@app.post("/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest):
    """Endpoint principal para consultas al agente RAG"""
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            executor,
            rag_agent.query,
            request.question,
            request.k_docs,
            request.temperature
        )

        sources = [SourceInfo(**source) for source in result["sources"]]

        return QueryResponse(
            answer=result["answer"],
            sources=sources,
            question=result["question"]
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Endpoint detallado de health check"""
    db_info = rag_agent.get_db_info()

    return HealthResponse(
        status="healthy",
        message="All systems operational",
        vector_db_status=db_info["status"],
        documents_count=db_info.get("count")
    )

# comando para lanzar la api
# uvicorn api:app --port 8008 --reload