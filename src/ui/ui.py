import os
import requests
import gradio as gr
from src.ui.utils.transcribe_audio import transcribe_audio
from src.ui.utils.process_image import encode_image_to_base64
from src.ui.utils.process_text_file import read_text_file
from config.config import SETTINGS
from config.logger_config import logger 

API_URL = SETTINGS.API_URL

def _normalize_source(src_item: dict) -> dict:
    """Normaliza una fuente heterogénea a una estructura común para la UI.

    Casos soportados según metadata['doc_type']:
      - example
      - terraform_book
      - documentation

    Campos de salida comunes:
      name, description, ref, ref_name, relevance_score, extras, path, section
    """
    # src_item puede ser dataclass (DocumentScore) o dict
    src = src_item if isinstance(src_item, dict) else getattr(src_item, "__dict__", {})
    metadata = src.get("metadata", {}) if isinstance(src.get("metadata"), dict) else {}

    doc_type = metadata.get("doc_type") or src.get("doc_type")
    relevance_score = (
        src.get("relevance_score")
        or src.get("score")
        or metadata.get("relevance_score")
        or 0.0
    )

    # Valores base/por defecto
    name = metadata.get("name") or metadata.get("source") or os.path.basename(metadata.get("file_path", "")) or os.path.basename(src.get("source", "")) or "Documento"
    description = metadata.get("description", "")
    ref = metadata.get("ref") or src.get("ref")
    path = metadata.get("file_path") or src.get("source", "") or metadata.get("path") or ""
    section = metadata.get("section") or src.get("section") or metadata.get("page") or ""
    page = metadata.get("page") or ""
    ref_name = None
    extras = {}

    # Normalización por tipo
    if doc_type == "example":
        ref_type = "Documentación .tf"
        name = metadata.get("example_name") or name
        description = metadata.get("example_description", "")
        # ref_name = doc_type + ".tf"
        ref_name = f"{doc_type}.tf"
        # extras: difficulty con codificación de color y lines_of_code si existe
        difficulty = metadata.get("difficulty")
        # Algunos extractores podrían guardar métricas de calidad; buscar lines_of_code en metadata
        lines_of_code = metadata.get("lines_of_code") or metadata.get("loc")
        # Mapear dificultad a color semáforo
        difficulty_color = None
        if isinstance(difficulty, str):
            d = difficulty.strip().lower()
            if d == "beginner":
                difficulty_color = "green"
            elif d in ("intermediate", "medio", "intermedio"):
                difficulty_color = "amber"
            elif d == "advanced":
                difficulty_color = "red"
        # Mapear color a emoji de círculo
        color_emoji = {
            "green": "🟢",
            "amber": "🟡",
            "red": "🔴"
        }.get(difficulty_color, "")
        extras = {
            "dificultad": f"{color_emoji}" if difficulty else None,
            "líneas de código": lines_of_code,
        }

    elif doc_type == "terraform_book":
        ref_type = "Libro"
        # name y description directos
        name = metadata.get("name", name)
        description = metadata.get("description", "")
        # ref_name = doc_type + "." + file_type
        file_type = metadata.get("file_type") or os.path.splitext(path)[1].lstrip(".") or "pdf"
        ref_name = f"{doc_type}.{file_type}"
        extras = {
            "page": page if page else None,
        }

    elif doc_type == "documentation":
        ref_type = "Documentación .md"
        # name = section; description vacío
        name = metadata.get("section") or section or name
        description = ""
        ref_name = f"{doc_type}.md"
    else:
        # Tipo desconocido: mantener valores por defecto y derivar ref_name del path
        ref_type = "Documento"
        ext = os.path.splitext(path)[1].lstrip(".") if path else "txt"
        ref_name = f"{(doc_type or 'document')}.{ext}"

    return {
        "ref_type": ref_type,
        "name": name,
        "description": description,
        "ref": ref,
        "ref_name": ref_name,
        "relevance_score": relevance_score,
        "extras": extras,
        "path": path,
        "section": section or "",
        "doc_type": doc_type or "unknown",
    }


def get_api_response(question: str) -> dict:
    """
    Consulta la API FastAPI del agente
    
    Args:
        question: Pregunta del usuario
        
    Returns:
        Diccionario con la respuesta y fuentes
    """
    try:
        logger.info("Enviando consulta a API", url=API_URL, question=question[:100], source="ui")
        response = requests.post(
            f"{API_URL}/query",
            json={"question": question},
            timeout=60
        )
        response.raise_for_status()
        response_data = response.json()
        logger.info("📝 Respuesta recibida de API", status_code=response.status_code, tiene_fuentes=bool(response_data.get("sources")), source="ui")
        return response_data

    
    except requests.exceptions.ConnectionError as e:
        logger.error("❌ Error de conexión con API",api_url=API_URL,error=str(e), source="ui")
        return {
            "answer": "❌ Error: No se puede conectar con la API. Asegúrate de que esté ejecutándose en " + API_URL,
            "sources": []
        }
    except requests.exceptions.Timeout as e:
        logger.error("❌ Timeout en consulta a API", timeout=60, error=str(e), source="ui")
        return {
            "answer": "❌ Error: La consulta tardó demasiado tiempo. Intenta con una pregunta más específica.",
            "sources": []
        }
    except Exception as e:
        logger.error("❌ Error inesperado en consulta a API", error=str(e), tipo_error=type(e).__name__, source="ui")
        return {
            "answer": f"❌ Error al consultar la API: {str(e)}",
            "sources": []
        }

