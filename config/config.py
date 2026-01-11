import os
from dataclasses import dataclass


@dataclass
class Settings:
    # Dentro de Docker la URL de Qdrant es el nombre del servicio del compose
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")

    # Usa la colección donde ya se indexaron los ejemplos
    QDRANT_COLLECTION_NAME: str = os.getenv("QDRANT_COLLECTION", "terraform_book")
    THRESHOLD: float = float(os.getenv("SCORE_THRESHOLD", "0.82"))

    # Mismo modelo que se usa al indexar (384 dims)
    EMBEDDINGS_MODEL_NAME: str = os.getenv(
        "EMBEDDING_MODEL", "intfloat/multilingual-e5-small"
    )

    LLM_MODEL_NAME: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    K_DOCS: int = int(os.getenv("K_DOCS", 5))
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", 0.0))
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", 3))

    API_URL: str = os.getenv("API_URL", "http://localhost:8008")


SETTINGS = Settings()
