import sys
import os
import time
import re
from dotenv import load_dotenv
from logger_config import logger, get_request_id, set_request_id
# Configurar paths y cargar variables de entorno
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
load_dotenv()
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from qdrant_client.models import VectorParams, Distance
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from src.services.embeddings import embeddings_model
from uuid import uuid4
from glob import glob
from pypdf import PdfReader


def load_pdf_documents(data_path: str) -> list[Document]:
    # Carga de documentos 
    print(f"\n📂 Cargando documentos desde: {data_path}")
    if not request_id:
        request_id = get_request_id()
    logger.info("Iniciando carga de documentos PDF",data_path=data_path,request_id=request_id,source="qdrant")

    try:
        pdf_files = sorted(glob(os.path.join(data_path, "*.pdf")))
        print(f"📄 Total de archivos PDF encontrados: {len(pdf_files)}")
        logger.info(f"📄 Total de archivos PDF encontrados: {len(pdf_files)}")
        documents = []

        for pdf_file in pdf_files:
            loader = PyPDFLoader(pdf_file)
            pages = loader.load()
            combined_content = "\n\n".join([page.page_content for page in pages])
            file_name = os.path.basename(pdf_file)
            source_name = os.path.splitext(file_name)[0]
            metadata = extract_pdf_metadata(pdf_file, file_name, len(pages))
            metadata['source'] = source_name
            metadata['file_path'] = pdf_file
            metadata['num_pages'] = len(pages)
            doc = Document(page_content=combined_content, metadata=metadata)
            documents.append(doc)

        print(f"📄 Total de documentos cargados: {len(documents)}")
        logger.debug("PDF cargado exitosamente",archivo=file_name,paginas=len(pages),request_id=request_id,source="qdrant")
    except Exception as e:
        logger.error("Error cargando PDF individual",archivo=os.path.basename(pdf_file),error=str(e),tipo_error=type(e).__name__,request_id=request_id,source="qdrant")
    
    logger.info("Carga de documentos completada",total_documentos=len(documents),request_id=request_id,source="qdrant")
        
    return documents


def extract_pdf_metadata(pdf_file: str, file_name: str, num_pages: int) -> dict:
    # Extraer metadatps del PDF
    if not request_id:
        request_id = get_request_id()
        
    metadata = {}
    try:
        logger.debug("Extrayendo metadatos del PDF",archivo=file_name,request_id=request_id,source="qdrant")
        reader = PdfReader(pdf_file)
        metadata_pdf = reader.metadata
        if metadata_pdf and '/Subject' in metadata_pdf:
            subject = metadata_pdf['/Subject']
            match = re.search(r'Páginas?\s*(\d+)-(\d+)', subject, re.IGNORECASE)
            if match:
                page_start = int(match.group(1))
                page_end = int(match.group(2))
                pages_range = f"{page_start}-{page_end}" if page_start != page_end else f"{page_start}"
                metadata['original_pages_range'] = pages_range
                
                logger.debug("Rango de páginas detectado",archivo=file_name,rango=pages_range,request_id=request_id,source="qdrant")
    except Exception as e:
        print(f"⚠️  No se pudo leer metadatos de {file_name}: {e}")
        logger.warning("No se pudo leer metadatos del PDF",archivo=file_name,error=str(e),tipo_error=type(e).__name__,request_id=request_id,source="qdrant")
    return metadata


def create_or_recreate_collection(qdrant_client: QdrantClient, collection_name: str, vector_size: int = 1536):
    # Creacion de la coleccion
    if not request_id:
        request_id = get_request_id()
    
    logger.info("Iniciando creación/recreacion de colección",collection_name=collection_name,vector_size=vector_size,request_id=request_id,source="qdrant")
    print(f"\n🗑️  Eliminando colección existente (si existe)...")
    
    try:
        qdrant_client.get_collection(collection_name=collection_name)
        qdrant_client.delete_collection(collection_name=collection_name)
        print("✅ Colección eliminada")
        logger.debug("Colección existente encontrada, eliminando",collection_name=collection_name,request_id=request_id,source="qdrant")
    except Exception:
        print("ℹ️  No existía colección previa")
        logger.debug("Colección no existia",collection_name=collection_name,request_id=request_id,source="qdrant")

    print(f"\n🔧 Creando colección '{collection_name}' con {vector_size} dimensiones (OpenAI)...")
    qdrant_client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )
    print("✅ Colección creada")
    logger.info("Colección creada exitosamente",collection_name=collection_name,vector_size=vector_size,request_id=request_id,source="qdrant")


