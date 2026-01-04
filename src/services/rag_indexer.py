import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import json
import time
import yaml
import shutil
import tempfile
import boto3
from botocore.exceptions import ClientError
from urllib.parse import quote

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import hashlib
import re

from qdrant_client import QdrantClient
from src.services.vector_store import (
    ensure_collection,
    add_documents_to_collection,
    delete_collection,
)

from dotenv import load_dotenv
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
    data_dir: Path = Path(
        "data"
    ).resolve()  # se sobreescribe en __post_init__ si hay S3
    manifest_path: Path = Path("data/docs/examples/manifest.yaml").resolve()
    chunk_configs: Dict[str, Dict[str, int]] = None
    chunk_overlap: int = 120
    batch_size: int = 50
    max_workers: int = 4

    # S3 / CloudFront (opcionales)
    s3_bucket: Optional[str] = os.getenv("S3_BUCKET")
    s3_prefix: str = os.getenv("S3_PREFIX", "data/")
    local_data_dir: Path = Path(
        os.getenv("LOCAL_DATA_DIR", "/tmp/jupiter_data")
    ).resolve()
    cloudfront_base_url: Optional[str] = os.getenv("CLOUDFRONT_BASE_URL")

    def __post_init__(self):
        if self.collections is None:
            self.collections = {
                "pdfs": "terraform_book",
                "examples": "examples_terraform",
                "code": "terraform_code",
            }

        # Si hay S3, trabajaremos en local_data_dir
        if self.s3_bucket:
            self.data_dir = self.local_data_dir
            self.manifest_path = (
                self.data_dir / "docs/examples/manifest.yaml"
            ).resolve()

        # ✅ CONFIGURACIÓN DIFERENCIADA DE CHUNKS
        if self.chunk_configs is None:
            self.chunk_configs = {
                "pdf": {
                    "chunk_size": 1200,
                    "chunk_overlap": 200,
                },  # Documentación con más contexto
                "terraform": {
                    "chunk_size": 1800,
                    "chunk_overlap": 300,
                },  # Código tf en bloques completos
                "markdown": {"chunk_size": 1000, "chunk_overlap": 150},  # Docs técnicas
                "example": {
                    "chunk_size": 2000,
                    "chunk_overlap": 400,
                },  # Ejemplos completos
            }


# DEDUPLICADOR DE CHUNKS
class ChunkDeduplicator:
    """Evita duplicación de chunks basándose en contenido y metadatos"""

    def __init__(self):
        self.seen_hashes: Dict[str, str] = {}
        self.duplicates_removed = 0
        self.similarity_threshold = 0.95  # Umbral de similitud

    @staticmethod
    def _hash_chunk(content: str, metadata_keys: Tuple[str, ...]) -> str:
        """Genera hash único para un chunk"""
        # Normalizar contenido (quitar espacios múltiples, etc.)
        normalized = re.sub(r"\s+", " ", content.strip())
        hash_input = normalized
        if metadata_keys:
            hash_input += "||".join(str(k) for k in metadata_keys)
        return hashlib.md5(hash_input.encode()).hexdigest()

    # VERIFICAR DUPLICADOS
    def is_duplicate(
        self,
        content: str,
        metadata: Dict[str, Any],
        metadata_keys: Tuple[str, ...] = ("source", "section"),
    ) -> bool:
        """Detecta si un chunk es duplicado"""
        meta_values = tuple(
            str(metadata.get(k, ""))
            for k in metadata_keys
            if metadata.get(k) is not None
        )
        chunk_hash = self._hash_chunk(content, meta_values)

        if chunk_hash in self.seen_hashes:
            self.duplicates_removed += 1
            logger.debug(
                f"⏭️ Chunk duplicado detectado",
                source="qdrant",
                hash=chunk_hash[:8],
                original_content=self.seen_hashes[chunk_hash][:50],
            )
            return True

        self.seen_hashes[chunk_hash] = content[:100]
        return False

    # ESTADÍSTICAS
    def get_stats(self) -> Dict[str, int]:
        """Retorna estadísticas de deduplicación"""
        total_processed = len(self.seen_hashes) + self.duplicates_removed
        return {
            "unique_chunks": len(self.seen_hashes),
            "duplicates_removed": self.duplicates_removed,
            "total_processed": total_processed,
            "deduplication_rate": (
                (self.duplicates_removed / total_processed * 100)
                if total_processed > 0
                else 0
            ),
        }


