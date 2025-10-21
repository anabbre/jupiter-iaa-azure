import os
import tempfile
import logging
import fitz
from typing import List
from dotenv import load_dotenv
from pinecone import Pinecone
from streamlit.runtime.uploaded_file_manager import UploadedFile
from langchain import hub
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain.prompts import PromptTemplate
from langchain_pinecone import PineconeVectorStore
from langchain_community.document_loaders import TextLoader
from langchain.chains.history_aware_retriever import create_history_aware_retriever
from langchain.chains.retrieval import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_openai import ChatOpenAI

load_dotenv()

# Variables desde .env
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENV = os.getenv("PINECONE_ENVIRONMENT", "us-east-1")  # valor por defecto

# Embeddings de OpenAI
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")


# --- Logging ---
def get_logger(name: str, subdir: str = None) -> logging.Logger:
    """
    Devolvemos un logger configurado para la aplicación.
    Los guardaremos en la carpeta logs/
    Cada dia se creará un nuevo archivo de log.
    """

    log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")

    if subdir:
        log_dir = os.path.join(log_dir, subdir)

    os.makedirs(log_dir, exist_ok=True)

    from datetime import datetime

    logs_file = os.path.join(log_dir, f"{datetime.now().strftime('%Y-%m-%d')}.log")
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Evitar agregar múltiples handlers si el logger ya tiene handlers
    if not logger.hasHandlers():
        file_handler = logging.FileHandler(logs_file, encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # También agregar un StreamHandler para salida en consola
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


logger = get_logger("app")
# ----


def save_file_with_content_check(output_dir, filename, content):
    """
    Guarda un archivo en output_dir comprobando si ya existe uno con el mismo nombre.
    Si existe y el contenido es igual, lo sobreescribe.
    Si existe y el contenido es diferente, guarda el nuevo archivo con un sufijo incremental.
    Devuelve el nombre final del archivo guardado.
    """
    import hashlib

    def get_hash(data):
        return hashlib.md5(data).hexdigest()

    base, ext = os.path.splitext(filename)
    candidate = filename
    path = os.path.join(output_dir, candidate)
    content_hash = get_hash(content)
    i = 1
    while os.path.exists(path):
        with open(path, "rb") as f:
            existing_hash = get_hash(f.read())
        if existing_hash == content_hash:
            break  # mismo contenido → sobreescribe
        else:
            candidate = f"{base}_{i}{ext}"
            path = os.path.join(output_dir, candidate)
            i += 1
    with open(path, "wb") as f:
        f.write(content)
    return candidate


def ingest_docs(
    uploaded_files: List[UploadedFile],
    assistant_id: str,
    index_name,
    delete_existing_files=False,
):
    try:
        if not os.path.exists("docs"):
            os.makedirs("docs")
            logger.info("Carpeta 'docs' creada")

        # Verificar que existe la carpeta específica del índice
        index_dir = os.path.join("docs", index_name)
        if not os.path.exists(index_dir):
            os.makedirs(index_dir)
            logger.info(f"Carpeta '{index_dir}' creada")

        # Inicializar cliente de Pinecone
        pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))

        # Comprobar si el índice existe
        existing_indexes = [idx.name for idx in pc.list_indexes()]
        index_exists = index_name in existing_indexes

        if not index_exists:
            logger.info(f"Creando nuevo índice: {index_name}")
            pc.create_index(
                name=index_name,
                dimension=1536,  # para text-embedding-3-small
                metric="cosine",
                spec={
                    "serverless": {
                        "cloud": "aws",
                        "region": PINECONE_ENV,  # configurable desde .env
                    }
                },
            )

        all_documents = []

        # Procesar cada archivo subido
        for uploaded_file in uploaded_files:
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=os.path.splitext(uploaded_file.name)[1]
            ) as temp_file:
                temp_file.write(uploaded_file.getvalue())
                temp_path = temp_file.name

            try:
                file_documents = []
                if uploaded_file.name.endswith(".pdf"):
                    pdf_doc = fitz.open(temp_path)
                    full_text = ""
                    for page_num in range(pdf_doc.page_count):
                        page = pdf_doc.load_page(page_num)
                        text = page.get_text()
                        full_text += f"\n--- Página {page_num + 1} ---\n{text}"
                        links = []
                        for link in page.get_links():
                            uri = link.get("uri")
                            if uri:
                                links.append(uri)
                        file_documents.append(
                            type(
                                "Doc",
                                (),
                                {
                                    "page_content": text,
                                    "metadata": {
                                        "filename": uploaded_file.name,
                                        "filetype": uploaded_file.type,
                                        "assistant_id": assistant_id,
                                        "page": page_num + 1,
                                        "links": links,
                                    },
                                },
                            )
                        )
                    output_dir = os.path.join("docs", index_name)
                    os.makedirs(output_dir, exist_ok=True)
                    output_path = os.path.join(
                        output_dir, f"{os.path.splitext(uploaded_file.name)[0]}.txt"
                    )
                    with open(output_path, "w", encoding="utf-8") as f:
                        f.write(full_text)
                    pdf_doc.close()

                elif uploaded_file.name.endswith(".md"):
                    # Evitamos 'unstructured': usamos TextLoader para .md
                    loader = TextLoader(temp_path, encoding="utf-8")
                    file_documents = loader.load()

                elif uploaded_file.name.endswith((".docx", ".txt", ".html", ".tf")):
                    loader = TextLoader(temp_path, encoding="utf-8")
                    file_documents = loader.load()

                else:
                    logger.warning(
                        f"Tipo de archivo no soportado: {uploaded_file.name}"
                    )
                    continue

                logger.info(
                    f"Cargados {len(file_documents)} documentos de {uploaded_file.name}"
                )

                output_dir = os.path.join("docs", index_name)
                os.makedirs(output_dir, exist_ok=True)
                final_filename = save_file_with_content_check(
                    output_dir, uploaded_file.name, uploaded_file.getvalue()
                )
                logger.info(
                    f"Archivo guardado en: {output_dir}, nombre original: {uploaded_file.name}, final: {final_filename}"
                )

                if not uploaded_file.name.endswith(".pdf"):
                    for doc in file_documents:
                        doc.metadata.update(
                            {
                                "filename": uploaded_file.name,
                                "filetype": uploaded_file.type,
                                "assistant_id": assistant_id,
                            }
                        )

                all_documents.extend(file_documents)

            finally:
                os.unlink(temp_path)

        if not all_documents:
            logger.warning("No se pudieron cargar documentos válidos")
            return

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200, add_start_index=True
        )
        documents = text_splitter.split_documents(all_documents)
        logger.info(f"Dividido en {len(documents)} chunks")

        batch_size = 100
        total_batches = (len(documents) + batch_size - 1) // batch_size

        _ = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))
        vectorstore = PineconeVectorStore(index_name=index_name, embedding=embeddings)

        if delete_existing_files:
            filenames = [
                doc.metadata["filename"]
                for doc in all_documents
                if "filename" in doc.metadata
            ]
            filenames = list(set(filenames))
            if filenames:
                vectorstore.delete(filter={"filename": {"$in": filenames}})
                logger.info(
                    f"Eliminados documentos anteriores para: {', '.join(filenames)}"
                )

        logger.info(
            f"Agregando {len(documents)} documentos a Pinecone en {total_batches} lotes"
        )

        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            end_idx = min(i + batch_size, len(documents))
            logger.info(
                f"Lote {i // batch_size + 1}/{total_batches} (docs {i + 1}-{end_idx})"
            )
            vectorstore.add_documents(batch)

        logger.info("****Carga en el índice vectorial completada****")
        return True

    except Exception as e:
        logger.error(f"Error: {e}")
        return False