def index_documents(qdrant_client: QdrantClient, documents: list[Document], collection_name: str):
    # Indexa documentos en Qdrant con embeddings
    if not request_id:
        request_id = get_request_id()
    
    logger.info("Iniciando indexación de documentos",total_documentos=len(documents),collection_name=collection_name,request_id=request_id,source="qdrant")
    try:
        vector_store = QdrantVectorStore(
            client=qdrant_client,
            collection_name=collection_name,
            embedding=embeddings_model
        )
        logger.info("Vector store inicializado",collection_name=collection_name,request_id=request_id,source="qdrant")

        print(f"\n📥 Insertando {len(documents)} documentos en Qdrant con IDs únicos...")
        logger.info(f"\n📥 Insertando {len(documents)} documentos en Qdrant con IDs únicos...")
        indexed_count = 0
        errors_count = 0
        for i, document in enumerate(documents, 1):
            try:
                start_time = time.time()
                doc_id = str(uuid4())
                document.metadata['doc_id'] = doc_id
                vector_store.add_documents(documents=[document], ids=[doc_id])
                pages_info = f"({document.metadata.get('num_pages', '?')} páginas)"
                original_pages = document.metadata.get('original_pages_range')
                original_pages_info = f" | Págs. originales: {original_pages}" if original_pages else ""
                print(f"   [{i}/{len(documents)}] ✅ ID: {doc_id[:8]}... | {document.metadata.get('source', 'documento')} {pages_info}{original_pages_info}")
                duration = time.time() - start_time
                logger.info("Documento indexado exitosamente",numero=f"{i}/{len(documents)}",doc_id=doc_id[:8],paginas=pages_info,paginas_originales=original_pages,duration=f"{duration:.3f}s",request_id=request_id,source="qdrant",process_time=f"{duration:.3f}s")
                indexed_count += 1
                time.sleep(0.5)
            except Exception as e:
                errors_count += 1
                logger.error("Error indexando documento",numero=i,total=len(documents),error=str(e),tipo_error=type(e).__name__,request_id=request_id,source="qdrant")
                continue
    except Exception as e:
        logger.error("Error crítico durante indexación",collection_name=collection_name,error=str(e),tipo_error=type(e).__name__,request_id=request_id,source="qdrant")
        raise


def main():
    # Creacion del indice
    start_time = time.time()
    request_id = f"qdrant_index_{int(time.time())}"
    set_request_id(request_id)
    
    logger.info("🚀... Iniciando creación del índice en Qdrant",request_id=request_id,source="qdrant")
    print("=" * 60)
    print("🚀 Iniciando creación del índice en Qdrant")
    print("=" * 60)
    
    try: 
        data_path = os.path.join(os.path.dirname(__file__), '../../data/optimized_chunks/Libro-TF')
        collection_name = "Terraform_Book_Index"

        # Crear cliente Qdrant localmente para evitar ejecutar código de inicialización
        qdrant_url = os.getenv('QDRANT_URL', 'http://localhost:6333')
        qdrant_api_key = os.getenv('QDRANT_API_KEY', None)
        qdrant_client = QdrantClient(url=qdrant_url, prefer_grpc=False, api_key=qdrant_api_key)

        logger.info("Conexión a Qdrant establecida",url=qdrant_url,request_id=request_id,source="qdrant")
        # 1. Cargar documentos
        documents = load_pdf_documents(data_path)
        if not documents:
            logger.error("No se cargaron documentos",data_path=data_path,request_id=request_id,source="qdrant")
            return
        # 2. Crear/recrear colección (usa el cliente creado arriba)
        create_or_recreate_collection(qdrant_client, collection_name)
        # 3. Indexar documentos
        index_documents(qdrant_client, documents, collection_name)

        print(f"\n{'=' * 60}")
        print("✨ Proceso completado exitosamente")        
        print(f"📊 Total de documentos indexados: {len(documents)}")
        print(f"{'=' * 60}\n")
        
        duration = time.time() - start_time 
        logger.info("✨ Proceso completado exitosamente",documentos_indexados=len(documents),collection_name=collection_name,duration=f"{duration:.3f}s",request_id=request_id,source="qdrant",process_time=f"{duration:.3f}s")
    except Exception as e:
        duration = time.time() - start_time
        logger.error("❌ Error crítico en proceso de indexación",error=str(e),tipo_error=type(e).__name__,duration=f"{duration:.3f}s",request_id=request_id,source="qdrant",process_time=f"{duration:.3f}s")
        raise


if __name__ == "__main__":
    main()