class MetadataEnricher:
    """Extrae y enriquece metadatos para mejorar búsquedas"""

    @staticmethod
    def extract_terraform_metadata(content: str, file_path: Path) -> Dict[str, Any]:
        """Extrae metadatos específicos de archivos Terraform"""
        metadata = {
            "resource_types": [],
            "providers": [],
            "modules": [],
            "has_variables": False,
            "has_outputs": False,
            "has_locals": False,
            "cloud_provider": "unknown",
            "azure_resources": [],
        }

        # Detectar provider
        if "azurerm" in content:
            metadata["cloud_provider"] = "azure"
        elif "aws" in content:
            metadata["cloud_provider"] = "aws"
        elif "google" in content:
            metadata["cloud_provider"] = "gcp"

        # Extraer recursos de Azure específicos
        azure_pattern = r'resource\s+"azurerm_([^"]+)"'
        azure_resources = re.findall(azure_pattern, content)
        metadata["azure_resources"] = list(set(azure_resources))

        # Extraer tipos de recursos
        resource_pattern = r'resource\s+"([^"]+)"\s+"([^"]+)"'
        resources = re.findall(resource_pattern, content)
        metadata["resource_types"] = list(set([r[0] for r in resources]))

        # Extraer providers
        provider_pattern = r'provider\s+"([^"]+)"'
        providers = re.findall(provider_pattern, content)
        metadata["providers"] = list(set(providers))

        # Extraer módulos
        module_pattern = r'module\s+"([^"]+)"'
        modules = re.findall(module_pattern, content)
        metadata["modules"] = list(set(modules))

        # Detectar secciones
        metadata["has_variables"] = "variable " in content
        metadata["has_outputs"] = "output " in content
        metadata["has_locals"] = "locals " in content

        return metadata

    @staticmethod
    def extract_section_from_pdf(page_content: str) -> Optional[str]:
        """Intenta extraer el título de sección de un chunk de PDF"""
        lines = page_content.split("\n")
        for line in lines[:5]:  # Buscar en las primeras 5 líneas
            line = line.strip()
            # Patrones comunes de títulos
            if line and (
                line.isupper() or re.match(r"^#+\s+", line) or re.match(r"^\d+\.", line)
            ):
                return line[:100]  # Limitar longitud
        return None

    @staticmethod
    def extract_code_quality_metrics(content: str) -> Dict[str, Any]:
        """Métricas de calidad del código Terraform"""
        return {
            "lines_of_code": len(content.split("\n")),
            "has_comments": "#" in content or "//" in content or "/*" in content,
            "complexity_score": content.count("{")
            + content.count("for_each")
            + content.count("count"),
            "has_data_sources": 'data "' in content,
        }


def _s3_list_objects(bucket: str, prefix: str) -> List[str]:
    s3 = boto3.client("s3")
    keys = []
    continuation_token = None

    while True:
        kwargs = {"Bucket": bucket, "Prefix": prefix}
        if continuation_token:
            kwargs["ContinuationToken"] = continuation_token

        resp = s3.list_objects_v2(**kwargs)
        for item in resp.get("Contents", []):
            key = item["Key"]
            if not key.endswith("/"):
                keys.append(key)

        if resp.get("IsTruncated"):
            continuation_token = resp.get("NextContinuationToken")
        else:
            break

    return keys


