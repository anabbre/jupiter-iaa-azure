import os
import tempfile
import base64
import gradio as gr
from openai import OpenAI
from gtts import gTTS
from agent import RAGAgent

from aux_files import _utils as aux
logger = aux.get_logger(__name__, subdir="ui")

# =============================
# CONFIGURACIÓN
# =============================

# Cargar claves de entorno
from dotenv import load_dotenv
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("Debes definir la variable de entorno OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

rag_agent = RAGAgent()

# =============================
# FUNCIONES DEL CHATBOT
# =============================

def chatbot_response(message, history):
    """
    Procesa entrada de texto del usuario.
    Si detecta que pide 'genera una imagen de ...', llama al generador de imágenes.
    """
    if message.lower().startswith("genera una imagen de"):
        prompt = message.replace("genera una imagen de", "").strip()
        try:
            result = client.images.generate(
                model="dall-e-3",  # Modelo correcto
                prompt=prompt,
                size="1024x1024",  # Tamaño válido para DALL-E 3
                n=1
            )
            image_url = result.data[0].url
            new_history = history.copy()
            new_history.append({"role": "user", "content": message})
            new_history.append({"role": "assistant", "content": f"![Imagen generada]({image_url})"})
            return new_history
        except Exception as e:
            new_history = history.copy()
            new_history.append({"role": "user", "content": message})
            new_history.append({"role": "assistant", "content": f"Error generando imagen: {e}"})
            return new_history

    # Detectar si es consulta de Terraform
    elif any(
        term in message.lower() for term in ["terraform", "tf", "azure provider", "infraestructura como código"]):
        try:
            # Usar el agente RAG para consultas de Terraform
            result = rag_agent.query(message)

            # Formatear las fuentes
            sources_text = "\n\n**Fuentes consultadas:**\n"
            for i, source in enumerate(result["sources"], 1):
                sources_text += f"{i}. {source['title']} "
                if source['url']:
                    sources_text += f"[Link]({source['url']}) "
                if source['section']:
                    sources_text += f"- Sección: {source['section']}"
                sources_text += "\n"

            # Construir respuesta con fuentes
            answer = f"{result['answer']}{sources_text}"

            new_history = history.copy()
            new_history.append({"role": "user", "content": message})
            new_history.append({"role": "assistant", "content": answer})
            return new_history
        except Exception as e:
            new_history = history.copy()
            new_history.append({"role": "user", "content": message})
            new_history.append({"role": "assistant", "content": f"Error consultando Terraform: {e}"})
            return new_history


    else:
        try:
            # Construir mensajes para la API
            messages = [{"role": "system", "content": "Eres un asistente útil y multimodal."}]
            for msg in history:
                messages.append(msg)
            messages.append({"role": "user", "content": message})

            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages
            )
            answer = completion.choices[0].message.content

            new_history = history.copy()
            new_history.append({"role": "user", "content": message})
            new_history.append({"role": "assistant", "content": answer})
            return new_history
        except Exception as e:
            new_history = history.copy()
            new_history.append({"role": "user", "content": message})
            new_history.append({"role": "assistant", "content": f"Error en chat: {e}"})
            return new_history

def encode_image_to_base64(image_path):
    """Convierte imagen a base64 para la API"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def interpret_image(image, question):
    """
    Usa GPT-4o con entrada multimodal para describir o responder preguntas sobre la imagen subida.
    """
    try:
        base64_image = encode_image_to_base64(image)
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un asistente que interpreta imágenes."},
                {"role": "user", "content": [
                    {"type": "text", "text": question},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]}
            ]
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error interpretando imagen: {e}"

def transcribe_audio(audio_file):
    """
    Transcribe audio en texto usando Whisper (OpenAI).
    """
    if not audio_file:
        return ""
    try:
        with open(audio_file, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=f
            )
        return transcript.text
    except Exception as e:
        return f"Error en transcripción: {e}"

def text_to_speech(text):
    """
    Convierte texto a voz usando gTTS y devuelve un archivo de audio temporal.
    """
    try:
        tts = gTTS(text=text, lang="es")
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(tmp_file.name)
        return tmp_file.name
    except Exception:
        logger.exception("TTS generation failed")
        return None

# =============================
# INTERFAZ GRADIO REORGANIZADA
# =============================

with gr.Blocks() as demo:
    gr.Markdown("# 🤖 Chatbot Multimodal con Gradio")

    with gr.Row():
        # Columna izquierda: Chatbot principal
        with gr.Column(scale=2):
            chatbot = gr.Chatbot(type="messages", height=500)

            with gr.Row():
                msg = gr.Textbox(label="Escribe tu mensaje aquí", scale=8)
                btn_tts = gr.Button("🔊", scale=1)

            with gr.Accordion("Entrada y salida de voz", open=False):
                with gr.Row():
                    btn_audio = gr.Audio(sources="microphone", type="filepath", label="Habla")
                    audio_output = gr.Audio(type="filepath", label="Respuesta")

        # Columna derecha: Funcionalidades de imagen
        with gr.Column(scale=1):
            img_input = gr.Image(type="filepath", label="Imagen para analizar")
            img_question = gr.Textbox(label="Pregunta sobre la imagen")
            img_answer = gr.Textbox(label="Análisis", lines=4)

    # Las funciones de callback se mantienen igual
    def user_message(user_msg, history):
        return "", chatbot_response(user_msg, history)

    msg.submit(
        user_message,
        [msg, chatbot],
        [msg, chatbot],
        api_name="chat"
    )

    def handle_audio(audio_file):
        if audio_file:
            return transcribe_audio(audio_file)
        return ""

    btn_audio.change(handle_audio, [btn_audio], [msg])

    def analyze_image(img, question):
        if img and question:
            return interpret_image(img, question)
        return "Sube una imagen y haz una pregunta."

    img_question.submit(analyze_image, [img_input, img_question], [img_answer])

    def last_to_speech(history):
        if not history:
            return None
        last_response = history[-1]["content"]
        if isinstance(last_response, str) and not last_response.startswith("!["):
            return text_to_speech(last_response)
        return None

    btn_tts.click(last_to_speech, [chatbot], [audio_output])

    gr.Markdown("*Puedes generar imágenes escribiendo 'genera una imagen de...'*")

# =============================
# MAIN
# =============================

def main():
    demo.launch()

if __name__ == "__main__":
    main()