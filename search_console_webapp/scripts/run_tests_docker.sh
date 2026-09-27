#!/usr/bin/env bash
# Ejecuta la suite de tests en Docker, aislada de todo lo real:
#   - Postgres 16 desechable (en RAM) con el esquema de tests/db/schema.sql
#   - red interna de Docker sin salida a internet
#   - variables ficticias de tests/docker/test.env (las carga el propio test que las necesita)
# Uso:  scripts/run_tests_docker.sh [argumentos de pytest]
#       UPDATE_SNAPSHOTS=1 scripts/run_tests_docker.sh tests/test_zz_*.py   # regenerar fotos
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"   # search_console_webapp
REPO_DIR="$(cd "$APP_DIR/.." && pwd)"
NET=clicandseo-test
DB=clicandseo-test-db
IMG=clicandseo-tests:py312

# Contexto mínimo (solo requirements y Dockerfile): no se añade .dockerignore al
# repo para no alterar el contexto de build de Railway.
COPYFILE_DISABLE=1 tar --no-xattrs --no-mac-metadata -C "$APP_DIR" -cf - requirements.txt tests/docker/Dockerfile \
  | docker build -q -t "$IMG" -f tests/docker/Dockerfile - >/dev/null

docker network inspect "$NET" >/dev/null 2>&1 || docker network create --internal "$NET" >/dev/null
docker rm -f "$DB" >/dev/null 2>&1 || true
docker run -d --name "$DB" --network "$NET" \
  -e POSTGRES_PASSWORD=test -e POSTGRES_DB=clicandseo_test \
  --tmpfs /var/lib/postgresql/data postgres:16-alpine >/dev/null
trap 'docker rm -f "$DB" >/dev/null 2>&1 || true' EXIT

for _ in $(seq 1 60); do
  docker exec "$DB" pg_isready -U postgres -q && break
  sleep 1
done
docker exec -i "$DB" psql -U postgres -d clicandseo_test -v ON_ERROR_STOP=1 -q \
  < "$APP_DIR/tests/db/schema.sql" >/dev/null

docker run --rm --network "$NET" \
  -e DATABASE_URL="postgresql://postgres:test@$DB:5432/clicandseo_test" \
  -e UPDATE_SNAPSHOTS="${UPDATE_SNAPSHOTS:-}" \
  -v "$REPO_DIR":/app -w /app/search_console_webapp \
  "$IMG" python -m pytest -p no:cacheprovider "$@"
