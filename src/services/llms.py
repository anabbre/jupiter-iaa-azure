from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

from src.config import SETTINGS

load_dotenv()


llm = ChatOpenAI(
    model=SETTINGS.LLM_MODEL_NAME,
    temperature=SETTINGS.LLM_TEMPERATURE,
    max_retries=SETTINGS.LLM_MAX_RETRIES
)
