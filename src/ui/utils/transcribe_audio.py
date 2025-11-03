import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# if not OPENAI_API_KEY:
#     raise ValueError("⚠️ Debes definir la variable de entorno OPENAI_API_KEY")

client = OpenAI()

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
                file=f,
                language="es"
            )
        return transcript.text
    except Exception as e:
        return f"❌ Error en transcripción: {e}"