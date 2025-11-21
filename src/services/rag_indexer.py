
import os
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
import json
import time
import yaml
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import hashlib

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance
from langchain_qdrant import QdrantVectorStore
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.services.embeddings import embeddings_model
from config.logger_config import logger, set_request_id, get_request_id

# CONFIGURACIÓN

load_dotenv()

class DocumentType(Enum):
    """Tipos de documentos soportados"""
    PDF = "pdf"
    TERRAFORM = "terraform"
    MARKDOWN = "markdown"
    EXAMPLE = "example"

@dataclass
class IndexConfig:
    """Configuración centralizada del indexador"""
    qdrant_url: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_api_key: Optional[str] = os.getenv("QDRANT_API_KEY")
    collections: Dict[str, str] = None
    data_dir: Path = Path("data").resolve()  
    manifest_path: Path = Path("data/docs/examples/manifest.yaml").resolve() 
    chunk_size: int = 800
    chunk_overlap: int = 120
    batch_size: int = 50
    max_workers: int = 4
    
    # Inicializar colecciones por defecto
    def __post_init__(self):
        if self.collections is None:
            self.collections = {
                "pdfs": "terraform_book",
                "examples": "examples_terraform",
                "code": "terraform_code"
            }

# DEDUPLICADOR DE CHUNKS
class ChunkDeduplicator:
    """Evita duplicación de chunks basándose en contenido y metadatos"""
    def __init__(self):
        self.seen_hashes: Dict[str, str] = {}
        self.duplicates_removed = 0
    
    @staticmethod
    def _hash_chunk(content: str, metadata_keys: Tuple[str, ...]) -> str:
        """Genera hash único para un chunk"""
        hash_input = content
        if metadata_keys:
            hash_input += "||".join(metadata_keys)
        return hashlib.md5(hash_input.encode()).hexdigest()
    
    def is_duplicate(self, content: str, metadata: Dict[str, Any], metadata_keys: Tuple[str, ...] = ("source", "page")) -> bool:
        """Detecta si un chunk es duplicado"""
        meta_values = tuple(str(metadata.get(k, "")) for k in metadata_keys if metadata.get(k) is not None)
        chunk_hash = self._hash_chunk(content, meta_values)
        
        if chunk_hash in self.seen_hashes:
            self.duplicates_removed += 1
            return True
        
        self.seen_hashes[chunk_hash] = content[:100]
        return False
    
    def get_stats(self) -> Dict[str, int]:
        """Retorna estadísticas de deduplicación"""
        return {
            "unique_chunks": len(self.seen_hashes),
            "duplicates_removed": self.duplicates_removed,
            "total_processed": len(self.seen_hashes) + self.duplicates_removed
        }

