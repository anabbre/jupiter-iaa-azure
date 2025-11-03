import os
from dataclasses import dataclass

@dataclass
class Settings:
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_COLLECTION_NAME: str = os.getenv("QDRANT_COLLECTION", "Terraform_Book_Index")
    EMBEDDINGS_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    LLM_MODEL_NAME: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    K_DOCS: int = int(os.getenv("K_DOCS", 3))
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", 0.0))
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", 3))

    API_URL: str = os.getenv("API_URL", "http://localhost:8008")


SETTINGS = Settings()