import os
from config.config import SETTINGS
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
    k_max = (
        state["k_docs"] + 5
    )  # Traer más documentos para que filtering los seleccione
    threshold = state["threshold"]

    try:
        logger.info(
            " - Iniciando búsqueda con search_examples",
            source="retrieval",
            question=question[:100],
            k_max=k_max,
        )

        hits = search_all_collections(
            query=question,
            collections=ALL_COLLECTIONS,
            k_per_collection=k_max,
            threshold=threshold,
        )

        # Ordenar los hits por score descendente y quedarse con los k_docs mejores
        hits = sorted(hits, key=lambda x: x.get("score", 0), reverse=True)[
            : state["k_docs"]
        ]

        logger.info(
            f"✅ search_examples retornó {len(hits)} resultados",
            source="retrieval",
            hits_count=len(hits),
        )

        # Convertir hits a DocumentScore (para LangGraph)
        raw_documents = []
        for rank, hit in enumerate(hits, 1):
            # Enriquecer metadata con un campo "ref" clicable si es posible
            md = hit.get("metadata", {}) or {}
            path = md.get("file_path") or hit.get("path") or ""
            pages = md.get("pages") or md.get("page")

            # --- LÓGICA DE GENERACIÓN DE ENLACES (S3 vs LOCAL) ---
            ref = ""
            s3_bucket = os.getenv("S3_DATA_BUCKET_NAME")
            aws_region = os.getenv(
                "AWS_DEFAULT_REGION", "eu-west-1"
            )  # Región por defecto si no está definida

            if path:
                if s3_bucket:
                    # ☁️ MODO NUBE (S3)
                    # El path indexado viene como "/app/data/pdfs/..." (ruta Docker)
                    # Lo convertimos a "data/pdfs/..." (Key de S3)
                    clean_key = path.replace("/app/", "", 1).lstrip("/")

                    # Construimos la URL pública de S3
                    # Formato: https://BUCKET.s3.REGION.amazonaws.com/KEY
                    ref = (
                        f"https://{s3_bucket}.s3.{aws_region}.amazonaws.com/{clean_key}"
                    )

                    # Si es un PDF y tenemos página, añadimos el ancla #page=X para que el navegador vaya directo
                    if pages and clean_key.endswith(".pdf"):
                        ref += f"#page={pages}"

                else:
                    # 💻 MODO LOCAL (Visor API)
                    # Mantiene la compatibilidad para cuando desarrollas en tu máquina
                    base_url = SETTINGS.API_URL
                    rel_path = ""
                    if "data/" in path.replace("\\", "/"):
                        # Extraer desde data/docs/ en adelante
                        rel_path = path.replace("\\", "/").split("data/", 1)[-1]
                        # Codificamos la ruta para la URL del visor local
                        ref = f"{base_url.rstrip('/')}/viewer/{rel_path.replace('/', '%2F')}"
                    else:
                        ref = f"{base_url.rstrip('/')}/{path}"

            # Guardar ref en metadata para que el Frontend lo pinte
            if ref:
                try:
                    md["ref"] = ref
                except Exception:
                    pass

            doc_score = DocumentScore(
                content=hit.get("content", ""),
                metadata=md,
                relevance_score=float(hit.get("score", 0.0)),  # Score de Qdrant
                source=hit.get("path", "unknown"),
                collection=hit.get("collection", "unknown"),
                line_number=None,
            )
            raw_documents.append(doc_score)

            logger.debug(
                f"Documento {rank} convertido a DocumentScore",
                source="retrieval",
                score=doc_score.relevance_score,
                source_file=doc_score.source,
            )

        logger.info(
            f"✅ Búsqueda completada",
            source="retrieval",
            documents_found=len(raw_documents),
            scores=[f"{d.relevance_score:.3f}" for d in raw_documents[:5]],
        )

        # Actualizar estado
        state["raw_documents"] = raw_documents
        state["documents"] = [doc.content for doc in raw_documents]
        # Propagar el campo `ref` en los metadatos
        state["documents_metadata"] = [
            {
                "metadata": doc.metadata,
                "source": doc.source,
                "score": doc.relevance_score,
                "collection": doc.collection,
                "ref": doc.metadata.get("ref", ""),  # Incluir el enlace clicable
            }
            for doc in raw_documents
        ]
        state["messages"].append(
            f"📚 Recuperados {len(raw_documents)} documentos crudos"
        )

        return state

    except Exception as e:
        logger.error(
            f"❌ Error durante la recuperación de documentos",
            source="retrieval",
            error=str(e),
            error_type=type(e).__name__,
            question=question[:100],
        )
        state["messages"].append(f"❌ Error en recuperación: {str(e)}")
        state["raw_documents"] = []
        return state
