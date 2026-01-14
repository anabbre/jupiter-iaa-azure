# 🌐 Generador automático de infraestructura Azure con IA y RAG

## 🧠 Descripción general

Este proyecto implementa un **asistente inteligente para infraestructura en Azure**, especializado en **Terraform** y basado en la arquitectura **RAG (Retrieval-Augmented Generation)**.  

El sistema utiliza una **base de datos vectorial Qdrant** y modelos **LLM de OpenAI** para responder preguntas, citar fuentes y generar código HCL válido para Azure.
Cuenta con una **interfaz web interactiva** desarrollada con **Gradio** para facilitar la interacción mediante chat.

---

## 🚀 Demo en vivo

El proyecto está desplegado y operativo en la nube. Puedes probarlo aquí:  
➡️ **Acceder al Asistente (Desplegado en AWS):**  
http://jupiter-iaa-dev-alb-1110535381.eu-west-1.elb.amazonaws.com

---

## ⚙️ Principales funcionalidades

### 🤖 Chatbot inteligente

- **Especialista en Azure:** Responde preguntas y genera configuraciones para el provider `azurerm`.
- **Explicación paso a paso:** Genera fragmentos de código HCL explicados detalladamente.
- **Citas precisas:** Indica el documento exacto y la sección utilizada (PDFs o Markdowns) para fundamentar la respuesta.
- **Historial de conversación:** Mantiene el contexto de las preguntas anteriores.

### 📚 Gestión de Conocimiento (RAG)

- **Sincronización Cloud:** Descarga y procesa automáticamente la documentación desde **AWS S3** al iniciar el servicio.
- **Lectura robusta:** Utiliza `pypdf` para procesar manuales técnicos complejos sin errores de lectura.
- **Motor Vectorial:** Indexación eficiente en Qdrant para búsquedas semánticas rápidas y precisas.

### 🎛️ Panel visual en Gradio

- Interfaz limpia y amigable para chatear con el asistente.
- Integración fluida con la API vía **Balanceador de Carga (ALB)** en AWS o vía host local en desarrollo.
- Visualización clara de las respuestas y fragmentos de código.

---

## 🏗️ Arquitectura y componentes

| Componente | Tecnología | Descripción |
|-------------|-------------|-------------|
| **Cómputo** | AWS ECS Fargate | Ejecución de contenedores *serverless* (API, UI, Qdrant) sin gestión de servidores. |
| **Red** | AWS ALB | Application Load Balancer para gestionar el tráfico, reglas de enrutado y *health checks*. |
| **Almacenamiento** | AWS S3 | Repositorio centralizado para los documentos de conocimiento (PDFs, docs y ejemplos).|
| **Backend** | FastAPI | API optimizada con soporte de **Doble Enrutamiento** (funciona en `/query` local y `/api/query` en nube). |
| **UI** | Gradio | Interfaz visual multimodal para interacción con el asistente (chat). |
| **Vector DB** | Qdrant | Almacenamiento de embeddings y búsqueda semántica. |
| **Agente RAG** | LangChain + OpenAI | Recupera contexto y genera respuestas fundamentadas. |
| **Contenedores** | Docker + GitHub Actions | Automatización de builds y despliegues. |
| **Seguridad** | Security Groups | Aislamiento de red entre servicios y exposición pública controlada. |

---

---

## 📁 Estructura del proyecto


