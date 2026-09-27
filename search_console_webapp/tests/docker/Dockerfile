# Imagen para ejecutar la suite de tests en local o en CI, aislada del Mac.
# Solo instala dependencias; el código se monta como volumen al ejecutar.
FROM python:3.12-slim-bookworm
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
WORKDIR /app/search_console_webapp
