from fastapi import FastAPI
from src.api.api import app as inner_app

app = FastAPI()

# Monta la app actual debajo de /api
app.mount("/api", inner_app)
