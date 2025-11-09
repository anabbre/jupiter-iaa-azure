import os, sys, logging
from pathlib import Path
from typing import List
import yaml

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, SearchRequest
from sentence_transformers import SentenceTransformer

# --- logging sencillo a consola ---
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger("search_examples")

load_dotenv()
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
MANIFEST_PATH = os.getenv("EXAMPLES_MANIFEST", "docs/examples/manifest.yaml")

def load_manifest():
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def main():
    if len(sys.argv) < 2:
        print("Uso: python Scripts/RAG/search_examples.py \"tu consulta\" [k]")
        sys.exit(1)
    query = sys.argv[1]
    top_k = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    manifest = load_manifest()
    collection = manifest["collection"]
    model_name = manifest.get("embeddings_model", "intfloat/multilingual-e5-small")

    log.info(f"Qdrant: {QDRANT_URL} | collection: {collection}")
    log.info(f"Modelo: {model_name}")
    model = SentenceTransformer(model_name)

    # E5: anteponer "query: "
    embedding = model.encode(f"query: {query}")

    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    results = client.search(
        collection_name=collection,
        query_vector=embedding,
        limit=top_k,
        with_payload=True
    )

    print("\n== Resultados ==")
    for i, r in enumerate(results, 1):
        name = r.payload.get("name")
        tags = ", ".join(r.payload.get("tags", []))
        path = r.payload.get("path")
        print(f"{i}. score={r.score:.4f} | {name} | [{tags}]")
        print(f"   {path}")

if __name__ == "__main__":
    main()
