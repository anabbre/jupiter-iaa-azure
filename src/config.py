import os
from dataclasses import dataclass

@dataclass
class Settings:
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION_NAME: str ="Terraform_Book_Index"
    EMBEDDINGS_MODEL_NAME: str = "text-embedding-3-small"
    LLM_MODEL_NAME: str = "gpt-4o-mini"
    K_DOCS: int = 3
    LLM_TEMPERATURE: float =  0.0
    LLM_MAX_RETRIES: int = 3

    API_URL: str = os.getenv("API_URL", "http://localhost:8008")


SETTINGS = Settings()