# =============================
# FUNCIONES PRINCIPALES
# =============================
def procesar_mensaje(history, texto, archivo):
    """
    Procesa el mensaje del usuario con texto y/o archivo (imagen o texto)
    """
    if not texto and not archivo:
        logger.warning("Intento de enviar mensaje vacío")
        return history, None

    # Construir el contenido del mensaje del usuario
    contenido_usuario = texto if texto else ""   
    logger.info("💬 Procesando mensaje", tiene_texto=bool(texto), tiene_archivo=bool(archivo), source="ui")

    # Procesar archivo (puede ser imagen o texto)
    if archivo:
        file_ext = os.path.splitext(archivo)[1].lower()
        logger.info(" Archivo detectado", extension=file_ext, nombre=os.path.basename(archivo), source="ui")
        # Si es imagen
        if file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
            logger.info("🖼️ Procesando imagen", extension=file_ext)
            base64_img = encode_image_to_base64(archivo)
            data_url = f"data:image/jpeg;base64,{base64_img}"
            if contenido_usuario:
                contenido_usuario += f"\n\n![Imagen adjunta]({data_url})"
            else:
                contenido_usuario = f"![Imagen adjunta]({data_url})"

        # Si es archivo de texto
        else:
            logger.info("📄 Procesando archivo de texto", extension=file_ext, source="ui")
            contenido_archivo = read_text_file(archivo)
            if contenido_usuario:
                contenido_usuario += f"\n\n📄 **Archivo adjunto ({os.path.basename(archivo)}):**\n```\n{contenido_archivo[:500]}...\n```"
            else:
                contenido_usuario = f"📄 **Archivo adjunto ({os.path.basename(archivo)}):**\n```\n{contenido_archivo[:500]}...\n```"

    # Agregar mensaje del usuario al historial
    history.append({"role": "user", "content": contenido_usuario})

    try:
        # Consultar la API con la pregunta del usuario
        result = get_api_response(contenido_usuario)

        # Obtener la respuesta del agente
        respuesta = result.get("answer", "❌ No se pudo generar una respuesta")

        # Agregar información de fuentes si están disponibles
        sources = result.get("sources", [])
        if sources and not respuesta.startswith("❌"):
            logger.info("Fuentes encontradas", cantidad_fuentes=len(sources), source="ui")

            # normalizamos los datos que traemos de las fuentes
            normalized = [_normalize_source(s) for s in sources]

            # Agrupar los datos normalizados por doc_type
            grouped_sources = {}
            for source in normalized:
                doc_type = source['doc_type']
                if doc_type not in grouped_sources:
                    grouped_sources[doc_type] = []
                grouped_sources[doc_type].append(source)

            # Construir la respuesta agrupada
            respuesta += "\n\n🔎 Fuentes consultadas:"

            num = 1
            for doc_type, sources in grouped_sources.items():
                if doc_type == "terraform_book":
                    respuesta += f"\n{num}. **{sources[0].get('ref_type')}: {sources[0].get('name')}** — {sources[0].get('description')}"
                    num += 1
                    for i, source in enumerate(sources, 1):
                        page = source['extras'].get('page', None)
                        if page and source.get('ref'):
                            respuesta += f"\n🔗 [Página {page}]({source['ref']})"
                elif doc_type == "documentation":
                    respuesta += f"\n{num}. **{sources[0].get('ref_type')}:**"
                    num += 1
                    for source in sources:
                        ref_url = f"[{source['ref_name']}]({source.get('ref')})" if source.get("ref") else source['ref_name']
                        respuesta += f"\n  - {source['name']} -- {source['description']} 🔗{ref_url}"
                else:
                    for i, source in enumerate(sources, 1):
                        extras = []
                        for k, v in source['extras'].items():
                            if v:
                                extras.append(f"{k}: {v}")
                        extra_txt = f" • {' | '.join(extras)}" if extras else ""
                        ref_url = f"[{source['ref_name']}]({source.get('ref')})" if source.get("ref") else source['ref_name']
                        respuesta += f"\n{i}. **{source['ref_type']}: {source['name']}**{' — ' + source['description'] if source['description'] else ''}{('\n' + extra_txt) if extra_txt else ''}\n🔗 {ref_url}"
                
    except Exception as e:
        logger.error("❌ Error al procesar la consulta", error=str(e), tipo_error=type(e).__name__, source="ui")
        respuesta = f"❌ Error al procesar la consulta: {str(e)}"

    # Agregar respuesta del agente al historial
    history.append({"role": "assistant", "content": respuesta})

    return history, None


