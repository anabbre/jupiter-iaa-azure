import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import sys
from src.Agent.graph import Agent
sys.path.append('/app')  # Asegura que /app esté en PYTHONPATH
from config.config import SETTINGS
from src.services.search import search_examples
from config.logger_config import logger
from src.services.search import search_examples
# OpenAI (v1 SDK). Si no hay API key, haremos fallback.
from openai import OpenAI
from .schemas import (
    HealthResponse,
    QueryRequest,
    QueryResponse,
    SourceInfo,
)



app = FastAPI(
    title="Terraform RAG Assistant API",
    description="API para consultar documentación de Terraform usando RAG",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = Agent()  # reservado para fases posteriores
executor = ThreadPoolExecutor(max_workers=5)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
USE_LLM = bool(OPENAI_API_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY) if USE_LLM else None

# Helpers LLM 
MIN_SCORE_THRESHOLD = 0.5  # Score mínimo de similitud (0-1)
MIN_RESULTS_REQUIRED = 0   # Mínimo de resultados relevantes
MAX_CONTEXT_CHARS = 6000  # límite de contexto para el prompt
CODE_LANG = "hcl"         # resaltado para Terraform


def _gather_context(hits: List[dict]):
    snippets = []
    for hit in hits:  
        snippets.append(f"# {hit['name']}\n{hit['content']}")
    return snippets


def _trim_context(snippets: List[str], max_chars: int = MAX_CONTEXT_CHARS) -> str:
    """
    Concatena y recorta para no exceder el tamaño máximo.
    """
    joined, acc = [], 0
    for s in snippets:
        if acc + len(s) > max_chars:
            joined.append(s[: max(0, max_chars - acc)])
            break
        joined.append(s)
        acc += len(s)
    return "\n\n---\n\n".join(joined)

def _validate_results_quality(hits):
    """
    Valida si los resultados tienen suficiente calidad.
    
    Returns:
        (es_valido, mensaje)
    """
    if not hits:
        return False, "No hay documentos"
    
    return True, "OK"

def _llm_answer_no_hallucination(question: str, context: str, hits: List[dict]) -> str:
    """
    Genera respuesta SIN HALLUCINATIONS.
    Si no hay contexto suficiente, lo rechaza.
    """
    if not USE_LLM:
        return (
            "Información disponible basada en la base de datos:\n\n"
            f"```{CODE_LANG}\n{context[:1200]}\n```"
        )

    system = (
        "REGLAS CRÍTICAS:\n"
        "1. SOLO responde basándote en el contexto proporcionado\n"
        "2. NO inventes recursos, módulos ni configuraciones que no estén en el contexto\n"
        "3. NO hagas suposiciones ni generalizaciones\n"
        "4. Si el contexto no responde a la pregunta, di: 'No tengo información sobre esto en mi base de datos'\n"
        "5. Si necesitas información externa, indícalo claramente\n"
        "6. Responde de forma estructurada y concisa\n"
        "7. Cuando muestres código, asegúrate de que está EXACTAMENTE en el contexto\n"
        "\n"
        "Eres un asistente de documentación de Terraform. Tu única fuente de verdad es el contexto."
    )

    user = (
        f"PREGUNTA: {question}\n\n"
        f"CONTEXTO DISPONIBLE:\n{context}\n\n"
        f"INSTRUCCIONES:\n"
        f"- Responde SOLO con lo que está en el contexto\n"
        f"- Si la pregunta no se responde con el contexto, recházala\n"
        f"- Estructura la respuesta de forma clara\n"
        f"- Cita la fuente cuando sea posible"
    )

    try:
        resp = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.1,  # MUY bajo para evitar hallucinations
            max_tokens=2000,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        
        text = resp.choices[0].message.content.strip()
        return text
    except Exception as e:
        logger.error(f"Error en LLM: {e}", source="api")
        return "Error al procesar la respuesta. Intenta de nuevo."

# Endpoints 

@app.get("/", response_model=HealthResponse)
async def root():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        message="Terraform RAG Assistant API is running",
        vector_db_status="connected",
        documents_count=None,
    )


