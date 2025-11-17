# from langchain_google_genai import GoogleGenerativeAIEmbeddings
# from langchain_openai import OpenAIEmbeddings
# from langchain_huggingface import HuggingFaceEmbeddings
# from dotenv import load_dotenv
# load_dotenv()
# from src.config import SETTINGS
# import os



# embeddings_model = OpenAIEmbeddings(
#     model=SETTINGS.EMBEDDINGS_MODEL_NAME ,
#     api_key=os.getenv("OPENAI_API_KEY")
# )

# # embeddings_model = HuggingFaceEmbeddings(
# #     model_name="intfloat/multilingual-e5-small"
# # )

from dotenv import load_dotenv
from src.config import SETTINGS
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()

embeddings_model = HuggingFaceEmbeddings(
    model_name=SETTINGS.EMBEDDINGS_MODEL_NAME or "intfloat/multilingual-e5-small",
    encode_kwargs={"normalize_embeddings": True},
)
