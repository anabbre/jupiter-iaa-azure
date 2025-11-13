import os, sys, logging
from pathlib import Path
from typing import List
import yaml

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, SearchRequest
from sentence_transformers import SentenceTransformer
from config.logger_config import logger, get_request_id, set_request_id


load_dotenv()
QDRANT_URL = "http://qdrant:6333"
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
MANIFEST_PATH = os.getenv("EXAMPLES_MANIFEST", "docs/examples/manifest.yaml")

def load_manifest():
    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
        logger.info("✅ Manifest loaded correctamente", source="qdrant")
    except Exception as e:
        logger.error(f"❌ Error cargando el manifest: {e}", source="qdrant")
        raise

def main():
    if len(sys.argv) < 2:
        logger.error("Uso: python Scripts/RAG/search_examples.py \"tu consulta\" [k]", source="qdrant")
        print("Uso: python Scripts/RAG/search_examples.py \"tu consulta\" [k]")
        sys.exit(1)
    query = sys.argv[1]
    top_k = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    manifest = load_manifest()
    collection = manifest["collection"]
    model_name = manifest.get("embeddings_model", "intfloat/multilingual-e5-small")

    logger.info(f"Qdrant: {QDRANT_URL} | collection: {collection}", source="qdrant")
    logger.info(f"Modelo: {model_name}", source="qdrant")
    model = SentenceTransformer(model_name)

    # E5: anteponer "query: "
    embedding = model.encode(f"query: {query}")

    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    try:
        results = client.search(
            collection_name=collection,
            query_vector=embedding,
            limit=top_k,
            with_payload=True
        )
        logger.info(f"Búsqueda realizada para query: '{query}' con top_k={top_k}", source="qdrant")
    except Exception as e:
        logger.error(f"❌ Error en la búsqueda: {e}", source="qdrant")
        sys.exit(2)     
    

        print("\n== Resultados ==")
        for i, r in enumerate(results, 1):
            name = r.payload.get("name")
            tags = ", ".join(r.payload.get("tags", []))
            path = r.payload.get("path")
            print(f"{i}. score={r.score:.4f} | {name} | [{tags}]")
            print(f"   {path}")
            logger.info(f"Resultado {i}: {name} | score={r.score:.4f} | tags=[{tags}] | path={path}",source="qdrant",result_index=i,result_score=r.score,result_name=name,result_tags=tags,result_path=path)

if __name__ == "__main__":
    main()