import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import sys

from fastapi.responses import FileResponse
from src.Agent.graph import Agent

sys.path.append("/app")  # Asegura que /app esté en PYTHONPATH
from config.config import SETTINGS
from src.services.search import search_examples
from config.logger_config import logger
from src.services.vector_store import vector_store as qdrant_vector_store
from src.services.search import search_examples
from src.services.embeddings import embeddings_model

# OpenAI (v1 SDK). Si no hay API key, haremos fallback.
from openai import OpenAI
from src.api.schemas import (
    HealthResponse,
    QueryRequest,
    QueryResponse,
    SourceInfo,
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


@app.get("/viewer/{path:path}")
def serve_doc(path: str):
    file_path = os.path.join("data", path)
    if not os.path.exists(file_path):
        return {"error": "File not found", "path": file_path}
    return FileResponse(file_path)


from src.services.vector_store import COLLECTIONS, get_collection_info


@app.get("/", response_model=HealthResponse)
async def root():
    """
    Health check endpoint
    """
    docs_info = get_collection_info(COLLECTIONS["docs"])
    documents_count = docs_info.get("points_count") if docs_info else None

    return HealthResponse(
        status="healthy",
        message="Terraform RAG Assistant API LangGraph",
        vector_db_status="connected" if docs_info is not None else "disconnected",
        documents_count=documents_count,
    )


@app.post("/query", response_model=QueryResponse)
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
            # Preparar contexto conversacional opcional
            context = []
            try:
                req_msgs = getattr(request, "context", None)
            except Exception:
                req_msgs = None
            if req_msgs:
                for m in req_msgs[-6:]:
                    role = getattr(m, "role", None)
                    content = getattr(m, "content", None)
                    if role and content:
                        context.append({"role": role, "content": content})

            # Intentar pasar context al agente; fallback si no lo soporta
            try:
                result = agent.invoke(
                    request.question, request.k_docs, request.threshold, context=context
                )
            except TypeError:
                result = agent.invoke(
                    request.question, request.k_docs, request.threshold
                )
            # Extraer respuesta
            answer = result.get("answer", "No se pudo generar respuesta.")
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
            "Error en /query",
            source="api",
            question=request.question[:100] if request else "unknown",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(status_code=500, detail=str(e))


# Endpoints de debug
@app.get("/debug/agent-status")
async def debug_agent_status():
    """Verifica que el Agent este inicializado"""
    agent = Agent()
    return {
        "status": "ok",
        "agent_initialized": agent is not None,
        "graph_compiled": agent.graph is not None if agent else False,
    }


@app.post("/debug/test-agent")
async def debug_test_agent(question: str = "que es terraform?"):
    """Prueba el Agent completo y muestra el flujo"""
    try:
        start = time.time()
        agent = Agent()
        result = agent.invoke(question)
        duration = time.time() - start

        return {
            "question": question,
            "duration_seconds": round(duration, 2),
            "is_valid_scope": result.get("is_valid_scope"),
            "intent": result.get("intent"),
            "intents": result.get("intents"),
            "is_multi_intent": result.get("is_multi_intent"),
            "response_action": result.get("response_action"),
            "target_collections": result.get("target_collections"),
            "documents_count": len(result.get("documents", [])),
            "answer_preview": result.get("answer", "")[:500],
            "messages": result.get("messages", []),
        }
    except Exception as e:
        return {"error": str(e), "error_type": type(e).__name__}


@app.get("/debug/qdrant-status")
async def debug_qdrant_status():
    """Verifica estado de Qdrant y colecciones"""
    try:
        import src.services.vector_store as vs

        # fallback: si la imagen vieja no tiene list_collections, no explota
        if hasattr(vs, "list_collections"):
            all_collections = vs.list_collections()
        else:
            # fallback directo al cliente
            cols = vs.qdrant_client.get_collections()
            all_collections = [c.name for c in getattr(cols, "collections", [])]

        collections_info = {}
        for _, name in vs.COLLECTIONS.items():
            if hasattr(vs, "get_collection_info"):
                collections_info[name] = vs.get_collection_info(name)
            else:
                # mínimo viable
                collections_info[name] = {"exists": name in all_collections}

        return {
            "status": "connected",
            "url": vs.SETTINGS.QDRANT_URL,
            "all_collections": all_collections,
            "collections_info": collections_info,
            "vector_store_has_list_collections": hasattr(vs, "list_collections"),
            "vector_store_file": getattr(vs, "__file__", "unknown"),
        }

    except Exception as e:
        logger.error(f"Error verificando Qdrant: {e}", source="api")
        return {"status": "error", "error": str(e)}


@app.post("/debug/test-search")
async def debug_test_search(question: str = "que es terraform?"):
    """Prueba search_examples directamente"""
    try:
        from src.services.search import search_examples

        # Llamar search_examples directamente
        hits = search_examples(
            query=question, k=SETTINGS.K_DOCS, threshold=SETTINGS.THRESHOLD
        )

        logger.info(
            f"Test search completado",
            source="api",
            hits_count=len(hits),
            first_hit=str(hits[0]) if hits else "NO HITS",
        )

        return {
            "question": question,
            "hits_count": len(hits),
            "hits": [
                {
                    "name": h.get("name"),
                    "score": h.get("score"),
                    "doc_type": h.get("doc_type"),
                    "collection": h.get("collection"),
                    "content_preview": h.get("content", "")[:200],
                }
                for h in hits
            ],
        }
    except Exception as e:
        return {"error": str(e), "error_type": type(e).__name__}


@app.get("/debug/embeddings-model")
async def debug_embeddings_model():
    """Verifica modelo de embeddings"""
    try:
        from src.services.embeddings import embeddings_model

        return {
            "status": "ok",
            "model": str(embeddings_model),
            "model_type": type(embeddings_model).__name__,
        }
    except Exception as e:
        return {"error": str(e)}