def get_docs_by_index(index_name: str, limit: int = 7, chunked: bool = False):
    """
    Obtiene documentos de un índice específico en Pinecone.
    """
    try:
        _ = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))
        vectorstore = PineconeVectorStore(index_name=index_name, embedding=embeddings)

        # Búsqueda robusta: consulta neutra + fallback MMR
        docs = vectorstore.similarity_search("terraform", k=limit)
        if not docs:
            docs = vectorstore.max_marginal_relevance_search("terraform", k=limit)

        if chunked:
            return [doc.page_content for doc in docs]
        else:
            return docs

    except Exception as e:
        logger.error(f"Error al obtener documentos del índice {index_name}: {e}")
        return []


def run_llm_on_index(query: str, chat_history: list, index_name: str):
    """
    Ejecuta el modelo de lenguaje utilizando el índice especificado para responder consultas.
    """
    try:
        logger.info(
            f"[AGENTE] Nueva consulta recibida: '{query}' | Historial: {chat_history} | Índice: {index_name}"
        )
        vectorstore = PineconeVectorStore(index_name=index_name, embedding=embeddings)

        chat = ChatOpenAI(
            verbose=True,
            temperature=0.15,
            top_p=0.85,
            model="gpt-4o-mini",
            max_tokens=4096,
        )
        logger.info(
            f"[AGENTE] Parámetros del modelo: temperature={chat.temperature}, top_p={chat.top_p}, max_tokens={chat.max_tokens}"
        )

        custom_prompt = PromptTemplate(
            input_variables=["context", "input"],
            template="""
            Eres un asistente experto en código de Terraform. Responde siempre en español, de forma clara y concisa.
            Si no sabes la respuesta, simplemente indícalo.
            Si has utilizado información de los documentos proporcionados en el contexto para responder, incluye al final la frase exacta '*fuentes utilizadas:*' seguida de las fuentes utilizadas.
            Si la respuesta es un saludo o no requiere información de los documentos, no incluyas la frase '*fuentes utilizadas:*' ni ninguna referencia a fuentes.
            Contexto:
            {context}
            Pregunta:
            {input}
            """,
        )

        stuff_documents_chain = create_stuff_documents_chain(chat, custom_prompt)

        logger.info(
            "[AGENTE] Descargando prompt de rephrase y configurando retriever..."
        )
        rephrase_prompt = hub.pull("langchain-ai/chat-langchain-rephrase")
        history_aware_retriever = create_history_aware_retriever(
            llm=chat, retriever=vectorstore.as_retriever(), prompt=rephrase_prompt
        )

        qa = create_retrieval_chain(
            retriever=history_aware_retriever, combine_docs_chain=stuff_documents_chain
        )

        logger.info("[AGENTE] Obteniendo respuesta final...")
        result = qa.invoke({"input": query, "chat_history": chat_history})

        logger.info(f"[AGENTE] Documentos consultados: {result}")
        context_docs = result.get("context", []) if isinstance(result, dict) else []

        logger.info(f"[AGENTE] Respuesta final del agente: {result['answer']}")

        return {
            "query": result["input"],
            "result": result["answer"],
            "source_documents": context_docs,
        }
    except Exception as e:
        logger.error(f"Error al ejecutar consulta en índice {index_name}: {e}")
        raise ValueError(f"Error al ejecutar consulta en índice {index_name}: {e}")


def create_sources_string(source_urls):
    if not source_urls:
        return ""
    sources_list = list(set(source_urls))
    sources_list.sort()
    sources_string = "Fuentes:\n"
    for i, source in enumerate(sources_list):
        sources_string += f"{i + 1}. {source}\n"
    return sources_string


if __name__ == "__main__":
    pass
