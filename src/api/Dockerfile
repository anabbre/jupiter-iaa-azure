# Usar Python 3.12 como base
FROM python:3.12-slim

# Establecer directorio de trabajo
WORKDIR /app

# Variables de entorno
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src:$PYTHONPATH

# Copiar archivos de dependencias
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install -r requirements.txt

# Copiar código fuente
COPY src/ ./src/
COPY config/ ./config/

# Crear directorios necesarios
RUN mkdir -p logs

# Exponer puerto
EXPOSE 8008

# Iniciar aplicación
CMD ["uvicorn", "src.api.api:app", "--host", "0.0.0.0", "--port", "8008"]
