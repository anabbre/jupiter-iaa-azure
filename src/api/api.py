import os
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import sys

from fastapi.responses import FileResponse
from src.Agent.graph import Agent

sys.path.append("/app")  # Asegura que /app esté en PYTHONPATH
from config.config import SETTINGS
from config.logger_config import logger

# OpenAI (v1 SDK). Si no hay API key, haremos fallback.
from src.api.schemas import (
    HealthResponse,
    QueryRequest,
    QueryResponse,
)

app = FastAPI(
    title="Terraform RAG Assistant API",
    description="API para consultar documentacion de Terraform usando RAG con LangGraph",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Endpoints


# Endpoint de health simple
@app.get("/api/health")
@app.get("/health")
async def health():
    """Health check básico"""
    return {"status": "ok"}


@app.get("/viewer/{path:path}")
def serve_doc(path: str):
    file_path = os.path.join("data", path)
    if not os.path.exists(file_path):
        return {"error": "File not found", "path": file_path}
    return FileResponse(file_path)


@app.get("/", response_model=HealthResponse)
async def root():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        message="Terraform RAG Assistant API LangGraph",
        vector_db_status="connected",
        documents_count=None,
    )


@app.post("/api/query", response_model=QueryResponse)  # Llamadas de AWS
@app.post("/query", response_model=QueryResponse)  # Llamadas en local
async def query_endpoint(request: QueryRequest):
    """
    Endpoint principal - Ejecuta el Agent de LangGraph
    """
    start_time = time.time()

    try:

        logger.info(
            f"📨 Nueva consulta recibida",
            source="api",
            question=request.question,
            k_docs=request.k_docs,
            threshold=request.threshold,
        )

        # 1) seteamos parámetros iniciales
        k = request.k_docs or SETTINGS.K_DOCS
        threshold = request.threshold or SETTINGS.THRESHOLD
        logger.info(f"Parámetros procesados", source="api", k=k, threshold=threshold)

        # 2) Invocar agente
        try:
            agent = Agent()
            result = agent.invoke(
                request.question, k, threshold, chat_history=request.chat_history
            )

            # Extraer respuestas del estado del grafo
            answer = result.get("answer", "")
            response_time_ms = (time.time() - start_time) * 1000
            logger.info(
                "Respuesta generada",
                source="api",
                intent=result.get("intent"),
                action=result.get("response_action"),
                is_valid_scope=result.get("is_valid_scope"),
                docs_count=len(result.get("documents", [])),
                response_time_ms=round(response_time_ms, 2),
            )
        except Exception as e:
            logger.error(
                f"❌ Error al llamar al agente: {e}",
                source="api",
                error_type="Exception",
            )
            raise HTTPException(
                status_code=500, detail=f"Error al llamar al agente: {str(e)}"
            )

        # 3) Proceso las fuentes
        try:
            # Construir sources desde documents_metadata
            sources = []
            for source in result.get("raw_documents", []):
                sources.append(source)
            logger.info(f"Fuentes procesadas", source="api", sources_count=len(sources))
            # Validar que encontró documentos
            if result.get("is_valid_scope", True) and not sources:
                logger.warning(
                    f"⚠️ Sin documentos encontrados",
                    source="api",
                    question=request.question,
                )

        except Exception as e:
            logger.error(
                f"❌ Error procesando fuentes: {e}",
                source="api",
                error_type="Exception",
            )

        # 4) Respuesta
        return QueryResponse(
            answer=answer,
            sources=sources,
            question=request.question,
            context=result.get("context_hist", []),
        )

    except Exception as e:
        logger.error(
            "❌ Error crítico",
            source="api",
            question=request.question[:100] if request else "unknown",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(status_code=500, detail=str(e))


# Endpoints de debug
@app.post("/debug/test-search")
async def debug_test_search(question: str = "What is terraform?"):
    """
    Prueba la búsqueda en Qdrant directamente
    Muestra exactamente qué retorna search_examples()
    """
    try:
        logger.info(f"🔍 Test search iniciado", source="api", question=question)
        from src.services.search import search_examples

        # Llamar search_examples d irectamente
        hits = search_examples(query=question, k=5, threshold=0.0)

        logger.info(
            f"Test search completado",
            source="api",
            hits_count=len(hits),
            first_hit=str(hits[0]) if hits else "NO HITS",
        )

        return {
            "question": question,
            "hits_count": len(hits),
            "hits": hits,
            "raw_data": [
                {
                    "name": h.get("name"),
                    "score": h.get("score"),
                    "doc_type": h.get("doc_type"),
                    "path": h.get("path"),
                }
                for h in hits
            ],
        }
    except Exception as e:
        logger.error(
            f"❌ Error en test search: {e}", source="api", error_type=type(e).__name__
        )
        return {"error": str(e), "error_type": type(e).__name__}


@app.post("/debug/vector-store-search")
async def debug_vector_store_search(question: str = "What is terraform?"):
    """
    Prueba directamente vector_store.similarity_search()
    (Sin procesamiento de search_examples)
    """
    try:
        logger.info(f"🔍 Vector store search iniciado", source="api", question=question)

        from src.services.vector_store import vector_store

        # Llamar directamente
        docs = vector_store.similarity_search(question, k=5)

        logger.info(
            f"Vector store search completado", source="api", docs_count=len(docs)
        )

        return {
            "question": question,
            "docs_count": len(docs),
            "docs": [
                {
                    "page_content": d.page_content[:200] if d.page_content else "",
                    "metadata": d.metadata,
                }
                for d in docs
            ],
        }
    except Exception as e:
        logger.error(
            f"❌ Error en vector store search: {e}",
            source="api",
            error_type=type(e).__name__,
        )
        return {"error": str(e), "error_type": type(e).__name__}


@app.get("/debug/embeddings-model")
async def debug_embeddings_model():
    """Verifica qué modelo de embeddings está en uso"""
    try:
        from src.services.embeddings import embeddings_model

        logger.info(f"📦 Info modelo embeddings", source="api")

        return {
            "status": "ok",
            "model": str(embeddings_model),
            "model_type": type(embeddings_model).__name__,
        }
    except Exception as e:
        logger.error(f"❌ Error verificando embeddings: {e}", source="api")
        return {"error": str(e)}
