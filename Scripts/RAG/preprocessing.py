import sys
from pypdf import PdfReader, PdfWriter
from typing import Dict, List, Any, Optional, Tuple
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../config')))
# from config.logger_config import logger, get_request_id, set_request_id
from logger_config import logger, get_request_id, set_request_id


import json
from pathlib import Path
import re
from collections import defaultdict
import shutil
import time


class PDFSectionExtractor:
    """
    Extrae secciones de PDFs con agrupación inteligente por páginas.

    Funcionalidad RAG optimizada:
    - Detecta automáticamente chunks que comparten páginas
    - Fusiona chunks redundantes en un solo fragmento por rango de páginas
    - Preserva cohesión semántica y metadatos completos
    - Elimina duplicación para mejorar eficiencia del sistema RAG
    """
    DATA_DIR = Path(__file__).parents[2] / "data"

    @staticmethod
    def extraer_secciones_por_niveles(
        nombre_pdf: str,
        niveles_filtro: Optional[List[int]] = None,
        output_dir: str = "optimized_chunks"
    ) -> List[str]:
        """
        Extrae y agrupa secciones del PDF eliminando redundancia.

        Args:
            nombre_pdf: Nombre del PDF
            niveles_filtro: Niveles jerárquicos a incluir
            output_dir: Directorio de salida (por defecto: optimized_chunks)

        Returns:
            Lista de archivos PDF generados (sin duplicación)
        """
        try:
            request_id
        except NameError:
            request_id = get_request_id()
        start_time = time.time()
        logger.info("Iniciando extracción de secciones PDF",pdf=nombre_pdf,niveles_filtro=niveles_filtro,request_id=request_id,source="pdf_extractor")
        
        try:
            if not nombre_pdf.endswith('.pdf'):
                nombre_pdf += '.pdf'

            pdf_path = PDFSectionExtractor.DATA_DIR / nombre_pdf
            json_path = PDFSectionExtractor.DATA_DIR / f"{pdf_path.stem}_esquema.json"

            if not pdf_path.exists():
                logger.error("PDF no encontrado",pdf_path=str(pdf_path),request_id=request_id,source="pdf_extractor")
                raise FileNotFoundError(f"No se encontró el PDF: {pdf_path}")
            if not json_path.exists():
                logger.error("Esquema JSON no encontrado",json_path=str(json_path),request_id=request_id,source="pdf_extractor")
                raise FileNotFoundError(f"No se encontró el esquema: {json_path}")

            # Cargar PDF y esquema
            logger.info("Cargando PDF y esquema", request_id=request_id, source="pdf_extractor")
            reader = PdfReader(str(pdf_path))
            with open(json_path, 'r', encoding='utf-8') as f:
                esquema = json.load(f)

            logger.info("Archivos cargados",total_paginas=len(reader.pages),total_secciones_esquema=len(esquema),request_id=request_id,source="pdf_extractor")
            # Filtrar secciones por nivel
            logger.info("Filtrando secciones por nivel",niveles_solicitados=niveles_filtro, request_id=request_id,source="pdf_extractor")
            # Filtrar secciones por nivel
            secciones = PDFSectionExtractor._filtrar_secciones(esquema, niveles_filtro)

            if not secciones:
                logger.warning("No se encontraron secciones después del filtrado",niveles_filtro=niveles_filtro,request_id=request_id,source="pdf_extractor")
                print("⚠ No se encontraron secciones con los filtros aplicados.")
                return []
            
            logger.info("Secciones filtradas exitosamente",secciones_filtradas=len(secciones),request_id=request_id,source="pdf_extractor")

            # Calcular rangos de páginas para cada sección
            logger.debug("Calculando rangos de páginas",request_id=request_id,source="pdf_extractor")
            secciones_con_rangos = PDFSectionExtractor._calcular_rangos_paginas(
                secciones, len(reader.pages)
            )

            # PASO CLAVE: Agrupar secciones por rango de páginas único
            # Esto elimina la duplicación de chunks que comparten páginas
            logger.debug("Agrupando secciones por rango de páginas",request_id=request_id,source="pdf_extractor")
            chunks_agrupados = PDFSectionExtractor._agrupar_por_rango_paginas(
                secciones_con_rangos
            )

            print(f"📊 Análisis de agrupación:")
            print(f"   • Secciones originales: {len(secciones_con_rangos)}")
            print(f"   • Chunks únicos (sin duplicación): {len(chunks_agrupados)}")
            print(f"   • Reducción: {len(secciones_con_rangos) - len(chunks_agrupados)} chunks redundantes eliminados\n")

            # Análisis de agrupación
            reduccion = len(secciones_con_rangos) - len(chunks_agrupados)
            logger.info("Análisis de agrupación completado",secciones_originales=len(secciones_con_rangos),chunks_unicos=len(chunks_agrupados),chunks_redundantes_eliminados=reduccion,porcentaje_reduccion=f"{(reduccion/len(secciones_con_rangos)*100):.1f}%",request_id=request_id,source="pdf_extractor")
            
            # Crear directorio de salida (limpiar si ya existe)
            output_path = PDFSectionExtractor.DATA_DIR / output_dir / pdf_path.stem

            # Limpiar carpeta existente antes de generar nuevos chunks
            if output_path.exists():
                logger.info("Limpiando chunks anteriores",path=str(output_path),request_id=request_id,source="pdf_extractor")
                print(f"🗑️  Limpiando chunks anteriores en {output_path.name}/")
                try:
                    shutil.rmtree(output_path)
                    logger.debug("Carpeta limpiada exitosamente",request_id=request_id,source="pdf_extractor")
                    print(f"✓ Carpeta limpiada exitosamente\n")
                except Exception as e:
                    logger.warning("Error al limpiar carpeta",error=str(e),request_id=request_id,source="pdf_extractor")
                    print(f"⚠ Advertencia al limpiar carpeta: {e}\n")

            output_path.mkdir(parents=True, exist_ok=True)

            # Generar PDFs optimizados (un PDF por rango único de páginas)
            logger.info("Iniciando generación de PDFs optimizados",chunks_a_generar=len(chunks_agrupados),request_id=request_id,source="pdf_extractor")
            archivos = PDFSectionExtractor._generar_pdfs_optimizados(
                reader, chunks_agrupados, output_path
            )
            duration = time.time() - start_time
            logger.info("Extracción completada exitosamente",archivos_generados=len(archivos),duration=f"{duration:.3f}s",output_path=str(output_path),request_id=request_id,source="pdf_extractor",process_time=f"{duration:.3f}s")
            return archivos
        except Exception as e:
            duration = time.time() - start_time
            logger.error("Error en extracción de secciones",error=str(e),tipo_error=type(e).__name__,pdf=nombre_pdf,duration=f"{duration:.3f}s",request_id=request_id,source="pdf_extractor",process_time=f"{duration:.3f}s")
            raise

    @staticmethod
    def _filtrar_secciones(
        esquema: List[Dict[str, Any]],
        niveles_filtro: Optional[List[int]]
    ) -> List[Dict[str, Any]]:
        """Filtra secciones por nivel jerárquico"""
        try:
            request_id
        except NameError:
            request_id = get_request_id()
            
        logger.debug("Agrupando por rango de paginas",secciones=len(secciones),request_id=request_id,source="pdf_extractor")
        
        secciones = []
        for seccion in esquema:
            if niveles_filtro and seccion['nivel'] not in niveles_filtro:
                continue
            if seccion['pagina'] is None:
                continue
            secciones.append({
                'titulo': seccion['titulo'],
                'pagina': seccion['pagina'],
                'nivel': seccion['nivel']
            })
        return secciones

    @staticmethod
    def _calcular_rangos_paginas(
        secciones: List[Dict[str, Any]],
        total_paginas: int
    ) -> List[Dict[str, Any]]:
        """
        Calcula el rango de páginas [inicio, fin) para cada sección.

        Lógica:
        - Una sección va desde su página inicial hasta donde comienza la siguiente
        - La última sección llega hasta el final del documento
        - Si dos secciones están en la misma página, ambas tendrán el mismo rango
        """
        try:
            request_id
        except NameError:
            request_id = get_request_id()
            
        logger.debug("Calculando rangos de páginas",secciones=len(secciones),total_paginas=total_paginas,request_id=request_id,source="pdf_extractor") 
        for i, seccion in enumerate(secciones):
            if i < len(secciones) - 1:
                # La sección termina donde comienza la siguiente
                seccion['pagina_fin'] = secciones[i + 1]['pagina']
            else:
                # Última sección: hasta el final del documento
                seccion['pagina_fin'] = total_paginas

            # Asegurar que siempre incluya al menos la página de inicio
            if seccion['pagina_fin'] == seccion['pagina']:
                seccion['pagina_fin'] = seccion['pagina'] + 1

        return secciones

    @staticmethod
    def _agrupar_por_rango_paginas(
        secciones: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        FUNCIONALIDAD CLAVE PARA RAG:
        Agrupa todas las secciones que comparten el mismo rango de páginas.

        Esto elimina la duplicación de chunks para la misma página,
        mejorando la precisión y eficiencia del sistema RAG.

        Args:
            secciones: Lista de secciones con rangos de páginas calculados

        Returns:
            Lista de chunks únicos, cada uno representando un rango único de páginas
            con metadatos de todas las secciones incluidas
        """
        try:
            request_id
        except NameError:
            request_id = get_request_id()
            
        logger.debug("Inicio agrupación por rango de páginas",secciones=len(secciones),request_id=request_id,source="pdf_extractor")
        
        # Diccionario para agrupar por rango de páginas (clave: tupla (inicio, fin))
        grupos: Dict[Tuple[int, int], List[Dict[str, Any]]] = defaultdict(list)

        for seccion in secciones:
            rango = (seccion['pagina'], seccion['pagina_fin'])
            grupos[rango].append(seccion)

        # Crear chunks únicos fusionando secciones del mismo rango
        chunks_unicos = []
        for (pagina_inicio, pagina_fin), secciones_grupo in grupos.items():
            # Fusionar títulos de todas las secciones en este rango
            titulos = [s['titulo'] for s in secciones_grupo]
            niveles = [s['nivel'] for s in secciones_grupo]

            # Crear título compuesto (usa el primero como principal)
            titulo_principal = titulos[0]

            # Construir metadatos completos
            chunk_unico = {
                'pagina_inicio': pagina_inicio,
                'pagina_fin': pagina_fin,
                'titulo_principal': titulo_principal,
                'titulos_incluidos': titulos,  # Todas las secciones en este chunk
                'niveles': niveles,
                'num_secciones': len(secciones_grupo),
                'secciones_fusionadas': len(secciones_grupo) > 1  # Flag de fusión
            }

            chunks_unicos.append(chunk_unico)

        # Ordenar por página de inicio
        chunks_unicos.sort(key=lambda x: x['pagina_inicio'])

        return chunks_unicos

    @staticmethod
    def _generar_pdfs_optimizados(
        reader: PdfReader,
        chunks: List[Dict[str, Any]],
        output_path: Path
    ) -> List[str]:
        """
        Genera un PDF por cada chunk único (rango de páginas sin duplicación).

        Cada PDF incluye:
        - Las páginas originales del PDF con formato preservado
        - Metadatos con todas las secciones incluidas en ese chunk
        - Nombre descriptivo indicando el contenido
        """
        try:
            request_id
        except NameError:
            request_id = get_request_id()
                
            
        logger.info("Iniciando generación de PDFs",chunks_totales=len(chunks),output_path=str(output_path),request_id=request_id,source="pdf_extractor")
        archivos = []
        errores = 0 # Errores por chunk

        for idx, chunk in enumerate(chunks):
            pagina_inicio = chunk['pagina_inicio']
            pagina_fin = chunk['pagina_fin']
            titulo_principal = chunk['titulo_principal']
            num_secciones = chunk['num_secciones']

            # Crear nombre descriptivo del archivo
            nombre_limpio = PDFSectionExtractor._limpiar_nombre_archivo(titulo_principal)

            # Añadir sufijo si contiene múltiples secciones fusionadas
            if num_secciones > 1:
                sufijo = f"_y_{num_secciones-1}_mas"
            else:
                sufijo = ""

            pdf_file = output_path / f"{idx + 1:03d}_{nombre_limpio}{sufijo}.pdf"

            try:
                logger.debug("Generando PDF del chunk",chunk_numero=idx,paginas=f"{pagina_inicio+1}-{pagina_fin}",num_paginas=num_paginas,num_secciones=num_secciones,titulo=titulo_principal,request_id=request_id,source="pdf_extractor")
                # Crear writer y agregar páginas del chunk
                writer = PdfWriter()

                for page_num in range(pagina_inicio, pagina_fin):
                    if page_num < len(reader.pages):
                        writer.add_page(reader.pages[page_num])

                # Añadir metadatos al PDF
                metadata = {
                    '/Title': titulo_principal,
                    '/Subject': f"Páginas {pagina_inicio+1}-{pagina_fin}",
                    '/Keywords': ', '.join(chunk['titulos_incluidos'][:5]),  # Max 5 títulos
                }
                writer.add_metadata(metadata)

                # Guardar PDF optimizado
                with open(pdf_file, 'wb') as output_file:
                    writer.write(output_file)

                num_paginas = pagina_fin - pagina_inicio
                archivos.append(str(pdf_file))

                # Log detallado
                if num_secciones > 1:
                    print(f"✓ Chunk fusionado: {pdf_file.name}")
                    print(f"  └─ {num_paginas} página(s) | {num_secciones} secciones combinadas")
                    print(f"  └─ Secciones: {', '.join(chunk['titulos_incluidos'][:3])}{'...' if num_secciones > 3 else ''}")  
                    logger.info("Chunk fusionado generado",archivo=pdf_file.name,num_paginas=num_paginas,num_secciones=num_secciones,secciones=chunk['titulos_incluidos'][:3],request_id=request_id,source="pdf_extractor")
                else:
                    print(f"✓ Chunk único: {pdf_file.name} ({num_paginas} página(s))")
                    logger.info("Chunk único generado",archivo=pdf_file.name,num_paginas=num_paginas,request_id=request_id,source="pdf_extractor")

            except Exception as e:
                errores += 1
                print(f"✗ Error al generar {pdf_file.name}: {e}")
                logger.error(f"✗ Error al generar {pdf_file.name}: {e}")

        print(f"\n✅ Total chunks optimizados generados: {len(archivos)}")
        print(f"📈 Mejora para RAG: Sin duplicación de páginas, chunks semánticamente coherentes")  
        logger.info("Generación de PDFs completada",archivos_generados=len(archivos),errores=errores,request_id=request_id,source="pdf_extractor")
        
        return archivos

    @staticmethod
    def _limpiar_nombre_archivo(nombre: str) -> str:
        """Limpia y normaliza nombres para usar como archivos"""
        # Eliminar caracteres no válidos
        nombre_limpio = re.sub(r'[<>:"/\\|?*\[\]]', '', nombre)
        # Reemplazar espacios y puntos múltiples
        nombre_limpio = re.sub(r'\s+', '_', nombre_limpio)
        nombre_limpio = re.sub(r'\.+', '.', nombre_limpio)
        # Limitar longitud
        return nombre_limpio[:80].strip('._')


def extraer_secciones_por_niveles(
    nombre_pdf: str,
    niveles: List[int]
) -> List[str]:
    """
    Función de conveniencia para extraer secciones con agrupación optimizada.

    Args:
        nombre_pdf: Nombre del archivo PDF
        niveles: Niveles jerárquicos a incluir (ej: [1, 2] para capítulos y artículos)

    Returns:
        Lista de archivos PDF generados (sin duplicación)
    """
    return PDFSectionExtractor.extraer_secciones_por_niveles(
        nombre_pdf=nombre_pdf,
        niveles_filtro=niveles
    )


if __name__ == "__main__":
    from logger_config import set_session_id
    
    # Crear sesión para este proceso
    session_id = f"pdf_extract_{int(time.time())}"
    set_session_id(session_id)
    
    print("=" * 70)
    print("EXTRACTOR DE CHUNKS OPTIMIZADO PARA RAG")
    print("Agrupación automática | Sin duplicación | Metadatos completos")
    print("=" * 70)
    print()
    
    logger.info("Iniciando PDF extractor - Proceso principal",session_id=session_id,source="pdf_extractor")


    try:
        archivos = extraer_secciones_por_niveles(
            nombre_pdf="Libro-TF.pdf",
            niveles=[0, 1, 2, 3, 4]  # Capítulos (nivel 1) y Artículos (nivel 2)
        )

        print(f"\n{'='*70}")
        print(f"✅ Proceso completado exitosamente")
        print(f"📁 Chunks generados: {len(archivos)}")
        print(f"📂 Ubicación: data/optimized_chunks/Libro-TF/")
        print(f"💡 Beneficios RAG:")
        print(f"   • Sin páginas duplicadas en múltiples chunks")
        print(f"   • Fusión automática de secciones en la misma página")
        print(f"   • Metadatos completos para cada chunk")
        print(f"   • Mayor precisión en recuperación de información")
        print(f"{'='*70}")
        logger.info("Proceso de PDF extractor completado exitosamente",archivos_generados=len(archivos),session_id=session_id,source="pdf_extractor")

    except Exception as e:
        print(f"❌ Error: {e}")
        logger.error("Error en PDF extractor",error=str(e),tipo_error=type(e).__name__,session_id=session_id,source="pdf_extractor")