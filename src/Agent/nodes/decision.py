# src/Agent/nodes/decision.py
"""
Nodo de decisión basado en la intención detectada
"""
from config.config import SETTINGS
from src.Agent.state import AgentState
from config.logger_config import logger, get_request_id, set_request_id
from typing import Literal
from src.api.schemas import SourceInfo

# Umbral minimo score para devolver template code directamente

def _has_terraform_code(content: str) -> bool:
    """Verifica si el contenido tiene código Terraform"""
    if not content:
        return False
        
    tf_indicators = [
        "resource ",      # resource "azurerm_storage_account" "main"
        "variable ",      # variable "location" { }
        "output ",        # output "storage_id" { }
        "module ",        # module "network" { }
        "provider ",      # provider "azurerm" { }
        "terraform {",    # terraform { required_providers }
        "data ",          # data "azurerm_resource_group" "main"
        "locals {"        # locals { }
    ]
    return any(indicator in content for indicator in tf_indicators)

def _find_best_template(raw_documents: list, threshold: float) -> tuple:
    """Encuentra el mejor template code basado en el score y validez del código"""
    if not raw_documents:
        return None, False
    
    for doc in raw_documents:
        # Verificar score y contenido
        if doc.relevance_score >= threshold and _has_terraform_code(doc.content):
            return doc, True
    
    return None, False

def decide_response_type(state: AgentState) -> AgentState:
    """
    Decide la acción a tomar basada en la intención detectada

    Args:
        state: Estado con intentos y documentos

    Returns:
        Estado actualizado con la acción decidida
    """
    
    try:
        # Extraer datos del estado
        intent = state.get("intent", "")
        is_multi_intent = state.get("is_multi_intent", False)
        raw_documents = state.get("raw_documents", [])
        response_action = state.get("response_action", "")
        threshold = state.get("threshold", SETTINGS.THRESHOLD)

        logger.info("🤔 Evaluando tipo de respuesta", source="decision", intent=intent, is_multi_intent=is_multi_intent, num_docs=len(raw_documents), current_action=response_action)

        
        # Caso 1 - Hybrid
        if is_multi_intent or response_action == "hybrid_response":
            state["response_action"] = "hybrid_response"
            logger.info("✅ Decisión: hybrid_response",source="decision",reason="multi-intent detectado")
            state["messages"].append("🤔 Decisión: hybrid_response (código + explicación)")
            return state
        
        # Caso 2 - Código Template Directo
        if intent in ["code_template", "full_example"]:
            best_doc, found = _find_best_template(raw_documents, threshold)
                        
            if found and best_doc:
                state["response_action"] = "return_template"
                state["template_code"] = best_doc.content
                logger.info("✅ Decisión: return_template",source="decision",reason="template encontrado",score=best_doc.relevance_score,source_file=best_doc.source)
                state["messages"].append(f"🤔 Decisión: return_template (score: {best_doc.relevance_score:.2f})")
                return state
            else:
                # No hay buen template, generar con LLM
                logger.info("⚠️ No se encontró template con score >= {:.2f}".format(threshold),source="decision",best_score=raw_documents[0].relevance_score if raw_documents else 0)
    
        # Caso 3 - Generar Respuesta Completa
        state["response_action"] = "generate_answer"
        logger.info("✅ Decisión: generate_answer",source="decision",reason="default o explanation intent")
        state["messages"].append("🤔 Decisión: generate_answer (LLM genera)")
        return state
    
    except Exception as e:
        # En caso de error, fallback a generar respuesta
            logger.error("❌ Error durante la decisión de tipo de respuesta",source="agent",error=str(e),tipo_error=type(e).__name__ )
            state["response_action"] = "generate_answer"
            state["messages"].append(f"⚠️ Error en decisión, usando fallback: {str(e)}")
            return state

