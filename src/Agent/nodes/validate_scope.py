from typing import Literal
from src.Agent.state import AgentState
from src.services.relevance_filter import is_query_in_scope, get_rejection_message_for_query
from config.logger_config import logger

def validate_scope(state: AgentState) -> AgentState:
    """
    Valida si la consulta está dentro del scope (Terraform/Azure).
    
    Si está fuera de scope:
    - Marca is_valid_scope = False
    - Genera mensaje de rechazo apropiado
    
    Si está en scope:
    - Marca is_valid_scope = True
    - Continúa el flujo normal
    """
    question = state.get("question", "")
    
    logger.info("🔍 Validando scope de la consulta", source="validate_scope", question=question[:80])
    
    try:
        # Usar tu filtro existente
        is_valid, reason = is_query_in_scope(question, min_keywords=1)
        
        state["is_valid_scope"] = is_valid
        if is_valid:
            state["messages"].append(f"✅ Scope válido: {reason}")
            logger.info(f"🏷️ is_valid_scope antes de retornar: {state['is_valid_scope']}", source="validate_scope")
        else:
            state["messages"].append(f"❌ Fuera de scope: {reason}")
            state["answer"] = get_rejection_message_for_query(question)
            state["response_action"] = "rejected"
            logger.info(f"🏷️ is_valid_scope antes de retornar: {state['is_valid_scope']}", source="validate_scope")
        return state  
        
    except Exception as e:
        logger.error("❌ Error validando scope", source="validate_scope", error=str(e))
        # En caso de error, permitir continuar
        state["is_valid_scope"] = True
        state["messages"].append(f"⚠️ Error en validación: {str(e)}")
        return state


def should_continue(state: AgentState) -> Literal["continue", "reject"]:
    """
    Router condicional: decide si continuar o rechazar.
    """
    is_valid = state.get("is_valid_scope", True)  
    logger.info(f"🔀 should_continue: is_valid_scope={is_valid}", source="validate_scope")
    return "continue" if is_valid else "reject"


# Tests rápidos
if __name__ == "__main__":
    print("\n" + "="*60)
    print("🧪 TEST VALIDATE SCOPE")
    print("="*60)
    
    test_queries = [
        # Válidas
        ("Dame código para crear un storage account", True),
        ("Cómo configurar Azure Front Door", True),
        ("Qué es Terraform", True),
        ("Ejemplo de resource group en Azure", True),
        
        # Inválidas
        ("Hola", False),
        ("Qué tal", False),
        ("ok", False),
        ("Cuál es la fecha del partido de España", False),
        ("Cuéntame un chiste", False),
    ]
    
    for query, expected in test_queries:
        state = {
            "question": query,
            "messages": [],
            "is_valid_scope": True,
            "answer": "",
            "response_action": ""
        }
        
        result = validate_scope(state)
        is_valid = result["is_valid_scope"]
        status = "✅" if is_valid == expected else "❌"
        
        print(f"\n{status} '{query[:40]}...' → valid={is_valid} (expected={expected})")
        
        if not is_valid:
            print(f"   Respuesta: {result['answer'][:60]}...")
    
    print("\n" + "="*60)
    print("✅ Test completado")