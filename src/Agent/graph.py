# langgraph_agent/graph.py
"""
Construcción del grafo principal
"""
import time
from config.logger_config import logger, get_request_id, set_request_id
from langgraph.graph import StateGraph, END
from src.Agent.state import AgentState
from src.Agent.nodes.retrieval import retrieve_documents
from src.Agent.nodes.generation import generate_answer


class Agent:
    """
    Clase principal del agente LangGraph
    """

    def __init__(self):
        """Inicializa el agente compilando el grafo"""
        
        logger.info( "Inicializando Agent", source="agent")
        self.graph = self._create_graph()
        logger.info("Agent inicializado correctamente",source="agent")

    def _create_graph(self):
        """
        Crea y compila el grafo del agente

        Returns:
            Grafo compilado listo para usar
        """
        # Inicializar grafo
        logger.info("Inicio crección del grafo",source="agent")
        workflow = StateGraph(AgentState)

        # ========== NODOS ==========
        
        logger.info(f"Agregando nodo retrive ",source="agent")
        workflow.add_node("retrieve", retrieve_documents)
        logger.info(f"Agregando nodo generate ", source="agent")
        workflow.add_node("generate", generate_answer)

        # ========== EDGES ==========
        # Punto de entrada
        workflow.set_entry_point("retrieve")

        # Flujo lineal (por ahora)
        workflow.add_edge("retrieve", "generate")
        workflow.add_edge("generate", END)

        # Compilar
        logger.info("Compilando grafo", source="agent")
        return workflow.compile()
    

    def invoke(self, input_data: dict):
        """
        Ejecuta el grafo con los datos de entrada

        Args:
            input_data: Diccionario con los datos de entrada

        Returns:
            Resultado de la ejecución del grafo
        """
        request_id = get_request_id()
        logger.info( "Invocando grafo", request_id=request_id, input_keys=list(input_data.keys()), source="agent")
        
        start_time = time.time()
        
        #Tracking del grafo
        try: 
            result = self.graph.invoke(input_data)
            duration =time.time() - start_time
            logger.info(
                "Grafo ejecutado exitosamente",
                request_id=request_id,
                duration=f"{duration:.3f}s",
                result_keys=list(result.keys()) if isinstance(result, dict) else None,
                source="agent",
                process_time=f"{duration:.3f}s"
            )
        except Exception as e:
            duration = time.time() - start_time
            
            logger.error(
                "Error al invocar grafo",
                request_id=request_id,
                error=str(e),
                tipo_error=type(e).__name__,
                duration=f"{duration:.3f}s",
                source="agent",
                process_time=f"{duration:.3f}s"
            )
            raise
        
        return self.graph.invoke(input_data)


    def save_graph_png(self, filename: str = "graph.png"):
        """
        Guarda la visualización del grafo en formato PNG

        Args:
            filename: Nombre del archivo PNG a guardar
        """
        png_bytes = self.graph.get_graph().draw_mermaid_png()
        with open(filename, "wb") as f:
            f.write(png_bytes)


if __name__ == "__main__":
    logger.info( "Script de graph.py ejecutado directamente",
        source="agent"
    )
    agent = Agent()
    agent.save_graph_png()