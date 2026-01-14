# 🌐 Generador automático de infraestructura Azure con IA y RAG

## 🧠 Descripción general

Este proyecto implementa un **asistente inteligente para infraestructura en Azure**, especializado en **Terraform** y basado en la arquitectura **RAG (Retrieval-Augmented Generation)**.  

El sistema utiliza una **base de datos vectorial Qdrant** y modelos **LLM de OpenAI** para responder preguntas, citar fuentes y generar código HCL válido.  
Incluye además funcionalidades **multimodales** (voz, texto, imagen, audio) y una **interfaz web interactiva** desarrollada con **Gradio**.

---

## ⚙️ Principales funcionalidades

### 🤖 Chatbot inteligente

- Responde preguntas en español sobre Terraform y Azure.  
- Genera fragmentos de código HCL explicados paso a paso.  
- Cita las fuentes utilizadas en cada respuesta (documentos indexados en Qdrant).  
- Soporte multimodal: texto, voz, imágenes y archivos.

### 📚 Entrenamiento personalizado

- Permite subir archivos de entrenamiento (`.tf`, `.pdf`, `.docx`, `.txt`, etc.) para enriquecer la base de conocimiento.  
- Detección automática de duplicados y versiones de documentos.  
- Gestión y visualización de archivos procesados.

### 🎛️ Panel visual en Gradio

- Interfaz interactiva de chat y entrenamiento.  
- Integración con la API FastAPI del agente.  
- Control de audio, archivos y chat en una única vista.

---

## 🏗️ Arquitectura y componentes

| Componente | Tecnología | Descripción |
|-------------|-------------|-------------|
| **API Backend** | FastAPI | Exposición de endpoints REST para consultas y health check. |
| **UI** | Gradio | Interfaz visual multimodal para interacción con el asistente. |
| **Vector DB** | Qdrant | Almacenamiento de embeddings y búsqueda semántica. |
| **Agente RAG** | LangChain + OpenAI | Recupera contexto y genera respuestas precisas. |
| **Contenedores** | Docker + GitHub Actions | Automatización de builds y despliegues. |

---

## 💻 Instalación y ejecución local

### 1️⃣ Clonar el repositorio

```bash
git clone https://github.com/anabbre/jupiter-iaa-azure.git
cd jupiter-iaa-azure
```

### 2️⃣ Crear y activar entorno virtual

Requiere **Python 3.10+**.

```bash
python -m venv .venv
source .venv/bin/activate     # Linux / Mac
.venv\Scripts\activate        # Windows
```


### 3️⃣ Instalar dependencias

Puedes instalar las dependencias usando **pip** o, de forma más rápida y moderna, con **uv**:

**Con pip:**
```bash
pip install -r requirements.txt
```

**Con uv:**
```bash
uv pip install -r requirements.txt
```
> ℹ️ uv es un gestor de paquetes ultrarrápido compatible con pip. Puedes instalarlo con:
> ```bash
> pip install uv
> ```

### 4️⃣ Configurar variables de entorno

Crea un archivo `.env` en la raíz (usa `.env.example` como referencia):

```env

# -------- Qdrant Config --------
EMB_MODEL = "text-embedding-3-large"
QDRANT_URL = "http://localhost:6333"
QDRANT_COLLECTION = "Terraform_Book_Index"

# ------- LLM Config --------
DB_DIR = "src/rag/vector_db"
LLM_MODEL = "gpt-4o-mini"
K_DOCS = 3

# ------- API -------
API_URL = "http://localhost:8008"

# -------- Secrets --------
OPENAI_API_KEY=

```

### 5️⃣ Ejecutar la aplicación localmente

```bash
# Iniciar la API
uvicorn src.api.main:app --host 0.0.0.0 --port 8008 --reload

# Iniciar la interfaz de usuario
python -m src.ui.ui
```