def sync_s3_prefix_to_local(bucket: str, prefix: str, local_dir: Path) -> None:
    """
    Descarga s3://bucket/prefix... a local_dir, conservando rutas relativas.
    """
    s3 = boto3.client("s3")

    # limpieza defensiva
    local_dir.mkdir(parents=True, exist_ok=True)

    keys = _s3_list_objects(bucket, prefix)
    if not keys:
        raise RuntimeError(f"No hay objetos en s3://{bucket}/{prefix}")

    for key in keys:
        rel = key[len(prefix) :] if key.startswith(prefix) else key
        dest = (local_dir / rel).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            s3.download_file(bucket, key, str(dest))
        except ClientError as e:
            raise RuntimeError(f"Error descargando {key}: {e}") from e


def build_s3_key(config: IndexConfig, file_path: Path) -> Optional[str]:
    """
    Convierte un path local (dentro de config.data_dir) a key de S3 bajo config.s3_prefix.
    Solo aplica cuando estás en modo S3 (S3_BUCKET definido).
    """
    if not config.s3_bucket:
        return None

    base = config.data_dir.resolve()
    fp = file_path.resolve()

    # Si el archivo no cuelga de data_dir, no podemos calcular key fiable
    try:
        rel = fp.relative_to(base)
    except ValueError:
        return None

    prefix = config.s3_prefix.rstrip("/") + "/"
    return prefix + rel.as_posix()


def build_cloudfront_url(config: IndexConfig, s3_key: Optional[str]) -> Optional[str]:
    """
    URL estática (NO firmada) si tienes CLOUDFRONT_BASE_URL.
    Nota: si el contenido está privado, esta URL no funcionará sin signed URLs/cookies.
    """
    if not config.cloudfront_base_url or not s3_key:
        return None
    base = config.cloudfront_base_url.rstrip("/")
    return f"{base}/{quote(s3_key)}"


