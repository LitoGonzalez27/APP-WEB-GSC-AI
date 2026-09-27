# Imagen para ejecutar la suite de tests en local o en CI, aislada del Mac.
# Solo instala dependencias; el código se monta como volumen al ejecutar.
FROM python:3.12-slim-bookworm
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /deps
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
# Herramientas de comprobación: solo en esta imagen de tests, no en producción
RUN pip install --no-cache-dir ruff==0.6.9 pip-audit==2.7.3
WORKDIR /app/search_console_webapp
