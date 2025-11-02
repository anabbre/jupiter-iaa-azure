from pypdf import PdfReader
from pypdf.generic import Destination
from typing import Dict, List, Any
import json
from pathlib import Path


class PDFSchemaService:
    """Servicio para extraer esquemas de archivos PDF"""

    # Desde scripts/ -> subir 1 nivel hasta la raíz del proyecto
    DATA_DIR = Path(__file__).parent.parent / "data"

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
        # Normalizar nombre del archivo
        if not nombre_pdf.endswith('.pdf'):
            nombre_pdf += '.pdf'

        pdf_path = PDFSchemaService.DATA_DIR / nombre_pdf

        if not pdf_path.exists():
            raise FileNotFoundError(f"No se encontró el archivo: {pdf_path}")

        # Extraer esquema
        reader = PdfReader(str(pdf_path))
        esquema = []

        if reader.outline:
            PDFSchemaService._procesar_bookmarks(reader, reader.outline, esquema, nivel=0)

        # Guardar JSON en /data
        json_name = pdf_path.stem + '_esquema.json'
        json_path = PDFSchemaService.DATA_DIR / json_name

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(esquema, f, indent=2, ensure_ascii=False)

        return str(json_path)

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
    try:
        json_path = generar_esquema_pdf("Libro-TF.pdf")
        print(f"✓ Esquema generado en: {json_path}")
    except FileNotFoundError as e:
        print(f"✗ Error: {e}")
    except Exception as e:
        print(f"✗ Error al procesar: {e}")