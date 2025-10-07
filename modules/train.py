import streamlit as st
from aux_files import _utils as aux
logger = aux.get_logger(__name__, subdir="train")

def show_train(index_name):
    logger.info(f"Mostrando interfaz de entrenamiento para el índice: {index_name}")
    
    docs = aux.get_docs_by_index(index_name, limit=30)
    existing_filenames = set()
    if docs:
        st.markdown("### Documentos actualmente subidos para entrenamiento")
        existing_filenames = set(
            doc.metadata.get("filename", "Desconocido")
            for doc in docs if hasattr(doc, "metadata")
        )
        logger.info(f"Documentos existentes para el índice {index_name}: {existing_filenames}")
        for filename in existing_filenames:
            st.write(f"• {filename}")

    st.markdown("### Subir archivos de entrenamiento (.tf, .txt, .md, .pdf, .docx, .html)")
    uploaded_files = st.file_uploader(
        "Selecciona uno o varios archivos para añadir al modelo:",
        type=["tf", "txt", "md", "pdf", "docx", "html"],
        accept_multiple_files=True,
        key="file_uploader_train"
    )
    progress_placeholder = st.empty()

    if uploaded_files:
        if existing_filenames:
            files_to_add = [f for f in uploaded_files if f.name not in existing_filenames]
        else:
            files_to_add = list(uploaded_files)
            
        logger.info(f"Archivos seleccionados para añadir: {[f.name for f in files_to_add]}")

        if not files_to_add:
            logger.warning("Todos los archivos seleccionados ya están añadidos.")
            st.warning("Este/estos archivo(s) ya están añadidos.")
        else:
            progress_bar = progress_placeholder.progress(0, text="Procesando archivos...")
            with st.spinner("Procesando archivos y añadiendo al modelo..."):
                total_files = len(files_to_add)
                success = True
                for idx, file in enumerate(files_to_add):
                    result = aux.ingest_docs([file], assistant_id=index_name, index_name=index_name)
                    if not result:
                        success = False
                        logger.error(f"Error al procesar el archivo: {file.name}")
                    progress_bar.progress((idx + 1) / total_files, text=f"Procesando archivo {idx+1}/{total_files}")
            progress_bar.empty()
            if success:
                st.success("Archivos añadidos correctamente al modelo.")
                st.session_state.is_trained = True
                logger.info(f"Todos los archivos se añadieron correctamente al índice {index_name}.")
            else:
                st.error("Error al procesar algunos archivos. Revisa el log.")
                st.session_state.is_trained = False
                logger.error(f"Hubo errores al añadir algunos archivos al índice {index_name}.")
