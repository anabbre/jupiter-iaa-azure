from dotenv import load_dotenv
from config.config import SETTINGS
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()

embeddings_model = HuggingFaceEmbeddings(
    model_name=SETTINGS.EMBEDDINGS_MODEL_NAME or "intfloat/multilingual-e5-small",
    encode_kwargs={"normalize_embeddings": True},
)