Accede a la interfaz web en:  
➡️ [http://localhost:7860](http://localhost:7860)

---

## 🐳 Despliegue con Docker

El proyecto incluye archivos `Dockerfile` tanto para la **API** como para la **UI**, permitiendo el despliegue completo mediante Docker o Docker Compose.

### Construcción manual de imágenes

```bash
# API
docker build -t jupiter-api:test -f src/api/Dockerfile .

# UI
docker build -t jupiter-ui:test -f src/ui/Dockerfile .
```

### Ejecución manual

```bash
# Ejecutar API
docker run --env-file .env -p 8008:8008 jupiter-api:test

# Ejecutar UI
docker run -p 7860:7860 jupiter-ui:test
```

### Docker Compose

También puedes levantar toda la infraestructura (API, UI y Qdrant) con:

```bash
docker compose up --build
```

Cuando se ejecuta este comando, se levantan automáticamente tres contenedores:

| Contenedor | Descripción |
|-------------|-------------|
| **qdrant_db** | Base de datos vectorial que almacena embeddings y metadatos. Utiliza la imagen oficial `qdrant/qdrant`. |
| **terraform_rag_api** | Servicio backend desarrollado con FastAPI que gestiona las consultas al asistente y la comunicación con Qdrant. |
| **terraform_rag_ui** | Interfaz visual desarrollada con Gradio que permite interactuar con el asistente. |

📌 **Nota:**  
Con el volumen creado ejecutamos `src/services/rag_indexer.py` para llenar la base de datos vectorial (Qdrant) con los documentos y ejemplos del proyecto.

### ℹ️ ¿Qué hace `rag_indexer.py`?
Este script es el **indexador principal** del sistema. Se encarga de:
- Leer y procesar documentos (`.pdf`, `.md`, archivos Terraform, ejemplos) desde la carpeta `data/` y el manifest.
- Dividir los documentos en "chunks" optimizados para búsqueda semántica.
- Enriquecer cada chunk con metadatos útiles (tipo de recurso, sección, calidad del código, etc.).
- Eliminar duplicados para evitar información redundante.
- Insertar los chunks en las colecciones de Qdrant, listos para ser consultados por el asistente.

#### Uso básico:
```bash
python src/services/rag_indexer.py
```
Esto indexa todos los documentos y ejemplos.

#### Opciones avanzadas:
Puedes usar argumentos para controlar el proceso:
- `--recreate`          : Borra y recrea las colecciones antes de indexar (limpia la DB).
- `--only-pdfs`         : Solo indexa PDFs.
- `--only-tf`           : Solo indexa archivos Terraform.
- `--only-examples`     : Solo indexa ejemplos del manifest.
- `--chunk-size-pdf N`  : Cambia el tamaño de chunk para PDFs.
- `--chunk-size-tf N`   : Cambia el tamaño de chunk para Terraform.

Ejemplo:
```bash
python src/services/rag_indexer.py --recreate --only-pdfs
```
Esto solo indexa los PDFs y limpia la colección antes de empezar.

Una vez indexada la información, la UI podrá responder citando los chunks consultados vía API.

---

## 🚀 Integración Continua (CI/CD) con GitHub Actions

El proyecto cuenta con tres workflows principales definidos en `.github/workflows`, que automatizan la validación y construcción de las imágenes.

---

### 🧠 1. Build automático de la imagen Docker del API

**Archivo:** `.github/workflows/docker-api.yml`

- Construye la imagen Docker del backend (`jupiter-api`).  
- Se ejecuta al detectar cambios en `src/api/**`, `Dockerfile`, o archivos relevantes.  
- Publica la imagen en **GitHub Container Registry (GHCR)** al hacer push a `main`.

📦 **Imagen publicada:**  
`ghcr.io/<usuario>/jupiter-api`

**Uso local:**

```bash
cp .env.example .env
docker build -t jupiter-api:test -f src/api/Dockerfile .
docker run --env-file .env -p 8008:8008 jupiter-api:test
```

---

### 🖥️ 2. Build automático de la imagen Docker del UI (Gradio)

**Archivo:** `.github/workflows/docker-ui.yml`

- Construye la imagen Docker de la interfaz (`jupiter-ui`).  
- Se ejecuta al detectar cambios en `src/ui/**` o en el `Dockerfile`.  
- Publica la imagen en GHCR cuando se hace push a `main`.

📦 **Imagen publicada:**  
`ghcr.io/<usuario>/jupiter-ui`

**Uso local:**

```bash
docker build -t jupiter-ui:test -f src/ui/Dockerfile .
docker run -p 7860:7860 jupiter-ui:test
```

Accede al navegador en:  
➡️ [http://localhost:7860](http://localhost:7860)

---

### 🧩 3. Validación de archivos Terraform (pendiente de integración)

**Archivo:** `.github/workflows/terraform-validate.yml`

Workflow preparado para validar la sintaxis y formato de los archivos `.tf` mediante **Terraform CLI** y **TFLint**.  
Actualmente no se ejecuta porque el proyecto aún no contiene módulos de infraestructura, pero se integrará en la próxima fase cuando se despliegue la arquitectura en Azure.

**Objetivo futuro:**

- Validar automáticamente los `.tf` con `terraform fmt` y `terraform validate`.  
- Comprobar que la infraestructura cumpla las convenciones de estilo y seguridad.

---

## 🧩 Tecnologías principales

| Área | Tecnología / Herramienta |
|------|----------------------------|
| Lenguaje principal | Python 3.12 |
| Backend | FastAPI |
| Frontend | Gradio |
| Vector DB | Qdrant |
| Modelos LLM | OpenAI + LangChain |
| Contenedores | Docker & Docker Compose |
| CI/CD | GitHub Actions |
| Infraestructura futura | Terraform + Azure |

---

Máster en **Inteligencia Artificial, Cloud Computing y DevOps**  
Pontia Tech · 2025

---
