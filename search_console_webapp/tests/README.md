# Tests

## Cómo ejecutarlos

```bash
scripts/check.sh                       # todo: compilación, ruff, tests, selftest del scanner y pip-audit
scripts/run_tests_docker.sh            # solo la suite
scripts/run_tests_docker.sh -q tests/test_zz_route_map.py   # un fichero
```

Varias ejecuciones a la vez no se pisan: cada una crea su red y su Postgres (`TEST_RUN_ID` fija el nombre si hace falta).

El script lo monta todo en Docker (Colima vale):

- Postgres 16 desechable, en RAM, con el esquema de `tests/db/schema.sql`. Se borra al terminar.
- Red interna de Docker sin salida a internet.
- Imagen `python:3.12-slim` con las versiones exactas de `requirements.txt`.

No hace falta ninguna credencial. La app usa variables **ficticias** de `tests/docker/test.env`.

Tests de JavaScript (funciones puras del frontend, sin dependencias, Node 18+):

```bash
node --test tests/js/*.test.cjs
```

## CI

`.github/workflows/tests.yml` (raíz del repo) ejecuta en cada PR y push a `staging` y `main` los tests de JavaScript y `scripts/run_tests_docker.sh -q -rs`: el mismo comando que en local, con el Postgres desechable y la red interna sin salida. Sin secretos ni despliegues; permisos de solo lectura.

## Clasificación (sep-2026)

| Tipo | Ficheros | Qué necesitan |
|---|---:|---|
| Aislados | 16 | Nada: ni BD ni red (lógica pura, mocks de proveedores). |
| Integración con Postgres desechable | 25 | La base de Docker del script. Incluye las fotos de rutas y permisos y los de caracterización. |
| Dependientes de staging | 2 | `test_llm_prompt_sets_integration.py` y parte de `test_llm_prompt_readd_regression.py`: solo con `LLM_SETS_IT_PROJECT_ID` y `ALLOW_REMOTE_DB_TESTS=1`; si no, se saltan (42 tests). |
| Scripts manuales | 14 | `scripts/manual_checks/`: comprobaciones contra servicios reales; pytest no los recoge (`testpaths = tests`). |

Línea base (29-sep-2026, rama `staging`): **1163 passed, 49 skipped, 30 xfailed**. Los 49 saltados: 42 dependientes de staging y 7 de `test_llm_monitoring_e2e.py`, que se saltan si la base no tiene usuarios. Los 30 xfailed son los fallos previos de `known_failures.txt`. No usar `-p no:logging`: desactiva el fixture `caplog` y 4 tests dan error.

Varios tests antiguos comprueban texto del código (`read_text`/`getsource`); las garantías nuevas se prueban por comportamiento (respuestas, estado de la BD, sesión, conexiones devueltas).

## Fiabilidad: `GET /admin/users/<id>/billing-details`

`test_fiabilidad_billing_details.py` prueba el flujo real (decorador + ruta + consultas) contra la base desechable, con fallos provocados de verdad: consulta cancelada por `statement_timeout` (transitorio), tabla inexistente (programación) y pool agotado. Cubre 200/404/503/500, sesión conservada ante fallos técnicos, métricas no disponibles marcadas como tales, cursores y conexiones devueltos siempre y la clasificación de errores transitorios por SQLSTATE (`is_transient_db_error`). Contrato en `CLAUDE-base-de-datos.md` §2.

`test_fiabilidad_sesion.py`: el mismo contrato en los decoradores de sesión (`auth_required`, keepalive) y en `/auth/status`: un fallo de la base de datos no cierra la sesión; un usuario borrado sí. `tests/js/session-status.test.cjs` prueba que el gestor de sesión del frontend no la cierra ante un 5xx.

## Barreras (tests/conftest.py)

- **Base de datos**: si `DATABASE_URL` apunta a algo que no sea local o el Postgres de Docker, la suite se detiene sin ejecutar nada. Varios tests escriben y borran filas. Los tests de integración pensados para staging (`LLM_SETS_IT_PROJECT_ID`) solo corren si se exporta `ALLOW_REMOTE_DB_TESTS=1` a propósito.
- **Red**: las conexiones salientes de Python se bloquean salvo loopback, así que ningún test puede llamar a OpenAI, Anthropic, Gemini, Perplexity, SerpAPI, Stripe o Brevo. `ALLOW_NETWORK_TESTS=1` lo desactiva.
- **Fallos conocidos**: `tests/known_failures.txt` lista los 30 tests que ya fallaban antes de la limpieza de septiembre de 2026 (desfasados respecto al código, no fallos de la app). Salen como `xfailed`; cualquier fallo nuevo sale como `FAILED`.

## Tests de caracterización

Fijan el comportamiento ACTUAL (con sus defectos) de las partes críticas, para que una refactorización no lo cambie sin que nadie se entere. Los defectos encontrados están marcados en el propio test con `# COMPORTAMIENTO ACTUAL (posible defecto)`: arreglarlos es una decisión aparte y, cuando se haga, se cambia el test en el mismo commit.

- `test_char_stripe_webhooks.py`: webhooks de Stripe (firma, checkout, suscripción, facturas, idempotencia).
- `test_char_quotas.py`: cuotas, consumo, fechas de reset, unidades LLM y límites por proyecto y Enterprise.
- `test_char_quota_reset_and_crons.py`: reset diario de cuota y endpoints de cron (token, locks, watchdog).
- `test_fase0_seguridad.py`: los arreglos de seguridad de la fase 0.

## Fotos (snapshots)

- `test_zz_route_map.py`: todas las rutas de la app con endpoint y métodos. Detecta blueprints que dejan de registrarse en silencio.
- `test_zz_route_auth_matrix.py`: qué responde cada ruta a un visitante, un usuario gratuito, uno de pago y un admin. Detecta cualquier ruta que se abra o se cierre.

Si un cambio de rutas o permisos es intencionado, se regeneran y se revisa el diff en el commit:

```bash
UPDATE_SNAPSHOTS=1 scripts/run_tests_docker.sh tests/test_zz_route_map.py tests/test_zz_route_auth_matrix.py
```

## Esquema de la base de pruebas

`tests/db/schema.sql` es un `pg_dump --schema-only --no-owner --no-privileges` de staging (solo estructura, sin datos). Si una migración añade tablas o columnas, se vuelve a sacar y se commitea junto con la migración.
