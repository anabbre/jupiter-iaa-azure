"""
Construcción del grafo principal
"""
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
        self.graph = self._create_graph()

    def _create_graph(self):
        """
        Crea y compila el grafo del agente

        Returns:
            Grafo compilado listo para usar
        """
        # Inicializar grafo
        workflow = StateGraph(AgentState)

        # NODOS 
        workflow.add_node("retrieve", retrieve_documents)
        workflow.add_node("generate", generate_answer)

        # EDGES 
        # Punto de entrada
        workflow.set_entry_point("retrieve")

        # Flujo lineal (por ahora)
        workflow.add_edge("retrieve", "generate")
        workflow.add_edge("generate", END)

        # Compilar
        return workflow.compile()

    def invoke(self, input_data: dict):
        """
        Ejecuta el grafo con los datos de entrada

        Args:
            input_data: Diccionario con los datos de entrada

        Returns:
            Resultado de la ejecución del grafo
        """
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
    agent = Agent()
    agent.save_graph_png()