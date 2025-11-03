from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv
load_dotenv()
from src.config import SETTINGS



embeddings_model = OpenAIEmbeddings(
    model=SETTINGS.EMBEDDINGS_MODEL_NAME,
)



