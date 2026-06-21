# CLAUDE-manual-ai.md — Manual AI Analysis (AI Overview Monitoring)

> Manual del subsistema **Manual AI Analysis**: medición de presencia de la marca del cliente en los **AI Overviews de Google** (los bloques generativos que Google muestra encima de los resultados orgánicos).
>
> Última actualización: 2026-06-21.
>
> Sistemas hermanos: ver `CLAUDE-ai-mode.md` (Google AI Mode) y `CLAUDE-llm-monitoring.md` (LLMs públicos). El índice maestro está en `CLAUDE-INDEX.md`.

---

## Índice

1. [Visión general en 5 minutos](#1-visión-general-en-5-minutos)
2. [Diferencias con AI Mode y LLM Monitoring](#2-diferencias-con-ai-mode-y-llm-monitoring)
3. [Mapa de archivos](#3-mapa-de-archivos)
4. [Modelo de datos](#4-modelo-de-datos)
5. [Flujo completo de un análisis](#5-flujo-completo-de-un-análisis)
6. [Detección de AI Overview y expansión "collapsed"](#6-detección-de-ai-overview-y-expansión-collapsed)
7. [Integración con cuotas y billing](#7-integración-con-cuotas-y-billing)
8. [Endpoints HTTP](#8-endpoints-http)
9. [Variables de entorno y constantes](#9-variables-de-entorno-y-constantes)
10. [Cron diario](#10-cron-diario)
11. [Frontend](#11-frontend)
12. [Errores históricos y deuda técnica](#12-errores-históricos-y-deuda-técnica)
13. [Operaciones manuales y troubleshooting](#13-operaciones-manuales-y-troubleshooting)
14. [Tests y diagnóstico](#14-tests-y-diagnóstico)

---

## 1. Visión general en 5 minutos

**Qué hace para el usuario.** Manual AI Analysis monitoriza, por proyecto, si la marca del cliente aparece en los **AI Overviews** que Google muestra para sus keywords. El usuario configura:

- Un **dominio** (la marca propia).
- Un **país** (la SERP varía por país).
- Una lista de **keywords** (hasta 200).
- Hasta **4 competidores** seleccionados.
- Opcionalmente, **topic clusters** (agrupaciones temáticas de keywords).

Cada día el sistema, para cada keyword, consulta Google vía **SerpAPI**, detecta si aparece AI Overview, si el dominio del proyecto está citado como fuente, en qué posición, y qué otros dominios aparecen. De ahí se derivan métricas de **visibilidad**, **share of voice**, **posición media**, ranking de dominios y URLs citadas, y comparación AIO vs orgánico.

**Cómo se llama en la UI.** "AI Overview Monitoring" (título de la página). En código se llama `manual_ai`/Manual AI por razones históricas (es el sistema más antiguo de los tres).

**URL pública.** `https://<host>/manual-ai/`. Paywall para `plan='free'` salvo que tenga acceso compartido vía `project_collaborators`.

**Reglas de oro:**

1. La fuente de la SERP es **SerpAPI** (`engine=google`). No hacemos scraping directo.
2. El cron diario es **secuencial** (no hay paralelismo configurable, a diferencia de LLM Monitoring).
3. La idempotencia es por `UNIQUE(project_id, keyword_id, analysis_date)` en `manual_ai_results`.
4. Concurrencia entre runs se evita con un **PostgreSQL advisory lock** (`pg_try_advisory_lock(4242, YYYYMMDD)`).
5. La cuota se consume **1 RU por keyword analizada** + **1 RU adicional** si el AIO está "collapsed" y hay que reabrirlo con un segundo fetch.

---

## 2. Diferencias con AI Mode y LLM Monitoring

| | Manual AI | AI Mode | LLM Monitoring |
|---|---|---|---|
| **Producto Google/LLM medido** | AI Overviews (SGE) | Google AI Mode | ChatGPT / Claude / Gemini / Perplexity |
| **Fuente de datos** | SerpAPI `engine=google` | SerpAPI `engine=google_ai_mode` | APIs directas de los LLMs |
| **Tablas BD** | `manual_ai_*` | `ai_mode_*` | `llm_monitoring_*` |
| **Coste por análisis** | 1 RU/keyword (+1 si collapsed) | 1 RU/keyword | 1 unidad por (prompt × LLM) |
| **Paralelismo cron** | Secuencial | Secuencial | Paralelo (`LLM_PROJECT_PARALLELISM`) |
| **Timeout por proyecto** | No | No | Sí (`project_timeout.py`) |
| **Advisory lock class_id** | `4242` | `4243` | `acquire_analysis_lock` (tabla aparte) |

Los tres sistemas comparten patrón de arquitectura (blueprint Flask + repos + services + cron + JS modular) pero son módulos independientes con tablas distintas.

---

## 3. Mapa de archivos

### Núcleo modular (paquete `manual_ai/`)

| Archivo | Qué contiene |
|---|---|
| `manual_ai/__init__.py` | Crea el blueprint `manual_ai_bp` con `url_prefix='/manual-ai'`. |
| `manual_ai/config.py` | Constantes (`MANUAL_AI_KEYWORD_ANALYSIS_COST=1`, `MAX_KEYWORDS_PER_PROJECT=200`, `MAX_COMPETITORS_PER_PROJECT=4`, `CRON_LOCK_CLASS_ID=4242`, `EVENT_TYPES`). |
| `manual_ai_system_bridge.py` | Capa de compatibilidad. Reexporta el sistema modular nuevo o cae al monolítico antiguo si fallara el import. |

### Rutas (Flask)

| Archivo | Cubre |
|---|---|
| `manual_ai/routes/projects.py` | Dashboard HTML + CRUD proyectos + pause/resume/delete. |
| `manual_ai/routes/keywords.py` | CRUD keywords. |
| `manual_ai/routes/analysis.py` | Análisis on-demand y trigger del cron diario. |
| `manual_ai/routes/results.py` | Endpoints de stats / tablas / ranking. |
| `manual_ai/routes/competitors.py` | Gestión de competidores y charts comparativos. |
| `manual_ai/routes/clusters.py` | Topic clusters (agrupación temática de keywords). |
| `manual_ai/routes/exports.py` | Excel + PDF. |
| `manual_ai/routes/health.py` | `/api/health`. |

### Servicios (lógica)

| Archivo | Qué hace |
|---|---|
| `manual_ai/services/project_service.py` | Alta/baja/pause/resume de proyectos. |
| `manual_ai/services/analysis_service.py` | **Motor de análisis**: loop por keyword → cache → fetch SERP → detect AIO → expandir collapsed → guardar resultado + dominios + consumir cuota. |
| `manual_ai/services/cron_service.py` | `run_daily_analysis_for_all_projects`, advisory-lock, filtros de elegibilidad, snapshot+evento. |
| `manual_ai/services/competitor_service.py` | **Shell (~22 líneas)**: `class CompetitorService(_ValidationMixin, _HistoricalMixin, _ChartsMixin)`. Validación, sync histórico de flags `is_selected_competitor`, charts comparativos. Mixins en `manual_ai/services/_competitor/` (`validation.py`, `historical.py`, `charts.py`). |
| `manual_ai/services/cluster_service.py` | Clasificación de keywords en clusters temáticos. |
| `manual_ai/services/statistics_service.py` | **Shell (~21 líneas)**: `class StatisticsService(_OverviewMixin, _KeywordsMixin, _DomainsMixin, _AioOrganicMixin)`. Stats agregadas (visibility daily, top domains, urls ranking, AIO-vs-organic). Mixins en `manual_ai/services/_statistics/` (`overview.py`, `keywords.py`, `domains.py`, `aio_organic.py`). |
| `manual_ai/services/domains_service.py` | `store_global_domains_detected` — escribe en `manual_ai_global_domains`. |
| `manual_ai/services/export_service.py` | Excel multi-hoja. |
| `manual_ai/services/pdf_export_service.py` | PDF multi-página vía ReportLab. |

### Repositorios (acceso a BD)

`manual_ai/models/project_repository.py`, `keyword_repository.py`, `result_repository.py`, `event_repository.py`.

### Utils

`manual_ai/utils/decorators.py` (`@with_backoff`), `validators.py` (`check_manual_ai_access`), `helpers.py`, `country_utils.py`, `export_filename.py`.

### Cron y scripts CLI

| Archivo | Qué contiene |
|---|---|
| `daily_analysis_cron.py` | Script CLI legacy invocado desde Procfile y `railway.json`. Llama directamente a `run_daily_analysis_for_all_projects()`. |

> ⚠️ **No hay un servicio Bun dedicado** para Manual AI (a diferencia de LLM Monitoring, AI Mode y Quota Reset). El cron Manual AI conviven entre **Procfile worker** + **`railway.json crons`** + **endpoint HTTP** `/manual-ai/api/cron/daily-analysis`. Verificar con Carlos qué disparador está realmente activo en Railway.

### Frontend

| Archivo | Qué contiene |
|---|---|
| `templates/manual_ai_dashboard.html` | Plantilla principal (1973 líneas). |
| `templates/paywall_manual_ai.html` | Paywall para usuarios free. |
| `static/js/manual-ai-system-modular.js` | Entry point ES modules (único que carga el template). |
| ~~`static/js/manual-ai-system.js`~~ | Monolito JS eliminado (ya no existe en el repo). |
| `static/js/manual-ai/*.js` | Submódulos: `manual-ai-core.js`, `-projects.js`, `-keywords.js`, `-analysis.js`, `-charts.js`, `-competitors.js`, `-clusters.js`, `-modals.js`, `-exports.js`, `-utils.js`. **`-analytics.js` es ahora un barrel (~13 líneas)** que reexporta 6 sub-módulos temáticos: `-analytics-core.js`, `-analytics-domains.js`, `-analytics-urls.js`, `-analytics-table.js`, `-analytics-comparative.js`, `-analytics-aio-organic.js`. |

### Migraciones

| Archivo | Qué hace |
|---|---|
| `create_manual_ai_tables.py` | Crea las 5 tablas base + índices. |
| `create_global_domains_table.py` | `manual_ai_global_domains`. |
| `add_competitors_fields.py` | Añade `selected_competitors JSONB`. |
| `add_topic_clusters_field.py` | Añade `topic_clusters JSONB`. |
| `migrate_manual_ai_quota_pause_fields.py` | Añade `is_paused_by_quota`, `paused_until`, `paused_at`, `paused_reason`. |
| `migrate_analysis_frequency_fields.py` | Añade `analysis_frequency_days` a `manual_ai_projects` y `ai_mode_projects` (2026-06-10). |

### Tests / diagnóstico

Scripts vigentes: `check_manual_ai_system.py`, `diagnose_cron_skip.py`. Los scripts de verificación de la migración (`audit_manual_ai_system.py`, `verify_manual_ai_refactoring.py`, `verify_manual_ai_js.sh`, `manual_ai/check_refactoring_status.py`) y el test de caracterización del blueprint (`tests/test_manual_ai_contract.py`, que congelaba el contrato de las 36 rutas) se eliminaron (último limpiado en commit 91a0f7a). El dato **36 endpoints** sigue siendo correcto (ver §8). Cobertura de **lógica de negocio** sigue ~0% (ver §14).

---

## 4. Modelo de datos

### `manual_ai_projects`

```
id                    SERIAL PK
user_id               INTEGER FK users(id) ON DELETE CASCADE
name                  VARCHAR(255)         -- UNIQUE por user_id
description           TEXT
domain                VARCHAR(255)         -- check ≥4 chars
country_code          VARCHAR(3) DEFAULT 'US'
is_active             BOOLEAN DEFAULT TRUE -- pausa manual
created_at            TIMESTAMP
updated_at            TIMESTAMP
-- migración quota-pause:
is_paused_by_quota    BOOLEAN
paused_until          TIMESTAMPTZ
paused_at             TIMESTAMPTZ
paused_reason         TEXT
-- migraciones posteriores:
selected_competitors  JSONB DEFAULT '[]'                              -- max 4 dominios
topic_clusters        JSONB DEFAULT '{"enabled":false,"clusters":[]}'
analysis_frequency_days INTEGER DEFAULT 1  -- cada cuántos días lo analiza el cron (7 = semanal)
```

Índices: `idx_manual_projects_user`, `idx_manual_projects_active`.

### `manual_ai_keywords`

```
id          SERIAL PK
project_id  FK manual_ai_projects ON DELETE CASCADE
keyword     VARCHAR(500)            -- UNIQUE por project_id
is_active   BOOLEAN DEFAULT TRUE
added_at    TIMESTAMP
```

### `manual_ai_results`

Una fila por (proyecto, keyword, día):

```
id                  SERIAL PK
project_id          FK CASCADE
keyword_id          FK CASCADE
analysis_date       DATE
keyword             VARCHAR(500)   -- denormalizado
domain              VARCHAR(255)   -- denormalizado (project.domain)
-- métricas AIO:
has_ai_overview     BOOLEAN
domain_mentioned    BOOLEAN
domain_position     INTEGER
ai_elements_count   INTEGER
impact_score        INTEGER
-- raw data:
raw_serp_data       JSONB
ai_analysis_data    JSONB
country_code        VARCHAR(3)
created_at          TIMESTAMP
-- (añadido por path quota): error_details, updated_at
UNIQUE(project_id, keyword_id, analysis_date)
```

Índices: `idx_manual_results_project_date`, `idx_manual_results_date`, `idx_manual_results_ai_overview`, `idx_manual_results_domain_mentioned`.

> ⚠️ La columna `updated_at` se usa en `ON CONFLICT DO UPDATE SET ... updated_at=NOW()` en el path de quota_error. **No aparece en el `CREATE TABLE` original** y no hay migración explícita en el repo. Verificar que existe en producción.

### `manual_ai_snapshots`

Snapshot diario por proyecto. Campos: `total_keywords`, `active_keywords`, `keywords_with_ai`, `domain_mentions`, `avg_position DECIMAL(5,2)`, `visibility_percentage DECIMAL(5,2)`, `change_type`, `change_description`, `keywords_added/removed`. UNIQUE `(project_id, snapshot_date)`.

### `manual_ai_events`

Anotaciones para overlay en gráficos.

```
event_type ∈ {
  project_created, keywords_added, keyword_deleted,
  manual_analysis_completed, manual_analysis_quota_exceeded,
  daily_analysis, competitors_changed, competitors_updated,
  manual_note_added, ...
}
```

### `manual_ai_global_domains`

**Una fila por dominio detectado** en cada AIO de cada keyword/día. Es la base de los rankings de dominios y URLs citadas.

```
project_id, keyword_id (CASCADE)
analysis_date DATE
keyword, project_domain (denorm)
detected_domain VARCHAR(255)
domain_position INTEGER          -- >0
domain_title TEXT
domain_source_url TEXT
country_code
is_project_domain      BOOLEAN
is_selected_competitor BOOLEAN
UNIQUE(project_id, keyword_id, analysis_date, detected_domain)
```

Índices: `idx_global_domains_project_date`, `idx_global_domains_domain`, `idx_global_domains_competitor_flag`.

### Diagrama de relaciones

```
users (id) ──< manual_ai_projects (user_id)
                  │
                  ├─< manual_ai_keywords
                  │       │
                  │       └─< manual_ai_results
                  │
                  ├─< manual_ai_snapshots
                  ├─< manual_ai_events
                  └─< manual_ai_global_domains

project_collaborators — tabla cross-módulo que da acceso "viewer" a usuarios secundarios.
```

---

## 5. Flujo completo de un análisis

### 5.1 Crear proyecto

`POST /manual-ai/api/projects` con `{name, domain, country_code, competitors[]}`. `ProjectService.create_project` valida acceso (`check_manual_ai_access`), normaliza dominio (`normalize_search_console_url`), valida competitors (max 4) y crea evento `project_created`.

### 5.2 Análisis manual on-demand

Frontend (`manual-ai-analysis.js`) → `POST /manual-ai/api/projects/{id}/analyze`. Endpoint en `analysis.py:analyze_project`:

1. `check_manual_ai_access` y ownership.
2. Llama `analysis_service.run_project_analysis(project_id, force_overwrite=True)`.
3. Si `{quota_exceeded: True}`: snapshot parcial + evento `manual_analysis_quota_exceeded` + **HTTP 429**.
4. Si OK: snapshot diario + evento `manual_analysis_completed` + 200.

### 5.3 Análisis diario (cron)

`CronService.run_daily_analysis_for_all_projects` (`cron_service.py`):

1. **PostgreSQL advisory lock** session-level: `pg_try_advisory_lock(4242, YYYYMMDD)` con `lock_conn.autocommit=True` (para que la lock no muera por `idle_in_transaction_session_timeout` de 15 min).
2. Si no obtiene lock: salta (`cron_skipped_lock`).
3. `_get_active_projects()`: SQL que filtra:
   - `is_active = TRUE`.
   - `is_paused_by_quota = FALSE` **OR** `paused_until <= NOW()` (auto-resume si caducó).
   - `users.plan != 'free'`.
   - `users.billing_status NOT IN ('canceled')`.
   - `≥ 1` keyword activa.
4. Para cada proyecto (secuencial):
   - Re-verifica plan/billing.
   - Si ya hay resultados hoy → skip (no sobreescribe).
   - Llama `analysis_service.run_project_analysis(project_id, force_overwrite=False, user_id=...)`.
5. Crea snapshot + evento `daily_analysis`.
6. Libera lock. Devuelve `{successful, failed, skipped, total_keywords, elapsed_seconds}`.

### 5.4 Motor `analysis_service.run_project_analysis`

Para cada keyword activa:

1. **Reverificar cuota** (`get_user_quota_status` en `quota_manager.py`). Si agotada → `pause_manual_ai_projects_for_quota` + retorna `quota_exceeded`.
2. Si ya existe resultado hoy y `force_overwrite=False` → skip.
3. **`_analyze_keyword`**:
   - **Cache check**: `services.ai_cache.ai_cache.get_cached_analysis(keyword, domain, country)`.
   - **Fetch SERP**: `services.serp_service.get_serp_json` envuelto por `quota_protected_serp_call` de `quota_middleware.py`. Engine `google`, `num=20`, location/gl/hl/google_domain de `services.country_config.get_country_config`. API key: `os.getenv('SERPAPI_KEY')`. Decorador `@with_backoff(max_attempts=3, base_delay_sec=1.0)`.
   - **Detectar AIO**: `services.ai_analysis.detect_ai_overview_elements(serp_data, project_domain)`. Devuelve dict con `has_ai_overview`, `domain_is_ai_source`, `domain_ai_source_position`, `total_elements`, `impact_score`, `debug_info: {references_found, requires_additional_request, page_token}`.
   - **Expansión collapsed AIO** (NUEVO 2026-04-09): si `requires_additional_request` y hay `page_token`, hace un **segundo fetch** con `page_token` para extraer `text_blocks/references` del AIO oculto tras "Show more". Cuesta 1 RU adicional. Si falla → no-op seguro.
   - **Cache write**.
4. **Guardar**: `result_repository.create_result` (insert en `manual_ai_results`).
5. **Almacenar dominios globales**: si `has_ai_overview`, `domains_service.store_global_domains_detected` extrae `references_found`, normaliza dominios, marca `is_project_domain` y `is_selected_competitor`, e inserta en `manual_ai_global_domains` (con DELETE previo del día para idempotencia).
6. **Consumir cuota**: `database.track_quota_consumption(user_id, ru_consumed=1, source='manual_ai', keyword, country_code, metadata={project_id, force_overwrite, domain})`.
7. Si excepción tiene `is_quota_error=True`: insert con `error_details='QUOTA_EXCEEDED:...'` (UPSERT), pausa proyecto, retorna `quota_exceeded`.

### 5.5 Cálculo de métricas

| Métrica | Fórmula |
|---|---|
| **Visibility (%)** | `domain_mentions / keywords_with_ai * 100` |
| **AIO weight (%)** | `keywords_with_ai / keywords_analyzed * 100` |
| **Avg position** | `AVG(domain_position) WHERE domain_mentioned=TRUE` |
| **Top domains** | Agregación de `manual_ai_global_domains` por `detected_domain`. |
| **Share of voice** | Implícito en `competitor_service.get_project_comparative_charts_data` (proyecto vs cada competidor). |
| **AIO vs Organic** | `statistics_service.get_aio_vs_organic_comparison` cruza top10 orgánico (de `raw_serp_data`) con references AIO → 4 cuadrantes (Rank&Cited / Rank-only / Cited-only / Neither). No consume SerpAPI. |

---

## 6. Detección de AI Overview y expansión "collapsed"

Detalle del fix más crítico del 2026-04-09 (vive como `# NUEVO 2026-04-09` en `analysis_service.py:361-402`).

### El problema

SerpAPI a veces devuelve un AIO con `page_token` pero **sin** `text_blocks` ni `references`. Es el estado **"collapsed"**: el AIO existe en la SERP pero está oculto tras un botón "Show more" / "Mostrar más".

Antes del fix, en este caso el sistema:
- Marcaba `has_ai_overview=true` (correcto).
- Pero perdía `references`, `text_blocks`, `domain_position`, `domain_mentioned` (lo importante).

**Producción mide ~12% de AIOs en este estado.** Algunos casos extremos: UEMC 23.6%, Catalonia 22.2%, Adeslas 10.4%.

### El fix

Si `debug_info.requires_additional_request == True` y hay `page_token`:

1. Segundo fetch a SerpAPI con `page_token` (cuesta 1 RU adicional).
2. Re-analizar el payload expandido.
3. Si el segundo fetch falla → no-op seguro: se mantiene el resultado collapsed sin reventar el flujo.

### Coste

`MANUAL_AI_KEYWORD_ANALYSIS_COST = 1` por keyword normal. Las keywords con AIO collapsed consumen **2 RU** (fetch inicial + fetch con `page_token`). El `quota_middleware.py` lo contabiliza correctamente.

---

## 7. Integración con cuotas y billing

### Coste

- `MANUAL_AI_KEYWORD_ANALYSIS_COST = 1` RU por keyword (`manual_ai/config.py`).
- Expansión collapsed AIO: 1 RU adicional vía `quota_middleware`.

### Pre-validación

Al inicio de `run_project_analysis` y **dentro del loop por keyword**, se llama a `quota_manager.get_user_quota_status(user_id)`. Si `can_consume=False` o `remaining < 1`: rompe el loop y pausa el proyecto.

### Pause flag

`database.pause_manual_ai_projects_for_quota(user_id, paused_until, reason='quota_exceeded')` setea `is_paused_by_quota=TRUE` + `paused_until` + `paused_reason` en **todos** los proyectos del usuario.

El cron filtra estos proyectos (`COALESCE(is_paused_by_quota, FALSE)=FALSE OR paused_until <= NOW()`).

### Auto-unpause

Dos vías:
1. Cuando `paused_until` expira y el usuario intenta analizar, `analysis_service` limpia los flags y continúa.
2. `database.resume_quota_pauses_for_user` (llamado desde el webhook Stripe `invoice.payment_succeeded` y desde el cron quota-reset) los limpia tras renovación.

### Notificación al usuario

- HTTP 429 con `{quota_exceeded: True, quota_info, action_required, keywords_analyzed, keywords_remaining, paused_until}`.
- El frontend (`manual-ai-analysis.js`) muestra modal con info de upgrade.

### Acceso por plan

`check_manual_ai_access(user)` bloquea `plan='free'` salvo que tenga `project_collaborators` con módulo `manual_ai`.

---

## 8. Endpoints HTTP

Todos bajo prefijo `/manual-ai`.

### UI (HTML)
- `GET /` — `projects.manual_ai_dashboard` → render `manual_ai_dashboard.html`.

### API proyectos
- `GET /api/projects` — lista del user.
- `POST /api/projects` — crear.
- `GET /api/projects/<id>` — detalles (allow_shared).
- `PUT /api/projects/<id>` — actualizar nombre/descripción.
- `DELETE /api/projects/<id>` — borrado permanente (requiere pause previo).
- `PUT /api/projects/<id>/pause` — pausa manual.
- `PUT /api/projects/<id>/resume` — reanudar (puede devolver 402 si quota_exceeded).

### API keywords
- `GET /api/projects/<id>/keywords`
- `POST /api/projects/<id>/keywords` — añadir (límite 200).
- `PUT /api/projects/<id>/keywords/<kw_id>`
- `DELETE /api/projects/<id>/keywords/<kw_id>`

### API análisis
- `POST /api/projects/<id>/analyze` — análisis on-demand. Status: 200 / 400 / 402 / 429 quota / 503 / 500.
- `POST /api/cron/daily-analysis` — cron diario (`@cron_or_auth_required`). Soporta `?async=1` (HTTP 202).

### API resultados / stats
- `GET /api/projects/<id>/results?days=30`
- `GET /api/projects/<id>/stats?days=30`
- `GET /api/projects/<id>/stats-latest`
- `GET /api/projects/<id>/ai-overview-table?days=30`
- `GET /api/projects/<id>/ai-overview-table-latest`
- `GET /api/projects/<id>/top-domains`
- `GET /api/projects/<id>/global-domains-ranking?days=30`
- `GET /api/projects/<id>/urls-ranking?days=30&limit=20`
- `GET /api/projects/<id>/aio-vs-organic?days=30`

### API competidores
- `GET /api/projects/<id>/competitors`
- `PUT /api/projects/<id>/competitors`
- `GET /api/projects/<id>/competitors-charts?days=30`
- `GET /api/projects/<id>/comparative-charts?days=30`

### API clusters
- `GET /api/projects/<id>/clusters`
- `PUT /api/projects/<id>/clusters`
- `GET /api/projects/<id>/clusters/statistics?days=30`
- `POST /api/projects/<id>/clusters/validate`
- `POST /api/projects/<id>/clusters/test`

### API exports / health
- `POST /api/projects/<id>/download-excel` (body: `{days}`) → `.xlsx`.
- `GET /api/projects/<id>/export/pdf?days=30` → `.pdf` (1-365 clamp).
- `GET /api/health` — sin auth. Devuelve `{status, db, last_cron, results_today, global_domains_today}`.

---

## 9. Variables de entorno y constantes

### Env vars

| Variable | Para qué sirve |
|---|---|
| `SERPAPI_KEY` | **Obligatoria**. Sin ella todas las keywords fallan. |
| `CRON_TOKEN` o `CRON_SECRET` | Bearer compartido para `/api/cron/daily-analysis`. |
| `SCREENSHOT_CACHE_TTL_SECONDS` | Default 3600. Cache de screenshots SERP. |
| `SCREENSHOT_CACHE_MAX` | Default 200. |

> Manual AI **no tiene** flags tipo `MANUAL_AI_PARALLELISM` ni `MANUAL_AI_TIMEOUT_MINUTES` (a diferencia de LLM Monitoring). El cron es estrictamente secuencial.

### Constantes hardcodeadas (`manual_ai/config.py`)

```
MANUAL_AI_KEYWORD_ANALYSIS_COST = 1
MAX_KEYWORDS_PER_PROJECT        = 200
MAX_COMPETITORS_PER_PROJECT     = 4
MAX_NOTE_LENGTH                 = 500
DEFAULT_DAYS_RANGE              = 30
DEFAULT_TOP_DOMAINS_LIMIT       = 10
CRON_LOCK_CLASS_ID              = 4242
```

Default country: `'US'` (puede sobreescribirse por proyecto).

---

## 10. Cron diario

### Schedule y disparador real en producción (verificado 2026-06-10)

El disparador real es el servicio Bun **`function-bun-AI-Overview`** en Railway (verificado vía Railway GraphQL API el 2026-06-19), con `cronSchedule`:
- **production**: `0 04 * * 1,4,6` (lun/jue/sáb 04:00 UTC — NO es diario).
- **staging**: `0 05 * * 6` (sáb 05:00 UTC).

Llama a `/manual-ai/api/cron/daily-analysis?async=1` con Bearer `CRON_TOKEN`. El source del Bun service no está en el repo; vive en Railway (dashboard).

**Por qué NO se ejecutan ni Procfile ni railway.json** (confirmado por API: el servicio web `Clicandseo` no tiene `cronSchedule`):
- El arranque lo gobierna `nixpacks.toml` (`[phases.start] = "python3 app.py"`), así que el `Procfile` es inerte en Railway. La línea `cron:` del Procfile se eliminó el 2026-06-19 (no había servicio que la corriera).
- El array `crons` de `railway.json` no es parte del esquema de Railway (solo honra `deploy.cronSchedule`), así que se ignora. **Se mantiene a propósito** como manifiesto documental porque `test_llm_cron_jobs.py` lo valida; NO refleja los horarios reales (que son los de arriba).
- `daily_analysis_cron.py` queda como entrypoint de invocación **manual** (`railway run ... python3 daily_analysis_cron.py`), no programado.

### Frecuencia por proyecto (NUEVO 2026-06-10)

`manual_ai_projects.analysis_frequency_days` (default 1) controla cada cuántos días analiza el cron cada proyecto: en `_process_projects` se salta el proyecto si ya tiene resultados con `analysis_date > hoy - N`. Con 1 el comportamiento es el histórico (máx. 1 vez/día); con 7 es semanal. Mismo campo y lógica en `ai_mode_projects`. Caso de uso original: cliente Fly me to the moon (user 665719, Mireia) con frecuencia semanal para ahorrar cuota — proyecto manual_ai id 29. ⚠️ Los proyectos nuevos nacen con default 1; si ese cliente crea más proyectos hay que ponerles el 7 a mano (UPDATE en BD). El botón "Analizar" on-demand NO respeta esta frecuencia (solo gobierna el cron).

### Idempotencia / concurrencia

- **PostgreSQL advisory lock** `pg_try_advisory_lock(4242, YYYYMMDD)`. Si ya está lockeado → "Another daily run in progress (skipped)".
- `lock_conn.autocommit=True` (NUEVO 2026-04-09) para que la lock no muera por `idle_in_transaction_session_timeout` cuando los runs duran >15 min.
- UNIQUE constraint `(project_id, keyword_id, analysis_date)` en `manual_ai_results`.
- Skip explícito si `existing_results > 0` para `(project_id, today)` (cron mode no sobreescribe).

### Filtros de elegibilidad

```sql
WHERE p.is_active = TRUE
  AND (p.is_paused_by_quota = FALSE OR p.paused_until <= NOW())
  AND u.plan != 'free'
  AND u.billing_status NOT IN ('canceled')
  AND EXISTS (SELECT 1 FROM manual_ai_keywords k
              WHERE k.project_id = p.id AND k.is_active = TRUE)
```

### Características operativas

- **Paralelismo**: ninguno. Procesa proyectos secuencialmente con `for project in projects`.
- **Timeout**: ninguno por proyecto. Un proyecto con red colgada puede arrastrar al cron entero hasta el `idle_in_transaction_session_timeout`.
- **Registro del run**: **no escribe en `cron_runs`**. Loguea JSON estructurado (`event: cron_start, cron_projects_found, cron_end, cron_skipped_lock`) con `job_id=cron-{epoch}` y crea evento `daily_analysis` en `manual_ai_events` por cada proyecto exitoso.
- **Alertas** (NUEVO 2026-06-10): email de resumen OK/WARNING/CRITICAL por run (`cron_alerts.send_simple_run_completion_email`, hook en `CronService._send_completion_email`) + detección diaria de "cron parado" (`cron_routes._run_module_staleness_check`, umbral `CRON_STALENESS_MAX_DAYS=4`).

---

## 11. Frontend

### Plantilla principal

`templates/manual_ai_dashboard.html` (1973 líneas). Stack:
- **Chart.js** (CDN) — gráficos visibility, position distribution, comparativas.
- **Grid.js** (CDN, theme mermaid) — tablas (AI overview keywords, global domains ranking, urls ranking, AIO vs Organic).
- **Font Awesome** 6.0, **GTM** `GTM-NXJS74ZQ`.
- **CSS propios**: `manual-ai.css`, `quota-ui.css`, `clusters-styles.css`, `paywall.css`, `tablas.css`, `modales-datos.css`, `sidebar-navigation.css`, `navbar.css`.
- **Bloque paywall** (`access_blocked`): overlay con CTA `/billing` cuando user es free.

### Submódulos JS

Entry: `static/js/manual-ai-system-modular.js`. Cada submodule tiene responsabilidad clara:

| Módulo | Líneas | Responsabilidad |
|---|---:|---|
| `manual-ai-core.js` | 667 | Clase `ManualAISystem`, init, cache de DOM, auto-refresh, clearObsoleteCache. |
| `manual-ai-projects.js` | 696 | List, render, create, pause, resume, delete. Validación de dominio. |
| `manual-ai-keywords.js` | 285 | Add/remove, modal, contador con límite 200. |
| `manual-ai-analysis.js` | 203 | `analyzeProject(id)` → POST analyze, manejo de quota_exceeded. |
| `manual-ai-charts.js` | 547 | renderVisibility/Positions, anotaciones de eventos sobre gráfico. |
| `manual-ai-competitors.js` | 339 | Form chips, validación, charts comparativos. |
| `manual-ai-clusters.js` | 758 | Config UI clusters, validación, gráficos. |
| `manual-ai-modals.js` | 837 | Modales de detalles, edición, confirmación delete. |
| `manual-ai-analytics.js` | 13 | **Barrel**: reexporta los 6 sub-módulos de analytics (abajo). Stats endpoints, render Grid.js, ranking dominios/urls, AIO vs Organic. |
| ↳ `manual-ai-analytics-core.js` | 187 | Núcleo de analytics. |
| ↳ `manual-ai-analytics-domains.js` | 276 | Ranking de dominios. |
| ↳ `manual-ai-analytics-urls.js` | 389 | Ranking de URLs. |
| ↳ `manual-ai-analytics-table.js` | 259 | Tabla AI overview (Grid.js). |
| ↳ `manual-ai-analytics-comparative.js` | 301 | Charts comparativos vs competidores. |
| ↳ `manual-ai-analytics-aio-organic.js` | 278 | Comparativa AIO vs orgánico. |
| `manual-ai-exports.js` | 250 | Botones descarga Excel/PDF. |
| `manual-ai-utils.js` | 209 | escapeHtml, debounce, getDomainLogoUrl, normalizeDomainString, isValidDomain. |

### Refresco

Auto-refresh con `refreshInterval` (en core). Cachebusting con `?_t=${Date.now()}` cuando relevante. **No usa websockets**.

---

## 12. Errores históricos y deuda técnica

### Comentarios marcadores en código

- **`# NOTA 2026-04-09`** (`analysis_service.py:147-153`): antes se abría conn+cur al inicio del método y se mantenía abierta durante todo el loop de keywords. Era vulnerable al `idle_in_transaction_session_timeout` (15 min, hardening del 2026-04-08). Ahora la conn de quota_error se abre localmente sólo cuando hace falta.
- **`# NUEVO 2026-04-09 (collapsed AIO)`** (`analysis_service.py:361-402`): segundo fetch con `page_token` cuando AIO está collapsed. Detallado en §6.
- **`# NUEVO 2026-04-09 (advisory lock autocommit)`** (`cron_service.py:56-63`): `lock_conn.autocommit=True` para que la lock no muera por `idle_in_transaction_session_timeout`.

### Deuda técnica conocida

| Deuda | Impacto | Riesgo |
|---|---|---|
| **Cron sin paralelismo ni timeout por proyecto** | 40-60 proyectos pueden tardar >15 min, un proyecto colgado arrastra todo. | Medio-alto. |
| ~~Sin alertas de cron por email~~ **RESUELTO 2026-06-10** | Email por run + detección de cron parado. | — |
| **Sin tests unitarios reales** | Cobertura 0%. Cualquier cambio requiere test manual extensivo. | Alto. |
| **Doble entrada del cron** (Procfile + railway.json + endpoint) | No claro cuál se ejecuta en producción. La advisory lock lo mitiga. | Medio. |
| **`manual_ai_results.updated_at`** usado en código pero sin migración explícita | Posible fallo silencioso si la columna no existe en producción. | Bajo (ya verificado en runtime). |
| ~~Bridge con fallback a monolítico que ya no existe~~ **RESUELTO 2026-06-19** | El bridge se simplificó: ya no tiene rama de fallback muerta, solo reexporta del paquete modular. | — |
| ~~Versión monolítica del JS sigue presente~~ **RESUELTO** | El monolito JS ya estaba eliminado. | — |
| ~~`import manual_ai_system` muerto en `diagnostic_endpoint.py`~~ **RESUELTO 2026-06-19** | Test 6 repuntado al paquete modular vía bridge. | — |
| ~~Artefactos `.md` de migración + scripts de verificación de refactor~~ **RESUELTO 2026-06-19** | Eliminados 11 archivos de proceso; se conservan los `README.md` de arquitectura. | — |

### Archivos `.md` sueltos del repo

Los `.md` sueltos del repo (`ANALISIS_RETRY_SYSTEM.md`, `IMPLEMENTACION_RETRY*.md`, `ELIMINACION_ANALISIS_MANUAL.md`, `FIX_DISCREPANCIA_MENCIONES_LLM.md`, `MEJORAS_LLM_MONITORING.md`, `OPTIMIZACION_CRON_DIARIO.md`, `SOLUCION_OPENAI_GPT5.md`, `SOLUCION_QUERIES_INCOMPLETAS.md`) son **de LLM Monitoring**, NO de Manual AI. La historia de Manual AI vive en los comentarios `# NOTA/NUEVO 2026-04-09` del propio código.

`FIX_GRIDJS_ERROR.md` es frontend genérico, posiblemente afecta a Manual AI también.

---

## 13. Operaciones manuales y troubleshooting

### Disparar manualmente el cron Manual AI

```bash
curl -X POST "$APP_URL/manual-ai/api/cron/daily-analysis?async=0" \
  -H "Authorization: Bearer $CRON_TOKEN"
```

### Disparar análisis on-demand de un proyecto

Como user (con cookie de sesión), desde la UI o:

```bash
curl -X POST "$APP_URL/manual-ai/api/projects/<id>/analyze" \
  -H "Cookie: session=..."
```

### "Un cliente dice que su proyecto Manual AI no se actualiza"

1. Health-check: `GET /manual-ai/api/health` (sin auth) — devuelve `last_cron, results_today`.
2. Mirar `manual_ai_projects.is_paused_by_quota` y `paused_until`.
3. Si pausado por cuota: ver `CLAUDE-stripe-cuotas-crons.md` (sección de troubleshooting).
4. Comprobar si hay resultados hoy en `manual_ai_results` para ese `project_id`.
5. Si todo OK pero no hay resultados, lanzar el cron manualmente.

### "Las keywords de un proyecto se quedaron a medias"

Posible causa: agotamiento de cuota durante el run. Comprobar:
- `manual_ai_results` para ese día (cuántas keywords se llegaron a procesar).
- `manual_ai_events` con `event_type='manual_analysis_quota_exceeded'`.
- `users.quota_used` vs `users.quota_limit`.

### "El cron Manual AI no se está ejecutando"

Confirmar **en Railway** qué disparador está activo:
- Si Procfile `cron:` worker → mirar logs del worker.
- Si endpoint HTTP → mirar logs de la app filtrando `cron_start` / `cron_projects_found`.
- Si nada de lo anterior → **crear un Bun service** análogo al de Quota Reset (esto es deuda conocida).

### "Hay un AIO que detecta el sistema pero no captura references"

Probablemente es un AIO collapsed sin `page_token`. Mirar `raw_serp_data` del resultado — si `requires_additional_request=true` pero `page_token=null`, SerpAPI no nos da herramienta para abrirlo. Es un caso aceptado actualmente (~12% de AIOs).

---

## 14. Tests y diagnóstico

### Scripts de auditoría (no son tests con asserts)

| Archivo | Cubre |
|---|---|
| `check_manual_ai_system.py` | Smoke check del sistema. |
| `diagnose_cron_skip.py` | Investigar por qué el cron saltó algún proyecto (genérico, también LLM). |

> Los scripts de auditoría/verificación del refactor (`audit_manual_ai_system.py`, `verify_manual_ai_refactoring.py`, `verify_manual_ai_js.sh`, `manual_ai/check_refactoring_status.py`) y el test de caracterización del blueprint (`tests/test_manual_ai_contract.py`) se eliminaron (último limpiado en commit 91a0f7a).

### Lo que NO está cubierto

- Lógica de detección AIO (`detect_ai_overview_elements`).
- Expansión collapsed.
- Parser de references.
- Cálculos de visibility / share-of-voice.
- Validaciones de competidores.
- Cluster classification.
- Idempotencia de `manual_ai_results`.

### Recomendación

Empezar a añadir tests unitarios reales (con `DATABASE_URL` env var, sin credenciales hardcodeadas) al menos para `detect_ai_overview_elements` y `_analyze_keyword`.

---

## TL;DR

1. **Manual AI = SerpAPI google + parser AIO + ranking dominios.** No es AI Mode (otro engine) ni LLM Monitoring (otros providers).
2. **Cron secuencial sin timeout.** Riesgo conocido: un proyecto colgado bloquea todo. Advisory lock protege contra concurrencia.
3. **Idempotencia por UNIQUE `(project_id, keyword_id, analysis_date)`.** No duplica nunca, sobreescribe sólo en modo manual `force_overwrite`.
4. **Quota = 1 RU/keyword normal, 2 RU si AIO collapsed.** El segundo fetch reabre el AIO oculto tras "Show more".
5. **Alertas por email activas (desde 2026-06-10).** Email de resumen OK/WARNING/CRITICAL por run + detección diaria de "cron parado" (umbral 4 días).
6. **Deuda principal**: portar el patrón Bun service + parallelism + timeout que ya existe en LLM Monitoring.

---

## Historial de cambios del doc

- **2026-06-21**: Sincronizado al código actual. `statistics_service.py` y `competitor_service.py` documentados como shells que componen mixins (`_statistics/`, `_competitor/`). `manual-ai-analytics.js` documentado como barrel (~13 líneas) que reexporta 6 sub-módulos temáticos. Eliminadas las menciones a scripts/tests borrados (`audit_manual_ai_system.py`, `verify_manual_ai_refactoring.py`, `verify_manual_ai_js.sh`, `check_refactoring_status.py`, `tests/test_manual_ai_contract.py`); el dato de 36 endpoints sigue vigente. Resuelta la contradicción del TL;DR sobre alertas por email (existen desde 2026-06-10). Refrescados números de línea de los marcadores en `analysis_service.py`/`cron_service.py`.

— Fin del manual —
