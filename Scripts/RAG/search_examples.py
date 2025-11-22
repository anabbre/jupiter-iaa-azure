import os, sys, logging
import yaml
from pathlib import Path
from typing import List
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, SearchRequest
from sentence_transformers import SentenceTransformer
from config.logger_config import logger, get_request_id, set_request_id


load_dotenv()
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
MANIFEST_PATH = os.getenv("EXAMPLES_MANIFEST", "docs/examples/manifest.yaml")

def load_manifest():
    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            logger.info("✅ Manifest loaded correctamente", source="qdrant", manifest_path=MANIFEST_PATH)
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"❌ Error cargando el manifest: {e}", source="qdrant", manifest_path=MANIFEST_PATH)
        raise

def main():
    if len(sys.argv) < 2:
        logger.error("Uso: python Scripts/RAG/search_examples.py \"tu consulta\" [k]", source="qdrant")
        print("Uso: python Scripts/RAG/search_examples.py \"tu consulta\" [k]")
        sys.exit(1)
    
    query = sys.argv[1]
    top_k = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    logger.info(f"🔍 Iniciando búsqueda", source="qdrant", query=query, top_k=top_k)
    manifest = load_manifest()
    collection = manifest["collection"]
    model_name = manifest.get("embeddings_model", "intfloat/multilingual-e5-small")

    logger.info(f"Qdrant: {QDRANT_URL} | collection: {collection}", source="qdrant")
    
    logger.info(f"Modelo: {model_name}", source="qdrant",query=query)
    model = SentenceTransformer(model_name)

    # E5: anteponer "query: "
    embedding = model.encode(f"query: {query}") 
    logger.info(f"Conectando a Qdrant: {QDRANT_URL}", source="qdrant", qdrant_url=QDRANT_URL)
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    
    try:
        results = client.search(
            collection_name=collection,
            query_vector=embedding,
            limit=top_k,
            with_payload=True
        )
        logger.info(f"Búsqueda realizada para query: '{query}' con top_k={top_k}", source="qdrant")
        print("\n== Resultados ==")
        for i, r in enumerate(results, 1):
            metadata = r.payload.get("metadata", {})
            name = metadata.get("name", "N/A")
            tags = ", ".join(metadata.get("tags", []))
            path = metadata.get("path", "N/A")
            doc_type = metadata.get("doc_type", "N/A")
            
            print(f"{i}. score={r.score:.4f} | {name} | [{tags}]")
            print(f"   path: {path}")
            print(f"   type: {doc_type}")
        
            logger.info(f"Resultado encontrado",source="qdrant",result_index=i,result_score=r.score,result_name=name,result_tags=tags,result_path=path,result_type=doc_type)
    except Exception as e:
        logger.error(f"❌ Error en la búsqueda: {e}", source="qdrant",query=query, error_type=type(e).__name__)
        sys.exit(2)     
    


if __name__ == "__main__":
    main()