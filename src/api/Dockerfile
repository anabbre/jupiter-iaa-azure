# Usar Python 3.12 como base
FROM python:3.12-slim

# Establecer directorio de trabajo
WORKDIR /app

# Variables de entorno
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Copiar archivos de dependencias
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

# Copiar código fuente
COPY src/ ./src/
COPY config/ ./config/
COPY Scripts/ ./Scripts/
COPY data/docs/examples/ ./data/docs/examples/
COPY data/terraform/ ./data/terraform/
COPY data/optimized_chunks/ ./data/optimized_chunks/

# Crear directorios necesarios
RUN mkdir -p logs

# Exponer puerto
EXPOSE 8008

# INICIO SEGURO: Intenta indexar, si falla por lo que sea, arranca la API igual
CMD ["sh", "-c", "python Scripts/RAG/index_examples.py && uvicorn src.api.app_main:app --host 0.0.0.0 --port 8008"]