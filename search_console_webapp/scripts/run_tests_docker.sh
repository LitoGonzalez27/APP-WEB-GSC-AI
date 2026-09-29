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
# Cada ejecución tiene su propia red y su propio Postgres, así que se pueden
# lanzar varias a la vez. El alias de red es siempre clicandseo-test-db, que es
# el host que tests/conftest.py acepta como base desechable.
RUN_ID="${TEST_RUN_ID:-$$}"
NET="clicandseo-test-$RUN_ID"
DB="clicandseo-test-db-$RUN_ID"
DB_ALIAS=clicandseo-test-db
IMG=clicandseo-tests:py312

# Contexto mínimo (solo requirements y Dockerfile): no se añade .dockerignore al
# repo para no alterar el contexto de build de Railway.
# En macOS (bsdtar) se excluyen atributos extendidos y metadatos de Apple, que
# rompen el build; el tar de GNU (Linux, CI) no tiene esas opciones ni los necesita.
TAR_OPTS=()
if tar --version 2>/dev/null | grep -qi bsdtar; then
  TAR_OPTS=(--no-xattrs --no-mac-metadata)
fi
COPYFILE_DISABLE=1 tar ${TAR_OPTS[@]+"${TAR_OPTS[@]}"} -C "$APP_DIR" -cf - requirements.txt requirements-dev.txt tests/docker/Dockerfile \
  | docker build -q -t "$IMG" -f tests/docker/Dockerfile - >/dev/null

cleanup() {
  docker rm -f "$DB" >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup
docker network create --internal "$NET" >/dev/null
docker run -d --name "$DB" --network "$NET" --network-alias "$DB_ALIAS" \
  -e POSTGRES_PASSWORD=test -e POSTGRES_DB=clicandseo_test \
  --tmpfs /var/lib/postgresql/data postgres:16-alpine \
  postgres -c fsync=off -c synchronous_commit=off -c full_page_writes=off \
           -c wal_level=minimal -c max_wal_senders=0 -c max_wal_size=64MB \
           -c checkpoint_timeout=30s >/dev/null
# Opciones solo para esta base desechable en RAM: la matriz de permisos la vacía
# cientos de veces y, con los valores por defecto, el WAL llenaba el tmpfs.

# Por TCP: durante la inicialización Postgres arranca un servidor temporal solo
# por socket y lo reinicia; pg_isready sin -h lo daba por listo antes de tiempo.
for _ in $(seq 1 60); do
  docker exec "$DB" pg_isready -h 127.0.0.1 -U postgres -q && break
  sleep 1
done
docker exec -i "$DB" psql -U postgres -d clicandseo_test -v ON_ERROR_STOP=1 -q \
  < "$APP_DIR/tests/db/schema.sql" >/dev/null

docker run --rm --network "$NET" \
  -e DATABASE_URL="postgresql://postgres:test@$DB_ALIAS:5432/clicandseo_test" \
  -e UPDATE_SNAPSHOTS="${UPDATE_SNAPSHOTS:-}" \
  -v "$REPO_DIR":/app -w /app/search_console_webapp \
  "$IMG" python -m pytest -p no:cacheprovider "$@"
