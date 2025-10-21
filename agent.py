from typing import Annotated, Dict, List, TypedDict

from langchain.prompts import ChatPromptTemplate
from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

try:
    from langchain.schema import BaseMessage, HumanMessage
except ImportError:
    from langchain_core.messages import BaseMessage, HumanMessage

from dotenv import load_dotenv

load_dotenv()


# Configuración
DB_DIR = "src/rag/vector_db"
EMB_MODEL = "text-embedding-3-small"
LLM_MODEL = "gpt-4o-mini"
K_DOCS = 3


class AgentState(TypedDict):
    """
    Estado del agente RAG

    - messages: Lista de mensajes intercambiados (HumanMessage y AIMessage)
    - sources: Lista de diccionarios con metadatos de las fuentes consultadas
    """

    messages: Annotated[List[BaseMessage], add_messages]
    sources: List[dict]


class RAGAgent:
    """
    Agente RAG para responder preguntas sobre Terraform
    Usa una base de datos vectorial Chroma y un LLM de OpenAI

    - embeddings: Modelo de embeddings de OpenAI
    - vectorstore: Base de datos vectorial Chroma
    - llm: Modelo de lenguaje (ChatOpenAI)
    """

    def __init__(self):
        self.embeddings = OpenAIEmbeddings(model=EMB_MODEL)
        self.vectorstore = Chroma(persist_directory=DB_DIR, embedding_function=self.embeddings)
        self.llm = None
        self._init_llm()

    def _init_llm(self, temperature: float = 0.0):
        """Inicializa o reinicializa el LLM con la temperatura especificada"""
        self.llm = ChatOpenAI(model=LLM_MODEL, temperature=temperature)

    def search_docs(self, query: str, k: int = K_DOCS) -> tuple:
        """Busca documentos relevantes en la base de datos vectorial"""
        results = self.vectorstore.similarity_search_with_score(query, k=k)

        formatted_results = []
        sources = []

        for i, (doc, score) in enumerate(results):
            content = doc.page_content[:500]

            metadata = {
                "title": doc.metadata.get("title", "Sin título"),
                "url": doc.metadata.get("url", ""),
                "section": doc.metadata.get("section", ""),
                "subsection": doc.metadata.get("subsection", ""),
                "score": round(score, 3),
            }

            sources.append(metadata)

            formatted_results.append(
                f"[Documento {i + 1}]\n"
                f"Título: {metadata['title']}\n"
                f"Sección: {metadata['section']} > {metadata['subsection']}\n"
                f"Contenido: {content}...\n"
            )

        return "\n---\n".join(formatted_results), sources

    def retrieve_node(self, state: AgentState, k_docs: int = K_DOCS) -> AgentState:
        """Nodo que recupera información relevante"""
        last_message = state["messages"][-1].content

        results, sources = self.search_docs(last_message, k=k_docs)

        context_message = HumanMessage(content=f"Contexto encontrado:\n\n{results}")

        return {"messages": [context_message], "sources": sources}

    def generate_node(self, state: AgentState) -> AgentState:
        """Nodo que genera la respuesta usando el LLM"""
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
Actúa como un Ingeniero/a DevOps senior especializado/a en Terraform (HCL) y buenas prácticas de IaC.
Objetivo: generar configuraciones de Terraform con sintaxis correcta, mínimas suposiciones, y ancladas al CONTEXT (RAG) cuando exista.

Reglas duras:
- Idioma de respuesta: español.
- El código debe venir en UN ÚNICO bloque de código markdown etiquetado como hcl.
- Prohíbe pseudocódigo: únicamente HCL válido. Nombres y argumentos reales.
- Antes de responder, realiza un chequeo silencioso de sintaxis (auto-revisión mental de estructura de bloques, atributos obligatorios, tipos y referencias).
- Si falta información esencial (proveedor, región, versión, etc.), haz suposiciones explícitas y razonables en “Notas”, o sugiere variantes. No inventes recursos que no estén en la documentación del proveedor.
- Prioriza el CONTEXT (RAG). Si el contexto es insuficiente para una parte de la respuesta, decláralo como “Insuficiente en contexto” y ofrece una opción genérica clara.

Buenas prácticas por defecto:
- Incluye bloque provider con versión o constraints razonables.
- Añade versiones mínimas de Terraform si procede (terraform { required_version } y required_providers).
- Usa nombres de recurso y variables consistentes y en minúsculas con _.
- Para variables: tipa con variable { type = ... }, defaults prudentes (si aplica) y descripción.
- Evita recursos huérfanos: si defines un resource dependiente, incluye dependencias o data sources necesarios.
- Estructura cohesiva en un solo archivo (main.tf) salvo que el usuario pida dividir. Si hace falta, comenta con # nombre_de_archivo.tf sobre cada sección del mismo bloque.
- No salgas del bloque de código HCL con comentarios extensos: las explicaciones van fuera del bloque.

Citas y veracidad:
- Cuando derives comportamiento de CONTEXT (RAG), referencia título/sección de ese contexto en la sección “Notas” (p. ej., [Doc 1: Título – Sección]).
- Si no hay cobertura en el contexto, dilo claramente. No alucines.

Si te preguntan conusltas normales o teóricas y no te piden que generes código, simplemenete
responde en base a la información que tienes en la DB Vectorial y cita las fuentes.""",
                ),
                ("placeholder", "{messages}"),
            ]
        )

        chain = prompt | self.llm
        response = chain.invoke({"messages": state["messages"]})

        return {"messages": [response]}

    def create_graph(self, k_docs: int = K_DOCS):
        """Crea el grafo del agente RAG"""
        workflow = StateGraph(AgentState)

        def retrieve_with_k(state):
            return self.retrieve_node(state, k_docs)

        workflow.add_node("retrieve", retrieve_with_k)
        workflow.add_node("generate", self.generate_node)

        workflow.add_edge(START, "retrieve")
        workflow.add_edge("retrieve", "generate")
        workflow.add_edge("generate", END)

        return workflow.compile()

    def query(self, question: str, k_docs: int = K_DOCS, temperature: float = 0.0) -> Dict:
        """Ejecuta una consulta al agente RAG"""
        if temperature != self.llm.temperature:
            self._init_llm(temperature)

        agent = self.create_graph(k_docs)

        initial_state = {"messages": [HumanMessage(content=question)], "sources": []}

        result = agent.invoke(initial_state)

        answer = result["messages"][-1].content
        sources = result["sources"]

        return {"answer": answer, "sources": sources, "question": question}
