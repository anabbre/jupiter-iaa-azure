from concurrent.futures import ThreadPoolExecutor
import os
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.services.search import search_examples
from src.services.vector_store import qdrant_vector_store
from src.api.schemas import QueryRequest, QueryResponse, HealthResponse, SourceInfo
from src.Agent.graph import Agent  

# OpenAI (v1 SDK). Si no hay API key, haremos fallback.
from openai import OpenAI

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

MAX_CONTEXT_CHARS = 6000  # límite de contexto para el prompt
CODE_LANG = "hcl"         # resaltado para Terraform


def _gather_context(query: str, k: int) -> List[str]:
    """
    Devuelve una lista de fragmentos de texto (page_content) de los k documentos más relevantes.
    """
    docs = qdrant_vector_store.similarity_search(query, k=k)
    snippets: List[str] = []

    for d in docs:
        meta = d.metadata or {}
        header = f"# {meta.get('name', meta.get('path', 'snippet'))}"
        if meta.get("page") is not None:
            header += f" (pág. {meta.get('page')})"
        block = f"{header}\n{d.page_content.strip()}"
        snippets.append(block)

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


def _llm_answer(question: str, context: str) -> str:
    """
    Si hay OPENAI_API_KEY usa el LLM. Si no, devuelve fallback con snippets.
    """
    if not USE_LLM:
        # Fallback: muestra instrucciones + el mejor contexto en bloque de código
        return (
            "No tengo acceso al LLM en este entorno, te propongo este fragmento "
            "extraído de los ejemplos para que lo adaptes:\n\n"
            f"```{CODE_LANG}\n{context[:1200]}\n```"
        )

    system = (
        "Eres un asistente DevOps experto en Terraform. Responde SOLO con HCL válido "
        "cuando el usuario pida código. Usa el contexto proporcionado, no inventes "
        "recursos ni nombres que no estén en el contexto. Si faltan datos, indícalo brevemente."
    )

    user = (
        f"Pregunta: {question}\n\n"
        "Genera un bloque HCL conciso (y opcionalmente variables/locales) basado en el contexto.\n"
        "Si el tema es habilitar HTTPS en Azure Static Web Apps, incluye los recursos y referencias mínimas.\n\n"
        "Contexto:\n"
        f"{context}"
    )

    # Modelo ligero recomendado para código+instrucciones
    resp = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.1,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )

    text = resp.choices[0].message.content.strip()
    return text


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
    """Endpoint principal para consultas al vector store de Terraform RAG"""
    try:
        # 1) nº de docs a recuperar
        k = request.k_docs or 3

        # 2) Buscar ejemplos en Qdrant (metadatos para UI)
        hits = search_examples(request.question, k=k)

        # 3) Construir sources para respuesta
        sources = []
        for h in hits:
            sources.append(
                SourceInfo(
                    section=h.get("section", ""),
                    pages=h.get("pages", "-"),
                    path=h.get("path", ""),
                    name=h.get("name", ""),
                )
            )

        # 4) Contexto + LLM / Fallback
        context_snippets = _gather_context(request.question, k=k)
        context = _trim_context(context_snippets, MAX_CONTEXT_CHARS)
        answer = _llm_answer(request.question, context)

        # 5) Responder
        return QueryResponse(
            answer=answer,
            sources=sources,
            question=request.question,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
