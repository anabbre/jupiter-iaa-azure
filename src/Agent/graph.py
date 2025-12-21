# langgraph_agent/graph.py
"""
Construcción del grafo principal
"""
import time
from langgraph.graph import StateGraph, END
from config.logger_config import logger

from src.Agent.state import AgentState
from src.Agent.nodes.validate_scope import validate_scope, should_continue
from src.Agent.nodes.intent_classifier import classify_intent
from src.Agent.nodes.retrieval import retrieve_documents
from src.Agent.nodes.decision import decide_response_type, get_next_node
from src.Agent.nodes.generation import generate_answer, format_template, format_hybrid

def reject_query(state: AgentState) -> AgentState:
    """
    Nodo de rechazo: La respuesta ya está en state["answer"].
    Solo añade mensaje de log.
    """
    logger.info("🚫 Query rechazada (fuera de scope)", source="agent")
    state["messages"].append("🚫 Query rechazada")
    return state


class Agent:
    """
    Agente Terraform Generator con validación de scope.
    """
    
    def __init__(self):
        logger.info("🚀 Inicializando Terraform Generator", source="agent")
        try:
            self.graph = self._create_graph()
            logger.info("✅ Agent inicializado", source="agent")
        except Exception as e:
            logger.error("❌ Error inicializando Agent", source="agent", error=str(e))
            raise
    
    def _create_graph(self):
        """
        Crea el grafo:
        
        validate_scope ─┬─→ classify_intent → retrieve → decide ─┬─→ generate ──────→  END
                        │                                        ├─→ format_template → END
                        │                                        └─→ format_hybrid ──→ END
                        └─→ reject ──────────────────────────────────────────────────→ END
        """
        logger.info("🔧 Creando grafo", source="agent")
        
        workflow = StateGraph(AgentState)
        
        # ========== NODOS ==========
        workflow.add_node("validate_scope", validate_scope)
        workflow.add_node("reject", reject_query)
        workflow.add_node("classify_intent", classify_intent)
        workflow.add_node("retrieve", retrieve_documents)
        workflow.add_node("decide", decide_response_type)
        workflow.add_node("generate", generate_answer)
        workflow.add_node("format_template", format_template)
        workflow.add_node("format_hybrid", format_hybrid)
        
        # ========== EDGES ==========
        
        # 1. Entry point: validate_scope
        workflow.set_entry_point("validate_scope")
        
        # 2. Branching desde validate_scope
        workflow.add_conditional_edges(
            "validate_scope",
            should_continue,
            {
                "continue": "classify_intent",
                "reject": "reject"
            }
        )
        
        # 3. Flujo principal
        workflow.add_edge("classify_intent", "retrieve")
        workflow.add_edge("retrieve", "decide")
        
        # 4. Branching desde decide
        workflow.add_conditional_edges(
            "decide",
            get_next_node,
            {
                "generate": "generate",
                "format_template": "format_template",
                "format_hybrid": "format_hybrid"
            }
        )
        
        # 5. Todos terminan en END
        workflow.add_edge("reject", END)
        workflow.add_edge("generate", END)
        workflow.add_edge("format_template", END)
        workflow.add_edge("format_hybrid", END)
        
        logger.info("✅ Grafo compilado", source="agent")
        return workflow.compile()
    
    def invoke(self, question: str, k_docs: int, threshold: float) -> dict:
        """
        Ejecuta el grafo con una pregunta.
        """
        start_time = time.time()
        
        # Estado inicial
        state = {
            "question": question,
            "k_docs": k_docs,
            "threshold": threshold,
            "messages": [],
            # Scope
            "is_valid_scope": True,
            # Intent
            "intent": "",
            "intents": [],
            "is_multi_intent": False,
            "target_collections": [],
            "response_action": "",
            "intent_scores": {},
            # Retrieval
            "raw_documents": [],
            "documents": [],
            "documents_metadata": [],
            # Generation
            "answer": "",
            "template_code": None,
            "explanation": None,
        }
        
        logger.info("▶️ Ejecutando grafo", source="agent", question=question[:80])
        
        try:
            result = self.graph.invoke(state)
            duration = time.time() - start_time
            
            logger.info("✅ Grafo completado", source="agent",
                       duration=f"{duration:.2f}s",
                       is_valid_scope=result.get("is_valid_scope"),
                       intent=result.get("intent"),
                       action=result.get("response_action"))
            
            return result
            
        except Exception as e:
            logger.error("❌ Error en grafo", source="agent", error=str(e))
            raise
        
def query(self, question: str) -> str:
        """Método simple que devuelve solo la respuesta."""
        result = self.invoke(question)
        return result.get("answer", "No se pudo generar respuesta.")
    
# TEst
if __name__ == "__main__":
    import sys
    
    print("\n" + "="*60)
    print("🧪 TEST GRAPH COMPLETO")
    print("="*60)
    
    agent = Agent()
    
    # Query de prueba
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        question = "Dame codigo para crear un storage account"
    
    print(f"\n📝 Query: {question}")
    print("-"*60)
    
    result = agent.invoke(question, k_docs=5, threshold=0.1)
    
    # Mostrar resultados
    print(f"\n🔍 Scope válido: {result.get('is_valid_scope', True)}")
    print(f"🎯 Intent: {result.get('intent', 'N/A')}")
    print(f"📊 Multi-intent: {result.get('is_multi_intent', False)}")
    print(f"🔀 Action: {result.get('response_action', 'N/A')}")
    print(f"📚 Documentos: {len(result.get('documents', []))}")
    print(f"🗂️ Colecciones: {result.get('target_collections', [])}")
    
    print(f"\n{'='*60}")
    print("💬 RESPUESTA:")
    print("="*60)
    answer = result['answer']
    print(answer[:1500] if len(answer) > 1500 else answer)
    
    if len(answer) > 1500:
        print(f"\n... (truncada, total: {len(answer)} chars)")
    
    print("\n" + "="*60)
    print("📋 MENSAJES DEL FLUJO:")
    print("="*60)
    for msg in result['messages']:
        print(f"  {msg}")
    print("="*60)