# Cargador unificado de documentos
class DocumentLoader:
    """Cargador unificado de documentos"""

    def __init__(self, config: IndexConfig):
        self.config = config
        self.deduplicator = ChunkDeduplicator()
        self.metadata_enricher = MetadataEnricher()
        self.request_id = get_request_id()

        # Splitters por tipos (usado en varios métodos)
        self.splitters = {
            "pdf": RecursiveCharacterTextSplitter(
                chunk_size=config.chunk_configs["pdf"]["chunk_size"],
                chunk_overlap=config.chunk_configs["pdf"]["chunk_overlap"],
                separators=["\n\n", "\n", ". ", " ", ""],
            ),
            "terraform": RecursiveCharacterTextSplitter(
                chunk_size=config.chunk_configs["terraform"]["chunk_size"],
                chunk_overlap=config.chunk_configs["terraform"]["chunk_overlap"],
                separators=[
                    "\n\n",
                    "\nresource ",
                    "\nmodule ",
                    "\nvariable ",
                    "\n",
                    " ",
                ],
            ),
            "markdown": RecursiveCharacterTextSplitter(
                chunk_size=config.chunk_configs["markdown"]["chunk_size"],
                chunk_overlap=config.chunk_configs["markdown"]["chunk_overlap"],
                separators=["\n## ", "\n### ", "\n\n", "\n", " "],
            ),
            "example": RecursiveCharacterTextSplitter(
                chunk_size=config.chunk_configs["example"]["chunk_size"],
                chunk_overlap=config.chunk_configs["example"]["chunk_overlap"],
                separators=["\n\n", "\nresource ", "\n", " "],
            ),
        }

    def load_pdfs(self, pdf_dir: Path) -> List[Document]:
        """Carga PDFs completos o desde directorio"""
        documents: List[Document] = []
        pdf_files = sorted(pdf_dir.glob("**/*.pdf")) if pdf_dir.is_dir() else [pdf_dir]

        logger.info(
            f"📄 Cargando {len(pdf_files)} PDFs",
            source="qdrant",
            pdf_count=len(pdf_files),
        )

        for pdf_file in pdf_files:
            try:
                loader = PyPDFLoader(str(pdf_file))
                pages = loader.load()

                # Filtra páginas sin contenido
                valid_pages = [
                    p for p in pages if p and p.page_content and p.page_content.strip()
                ]
                if not valid_pages:
                    logger.warning(
                        "⏭️ PDF sin contenido válido",
                        source="qdrant",
                        file=pdf_file.name,
                    )
                    continue

                chunks = self.splitters["pdf"].split_documents(valid_pages)
                chunks = [
                    c for c in chunks if c and c.page_content and c.page_content.strip()
                ]

                logger.info(
                    f"📑 PDF dividido en chunks",
                    source="qdrant",
                    file=pdf_file.name,
                    pages=len(valid_pages),
                    chunks=len(chunks),
                )

                # Enriquecer metadatos de cada chunk
                added = 0
                for i, chunk in enumerate(chunks):
                    section = self.metadata_enricher.extract_section_from_pdf(
                        chunk.page_content
                    )

                    if self.deduplicator.is_duplicate(
                        chunk.page_content,
                        {"source": str(pdf_file), "section": section or f"chunk_{i}"},
                    ):
                        continue

                    s3_key = build_s3_key(self.config, pdf_file)
                    source_url = build_cloudfront_url(self.config, s3_key)

                    chunk.metadata.update(
                        {
                            "name": "Terraform: Up & Running",
                            "description": "Libro completo de Terraform - conceptos y best practices",
                            "source": pdf_file.name,
                            "file_path": str(pdf_file),
                            "file_type": "pdf",
                            "doc_type": "terraform_book",
                            "chunk_id": i,
                            "total_chunks": len(chunks),
                            "section": section or "Unknown",
                            "page_start": chunk.metadata.get("page", 0),
                            "search_context": f"{section or 'Terraform Documentation'} - {chunk.page_content[:200]}",
                            # S3/CloudFront (para construir presigned en runtime)
                            "s3_bucket": self.config.s3_bucket,
                            "s3_key": s3_key,
                            "source_url": source_url,
                        }
                    )
                    documents.append(chunk)
                    added += 1

                logger.info(
                    f"✅ PDF procesado",
                    source="qdrant",
                    file=pdf_file.name,
                    chunks_indexed=added,
                )
            except Exception as e:
                logger.error(
                    f"❌ Error cargando PDF",
                    source="qdrant",
                    file=pdf_file.name,
                    error=str(e),
                )

        return documents

    def load_terraform_files(
        self, tf_dir: Path, is_example: bool = False
    ) -> List[Document]:
        """Carga archivos Terraform SIN CHUNKING (archivos completos)"""
        documents: List[Document] = []
        tf_files = sorted(tf_dir.glob("**/*.tf"))

        logger.info(
            f"🔧 Cargando {len(tf_files)} archivos Terraform",
            source="qdrant",
            tf_count=len(tf_files),
            is_example=is_example,
        )

        # Cargar y procesar cada TF
        for tf_file in tf_files:
            try:
                with open(tf_file, "r", encoding="utf-8") as f:
                    content = f.read()

                if not content or not content.strip():
                    continue

                # Extraer metadatos específicos de Terraform
                tf_metadata = self.metadata_enricher.extract_terraform_metadata(
                    content, tf_file
                )
                quality_metrics = self.metadata_enricher.extract_code_quality_metrics(
                    content
                )

                s3_key = build_s3_key(self.config, tf_file)
                source_url = build_cloudfront_url(self.config, s3_key)

                # NO usar splitter, crear documento completo directamente
                doc = Document(
                    page_content=content,  # Contenido completo sin dividir
                    metadata={
                        "source": tf_file.name,
                        "file_path": str(tf_file),
                        "file_type": "terraform",
                        "doc_type": "example" if is_example else "terraform_code",
                        "is_complete": True,
                        "chunk_id": 0,
                        "total_chunks": 1,  # Solo 1 chunk = archivo completo
                        # Metadatos específicos de Terraform
                        **tf_metadata,
                        **quality_metrics,
                        "search_context": f"Terraform {tf_file.stem} - Resources: {', '.join(tf_metadata['resource_types'][:5])}",
                        "s3_bucket": self.config.s3_bucket,
                        "s3_key": s3_key,
                        "source_url": source_url,
                    },
                )

                # Verificar duplicados (ahora con el archivo completo)
                if self.deduplicator.is_duplicate(
                    doc.page_content, {"source": str(tf_file)}
                ):
                    logger.info(
                        "⏭️ TF duplicado omitido", source="qdrant", file=tf_file.name
                    )
                    continue

                documents.append(doc)
                logger.info(
                    "✅ TF completo indexado",
                    source="qdrant",
                    file=tf_file.name,
                    size=len(content),
                    resources=len(tf_metadata["resource_types"]),
                )

            except Exception as e:
                logger.error(
                    f"❌ Error cargando TF",
                    source="qdrant",
                    file=tf_file.name,
                    error=str(e),
                )

        logger.info(
            f"✅ Total TF procesados",
            source="qdrant",
            files=len(tf_files),
            docs_indexed=len(documents),
        )
        return documents

    def load_markdown_files(
        self, md_dir: Path, is_example: bool = False
    ) -> List[Document]:
        """Carga archivos Markdown"""
        documents: List[Document] = []
        md_files = sorted(md_dir.glob("**/*.md"))

        logger.info(
            f"📝 Cargando {len(md_files)} archivos Markdown",
            source="qdrant",
            md_count=len(md_files),
            is_example=is_example,
        )

        # Cargar y procesar cada MD
        for md_file in md_files:
            try:
                loader = TextLoader(str(md_file), encoding="utf-8")
                md_docs = loader.load()

                splitter_type = "example" if is_example else "markdown"
                chunks = self.splitters[splitter_type].split_documents(md_docs)
                chunks = [
                    c for c in chunks if c and c.page_content and c.page_content.strip()
                ]
                if not chunks:
                    continue

                added = 0
                for i, chunk in enumerate(chunks):
                    if self.deduplicator.is_duplicate(
                        chunk.page_content, {"source": str(md_file), "chunk_id": i}
                    ):
                        continue

                    section_match = re.search(
                        r"^#+\s+(.+)$", chunk.page_content, re.MULTILINE
                    )
                    section = (
                        section_match.group(1) if section_match else "Introduction"
                    )

                    s3_key = build_s3_key(self.config, md_file)
                    source_url = build_cloudfront_url(self.config, s3_key)

                    chunk.metadata.update(
                        {
                            "source": md_file.name,
                            "file_path": str(md_file),
                            "file_type": "markdown",
                            "doc_type": "example" if is_example else "documentation",
                            "chunk_id": i,
                            "total_chunks": len(chunks),
                            "section": section,
                            "search_context": f"{section} - {chunk.page_content[:200]}",
                            "s3_bucket": self.config.s3_bucket,
                            "s3_key": s3_key,
                            "source_url": source_url,
                        }
                    )
                    documents.append(chunk)
                    added += 1

                logger.info(
                    f"✅ MD procesado",
                    source="qdrant",
                    file=md_file.name,
                    chunks_indexed=added,
                )
            except Exception as e:
                logger.error(
                    f"❌ Error cargando MD",
                    source="qdrant",
                    file=md_file.name,
                    error=str(e),
                )

        return documents

    def load_from_manifest(self) -> List[Document]:
        """Carga ejemplos desde manifest.yaml"""
        documents: List[Document] = []
        try:
            with open(self.config.manifest_path, "r", encoding="utf-8") as f:
                manifest = yaml.safe_load(f)

            examples = manifest.get("examples", [])
            logger.info(
                f"📋 Cargando {len(examples)} ejemplos del manifest",
                source="qdrant",
                examples_count=len(examples),
            )
            for ex in examples:
                ex_path = Path(ex["path"])
                if not ex_path.exists():
                    logger.warning(
                        f"⚠️ Ruta de ejemplo no existe",
                        source="qdrant",
                        path=str(ex_path),
                    )
                    continue

                # Cargar según tipo
                if ex_path.is_file() and ex_path.suffix == ".pdf":
                    docs = self.load_pdfs(ex_path)
                elif ex_path.is_dir():
                    # Marcar como ejemplo
                    docs = self.load_terraform_files(
                        ex_path, is_example=True
                    ) + self.load_markdown_files(ex_path, is_example=True)
                else:
                    continue

                # Metadatos adicionales del manifest
                for doc in docs:
                    doc.metadata.update(
                        {
                            "example_id": ex.get("id"),
                            "example_name": ex.get("name"),
                            "example_description": ex.get("description", ""),
                            "tags": ex.get("tags", []),
                            "category": ex.get("category", "general"),
                            "difficulty": ex.get("difficulty", "intermediate"),
                            "search_context": f"{ex.get('name')} - {ex.get('description', '')} - {doc.metadata.get('search_context', '')}",
                        }
                    )
                documents.extend(docs)
                logger.info(
                    f"✅ Ejemplo '{ex.get('id')}' cargado",
                    source="qdrant",
                    docs_count=len(docs),
                )
        except FileNotFoundError:
            logger.warning(
                f"⚠️ Manifest no encontrado",
                source="qdrant",
                path=str(self.config.manifest_path),
            )
        except Exception as e:
            logger.error(f"❌ Error cargando manifest", source="qdrant", error=str(e))
        return documents


