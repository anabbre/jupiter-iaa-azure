# # langgraph_agent/nodes/retrieval.py
# """
# Nodo de recuperación de documentos
# """
# from src.Agent.state import AgentState
# from src.services.vector_store import qdrant_vector_store, n_docs
# from config.logger_config import logger, get_request_id, set_request_id

# def retrieve_documents(state: AgentState) -> AgentState:
#     """
#     Busca documentos relevantes en la DB vectorial

#     Args:
#         state: Estado actual del grafo

#     Returns:
#         Estado actualizado con documentos recuperados
#     """
    
#     question = state["question"]
#     try: 
#         # Buscar documentos similares
#         docs = qdrant_vector_store.similarity_search(question, k=n_docs)

#         # Actualizar estado
#         state["documents"] = [doc.page_content for doc in docs]
#         logger.info(" - Búsqueda completada",source="agent")

#         state["documents_metadata"] = [
#             {
#                 "metadata": doc.metadata,  # Metadata del documento (página, fuente, etc.)
#             }
#             for doc in docs
#         ]

#         state["messages"].append(f"📚 Recuperados {len(docs)} documentos")
#         logger.info("✅ Estado actualizado exitosamente",source="agent")
#         return state
#     except Exception as e:
#         logger.error(f"❌ Error durante la recuperación de documentos", source="agent",error=str(e),tipo_error=type(e).__name__)
#         state["messages"].append(f"❌ Error en recuperación: {str(e)}",source="agent")
#         raise

from src.Agent.state import AgentState, DocumentScore
from src.services.search import search_examples  # ← Tu search.py
from config.logger_config import logger


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
    k_max = 10  # Traer más documentos para que filtering los seleccione
    
    try:
        logger.info(" - Iniciando búsqueda con search_examples",source="retrieval",question=question[:100],k=k_max)
        
        # Usar TU search_examples actual
        # Retorna: List[Dict] con keys: score, content, metadata, path, doc_type, etc
        hits = search_examples(
            question, 
            k=k_max, 
            threshold=0.7,
            collections=state.get("target_collections")  
        )

        logger.info(f"✅ search_examples retornó {len(hits)} resultados",source="retrieval",hits_count=len(hits))
        
        # Convertir hits a DocumentScore (para LangGraph)
        raw_documents = []
        for rank, hit in enumerate(hits, 1):
            doc_score = DocumentScore(
                content=hit.get("content", ""),
                metadata=hit.get("metadata", {}),
                relevance_score=float(hit.get("score", 0.0)),  # Score de Qdrant
                source=hit.get("path", "unknown"),
                line_number=None  # No aplica para Terraform
            )
            raw_documents.append(doc_score)
            
            logger.debug(f"Documento {rank} convertido a DocumentScore",source="retrieval",score=doc_score.relevance_score,source_file=doc_score.source)
        
        logger.info(f"✅ Búsqueda completada",source="retrieval",documents_found=len(raw_documents),scores=[f"{d.relevance_score:.3f}" for d in raw_documents[:5]])
        
        # Actualizar estado
        state["raw_documents"] = raw_documents
        state["documents"] = [doc.content for doc in raw_documents]
        state["documents_metadata"] = [{"metadata": doc.metadata, "source": doc.source, "score": doc.relevance_score} for doc in raw_documents]
        state["messages"].append(
            f"📚 Recuperados {len(raw_documents)} documentos crudos"
        )
        
        return state
        
    except Exception as e:
        logger.error(f"❌ Error durante la recuperación de documentos",source="retrieval",error=str(e),error_type=type(e).__name__,question=question[:100])
        state["messages"].append(f"❌ Error en recuperación: {str(e)}")
        state["raw_documents"] = []
        raise