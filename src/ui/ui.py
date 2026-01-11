import os
import requests
import gradio as gr
from config.config import SETTINGS
from config.logger_config import logger


API_URL = SETTINGS.API_URL


def _normalize_source(src_item: dict) -> dict:
    """Normaliza una fuente heterogénea a una estructura común para la UI."""
    src = src_item if isinstance(src_item, dict) else getattr(src_item, "__dict__", {})
    metadata = src.get("metadata", {}) if isinstance(src.get("metadata"), dict) else {}

    doc_type = metadata.get("doc_type") or src.get("doc_type")
    relevance_score = (
        src.get("relevance_score")
        or src.get("score")
        or metadata.get("relevance_score")
        or 0.0
    )

    name = (
        metadata.get("name")
        or metadata.get("source")
        or os.path.basename(metadata.get("file_path", ""))
        or "Documento"
    )
    description = metadata.get("description", "")
    ref = metadata.get("ref") or src.get("ref")
    path = (
        metadata.get("file_path") or src.get("source", "") or metadata.get("path") or ""
    )
    section = (
        metadata.get("section") or src.get("section") or metadata.get("page") or ""
    )
    page = metadata.get("page") or ""
    ref_name = None
    extras = {}

    if doc_type == "example":
        ref_type = "Documentación .tf"
        name = metadata.get("example_name") or name
        description = metadata.get("example_description", "")
        ref_name = f"{doc_type}.tf"
        difficulty = metadata.get("difficulty")
        lines_of_code = metadata.get("lines_of_code") or metadata.get("loc")
        difficulty_color = None
        if isinstance(difficulty, str):
            d = difficulty.strip().lower()
            if d == "beginner":
                difficulty_color = "green"
            elif d in ("intermediate", "medio", "intermedio"):
                difficulty_color = "amber"
            elif d == "advanced":
                difficulty_color = "red"

        color_emoji = {"green": "🟢", "amber": "🟡", "red": "🔴"}.get(
            difficulty_color, ""
        )
        extras = {
            "dificultad": f"{color_emoji}" if difficulty else None,
            "líneas de código": lines_of_code,
        }

    elif doc_type == "terraform_book":
        ref_type = "Libro"
        file_type = (
            metadata.get("file_type") or os.path.splitext(path)[1].lstrip(".") or "pdf"
        )
        ref_name = f"{doc_type}.{file_type}"
        extras = {"page": page if page else None}

    elif doc_type == "documentation":
        ref_type = "Documentación .md"
        name = metadata.get("section") or section or name
        ref_name = f"{doc_type}.md"
    else:
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
        "doc_type": doc_type or "unknown",
    }


def get_api_response(question: str, chat_history: list = None) -> dict:
    """Consulta la API FastAPI del agente."""
    try:
        logger.info(
            "Enviando consulta a API", url=API_URL, question=question[:100], source="ui"
        )
        response = requests.post(
            f"{API_URL}/query",
            json={"question": question, "chat_history": chat_history or []},
            timeout=60,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error("❌ Error en consulta a API", error=str(e), source="ui")
        return {"answer": f"❌ Error al consultar la API: {str(e)}", "sources": []}


# ===================
# LÓGICA PRINCIPAL
# ===================
def procesar_mensaje(history, texto):
    if not texto:
        return history, ""

    logger.info("💬 Procesando mensaje", texto=texto, source="ui")

    # Añadir mensaje del usuario al chat
    history.append({"role": "user", "content": texto})

    try:
        # Preparar historial para la API
        history_for_api = [
            {"role": msg["role"], "content": msg["content"]} for msg in history
        ]

        # Llamar a la API
        result = get_api_response(texto, chat_history=history_for_api)

        respuesta = result.get("answer", "❌ No se pudo generar una respuesta")
        sources = result.get("sources", [])

        # Formatear fuentes si existen
        if sources and not respuesta.startswith("❌"):
            normalized = [_normalize_source(s) for s in sources]

            # Agrupar fuentes por tipo
            grouped_sources = {}
            for source in normalized:
                dt = source["doc_type"]
                if dt not in grouped_sources:
                    grouped_sources[dt] = []
                grouped_sources[dt].append(source)

            respuesta += "\n\n🔎 Fuentes consultadas:"
            num = 1
            for doc_type, srcs in grouped_sources.items():
                if doc_type == "terraform_book":
                    s = srcs[0]
                    respuesta += f"\n{num}. **{s['ref_type']}: {s['name']}**"
                    num += 1
                    for sub in srcs:
                        page = sub["extras"].get("page")
                        if page and sub.get("ref"):
                            respuesta += f"\n🔗 [Página {page}]({sub['ref']})"
                else:
                    for s in srcs:
                        ref_url = (
                            f"[{s['ref_name']}]({s.get('ref')})"
                            if s.get("ref")
                            else s["ref_name"]
                        )
                        respuesta += (
                            f"\n{num}. **{s['ref_type']}: {s['name']}** 🔗 {ref_url}"
                        )
                        num += 1

    except Exception as e:
        respuesta = f"❌ Error: {str(e)}"

    # Añadir respuesta del asistente
    history.append({"role": "assistant", "content": respuesta})
    return history, ""


# =============================
# INTERFAZ GRADIO (Limpia)
# =============================
with gr.Blocks(
    theme=gr.themes.Soft(
        primary_hue="indigo",
        secondary_hue="purple",
        neutral_hue="slate",
        font=["Inter", "sans-serif"],
    ),
    title="Terraform RAG Assistant",
) as app:

    # Cabecera
    gr.HTML(
        """
        <div style="text-align: center; margin-bottom: 20px;">
            <h1>🤖 Terraform RAG Assistant</h1>
            <p>Asistente experto en Terraform e Infraestructura</p>
        </div>
    """
    )

    chatbot = gr.Chatbot(
        type="messages",
        height=600,
        show_label=False,
        avatar_images=(
            None,
            "https://api.dicebear.com/9.x/bottts-neutral/svg?seed=Sarah",
        ),
        show_copy_button=True,
    )

    # Área de entrada de texto
    with gr.Row():
        texto_input = gr.Textbox(
            placeholder="💬 Escribe tu pregunta aquí...",
            scale=8,
            show_label=False,
            lines=1,
            autofocus=True,
        )
        btn_enviar = gr.Button("📤 Enviar", variant="primary", scale=1)

    # Eventos (Solo Texto)
    texto_input.submit(procesar_mensaje, [chatbot, texto_input], [chatbot, texto_input])

    btn_enviar.click(procesar_mensaje, [chatbot, texto_input], [chatbot, texto_input])

if __name__ == "__main__":
    logger.info("🚀 Iniciando Gradio UI (Modo Texto)", puerto=7860)
    app.launch(server_name="0.0.0.0", server_port=7860, show_api=False)
