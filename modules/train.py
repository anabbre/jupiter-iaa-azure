import streamlit as st
from aux_files import _utils as aux

def show_train(index_name):
        # Módulo para mostrar el listado de documentos actualmente subidos al índice
        docs = aux.get_docs_by_index(index_name, limit=30)
        existing_filenames = set()
        if docs:
            st.markdown("### Documentos actualmente subidos para entrenamiento")
            # Obtener nombres de archivos ya subidos (únicos)
            existing_filenames = set(
                doc.metadata.get("filename", "Desconocido") 
                for doc in docs if hasattr(doc, "metadata")
            )
            # Mostrar solo nombres únicos
            for filename in existing_filenames:
                st.write(f"• {filename}")
                
        # Módulo para subir nuevos archivos al entrenamiento
        st.markdown("### Subir archivos de entrenamiento (.tf, .txt, .md, .pdf, .docx, .html)")
        uploaded_files = st.file_uploader(
            "Selecciona uno o varios archivos para añadir al modelo:",
            type=["tf", "txt", "md", "pdf", "docx", "html"],
            accept_multiple_files=True,
            key="file_uploader_train"
        )       
        progress_placeholder = st.empty()
                
        if uploaded_files:
            # Filtrar archivos que no estén en existing_filenames
            if existing_filenames:
                files_to_add = [file for file in uploaded_files if file.name not in existing_filenames]
            else:
                files_to_add = [file for file in uploaded_files]
            if not files_to_add:
                st.warning("Este archivo ya ha sido añadido previamente.")
            else:            
                progress_bar = progress_placeholder.progress(0, text="Procesando archivos...")
                with st.spinner("Procesando archivos y añadiendo al modelo..."):
                    total_files = len(uploaded_files)
                    success = True
                    for idx, file in enumerate(uploaded_files):
                        # Procesar cada archivo individualmente
                        result = aux.ingest_docs([file], assistant_id=index_name, index_name=index_name)
                        if not result:
                            success = False
                        progress_bar.progress((idx + 1) / total_files, text=f"Procesando archivo {idx+1}/{total_files}")
                    progress_bar.empty()
                if success:
                    st.success("Archivos añadidos correctamente al modelo.")
                    st.session_state.is_trained = True
                else:
                    st.error("Error al procesar los archivos. Revisa el log para más detalles.")
                    st.session_state.is_trained = False
