# 🚀 Terraform RAG Assistant — Azure

Asistente inteligente (RAG) para **Terraform + Azure** que:

- recupera contexto desde **Qdrant** (ejemplos y PDFs indexados),
- genera **código HCL** y respuestas explicadas,
- expone una **API FastAPI** y una **UI en Gradio**,
- se ejecuta en **Docker** y tiene **CI/CD** con GitHub Actions.

---

## 🧭 Contenidos

- [Qué es](#-qué-es)
- [Funciones principales](#-funciones-principales)
- [Arquitectura](#-arquitectura)
- [Configuración (.env)](#-configuración-env)
- [Arranque rápido con Makefile](#-arranque-rápido-con-makefile)
- [Servicios y URLs](#-servicios-y-urls)
- [CI/CD (Workflows)](#-cicd-workflows)
- [Ejemplos de preguntas](#-ejemplos-de-preguntas)
- [Notas y troubleshooting](#-notas-y-troubleshooting)

---

## 🧠 Qué es

Este proyecto implementa un **agente RAG** para ayudar con tareas de Terraform en Azure.
Cuando haces una consulta, el sistema:

1) **Busca** en Qdrant los fragmentos más relevantes (carpetas con `.tf`, `.md`, `.txt` y páginas de PDFs).  
2) **Construye** un contexto con esas fuentes.  
3) **Genera** la respuesta con un LLM (OpenAI), **incluyendo HCL** cuando procede, y **cita** las fuentes.

> La colección por defecto se define en `docs/examples/manifest.yaml` (p.ej. `collection: jupiter_examples`).

---

## ✨ Funciones principales

- **Chat técnico** en español sobre Terraform/Azure.
- **Generación de HCL** lista para copiar.
- **Citas de fuentes** (ruta, sección y páginas).
- **UI multimodal** (texto/voz/archivos) en Gradio.
- **API FastAPI** para integrarse con otras apps.
- **Indexador** de ejemplos/PDFs para poblar Qdrant.

---

## 🏗️ Arquitectura

| Capa | Tecnología | Descripción |
|---|---|---|
| **UI** | Gradio | Chat visual multimodal que llama a la API. |
| **API** | FastAPI | Endpoints `/` (health) y `/query` para preguntas. |
| **RAG** | LangChain + OpenAI | Recupera contexto (Qdrant) y redacta la respuesta. |
| **Vector DB** | Qdrant | Almacena embeddings y metadatos. |
| **Contenedores** | Docker Compose | Orquesta Qdrant, API y UI. |

---

## 🔐 Configuración (.env)

1. **Duplica** el ejemplo y edítalo:

   ```bash
   cp .env.example .env
   ```

2. **Variables mínimas** a completar en `.env`:

   ```bash
   # Clave de OpenAI (obligatoria para la generación con LLM)
   OPENAI_API_KEY=sk-...

   # Qdrant (se usa el contenedor local por defecto)
   QDRANT_URL=http://qdrant:6333
   ```

   > Crea tu clave en el panel de OpenAI (API Keys) e insértala en `OPENAI_API_KEY`.

3. **Opcional**: si cambias la colección o el modelo, edita `docs/examples/manifest.yaml`.

---

## ⚙️ Arranque rápido con Makefile

> Recomendado para levantar todo sin recordar comandos largos.

```makefile
# --- Contenedores ---
up:            ## Levanta Qdrant + API + UI (build)
\tdocker compose up -d --build

down:          ## Para y elimina contenedores y volúmenes
\tdocker compose down -v

logs-api:      ## Logs en vivo de la API
\tdocker compose logs -f api

logs-ui:       ## Logs en vivo de la UI
\tdocker compose logs -f ui

# --- RAG / Indexación ---
rag-index-examples:  ## (Re)indexa según docs/examples/manifest.yaml
\tdocker compose run --rm api python Scripts/RAG/index_examples.py

rag-reindex-examples: ## Alias explícito
\t$(MAKE) rag-index-examples

rag-search-test: ## Prueba una búsqueda directa
\tdocker compose run --rm api python -c "from src.services.search import search_examples; print(search_examples('https en static site de Azure', k=3))"

# --- Health & curl helpers ---
api-health:    ## Comprueba salud de la API
\tcurl -s http://localhost:8008 | jq

api-query:     ## Lanza consulta de ejemplo (k_docs=3)
\tcurl -s -X POST http://localhost:8008/query \\
\t  -H \"content-type: application/json\" \\
\t  -d '{\"question\":\"¿Cómo configurar backend remoto en Terraform con S3?\",\"k_docs\":3}' | jq
```

### ▶️ Pasos

1. **Levantar servicios**

   ```bash
   make up
   ```

2. **Indexar ejemplos del manifiesto**

   ```bash
   make rag-index-examples
   ```

3. **Probar**

   ```bash
   make api-health
   make api-query
   ```

4. **Abrir la UI**
   - Gradio: <http://localhost:7860>

---

## 🌐 Servicios y URLs

- **API (FastAPI)** → <http://localhost:8008>  
  - Docs OpenAPI: <http://localhost:8008/docs>
- **UI (Gradio)** → <http://localhost:7860>
- **Qdrant (Dashboard)** → <http://localhost:6333/dashboard#/>  
  - REST: `http://localhost:6333`

> Los puertos vienen mapeados en `docker-compose.yml`:
>
> - API: `8008:8008`
> - UI: `7860:7860`
> - Qdrant: `6333:6333` (y `6334` gRPC)

---

## 🔄 CI/CD (Workflows)

En `.github/workflows/` hay **tres** workflows principales:

1. **`docker-api.yml` — Build de la imagen del backend**
   - Construye la imagen Docker de la API cuando hay cambios relevantes.
   - Publica en GHCR (`ghcr.io/<usuario>/jupiter-api`) al hacer push a `main`.

2. **`docker-ui.yml` — Build de la imagen de la UI (Gradio)**
   - Construye la imagen de la interfaz y la publica en GHCR (`ghcr.io/<usuario>/jupiter-ui`).

3. **`terraform-validate.yml` — Validación de ejemplos Terraform**
   - Detecta carpetas con `.tf` en `docs/examples/**`.
   - Ejecuta `terraform fmt -check`, `init -backend=false` y `validate` **offline**.

> Estos workflows facilitan calidad y reproducibilidad sin depender de nubes externas.

---

## 💬 Ejemplos de preguntas

- **HTTPS en Static Web App con Azure Front Door**
  > _“¿Cómo activo HTTPS en una static web app de Azure según los ejemplos?”_

- **Backend remoto en S3**
  > _“¿Cómo configurar backend remoto en Terraform con S3?”_

- **Variables y outputs**
  > _“Dame un ejemplo mínimo de variables y outputs para un módulo de storage en Azure.”_

> Consejo: cuanto más específica sea la consulta, mejor priorizará el RAG los **ejemplos** sobre los PDFs.