```text
JUPITER-IAA-AZURE/
├─ .github/
│  └─ workflows/
│     ├─ terraform-validate.yml     # Validación/chequeos de Terraform (CI)
│     ├─ docker-api.yml             # Build + push imagen API
│     ├─ docker-ui.yml              # Build + push imagen UI
│     ├─ deploy-api.yml             # Deploy API en ECS (CD)
│     └─ deploy-ui.yml              # Deploy UI en ECS (CD)
│
├─ config/                          # Configuración de la app (logger, reglas, etc.)
│
├─ data/
│  ├─ docs/                         # Markdown(s) adicionales de documentación
│  ├─ pdfs/
│  │  └─ Libro-TF.pdf               # Manual/Libro usado como fuente (ejemplo)
│  └─ terraform/                    # Casos de uso / ejemplos Terraform (carpetas ex01..ex10)
│     ├─ 01-storage-static-website/
│     ├─ 02-storage-cdn/
│     ├─ 03-frontdoor-static/
│     ├─ 04-static-site-app-service/
│     ├─ 05-static-site+custom-domain/
│     ├─ 06-static-site+https/
│     ├─ 07-static-site+logging/
│     ├─ 08-static-site+diagnostics/
│     ├─ 09-static-site+alerts/
│     └─ 10-static-site+tfvars-ejemplo/
│
infra/                           # Infraestructura como código (Terraform) para AWS
├── ecs/                         # Definiciones auxiliares relacionadas con ECS
│   ├── taskdef-api.json         # Plantilla / referencia de Task Definition para la API
│   └── taskdef-ui.json          # Plantilla / referencia de Task Definition para la UI
│
├── envs/
│   └── dev/                     # Entorno de despliegue DEV
│       ├── main.tf              # Entry point del entorno (orquesta los módulos)
│       ├── variables.tf         # Variables del entorno
│       ├── outputs.tf           # Outputs expuestos (URLs, ARNs, etc.)
│       ├── versions.tf          # Versiones de providers y Terraform
│       ├── backend.tf           # Configuración del backend de estado (si aplica)
│       ├── terraform.tfvars     # Valores concretos del entorno DEV
│       └── .terraform.lock.hcl  # Lock de providers (generado con terraform init)
│
├── modules/                     # Módulos Terraform reutilizables
│   ├── network/                 # Red base (VPC, subnets, routing, etc.)
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   │
│   ├── alb/                     # Application Load Balancer
│   │   ├── main.tf              # ALB, listeners y reglas
│   │   ├── variables.tf
│   │   └── outputs.tf           # DNS del ALB, ARNs, etc.
│   │
│   ├── ecr/                     # Elastic Container Registry
│   │   ├── main.tf              # Repositorios Docker (API / UI)
│   │   ├── variables.tf
│   │   └── outputs.tf
│   │
│   ├── ecs/                     # ECS Fargate (servicios y tareas)
│   │   ├── main.tf              # Cluster, servicios y task definitions
│   │   ├── variables.tf
│   │   └── outputs.tf
│
├─ qdrant_config/
│  └─ config.yaml                   # Config de Qdrant (cuando aplica)
│
├─ src/
│  ├─ api/
│  │  ├─ api.py                     # FastAPI: endpoints (/health, /query, /debug/...)
│  │  ├─ schemas.py                 # Modelos de request/response
│  │  └─ Dockerfile                 # Imagen API
│  │
│  ├─ ui/
│  │  ├─ ui.py                      # Gradio UI: chat + conexión con API
│  │  └─ Dockerfile                 # Imagen UI
│  │
│  ├─ services/
│  │  ├─ rag_indexer.py             # Indexador: PDFs/MD/ejemplos -> chunks -> Qdrant
│  │  ├─ embeddings.py              # Embeddings y configuración del modelo
│  │  ├─ search.py                  # Recuperación/consulta a Qdrant
│  │  ├─ relevance_filter.py        # Filtro de relevancia / scoring (si aplica)
│  │  ├─ llms.py                    # Cliente/abstracción LLM
│  │  └─ vector_store.py            # Cliente Qdrant + ensure_collection, etc.
│  │
│  └─ Agent/
│     ├─ graph.py                   # Orquestación del agente (LangGraph)
│     ├─ context_agent.py           # Gestión de contexto/historial
│     └─ nodes/                     # Nodos: retrieval, generation, validation, etc.
│
├─ docker-compose.yml               # Stack local (qdrant + api + ui)
├─ Makefile                         # Comandos de arranque/indexación (start, rag-index, rag-reindex...)
├─ requirements.txt                 # Dependencias Python
├─ pyproject.toml                   # Config del proyecto / tooling
├─ .env.example                     # Plantilla de variables de entorno
└─ README.md
```

---

## 💻 Instalación y ejecución local

### 1️⃣ Clonar el repositorio

