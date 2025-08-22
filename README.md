# Generador automático de infraestructura Azure con IA

## Flujo de uso y comportamiento de la aplicación

La aplicación cuenta con dos pestañas principales:

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

### 2. Entrenamiento

- Permite subir archivos de entrenamiento para mejorar el asistente.
- Se muestran los documentos ya subidos al modelo, agrupados por nombre único.
- El usuario puede subir archivos de tipo `.tf`, `.txt`, `.md`, `.pdf`, `.docx`, `.html`.
- Al subir archivos:
	- Si el nombre del archivo ya existe y el contenido es igual, se sobreescribe el archivo existente.
	- Si el nombre del archivo ya existe pero el contenido es diferente, el nuevo archivo se guarda con un sufijo incremental (`nombre_1`, `nombre_2`, etc.).
	- Si el archivo no existe, se guarda normalmente.
- El sistema muestra el progreso de subida y procesamiento de archivos.
- Al finalizar, indica si los archivos se añadieron correctamente o si hubo algún error.

#### Casuísticas:
- Si se intenta subir un archivo ya existente (mismo nombre y contenido), se sobreescribe.
- Si se sube un archivo con el mismo nombre pero diferente contenido, se guarda con sufijo incremental.
- Si el archivo es de tipo no soportado, se muestra una advertencia y no se procesa.
- Si no hay archivos válidos, se muestra una advertencia.

## Resumen del proceso

1. El usuario puede consultar al asistente en la pestaña "Chatbot" y ver las fuentes utilizadas en las respuestas.
2. En la pestaña "Entrenamiento", puede subir nuevos archivos para mejorar el modelo, siguiendo la lógica de comprobación de duplicados y contenido.
3. El sistema gestiona los archivos subidos, asegurando que no se pierda información relevante y evitando duplicados innecesarios.


## Pasos para ejecutar la aplicación

1. **Clona el repositorio**  
	```bash
	git clone https://github.com/anabbre/jupiter-iaa-azure.git
	```

2. **Instala las dependencias**  
	Asegúrate de tener Python 3.8+ y pip instalado.  
	```bash
	pip install -r requirements.txt
	```

3. **Configura las variables de entorno**  
	Crea un archivo `.env` en la raíz del proyecto con tus credenciales de Azure y otras configuraciones necesarias.  
	Ejemplo:
	```
	OPENAI_API_KEY==tu_openai_apikey
	PINECONE_API_KEY==tu_pinecode_apikey
	```

4. **Ejecuta la aplicación**  
	```bash
	streamlit run app.py
	```

5. **Accede a la interfaz web**  
	Abre tu navegador y visita la Local URL que te muestra y ya puedes interactuar con el chatbot.

