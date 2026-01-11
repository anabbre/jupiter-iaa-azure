
from src.Agent.state import AgentState, DocumentScore
from src.services.search import search_all_collections 
from config.logger_config import logger

ALL_COLLECTIONS = ["terraform_book", "examples_terraform"]
def retrieve_documents(state: AgentState) -> AgentState:
    """
    Busca documentos usando search_examples() 
    (la función de búsqueda de tu API actual)
    
    Args:
        state: Estado actual del grafo
    
    Returns:
        Estado actualizado con documentos crudos (sin filtrar)
    """
    question = state["question"]
    k_max = state["k_docs"] + 5  # Traer más documentos para que filtering los seleccione
    threshold = state["threshold"]
    
    try:
        logger.info(" - Iniciando búsqueda con search_examples",source="retrieval",question=question[:100],k_max=k_max)
        
        hits = search_all_collections(
            query=question,
            collections=ALL_COLLECTIONS,
            k_per_collection=k_max,
            threshold=threshold
        )

        logger.info(f"✅ search_examples retornó {len(hits)} resultados",source="retrieval",hits_count=len(hits))
        
        # Convertir hits a DocumentScore (para LangGraph)
        raw_documents = []
        for rank, hit in enumerate(hits, 1):
            doc_score = DocumentScore(
                content=hit.get("content", ""),
                metadata=hit.get("metadata", {}),
                relevance_score=float(hit.get("score", 0.0)),
                source=hit.get("path", "unknown"),
                collection=hit.get("collection", "unknown"),
                line_number=None
            )
            raw_documents.append(doc_score)
            
            logger.debug(f"Documento {rank} convertido a DocumentScore",source="retrieval",score=doc_score.relevance_score,source_file=doc_score.source)
        
        logger.info(f"✅ Búsqueda completada",source="retrieval",documents_found=len(raw_documents),scores=[f"{d.relevance_score:.3f}" for d in raw_documents[:5]])
        
        # Actualizar estado
        state["raw_documents"] = raw_documents
        state["documents"] = [doc.content for doc in raw_documents]
        state["documents_metadata"] = [
            {
                "metadata": doc.metadata,
                "source": doc.source,
                "score": doc.relevance_score,
                "collection": doc.collection
            }
            for doc in raw_documents
        ]
        state["messages"].append(
            f"📚 Recuperados {len(raw_documents)} documentos crudos"
        )
        
        return state
        
    except Exception as e:
        logger.error(f"❌ Error durante la recuperación de documentos",source="retrieval",error=str(e),error_type=type(e).__name__,question=question[:100])
        state["messages"].append(f"❌ Error en recuperación: {str(e)}")
        state["raw_documents"] = []
        return state