```bash
git clone [https://github.com/anabbre/jupiter-iaa-azure.git](https://github.com/anabbre/jupiter-iaa-azure.git)
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

El proyecto utiliza un `requirements.txt` optimizado para separar las versiones **CPU** de PyTorch (ahorrando espacio en CI/CD).  
Puedes instalar las dependencias usando **pip** o, de forma más rápida y moderna, con **uv**:

**Con pip:**
```bash
pip install -r requirements.txt
```

**Con uv:**
```bash
uv pip install -r requirements.txt
```

> ℹ️ `uv` es un gestor de paquetes ultrarrápido compatible con pip. Puedes instalarlo con:
> ```bash
> pip install uv
> ```

### 4️⃣ Configurar variables de entorno

1. Crea un archivo `.env` en la raíz del proyecto basándote en el ejemplo proporcionado (`.env.example`).
2. Rellena las claves necesarias.

Variables clave:

- `OPENAI_API_KEY` → Necesaria para que el asistente genere respuestas.
- `S3_BUCKET` o `S3_DATA_BUCKET_NAME` → Bucket S3 donde se alojan los documentos (PDFs, docs y ejemplos).  
  - Si tienes acceso al bucket del proyecto: usa `jupiter-iaa-docs` (si aplica en vuestro entorno).  
  - Si quieres usar tu propio bucket: crea uno en AWS, sube el contenido de la carpeta `data/` y pon aquí su nombre.
- `AWS_PROFILE` (opcional) → Perfil local de AWS si necesitas acceso a bucket privado desde tu máquina (para indexar en local).

> ✅ Consejo: si vas a ejecutar `make start` y no necesitas S3, puedes dejar el bucket sin definir y el sistema seguirá funcionando con los datos locales (siempre que estén presentes).

### 5️⃣ Ejecutar la aplicación localmente (recomendado: Makefile)

El `Makefile` encapsula el flujo completo: levantar Qdrant, esperar a que esté OK, indexar y levantar API + UI.

**Comando maestro:**
```bash
make start
```

Cuando termina, tendrás accesos:

- 📘 API Docs: http://localhost:8008/docs  
- 🤖 Chat UI:  http://localhost:7860  
- 🧠 Qdrant:   http://localhost:6333/dashboard  

#### Targets principales del Makefile (según el flujo actual)

- **`make wait-qdrant`**  
  Espera a que Qdrant esté saludable antes de lanzar nada.

- **`make rag-index`**  
  Indexación incremental (solo añade nuevo contenido; no borra colecciones).

- **`make rag-reindex`**  
  Reindexación completa (borra colecciones y recrea desde cero).  
  Ideal cuando cambias la estructura de chunks, metadatos o el modelo de embeddings.

- **`make cold-start`**  
  Arranque “en frío”: levanta Qdrant → espera → reindexa (completo) → levanta API + UI.

- **`make start`**  
  Comando maestro: ejecuta la carga/indexación y luego levanta los servicios.

> 💡 Si usas credenciales AWS locales para acceder a S3 durante el reindexado, el Makefile monta tu carpeta `~/.aws` dentro del contenedor de API y utiliza `AWS_PROFILE` (si está configurado).

---

## 🐳 Despliegue con Docker

Levanta la infraestructura completa localmente (API + UI + Qdrant) asegurando compatibilidad de librerías.

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
Una vez levantado el stack y creado el volumen, el indexador `src/services/rag_indexer.py` es el encargado de llenar Qdrant con los documentos y ejemplos del proyecto.

---

## ℹ️ ¿Qué hace `rag_indexer.py`?

Este script es el **indexador principal** del sistema. Se encarga de:

- Leer y procesar documentos (`.pdf`, `.md`, archivos Terraform, ejemplos) desde la carpeta `data/` y el manifest.
- Dividir los documentos en **chunks** optimizados para búsqueda semántica.
- Enriquecer cada chunk con metadatos útiles (tipo de fuente, sección, ejemplo, etc.).
- Eliminar duplicados para evitar información redundante.
- Insertar los chunks en las colecciones de Qdrant, listos para ser consultados por el asistente.

### Uso básico

```bash
python src/services/rag_indexer.py
```

Esto indexa todos los documentos y ejemplos.

### Opciones avanzadas

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

Una vez indexada la información, la UI podrá responder **citando** los chunks consultados vía API.

---

## ☁️ Flujo de Despliegue (CI/CD)

El proyecto utiliza una estrategia de **Integración y Despliegue Continuo (CI/CD)** basada en workflows de **GitHub Actions**, separando claramente las responsabilidades de validación, construcción y despliegue.

### 1) Integración Continua (CI) — Validación y Construcción

Estos workflows aseguran que el código sea correcto y generan los artefactos (imágenes Docker) necesarios.

- ✅ **Validación de Terraform (`terraform-validate.yml`)**
  - Se ejecuta en Pull Requests o pushes.
  - Verifica formato y validez del código (`terraform fmt`, `terraform validate`) para reducir errores en infraestructura.

- 🐳 **Build de imágenes (`docker-api.yml` / `docker-ui.yml`)**
  - Se disparan al hacer push a `main` (y/o al detectar cambios en `src/api` o `src/ui`, según configuración).
  - Construyen imágenes Docker optimizadas.
  - Publican imágenes en el registry configurado (p.ej. GHCR/ECR según la implementación final).

### 2) Despliegue Continuo (CD) — Actualización en AWS

- 🚀 **Deploy en ECS (`deploy-api.yml` / `deploy-ui.yml`)**
  - **Trigger:** normalmente se ejecutan después de que terminen con éxito los workflows de build.
  - **Acción:**
    1. Autenticación en AWS.
    2. Actualización de la Task Definition para apuntar a la nueva imagen.
    3. *Rolling update* del servicio (ECS reemplaza tareas progresivamente).

---

## 🔄 Sincronización de Datos (S3)

El código y los datos están desacoplados. Para actualizar la base de conocimiento del asistente sin necesidad de modificar el código:

1. Sube los nuevos documentos al bucket S3:

```bash
aws s3 sync ./data s3://jupiter-iaa-docs/data
```

2. Fuerza un nuevo despliegue del servicio de API (desde la consola de ECS o disparando el workflow `deploy-api`) para que los contenedores reinicien, descarguen los nuevos datos y reindexen Qdrant.

---

## 🧩 Tecnologías principales

| Área | Tecnología / Herramienta |
|------|----------------------------|
| Lenguaje principal | Python 3.12 |
| Backend | FastAPI (Async) |
| Frontend | Gradio 5.x |
| Vector DB | Qdrant |
| Modelos LLM | OpenAI + LangChain / LangGraph |
| Contenedores | Docker & Docker Compose |
| CI/CD | GitHub Actions |
| Procesamiento Docs | pypdf (v5.x) + LangChain |
| Infraestructura Cloud | AWS (ECS, Fargate, S3, ALB) |

---

## ✍️ Autores

- **Ana Belén Ballesteros Redondo**  
- **Amalia Martín Ruiz**  
- **Carlos Toro Morales**  
- **Juan Gonzalo Martínez Rubio**

---

Máster en **Inteligencia Artificial, Cloud Computing y DevOps**  
Pontia Tech · 2025

