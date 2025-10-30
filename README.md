# Generador automático de infraestructura Azure con IA y RAG


## Descripción general

Este proyecto implementa un asistente inteligente para infraestructura en Azure, especializado en Terraform y basado en arquitectura RAG (Retrieval-Augmented Generation). Utiliza una base de datos vectorial Qdrant y modelos LLM de OpenAI para responder preguntas, citar fuentes y generar código HCL válido. Incluye funcionalidades multimodales (voz, imagen, audio) y una API REST para integración.


## Principales funcionalidades

### Chatbot
- Interacción en español sobre Terraform y Azure.
- Respuestas basadas en documentos indexados y fuentes citadas.
- Generación de código HCL válido y explicación de buenas prácticas.
- Soporte multimodal: entrada/salida de voz, imágenes y audio.
- Visualización de fuentes utilizadas en cada respuesta.

### 1. Chatbot

- Permite interactuar con el asistente especializado en Terraform.
- El usuario puede escribir preguntas relacionadas con infraestructura y código Terraform.
- El asistente responde en español, de forma clara y concisa.
- Si la respuesta se basa en documentos subidos, se muestra la sección "Fuentes utilizadas" con los archivos y fragmentos relevantes.
- El usuario puede visualizar el contenido de cada fuente pulsando sobre el nombre del archivo.
- Si la respuesta no requiere fuentes, no se muestra la sección de fuentes.
- Se puede reiniciar la conversación en cualquier momento con el botón "Nueva conversación".

#### Casuísticas:
- Si el asistente no puede responder, muestra un mensaje de error amigable.
- El historial de chat se mantiene entre preguntas y respuestas.


### Entrenamiento


- Subida de archivos de entrenamiento para mejorar el asistente.
- Soporte para `.tf`, `.txt`, `.md`, `.pdf`, `.docx`, `.html`.
- Gestión automática de duplicados y versiones de documentos.
- Visualización y gestión de documentos ya subidos.

#### Casuísticas:
- Si se intenta subir un archivo ya existente (mismo nombre y contenido), se sobreescribe.
- Si se sube un archivo con el mismo nombre pero diferente contenido, se guarda con sufijo incremental.
- Si el archivo es de tipo no soportado, se muestra una advertencia y no se procesa.
- Si no hay archivos válidos, se muestra una advertencia.


## Arquitectura y componentes

- **Vector DB Qdrant**: Almacena embeddings y permite búsquedas semánticas rápidas.
- **RAGAgent**: Recupera contexto relevante y genera respuestas con LLM.
- **API FastAPI**: Exposición de endpoints para consulta y health check.
- **Ingesta de documentos**: Scripts para indexar y actualizar la base de conocimiento.
- **Interfaz Gradio/Streamlit**: Chatbot multimodal y panel de entrenamiento.
- **Docker y Docker Compose**: Despliegue sencillo de la app y la base Qdrant.

1. El usuario puede consultar al asistente en la pestaña "Chatbot" y ver las fuentes utilizadas en las respuestas.
2. En la pestaña "Entrenamiento", puede subir nuevos archivos para mejorar el modelo, siguiendo la lógica de comprobación de duplicados y contenido.
3. El sistema gestiona los archivos subidos, asegurando que no se pierda información relevante y evitando duplicados innecesarios.



## Instalación y ejecución


1. **Clona el repositorio**
	```bash
	git clone https://github.com/anabbre/jupiter-iaa-azure.git
	cd jupiter-iaa-azure
	```


2. **Instala las dependencias usando uv**
	Requiere Python 3.8+ y tener instalado [uv](https://github.com/astral-sh/uv).

	Si no tienes `uv` instalado, puedes instalarlo con:
	```bash
	pip install uv
	```

	Luego, crea un entorno virtual y activa el entorno:
	```bash
	uv venv .venv
	# En Windows
	.venv\Scripts\activate
	# En Linux/Mac
	source .venv/bin/activate
	```

	Instala las dependencias del proyecto:
	```bash
	uv pip install -r requirements.txt
	```


3. **Configura las variables de entorno**
	Crea un archivo `.env` en la raíz con tus credenciales y parámetros:
	```
	# -------- Qdrant Config --------
	EMB_MODEL = "text-embedding-3-large"
	QDRANT_URL = "http://localhost:6333"
	QDRANT_COLLECTION = "terraform_docs_index"

	# ------- LLM Config --------
	DB_DIR = "src/rag/vector_db"
	LLM_MODEL = "gpt-4o-mini"
	K_DOCS = 3

	# -------- Secrets --------
	OPENAI_API_KEY=

	```


4. **Ejecuta la aplicación**
	```bash
	uvicorn api:app --port 8008 --reload
	python ui.py
	```


5. **Accede a la interfaz web**
	Abre tu navegador y visita la URL local para interactuar con el chatbot y el panel de entrenamiento.

### Despliegue con Docker

Puedes levantar la app y la base Qdrant con Docker Compose:
```bash
docker-compose up --build
```
Esto inicia el servicio Qdrant y la app en modo Streamlit.

### Ingesta y actualización de documentos

Para reindexar o añadir nuevos documentos a la base vectorial, ejecuta:
```bash
python ingest.py
```
Puedes personalizar la colección y el modelo en `config/project_config.py` o vía variables de entorno.

## Endpoints principales (API)

- `GET /` y `/health`: Health check y estado de la base vectorial.
- `POST /query`: Consulta al agente RAG, recibe pregunta y devuelve respuesta con fuentes.

## Dependencias principales

- `langchain`, `langchain-openai`, `langchain-qdrant`, `qdrant-client`, `streamlit`, `gradio`, `fastapi`, `uvicorn`, `openai`, `gtts`, `pymupdf`, `python-dotenv`.

## Créditos y contacto

Desarrollado por [anabbre](https://github.com/anabbre). Para dudas o sugerencias, abre un issue en el repositorio.
