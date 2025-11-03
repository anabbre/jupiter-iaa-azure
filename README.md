
- Docker compose up --build

Con el volumen creado ejecutamos "create_book_index.py" para llenar la DB.

Ahí deberíamos poder acceder a la UI y que responda citando los chunks consultados vía API.

### CI: Build automático de la imagen Docker del API

Este repositorio incluye un workflow de GitHub Actions (`.github/workflows/docker-api.yml`) que:

- Construye la imagen Docker del API cuando hay cambios relevantes (código, Dockerfile, etc.).
- Publica la imagen en GitHub Container Registry (GHCR) al hacer push en `main` (tags: `latest` y `sha`).

**Uso local**

```bash
cp .env.example .env   # rellena tus claves
docker build -t jupiter-api:test -f src/api/Dockerfile .
docker run --env-file .env -p 8008:8008 jupiter-api:test