def procesar_audio(history, audio_file):
    """
    Transcribe el audio y lo muestra en el textbox
    """
    if not audio_file:
        return history, ""
    
    logger.info("Transcribiendo audio", archivo=audio_file, source="ui")

    # Transcribir audio
    texto_transcrito = transcribe_audio(audio_file)

    if texto_transcrito.startswith("❌"):
        logger.error("❌ Error en transcripción", error=texto_transcrito, source="ui")
        # Si hay error, mostrarlo en el chat
        history.append({"role": "assistant", "content": texto_transcrito})
        return history, ""

    logger.info("✅ Audio transcrito exitosamente", longitud=len(texto_transcrito), source="ui")
    # Devolver el texto transcrito para que el usuario lo vea antes de enviar
    return history, texto_transcrito


# =============================
# INTERFAZ GRADIO
# =============================

with gr.Blocks(
        theme=gr.themes.Soft(
            primary_hue="indigo",
            secondary_hue="purple",
            neutral_hue="slate",
            font=["Inter", "sans-serif"]
        ),
        title="Terraform RAG Assistant"
) as app:
    # Header principal
    gr.HTML("""
        <div class="main-header">
            <h1>🤖 Terraform RAG Assistant</h1>
            <p>Texto • Voz • Imágenes • Archivos</p>
        </div>
    """)

    with gr.Row():
        # =============================
        # COLUMNA IZQUIERDA: CHAT (70%)
        # =============================
        with gr.Column(scale=7):
            chatbot = gr.Chatbot(
                type="messages",
                height=650,
                show_label=False,
                avatar_images=(
                    "https://api.dicebear.com/9.x/fun-emoji/svg?seed=Destiny",
                    "https://api.dicebear.com/9.x/bottts-neutral/svg?seed=Sarah"
                ),
                show_copy_button=True
            )

            with gr.Row():
                texto_input = gr.Textbox(
                    placeholder="💬 Escribe tu pregunta aquí o usa los controles de la derecha...",
                    container=False,
                    scale=9,
                    show_label=False,
                    lines=1
                )
                btn_enviar = gr.Button("📤", variant="primary", scale=1, min_width=60)

        # =============================
        # COLUMNA DERECHA: CONTROLES COMPACTOS (30%)
        # =============================
        with gr.Column(scale=3, min_width=300):
            gr.HTML('<div class="control-panel">')

            # Sección 1: Audio
            gr.HTML('<div class="compact-section">')
            audio_input = gr.Audio(
                sources=["microphone"],
                type="filepath",
                show_label=False,
                elem_classes="compact-audio",
                waveform_options={"show_controls": False}
            )
            texto_transcrito = gr.Textbox(
                placeholder="Transcripción aparecerá aquí...",
                show_label=False,
                lines=2,
                max_lines=3,
                interactive=False
            )
            btn_usar_transcripcion = gr.Button(
                "✅ Usar transcripción",
                variant="primary",
                size="sm",
                visible=False
            )
            gr.HTML('</div>')

            # Sección 2: Archivos (ImÃ¡genes y Texto)
            archivo_input = gr.File(
                label="Imagen o Texto",
                file_types=["image", ".txt", ".md", ".py", ".js", ".json", ".csv", ".html", ".css", ".pdf", ".docx"],
                show_label=False,
                elem_classes="compact-file"
            )

            gr.HTML('</div>')
            gr.HTML('</div>')

    # =============================
    # EVENT HANDLERS
    # =============================

    # Enviar mensaje con texto/archivo
    def enviar_mensaje(history, texto, archivo):
        new_history, _ = procesar_mensaje(history, texto, archivo)
        return new_history, "", None, "", gr.update(visible=False)

    btn_enviar.click(
        enviar_mensaje,
        [chatbot, texto_input, archivo_input],
        [chatbot, texto_input, archivo_input, texto_transcrito, btn_usar_transcripcion]
    )

    texto_input.submit(
        enviar_mensaje,
        [chatbot, texto_input, archivo_input],
        [chatbot, texto_input, archivo_input, texto_transcrito, btn_usar_transcripcion]
    )

    # Transcribir audio cuando se graba
    def handle_audio(history, audio_file):
        new_history, transcripcion = procesar_audio(history, audio_file)
        show_btn = bool(transcripcion and not transcripcion.startswith("❌"))
        return new_history, transcripcion, gr.update(visible=show_btn)

    audio_input.stop_recording(
        handle_audio,
        [chatbot, audio_input],
        [chatbot, texto_transcrito, btn_usar_transcripcion]
    )

    audio_input.change(
        handle_audio,
        [chatbot, audio_input],
        [chatbot, texto_transcrito, btn_usar_transcripcion]
    )

    # Usar transcripción en el textbox
    def usar_transcripcion(texto_trans):
        return texto_trans, "", gr.update(visible=False)

    btn_usar_transcripcion.click(
        usar_transcripcion,
        [texto_transcrito],
        [texto_input, texto_transcrito, btn_usar_transcripcion]
    )

# =============================
# MAIN
# =============================

if __name__ == "__main__":
    logger.info("🚀 Iniciando Gradio UI", puerto=7860)
    app.launch(
        debug=True,
        share=True,
        server_name="0.0.0.0",
        server_port=7860,
        show_api=False
    )