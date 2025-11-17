import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.config import SETTINGS
from src.services.search import search_examples
from src.services.vector_store import qdrant_vector_store
from src.api.schemas import QueryRequest, QueryResponse, HealthResponse, SourceInfo
from src.Agent.graph import Agent  
from config.logger_config import logger
from src.services.conversation_store import log_query, log_response, log_error

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
MIN_SCORE_THRESHOLD = 0.5  # Score mínimo de similitud (0-1)
MIN_RESULTS_REQUIRED = 1   # Mínimo de resultados relevantes
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

def _validate_results_quality(hits: List[dict], min_threshold: float = MIN_SCORE_THRESHOLD) -> tuple[bool, str]:
    """
    Valida si los resultados tienen suficiente calidad.
    
    Returns:
        (es_valido, mensaje)
    """
    if not hits:
        return False, "No se encontraron documentos relevantes en la base de datos."
    
    # Verificar que al menos hay un resultado con buen score
    good_results = [h for h in hits if (h.get("score") or 0) >= min_threshold]
    
    if not good_results:
        avg_score = sum(h.get("score", 0) for h in hits) / len(hits)
        return False, (
            f"La información encontrada no es lo suficientemente relevante. "
            f"Score promedio: {avg_score:.2f} (mínimo requerido: {min_threshold}). "
            f"Intenta reformular tu pregunta."
        )
    
    if len(good_results) < MIN_RESULTS_REQUIRED:
        return False, (
            f"Se encontraron solo {len(good_results)} resultado(s) relevante(s). "
            f"Se requieren al menos {MIN_RESULTS_REQUIRED}."
        )
    
    return True, "OK"


# def _llm_answer(question: str, context: str) -> str:
#     """
#     Si hay OPENAI_API_KEY usa el LLM. Si no, devuelve fallback con snippets.
#     """
#     if not USE_LLM:
#         # Fallback: muestra instrucciones + el mejor contexto en bloque de código
#         return (
#             "No tengo acceso al LLM en este entorno, te propongo este fragmento "
#             "extraído de los ejemplos para que lo adaptes:\n\n"
#             f"```{CODE_LANG}\n{context[:1200]}\n```"
#         )

#     system = (
#         "Eres un asistente DevOps experto en Terraform. Responde SOLO con HCL válido "
#         "cuando el usuario pida código. Usa el contexto proporcionado, no inventes "
#         "recursos ni nombres que no estén en el contexto. Si faltan datos, indícalo brevemente."
#     )

#     user = (
#         f"Pregunta: {question}\n\n"
#         "Genera un bloque HCL conciso (y opcionalmente variables/locales) basado en el contexto.\n"
#         "Si el tema es habilitar HTTPS en Azure Static Web Apps, incluye los recursos y referencias mínimas.\n\n"
#         "Contexto:\n"
#         f"{context}"
#     )

#     # Modelo ligero recomendado para código+instrucciones
#     resp = openai_client.chat.completions.create(
#         model="gpt-4o-mini",
#         temperature=SETTINGS.LLM_TEMPERATURE,
#         messages=[
#             {"role": "system", "content": system},
#             {"role": "user", "content": user},
#         ],
#     )

#     text = resp.choices[0].message.content.strip()
#     return text

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
    """Endpoint principal para consultas al vector store de Terraform RAG"""
    start_time = time.time()
    try:
        logger.info(f"📨 Nueva consulta recibida",source="api",question=request.question,k_docs=request.k_docs,threshold=request.threshold)
        
        # 1) nº de docs a recuperar
        k = request.k_docs or SETTINGS.K_DOCS
        threshold = request.threshold or SETTINGS.THRESHOLD
        logger.info(f"Parámetros procesados",source="api",k=k,threshold=threshold)
        
        # 2) Buscar ejemplos en Qdrant (metadatos para UI)
        try:
            hits = search_examples(request.question, k=k, threshold=threshold)
            logger.info(f"✅ Búsqueda exitosa",source="api",hits_count=len(hits))
        except TypeError as te:
            logger.error(f"❌ Error de parámetros en search_examples: {te}",source="api",error_type="TypeError")
            raise HTTPException(status_code=500,detail=f"Error en búsqueda: {str(te)}")

        # VALIDACIÓN DE CALIDAD ✅ CRÍTICO
        is_valid, validation_msg = _validate_results_quality(hits, min_threshold=threshold)
        if not is_valid:
            logger.info(f"⚠️ Resultados rechazados por calidad",source="api",reason=validation_msg,question=request.question)
           
            response_time_ms = (time.time() - start_time) * 1000
            answer = f"❌ {validation_msg}"
            #  RESPUESTA RECHAZADA
            log_response(
                question=request.question,
                answer=answer,
                is_valid=False,
                sources_count=0,
                response_time_ms=response_time_ms
            )
            # Retornar respuesta clara de rechazo
            return QueryResponse(
                answer=f"❌ {validation_msg}",
                sources=[],
                question=request.question,
            )
        
            
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
        logger.info(f"Sources construidos",source="api",sources_count=len(sources))

        # 4) Contexto + LLM / Fallback
        context_snippets = _gather_context(request.question, k=k)
        context = _trim_context(context_snippets, MAX_CONTEXT_CHARS)
        logger.info(f"⌛ Generando respuesta",source="api",context_size=len(context) )
        
        answer = _llm_answer_no_hallucination(request.question, context)
        logger.info(f"✅ Respuesta generada",source="api",question=request.question )
        
        response_time_ms = (time.time() - start_time) * 1000
        
        # 📝 REGISTRAR RESPUESTA EXITOSA
        log_response(
            question=request.question,
            answer=answer,
            is_valid=is_valid,
            sources_count=len(sources),
            response_time_ms=response_time_ms
        )
        print ("\n\nPregunta:", request.question)
        print ("\n\nRespuesta:", answer)
        print ("\n\nFuentes:", sources)
        print ("\n\nContexto usado:", context[:500], "...\n")
        print ("\n\nContexto completo usado:", context_snippets)

        # 5) Responder
        return QueryResponse(
            answer=answer,
            sources=sources,
            question=request.question,
        )
        
    except HTTPException:
            raise
    except Exception as e:
        logger.error(f"❌ Error en /query: {e}",source="api",error_type=type(e).__name__)
        
        # REGISTRAR ERROR conver
        log_error(
            question=request.question if 'request' in locals() and hasattr(request, 'question') else "desconocida",
            error_type=type(e).__name__,
            error_message=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))