#!/usr/bin/env bash
# Comprobaciones antes de subir un cambio. Todo corre en Docker; nada toca
# bases de datos, APIs ni claves reales.
#   1. Compilación de todo el código Python.
#   2. ruff solo con errores reales: sintaxis y nombres no definidos.
#   3. Suite de tests (scripts/run_tests_docker.sh: Postgres desechable, sin red).
#   4. Selftest del Agent-Ready Scanner (necesita DNS: resuelve dominios públicos).
#   5. Dependencias de producción: en una imagen con SOLO requirements.txt se
#      importan todos los módulos externos que usa el código vivo.
#   6. pip-audit de requirements.txt (necesita red: consulta la base pública de
#      vulnerabilidades). Informativo: no hace fallar el script.
# Uso: scripts/check.sh
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REPO_DIR="$(cd "$APP_DIR/.." && pwd)"
IMG=clicandseo-tests:py312

COPYFILE_DISABLE=1 tar --no-xattrs --no-mac-metadata -C "$APP_DIR" -cf - requirements.txt requirements-dev.txt tests/docker/Dockerfile \
  | docker build -q -t "$IMG" -f tests/docker/Dockerfile - >/dev/null

run() {  # run <red> <comando...>
  local net="$1"; shift
  docker run --rm --network "$net" -e PYTHONPYCACHEPREFIX=/tmp/pyc \
    -v "$REPO_DIR":/app -w /app/search_console_webapp "$IMG" "$@"
}

echo "== 1. compileall"
run none python -m compileall -q -x '(worktrees|venv|__pycache__)' .

echo "== 2. ruff (E9, F63, F7, F82)"
run none ruff check --no-cache --select E9,F63,F7,F82 --exclude .claude --output-format concise .

echo "== 3. tests"
"$APP_DIR/scripts/run_tests_docker.sh" -q -p no:warnings -o log_cli=false

echo "== 4. selftest del Agent-Ready Scanner"
run bridge python -m agent_scanner.selftest | tail -1

echo "== 5. dependencias de producción (imagen solo con requirements.txt)"
printf 'FROM python:3.12-slim-bookworm\nENV PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1\nCOPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt\n' > /tmp/clicandseo-prod.Dockerfile
COPYFILE_DISABLE=1 tar --no-xattrs --no-mac-metadata -C "$APP_DIR" -cf - requirements.txt -C /tmp clicandseo-prod.Dockerfile \
  | docker build -q -t clicandseo-prodreq:check -f clicandseo-prod.Dockerfile - >/dev/null
docker run --rm --network none -e PYTHONPYCACHEPREFIX=/tmp/pyc -v "$REPO_DIR":/app -w /app/search_console_webapp \
  clicandseo-prodreq:check python scripts/check_prod_deps.py

echo "== 6. pip-audit (informativo)"
run bridge pip-audit -r requirements.txt --progress-spinner off --desc off || true

echo "== OK"