# CARGADORES DE DOCUMENTOS
class DocumentLoader:
    """Cargador unificado de documentos"""
    
    def __init__(self, config: IndexConfig):
        self.config = config
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap
        )
        self.deduplicator = ChunkDeduplicator()
        self.request_id = get_request_id()
    
    def load_pdfs(self, pdf_dir: Path) -> List[Document]:
        """Carga PDFs completos o desde directorio"""
        documents = []
        pdf_files = sorted(pdf_dir.glob("**/*.pdf")) if pdf_dir.is_dir() else [pdf_dir]
        
        logger.info(f"📄 Cargando {len(pdf_files)} PDFs", source="indexer", pdf_count=len(pdf_files))
        
        for pdf_file in pdf_files:
            try:
                loader = PyPDFLoader(str(pdf_file))
                pages = loader.load()
            
                # Filtra páginas sin contenido
                valid_pages = [p for p in pages if p and p.page_content and p.page_content.strip()]
                print(f"DEBUG: Valid pages after filter: {len(valid_pages)}")
                if not valid_pages:
                    logger.warning(f"⏭️ PDF sin contenido válido", source="indexer", file=pdf_file.name)
                    continue  

                contents = []
                for i, p in enumerate(valid_pages):
                    content = p.page_content
                    if content is None:
                        print(f"DEBUG: Page {i} has None content!")
                        continue
                    content_str = str(content).strip()
                    if not content_str:
                        print(f"DEBUG: Page {i} is empty string!")
                        continue
                    contents.append(content_str)
            
                print(f"DEBUG: Final contents count: {len(contents)}")
                if not contents:
                    print("DEBUG: No valid contents after filtering!")
                    continue
                    
                combined_content = "\n\n".join(contents)
                print(f"DEBUG: Successfully joined {len(contents)} pages")
                    # combined_content = "\n\n".join([p.page_content for p in valid_pages])
                
                # Verificar duplicados
                if not self.deduplicator.is_duplicate(combined_content, {"source": str(pdf_file)}):
                    doc = Document(
                        page_content=combined_content,
                        metadata={
                            "source": pdf_file.name,
                            "file_path": str(pdf_file),
                            "file_type": "pdf",
                            "num_pages": len(pages),
                            "doc_type": "terraform_book"
                        }
                    )
                    # Añadir documento completo
                    documents.append(doc)
                    logger.info(f"✅ PDF cargado", source="indexer", file=pdf_file.name, pages=len(pages))
                else:
                    logger.info(f"⏭️ PDF duplicado omitido", source="indexer",  file=pdf_file.name)
                    
            except Exception as e:
                logger.error(f"❌ Error cargando PDF", source="indexer", file=pdf_file.name, error=str(e))
        return documents
    
    def load_terraform_files(self, tf_dir: Path) -> List[Document]:
        """Carga archivos Terraform"""
        documents = []
        tf_files = sorted(tf_dir.glob("**/*.tf"))
        logger.info(f"🔧 Cargando {len(tf_files)} archivos Terraform", 
                source="indexer", tf_count=len(tf_files))
        
        for tf_file in tf_files:
            try:
                with open(tf_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if content and content.strip():
                    if not self.deduplicator.is_duplicate(content, {"source": str(tf_file)}):
                        # ✅ CAMBIO: Usar split_documents en lugar de split_text
                        temp_doc = Document(page_content=content, metadata={"source": str(tf_file)})
                        chunks = self.splitter.split_documents([temp_doc])
                        # Filtrar chunks vacíos/None
                        chunks = [c for c in chunks if c and c.page_content and c.page_content.strip()]
                        
                        if chunks:
                            for i, chunk in enumerate(chunks):
                                chunk.metadata.update({
                                    "source": tf_file.name,
                                    "file_path": str(tf_file),
                                    "file_type": "terraform",
                                    "chunk_id": i,
                                    "doc_type": "terraform_code"
                                })
                                documents.append(chunk)
                            
                            logger.info(f"✅ TF cargado", source="indexer", file=tf_file.name, chunks=len(chunks))
                    else:
                        logger.info(f"⏭️ TF duplicado omitido", source="indexer", file=tf_file.name)  
            except Exception as e:
                logger.error(f"❌ Error cargando TF", source="indexer", file=tf_file.name, error=str(e))
        return documents
    
    def load_markdown_files(self, md_dir: Path) -> List[Document]:
        """Carga archivos Markdown"""
        documents = []
        md_files = sorted(md_dir.glob("**/*.md"))
        
        logger.info(f"📝 Cargando {len(md_files)} archivos Markdown", 
                   source="indexer", md_count=len(md_files))
        
        for md_file in md_files:
            try:
                loader = TextLoader(str(md_file), encoding='utf-8')
                md_docs = loader.load()
                chunks = self.splitter.split_documents(md_docs)
                # Chunks no vacios
                chunks = [c for c in chunks if c and c.page_content and c.page_content.strip()]
            
                if chunks:  # ✅ Verificar que haya chunks
                    for doc in chunks:
                        if not self.deduplicator.is_duplicate(doc.page_content, {"source": str(md_file)}):
                            doc.metadata.update({
                                "source": md_file.name,
                                "file_path": str(md_file),
                                "file_type": "markdown",
                                "doc_type": "documentation"
                            })
                            documents.append(doc)
                    logger.info(f"✅ MD cargado", source="indexer", file=md_file.name, chunks=len(md_docs)) 
            except Exception as e:
                logger.error(f"❌ Error cargando MD", source="indexer", file=md_file.name, error=str(e))
        
        return documents
    
    def load_from_manifest(self) -> List[Document]:
        """Carga ejemplos desde manifest.yaml"""
        documents = []
        try:
            with open(self.config.manifest_path, 'r', encoding='utf-8') as f:
                manifest = yaml.safe_load(f)
            
            examples = manifest.get("examples", [])
            logger.info(f"📋 Cargando {len(examples)} ejemplos del manifest", 
                       source="indexer", examples_count=len(examples))
            
            for ex in examples:
                ex_path = Path(ex["path"])
                
                if ex_path.is_file() and ex_path.suffix == ".pdf":
                    docs = self.load_pdfs(ex_path)
                elif ex_path.is_dir():
                    # Cargar todos los tipos de archivo del directorio
                    docs = (self.load_terraform_files(ex_path) + self.load_markdown_files(ex_path))
                else:
                    continue
                
                # Añadir metadatos del manifest
                for doc in docs:
                    doc.metadata.update({
                        "example_id": ex.get("id"),
                        "example_name": ex.get("name"),
                        "tags": ex.get("tags", [])
                    })
                
                documents.extend(docs)
                logger.info(f"✅ Ejemplo '{ex.get('id')}' cargado", source="indexer", docs_count=len(docs))
        
        except FileNotFoundError:
            logger.warning(f"⚠️ Manifest no encontrado", source="indexer", path=str(self.config.manifest_path))
        except Exception as e:
            logger.error(f"❌ Error cargando manifest", source="indexer", error=str(e))
        
        return documents

# INDEXADOR
class QdrantIndexer:
    """Orquestador de indexación en Qdrant"""
    def __init__(self, config: IndexConfig):
        self.config = config
        self.client = self._create_client()
        self.loader = DocumentLoader(config)
        self.request_id = get_request_id()
    
    def _create_client(self) -> QdrantClient:
        """Crea cliente Qdrant"""
        try:
            kwargs = {"url": self.config.qdrant_url, "prefer_grpc": False}
            if self.config.qdrant_api_key:
                kwargs["api_key"] = self.config.qdrant_api_key
            
            client = QdrantClient(**kwargs)
            logger.info("✅ Conexión Qdrant establecida", source="indexer",url=self.config.qdrant_url)
            return client
        except Exception as e:
            logger.error("❌ Error conectando Qdrant", source="indexer", error=str(e))
            raise
    
    def prepare_collection(self, collection_name: str, recreate: bool = False):
        """Prepara colección (crea o recrea según necesidad)"""
        try:
            existing = [c.name for c in self.client.get_collections().collections]
            
            if collection_name in existing and recreate:
                logger.info(f"🗑️ Eliminando colección '{collection_name}'", 
                           source="indexer")
                self.client.delete_collection(collection_name)
            
            if collection_name not in existing or recreate:
                logger.info(f"🔧 Creando colección '{collection_name}'", 
                           source="indexer", collection=collection_name)
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=384,
                        distance=Distance.COSINE
                    )
                )
            else:
                logger.info(f"ℹ️ Colección '{collection_name}' ya existe", source="indexer")
        
        except Exception as e:
            logger.error(f"❌ Error preparando colección", source="indexer", collection=collection_name, error=str(e))
            raise
    
    def index_documents(self, documents: List[Document], collection_name: str,batch_size: Optional[int] = None):
        """Indexa documentos en Qdrant"""
        if not documents:
            logger.warning("⚠️ No hay documentos para indexar", source="indexer")
            return
        
        batch_size = batch_size or self.config.batch_size
        total = len(documents)
        logger.info(f"📥 Indexando {total} documentos en '{collection_name}'", 
                   source="indexer", docs_count=total, batch_size=batch_size)
        
        try:
            vector_store = QdrantVectorStore(
                client=self.client,
                collection_name=collection_name,
                embedding=embeddings_model
            )
            
            # Procesar en batches
            indexed = 0
            for i in range(0, total, batch_size):
                batch = documents[i:i+batch_size]
                try:
                    vector_store.add_documents(batch)
                    indexed += len(batch)
                    progress = (indexed / total) * 100
                    logger.info(f"✅ Batch {i//batch_size + 1} completado", source="indexer", documents=indexed, progress=f"{progress:.1f}%")
                    print(f"  [{progress:5.1f}%] {indexed}/{total} documentos indexados")
                
                except Exception as e:
                    logger.error(f"❌ Error en batch", source="indexer", batch=i//batch_size + 1, error=str(e))
            
            logger.info(f"✅ Indexación completada", source="indexer", collection=collection_name, docs_indexed=indexed)
        
        except Exception as e:
            logger.error(f"❌ Error crítico en indexación", source="indexer", collection=collection_name, error=str(e))
            raise
    
    def index_all(self, recreate_collections: bool = False):
        """Indexa todos los tipos de documentos"""
        start_time = time.time()
        
        print("\n" + "=" * 70)
        print("🚀 INICIANDO CARGA UNIFICADA DE DOCUMENTOS EN QDRANT")
        print("=" * 70 + "\n")
        
        logger.info("🚀 Inicio de indexación unificada", source="indexer", recreate_collections=recreate_collections)
        
        try:
            # 1. PDFs
            print("📄 FASE 1: Cargando PDFs...")
            pdfs = self.loader.load_pdfs(self.config.data_dir / "pdfs")
            self.prepare_collection(self.config.collections["pdfs"], recreate_collections)
            if pdfs:
                self.index_documents(pdfs, self.config.collections["pdfs"])
            
            # 2. Archivos Terraform
            print("\n🔧 FASE 2: Cargando archivos Terraform...")
            tfs = self.loader.load_terraform_files(self.config.data_dir / "terraform")
            self.prepare_collection(self.config.collections["code"], recreate_collections)
            if tfs:
                self.index_documents(tfs, self.config.collections["code"])
            
            # 3. Markdown
            print("\n📝 FASE 3: Cargando archivos Markdown...")
            mds = self.loader.load_markdown_files(self.config.data_dir / "docs")
            self.prepare_collection(self.config.collections["pdfs"], False)
            if mds:
                self.index_documents(mds, self.config.collections["pdfs"])
            
            # 4. Ejemplos del manifest
            print("\n📋 FASE 4: Cargando ejemplos desde manifest...")
            examples = self.loader.load_from_manifest()
            self.prepare_collection(self.config.collections["examples"], recreate_collections)
            if examples:
                self.index_documents(examples, self.config.collections["examples"])
            
            # Estadísticas finales
            duration = time.time() - start_time
            stats = self.loader.deduplicator.get_stats()
            total_docs = len(pdfs) + len(tfs) + len(mds) + len(examples)
            
            print("\n" + "=" * 70)
            print("✨ INDEXACIÓN COMPLETADA")
            print("=" * 70)
            print(f"📊 Documentos indexados: {total_docs}")
            print(f"📄 PDFs: {len(pdfs)}")
            print(f"🔧 Terraform: {len(tfs)}")
            print(f"📝 Markdown: {len(mds)}")
            print(f"📋 Ejemplos: {len(examples)}")
            print(f"⏱️  Tiempo total: {duration:.2f}s")
            print(f"✓ Chunks únicos: {stats['unique_chunks']}")
            print(f"⏭️  Duplicados eliminados: {stats['duplicates_removed']}")
            print("=" * 70 + "\n")
            
            logger.info("✅ Indexación completa", source="indexer",
                       total_docs=total_docs, duration=f"{duration:.2f}s",
                       dedup_stats=stats)
        
        except Exception as e:
            duration = time.time() - start_time
            logger.error("❌ Error en indexación", source="indexer",
                       duration=f"{duration:.2f}s", error=str(e))
            raise

# MAIN

def main():
    """Punto de entrada principal"""
    config = IndexConfig()
    
    # Override si lo necesitas
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--recreate", action="store_true", 
                       help="Recrear colecciones (borra contenido anterior)")
    parser.add_argument("--only-pdfs", action="store_true", help="Solo PDFs")
    parser.add_argument("--only-tf", action="store_true", help="Solo Terraform")
    parser.add_argument("--only-examples", action="store_true", help="Solo ejemplos")
    args = parser.parse_args()
    
    request_id = f"index_{int(time.time())}"
    set_request_id(request_id)
    
    try:
        indexer = QdrantIndexer(config)
        indexer.index_all(recreate_collections=args.recreate)
        print("\n✅ ¡Listo! Usa search_examples.py para hacer búsquedas.")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.error(f"Error fatal: {e}", source="indexer")
        sys.exit(1)

if __name__ == "__main__":
    main()
