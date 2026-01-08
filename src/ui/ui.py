import os
import requests
import gradio as gr
from config.config import SETTINGS
from config.logger_config import logger 

API_URL = SETTINGS.API_URL



def _normalize_source(src_item: dict) -> dict:
    """Normaliza una fuente heterogénea a una estructura común para la UI.

    Casos soportados según metadata['doc_type']:
      - terraform_book
      - documentation
      - example

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
    section = metadata.get("section") or ""
    ref_name = None
    extras = {}

    # Normalización por tipo
    if doc_type == "example":
        ref_type = "Ejemplos Terraform"
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
        ref_type = "Documentación markdown"
        # name = section; description vacío
        name = metadata.get("name", name)
        description = ""
        ref_name = f"{doc_type}.md"
        extras = {
            "section": section if section else None,
        }

    else:
        # Tipo desconocido: mantener valores por defecto y derivar ref_name del path
        name = metadata.get("name", name)
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


MAX_CONTEXT = 20


def _truncate_history(history: list) -> list:
    try:
        return history[-MAX_CONTEXT:] if isinstance(history, list) else history
    except Exception:
        return history


def get_api_response(question: str, context: list | None = None) -> dict:
    """
    Consulta la API FastAPI del agente
    
    Args:
        question: Pregunta del usuario
        
    Returns:
        Diccionario con la respuesta y fuentes
    """
    try:
        logger.info("Enviando consulta a API", url=API_URL, question=question[:100], source="ui")
        payload = {"question": question}
        if context and isinstance(context, list):
            payload["context"] = context[-MAX_CONTEXT:]

        response = requests.post(
            f"{API_URL}/query",
            json=payload,
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


def procesar_mensaje(history, texto):
    """
    Procesa el mensaje del usuario con texto
    """
    if not texto:
        logger.warning("Intento de enviar mensaje vacío")
        return history, None

    # Construir el contenido del mensaje del usuario
    contenido_usuario = texto if texto else ""   
    logger.info("💬 Procesando mensaje", tiene_texto=bool(texto), source="ui")

    # Agregar mensaje del usuario al historial con poda
    history.append({"role": "user", "content": contenido_usuario})
    try:
        history = history[-MAX_CONTEXT:]
    except Exception:
        pass

    try:
        # Consultar la API con la pregunta del usuario
        result = get_api_response(contenido_usuario, context=history)

        # Obtener la respuesta del agente
        respuesta = result.get("answer", "❌ No se pudo generar una respuesta")

        # Agregar información de fuentes si están disponibles
        sources = result.get("sources", [])
        if sources and not respuesta.startswith("❌"):
            logger.info("Fuentes encontradas", cantidad_fuentes=len(sources), source="ui")

            # normalizamos los datos que traemos de las fuentes
            normalized = [_normalize_source(s) for s in sources]

            # Agrupar los datos normalizados por doc_type y luego por name dentro de cada doc_type
            grouped_sources = {}
            for source in normalized:
                doc_type = source['doc_type']
                name = source['name']
                if doc_type not in grouped_sources:
                    grouped_sources[doc_type] = {}
                if name not in grouped_sources[doc_type]:
                    grouped_sources[doc_type][name] = {
                        "ref_type": source['ref_type'],
                        "description": source['description'],
                        "ref_name": source['ref_name'],
                        "ref": source['ref'],
                        "extras": []
                    }
                grouped_sources[doc_type][name]['extras'].extend(source['extras'] if isinstance(source['extras'], list) else [source['extras']])

            # Construir la respuesta agrupada
            respuesta += "\n\n🔎 Fuentes consultadas:"

            num = 1
            for doc_type, sources in grouped_sources.items():
                if doc_type == "terraform_book":
                    # Ejemplo adaptado: sources es un dict con nombres como clave
                    for name, source in sources.items():
                        respuesta += f"\n{num}. **{source.get('ref_type')}: {name}** — {source.get('description')}"
                        num += 1
                        # 'extras' es una lista de dicts, cada uno con 'page'
                        for extra in source.get('extras', []):
                            page = extra.get('page', None)
                            if page and source.get('ref'):
                                respuesta += "\n" + "&nbsp;" * 5 + f"🔗 [Página {page}]({source['ref']})"
                elif doc_type == "documentation":
                    respuesta += f"\n{num}. **{next(iter(sources.values()))['ref_type']}:**"
                    num += 1
                    for i, name in enumerate(sources, 1):
                        source = sources[name]
                        respuesta += "\n" + "&nbsp;" * 5 + f"🔗 [{name}]({source.get('ref')}) -- Secciones consultadas:"
                        extras = []
                        for key, value in enumerate(source['extras']):
                            section = value.get('section', None)
                            respuesta += "\n" + "&nbsp;" * 8 + f" ({key}) {section}" if section else ""
                        respuesta += "&nbsp;" * 8
                        respuesta += "\n"
                elif doc_type == "example":
                    respuesta += f"\n{num}. **{next(iter(sources.values()))['ref_type']}:**"
                    num += 1
                    for name, source in sources.items():
                        extras = []
                        # source['extras'] is a list of dicts, so flatten all key-values
                        for extra_dict in source['extras']:
                            for k, v in extra_dict.items():
                                if v:
                                    extras.append(f"{k}: {v}")
                        extra_txt = f"\t {' | '.join(extras)}" if extras else ""
                        ref_url = f"[{source['ref_name']}]({source.get('ref')})" if source.get("ref") else source['ref_name']
                        respuesta += "\n" + "&nbsp;" * 5 + f"  - {name} -- {source['description']}{('\n' + extra_txt) if extra_txt else ''}"
                        respuesta += "\n" + "&nbsp;" * 8 + f"🔗 {ref_url}"
                else:
                    respuesta += f"\n{num}. **{next(iter(sources.values()))['ref_type']}:**"
                    num += 1
                    for name, source in sources.items():
                        ref_url = f"[{source['ref_name']}]({source.get('ref')})" if source.get("ref") else source['ref_name']
                        respuesta += "\n" + "&nbsp;" * 5 + f"  - {name} -- {source['description']}"
                        respuesta += "\n" + "&nbsp;" * 8 + f"🔗 {ref_url}"
                
    except Exception as e:
        logger.error("❌ Error al procesar la consulta", error=str(e), tipo_error=type(e).__name__, source="ui")
        respuesta = f"❌ Error al procesar la consulta: {str(e)}"

    # Agregar respuesta del agente al historial con poda
    history.append({"role": "assistant", "content": respuesta})
    try:
        history = history[-MAX_CONTEXT:]
    except Exception:
        pass

    return history, None


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
            <p>Asistente de IA para consultas sobre Terraform con la documentación oficial.</p>
        </div>
    """)

    with gr.Row():
        # =========================
        # BLOQUE PRINCIPAL: CHATBOT
        # =========================
        with gr.Column(scale=10):
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
                    placeholder="💬 Escribe tu pregunta aquí...",
                    container=False,
                    scale=9,
                    show_label=False,
                    lines=1
                )
                btn_enviar = gr.Button("📤", variant="primary", scale=1, min_width=60)

    # =============================
    # EVENT HANDLERS
    # =============================

    # Enviar mensaje con texto
    def enviar_mensaje(history, texto):
        new_history, _ = procesar_mensaje(history, texto)
        return new_history, "", None, "", gr.update(visible=False)

    btn_enviar.click(
        enviar_mensaje,
        [chatbot, texto_input],
        [chatbot, texto_input]
    )

    texto_input.submit(
        enviar_mensaje,
        [chatbot, texto_input],
        [chatbot, texto_input]
    )



# =============================
# MAIN
# =============================

if __name__ == "__main__":
    logger.info("🚀 Iniciando Gradio UI", puerto=7860)
    app.launch(
        debug=False,
        share=False,
        server_name="0.0.0.0",
        server_port=7860,
        show_api=False
    )