# INDEXADOR
class QdrantIndexer:
    """Orquestador de indexación en Qdrant"""

    def __init__(self, config: IndexConfig):
        self.config = config
        self.loader = DocumentLoader(config)
        self.request_id = get_request_id()

    def prepare_collection(self, collection_name: str, recreate: bool = False):
        if recreate:
            delete_collection(collection_name)
        ensure_collection(collection_name)

    def index_documents(
        self, documents: List[Document], collection_name: str, batch_size: int = 50
    ):
        if not documents:
            logger.warning("⚠️ No hay documentos", source="qdrant")
            return

        batch_size = batch_size or self.config.batch_size
        total = len(documents)
        logger.info(
            f"📥 Indexando {total} docs", source="qdrant", collection=collection_name
        )

        indexed = 0
        for i in range(0, total, batch_size):
            batch = documents[i : i + batch_size]
            add_documents_to_collection(batch, collection_name)
            indexed += len(batch)
            progress = (indexed / total) * 100
            print(f"  [{progress:5.1f}%] {indexed}/{total}")

        logger.info(
            f"✅ {indexed} docs indexados", source="qdrant", collection=collection_name
        )

    def _create_client(self) -> QdrantClient:
        """Crea cliente Qdrant"""
        try:
            kwargs = {"url": self.config.qdrant_url, "prefer_grpc": False}
            if self.config.qdrant_api_key:
                kwargs["api_key"] = self.config.qdrant_api_key
            client = QdrantClient(**kwargs)
            logger.info(
                "✅ Conexión Qdrant establecida",
                source="qdrant",
                url=self.config.qdrant_url,
            )
            return client
        except Exception as e:
            logger.error("❌ Error conectando Qdrant", source="qdrant", error=str(e))
            raise

    def index_all(self, recreate_collections: bool = False):
        """Indexa todos los tipos de documentos"""
        start_time = time.time()

        print("\n" + "=" * 80)
        print("🚀 CARGA OPTIMIZADA DE DOCUMENTOS EN QDRANT")
        print("=" * 80)
        print(f"📊 Configuración:")
        print(
            f"   • PDFs: {self.config.chunk_configs['pdf']['chunk_size']} chars/chunk"
        )
        print(
            f"   • Terraform: {self.config.chunk_configs['terraform']['chunk_size']} chars/chunk"
        )
        print(
            f"   • Markdown: {self.config.chunk_configs['markdown']['chunk_size']} chars/chunk"
        )
        print(
            f"   • Ejemplos: {self.config.chunk_configs['example']['chunk_size']} chars/chunk"
        )
        print("=" * 80 + "\n")

        logger.info(
            "🚀 Inicio de indexación optimizada",
            source="qdrant",
            recreate_collections=recreate_collections,
        )

        stats = {"pdfs": 0, "terraform": 0, "markdown": 0, "examples": 0}

        try:
            # ===== FASE 1: PDFs =====
            print("📄 FASE 1: Cargando PDFs (documentación)...")
            print("-" * 80)
            pdfs = self.loader.load_pdfs(self.config.data_dir / "pdfs")
            stats["pdfs"] = len(pdfs)

            self.prepare_collection(
                self.config.collections["pdfs"], recreate_collections
            )
            if pdfs:
                self.index_documents(pdfs, self.config.collections["pdfs"])
                print(f"✅ {len(pdfs)} chunks de PDFs indexados\n")

            # # ===== FASE 2: Archivos Terraform ===== Cargamos desde el manifest de momento
            # print("🔧 FASE 2: Cargando archivos Terraform (código)...")
            # print("-" * 80)
            # tfs = self.loader.load_terraform_files(self.config.data_dir / "terraform", is_example=False)
            # stats["terraform"] = len(tfs)

            # self.prepare_collection(self.config.collections["code"], recreate_collections)
            # if tfs:
            #     self.index_documents(tfs, self.config.collections["code"])
            #     print(f"✅ {len(tfs)} chunks de Terraform indexados\n")

            # ===== FASE 3: Markdown =====
            print("📝 FASE 2: Cargando archivos Markdown (docs adicionales)...")
            print("-" * 80)
            mds = self.loader.load_markdown_files(
                self.config.data_dir / "docs", is_example=False
            )
            stats["markdown"] = len(mds)

            # Markdown va a la colección de PDFs (documentación)
            if mds:
                self.index_documents(mds, self.config.collections["pdfs"])
                print(f"✅ {len(mds)} chunks de Markdown indexados\n")

            #  ===== FASE 4: Manifest =====
            print("📋 FASE 3: Cargando ejemplos desde manifest (casos de uso)...")
            print("-" * 80)
            examples = self.loader.load_from_manifest()
            stats["examples"] = len(examples)

            self.prepare_collection(
                self.config.collections["examples"], recreate_collections
            )
            if examples:
                self.index_documents(examples, self.config.collections["examples"])
                print(f"✅ {len(examples)} chunks de ejemplos indexados\n")

            # Estadísticas finales
            duration = time.time() - start_time
            dedup_stats = self.loader.deduplicator.get_stats()
            total_docs = sum(stats.values())

            print("\n" + "=" * 80)
            print("✨ INDEXACIÓN COMPLETADA")
            print("=" * 80)
            print(f"📊 Resumen por tipo:")
            print(f"   📄 PDFs (documentación):     {stats['pdfs']:>6} chunks")
            print(f"   🔧 Terraform (código):       {stats['terraform']:>6} chunks")
            print(f"   📝 Markdown (docs):          {stats['markdown']:>6} chunks")
            print(f"   📋 Ejemplos (casos de uso):  {stats['examples']:>6} chunks")
            print(f"   {'─' * 76}")
            print(f"   📦 TOTAL:                    {total_docs:>6} chunks")
            print()
            print(f"🔍 Deduplicación:")
            print(f"   ✓ Chunks únicos:             {dedup_stats['unique_chunks']:>6}")
            print(
                f"   ⏭️  Duplicados eliminados:    {dedup_stats['duplicates_removed']:>6}"
            )
            print(
                f"   📈 Tasa de dedup:            {dedup_stats['deduplication_rate']:>5.1f}%"
            )
            print()
            print(f"⏱️  Tiempo total:               {duration:>6.2f}s")
            print(
                f"⚡ Velocidad:                  {total_docs/duration if duration > 0 else 0:>6.1f} chunks/s"
            )
            print("=" * 80 + "\n")

            logger.info(
                "✅ Indexación completa",
                source="qdrant",
                total_docs=total_docs,
                duration=f"{duration:.2f}s",
                dedup_stats=dedup_stats,
                stats=stats,
            )

        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                "❌ Error en indexación",
                source="qdrant",
                duration=f"{duration:.2f}s",
                error=str(e),
            )
            raise


