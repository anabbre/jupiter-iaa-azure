from config.project_config import SETTINGS
from fastapi import APIRouter

from schemas import RAGRequest
from langchain_qdrant import QdrantVectorStore
from langchain_chain.chain import rag_chain

from config.project_config import SETTINGS

router = APIRouter()

@router.post("/rag")
async def rag_endpoint(request: RAGRequest):
    """
    Endpoint to interact with the RAG system.
    """
    result = await rag_chain.ainvoke({"question": request.question})
    return {
        "question": result["question"],
        "answer": result["answer"],
        "source": result["source"].selection if result.get('source') else None,
        "source_reason": result["source"].reason if result.get('source') else None
    }

@router.post("/search")
async def search(query: str):

    vector_store = QdrantVectorStore.from_existing_collection(
        client=SETTINGS.qdrant_client,
        collection_name=SETTINGS.qdrant_collection,
        embedding=SETTINGS.embeddings_model,
    )

    found_docs = vector_store.similarity_search(query, k=SETTINGS.k_docs)
    return found_docs