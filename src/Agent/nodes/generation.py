"""
Nodo de generación de respuestas
"""
from src.Agent.state import AgentState
from src.services.llms import llm
from config.logger_config import logger, get_request_id, set_request_id


def generate_answer(state: AgentState) -> AgentState:
    """
    Genera una respuesta usando el LLM basándose en los documentos recuperados

    Args:
        state: Estado actual del grafo

    Returns:
        Estado actualizado con la respuesta generada
    """
    logger.info(" - Iniciando generación de respuesta",source="agent")
    question = state["question"]
    context = "\n\n".join(state["documents"])
    try:
        # Construir prompt
        prompt = f"""Responde la pregunta basándote en el siguiente contexto:

    Contexto:
    {context}

    Pregunta: {question}

    Respuesta:"""

        # Generar respuesta
        response = llm.invoke(prompt)
        # Actualizar estado
        state["answer"] = response.content
        state["messages"].append("✅ Respuesta generada")
        logger.info("✅ Respuesta generada y estado actualizado exitosamente",source="agent")
        return state
    except Exception as e:
            logger.error("❌ Error durante la generación de respuesta",source="agent",error=str(e),tipo_error=type(e).__name__ )
            state["messages"].append(f"❌ Error en generación: {str(e)}")
            raise