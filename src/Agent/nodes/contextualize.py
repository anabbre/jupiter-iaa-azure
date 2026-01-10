# src/Agent/nodes/contextualize.py
"""
Nodo que contextualiza preguntas de follow-up usando el historial.
"""
from src.Agent.state import AgentState
from src.services.llms import llm
from config.logger_config import logger


def contextualize_question(state: AgentState) -> AgentState:
    """
    Si hay historial, reformula la pregunta para incluir contexto.
    
    Ejemplo:
        Historial: "¿Qué es Terraform?" → "Terraform es..."
        Pregunta: "¿Cómo se instala?"
        Resultado: "¿Cómo se instala Terraform?"
    """
    question = state.get("question", "")
    chat_history = state.get("chat_history", [])
    
    # Guardar pregunta original
    state["original_question"] = question
    
    # Si no hay historial, no hay nada que contextualizar
    if not chat_history or len(chat_history) == 0:
        logger.info("📝 Sin historial, pregunta sin cambios", source="contextualize")
        return state
    
    logger.info("🔄 Contextualizando pregunta", source="contextualize", 
                question=question[:50], history_len=len(chat_history))
    
    try:
        # Formatear historial (últimos 6 mensajes = 3 turnos)
        history_text = ""
        for msg in chat_history[-6:]:
            role = "Usuario" if msg["role"] == "user" else "Asistente"
            content = msg["content"][:200]
            history_text += f"{role}: {content}\n"
        
        prompt = f"""Dado el historial de conversación sobre Terraform/Azure, reformula la pregunta del usuario para que sea autocontenida (se entienda sin el historial).

HISTORIAL:
{history_text}

PREGUNTA ACTUAL: {question}

INSTRUCCIONES:
- Si la pregunta ya es clara y autocontenida, devuélvela igual
- Si hace referencia a algo del historial (ej: "cómo se instala", "dame un ejemplo"), añade el contexto necesario
- Mantén el mismo idioma que la pregunta original
- Responde SOLO con la pregunta reformulada, sin explicaciones

PREGUNTA REFORMULADA:"""

        response = llm.invoke(prompt)
        contextualized = response.content.strip()
        
        # Validar que no esté vacía
        if contextualized and len(contextualized) > 3:
            state["question"] = contextualized
            logger.info("✅ Pregunta contextualizada", source="contextualize",
                       original=question[:50], contextualized=contextualized[:50])
        else:
            logger.warning("⚠️ Respuesta vacía, manteniendo original", source="contextualize")
        
        state["messages"].append(f"🔄 Contextualizada: {state['question'][:60]}")
        return state
        
    except Exception as e:
        logger.error("❌ Error contextualizando", source="contextualize", error=str(e))
        state["messages"].append(f"⚠️ Error en contextualización: {str(e)}")
        return state