import os
import gradio as gr
import requests
from src.ui.utils.transcribe_audio import transcribe_audio
from src.ui.utils.process_image import encode_image_to_base64
from src.ui.utils.process_text_file import read_text_file
from src.config import SETTINGS
from logger_config import logger 

API_URL = SETTINGS.API_URL


def get_api_response(pregunta: str) -> dict:
    """
    Consulta la API FastAPI del agente
    
    Args:
        pregunta: Pregunta del usuario
        
    Returns:
        Diccionario con la respuesta y fuentes
    """
    try:
        logger.info("Enviando consulta a API", url=API_URL, pregunta=pregunta[:100], source="ui")
        response = requests.post(
            f"{API_URL}/query",
            json={"question": pregunta},
            timeout=60
        )
        response.raise_for_status()
        logger.info(
            "Respuesta recibida de API",
            status_code=response.status_code,
            tiene_fuentes=bool(response.get("sources"),), 
            source="ui"
        )
        return response.json()

    
    except requests.exceptions.ConnectionError:
        logger.error("Error de conexión con API",api_url=API_URL,error=str(e), source="ui")
        return {
            "answer": "❌ Error: No se puede conectar con la API. Asegúrate de que esté ejecutándose en " + API_URL,
            "sources": []
        }
    except requests.exceptions.Timeout:
        logger.error("Timeout en consulta a API", timeout=60, error=str(e), source="ui")
        return {
            "answer": "❌ Error: La consulta tardó demasiado tiempo. Intenta con una pregunta más específica.",
            "sources": []
        }
    except Exception as e:
        logger.error("Error inesperado en consulta a API", error=str(e), tipo_error=type(e).__name__, source="ui")
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
    logger.info("Procesando mensaje", tiene_texto=bool(texto), tiene_archivo=bool(archivo), source="ui")

    # Procesar archivo (puede ser imagen o texto)
    if archivo:
        file_ext = os.path.splitext(archivo)[1].lower()
        logger.debug("Archivo detectado", extension=file_ext, nombre=os.path.basename(archivo), source="ui")
        # Si es imagen
        if file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
            logger.info("Procesando imagen", extension=file_ext)
            base64_img = encode_image_to_base64(archivo)
            data_url = f"data:image/jpeg;base64,{base64_img}"
            if contenido_usuario:
                contenido_usuario += f"\n\n![Imagen adjunta]({data_url})"
            else:
                contenido_usuario = f"![Imagen adjunta]({data_url})"

        # Si es archivo de texto
        else:
            logger.info("Procesando archivo de texto", extension=file_ext, source="ui")
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
        # python
        if sources and not respuesta.startswith("❌"):
            logger.info("Fuentes encontradas", cantidad_fuentes=len(sources), source="ui")
            # Enlace y título principal
            book_url = "https://digtvbg.com/files/LINUX/Brikman%20Y.%20Terraform.%20Up%20and%20Running.%20Writing...as%20Code%203ed%202022.pdf"
            book_title = "Terraform: Up & Running — Writing Infrastructure as Code (3rd ed, 2022)"
            respuesta += f"\n\n\n 📚 **Fuente:** [{book_title}]({book_url})"

            # Detalle de las fuentes extra (secciones y páginas)
            for i, source in enumerate(sources[:3], 1):
                section = source.get("section", "N/A")
                pages = source.get("pages", "N/A")

                respuesta += f"\n {section} ----- {'Página' if '-' not in pages else 'Páginas'}: {pages}"

    except Exception as e:
        logger.error("Error al procesar consulta", error=str(e), tipo_error=type(e).__name__, source="ui")
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
        logger.error("Error en transcripción", error=texto_transcrito, source="ui")
        # Si hay error, mostrarlo en el chat
        history.append({"role": "assistant", "content": texto_transcrito})
        return history, ""

    logger.info("Audio transcrito exitosamente", longitud=len(texto_transcrito), source="ui")
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
        title="Agente LangGraph Multimodal"
) as app:
    # Header principal
    gr.HTML("""
        <div class="main-header">
            <h1>🤖 Agente LangGraph con RAG</h1>
            <p>Texto • Voz • Imágenes • Archivos</p>
        </div>
    """)

    with gr.Row():
        # =============================
        # COLUMNA IZQUIERDA: CHAT (80%)
        # =============================
        with gr.Column(scale=4):
            chatbot = gr.Chatbot(
                type="messages",
                height=650,
                show_label=False,
                avatar_images=(
                    "https://api.dicebear.com/7.x/avataaars/svg?seed=User",
                    "https://api.dicebear.com/7.x/bottts/svg?seed=Bot"
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
        # COLUMNA DERECHA: CONTROLES COMPACTOS (20%)
        # =============================
        with gr.Column(scale=1, min_width=260):
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

            # Sección 2: Archivos (Imágenes y Texto)
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
        share=False,
        server_name="0.0.0.0",
        server_port=7860
    )