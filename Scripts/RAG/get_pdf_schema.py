import json
import time
from pypdf import PdfReader
from pypdf.generic import Destination
from config.logger_config import logger, get_request_id, set_request_id
from typing import Dict, List, Any
from pathlib import Path
from src.api.schemas import SourceInfo
from pathlib import Path


class PDFSchemaService:
    """Servicio para extraer esquemas de archivos PDF"""

    # Desde scripts/ -> subir 1 nivel hasta la raíz del proyecto
    DATA_DIR = Path(__file__).parents[2] / "data"


    @staticmethod
    def extraer_esquema(nombre_pdf: str) -> str:
        """
        Extrae el esquema de un PDF y lo guarda en /data.

        Args:
            nombre_pdf: Nombre del archivo PDF (con o sin extensión)

        Returns:
            Ruta del archivo JSON generado

        Raises:
            FileNotFoundError: Si el PDF no existe
            Exception: Si hay errores al procesar el PDF
        """
        
        try:
            request_id
        except NameError:
            request_id = get_request_id()
                
        start_time = time.time()    
        logger.info("ℹ️ Iniciando extracción de esquema PDF",pdf_original=nombre_pdf,request_id=request_id,source="pdf_schema")
        try:
            
            # Normalizar nombre del archivo
            if not nombre_pdf.endswith('.pdf'):
                nombre_pdf += '.pdf'

            pdf_path = PDFSchemaService.DATA_DIR / nombre_pdf

            if not pdf_path.exists():
                logger.error("❌ PDF no encontrado",pdf_path=str(pdf_path),request_id=request_id,source="pdf_schema")
                raise FileNotFoundError(f"No se encontró el archivo: {pdf_path}")

            # Extraer esquema
            reader = PdfReader(str(pdf_path))
            esquema = []
            logger.info("✅ PDF cargado exitosamente",pdf=pdf_path.name,total_paginas=len(reader.pages),tiene_bookmarks=bool(reader.outline),request_id=request_id,source="pdf_schema")

            if reader.outline:
                PDFSchemaService._procesar_bookmarks(reader, reader.outline, esquema, nivel=0)
                logger.info(" - Bookmarks procesados",total_secciones=len(esquema),request_id=request_id,source="pdf_schema")
            else:
                logger.warning("⚠️ El PDF no contiene bookmarks",pdf=pdf_path.name,request_id=request_id,source="pdf_schema")
            
            # Guardar JSON en /data
            json_name = pdf_path.stem + '_esquema.json'
            json_path = PDFSchemaService.DATA_DIR / json_name
            logger.info(" - Guardando esquema en JSON",json_path=str(json_path),secciones=len(esquema),request_id=request_id,source="pdf_schema")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(esquema, f, indent=2, ensure_ascii=False)
            
            duration = time.time() - start_time
            logger.info("✅ Esquema guardado exitosamente",json_path=str(json_path),total_secciones=len(esquema),tamaño_kb=f"{json_path.stat().st_size / 1024:.2f}",duration=f"{duration:.3f}s",request_id=request_id,source="pdf_schema",process_time=f"{duration:.3f}s")
            return str(json_path)

        except FileNotFoundError as e:
            logger.error("❌ Error: Archivo no encontrado",error=str(e),request_id=request_id,source="pdf_schema")
            raise
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error("❌ Error al extraer esquema", error=str(e),tipo_error=type(e).__name__,pdf=nombre_pdf,duration=f"{duration:.3f}s",request_id=request_id,source="pdf_schema",process_time=f"{duration:.3f}s")       
            raise

    @staticmethod
    def _procesar_bookmarks(reader: PdfReader, items, esquema: List[Dict], nivel: int):
        """Procesa recursivamente los bookmarks del PDF"""
        for item in items:
            if isinstance(item, Destination):
                try:
                    page_number = reader.get_destination_page_number(item)
                except:
                    page_number = None

                esquema.append({
                    "titulo": item.title,
                    "pagina": page_number,
                    "nivel": nivel
                })
            elif isinstance(item, list):
                PDFSchemaService._procesar_bookmarks(reader, item, esquema, nivel + 1)


# Función de conveniencia para uso directo
def generar_esquema_pdf(nombre_pdf: str) -> str:
    """
    Genera el esquema JSON de un PDF en /data.

    Args:
        nombre_pdf: Nombre del PDF (ej: "documento.pdf" o "documento")

    Returns:
        Ruta del JSON generado
    """
    return PDFSchemaService.extraer_esquema(nombre_pdf)


if __name__ == "__main__":
    
    from config.logger_config import set_session_id
    
    session_id = f"pdf_schema_{int(time.time())}"
    set_session_id(session_id)
    logger.info(" - Iniciando PDF Schema Service - Proceso principal",session_id=session_id,source="pdf_schema")
    
    try:
        json_path = generar_esquema_pdf("Libro-TF.pdf")
        logger.info("✅ Esquema generado exitosamente",json_path=json_path,session_id=session_id,source="pdf_schema")
        print(f"✅ Esquema generado en: {json_path}")
    except FileNotFoundError as e:
        logger.error("❌ Archivo PDF no encontrado",error=str(e),session_id=session_id,source="pdf_schema")
        print(f"❌ Error: {e}")
    except Exception as e:
        logger.error("❌ Error al procesar PDF",error=str(e),tipo_error=type(e).__name__,session_id=session_id,source="pdf_schema")
        print(f"❌ Error al procesar: {e}")