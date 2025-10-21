# Generador automático de infraestructura Azure con IA

[![Python checks](https://github.com/anabbre/jupiter-iaa-azure/actions/workflows/python_checks.yml/badge.svg)](https://github.com/anabbre/jupiter-iaa-azure/actions/workflows/python_checks.yml)
[![Docker build](https://github.com/anabbre/jupiter-iaa-azure/actions/workflows/docker_build.yml/badge.svg)](https://github.com/anabbre/jupiter-iaa-azure/actions/workflows/docker_build.yml)
[![Validate Terraform examples](https://github.com/anabbre/jupiter-iaa-azure/actions/workflows/terraform_examples.yml/badge.svg)](https://github.com/anabbre/jupiter-iaa-azure/actions/workflows/terraform_examples.yml)

Aplicación con dos pestañas: **Chatbot** (asistente experto en Terraform) y **Entrenamiento** (subida y gestión de documentos para RAG).

---

## Flujo de uso y comportamiento de la aplicación

### 1) Chatbot
- Interactúa en español con un asistente especializado en Terraform.
- Si la respuesta usa documentos, se muestra *Fuentes utilizadas*.
- Botón **Nueva conversación** para reiniciar el chat.

> Casuísticas:
> - Mensajes de error amigables si no puede responder.
> - El historial se mantiene entre preguntas.

### 2) Entrenamiento
- Subida de `.tf`, `.txt`, `.md`, `.pdf`, `.docx`, `.html`.
- Lógica de duplicados:
  - mismo nombre + mismo contenido → **sobrescribe**;
  - mismo nombre + distinto contenido → **sufijo incremental** (`_1`, `_2`, …).
- Se muestra progreso y resultado de la carga.

> Casuísticas:
> - Tipos no soportados → advertencia.
> - Sin archivos válidos → advertencia.

### Resumen del proceso
1. Consulta en **Chatbot** y visualiza fuentes si aplica.  
2. Sube documentos en **Entrenamiento** con gestión de duplicados.  
3. Se preserva la información relevante evitando duplicidades.

---

## Ejecución local

### 0) Requisitos
- Python 3.11+
- (Opcional) Docker + Docker Compose

### 1) Clonar
```bash
git clone https://github.com/anabbre/jupiter-iaa-azure.git
cd jupiter-iaa-azure
```

### 2) Variables de entorno
Crea un .env (o copia desde .env.example):
```
OPENAI_API_KEY=
PINECONE_API_KEY=
PINECONE_ENVIRONMENT=us-east-1
# (opcional) Telemetría/langsmith si lo usáis:
LANGCHAIN_PROJECT=
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=
```

### 3A) Ejecutar con Python
```
pip install -r requirements.txt
# API (FastAPI)
uvicorn api:app --port 8008 --reload
# UI (Streamlit)
python ui.py  # o: streamlit run app.py
```

### 3B) Ejecutar con Docker
```
docker compose up --build
# UI en http://localhost:8501  (si el compose lanza streamlit run app.py)
# API en http://localhost:8008   (si el compose expone la API)
```


## CI/CD del proyecto: 
- **Workflow en .github/workflows/terraform_examples.yml**
Se ejecuta en push/pull_request a develop y main cuando hay cambios en docs/ejemplos-terraform/**.
Pasos: checkout → setup-terraform → terraform fmt --check → terraform init (sin backend) → terraform validate.

- **Python checks (lint + formato + seguridad + tests)**
Workflow en .github/workflows/python_checks.yml.
Pasos: ruff (lint), black --check (formato), isort --check, mypy (permisivo), bandit (seguridad), pytest si hay tests.

- **Docker build (GHCR)
Workflow en .github/workflows/docker_build.yml**
Construye y publica la imagen en GitHub Container Registry (ghcr.io/<owner>/<repo>:latest y :sha).

Los badges arriba muestran el estado en tiempo real de estos workflows.