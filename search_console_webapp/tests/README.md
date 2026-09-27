# Tests

## Cómo ejecutarlos

```bash
scripts/run_tests_docker.sh            # suite completa
scripts/run_tests_docker.sh -q tests/test_zz_route_map.py   # un fichero
```

El script lo monta todo en Docker (Colima vale):

- Postgres 16 desechable, en RAM, con el esquema de `tests/db/schema.sql`. Se borra al terminar.
- Red interna de Docker sin salida a internet.
- Imagen `python:3.12-slim` con las versiones exactas de `requirements.txt`.

No hace falta ninguna credencial. La app usa variables **ficticias** de `tests/docker/test.env`.

## Barreras (tests/conftest.py)

- **Base de datos**: si `DATABASE_URL` apunta a algo que no sea local o el Postgres de Docker, la suite se detiene sin ejecutar nada. Varios tests escriben y borran filas. Los tests de integración pensados para staging (`LLM_SETS_IT_PROJECT_ID`) solo corren si se exporta `ALLOW_REMOTE_DB_TESTS=1` a propósito.
- **Red**: las conexiones salientes de Python se bloquean salvo loopback, así que ningún test puede llamar a OpenAI, Anthropic, Gemini, Perplexity, SerpAPI, Stripe o Brevo. `ALLOW_NETWORK_TESTS=1` lo desactiva.
- **Fallos conocidos**: `tests/known_failures.txt` lista los 30 tests que ya fallaban antes de la limpieza de septiembre de 2026 (desfasados respecto al código, no fallos de la app). Salen como `xfailed`; cualquier fallo nuevo sale como `FAILED`.

## Fotos (snapshots)

- `test_zz_route_map.py`: todas las rutas de la app con endpoint y métodos. Detecta blueprints que dejan de registrarse en silencio.
- `test_zz_route_auth_matrix.py`: qué responde cada ruta a un visitante, un usuario gratuito, uno de pago y un admin. Detecta cualquier ruta que se abra o se cierre.

Si un cambio de rutas o permisos es intencionado, se regeneran y se revisa el diff en el commit:

```bash
UPDATE_SNAPSHOTS=1 scripts/run_tests_docker.sh tests/test_zz_route_map.py tests/test_zz_route_auth_matrix.py
```

## Esquema de la base de pruebas

`tests/db/schema.sql` es un `pg_dump --schema-only --no-owner --no-privileges` de staging (solo estructura, sin datos). Si una migración añade tablas o columnas, se vuelve a sacar y se commitea junto con la migración.
