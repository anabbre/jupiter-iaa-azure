import pandas as pd
import streamlit as st
import os
import utils

def main():
    """Función principal que muestra solo el chatbot del asistente terraform"""
    st.set_page_config(layout="wide")

    # Nombre fijo del asistente
    index_name = "terraform"

    # Inicializar variables de sesión necesarias para el chat
    if "chat_histories" not in st.session_state:
        st.session_state.chat_histories = {}
    if "message_sources" not in st.session_state:
        st.session_state.message_sources = {}
    if "is_processing" not in st.session_state:
        st.session_state.is_processing = False
    if "current_prompt" not in st.session_state:
        st.session_state.current_prompt = None

    # Inicializar historial de chat si no existe
    if index_name not in st.session_state.chat_histories:
        st.session_state.chat_histories[index_name] = {
            "user_prompt_history": [],
            "chat_answers_history": [],
            "chat_history": [],
            "used_fragments": {}
        }

    # Obtener el estado del chat
    chat_state = st.session_state.chat_histories[index_name]

    # Mostrar el título
    st.title(f"Chat con asistente de Terraform")


    # Botón para subir archivos de entrenamiento
    st.markdown("### Subir archivos de entrenamiento (.tf, .txt, .md, .pdf, .docx, .html)")
    uploaded_files = st.file_uploader(
        "Selecciona uno o varios archivos para añadir al modelo:",
        type=["tf", "txt", "md", "pdf", "docx", "html"],
        accept_multiple_files=True,
        key="file_uploader_train"
    )
    if uploaded_files:
        with st.spinner("Procesando archivos y añadiendo al modelo..."):
            success = utils.ingest_docs(uploaded_files, assistant_id="terraform", index_name=index_name)
        if success:
            st.success("Archivos añadidos correctamente al modelo.")
        else:
            st.error("Error al procesar los archivos. Revisa el log para más detalles.")

    # Botón para reiniciar conversación
    if st.button("🔄 Reiniciar conversación", key="reset_chat"):
        chat_state["user_prompt_history"] = []
        chat_state["chat_answers_history"] = []
        chat_state["chat_history"] = []
        chat_state["used_fragments"] = {}
        st.session_state.message_sources = {}
        st.session_state.is_processing = False
        st.session_state.current_prompt = None
        st.rerun()

    # Área de mensajes con scroll
    chat_messages = st.container(height=300)
    with chat_messages:
        # Mostrar historial de mensajes
        for i, (user_query, ai_response) in enumerate(zip(
                chat_state["user_prompt_history"],
                chat_state["chat_answers_history"]
        )):
            # Mensaje del usuario
            st.chat_message("user").write(user_query)

            # Extraer respuesta sin fuentes
            clean_response = ai_response
            if "*fuentes utilizados:*" in ai_response:
                clean_response = ai_response.split("*fuentes utilizados:*")[0]

            # Mensaje del asistente
            with st.chat_message("assistant"):
                st.markdown(clean_response)

                # Mostrar fuentes para este mensaje específico
                message_id = f"msg_{i}"
                if message_id in st.session_state.message_sources and st.session_state.message_sources[message_id]:
                    st.markdown("**Fuentes utilizadas:**")

                    # Crear 4 columnas para las fuentes
                    cols = st.columns(4)

                    # Obtener fuentes de este mensaje
                    message_fragments = st.session_state.message_sources[message_id]
                    fragments_by_file = {}

                    # Agrupar fuentes por archivo
                    for key, fragment in message_fragments.items():
                        filename = fragment["metadata"].get("filename", "Desconocido") if "metadata" in fragment else "Desconocido"
                        if filename not in fragments_by_file:
                            fragments_by_file[filename] = []
                        fragments_by_file[filename].append(fragment)

                    # Distribuir las fuentes entre las columnas
                    files_list = list(fragments_by_file.items())
                    for j, (filename, fragments) in enumerate(files_list):
                        col_index = j % 4  # Distribuir en las 4 columnas
                        with cols[col_index]:
                            if st.button(f"📄 {filename} ({len(fragments)})", key=f"file_{message_id}_{filename}"):
                                st.session_state.show_fragment_dialog = True
                                st.session_state.current_file = filename
                                st.session_state.current_fragments = fragments
                                st.rerun()

        # Mostrar mensaje en procesamiento (si aplica)
        if st.session_state.is_processing and st.session_state.current_prompt:
            st.chat_message("user").write(st.session_state.current_prompt)
            with st.chat_message("assistant"):
                with st.spinner("Pensando..."):
                    # Generar respuesta
                    generated_response = utils.run_llm_on_index(
                        query=st.session_state.current_prompt,
                        chat_history=chat_state["chat_history"],
                        index_name=index_name
                    )

                    # Crear un ID para este mensaje
                    message_id = f"msg_{len(chat_state['user_prompt_history'])}"
                    st.session_state.message_sources[message_id] = {}

                    # Guardar fuentes específicas para este mensaje
                    if "source_documents" in generated_response and generated_response["source_documents"]:
                        for doc in generated_response["source_documents"]:
                            if hasattr(doc, "metadata") and "filename" in doc.metadata:
                                fragment_key = f"{doc.metadata.get('filename')}_{doc.page_content[:30]}"
                                # Guardar en el historial general
                                if "used_fragments" not in chat_state:
                                    chat_state["used_fragments"] = {}
                                if fragment_key not in chat_state["used_fragments"]:
                                    chat_state["used_fragments"][fragment_key] = {
                                        "content": doc.page_content,
                                        "metadata": doc.metadata
                                    }
                                # Guardar para este mensaje específico
                                st.session_state.message_sources[message_id][fragment_key] = {
                                    "content": doc.page_content,
                                    "metadata": doc.metadata
                                }

                    # Actualizar historial
                    chat_state["user_prompt_history"].append(st.session_state.current_prompt)
                    chat_state["chat_answers_history"].append(generated_response['result'])
                    chat_state["chat_history"].append(("human", st.session_state.current_prompt))
                    chat_state["chat_history"].append(("ai", generated_response["result"]))

                    # Finalizar procesamiento
                    st.session_state.is_processing = False
                    st.session_state.current_prompt = None
                    st.rerun()

    # Input para nuevos mensajes
    prompt = st.chat_input("Haz una pregunta sobre Terraform...")
    if prompt and not st.session_state.is_processing:
        # Iniciar procesamiento
        st.session_state.is_processing = True
        st.session_state.current_prompt = prompt
        st.rerun()

    # Dialog de fuentes
    if "show_fragment_dialog" in st.session_state and st.session_state.show_fragment_dialog:
        if hasattr(st.session_state, "current_fragments") and st.session_state.current_file:
            @st.dialog(f"Fuentes de {st.session_state.current_file}", width='large')
            def show_fragments_dialog():
                st.subheader(f"Fuentes de {st.session_state.current_file}")

                for idx, fragment in enumerate(st.session_state.current_fragments):
                    expander_title = ""
                    if "metadata" in fragment and "page" in fragment["metadata"]:
                        expander_title = f"Page {int(fragment['metadata']['page'])} --- "
                    expander_title += fragment['content'][:90] + "..."

                    with st.expander(expander_title, expanded=(idx == 0)):
                        st.markdown("**Contenido:**")
                        st.markdown(f"```\n{fragment['content']}\n```")

            show_fragments_dialog()
            st.session_state.show_fragment_dialog = False

if __name__ == "__main__":
    main()