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

# Crear directorios necesarios
RUN mkdir -p logs

# Exponer puerto
EXPOSE 8008

# Iniciar indexación y luego la aplicación
CMD python Scripts/RAG/index_examples.py --force && uvicorn src.api.app_main:app --host 0.0.0.0 --port 8008