def main():
    """Punto de entrada principal"""
    # Si hay S3_BUCKET, descargamos data/ a local antes de indexar
    s3_bucket = os.getenv("S3_BUCKET")
    if s3_bucket:
        s3_prefix = os.getenv("S3_PREFIX", "data/")
        local_dir = Path(os.getenv("LOCAL_DATA_DIR", "/tmp/jupiter_data")).resolve()

        # Para evitar mezclar ejecuciones
        if local_dir.exists():
            shutil.rmtree(local_dir, ignore_errors=True)

        print(f"⬇️ Descargando desde S3: s3://{s3_bucket}/{s3_prefix} -> {local_dir}")
        sync_s3_prefix_to_local(s3_bucket, s3_prefix, local_dir)
        print("✅ Descarga S3 completa")

    config = IndexConfig()
    # Override si lo necesitas
    import argparse

    parser = argparse.ArgumentParser(
        description="Indexador optimizado de documentos Terraform"
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Recrear colecciones (borra contenido anterior)",
    )
    parser.add_argument("--only-pdfs", action="store_true", help="Solo indexar PDFs")
    parser.add_argument("--only-tf", action="store_true", help="Solo indexar Terraform")
    parser.add_argument(
        "--only-examples", action="store_true", help="Solo indexar ejemplos"
    )
    parser.add_argument(
        "--chunk-size-pdf", type=int, help="Tamaño de chunk para PDFs (default: 1200)"
    )
    parser.add_argument(
        "--chunk-size-tf",
        type=int,
        help="Tamaño de chunk para Terraform (default: 1800)",
    )
    args = parser.parse_args()

    if args.chunk_size_pdf:
        config.chunk_configs["pdf"]["chunk_size"] = args.chunk_size_pdf
    if args.chunk_size_tf:
        config.chunk_configs["terraform"]["chunk_size"] = args.chunk_size_tf

    request_id = f"index_{int(time.time())}"
    set_request_id(request_id)

    try:
        indexer = QdrantIndexer(config)

        # Modos de indexación selectiva
        if args.only_pdfs:  # Solo PDFs
            print("📄 Modo: Solo PDFs")
            pdfs = indexer.loader.load_pdfs(config.data_dir / "pdfs")
            indexer.prepare_collection(config.collections["pdfs"], args.recreate)
            if pdfs:
                indexer.index_documents(pdfs, config.collections["pdfs"])

        elif args.only_tf:  # Solo Terraform
            print("🔧 Modo: Solo Terraform")
            tfs = indexer.loader.load_terraform_files(config.data_dir / "terraform")
            indexer.prepare_collection(config.collections["code"], args.recreate)
            if tfs:
                indexer.index_documents(tfs, config.collections["code"])

        elif args.only_examples:  # Solo ejemplos
            print("📋 Modo: Solo ejemplos")
            examples = indexer.loader.load_from_manifest()
            indexer.prepare_collection(config.collections["examples"], args.recreate)
            if examples:
                indexer.index_documents(examples, config.collections["examples"])

        else:
            # Indexación completa
            indexer.index_all(recreate_collections=args.recreate)
        print("\n✅ ¡Indexación completada! Usa tu API para hacer búsquedas.")

    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        logger.error(f"Error fatal: {e}", source="qdrant")
        sys.exit(1)


if __name__ == "__main__":
    main()
