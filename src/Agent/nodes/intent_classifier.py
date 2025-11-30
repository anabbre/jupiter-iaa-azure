# src/Agent/nodes/intent_classifier.py
"""
Detecta múltiples intenciones en una query para búsqueda paralela.
"""
import re
from typing import List, Dict, Tuple
import unicodedata
from src.Agent.state import AgentState
from config.logger_config import logger


# Patrones de intención con pesos
INTENT_PATTERNS = {
    "explanation": {
        "keywords": [
            "que es", "what is", "explain", "explica", "explicame",    
            "definicion", "definition", "concepto", "concept", "como funciona",
            "how does", "por que", "why", "cuando", "when", "diferencia",
            "difference", "comparar", "compare", "significa", "means",
            "introduccion", "overview", "teoria", "theory", "dime"
        ],
        "patterns": [
            r"\?$",  # Termina en pregunta
            r"^(que|como|como|por |cual |cuando)\s",
            r"(explica|explicame|dime|cuentame)\s"
        ],
        "weight": 1.0,
        "collection": "terraform_book"
    },
    "code_template": {
        "keywords": [
            "codigo", "code", "template", "plantilla", "crear", "create",
            "configurar", "configure", "setup", "implementar", "implement",
            "desplegar", "deploy", "provisionar", "provision", "generar",
            "generate", "escribir", "write", "dame", "give me", "necesito",
            "i need", "quiero", "i want", "hazme", "make me"
        ],
        "patterns": [
            r"(crea|crear|genera|generar|escribe|escribir|dame|hazme)\s",
            r"(template|plantilla|código|code)\s+(para|for|de|of)",
            r"(necesito|quiero|want|need)\s+(un|una|a|the)?\s*(código|code|template)"
        ],
        "weight": 1.2,  # Prioridad ligeramente mayor (caso de uso principal)
        "collection": "examples_terraform"
    },
    "full_example": {
        "keywords": [
            "ejemplo", "example", "sample", "demo", "tutorial", "guia",
            "guide", "paso a paso", "step by step", "caso de uso", "use case",
            "proyecto", "project", "completo", "complete", "full", "end to end",
            "e2e", "real", "producción", "production"
        ],
        "patterns": [
            r"ejemplo\s+(completo|de|para)",
            r"(full|complete)\s+example",
            r"caso\s+de\s+uso",
            r"paso\s+a\s+paso"
        ],
        "weight": 1.1,
        "collection": "examples_terraform"
    }
}

# Conectores que indican multi-intent
MULTI_INTENT_CONNECTORS = [
    " y ", " and ", " también ", " also ", " además ", " plus ",
    " con ", " with ", " incluyendo ", " including "
]
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
    
    for intent, config in INTENT_PATTERNS.items():
        score = 0.0
        # +1 por cada keyword encontrada
        score += sum(1 for kw in config["keywords"] if kw in query_lower)
        # +1.5 por cada patrón regex que matchea
        score += sum(1.5 for p in config["patterns"] if re.search(p, query_lower))
        # Aplicar peso
        scores[intent] = score * config["weight"]
    
    return scores

def is_multi_intent(query: str, scores: Dict[str, float]) -> bool:
    """Detecta si la query tiene múltiples intenciones."""
    query_norm = normalize(query)
    has_connector = any(c in query_norm for c in MULTI_INTENT_CONNECTORS)
    intents_found = [k for k, v in scores.items() if v > 0]
    return has_connector and len(intents_found) >= 2


def get_primary_intent(scores: Dict[str, float]) -> str:
    """Obtiene el intent con mayor score."""
    if not scores or all(v == 0 for v in scores.values()):
        return "code_template"
    return max(scores, key=scores.get)

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
    has_connector = any(c in query_lower for c in MULTI_INTENT_CONNECTORS)
    intents_found = [k for k, v in scores.items() if v > 0]
    is_multi = has_connector and len(intents_found) >= 2
    
    # Intent primario (el de mayor score, o default)
    primary = max(scores, key=scores.get) if any(scores.values()) else "code_template"
    
    # Determinar colecciones y acción
    if is_multi:
        collections = ["terraform_book", "examples_terraform"]
        action = "hybrid_response"
    else:
        collections = [INTENT_PATTERNS[primary]["collection"]]
        action = "generate_answer" if primary == "explanation" else "return_template"
    
    # Actualizar estado
    state["intent"] = primary
    state["intents"] = intents_found if is_multi else [primary]
    state["is_multi_intent"] = is_multi
    state["target_collections"] = collections
    state["response_action"] = action
    state["intent_scores"] = scores
    
    state["messages"].append(f"🎯 Intent: {primary} | Multi: {is_multi} | Collections: {collections}")
    logger.info("✅ Intent clasificado", source="intent_classifier", intent=primary, multi=is_multi, collections=collections, scores=scores)
    
    return state


# TEST
if __name__ == "__main__":
    test_queries = [
        "¿Qué es Terraform?",
        "Dame código para crear un storage account",
        "Explícame y dame un ejemplo de resource group",
        "Necesito una plantilla para desplegar AKS",
        "Tutorial paso a paso de Azure Functions",
        "Crea un resource group",
        "How to configure a virtual network?",
    ]
    
    print("\n" + "="*70)
    print("🧪 TEST INTENT CLASSIFIER")
    print("="*70)
    
    for q in test_queries:
        scores = calculate_scores(q)
        primary = get_primary_intent(scores)
        is_multi = is_multi_intent(q, scores)
        
        collections = ["terraform_book", "examples_terraform"] if is_multi else [INTENT_PATTERNS[primary]["collection"]]
        
        print(f"\n📝 {q}")
        print(f"   Scores: {', '.join(f'{k}={v:.1f}' for k,v in scores.items())}")
        print(f"   → Intent: {primary} | Multi: {is_multi}")
        print(f"   → Collections: {collections}")
    
    print("\n" + "="*70)
    print("✅ Test completado")
    print("="*70)