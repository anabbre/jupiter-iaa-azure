import os
from dataclasses import dataclass
from qdrant_client import QdrantClient
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings

@dataclass
class Settings:
    qdrant_url: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_collection: str = os.getenv("QDRANT_COLLECTION", "terraform_docs_index_pre")
    embedding_model_name: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
    llm_model_name: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    persist_db_dir: str = os.getenv("DB_DIR", "src/rag/vector_db")
    k_docs: int = int(os.getenv("K_DOCS", 5))
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")

    # modelo de embeddings
    embeddings_model = OpenAIEmbeddings(model=embedding_model_name)
    qdrant_client = QdrantClient(url=qdrant_url)

SETTINGS = Settings()