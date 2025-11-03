FROM python:3.12-slim

# Establecer directorio de trabajo
WORKDIR /app

# Variables de entorno
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV GRADIO_SERVER_NAME=0.0.0.0
ENV GRADIO_SERVER_PORT=7860

# Copiar archivos de dependencias
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY src/ ./src/
COPY config/ ./config/

# Crear directorios necesarios
RUN mkdir -p logs

# Exponer puerto
EXPOSE 7860

# Iniciar aplicación
CMD ["gradio", "src/ui/ui.py"]
