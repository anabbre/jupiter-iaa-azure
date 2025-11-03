"""
Nodo de generación de respuestas
"""
from src.Agent.state import AgentState
from src.services.llms import llm


def generate_answer(state: AgentState) -> AgentState:
    """
    Genera una respuesta usando el LLM basándose en los documentos recuperados

    Args:
        state: Estado actual del grafo

    Returns:
        Estado actualizado con la respuesta generada
    """
    question = state["question"]
    context = "\n\n".join(state["documents"])

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

    return state