# src/Agent/nodes/intent_classifier.py
"""
Detecta múltiples intenciones en una query para búsqueda paralela.
"""
import re
from typing import Dict
import unicodedata
from src.Agent.state import AgentState
from config.logger_config import logger
from config.classifier_loader import (
    get_intent_patterns,
    get_multi_intent_connectors
)


def normalize(text: str) -> str:
    """Normaliza texto: minúsculas y sin tildes."""
    text = text.lower()
    # Quitar tildes: é→e, ñ→n, etc.
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return text

def calculate_scores(query: str) -> Dict[str, float]:
    """Calcula score ponderado para cada intent."""
    query_lower = normalize(query)
    scores = {}
    # Cargar patrones de intención del YAML
    intent_patterns = get_intent_patterns()
    for intent, config in intent_patterns.items():
        score = 0.0
        # +1 por cada keyword encontrada
        score += sum(1 for kw in config["keywords"] if kw in query_lower)
        # +1.5 por cada patrón regex que matchea
        score += sum(1.5 for p in config["patterns"] if re.search(p, query_lower))
        # Aplicar peso
        scores[intent] = score * config["weight"]
    
    return scores

def classify_intent(state: AgentState) -> AgentState:
    """
    Nodo LangGraph: Clasifica intent y asigna colecciones.
    """
    from config.logger_config import logger
    question = state["question"]
    query_lower = question.lower()
    
    logger.info("🎯 Clasificando intent", source="intent_classifier", question=question[:80])
    
    # Calcular scores
    scores = calculate_scores(question)
    
    # Detectar multi-intent
    connectors = get_multi_intent_connectors()
    has_connector = any(c in query_lower for c in connectors)
    intents_found = [k for k, v in scores.items() if v > 0]
    is_multi = has_connector and len(intents_found) >= 2
    
    # Intent primario (el de mayor score, o default)
    primary = max(scores, key=scores.get) if any(scores.values()) else "code_template"
    
    # Determinar acción (formato de respuesta)
    if is_multi:
        action = "hybrid_response"
    elif primary == "explanation":
        action = "generate_answer"
    else:
        action = "return_template"
    
    # Actualizar estado
    state["intent"] = primary
    state["intents"] = intents_found if is_multi else [primary]
    state["is_multi_intent"] = is_multi
    #state["target_collections"] = []
    state["response_action"] = action
    state["intent_scores"] = scores
    
    state["messages"].append(f"🎯 Intent: {primary} | Multi: {is_multi} ")
    logger.info("✅ Intent clasificado", source="intent_classifier", intent=primary, multi=is_multi, scores=scores)
    
    return state

