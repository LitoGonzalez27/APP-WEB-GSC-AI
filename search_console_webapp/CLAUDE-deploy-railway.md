# CLAUDE-deploy-railway.md — Deploy en Railway

> Manual del **Deploy** del proyecto en Railway: servicios, archivos de configuración, env vars, builds, Bun functions, operaciones manuales y deuda técnica.
>
> Última actualización: 2026-05-08.
>
> Manuales relacionados: `CLAUDE-stripe-cuotas-crons.md`, `CLAUDE-base-de-datos.md`, `CLAUDE-llm-monitoring.md`. Índice maestro: `CLAUDE-INDEX.md`.

---

## Índice

1. [Visión general en 5 minutos](#1-visión-general-en-5-minutos)
2. [Servicios en Railway](#2-servicios-en-railway)
3. [Archivos de configuración](#3-archivos-de-configuración)
4. [Bun functions (los archivos JS)](#4-bun-functions-los-archivos-js)
5. [Variables de entorno](#5-variables-de-entorno)
6. [Builds y deploy](#6-builds-y-deploy)
7. [Verificación post-deploy](#7-verificación-post-deploy)
8. [Logs y monitoreo](#8-logs-y-monitoreo)
9. [Acceso a producción](#9-acceso-a-producción)
10. [MCP de Railway](#10-mcp-de-railway)
11. [Errores históricos y deuda técnica](#11-errores-históricos-y-deuda-técnica)
12. [Operaciones manuales — chuleta de comandos](#12-operaciones-manuales--chuleta-de-comandos)

---

## 1. Visión general en 5 minutos

- **La app está hospedada en Railway**.
- **URLs públicas**:
  - Técnica Railway: `https://clicandseo.up.railway.app`.
  - Dominio custom: `https://app.clicandseo.com`.
  - Ambas aparecen como hardcoded fallback en distintos sitios — la mezcla es deuda técnica conocida.
- **Separación staging / producción**: vía env var `RAILWAY_ENVIRONMENT` (`staging` | `production`). En `app.py:101-104` se calcula `is_production` / `is_staging` / `is_development`. Activa ProxyFix, security headers y HSTS solo en prod/staging.
- **Bases de datos separadas**:
  - Staging: `caboose.proxy.rlwy.net:13631`.
  - Producción: `switchyard.proxy.rlwy.net:18167`.
  - URLs hardcoded en `migrate_llm_staging_to_production.py:11-12` (riesgo).
- **Deploy automático por push**: branches `main` (producción) y `staging` (staging). No hay CI/CD pipeline (no hay `.github/workflows`).
- **Builder**: nixpacks (no Dockerfile). Procfile define `web` y `cron` (este último probablemente inactivo en producción — el cron real lo hacen los Bun services).

**Reglas de oro:**

1. **Los crons reales son servicios Bun, NO el array `crons` de `railway.json`** (que está silenciosamente ignorado en este proyecto).
2. **Las migraciones de BD NO se ejecutan automáticamente** en cada deploy (a propósito). Se lanzan manualmente con `railway run --service Clicandseo python3 migrate_xxx.py`.
3. **Las env vars secretas** se gestionan en Railway dashboard (Settings → Variables → Raw Editor), no en el repo.
4. **`RAILWAY_STAGING_VARIABLES.txt` está commited al repo con secretos** (vulnerabilidad — debería rotarse).

---

## 2. Servicios en Railway

8 servicios en producción (basado en código + docs):

| Servicio | Tipo | Schedule | Endpoint que llama | Confirmado |
|---|---|---|---|---|
| **App principal Flask** ("Clicandseo") | nixpacks Python | always-on | n/a | ✅ |
| **Postgres** ("BD - Brand Monitor") | Railway Postgres plugin | n/a | n/a | ✅ (referenciada vía `${{BD - Brand Monitor.DATABASE_URL}}`) |
| `function-bun-LLM-Monitoring` | Bun | diario | `/api/llm-monitoring/cron/daily-analysis?async=1` | ✅ |
| `function-bun-AI-Mode` | Bun | diario | `/ai-mode-projects/api/cron/daily-analysis?async=1` | ✅ |
| `function-bun-Quota-Reset` (o `Quota-reset`) | Bun | `30 1 * * *` | `/api/cron/quota-reset?async=1&triggered_by=bun_cron` | ✅ |
| `function-bun-Model-Discovery` | Bun | quincenal `0 9 1,15 * *` | `/api/llm-monitoring/cron/model-discovery` | ✅ |
| `function-bun-Manual-AI` | Bun | — | — | ❌ **NO EXISTE** |

> ⚠️ **Deuda técnica conocida**: no hay Bun service para Manual AI. El cron Manual AI hoy depende de la confluencia ambigua entre Procfile worker, `railway.json crons` (que no se ejecuta) y el endpoint HTTP. Acción recomendada: crear `manual_ai_cron_function.js` copiando el patrón de `quota_reset_cron_function.js`.

> ⚠️ **Inconsistencia de nomenclatura**: `function-bun-Quota-Reset` vs `function-bun-Quota-reset` (mayúsculas distintas). Mantener una sola para evitar duplicados accidentales.

**No hay otros servicios** detectables desde código (no Redis, no workers Celery, no Sentry). Aunque `redis==5.1.1` está en `requirements.txt`, `RATE_LIMIT_STORAGE_URL` default es `memory://` (Redis no está en uso — deuda).

---

## 3. Archivos de configuración

### `railway.json`

`/Users/carlosgonzalez/Desktop/app/APP-WEB-GSC-AI/search_console_webapp/railway.json`. Contiene:

- Array **`crons`** con 6 entradas:
  - `daily_analysis_cron.py @ 02:00` (Manual AI).
  - `daily_ai_mode_cron.py @ 03:00` (AI Mode).
  - `BREVO_CONTACT_LIST_ID=8 sync_users_to_brevo.py @ 03:15`.
  - `daily_llm_monitoring_cron.py @ 04:00` (LLM Monitoring).
  - `weekly_model_check_cron.py @ Sun 00:00`.
  - `daily_quota_reset_cron.py @ 01:30`.
- Array **`functions`**: una entrada (`llm-monitoring-cron`, runtime `bun`, schedule `0 5 * * *`).

> 🚨 **CRÍTICO**: el array `crons` **NO se ejecuta en este proyecto**. Documentado en `CLAUDE-stripe-cuotas-crons.md` y `cron_routes.py:8-15`. Confirmado en `quota_reset_cron_function.js:9-10`: *"Railway silently did not run it for ~50 days"*. Esto causó el caso Driza UEMC (53 días sin reset).

**No hay builders explícitos** en `railway.json`; el build se rige por `nixpacks.toml`.

### `Procfile`

```
web: python3 app.py
cron: python3 daily_analysis_cron.py
```

- Cabecera del Procfile (10 líneas de comentarios) explica que el step `release:` que antes corría `playwright install-deps` se eliminó porque rompía cada deploy. Se movió a `nixpacks.toml`.
- **Estado real**: solo `web` está garantizado. El proceso `cron` puede estar inactivo (el cron real corre por Bun functions).
- **Las migraciones NO se ejecutan en cada deploy** (a propósito). Filosofía documentada: *"DB migrations should be run intentionally"*.

### `nixpacks.toml`

Tres fases:

```toml
[phases.setup]
nixPkgs = ["python3", "gcc"]
aptPkgs = [
  # 22 paquetes apt para Playwright Chromium:
  "libnss3", "libatk1.0-0t64", "libcups2t64", "libgbm1",
  "fonts-noto-color-emoji", ...
]

[phases.install]
cmds = [
  "python3 -m venv /opt/venv",
  "/opt/venv/bin/pip install -r requirements.txt",
  "/opt/venv/bin/python3 -m playwright install chromium"
]

[phases.start]
cmd = "python3 app.py"
```

- Los `aptPkgs` están en **setup phase** para que se cacheen y no fallen por "mirror sync in progress".
- `playwright install chromium` sin `--with-deps` (los apt están en setup).

### `postinstall.sh`

```bash
playwright install chromium
python3 fix_quota_events_table.py || echo "non-critical"
```

> ⚠️ **No queda claro si Railway lo ejecuta**. Probablemente vestigio; la lógica equivalente está en `nixpacks.toml`.

### `requirements.txt`

Sin configuración Railway-específica. Stack:
- Flask 3.0.3.
- psycopg2-binary 2.9.9.
- stripe 12.4.0.
- playwright 1.48.0.
- openai≥1.56,<2, anthropic 0.39.0, google-generativeai 0.8.5.
- redis 5.1.1 (no usado).

> Hay un `requirements_llm_monitoring.txt` separado **pero no usado** por nixpacks (que solo instala `requirements.txt`). Deuda.

### Otros archivos

- **`railway`** (sin extensión, 9 bytes con contenido literal `Not Found`) — **basura, borrar**.
- **`package.json`, `bun.lockb`** — **no existen** en la raíz. Los Bun functions son archivos JS sueltos sin dependencias externas.

---

## 4. Bun functions (los archivos JS)

Todos siguen el mismo patrón:
```js
fetch(endpoint, {
  method: 'POST',
  headers: { Authorization: 'Bearer ' + CRON_TOKEN },
  signal: AbortSignal.timeout(60000)
})
```

Si falla, llaman a `/api/llm-monitoring/cron/alert` con payload `{notify_email, job_name, status, message, endpoint, response_status, response_body, run_at}`.

### `llm_monitoring_cron_function.js` (82 líneas)

- Endpoint: `POST {APP_URL}/api/llm-monitoring/cron/daily-analysis?async=1`.
- Default `APP_URL = https://clicandseo.up.railway.app`.
- `notifyEmail` resuelto desde `CRON_ALERT_EMAIL` || `MODEL_DISCOVERY_EMAIL` || `info@soycarlosgonzalez.com` (hardcoded fallback).

### `ai_mode_cron_function.js` (82 líneas)

- Mismo patrón. Endpoint: `/ai-mode-projects/api/cron/daily-analysis?async=1`.
- Reusa `/api/llm-monitoring/cron/alert` para alertas (no tiene endpoint propio).

### `quota_reset_cron_function.js` (52 líneas)

- Endpoint: `/api/cron/quota-reset?async=1&triggered_by=bun_cron`.
- **Default `APP_URL = https://app.clicandseo.com`** (¡ojo! distinto al resto que usan `clicandseo.up.railway.app`).
- **No envía alerta por email** desde el Bun (el endpoint Flask se encarga vía `_send_stuck_quota_alert` post-reset).
- Comentario: *"function follows the same proven pattern"* (ver `cron_routes.py:11-14` para el porqué).

### `llm_model_discovery_cron_function.js` (117 líneas)

- Endpoint: `/api/llm-monitoring/cron/model-discovery?notify_email=...&auto_update=...`.
- Acepta `AUTO_UPDATE_MODELS` (default `false`), `MODEL_DISCOVERY_EMAIL`, `CRON_ALERT_EMAIL`.
- Imprime resumen de modelos nuevos descubiertos. Si falla → alert vía `/api/llm-monitoring/cron/alert`.

### `manual_ai_cron_function.js` — **NO EXISTE**

Confirmado con `find`. Deuda técnica documentada en `CLAUDE-manual-ai.md`.

> Existe `cron_worker.py` (37 líneas, usa la lib `schedule` de Python para llamar a `/manual-ai/api/cron/daily-analysis` cada día a las 02:00). **No queda claro si está deployed como worker en Railway**.

---

## 5. Variables de entorno

Lista exhaustiva extraída con `grep` sobre todos los `.py` + `RAILWAY_STAGING_VARIABLES.txt` + Bun functions.

### Críticas / obligatorias

| Variable | Para qué |
|---|---|
| `DATABASE_URL` | Postgres URL (Railway lo inyecta vía `${{BD - Brand Monitor.DATABASE_URL}}`). |
| `FLASK_SECRET_KEY` | Clave Flask para sesiones. **Default inseguro en código**. |
| `SECRET_KEY` | Referenciado pero rol no claro. |
| `RAILWAY_ENVIRONMENT` | `staging` | `production`. |
| `RAILWAY_ENVIRONMENT_NAME` | Alternativa. |
| `APP_ENV` | Fallback para nombre de entorno. |
| `PORT` | Railway lo inyecta automáticamente; default 5001. |
| `PUBLIC_BASE_URL` | `https://app.clicandseo.com` (default en `brevo_api_service.py:17`). |

### Stripe

`STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_WEBHOOK_SECRET_ALT`, `STRIPE_ENTERPRISE_PRODUCT_ID`, `STRIPE_PORTAL_CONFIGURATION_ID`, `STRIPE_TAX_ID_COLLECTION_REQUIRED`.

Precios:
- `PRICE_ID_BASIC`, `PRICE_ID_BASIC_MONTHLY`, `PRICE_ID_BASIC_ANNUAL`.
- `PRICE_ID_PREMIUM`, `PRICE_ID_PREMIUM_MONTHLY`, `PRICE_ID_PREMIUM_ANNUAL`.
- `PRICE_ID_BUSINESS_MONTHLY`, `PRICE_ID_BUSINESS_ANNUAL`.

Otros: `CUSTOMER_PORTAL_RETURN_URL`, `PRICING_PAGE_URL`, `BILLING_ENABLED`, `TRIAL_DAYS`.

### OAuth / Auth

`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `CLIENT_SECRETS_FILE`, `TOKEN_FILE`, `TOKEN_ENCRYPTION_KEY` (Fernet), `RECAPTCHA_SECRET_KEY`, `RECAPTCHA_SITE_KEY`, `RECAPTCHA_MIN_SCORE`, `SESSION_TIMEOUT_MINUTES`, `SESSION_WARNING_MINUTES`, `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_HTTPONLY`, `SESSION_COOKIE_SAMESITE`, `OAUTHLIB_INSECURE_TRANSPORT` (auto-set a `1` solo si NO `RAILWAY_ENVIRONMENT`).

### API keys de LLMs y SerpAPI

`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `GOOGLE_AI_API_KEY` (alternativa), `PERPLEXITY_API_KEY`, `JINA_API_KEY`, `SERPAPI_KEY` y `SERPAPI_API_KEY` (ambas formas), `SERPAPI_RETRY_ATTEMPTS`, `SERPAPI_RETRY_BACKOFF_SECONDS`, `SERP_CALL_CACHE_MAX`, `SERP_CALL_CACHE_TTL_SECONDS`.

### Cron

| Variable | Default |
|---|---|
| `CRON_TOKEN` (o `CRON_SECRET`) | (oblig.) |
| `APP_URL` | (Bun functions) |
| `CRON_ALERT_EMAIL` / `CRON_ALERTS_EMAIL` | `info@soycarlosgonzalez.com` |
| `CRON_ALERTS_ENABLED` | `true` |
| `CRON_ALERT_DURATION_MIN` | `90` |
| `CRON_ALERT_ERROR_RATE` | `0.20` |
| `CRON_ALERT_COST_MULTIPLIER` | `2.0` |
| `MODEL_DISCOVERY_EMAIL` | — |
| `AUTO_UPDATE_MODELS` | `false` |
| `NOTIFICATION_EMAIL` | — |

### Email / Brevo

`SMTP_SERVER` (default `smtp-relay.brevo.com`), `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `USE_STARTTLS`, `FROM_EMAIL` (default `info@clicandseo.com`), `FROM_NAME` (default `Clicandseo`), `BREVO_API_KEY`, `BREVO_CONTACT_LIST_ID`, `BREVO_FOLDER_ID`, `BREVO_TARGET_LIST_NAME`.

### Pool / DB

`DB_POOL_MIN` (default 2), `DB_POOL_MAX` (default 20), `DB_POOL_WAIT_SECONDS` (default 10), `DB_POOL_DISABLED`, `DB_RETRY_ATTEMPTS`, `DB_RETRY_BACKOFF_SECONDS`.

### Paralelismo / timeouts

| Variable | Default |
|---|---|
| `LLM_PROJECT_PARALLELISM` | `2` (prod = 3) |
| `LLM_PROJECT_TIMEOUT_MINUTES` | `30` |
| `LLM_HEALTHCHECK_DELAY_SECONDS` | `2` |
| `LLM_HEALTHCHECK_RETRIES` | `2` |
| `OPENAI_CONCURRENCY` | `2` |
| `PERPLEXITY_CONCURRENCY` | `4` |
| `AI_OVERVIEW_MAX_DURATION_SECONDS` | — |

### Cuotas

`ENFORCE_QUOTAS`, `QUOTA_GRACE_PERIOD_HOURS`, `QUOTA_SOFT_LIMIT_PCT`, `QUOTA_RESET_INTERVAL_DAYS`, `AIO_MODULE_ENABLED`.

### Rate limiting

`RATE_LIMIT_DEFAULT` (default `200 per hour;50 per minute`), `RATE_LIMIT_STORAGE_URL` (default `memory://`).

### Otras

`APP_TZ` (default `Europe/Madrid`), `ENCRYPTION_KEY` (en `RAILWAY_STAGING_VARIABLES.txt` pero **no encontré uso en `.py`** — posible legacy o duplicado de `TOKEN_ENCRYPTION_KEY`).

### ⚠️ Vulnerabilidad de seguridad

**`RAILWAY_STAGING_VARIABLES.txt` contiene secretos en plano** (Stripe test keys, Brevo SMTP password, BREVO_API_KEY, OPENAI/ANTHROPIC/GOOGLE/PERPLEXITY API keys, FLASK_SECRET_KEY, CRON_TOKEN, SERPAPI_KEY, ENCRYPTION_KEY, GOOGLE_CLIENT_SECRET).

**El archivo está commited al repo** (no en .gitignore). Si el repo se hace público o se filtra → todas esas keys deben rotarse.

---

## 6. Builds y deploy

### Mecanismo

- Railway está configurado con **auto-deploy por git push**.
- Branches:
  - `main` → producción.
  - `staging` → staging.
  - `codex/staging-keywords-updates` (rama feature).
  - Backups: `backup_main_before_merge_20260214`, `backup_staging_before_merge_20260214`.
- Recent commits muestran el flow: `Merge branch 'staging' into main`.

### Build process

**nixpacks** (no Dockerfile):

1. **Setup phase**: descarga apt packages para Playwright (cacheado).
2. **Install phase**: crea venv + pip install + Chromium.
3. **Start phase**: `python3 app.py`.

### Sin script de deploy automático

`/Users/carlosgonzalez/Desktop/app/APP-WEB-GSC-AI/search_console_webapp/` no tiene `deploy.sh` ni similar. Railway usa los hooks integrados de su plataforma.

### Migraciones de BD durante el deploy

> 🚨 **NO se ejecutan automáticamente** en cada deploy (a propósito).

- Comentario en `Procfile:8-9` deja claro: *"DB migrations should be run intentionally"*.
- Comando manual: `railway run --service Clicandseo python3 <migration_script>.py`.
- `postinstall.sh` ejecuta una sola migración (`fix_quota_events_table.py`) tolerante a errores. **No queda claro si Railway lo ejecuta**.

### CI/CD pipeline

**No hay**. No `.github/workflows`, no `.gitlab-ci.yml`. El deploy es push → Railway watcher.

---

## 7. Verificación post-deploy

### No hay smoke tests automatizados

No hay scripts CI que validen el deploy. Solo scripts manuales tipo `verify_*.py`:

| Script | Para qué |
|---|---|
| `verify_llm_monitoring_setup.py` | Setup LLM. |
| `verify_manual_ai_refactoring.py` | Integridad post-refactor. |
| `check_production_ready.py` | Pre-deploy check. |
| `check_staging_config.py` | Diff staging vs prod. |

### Health-check endpoints

| URL | Archivo |
|---|---|
| `GET /api/llm-monitoring/health` | `llm_monitoring_routes.py:5222` |
| `GET /manual-ai/api/health` | `manual_ai/routes/health.py` |
| `GET /api/health` (ai-mode) | `ai_mode_projects/routes/health.py:16-17` (función `manual_ai_health` — naming residual de copy/paste) |
| `POST/GET /api/cron/quota-health-check` | `cron_routes.py:108` |

> **No hay un `/healthz` general**. Railway usa el HTTP 200 de la raíz `/` para detectar liveness (no configurado healthcheck path explícito en `railway.json`).

---

## 8. Logs y monitoreo

### Logs Railway

- Vía CLI: `railway logs --service <name>`.
- Vía dashboard.
- **No están enviados a servicio externo**.

### Sin integración con observabilidad externa

`grep` confirma 0 referencias a `sentry_sdk`, `datadog`, `DD_API`. Solo logging estándar de Python.

### Logs estructurados

**No JSON**. `app.py:68-72` usa `logging.basicConfig` con formato textual:
```
'%(asctime)s - %(name)s - %(levelname)s - %(message)s'
```

En producción/staging baja nivel a `WARNING` (`app.py:110-112`).

> **Excepción**: el cron Manual AI sí emite logs JSON estructurados (`event: cron_start, cron_projects_found, cron_end, cron_skipped_lock`).

### Alertas

Vía email (Brevo SMTP):
- `cron_alerts.py` para LLM Monitoring (duración / error rate / cost spike).
- `cron_routes.py:_send_stuck_quota_alert` para quota reset.

### Tabla `llm_monitoring_analysis_runs`

Hace de log de auditoría de cada run de cron LLM en BD (lo que CLAUDE.md general llama "cron_runs" — ese nombre está obsoleto).

---

## 9. Acceso a producción

### Railway CLI

```bash
railway run --service Clicandseo <comando>
```

Útil para migraciones one-off:

```bash
railway run --service Clicandseo python3 migrate_xxx.py
```

### Conexión directa a Postgres

```bash
psql "$DATABASE_URL"
# o:
railway connect Postgres
```

URLs reales (con credenciales) **hardcoded** en `migrate_llm_staging_to_production.py:12-13` (riesgo).

### Scripts con creds hardcoded — ⚠️ riesgo de seguridad

Detectados:
- `check_ai_mode_data.py:13`
- `check_ai_mode_snapshots_structure.py`
- `analyze_ai_mode_migration.py`
- `check_projects_confusion.py`
- `create_ai_table.py`
- `fix_db_connection.py`
- `migrate_llm_staging_to_production.py`
- `run_ai_mode_analysis_manual.py`
- `add_missing_columns_production.py`
- `verify_migration_final.py`
- `create_ai_mode_tables_production.py`
- `export_hm_fertility_keywords_unique.py`

**Todos deberían usar `os.getenv('DATABASE_URL')`**.

---

## 10. MCP de Railway

Carlos tiene acceso a Railway desde Claude vía MCP. Funciones disponibles:

| Función | Para qué |
|---|---|
| `mcp__Railway__list-projects` | Lista proyectos. |
| `mcp__Railway__list-services` | Lista servicios. |
| `mcp__Railway__list-deployments` | Lista deploys. |
| `mcp__Railway__list-variables` | Lee env vars. |
| `mcp__Railway__set-variables` | Setea env vars. |
| `mcp__Railway__get-logs` | Obtiene logs. |
| `mcp__Railway__deploy` | Dispara deploy. |
| `mcp__Railway__link-service` | Linkea servicio. |
| `mcp__Railway__link-environment` | Linkea entorno. |
| `mcp__Railway__create-environment` | Crea entorno. |
| `mcp__Railway__generate-domain` | Genera dominio. |
| `mcp__Railway__check-railway-status` | Check status. |

**No detecté uso explícito de Railway MCP en el código** (lógico — el MCP es del lado de Claude, no de la app).

Desde Claude se puede: listar servicios y entornos, leer/setear variables de entorno, ver logs, redeployar, generar dominios.

---

## 11. Errores históricos y deuda técnica

### Bugs históricos resueltos

#### Array `crons` de `railway.json` silenciosamente ignorado durante 50 días

- **Síntoma**: el cron de quota reset no se disparaba. Causó que clientes pagando estuvieran 53 días sin servicio (caso Driza UEMC).
- **Causa**: el array `crons` de `railway.json` no se ejecuta en este proyecto (Railway no lo soporta como esperábamos).
- **Fix**: crear servicio `function-bun-Quota-reset` que llama a `/api/cron/quota-reset`. Documentado en `cron_routes.py:8-15`.

#### Playwright apt deps timeout

- **Causa**: el step `release` antiguo del Procfile reinstalaba ~300 paquetes apt + Chromium en cada deploy → timeouts.
- **Fix**: movido a `nixpacks.toml` setup phase (cacheado).

#### OAuth `InsecureTransportError`

- **Causa**: faltaba ProxyFix → Railway termina SSL en proxy y reenvía HTTP, `request.url` devolvía `http://`, OAuth fallaba.
- **Fix**: ProxyFix en `app.py:127-130`.

#### Webhooks Stripe 200 silencioso y `current_period_end = NULL`

Ver `CLAUDE-stripe-cuotas-crons.md` §12.

#### Self-deadlock en pool DB al despausar proyectos

Ver `CLAUDE-base-de-datos.md` §9.

### Discrepancias entre staging y producción

| Diferencia | Detalle |
|---|---|
| Default URL en Bun functions | `clicandseo.up.railway.app` (LLM, AI Mode) vs `app.clicandseo.com` (Quota Reset). Si `APP_URL` no está set, mitad apuntan a un sitio y mitad al otro. |
| Google OAuth credentials | Diferentes entre staging/prod (gestionado por `GOOGLE_REDIRECT_URI`). |
| Logging level | DEBUG en dev, WARNING en staging/prod. |
| HSTS | Solo en producción (no en staging) — `app.py:147-148`. |
| Bases de datos | Completamente separadas (caboose vs switchyard). |

### Deuda técnica conocida

| Deuda | Impacto | Riesgo |
|---|---|---|
| **Inconsistencia mayúsculas Bun services** (`Quota-Reset` vs `Quota-reset`) | Riesgo de duplicar servicio sin querer. | Medio. |
| **Archivo `railway`** (sin extensión) con contenido `Not Found` | Basura. | Trivial. |
| **`cron_worker.py`** (Python con lib `schedule`) duplica funcionalidad de Bun | No claro si está deployed. | Medio. |
| **`manual_ai_cron_function.js` no existe** | Cron Manual AI sin disparador claro. | Alto. |
| **`redis==5.1.1`** en requirements pero no en uso | Deuda. | Trivial. |
| **`requirements_llm_monitoring.txt`** separado pero no usado | Deuda. | Trivial. |
| **`postinstall.sh`** rol no claro | Posible vestigio. | Bajo. |
| **`ENCRYPTION_KEY` vs `TOKEN_ENCRYPTION_KEY`** | Posible duplicado. | Bajo. |
| **`RAILWAY_STAGING_VARIABLES.txt` con secretos** commited | Vulnerabilidad. | Alto. |
| **Scripts con creds DB hardcoded** | Vulnerabilidad. | Alto. |
| **Sin CI/CD pipeline** | Sin smoke tests automatizados post-deploy. | Medio. |
| **Sin backup automático verificado de Postgres** | Pérdida de datos en catástrofe. | Alto. |

### Documentos `.md` históricos

- `RAILWAY_STAGING_VARIABLES.txt` — set de env vars staging con secretos.
- `CLAUDE-stripe-cuotas-crons.md` — arquitectura de Bun crons.
- `OPTIMIZACION_CRON_DIARIO.md`, `IMPLEMENTACION_RETRY*.md`, `MEJORAS_LLM_MONITORING.md`, `ANALISIS_RETRY_SYSTEM.md`.
- `ai_mode_projects/SAFE_MIGRATION.md`, `manual_ai/SAFE_MIGRATION.md`, `*COMPLETION_SUMMARY.md`.

---

## 12. Operaciones manuales — chuleta de comandos

### Ver logs

```bash
railway logs --service Clicandseo                      # app
railway logs --service function-bun-LLM-Monitoring
railway logs --service function-bun-Quota-Reset
railway logs --service function-bun-AI-Mode
```

O vía MCP: `mcp__Railway__get-logs`.

### Reiniciar un servicio

- Dashboard Railway → botón "Restart".
- Vía MCP: redeploy con `mcp__Railway__deploy`.

### Disparar un cron manualmente

```bash
# Quota reset
curl -X POST "$APP_URL/api/cron/quota-reset?async=0" \
  -H "Authorization: Bearer $CRON_TOKEN"

# LLM Monitoring (15-20 min)
curl -X POST "$APP_URL/api/llm-monitoring/cron/daily-analysis?async=0" \
  -H "Authorization: Bearer $CRON_TOKEN"

# AI Mode
curl -X POST "$APP_URL/ai-mode-projects/api/cron/daily-analysis?async=0" \
  -H "Authorization: Bearer $CRON_TOKEN"

# Manual AI
curl -X POST "$APP_URL/manual-ai/api/cron/daily-analysis" \
  -H "Authorization: Bearer $CRON_TOKEN"

# Health-check standalone
curl -X POST "$APP_URL/api/cron/quota-health-check" \
  -H "Authorization: Bearer $CRON_TOKEN"
```

### Ver / setear env vars

- Dashboard Railway → Settings → Variables → Raw Editor.
- Vía MCP: `mcp__Railway__list-variables`, `mcp__Railway__set-variables`.

### Conectar a la BD

```bash
psql "$DATABASE_URL"          # con env var local
railway connect Postgres       # con Railway CLI
```

### Hacer rollback

- Dashboard Railway → Deployments → click en deploy anterior → "Redeploy".
- **No hay script de rollback automatizado** en el repo.

### Ejecutar migración one-off

```bash
railway run --service Clicandseo python3 <migration>.py
```

### Health checks rápidos

```bash
curl https://app.clicandseo.com/api/llm-monitoring/health
curl https://app.clicandseo.com/manual-ai/api/health
curl https://app.clicandseo.com/api/health   # ai-mode (route compartida)
```

### Backup manual de Postgres

```bash
pg_dump "$DATABASE_URL" > backup_$(date +%Y%m%d).sql
```

### Restore desde backup

```bash
psql "$DATABASE_URL" < production_backup_20251019_230248.sql
```

---

## TL;DR

1. **Railway con auto-deploy por git push** (branches `main` y `staging`). Sin CI/CD pipeline.
2. **8 servicios**: app Flask + Postgres + 5 Bun functions (cron). **Falta `function-bun-Manual-AI`** (deuda).
3. **Builder = nixpacks**, no Dockerfile. Procfile define `web` y `cron`; el `cron` probablemente inactivo.
4. **El array `crons` de `railway.json` NO se ejecuta** en este proyecto. Los crons reales son los Bun services. Documentado tras el caso Driza UEMC.
5. **Migraciones manuales**: `railway run --service Clicandseo python3 migrate_xxx.py`. NO automáticas en deploy.
6. **`RAILWAY_STAGING_VARIABLES.txt` está commited con secretos** — vulnerabilidad. Debería rotarse.
7. **Sin backup automático verificado** de Postgres. Riesgo alto.
8. **Sin observabilidad externa** (Sentry/Datadog). Solo logs Railway + alertas email vía Brevo.
9. **MCP Railway disponible desde Claude** — listar servicios, leer/setear vars, redeploy, logs.
10. **Health-check endpoints**: `/api/llm-monitoring/health`, `/manual-ai/api/health`, `/api/health` (AI Mode), `/api/cron/quota-health-check`. No hay `/healthz` general.

— Fin del manual —
