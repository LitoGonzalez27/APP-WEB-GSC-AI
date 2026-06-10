# CLAUDE-llm-monitoring.md — LLM Monitoring (LLM Visibility Monitor)

> Manual del subsistema **LLM Monitoring**: monitorización diaria de la visibilidad de la marca del cliente en respuestas de **modelos LLM públicos** (ChatGPT, Claude, Gemini, Perplexity).
>
> **Es el producto principal de la app y el motor más complejo.** Más providers, más estado, más dinero en juego.
>
> Última actualización: 2026-05-08.
>
> Sistemas hermanos: ver `CLAUDE-manual-ai.md` (AI Overviews / SGE) y `CLAUDE-ai-mode.md` (Google AI Mode). El índice maestro está en `CLAUDE-INDEX.md`.

---

## Índice

1. [Visión general en 5 minutos](#1-visión-general-en-5-minutos)
2. [Diferencias con Manual AI y AI Mode](#2-diferencias-con-manual-ai-y-ai-mode)
3. [Mapa de archivos](#3-mapa-de-archivos)
4. [Modelo de datos](#4-modelo-de-datos)
5. [Modelos LLM soportados y discovery](#5-modelos-llm-soportados-y-discovery)
6. [Flujo completo de un análisis](#6-flujo-completo-de-un-análisis)
7. [Detección de marca, posición y sentimiento](#7-detección-de-marca-posición-y-sentimiento)
8. [Integración con cuotas y billing](#8-integración-con-cuotas-y-billing)
9. [Costes y pricing](#9-costes-y-pricing)
10. [Endpoints HTTP](#10-endpoints-http)
11. [Variables de entorno y constantes](#11-variables-de-entorno-y-constantes)
12. [Cron diario](#12-cron-diario)
13. [Sistema de retry (5 capas)](#13-sistema-de-retry-5-capas)
14. [Locale fidelity](#14-locale-fidelity)
15. [Frontend](#15-frontend)
16. [Modelos, prompts y clusters](#16-modelos-prompts-y-clusters)
17. [Mejoras y fixes históricos](#17-mejoras-y-fixes-históricos)
18. [Operaciones manuales y troubleshooting](#18-operaciones-manuales-y-troubleshooting)
19. [Tests](#19-tests)

---

## 1. Visión general en 5 minutos

**Qué hace para el usuario.** Para cada proyecto del usuario, el sistema lanza diariamente un conjunto fijo de **prompts** (queries) configurados a mano contra **varios LLMs públicos** (ChatGPT, Claude, Gemini, Perplexity). Recoge la respuesta cruda y analiza:

- Si la marca del cliente se menciona.
- En qué posición de la lista (con `position_source` ∈ `text` / `link` / `both`).
- Con qué sentimiento (`positive` / `negative` / `neutral` + score).
- Qué competidores se mencionan también.
- Qué URLs/fuentes cita el LLM (sources).
- Tokens consumidos y `cost_usd`.

Por (proyecto × LLM × día) se agregan métricas en `llm_monitoring_snapshots`:

- `mention_rate` (% prompts con mención).
- `avg_position`.
- `appeared_in_top3 / top5 / top10`.
- `share_of_voice` (cantidad).
- **`weighted_share_of_voice`** (ponderado por posición — pesos 2.0 / 1.5 / 1.2 / 1.0 / 0.8).
- Distribución de sentimiento.
- Coste y latencias.

**Cómo se llama en la UI.** "LLM Visibility Monitor" / "LLM Monitoring".

**URL pública.** `https://<host>/llm-monitoring`. Bloqueado para `plan='free'` (no se puede acceder al producto en absoluto).

**Reglas de oro:**

1. La fuente de pricing y modelos es **`llm_model_registry` en BD** (single source of truth). El cron `weekly_model_discovery` la actualiza.
2. El cron es **paralelo por proyecto** (`LLM_PROJECT_PARALLELISM`, default 2, prod 3) y **paralelo por tarea dentro del proyecto** (`max_workers=8`).
3. Cada proyecto tiene **timeout** (`LLM_PROJECT_TIMEOUT_MINUTES`, default 30) — un proyecto colgado se mata sin bloquear al resto.
4. **Idempotencia** por `UNIQUE(project_id, query_id, llm_provider, analysis_date)` con `INSERT ... ON CONFLICT DO UPDATE`.
5. **Lock global** del run en `llm_monitoring_analysis_runs` (un run a la vez en toda la app).
6. **Retry de 5 capas**: provider → circuit breaker → task retry → reconciliación → re-run manual.

---

## 2. Diferencias con Manual AI y AI Mode

| | LLM Monitoring | Manual AI | AI Mode |
|---|---|---|---|
| **Producto medido** | LLMs públicos (GPT/Claude/Gemini/Perplexity) | AI Overviews (SGE) | Google AI Mode |
| **Fuente de datos** | APIs directas de cada LLM | SerpAPI `google` | SerpAPI `google_ai_mode` |
| **Tablas BD** | `llm_monitoring_*` | `manual_ai_*` | `ai_mode_*` |
| **Estructura** | Proyecto → N prompts × M LLMs (cartesian) | Proyecto → N keywords | Proyecto → N keywords |
| **Coste por análisis** | 1 unidad por (prompt × LLM) | 1 RU/keyword | 1 RU/keyword |
| **Plan free puede acceder** | **No** (bloqueado) | Sí (con paywall blando) | Sí (con paywall blando) |
| **Paralelismo** | Sí (proyecto + tareas) | No | No |
| **Timeout por proyecto** | Sí | No | No |
| **Bun service Railway** | Sí (`function-bun-LLM-Monitoring`) | No | Sí |
| **Lock concurrencia** | `llm_monitoring_analysis_runs` (tabla) | `pg_try_advisory_lock(4242)` | `pg_try_advisory_lock(4243)` |
| **Coste $$ por run** | Significativo ($$ tokens LLM) | Bajo (1 SerpAPI/keyword) | Bajo (1 SerpAPI/keyword) |

LLM Monitoring es el sistema más caro y más sensible: cada run consume tokens reales facturables por OpenAI / Anthropic / Google / Perplexity. Por eso tiene la infraestructura más sofisticada (retry, circuit breaker, alertas de coste, model registry con aprobación por email).

---

## 3. Mapa de archivos

### Núcleo backend

| Archivo | Líneas | Qué contiene |
|---|---:|---|
| `services/llm_monitoring_service.py` | 2491 | Clase `MultiLLMMonitoringService`, `analyze_project`, `analyze_all_active_projects`, `analyze_brand_mention`, `_detect_position_in_list`, `_analyze_sentiment_with_llm`, `_create_snapshot`, `_calculate_weighted_mentions`. **Pieza central**. |
| `services/llm_monitoring_stats.py` | — | `LLMMonitoringStatsService.get_project_urls_ranking`. |
| `llm_monitoring_routes.py` | 8824 | Blueprint `llm_monitoring_bp` con prefijo `/api/llm-monitoring`. **Todos los endpoints viven aquí**. |
| `llm_monitoring_limits.py` | — | `LLM_PLAN_LIMITS`, `can_access_llm_monitoring`, `get_user_monthly_llm_usage`, `get_upgrade_options`. |

### Providers

| Archivo | Qué contiene |
|---|---|
| `services/llm_providers/base_provider.py` | Clase abstracta + `get_model_pricing_from_db`, `get_current_model_for_provider`, `extract_urls_from_text`. |
| `services/llm_providers/openai_provider.py` | OpenAI. Fallback `gpt-5.4`. Soporta `max_completion_tokens` (gpt-5/o1) y `max_tokens` (legacy). Fallback a gpt-4o ante fallos. Respeta `OPENAI_PREFERRED_MODEL`. |
| `services/llm_providers/anthropic_provider.py` | Anthropic. Fallback `claude-sonnet-4-6`. |
| `services/llm_providers/google_provider.py` | Gemini. |
| `services/llm_providers/perplexity_provider.py` | Perplexity. Fallback `sonar-pro`. Normalizador legacy → actual. `web_search_options.user_location`. |
| `services/llm_providers/provider_factory.py` | `LLMProviderFactory.create_provider`, `create_all_providers`. |
| `services/llm_providers/locale_helpers.py` | `LocaleContext`, `LANGUAGE_NAMES`, `COUNTRY_NAMES`, `COUNTRY_NAMES_LOCALIZED`, `create_locale_context`, `build_system_instruction`. |
| `services/llm_providers/retry_handler.py` | `with_retry` decorator, `CircuitBreaker` (singleton global), `RetryConfig`, `classify_error`, `with_timeout`, `RetryMetrics`. |

### Cron y schedule

| Archivo | Qué contiene |
|---|---|
| `daily_llm_monitoring_cron.py` | Script standalone (legacy). |
| `llm_monitoring_cron_function.js` | **Bun function** que dispara `POST /api/llm-monitoring/cron/daily-analysis?async=1` y envía alertas por email si hay error. **Es lo que ejecuta producción.** |
| `project_timeout.py` | `run_project_with_timeout` — daemon thread + `join(timeout)`. |
| `cron_alerts.py` | `check_and_send_cron_alerts` (alertas de duración / error rate / cost spike). |

### Model discovery

| Archivo | Qué contiene |
|---|---|
| `weekly_model_discovery_cron.py` | Clase `ModelDiscoveryService`. Descubrimiento por API + email de aprobación. |
| `weekly_model_check_cron.py` | Variante adicional. |
| `llm_model_discovery_cron_function.js` | Bun function. |
| Endpoint `POST /api/llm-monitoring/cron/model-discovery` | (`llm_monitoring_routes.py:7982`) Versión v2 con flujo de aprobación por token. |

### Migraciones / setup

`create_llm_monitoring_tables.py`, `migrate_llm_brand_fields.py`, `migrate_competitors_structure.py`, `migrate_llm_add_country.py`, `migrate_quota_pause_fields.py`, `add_prompt_clusters_to_llm_monitoring.py`, `migrate_add_sources_field.py`, `migrate_add_position_source.py`, `migrate_add_error_fields.py`, `migrate_add_weighted_sov.py`, `migrate_llm_execution_metadata.py`, `migrate_llm_enterprise_support.py`, `migrate_llm_prompt_limits.py`, `migrate_llm_query_min_length.py`, `migrate_llm_queries_unique_constraint.py`, `migrate_llm_model_discovery_v2.py`.

SQL: `update_llm_models_freetier_may2026.sql`, `update_llm_pricing_2026.sql`, `update_llm_models.sql`, `migrate_to_gemini_flash.sql`.

### Frontend

| Archivo | Líneas | Qué contiene |
|---|---:|---|
| `templates/llm_monitoring.html` | 2473 | Plantilla principal. |
| `static/js/llm_monitoring.js` | **8785** | Toda la lógica del frontend. |
| `static/llm-monitoring.css` | — | Estilos. |
| `static/llm-monitoring-enhanced.css` | — | Estilos extra. |
| `static/sov-metrics-ui.css` | — | Toggle weighted/standard SoV. |

### Diagnóstico y fix scripts

`diagnose_llm_queries.py`, `diagnose_llm_providers.py`, `diagnose_llm_mention_detection.py`, `check_llm_models_config.py`, `check_llm_project_config.py`, `check_llm_tables.py`, `fix_llm_models.py`, `fix_llm_project_3_config.py`, `fix_openai_incomplete_analysis.py`, `fix_openai_model.py`, `fix_openai_monitoring.py`, `update_models_now.py`, `update_to_gpt53_chat.py`, `update_current_llm_models.py`, `configure_gpt5.py`, `admin_fix_llm_models.py`.

### Tests

`test_llm_cron_jobs.py`, `test_llm_monitoring_endpoints.py`, `test_llm_monitoring_frontend.py`, `test_llm_monitoring_service.py`, `test_llm_providers.py`, `test_all_llm_providers.py`, `test_locale_fidelity.py`, `test_project_parallelism.py`, `test_project_timeout.py`.

### Documentos `.md` históricos

`MEJORAS_LLM_MONITORING.md`, `FIX_DISCREPANCIA_MENCIONES_LLM.md`, `OPTIMIZACION_CRON_DIARIO.md`, `SOLUCION_OPENAI_GPT5.md`, `SOLUCION_QUERIES_INCOMPLETAS.md`, `IMPLEMENTACION_RETRY.md`, `IMPLEMENTACION_RETRY_SYSTEM.md`, `ANALISIS_RETRY_SYSTEM.md`, `ELIMINACION_ANALISIS_MANUAL.md`. Resumen en §17.

---

## 4. Modelo de datos

### `llm_monitoring_projects`

```
id                     SERIAL PK
user_id                FK users(id) ON DELETE CASCADE
name                   VARCHAR              -- UNIQUE(user_id, name)
brand_name             VARCHAR
industry               VARCHAR
enabled_llms           TEXT[]               -- default ['openai','anthropic','google','perplexity']
competitors            JSONB                -- legacy
language               VARCHAR
country_code           VARCHAR(2) DEFAULT 'ES'
queries_per_llm        INTEGER              -- 5..5000
is_active              BOOLEAN
last_analysis_date     DATE
created_at, updated_at TIMESTAMP
-- migraciones posteriores:
brand_domain           VARCHAR(255)
brand_keywords         JSONB
competitor_domains     JSONB
competitor_keywords    JSONB
selected_competitors   JSONB                -- estructura unificada [{id, domain, keywords[]}]
prompt_clusters        JSONB                -- {enabled, clusters:[{name}]}
is_paused_by_quota     BOOLEAN
paused_until           TIMESTAMP
paused_at              TIMESTAMP
paused_reason          TEXT
```

### `llm_monitoring_queries`

```
id              SERIAL PK
project_id      FK CASCADE
query_text      TEXT
language        VARCHAR
query_type      VARCHAR    -- 'general' | 'with_brand' | 'with_competitor'
topic_cluster   TEXT NULL  -- cluster asignado
is_active       BOOLEAN
added_at        TIMESTAMP
UNIQUE(project_id, query_text)
```

### `llm_monitoring_results`

**UNA fila por (project_id, query_id, llm_provider, analysis_date)**:

```
-- identificación:
llm_provider        VARCHAR
model_used          VARCHAR
query_text          TEXT
brand_name          VARCHAR
-- detección:
brand_mentioned     BOOLEAN
mention_count       INTEGER
mention_contexts    TEXT[]
-- posición:
appears_in_numbered_list  BOOLEAN
position_in_list    INTEGER
total_items_in_list INTEGER
position_source     VARCHAR(10)  -- 'text' | 'link' | 'both'
-- sentimiento:
sentiment           VARCHAR
sentiment_score     DECIMAL(3,2)
-- competidores:
competitors_mentioned JSONB
-- respuesta cruda:
full_response       TEXT
response_length     INTEGER
-- sources:
sources             JSONB        -- [{url, provider}, ...]
-- performance:
tokens_used, input_tokens, output_tokens INTEGER
cost_usd            DECIMAL(10,6)
response_time_ms    INTEGER
-- errores:
has_error           BOOLEAN
error_message       TEXT
-- locale audit:
execution_metadata  JSONB
prompt_version      VARCHAR
created_at          TIMESTAMP
UNIQUE(project_id, query_id, llm_provider, analysis_date)
```

### `llm_monitoring_snapshots`

Agregado diario por LLM. **UNIQUE(project_id, llm_provider, snapshot_date)**.

```
total_queries, total_mentions, mention_rate
avg_position
appeared_in_top3, appeared_in_top5, appeared_in_top10
total_competitor_mentions
share_of_voice
competitor_breakdown        JSONB
weighted_share_of_voice     DECIMAL(5,2)
weighted_competitor_breakdown JSONB
positive_mentions, neutral_mentions, negative_mentions
avg_sentiment_score
avg_response_time_ms
total_cost_usd
total_tokens
created_at
```

### `llm_model_registry` — single source of truth de modelos y precios

```
llm_provider, model_id              -- UNIQUE
model_display_name
cost_per_1m_input_tokens            DECIMAL
cost_per_1m_output_tokens           DECIMAL
max_tokens, max_output_tokens       INTEGER
supports_vision, supports_functions BOOLEAN
model_category                      VARCHAR
knowledge_cutoff_*                  *
is_current                          BOOLEAN  -- el "actual" del provider
is_available                        BOOLEAN
-- flujo aprobación v2:
pending_approval                    BOOLEAN
approval_token                      VARCHAR
approval_token_expires_at           TIMESTAMP
pre_switch_validated                BOOLEAN
detected_at, last_used_at           TIMESTAMP
total_queries, total_tokens_consumed, total_cost  -- contadores
```

### `llm_model_changelog`

Historial de cambios de modelos (`change_type`, `changed_by`, `reason`, `metadata JSONB`).

### `llm_monitoring_analysis_runs` — lock global del cron

Tabla en `database.py:423`. Gestionada por `acquire_analysis_lock` / `release_analysis_lock` / `get_latest_analysis_run`.

```
id                  BIGSERIAL PK
started_at          TIMESTAMPTZ
completed_at        TIMESTAMPTZ
status              VARCHAR  -- 'running' | 'completed' | 'failed'
total_projects, successful_projects, failed_projects, total_queries  INTEGER
error_message       TEXT
triggered_by        VARCHAR  -- 'cron' | 'manual' | 'api'
```

### Vista `llm_visibility_comparison`

Vista pivot que compara `mention_rate` por proveedor y devuelve best/worst LLM para una marca.

### `user_llm_api_keys` — definida pero NO usada

Tiene campos para keys cifradas, presupuesto mensual, etc. **El modelo de negocio actual usa API keys globales del operador** (vía env vars), no per-user. Tabla queda como código muerto.

---

## 5. Modelos LLM soportados y discovery

### Proveedores

`LLM_PROVIDERS = ['openai', 'anthropic', 'google', 'perplexity']` (en `llm_monitoring_limits.py:16`).

### Modelos activos (post `update_llm_models_freetier_may2026.sql`, 2026-05-05)

Alineados con free tiers de cada LLM-app:

| Provider | Modelo | $/1M input | $/1M output |
|---|---|---:|---:|
| **OpenAI** | `gpt-5.3-chat-latest` | $1.75 | $14.00 |
| **Anthropic** | `claude-sonnet-4-6` | $3.00 | $15.00 |
| **Google** | `gemini-3-flash-preview` | $0.50 | $3.00 |
| **Perplexity** | `sonar` | $1.00 | $1.00 |

### Fallbacks hardcoded (cuando BD no devuelve current)

- OpenAI → `gpt-5.4`.
- Anthropic → `claude-sonnet-4-6`.
- Perplexity → `sonar-pro`.
- OpenAI también respeta `OPENAI_PREFERRED_MODEL` env var.

### Selección

`BaseLLMProvider.__init__` usa, en orden:

1. Parámetro `model` (si se pasa explícito).
2. `get_current_model_for_provider(provider)` (lee `is_current=TRUE` en `llm_model_registry`).
3. Fallback hardcoded.

### Free tier vs paid

**No hay restricción a nivel de modelo por usuario en LLM Monitoring**. El plan **free** simplemente **no puede acceder al producto en absoluto** (`LLM_ALLOWED_PLANS = ['basic','premium','business','enterprise']`).

El `update_llm_models_freetier_may2026.sql` lo que hace es elegir como "current" globalmente los modelos que mejor reflejan **lo que ven los usuarios free de cada LLM-app** (para no medir un GPT-5 caro si los usuarios reales del cliente ven GPT-5-chat-latest).

### Discovery de modelos nuevos

Dos vías:

**Vía 1 — Script `weekly_model_discovery_cron.py`:**
- Clase `ModelDiscoveryService`.
- Consulta APIs de OpenAI / Google / Anthropic / Perplexity.
- Filtra por `NON_CHAT_PATTERNS = ['image','codex','embedding','tts','whisper','dall-e','vision','realtime','audio','moderation','-lite','customtools']`.
- Inserta en `llm_model_registry`.
- Si `AUTO_UPDATE_MODELS=true` → activa automáticamente.

**Vía 2 — Endpoint `POST /api/llm-monitoring/cron/model-discovery` (v2):**
- Añade flujo de aprobación por email con tokens.
- Endpoints `/models/approve` y `/models/reject` (con tokens efímeros).
- Validación pre-switch (test_connection del modelo nuevo).
- Registro en `llm_model_changelog`.

---

## 6. Flujo completo de un análisis

### 6.1 Crear proyecto (UI / API)

`POST /api/llm-monitoring/projects`. Configura:
- `name`, `brand_name`, `brand_domain`, `brand_keywords[]`, `industry`, `language`, `country_code`.
- `enabled_llms[]` — lista de providers activos.
- `selected_competitors[{domain, keywords[]}]`.
- `queries_per_llm`.

Después: añadir prompts (`POST /projects/:id/queries`), opcionalmente clusters (`PUT /projects/:id/clusters`), y disparar `POST /projects/:id/run-initial-analysis` para el primer análisis.

### 6.2 Cron diario

Bun service `function-bun-LLM-Monitoring` (Railway) → `POST /api/llm-monitoring/cron/daily-analysis?async=1` (Bearer `CRON_TOKEN`) → endpoint `trigger_daily_analysis` (`llm_monitoring_routes.py:5058`):

1. **Adquiere lock global**: `acquire_analysis_lock(triggered_by)`. Si ya hay un run activo (`status='running'` y `started_at < 30 min`) → 409 con info del run.
2. Lanza thread → `analyze_all_active_projects(api_keys=None, max_workers=10)`.
3. Al final → `release_analysis_lock(run_id, total_projects, successful, failed, total_queries)`.
4. En errores libera el lock y devuelve 500 / 409.

### 6.3 `analyze_all_active_projects` (líneas 2185-2339)

Pipeline:

1. Crea `MultiLLMMonitoringService` (instancia los 4 providers vía Factory + valida conexión).
2. Carga proyectos con `is_active=TRUE` AND `is_paused_by_quota=FALSE`.
3. **Fase 1 — eligibility filter SECUENCIAL**: para cada proyecto, `can_access_llm_monitoring(user)` (descarta plans/billing inválidos), aplica `max_projects` por usuario. Sin race conditions porque es secuencial.
4. **Fase 2 — análisis PARALELO por proyecto**: `LLM_PROJECT_PARALLELISM` (default 2, prod 3) con `ThreadPoolExecutor`. Cada proyecto se ejecuta dentro de `run_project_with_timeout` (`project_timeout.py`, `LLM_PROJECT_TIMEOUT_MINUTES` default 30).

### 6.4 `analyze_project(project_id)` (línea 1056)

Pasos:

1. Determina `analysis_date` con TZ `APP_TZ` (default `Europe/Madrid`).
2. SELECT del proyecto. Si `is_paused_by_quota` → return early.
3. SELECT del usuario, valida `can_access_llm_monitoring` y `plan_limits` (con override custom para enterprise: `custom_llm_prompts_limit`, `custom_llm_monthly_units_limit`).
4. Construye `LocaleContext` con `language` + `country_code` (ver §14).
5. Carga queries activas. Si 0 → skip. Si len > `max_prompts_per_project` → error `prompt_limit_exceeded`.
6. Filtra `enabled_llms` ∩ providers disponibles.
7. **Valida cuota mensual**: `get_user_monthly_llm_usage(user_id)` vs `max_monthly_units`. Si excede → `pause_llm_projects_for_quota` y return `llm_quota_exceeded`.
8. **Health check pre-análisis**: para cada provider activo llama `provider.test_connection()` con `LLM_HEALTHCHECK_RETRIES` (default 2) y `LLM_HEALTHCHECK_DELAY_SECONDS` (default 2). Excluye los unhealthy.
9. Selecciona sentiment analyzer (preferencia `google` > `openai` > `anthropic` > `perplexity`).
10. Parsea `selected_competitors` y construye `competitor_term_to_name` (mapa `'orange.es' → 'Orange'`).
11. Construye `tasks = [(project, query, provider) ...]`.
12. **ThreadPoolExecutor con `max_workers=8`** para tareas. Cada tarea respeta semáforo por provider (`provider_semaphores`).
13. `_execute_single_query_task`:
    - `provider.execute_query(query, locale=...)` (con `@with_retry`).
    - `analyze_brand_mention` (detalle en §7).
    - Si mencionado: `_analyze_sentiment_with_llm`.
    - INSERT/UPSERT en `llm_monitoring_results`.
14. **Sistema de retry de tareas fallidas** (líneas 1488-1562): 2 reintentos con delays 3s, 6s.
15. **Snapshot por LLM** (`_create_snapshot`): calcula métricas agregadas y `weighted_share_of_voice`. Upserta en `llm_monitoring_snapshots`.
16. UPDATE `last_analysis_date` en proyecto.
17. Devuelve dict con `completeness_by_llm`, `incomplete_llms`, `all_queries_analyzed`.

---

## 7. Detección de marca, posición y sentimiento

### Detección de marca (`analyze_brand_mention`, línea 445)

- Usa `brand_variations` (de `brand_domain` + `brand_keywords`, fallback a `brand_name`) — `extract_brand_variations` viene de `services/ai_analysis.py`.
- **Búsqueda con regex `\b...\b`** con y sin acentos (`remove_accents`).
- **Detección en sources/URLs**: si la marca no está en texto pero `brand_domain` aparece en `source.url` (host normalizado), marca como mencionada.
- **`position_source`**:
  - `text`: sólo en texto.
  - `link`: sólo en URL citada — asigna posición **15** por defecto.
  - `both`: en ambos.
- Detecta competidores en texto **y** en URLs citadas.
- Agrupa competidores bajo `competitor_term_to_name` (orange.es + orange → "Orange").

### Detección de posición (`_detect_position_in_list`, línea 698)

Patrones explícitos:

- Listas numeradas con regex que **requieren inicio de línea** (evita falso positivo de "(2025)" como posición).
- Ordinales multiidioma EN/ES/FR/DE/IT/PT.
- Bullets.
- Filtro `MAX_VALID_POSITION = 30`.

> ⚠️ Eliminado el patrón de referencias `[1]`/`(1)` porque causaba falsos positivos con citaciones bibliográficas.

**Inferencia contextual** si no hay lista explícita: posición 1/3/5/8/12 según ubicación relativa de la mención en el texto.

### Sentimiento (`_analyze_sentiment_with_llm`, línea 894)

- Pide a Gemini analizar contextos en JSON: `{sentiment, score}`.
- Fallback a keywords multiidioma (`_analyze_sentiment_keywords`).

A diferencia de AI Mode (que sólo usa keywords inglesas), aquí el sentimiento usa **un LLM real** (Gemini) y soporta cualquier idioma del prompt.

---

## 8. Integración con cuotas y billing

### Acceso al producto

`llm_monitoring_limits.LLM_ALLOWED_PLANS = ['basic','premium','business','enterprise']` y `LLM_ALLOWED_STATUSES = ['active','trialing','beta']`. **El plan free no puede acceder.** Admin siempre puede.

Decorador: `enforce_llm_access` (`llm_monitoring_routes.py:101`).

### Cuotas por plan (`LLM_PLAN_LIMITS`)

| Plan | max_projects | max_prompts_per_project | max_monthly_units |
|---|---:|---:|---:|
| **basic** | 1 | 20 | 640 |
| **premium** | 3 | 30 | 2880 |
| **business** | 5 | 60 | 9600 |
| **enterprise** | None | None | None |

Enterprise puede sobrescribir con `users.custom_llm_prompts_limit` y `users.custom_llm_monthly_units_limit`.

### Unidad de consumo

**1 unidad = 1 prompt × 1 LLM** (un row insertado en `llm_monitoring_results`).

`get_user_monthly_llm_usage(user_id)` cuenta filas en `llm_monitoring_results` para los proyectos del usuario, en ventana basada en `users.quota_reset_date - interval_days` (default 30) o `current_period_start/end`.

### Pausa por cuota

En `analyze_project`, si al validar units `used + expected > max_units`:
- `database.pause_llm_projects_for_quota(user_id, paused_until, reason='quota_exceeded')`.
- Marca **todos los proyectos LLM** del usuario con `is_paused_by_quota=TRUE`.
- Devuelve error sin ejecutar nada.

Es **proyecto-completo, no por prompt** (a diferencia de Manual AI / AI Mode que pueden parar a mitad de un proyecto).

### Despausa

`resume_quota_pauses_for_user(user_id)` — llamado desde el webhook Stripe `invoice.payment_succeeded` y el cron quota-reset (ver `CLAUDE-stripe-cuotas-crons.md`). Limpia `is_paused_by_quota` en proyectos de Manual AI y LLM (no AI Mode todavía — verificar).

---

## 9. Costes y pricing

### Single source of truth

Tabla `llm_model_registry`, columnas `cost_per_1m_input_tokens` / `cost_per_1m_output_tokens`. Función `get_model_pricing_from_db(provider, model_id)` (en `base_provider.py:70`) las lee y convierte a "por token".

Al inicializar cada provider, se cachea en `self.pricing`.

### Cálculo

Cada provider calcula:

```
cost_usd = input_tokens * pricing['input'] + output_tokens * pricing['output']
```

y lo devuelve en el dict de respuesta. Se persiste en `llm_monitoring_results.cost_usd` y se agrega en `llm_monitoring_snapshots.total_cost_usd`.

### Uso por `cron_alerts.py`

Función `_check_cost_spike` consulta:

```sql
SUM(cost_usd) FROM llm_monitoring_results
WHERE created_at::date = CURRENT_DATE
```

vs **media móvil 7d** (excluyendo hoy). Si hoy > `multiplier × media` (default 2x) → alerta.

> ⚠️ **No se localiza llamada a `check_and_send_cron_alerts(run_id)` desde el cron LLM actual.** El sistema de alertas de duración / error rate / cost spike está implementado en `cron_alerts.py` pero **no se dispara automáticamente** tras cada run. El Bun service sólo envía email puntual de fallo del cron a `/cron/alert`. Esta es **deuda técnica conocida**.

---

## 10. Endpoints HTTP

Todos bajo prefijo `/api/llm-monitoring`. Decoradores: `@login_required`, `@validate_project_ownership`, `@cron_or_auth_required`, y middleware `enforce_llm_access` (excepto `/cron/*` y `/health`).

### UI / proyectos

| URL | Método | Línea |
|---|---|---:|
| `/projects` | GET (lista) | 393 |
| `/projects` | POST (crear) | 595 |
| `/usage` | GET | 581 |
| `/projects/<id>` | GET | 789 |
| `/projects/<id>` | PUT | 1416 |
| `/projects/<id>` | DELETE (soft) | 1715 |
| `/projects/<id>/activate` | PUT | 1652 |
| `/projects/<id>/deactivate` | PUT | 1604 |
| `/projects/<id>/queries` | POST (bulk add) | 1805 |
| `/projects/<id>/queries/<query_id>` | DELETE | 1958 |
| `/projects/<id>/queries` | GET | 3941 |
| `/projects/<id>/queries/suggest` | POST (Gemini IA) | 2801 |
| `/projects/<id>/queries/suggest-variations` | POST | 2907 |
| `/projects/<id>/run-initial-analysis` | POST | 3132 |
| `/projects/<id>/metrics` | GET | 3259 |
| `/projects/<id>/comparison` | GET | 3603 |
| `/projects/<id>/share-of-voice-history` | GET (`?metric=weighted\|normal`) | 4185 |
| `/projects/<id>/urls-ranking` | GET | 3529 |
| `/projects/<id>/responses` | GET (inspección manual) | 5272 |
| `/projects/<id>/queries/<qid>/history` | GET | 2655 |
| `/projects/<id>/export/excel` | GET | 5421 |
| `/projects/<id>/export/pdf` | GET | 6560 |

### Clusters

| URL | Método | Línea |
|---|---|---:|
| `/projects/<id>/clusters` | GET | 2068 |
| `/projects/<id>/clusters` | PUT | 2130 |
| `/projects/<id>/clusters/rename` | POST | 2214 |
| `/projects/<id>/queries/<qid>/cluster` | PUT | 2303 |
| `/projects/<id>/queries/bulk-cluster` | POST | 2384 |
| `/projects/<id>/clusters/metrics` | GET | 2465 |

### Modelos (admin)

| URL | Método | Línea |
|---|---|---:|
| `/models` | GET | 4807 |
| `/models/current` | GET | 4877 |
| `/models/<model_id>` | PUT | 4961 |
| `/models/approve` | GET (token) | 8404 |
| `/models/reject` | GET (token) | 8538 |
| `/models/changelog` | GET | 8650 |

### Cron

| URL | Método | Línea | Auth |
|---|---|---:|---|
| `/cron/daily-analysis?async=1&project_id=N` | POST | 5058 | Bearer CRON_TOKEN |
| `/cron/model-discovery?notify_email=&auto_update=` | POST | 7982 | Bearer |
| `/cron/alert` | POST | 8717 | — |

### Salud

| URL | Método | Línea |
|---|---|---:|
| `/health` | GET | 5222 |

### UI (fuera del blueprint)

| URL | Handler | Archivo |
|---|---|---|
| `/llm-monitoring` | `llm_monitoring_page` | `app.py:3894` |

---

## 11. Variables de entorno y constantes

### API keys (globales)

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GOOGLE_API_KEY` (o `GOOGLE_AI_API_KEY`)
- `PERPLEXITY_API_KEY`

### Concurrencia / paralelismo

| Variable | Default | Para qué sirve |
|---|---|---|
| `LLM_PROJECT_PARALLELISM` | 2 (prod 3) | Proyectos en paralelo dentro del cron. |
| `LLM_PROJECT_TIMEOUT_MINUTES` | 30 | Timeout por proyecto. |
| `OPENAI_CONCURRENCY` | 2 | Semáforo OpenAI. |
| `GOOGLE_CONCURRENCY` | 3 | Semáforo Google. |
| `ANTHROPIC_CONCURRENCY` | 3 | Semáforo Anthropic. |
| `PERPLEXITY_CONCURRENCY` | 4 | Semáforo Perplexity. |
| `OPENAI_TIMEOUT` | 90 | Timeout request OpenAI. |
| `GOOGLE_TIMEOUT` | 30 | Timeout request Google. |
| `ANTHROPIC_TIMEOUT` | 60 | Timeout request Anthropic. |
| `PERPLEXITY_TIMEOUT` | 45 | Timeout request Perplexity. |

### Health check / retry

| Variable | Default | Para qué sirve |
|---|---|---|
| `LLM_HEALTHCHECK_RETRIES` | 2 | Reintentos del health check pre-análisis. |
| `LLM_HEALTHCHECK_DELAY_SECONDS` | 2 | Delay entre health checks. |
| `CIRCUIT_BREAKER_THRESHOLD` | 3 | Failures consecutivos antes de abrir el breaker. |
| `CIRCUIT_BREAKER_COOLDOWN` | 120 | Segundos en estado OPEN. |

### Otros

| Variable | Default | Para qué sirve |
|---|---|---|
| `OPENAI_PREFERRED_MODEL` | (none) | Fuerza un modelo OpenAI específico. |
| `APP_TZ` | `Europe/Madrid` | Timezone para `analysis_date`. |
| `CRON_TOKEN` | (oblig.) | Bearer compartido. |
| `APP_URL` | (oblig.) | URL pública (Bun). |
| `CRON_ALERT_EMAIL` o `MODEL_DISCOVERY_EMAIL` | — | Destinatario alertas. |
| `AUTO_UPDATE_MODELS` | false | Auto-activar nuevos modelos descubiertos. |
| `QUOTA_RESET_INTERVAL_DAYS` | 30 | Ventana de cómputo de cuota mensual. |

---

## 12. Cron diario

### Definición Railway

En `railway.json` hay tanto un cron Python (`0 4 * * *` ejecuta `daily_llm_monitoring_cron.py`) como una function Bun (`0 5 * * *`, `llm_monitoring_cron_function.js`).

> Según `CLAUDE-stripe-cuotas-crons.md`, **los crons Python no se ejecutan en este proyecto**. La fuente real es el Bun service.

### Bun service

Hace `POST {APP_URL}/api/llm-monitoring/cron/daily-analysis?async=1` con `Authorization: Bearer ${CRON_TOKEN}` y timeout 60s (espera la respuesta 202).

### Endpoint `trigger_daily_analysis` (`llm_monitoring_routes.py:5058`)

- Lee `?async=1` y `?project_id=N` (modo single project).
- **Modo `project_id`**: invoca `service.analyze_project` directamente, sin lock global (re-runs).
- **Modo all-projects + async**: `acquire_analysis_lock(triggered_by)`. Si ya hay un run activo → 409. Si OK, dispara thread → `analyze_all_active_projects(api_keys=None, max_workers=10)` → `release_analysis_lock(...)`.
- **Modo all-projects + sync**: idéntico pero retorna 200 al terminar.
- En errores libera el lock y devuelve 500 / 409.

### Filtros de elegibilidad

**Paso 1 secuencial** (en `analyze_all_active_projects`):
- `can_access_llm_monitoring(user)` → plan/billing válidos.
- `max_projects` por plan no excedido.

**Paso 2 (dentro de `analyze_project`)**:
- `is_paused_by_quota=TRUE` → skip.
- 0 queries activas → skip.
- > `max_prompts_per_project` → error.
- > `max_monthly_units` → pause + skip.

### Estructura 2 fases

1. **Fase 1 secuencial** — filter eligibility (mutación de `user_project_counts` sin race conditions).
2. **Fase 2 paralela** — `ThreadPoolExecutor(max_workers=LLM_PROJECT_PARALLELISM)` con `as_completed`, cada proyecto envuelto en `run_project_with_timeout`.

### `project_timeout.py`

Daemon thread + `join(timeout_minutes*60)`. Si timeout → devuelve:

```python
{ 'project_id': N, 'success': False, 'timed_out': True,
  'error': 'Project timeout after Xm' }
```

El thread se queda zombie (es daemon → muere con el proceso).

### Idempotencia

Por (project_id, query_id, llm_provider, analysis_date) — UNIQUE constraint en `llm_monitoring_results` con `INSERT ... ON CONFLICT DO UPDATE`. Si el cron se ejecuta dos veces el mismo día, los resultados se sobrescriben en lugar de duplicar.

El lock `acquire_analysis_lock` evita ejecuciones simultáneas del run completo.

### Registro de run

`llm_monitoring_analysis_runs` con `status` running/completed/failed, contadores y `triggered_by`.

### Alertas

Como se mencionó en §9: el sistema de alertas de duración / error rate / cost spike (`cron_alerts.py`) **existe pero NO se dispara automáticamente** desde el cron LLM. Sólo se envía email puntual si el Bun service falla al hacer el POST inicial.

---

## 13. Sistema de retry (5 capas)

Documentado en `IMPLEMENTACION_RETRY.md`, `IMPLEMENTACION_RETRY_SYSTEM.md`, `ANALISIS_RETRY_SYSTEM.md`.

```
┌─────────────────────────────────────────────────────────────┐
│ CAPA 1 — @with_retry (decorador en retry_handler.py:240)    │
│  ─ Aplicado en cada execute_query de cada provider          │
│  ─ Consulta circuit_breaker antes de la llamada             │
│  ─ classify_error → rate_limit / timeout / server / network │
│                    / non_retryable / quota_exhausted        │
│  ─ Bucle de reintentos según RetryConfig.RETRYABLE_ERRORS   │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│ CAPA 2 — Circuit Breaker                                    │
│  ─ Estados CLOSED / OPEN / HALF_OPEN                        │
│  ─ Failure threshold 3, cooldown 120s                       │
│  ─ Cuando OPEN se rechaza inmediatamente                    │
│  ─ Tras cooldown → HALF_OPEN para probar 1 request          │
│  ─ Compartido entre todos los threads (singleton)           │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│ CAPA 3 — Retry de tareas fallidas (analyze_project)          │
│  ─ Líneas 1488-1562                                         │
│  ─ 2 reintentos extra con delays 3s, 6s                     │
│  ─ Antes eran 4 reintentos con 5s/10s/20s/30s; reducido en  │
│    OPTIMIZACION_CRON_DIARIO.md porque el provider ya retoma │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│ CAPA 4 — Reconciliación post-análisis                       │
│  ─ daily_llm_monitoring_cron.py:135                         │
│  ─ Si proyectos con incomplete_llms:                        │
│    fuerza OPENAI_CONCURRENCY=1, GOOGLE_CONCURRENCY=3        │
│    y reanaliza con max_workers=5                            │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│ CAPA 5 — Single project re-run manual                       │
│  ─ POST /cron/daily-analysis?project_id=N&async=1           │
└─────────────────────────────────────────────────────────────┘
```

### Manejo especial de `quota_exhausted`

Mensajes con `"per_day"`, `"retry in Xh"`, `"quota exhausted"`:
- Fuerza apertura del circuit breaker.
- Return inmediato sin más reintentos (no merece la pena reintentar inmediatamente algo que dice "vuelve mañana").

### Health check pre-análisis

Excluye providers no saludables del análisis del proyecto entero (no se intenta usarlos). Reduce el pool de tareas y evita fallos masivos.

### `RetryConfig.RETRYABLE_ERRORS` (delays exponenciales)

| Tipo | Max retries | Delays |
|---|---:|---|
| rate_limit | 2 | 5s / 30s |
| timeout | 2 | 1s / 10s |
| server_error | 2 | 3s / 20s |
| network | 2 | 1s / 10s |
| non_retryable | 0 | — |
| quota_exhausted | 0 | abre breaker |

---

## 14. Locale fidelity

Implementado en 2026-04-08. Cada provider recibe la **query raw + locale aparte** y aplica su mecanismo nativo:

| Provider | Mecanismo de locale |
|---|---|
| **OpenAI** | System message en el role `system`. |
| **Anthropic** | System message en el campo `system`. |
| **Perplexity** | System message + `web_search_options.user_location`. |
| **Gemini** | Prepended block (no tiene system role nativo). |

`LocaleContext` se construye con `language` + `country_code` del proyecto. `build_system_instruction` genera el texto del system message en el idioma de destino.

`COUNTRY_NAMES_LOCALIZED` traduce el país al idioma del prompt (ej. "España" en español, "Spain" en inglés).

Test: `test_locale_fidelity.py` verifica que cada provider aplica el locale correctamente.

> ⚠️ Antes de este fix se usaba `execute_query("Hi")` para health check, lo que disparaba el retry chain y fallback gpt-5→gpt-4o innecesariamente. Ahora `test_connection()` es ligero y no dispara nada.

---

## 15. Frontend

### Plantilla principal

`templates/llm_monitoring.html` (2473 líneas). Estructura:

- Header con `nav-tabs` (sólo tab "Projects").
- `#projectsTab` — grid de proyectos.
- `#metricsSection` — vista detalle de proyecto: header con time-filter global (7/14/30/60/90 días), botones Manage Prompts / Models / Edit / Delete.

### Charts (Chart.js)

- Mention Rate.
- Share of Voice (timeline).
- Mentions Timeline.
- Sentiment Distribution.
- Share of Voice Donut.
- Clusters Performance.

### Tablas (GridJS)

- Comparison.
- Queries/Prompts (`#queriesTable`).
- URLs Ranking (`#urlsContainerLLM`).
- Responses (`#responsesContainer`).

### Modales

- Prompts Management Modal (con tabs Prompts / Clusters).
- SoV Info Modal.
- Models Info.
- Knowledge Cutoff.
- AI Suggestions.
- Project edit/create.

### Banners

- `#llmModelScopeBanner` — scope de modelo.
- Banner de acceso compartido.

### JS

`static/js/llm_monitoring.js` (8785 líneas) — clase principal `window.llmMonitoring` con métodos:

- `renderShareOfVoiceChart`, `renderShareOfVoiceDonutChart`.
- `renderMentionRateChart`, `renderMentionsTimelineChart`.
- `renderSentimentDistributionChart`, `renderClustersPerformanceChart`.
- `loadQueryHistoryChart`.
- `comparisonGrid`, `queriesGrid`.
- `showPromptsManagementModal`, `switchPromptsTab`.

Usa **gridjs** para tablas y **Chart.js** para gráficos.

### CSS

- `static/llm-monitoring.css`.
- `static/llm-monitoring-enhanced.css`.
- `static/sov-metrics-ui.css` (toggle weighted/standard).

### Brand Radar

> **No es parte del módulo LLM Monitoring.** "Brand Radar" en este repo se refiere a las herramientas MCP de Ahrefs (servicio externo independiente), no al módulo LLM. No hay integración entre ambos.

---

## 16. Modelos, prompts y clusters

### Estructura

Un proyecto tiene:
- **N prompts** (`llm_monitoring_queries`).
- **M modelos LLM** en `enabled_llms`.

El análisis hace **cartesian product N × M tareas** por día. Cada tarea persiste 1 fila en `llm_monitoring_results`.

### Prompt Clusters

Añadido por `add_prompt_clusters_to_llm_monitoring.py`. Configuración a nivel proyecto en `llm_monitoring_projects.prompt_clusters JSONB`:

```json
{
  "enabled": true,
  "clusters": [{ "name": "Branded queries" }, { "name": "Comparison" }]
}
```

Cada query puede asignarse a un cluster vía `llm_monitoring_queries.topic_cluster TEXT NULL`. La asignación valida que el nombre exista en la config del proyecto antes de aceptarlo (`_sanitize_prompt_clusters_config`, `_normalize_cluster_name`).

Endpoints: `GET/PUT /clusters`, `rename`, `bulk-cluster`, `metrics`.

### Topic Clusters vs Prompt Clusters

- **LLM Monitoring**: `topic_cluster` (singular, en queries) + `prompt_clusters` (config en project).
- **Manual AI**: `topic_clusters` distinto (`add_topic_clusters_field.py`).

Son conceptualmente lo mismo; nombres distintos por motivos históricos.

### Visualización agrupada

El chart "Clusters Performance" muestra `mention_rate` / SoV agregado por cluster. Endpoint `/projects/<id>/clusters/metrics` devuelve la agregación.

### Tipos de prompt automáticos

`query_type` ∈ `general` / `with_brand` / `with_competitor`. Sólo se usa cuando se generan vía `generate_queries_for_project`. Los user-added quedan en `general`.

### Sugerencia con IA

`generate_query_suggestions_with_ai` (línea 2346):
- Usa **Gemini Flash** con prompt en inglés.
- Output en idioma destino del proyecto.
- Evita duplicados con queries existentes.
- Valida longitud (15-500 chars).

Endpoint: `POST /projects/<id>/queries/suggest`.

---

## 17. Mejoras y fixes históricos

### `MEJORAS_LLM_MONITORING.md` (Nov 2025)

- Añadió `weighted_share_of_voice` (pesos 2.0/1.5/1.2/0.8 por posición) en `llm_monitoring_snapshots`.
- Mejoró detección en sources (regex de dominio completo restrictivo, evita falsos positivos tipo `kipuka` cuando la marca es `kipu`).
- UX con toggle Weighted/Standard y modal informativo.

### `FIX_DISCREPANCIA_MENCIONES_LLM.md` (Nov 2025)

Fix discrepancia entre tabla y "Brand Mentions Analysis": el endpoint `/queries` ahora unifica `text_mentions + url_citations` mediante `brand_in_text OR brand_in_urls`. Antes la tabla sumaba ambos pero "Brand Mentions Analysis" sólo contaba texto.

### `OPTIMIZACION_CRON_DIARIO.md` (Nov 2025)

- **Bug crítico**: `_save_error_result` estaba fuera de la clase.
- Reducción de `OPENAI_CONCURRENCY` (3→2), `GOOGLE_CONCURRENCY` (6→5), `max_workers` global (10→8).
- Aumentó retries (2→4) y delays (fijo 2s → 5/10/20/30s).
- Añadió pasada de reconciliación con `OPENAI_CONCURRENCY=1`.

### `SOLUCION_OPENAI_GPT5.md` (Nov 2025)

- GPT-5 ya **no acepta `max_tokens`**; ahora usa `max_completion_tokens`.
- Pricing en BD estaba mal ($15/$45 era erróneo, real $1.25/$10 — luego se actualizó a $1.75/$14 para gpt-5.3-chat-latest).
- El sistema usaba `gpt-4o` porque era el `is_current=TRUE` por error.

### `SOLUCION_QUERIES_INCOMPLETAS.md` (Nov 2025)

- Validación de completitud por LLM (`completeness_by_llm`, `incomplete_llms`, `all_queries_analyzed` en el resultado).
- Snapshots loguean warning cuando faltan queries.
- Script `diagnose_llm_queries.py` para investigar.

### `IMPLEMENTACION_RETRY*.md` / `ANALISIS_RETRY_SYSTEM.md`

- Implementación de `retry_handler.py` con `with_retry`, `CircuitBreaker`, `classify_error`, `RetryConfig`.
- Manejo especial de `quota_exhausted` que abre el circuit breaker inmediatamente.

### `ELIMINACION_ANALISIS_MANUAL.md`

Eliminó el "análisis manual" del LLM Monitoring (botón ad-hoc de re-analizar un proyecto). Ahora todo va por cron + endpoint single-project.

### Otros cambios reflejados en código

- **`LocaleContext`** (2026-04-08): cada provider recibe query raw + locale separado. Test `test_locale_fidelity.py`.
- **`test_connection()` ligero**: reemplaza `execute_query("Hi")` para health check, sin disparar retry chain ni fallback.

---

## 18. Operaciones manuales y troubleshooting

### Disparar todo el cron LLM manualmente

```bash
curl -X POST "$APP_URL/api/llm-monitoring/cron/daily-analysis?async=0" \
  -H "Authorization: Bearer $CRON_TOKEN"
```

### Re-analizar un proyecto concreto

```bash
curl -X POST "$APP_URL/api/llm-monitoring/cron/daily-analysis?project_id=N&async=1" \
  -H "Authorization: Bearer $CRON_TOKEN"
```

### Disparar discovery de modelos

```bash
curl -X POST "$APP_URL/api/llm-monitoring/cron/model-discovery?notify_email=cgonalba@gmail.com&auto_update=false" \
  -H "Authorization: Bearer $CRON_TOKEN"
```

### "Un cliente dice que LLM Monitoring no se actualiza"

1. Mirar `llm_monitoring_analysis_runs` — ¿está `status='running'` y `started_at` reciente? Si sí, esperar.
2. Si no hay run hoy: lanzar manualmente.
3. Si el run terminó pero faltan resultados: mirar `incomplete_llms` en logs y disparar reconciliación.
4. Mirar `is_paused_by_quota` en el proyecto.
5. Mirar `users.quota_used` y los `LLM_PLAN_LIMITS` (max_monthly_units).

### "Stripe ha cobrado pero LLM sigue pausado"

Ver `CLAUDE-stripe-cuotas-crons.md` (sección de troubleshooting). El webhook `invoice.payment_succeeded` debería despausar; si no, hay desincronización.

### "Detectamos un modelo nuevo en Discovery, ¿qué hacemos?"

1. Recibes email con tokens de aprobación / rechazo.
2. Pinchas en `/models/approve?token=...` para activarlo.
3. El sistema valida el modelo (test_connection) antes de marcarlo `is_current=TRUE`.
4. Próximo cron usará el modelo nuevo.

### "Coste disparado en algún día"

1. Mirar logs del cron de ese día.
2. `SELECT SUM(cost_usd) FROM llm_monitoring_results WHERE created_at::date = '2026-XX-XX' GROUP BY llm_provider`.
3. Comparar con media móvil 7d.
4. Causas típicas: modelo más caro accidentalmente activado, queries más largas, retries excesivos.

### "Un provider está fallando consistentemente"

1. Mirar logs — `circuit_breaker: True` para ese provider?
2. Si breaker abierto: esperar cooldown (120s) o forzar reset reiniciando la app.
3. Verificar que la API key es válida (`test_connection`).
4. Verificar que el modelo `is_current=TRUE` en `llm_model_registry` es válido para esa API key.

### "El cron LLM está tardando demasiado"

1. Subir `LLM_PROJECT_PARALLELISM` (cuidado: aumenta coste si hay errores que reintentan).
2. Bajar `LLM_PROJECT_TIMEOUT_MINUTES` para cortar proyectos colgados antes.
3. Bajar concurrencia de un provider problemático (`OPENAI_CONCURRENCY=1`).

---

## 19. Tests

| Archivo | Cubre |
|---|---|
| `test_llm_cron_jobs.py` | Existencia de archivos cron, sintaxis Python, configuración `railway.json`, imports críticos, helpers. |
| `test_llm_monitoring_endpoints.py` | Imports, estructura del Blueprint, presencia de funciones de endpoint, decoradores, registro en `app.py`, integración DB. |
| `test_llm_monitoring_frontend.py` | Existencia de archivos HTML/JS/CSS, estructura HTML, funciones JS, estilos CSS, ruta en `app.py`, integración API, responsive, Chart.js. |
| `test_llm_monitoring_service.py` | Tests del servicio (asumido similar al patrón). |
| `test_llm_providers.py` | Estructura providers, imports, `test_interface_implementation`, Factory pattern, helpers de BD (`get_model_pricing_from_db`, `get_current_model_for_provider`). |
| `test_all_llm_providers.py` | **Test integración real con APIs** (calls reales — cuidado, consume cuota). |
| `test_locale_fidelity.py` | Fidelidad del locale (LocaleContext aplicado correctamente por cada provider). |
| `test_project_parallelism.py` | Comportamiento de `LLM_PROJECT_PARALLELISM` (paths secuencial vs paralelo, orden preservado). |
| `test_project_timeout.py` | `run_project_with_timeout` (daemon + join, dict sintético `timed_out`). |

Adicionalmente: `test_cron_alerts.py`, `test_cron_routes.py`, `test_db_pool.py`.

---

## TL;DR

1. **LLM Monitoring = APIs de OpenAI/Anthropic/Google/Perplexity + parser de menciones + agregación SoV.** Es el producto principal y el más caro.
2. **Cron paralelo de 2 niveles**: proyectos en paralelo (`LLM_PROJECT_PARALLELISM`) y tareas en paralelo dentro del proyecto (`max_workers=8`). Con timeout por proyecto (`LLM_PROJECT_TIMEOUT_MINUTES`).
3. **Idempotencia por `(project_id, query_id, llm_provider, analysis_date)`**. Lock global vía `llm_monitoring_analysis_runs`.
4. **Retry de 5 capas**: provider → circuit breaker → task retry → reconciliación → re-run manual.
5. **`llm_model_registry` es la single source of truth** de modelos y precios. Cron weekly los descubre y los activa con flujo de aprobación por email.
6. **Quota = 1 unidad por (prompt × LLM)**. Plan free **no puede acceder al producto**.
7. **Costes reales en juego**: cada run consume tokens facturables. `cron_alerts.py` tiene detección de cost spike pero **no se dispara automáticamente** (deuda).
8. **Locale fidelity**: cada provider aplica el locale en su mecanismo nativo (system message / prepended block / web_search_options).
9. **Frontend pesado**: `llm_monitoring.js` 8785 líneas, `llm_monitoring.html` 2473 líneas, charts/tables/modals/banners.
10. **Brand Radar no es parte de LLM Monitoring** (es Ahrefs MCP externo).

— Fin del manual —