def get_next_node(state: AgentState) -> Literal["generate", "format_template", "format_hybrid"]:
    """
    Router condicional para LangGraph.
    
    Determina qué nodo de generación ejecutar basado en response_action.
    
    Returns:
        Nombre del siguiente nodo
    """
    action = state.get("response_action", "generate_answer")
    
    routing = {
        "return_template": "format_template",
        "hybrid_response": "format_hybrid",
        "generate_answer": "generate"
    }
    
    next_node = routing.get(action, "generate")
    logger.debug(f"🔀 Routing a: {next_node}",source="decision",action=action)
    return next_node

# tests rápidos
if __name__ == "__main__":
    from src.Agent.state import DocumentScore
    
    print("\n" + "="*60)
    print("🧪 TEST DECISION NODE")
    print("="*60)
    
    # Test 1: Multi-intent → hybrid_response
    state1 = {
        "intent": "code_template",
        "is_multi_intent": True,
        "raw_documents": [],
        "response_action": "",
        "messages": []
    }
    result1 = decide_response_type(state1)
    status1 = "✅" if result1["response_action"] == "hybrid_response" else "❌"
    print(f"\n{status1} Test 1: Multi-intent → {result1['response_action']}")
    
    # Test 2: Code template con buen doc → return_template
    doc_bueno = DocumentScore(
        content='resource "azurerm_storage_account" "main" { name = "test" }',
        metadata={},
        relevance_score=0.85,
        source="main.tf"
    )
    state2 = {
        "intent": "code_template",
        "is_multi_intent": False,
        "raw_documents": [doc_bueno],
        "response_action": "",
        "messages": []
    }
    result2 = decide_response_type(state2)
    status2 = "✅" if result2["response_action"] == "return_template" else "❌"
    print(f"{status2} Test 2: Code + buen doc (0.85) → {result2['response_action']}")
    
    # Test 3: Code template con doc bajo score → generate_answer
    doc_bajo = DocumentScore(
        content='resource "azurerm_storage_account" "main" { }',
        metadata={},
        relevance_score=0.75,  # Bajo threshold
        source="main.tf"
    )
    state3 = {
        "intent": "code_template",
        "is_multi_intent": False,
        "raw_documents": [doc_bajo],
        "response_action": "",
        "messages": []
    }
    result3 = decide_response_type(state3)
    status3 = "✅" if result3["response_action"] == "generate_answer" else "❌"
    print(f"{status3} Test 3: Code + doc bajo score (0.75) → {result3['response_action']}")
    
    # Test 4: Code template con doc sin código TF → generate_answer
    doc_sin_tf = DocumentScore(
        content='Este es un README sin código terraform',
        metadata={},
        relevance_score=0.90,
        source="readme.md"
    )
    state4 = {
        "intent": "code_template",
        "is_multi_intent": False,
        "raw_documents": [doc_sin_tf],
        "response_action": "",
        "messages": []
    }
    result4 = decide_response_type(state4)
    status4 = "✅" if result4["response_action"] == "generate_answer" else "❌"
    print(f"{status4} Test 4: Code + doc sin TF (0.90) → {result4['response_action']}")
    
    # Test 5: Explanation → generate_answer
    state5 = {
        "intent": "explanation",
        "is_multi_intent": False,
        "raw_documents": [],
        "response_action": "",
        "messages": []
    }
    result5 = decide_response_type(state5)
    status5 = "✅" if result5["response_action"] == "generate_answer" else "❌"
    print(f"{status5} Test 5: Explanation → {result5['response_action']}")
    
    print("\n" + "="*60)
    all_passed = all([
        result1["response_action"] == "hybrid_response",
        result2["response_action"] == "return_template",
        result3["response_action"] == "generate_answer",
        result4["response_action"] == "generate_answer",
        result5["response_action"] == "generate_answer",
    ])
    print(f"{'✅ Todos los tests pasaron!' if all_passed else '❌ Algunos tests fallaron'}")
    print("="*60)