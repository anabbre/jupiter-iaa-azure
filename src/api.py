import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException

from schemas import QueryRequest, QueryResponse, HealthResponse, SourceInfo
from config.project_config import SETTINGS
from agent import RAGAgent

from utils.aux_qdrant_ingest import ingest_document

router = APIRouter()


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


@app.get("/")
async def read_root():
    return {"message": "Welcome to the RAG and Semantic Search API"}


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
    """Comprueba el estado del sistema y de la colección Qdrant configurada"""
    try:
        client = SETTINGS.qdrant_client
        # Intenta obtener información solo de la colección configurada
        collection_info = client.get_collection(collection_name=SETTINGS.qdrant_collection)
        db_info = rag_agent.get_db_info()  # mantiene tu lógica de comprobación general
        status = "ok"
        message = f"Collection '{SETTINGS.qdrant_collection}' is accessible"
        documents_count = collection_info.vectors_count  # ✅ solo la colección deseada

    except Exception as e:
        status = "error"
        message = f"Error: {e}"
        documents_count = 0
        db_info = {"status": "disconnected"}

    return HealthResponse(
        status=status,
        message=message,
        vector_db_status=db_info["status"],
        documents_count=documents_count
    )

# app/api/routes/ingest.py


@router.post("/ingest")
async def ingest_file(file: UploadFile = File(...)):
    """
    Sube un documento al vector store (PDF, TXT, DOCX, etc.).
    """
    try:
        content = await file.read()
        await ingest_document(file.filename, content)
        return {"status": "ok", "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

