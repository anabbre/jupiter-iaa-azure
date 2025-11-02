from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv
load_dotenv()

# modelo de openai embeddings
MODEL_NAME = "text-embedding-3-small"

embeddings_model_langchain = OpenAIEmbeddings(model=MODEL_NAME)