@app.post("/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest):
    start_time = time.time()
    try:
        logger.info(f"📨 Nueva consulta", source="api", question=request.question)
        
        result = agent.invoke(request.question, chat_history=request.chat_history)
        
        # Validar que el scope es válido
        if not result.get("is_valid_scope", True):
            logger.warning(f"⚠️ Query rechazada", source="api", question=request.question)
            return QueryResponse(
                answer="❌ La consulta está fuera del scope de Terraform/Azure",
                sources=[],
                question=request.question,
            )
        
        # Extraer respuestas del estado del grafo
        answer = result.get("answer", "")
        documents = result.get("raw_documents", [])
        
        # Validar que encontró documentos
        if not documents:
            logger.warning(f"⚠️ Sin documentos encontrados", source="api", question=request.question)
            return QueryResponse(
                answer="❌ No encontré documentos relevantes en la base de datos",
                sources=[],
                question=request.question,
            )
        # Construir sources desde documentos del grafo
        sources = []
        for doc in documents:
            sources.append(
                SourceInfo(
                    name=doc.metadata.get("name", doc.source),  
                    path=doc.source,                             
                    section=doc.metadata.get("section", ""),
                    pages=doc.metadata.get("pages", "-")
                )
            )
        response_time_ms = (time.time() - start_time) * 1000
        logger.info("✅ Respuesta completada",source="api",documents_count=len(documents),response_time_ms=round(response_time_ms, 2))
        
        return QueryResponse(
            answer=answer,
            sources=sources,
            question=request.question,
        )
        
    except Exception as e:
        logger.error(f"❌ Error crítico",source="api",error=str(e),error_type=type(e).__name__)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/debug/test-search")
async def debug_test_search(question: str = "What is terraform?"):
    """
    Prueba la búsqueda en Qdrant directamente
    Muestra exactamente qué retorna search_examples()
    """
    try:
        logger.info(f"🔍 Test search iniciado",source="api",question=question)
        from src.services.search import search_examples
        # Llamar search_examples d irectamente
        hits = search_examples(query=question, k=5, threshold=0.0)
        
        logger.info(f"Test search completado",source="api",hits_count=len(hits),first_hit=str(hits[0]) if hits else "NO HITS")
        
        return {
            "question": question,
            "hits_count": len(hits),
            "hits": hits,
            "raw_data": [
                {
                    "name": h.get("name"),
                    "score": h.get("score"),
                    "doc_type": h.get("doc_type"),
                    "path": h.get("path")
                }
                for h in hits
            ]
        }
    except Exception as e:
        logger.error(
            f"❌ Error en test search: {e}",
            source="api",
            error_type=type(e).__name__
        )
        return {
            "error": str(e),
            "error_type": type(e).__name__
        }


@app.post("/debug/vector-store-search")
async def debug_vector_store_search(question: str = "What is terraform?"):
    """
    Prueba directamente vector_store.similarity_search()
    (Sin procesamiento de search_examples)
    """
    try:
        logger.info(
            f"🔍 Vector store search iniciado",
            source="api",
            question=question
        )
        
        from src.services.vector_store import vector_store
        
        # Llamar directamente
        docs = vector_store.similarity_search(question, k=5)
        
        logger.info(
            f"Vector store search completado",
            source="api",
            docs_count=len(docs)
        )
        
        return {
            "question": question,
            "docs_count": len(docs),
            "docs": [
                {
                    "page_content": d.page_content[:200] if d.page_content else "",
                    "metadata": d.metadata
                }
                for d in docs
            ]
        }
    except Exception as e:
        logger.error(
            f"❌ Error en vector store search: {e}",
            source="api",
            error_type=type(e).__name__
        )
        return {
            "error": str(e),
            "error_type": type(e).__name__
        }


@app.get("/debug/embeddings-model")
async def debug_embeddings_model():
    """Verifica qué modelo de embeddings está en uso"""
    try:
        from src.services.embeddings import embeddings_model
        
        logger.info(f"📦 Info modelo embeddings",source="api")
        
        return {
            "status": "ok",
            "model": str(embeddings_model),
            "model_type": type(embeddings_model).__name__
        }
    except Exception as e:
        logger.error(f"❌ Error verificando embeddings: {e}", source="api")
        return {
            "error": str(e)
        }