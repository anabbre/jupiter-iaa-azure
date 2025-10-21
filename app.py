import streamlit as st
from aux_files import _utils as aux

logger = aux.get_logger(__name__, subdir="app")


def main():
    """Función principal que despliega el proyecto"""
    logger.info("🚀 Aplicación iniciada")
    st.set_page_config(layout="wide")

    # Nombre fijo del asistente
    index_name = "terraform"

    # Crear las pestañas antes de usarlas
    tabs = st.tabs(["Chatbot", "Entrenamiento"])

    # Pestaña de chatbot
    with tabs[0]:
        from modules.chatbot import show_chatbot

        show_chatbot(index_name)

    # Pestaña de entrenamiento
    with tabs[1]:
        from modules.train import show_train

        show_train(index_name)


if __name__ == "__main__":
    main()
