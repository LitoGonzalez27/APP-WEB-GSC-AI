# scripts/

Scripts que no forman parte de la app en marcha. Estaban sueltos en la raíz y se movieron aquí el 2026-09-27 (fase 2 de la limpieza) sin cambiar su código. En la raíz solo queda lo que usa la app (lo alcanzable desde `app.py` y desde `railway.json`).

| Carpeta | Qué hay |
|---|---|
| `migrations/` | Migraciones de BD ya aplicadas (`migrate_*`, `add_*`, `create_*`, `*.sql`). Se conservan como historial del esquema y para montar entornos nuevos. |
| `maintenance/` | Reparaciones y utilidades puntuales: `repair_collapsed_aio`, `repair_goto_history`, `rerun_single_project`, semilla de demo, descubrimiento de modelos semanal, `llm_monitoring_lock_cleanup.sql`. |
| `diagnostics/` | Diagnósticos de un solo uso (`check_*`, `diagnose_*`, `verify_*`, OAuth, webhooks). Algunos son antiguos: leer antes de ejecutar. |
| `manual_checks/` | Los antiguos `test_*.py` de la raíz. No son tests de pytest: son scripts que hablan con la BD de staging o con APIs reales (algunos con coste). |

Herramientas de la limpieza, en la raíz de `scripts/`:

- `run_tests_docker.sh`: suite de tests en Docker (ver `tests/README.md`).
- `check.sh`: todas las comprobaciones antes de subir un cambio.
- `check_prod_deps.py`: comprueba que `requirements.txt` cubre los imports del código vivo.

## Cómo se ejecutan

Siempre desde `search_console_webapp/` y como módulo, para que encuentren `database`, `auth`, etc.:

```bash
python3 -m scripts.migrations.migrate_llm_search_p3
railway run --service Clicandseo python3 -m scripts.maintenance.repair_collapsed_aio mark --apply
```

Un `python3 scripts/migrations/x.py` directo falla con `ModuleNotFoundError: database`, porque Python busca los imports en la carpeta del script.

## Borrados en la misma limpieza (siguen en el historial de git)

`admin_billing_routes.py` (nunca se registraba), `cron_worker.py` (duplicaba el cron de Bun), `setup.py` y `setup_testing_environment.py` (configuración antigua), `run_all_tests.py` y `run_full_staging_tests.py` (sustituidos por `run_tests_docker.sh`; el segundo llamaba a scripts que ya no existían), `check_manual_ai_system.py` (importaba un módulo inexistente), `postinstall.sh` (no lo ejecutaba nada), `requirements_llm_monitoring.txt` (duplicado sin uso) y `FIX_GRIDJS_ERROR.md` (nota de un bug cerrado).

Para recuperar cualquiera: `git log --all -- <ruta>` y `git show <commit>^:<ruta>`.
