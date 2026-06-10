# CLAUDE-ai-mode.md — AI Mode (Google AI Mode)

> Manual del subsistema **AI Mode**: monitorización de la presencia de marca en **Google AI Mode** — la respuesta generativa-conversacional que Google sirve en `google.com/ai`.
>
> Última actualización: 2026-05-08.
>
> Sistemas hermanos: ver `CLAUDE-manual-ai.md` (AI Overviews / SGE) y `CLAUDE-llm-monitoring.md` (LLMs públicos). El índice maestro está en `CLAUDE-INDEX.md`.

---

## Índice

1. [Visión general en 5 minutos](#1-visión-general-en-5-minutos)
2. [Diferencias con Manual AI y LLM Monitoring](#2-diferencias-con-manual-ai-y-llm-monitoring)
3. [Mapa de archivos](#3-mapa-de-archivos)
4. [Modelo de datos](#4-modelo-de-datos)
5. [Flujo completo de un análisis](#5-flujo-completo-de-un-análisis)
6. [Detección de marca y matching robusto](#6-detección-de-marca-y-matching-robusto)
7. [Integración con cuotas y billing](#7-integración-con-cuotas-y-billing)
8. [Endpoints HTTP](#8-endpoints-http)
9. [Variables de entorno y constantes](#9-variables-de-entorno-y-constantes)
10. [Cron diario](#10-cron-diario)
11. [Frontend](#11-frontend)
12. [Bridge con otros sistemas](#12-bridge-con-otros-sistemas)
13. [Errores históricos y deuda técnica](#13-errores-históricos-y-deuda-técnica)
14. [Operaciones manuales y troubleshooting](#14-operaciones-manuales-y-troubleshooting)
15. [Tests y diagnóstico](#15-tests-y-diagnóstico)

---

## 1. Visión general en 5 minutos

**Qué hace para el usuario.** AI Mode monitoriza si la **marca** del cliente aparece en las respuestas generativas-conversacionales de **Google AI Mode** (no es Google AI Overviews / SGE — es un producto diferente de Google). Para cada keyword del proyecto, el sistema lanza diariamente una consulta al engine `google_ai_mode` de SerpAPI y analiza la respuesta para detectar:

- Menciones de la marca en `text_blocks` (bloques de texto generados por IA) y/o en `references` (fuentes citadas).
- Posición de la mención (1-based dentro de las references; 0 si la mención está sólo en texto).
- Sentimiento aproximado (positivo / negativo / neutral) por palabras clave en el snippet.
- Total de fuentes citadas en la respuesta.
- Otros dominios y URLs citados como fuentes (para SoV de "media sources" tipo TechCrunch, Forbes…).

**Cómo se llama en la UI.** "AI Mode Monitoring" (título de la página). Internamente conviven los términos "AI Mode" y "AI Overview" como sinónimos del módulo (legado del copy reciclado de Manual AI durante la refactorización).

**URL pública.** `https://<host>/ai-mode-projects/`. Paywall para `plan='free'` salvo acceso compartido.

**Reglas de oro:**

1. La fuente de datos es **SerpAPI** con `engine="google_ai_mode"` (string literal en `analysis_service.py:362`, no es la concatenación de las constantes `SERPAPI_AI_MODE_ENGINE='google'` + `SERPAPI_AI_MODE_TYPE='ai_mode'` — esas constantes están **muertas**).
2. El cron diario es **secuencial** (sin paralelismo configurable, sin timeout por proyecto).
3. La idempotencia es por `UNIQUE(project_id, keyword_id, analysis_date)` en `ai_mode_results`.
4. Concurrencia entre runs se evita con un **PostgreSQL advisory lock** (`pg_try_advisory_lock(4243, YYYYMMDD)`).
5. Cuota = 1 RU por keyword.

---

## 2. Diferencias con Manual AI y LLM Monitoring

| | AI Mode | Manual AI | LLM Monitoring |
|---|---|---|---|
| **Producto medido** | Google AI Mode (`google.com/ai`) | AI Overviews (SGE clásico) | ChatGPT / Claude / Gemini / Perplexity |
| **Fuente de datos** | SerpAPI `engine=google_ai_mode` | SerpAPI `engine=google` | APIs directas |
| **Tablas BD** | `ai_mode_*` | `manual_ai_*` | `llm_monitoring_*` |
| **Coste por análisis** | 1 RU/keyword | 1 RU/keyword (+1 si collapsed) | 1 unidad por (prompt × LLM) |
| **Paralelismo cron** | Secuencial | Secuencial | Paralelo (`LLM_PROJECT_PARALLELISM`) |
| **Timeout por proyecto** | No | No | Sí (`project_timeout.py`) |
| **Bun service Railway** | Sí (`function-bun-AI-Mode`) | No | Sí (`function-bun-LLM-Monitoring`) |
| **Advisory lock class_id** | `4243` | `4242` | `acquire_analysis_lock` (tabla aparte) |
| **Max keywords/proyecto** | 300 | 200 | N/A (es por prompts × LLMs) |
| **Max competidores** | 10 | 4 | Ilimitado en plan enterprise |

AI Mode es estructuralmente una réplica de Manual AI (mismo patrón de blueprint, repos, services, cron, JS modular) pero con tablas distintas y engine SerpAPI diferente. **La refactorización de AI Mode reusó plantillas y comentarios de Manual AI**, de ahí los strings residuales como "Manual AI Excel" en `exports.py` y el `README.md` que empieza con `# 🤖 Manual AI Analysis System` aunque viva en `ai_mode_projects/`.

---

## 3. Mapa de archivos

### Núcleo del módulo (paquete `ai_mode_projects/`)

| Archivo | Qué contiene |
|---|---|
| `ai_mode_projects/__init__.py` | Crea el blueprint `ai_mode_bp` con `url_prefix='/ai-mode-projects'`. |
| `ai_mode_projects/config.py` | Constantes (`AI_MODE_KEYWORD_ANALYSIS_COST=1`, `MAX_KEYWORDS_PER_PROJECT=300`, `MAX_COMPETITORS_PER_PROJECT=10`, `CRON_LOCK_CLASS_ID=4243`, `EVENT_TYPES`). |
| `ai_mode_system_bridge.py` | Capa de aislamiento de import. Reexporta `ai_mode_bp` y `run_daily_analysis_for_all_ai_mode_projects()`. Si import falla → `USING_AI_MODE_SYSTEM=False` (sistema desactivado en silencio). |
| `daily_ai_mode_cron.py` | Script CLI legacy (no es lo que ejecuta producción). |

### Rutas (Flask)

| Archivo | Cubre |
|---|---|
| `ai_mode_projects/routes/projects.py` | Dashboard, CRUD proyectos, pause/resume. |
| `ai_mode_projects/routes/keywords.py` | CRUD keywords. |
| `ai_mode_projects/routes/analysis.py` | Análisis manual y trigger del cron diario. |
| `ai_mode_projects/routes/results.py` | Stats, tablas, rankings. |
| `ai_mode_projects/routes/competitors.py` | Competidores y charts comparativos. |
| `ai_mode_projects/routes/clusters.py` | Topic clusters. |
| `ai_mode_projects/routes/exports.py` | Excel. |
| `ai_mode_projects/routes/health.py` | `/api/health`. |

### Servicios (lógica)

| Archivo | Qué hace |
|---|---|
| `ai_mode_projects/services/analysis_service.py` | **Motor del análisis**. Llama SerpAPI, parsea, decide menciones, controla cuota. |
| `ai_mode_projects/services/cron_service.py` | Job diario; advisory lock por día; iteración secuencial sobre proyectos. |
| `ai_mode_projects/services/project_service.py` | CRUD/lógica de proyectos (pause/resume, ownership). |
| `ai_mode_projects/services/statistics_service.py` | Agregaciones para gráficos (visibility por día, posiciones, top domains, ranking global). |
| `ai_mode_projects/services/competitor_service.py` | Validación de competidores, charts comparativos, sync de flags históricos. |
| `ai_mode_projects/services/cluster_service.py` | Topic clusters: validación, classify, statistics. |
| `ai_mode_projects/services/domains_service.py` | `store_global_domains_detected` (escribe en `ai_mode_global_domains`). |
| `ai_mode_projects/services/export_service.py` | Excel export. |

### Repositorios

`ai_mode_projects/models/project_repository.py`, `keyword_repository.py`, `result_repository.py`, `event_repository.py`.

### Utils

`ai_mode_projects/utils/decorators.py` (`@with_backoff`), `validators.py` (`check_ai_mode_access`), `helpers.py`, `country_utils.py`.

### Cron Bun (servicio Railway)

| Archivo | Qué contiene |
|---|---|
| `ai_mode_cron_function.js` | Handler Bun que dispara `POST /ai-mode-projects/api/cron/daily-analysis?async=1` con `Authorization: Bearer $CRON_TOKEN`. Si falla, postea a `/api/llm-monitoring/cron/alert` (endpoint de LLM Monitoring reusado). |

### Migraciones / setup BD

| Archivo | Qué hace |
|---|---|
| `create_ai_mode_tables.py` | Versión local. |
| `create_ai_mode_tables_production.py` | Versión producción (mismo SQL; ⚠️ credenciales hardcodeadas). |
| `add_selected_competitors_to_ai_mode.py` | Añade `selected_competitors JSONB`. |
| `add_topic_clusters_to_ai_mode.py` | Añade `topic_clusters JSONB` + índice GIN. |
| `analyze_ai_mode_migration.py` | Diff staging vs prod (one-shot). |

> ⚠️ **No se encontró** una migración explícita para `ai_mode_global_domains` ni para los campos de pause-by-quota (`is_paused_by_quota`, `paused_until`, `paused_at`, `paused_reason`). Existen en producción (el código las usa con confianza) pero el SQL de creación no aparece en el repo. Probablemente se aplicaron manualmente vía psql.

### Frontend

| Archivo | Qué contiene |
|---|---|
| `templates/ai_mode_dashboard.html` | Plantilla principal. Reusa CSS de Manual AI. |
| `static/js/ai-mode-system-modular.js` | Entry point del JS; importa los 11 módulos. |
| `static/js/ai-mode-projects/*.js` | 11 archivos: `ai-mode-core.js`, `-utils.js`, `-projects.js`, `-keywords.js`, `-analysis.js`, `-charts.js`, `-analytics.js`, `-competitors.js`, `-clusters.js`, `-modals.js`, `-exports.js`. |

> ⚠️ Carpeta huérfana `ai-mode-projects/utils/validators.py` (con guion) — directorio aparente abandonado de un primer intento de refactorización. La carpeta real es `ai_mode_projects/` (con guion bajo).

### Tests / scripts de diagnóstico

| Archivo | Qué hace |
|---|---|
| `test_ai_mode_system.py` | Verifica tablas, conexión y registro del blueprint. |
| `quick_test_ai_mode.py` | Existencia de archivos clave. |
| `check_ai_mode_data.py` | Inspecciona contenido por proyecto. |
| `check_ai_mode_snapshots_structure.py` | Diff de columnas vs `manual_ai_snapshots`. |
| `inspect_ai_mode_structure.py` | Lista todas las tablas `ai_mode_*` con su esquema. ⚠️ creds hardcodeadas. |
| `clean_ai_mode_laserum.py` | Borrado puntual de datos del cliente Laserum. |
| `run_ai_mode_analysis_manual.py` | Lanza análisis manual desde CLI. ⚠️ creds hardcodeadas. |
| `verify_ai_mode_brand_detection.py` | Verifica detección de marca para un proyecto. |
| `verify_ai_mode_methods.py` | Comprueba que ciertos métodos existen en el código. |

**No hay tests pytest reales.** Todo son scripts de inspección/verificación CLI sin asserts formales.

---

## 4. Modelo de datos

### `ai_mode_projects`

```
id                    SERIAL PK
user_id               INTEGER FK users(id) ON DELETE CASCADE
name                  VARCHAR(255)         -- UNIQUE(user_id, name)
description           TEXT
brand_name            VARCHAR(255)         -- la marca a buscar (≥2 chars)
country_code          VARCHAR(3) DEFAULT 'US'
is_active             BOOLEAN DEFAULT TRUE
created_at            TIMESTAMP
updated_at            TIMESTAMP
-- migraciones posteriores:
selected_competitors  JSONB DEFAULT '[]'   -- max 10 dominios
topic_clusters        JSONB DEFAULT NULL   -- índice GIN idx_ai_mode_projects_topic_clusters
-- pause-by-quota (migración no localizada en repo):
is_paused_by_quota    BOOLEAN
paused_until          TIMESTAMP
paused_at             TIMESTAMP
paused_reason         TEXT
```

### `ai_mode_keywords`

```
id          SERIAL PK
project_id  FK ai_mode_projects ON DELETE CASCADE
keyword     VARCHAR(500)         -- UNIQUE(project_id, keyword)
is_active   BOOLEAN DEFAULT TRUE
added_at    TIMESTAMP
```

### `ai_mode_results`

Una fila por (proyecto, keyword, día):

```
id                  SERIAL PK
project_id          FK
keyword_id          FK
analysis_date       DATE
keyword             VARCHAR(500)   -- denorm
brand_name          VARCHAR(255)   -- denorm
brand_mentioned     BOOLEAN
mention_position    INTEGER        -- 0 si mención sólo en text_blocks; 1..N si en references
mention_context     TEXT
total_sources       INTEGER
sentiment           VARCHAR(50)    -- positive / negative / neutral
raw_ai_mode_data    JSONB          -- payload SerpAPI completo
country_code        VARCHAR(3)
created_at          TIMESTAMP
UNIQUE(project_id, keyword_id, analysis_date)
```

Índices: `(project_id, analysis_date)`, `analysis_date`, `brand_mentioned`.

### `ai_mode_snapshots`

```
id                      SERIAL PK
project_id              FK
snapshot_date           DATE
total_keywords          INTEGER
active_keywords         INTEGER
total_mentions          INTEGER
avg_position            DECIMAL(5,2)
visibility_percentage   DECIMAL(5,2)
change_type             VARCHAR(50)
change_description      TEXT
keywords_added          INTEGER
keywords_removed        INTEGER
created_at              TIMESTAMP
UNIQUE(project_id, snapshot_date)
```

### `ai_mode_events`

Anotaciones para overlay en gráficos. Tipos definidos en `config.py:EVENT_TYPES`.

```
id                  SERIAL PK
project_id          FK
event_date          DATE
event_type          VARCHAR(50)
event_title         TEXT
event_description   TEXT
keywords_affected   INTEGER
user_id             FK users
created_at          TIMESTAMP
```

### `ai_mode_global_domains`

Tabla **no creada** en `create_ai_mode_tables.py` — se infiere de `domains_service.py`. Columnas usadas:

```
project_id, keyword_id, analysis_date
keyword, project_domain (denorm)
detected_domain VARCHAR(255)
domain_position INTEGER
domain_title TEXT
domain_source_url TEXT
country_code
is_project_domain      BOOLEAN
is_selected_competitor BOOLEAN
UNIQUE(project_id, keyword_id, analysis_date, detected_domain)
```

`health.py` consulta esta tabla envuelto en try/except, devolviendo 0 si no existe — patrón "tolerar deployments antiguos".

### Relaciones

```
users (id) ──< ai_mode_projects (user_id)
                  │
                  ├─< ai_mode_keywords
                  │       │
                  │       └─< ai_mode_results
                  │
                  ├─< ai_mode_snapshots
                  ├─< ai_mode_events
                  └─< ai_mode_global_domains
```

---

## 5. Flujo completo de un análisis

### 5.1 Crear proyecto

Frontend `ai-mode-projects.js:handleCreateProject` → `POST /ai-mode-projects/api/projects`. `ProjectService.create_project` → `ProjectRepository.create_project` (insert en `ai_mode_projects`). Se inserta evento `PROJECT_CREATED` en `ai_mode_events`.

### 5.2 Análisis manual ad-hoc

Frontend `ai-mode-analysis.js:analyzeProject` → `POST /ai-mode-projects/api/projects/<id>/analyze`. Backend: `routes/analysis.py:analyze_project` → `AnalysisService.run_project_analysis(project_id, force_overwrite=True)`.

### 5.3 Análisis diario por cron

1. Bun service Railway (`function-bun-AI-Mode`) ejecuta `ai_mode_cron_function.js`.
2. POST `/ai-mode-projects/api/cron/daily-analysis?async=1` con `Authorization: Bearer $CRON_TOKEN`.
3. `routes/analysis.py:trigger_daily_analysis` (decorador `@cron_or_auth_required`) lanza `threading.Thread(daemon=True)` que ejecuta `cron_service.run_daily_analysis_for_all_projects()`.
4. Responde **HTTP 202** inmediato.

### 5.4 Motor `AnalysisService.run_project_analysis`

1. Obtiene `current_user` (de sesión o por `user_id` del cron).
2. Carga proyecto y keywords activas. Si lista vacía → `[]`.
3. **Pause-by-quota check**: si proyecto pausado y `paused_until > now` → return `{success:False, error:'project_paused_quota', paused_until}`. Si `paused_until <= now`, despausa.
4. Comprueba cuota global vía `quota_manager.get_user_quota_status`. Si `can_consume=False` → `database.pause_ai_mode_projects_for_quota(...)` y return `quota_exceeded`.
5. Itera por keywords. **En CADA iteración** re-valida cuota — si se queda sin a mitad, pausa proyectos y devuelve resultados parciales con flag `quota_exceeded`.
6. Si ya existe resultado de hoy y `force_overwrite=False` → skip; si `True` → `delete_result_for_date` antes.
7. **`_analyze_keyword`** (con `@with_backoff(max_attempts=3)`):
   - Construye params SerpAPI: `{q: keyword, engine: "google_ai_mode", location: <ciudad/país>, api_key}`.
   - La `location` se calcula vía `convert_iso_to_internal_country` + `services.country_config.get_country_config` (fallback `Madrid, Spain`).
   - Llama `GoogleSearch(...).get_dict()`.
   - Pausa de 0.3s entre keywords.
8. **`_parse_ai_mode_response`** (detallado en §6).
9. Guarda con `ResultRepository.create_result` (incluye `raw_ai_mode_data` JSON con payload completo).
10. **Dominios globales**: orden estable por `index` asc; llama `DomainsService.store_global_domains_detected` que upsertea en `ai_mode_global_domains` marcando `is_project_domain` / `is_selected_competitor`.
11. `database.track_quota_consumption(user_id, ru_consumed=1, source='ai_mode', keyword=..., country_code=..., metadata={project_id, force_overwrite, brand_name})`.

### 5.5 Snapshot diario

Tras procesar un proyecto en el cron (`cron_service.py:_process_projects`):
- `_calculate_snapshot_metrics` → totals, mentions, `avg_position`, `visibility_percentage`.
- Inserta fila en `ai_mode_snapshots`.
- Inserta evento `daily_analysis` en `ai_mode_events`.

### 5.6 Cálculo de visibilidad / SoV / posición

`statistics_service.py:get_project_statistics` usa subquery `WITH latest_results AS (SELECT DISTINCT ON (k.id) ...)` para tomar el resultado más reciente por keyword en la ventana, y deriva:

| Métrica | Fórmula |
|---|---|
| `visibility_percentage` | `mentions / analyzed * 100` |
| `avg_position` | `AVG(mention_position WHERE mention_position IS NOT NULL)` |
| **SoV** | Share de menciones en el universo de keywords del proyecto (no por sentimiento). |

---

## 6. Detección de marca y matching robusto

Detalle de `_parse_ai_mode_response` (`analysis_service.py`).

### Estructura del payload SerpAPI

```
text_blocks: [
  { type, snippet, reference_indexes }
],
references: [
  { link, index, title, source, snippet }
]
```

### Generación de variaciones de la marca

A partir de `brand_name` el sistema genera variaciones:
- Lowercase, sin espacios, sin guiones.
- Sin prefijo `get` (ej. `getquipu` → `quipu`).
- Añadiendo dominios `.com`/`.es`/`www.`.

### Prioridad de match en references

Orden por `index` 0-based ascendente. Para cada reference se comprueba:

1. **Substring match en `netloc` del link** (excluye `www.`).
2. **Substring match en URL completa**.
3. **Word-boundary regex `\b<v>\b` en `title` / `snippet` / `source`**.

> ⚠️ El paso 3 es el **FIX CRÍTICO** comentado en `analysis_service.py:516`. Antes se usaba substring match a secas y `quipu` matcheaba `quipus`. Ahora `\b...\b` evita falsos positivos.

### Match en text_blocks

Si no se encuentra en references, busca en `text_blocks` con word boundaries. Asigna `mention_position=0` para menciones sólo en texto generado por IA (vs 1..N para references).

### Sentimiento

Lista hardcoded de **11 palabras positivas y 10 negativas en inglés**. Para keywords en castellano (la mayoría de clientes ESP) **el sentimiento será siempre `neutral`**. Es deuda conocida.

```python
positive_words = ['best','top','leading','excellent','great','recommended','popular','trusted','premium','quality','reliable']
negative_words = ['worst','bad','poor','avoid','overpriced','expensive','slow','outdated','unreliable','disappointing']
```

---

## 7. Integración con cuotas y billing

### Coste

`AI_MODE_KEYWORD_ANALYSIS_COST = 1` (1 RU por keyword) — `config.py:6`.

### Track

`database.track_quota_consumption` con `source='ai_mode'`.

### Pause flag

Cada proyecto tiene `is_paused_by_quota`, `paused_until`, `paused_at`, `paused_reason` en `ai_mode_projects`.

`database.pause_ai_mode_projects_for_quota(user_id, paused_until, reason)` actualiza **todos** los proyectos `is_active=TRUE` del user.

### Despausa al renovar Stripe

`database.resume_quota_pauses_for_user(user_id)` (lineas 2515-2523) hace:

```sql
UPDATE ai_mode_projects
SET is_paused_by_quota=FALSE,
    paused_until=NULL,
    paused_at=NULL,
    paused_reason=NULL
WHERE user_id = %s
```

Se llama desde el webhook `invoice.payment_succeeded` y el cron diario de quota-reset (ver `CLAUDE-stripe-cuotas-crons.md`).

### Filtros del cron

`CronService._get_active_projects` filtra:
- `is_active = TRUE`.
- `is_paused_by_quota = FALSE` **OR** `paused_until <= NOW()` (auto-despause cuando expira el lock).
- `users.plan != 'free'`.
- `users.billing_status NOT IN ('canceled')`.

### Validación previa por petición

`utils/validators.py:check_ai_mode_access` bloquea plan `free` salvo `user_has_any_module_access(user_id, 'ai_mode')` (acceso compartido entre cuentas).

### Notificación al usuario sin cuota

- Endpoint manual: **HTTP 429** con `quota_exceeded:true` y `quota_info`. Frontend muestra `window.QuotaUI.showBlockModal(...)`.
- Si plan free: HTTP 402 → redirect a `/billing` tras 1.2s.

---

## 8. Endpoints HTTP

Todos bajo prefix `/ai-mode-projects`.

### UI

| URL | Método | Auth | Función |
|---|---|---|---|
| `/` | GET | `@auth_required` | Renderiza `ai_mode_dashboard.html`. |

### API — proyectos

| URL | Método | Función |
|---|---|---|
| `/api/projects` | GET / POST | Lista / crear. |
| `/api/projects/<id>` | GET / PUT / DELETE | Detalle / update / borrar (requiere pause previo). |
| `/api/projects/<id>/pause` | PUT | Pausa proyecto. |
| `/api/projects/<id>/resume` | PUT | Reanuda. 402 si cuota agotada. |

### API — keywords

| URL | Método | Función |
|---|---|---|
| `/api/projects/<id>/keywords` | GET / POST | Listar / añadir (límite 300). |
| `/api/projects/<id>/keywords/<kid>` | DELETE / PUT | Eliminar / editar. |

### API — análisis

| URL | Método | Auth | Función |
|---|---|---|---|
| `/api/projects/<id>/analyze` | POST | `@auth_required` | Análisis manual (`force_overwrite=True`). 402 paywall, 429 cuota. |
| `/api/cron/daily-analysis` | POST | `@cron_or_auth_required` | Cron diario. `?async=1` → 202; sync → 200/500. |

### API — resultados / stats

| URL | Función |
|---|---|
| `/api/projects/<id>/results` | Resultados ventana (default 30d). |
| `/api/projects/<id>/stats` | Stats agregadas. |
| `/api/projects/<id>/stats-latest` | Stats último análisis. |
| `/api/projects/<id>/ai-overview-table` | Tabla detallada. |
| `/api/projects/<id>/ai-overview-table-latest` | Tabla del último análisis por keyword. |
| `/api/projects/<id>/top-domains` | Top dominios. |
| `/api/projects/<id>/global-domains-ranking` | Ranking global de dominios detectados. |
| `/api/projects/<id>/urls-ranking` | Ranking de URLs. |

### API — competitors

| URL | Método | Función |
|---|---|---|
| `/api/projects/<id>/competitors` | GET / PUT | Get/set lista (max 10). |
| `/api/projects/<id>/competitors-charts` | GET | Datos para gráficas. |
| `/api/projects/<id>/comparative-charts` | GET | Charts comparativos. |

### API — clusters

| URL | Método | Función |
|---|---|---|
| `/api/projects/<id>/clusters` | GET / PUT | Config de topic clusters. |
| `/api/projects/<id>/clusters/statistics` | GET | Stats por cluster. |
| `/api/projects/<id>/clusters/validate` | POST | Validar config sin guardar. |
| `/api/projects/<id>/clusters/test` | POST | Clasificar una keyword. |

### API — exports / health

| URL | Método | Función |
|---|---|---|
| `/api/projects/<id>/download-excel` | POST | Genera Excel (función llamada `generate_manual_ai_excel` por copy-paste). |
| `/api/projects/<id>/export` | GET | Placeholder ("coming soon"). |
| `/api/health` | GET | Health-check sin auth. |

---

## 9. Variables de entorno y constantes

### Env vars

| Variable | Para qué sirve |
|---|---|
| `SERPAPI_API_KEY` | **Preferida**. |
| `SERPAPI_KEY` | Fallback. |
| `APP_URL` | Usado por el cron Bun. |
| `CRON_TOKEN` | Bearer para `cron_or_auth_required`. |
| `CRON_ALERT_EMAIL` o `MODEL_DISCOVERY_EMAIL` | Destinatario alertas si Bun falla. |

### Constantes hardcodeadas (`config.py`)

```
AI_MODE_KEYWORD_ANALYSIS_COST = 1
MAX_KEYWORDS_PER_PROJECT      = 300
MAX_COMPETITORS_PER_PROJECT   = 10
MAX_NOTE_LENGTH               = 500
DEFAULT_DAYS_RANGE            = 30
CRON_LOCK_CLASS_ID            = 4243
SERPAPI_AI_MODE_ENGINE        = 'google'    # ⚠️ MUERTA
SERPAPI_AI_MODE_TYPE          = 'ai_mode'   # ⚠️ MUERTA
```

> El código real usa literal `engine="google_ai_mode"` en `analysis_service.py:362`, no la concatenación de las constantes.

Hardcoded en `_analyze_keyword`:
- Pausa de 0.3 s entre keywords.
- Backoff `max_attempts=3`, `base_delay_sec=1.0`.
- Timeout frontend 30 min.

---

## 10. Cron diario

### Disparo

Servicio Bun **`function-bun-AI-Mode`** en Railway con schedule **`0 4 * * 1,4,6`** (lunes, jueves y sábado a las 04:00 UTC — NO es diario; verificado en Railway 2026-06-10). Ejecuta `ai_mode_cron_function.js` que llama:

```
POST ${APP_URL}/ai-mode-projects/api/cron/daily-analysis?async=1
Authorization: Bearer ${CRON_TOKEN}
AbortSignal.timeout(60000)
```

(60 s para recibir el 202).

### Endpoint Flask

`routes/analysis.py:trigger_daily_analysis` (`@cron_or_auth_required`). En modo `async=1` lanza un `threading.Thread(daemon=True)` que ejecuta `cron_service.run_daily_analysis_for_all_projects()` y responde HTTP 202 sin bloquear.

### Lógica del cron

1. **Idempotencia**: `pg_try_advisory_lock(CRON_LOCK_CLASS_ID=4243, today_yyyymmdd)`. Si ya está lockeado → devuelve `{success:True, message:"Another daily run in progress"}` sin trabajar.
2. `_get_active_projects` → SELECT con los filtros de §7.
3. Itera **secuencial** (no paralelo, a diferencia de LLM Monitoring):
   - Verifica plan/billing del user otra vez.
   - Si ya hay resultados en `ai_mode_results` dentro de la ventana `analysis_frequency_days` del proyecto (default 1 = comportamiento histórico "hoy"; 7 = semanal; NUEVO 2026-06-10, migración `migrate_analysis_frequency_fields.py`) → skip.
   - Llama a `analysis_service.run_project_analysis(project_id, force_overwrite=False, user_id=...)`.
   - Si devuelve `error in ('QUOTA_EXCEEDED', 'project_paused_quota')` → cuenta como skipped.
   - Crea snapshot diario + evento `daily_analysis`.
4. Libera el advisory lock con `pg_advisory_unlock`.
5. Devuelve `{successful, failed, skipped, total_keywords, elapsed_seconds}`.

### Sin paralelismo ni timeout-por-proyecto

A diferencia del cron LLM Monitoring (que tiene `LLM_PROJECT_PARALLELISM` y `LLM_PROJECT_TIMEOUT_MINUTES`), AI Mode itera **secuencialmente** y no envuelve cada proyecto en daemon thread con `join(timeout)`. **Un proyecto colgado en SerpAPI podría bloquear todo el cron** hasta el timeout interno de SerpAPI.

### Registro

- Logs en JSON estructurado (`event: cron_start, cron_skipped_lock, cron_projects_found, cron_end`).
- **No usa `cron_runs` table** como LLM Monitoring; el rastro vive en `ai_mode_events` con `event_type='daily_analysis'`.
- **Sin alertas por email integradas** para AI Mode (las alertas del Bun van a `/api/llm-monitoring/cron/alert`).

---

## 11. Frontend

### Plantilla

`templates/ai_mode_dashboard.html` reusa estilos de Manual AI (`manual-ai.css`), `quota-ui.css`, `clusters-styles.css`, `paywall.css`. Reusa Chart.js + Grid.js.

Secciones de UI:
- "Your AI Mode Projects".
- "AI Mode Dashboard".
- "AI Mode Keywords Details".
- "Top Mentioned URLs in AI Mode".
- Ranking de "media sources detected in AI Mode".
- Paywall overlay si `access_blocked` (free sin shared access).

### JS

Entry: `static/js/ai-mode-system-modular.js`. Importa los 11 módulos de `static/js/ai-mode-projects/` y compone una clase `AIModeSystem` (con `Object.assign(prototype, ...)`). Instancia global `window.aiModeSystem` al `DOMContentLoaded`. Registra plugin `htmlLegendPlugin` en Chart.js.

### Componentes

- **Charts** (`ai-mode-charts.js`): visibility chart, positions chart, anotaciones de eventos.
- **Analytics** (`ai-mode-analytics.js`): top domains, global domains ranking, top URLs, keywords table, comparative charts.
- **Tablas Grid.js**: para keywords/URLs/dominios.
- **Modals** (`ai-mode-modals.js`): proyecto, settings, accesos compartidos.

### Refresco

- Auto-refresh interval (`setupAutoRefresh` en core).
- **Backup polling** durante análisis manual: cada 30s revisa si `total_results` cambió, hasta 10 min de timeout (`ai-mode-analysis.js:27-53`). Sirve como red de seguridad si la petición original cae por red.

---

## 12. Bridge con otros sistemas

### `ai_mode_system_bridge.py`

**Único propósito**: aislamiento de import. Reexporta `ai_mode_bp` y `run_daily_analysis_for_all_ai_mode_projects()`. Si import falla, pone `USING_AI_MODE_SYSTEM=False` y el sistema queda **desactivado en silencio** (devuelve dict de error). `app.py:3811-3827` lo importa con try/except sin tirar la app abajo.

### Dependencias compartidas con otros sistemas

| Recurso | También usado por |
|---|---|
| `services.country_config.get_country_config` | Manual AI / GSC |
| `services.utils.normalize_search_console_url` | Search Console |
| `services.project_access_service.user_has_any_module_access` | Módulo de invitaciones (cross-app) |
| `services.ai_cache.ai_cache` | Lazy import, no se ve activo |
| `database.py` | Pool, `pause_ai_mode_projects_for_quota`, `resume_quota_pauses_for_user`, `track_quota_consumption` |
| `quota_manager.get_user_quota_status` | Todos los módulos con cuota |
| `auth.py` | OAuth |
| `llm_monitoring_limits.get_upgrade_options` | Reusado para mostrar opciones de upgrade en paywall |

### NO hay bridge directo con Manual AI ni LLM Monitoring

Son **tres sistemas paralelos** que comparten `users`, cuotas y patrón arquitectural pero **no datos**. La pausa por cuota se replica en las 4 tablas (`ai_mode_projects`, `manual_ai_projects`, `llm_monitoring_projects`, y campos legacy en `users`).

---

## 13. Errores históricos y deuda técnica

### Comentarios encontrados en código

- **`# VALIDACIÓN CRÍTICA 1`** (`analysis_service.py:411-413`): defensa contra `serp_data == None` o no-dict.
- **`# VALIDACIÓN CRÍTICA 2`** (`analysis_service.py:423-425`): sin `brand_name` → return temprano.
- **`# FIX CRÍTICO: Añadir snippet`** (`analysis_service.py:516`): antes no se buscaba en el snippet de la reference, perdiendo menciones.
- **Word boundaries** (`analysis_service.py:549-558`): regex `\b...\b` para evitar `quipu` ⊂ `quipus`.
- **Variación sin `get`** (`analysis_service.py:484-487`): `getquipu` → `quipu`.

### Deuda técnica conocida

| Deuda | Impacto | Riesgo |
|---|---|---|
| **Engine declarado pero ignorado** (constantes `SERPAPI_AI_MODE_ENGINE` muertas) | Confusión al leer config. | Trivial. |
| **README heredado** (empieza con `# 🤖 Manual AI Analysis System`) | Confusión. | Trivial. |
| **`exports.py` llama `generate_manual_ai_excel`** | Strings copy-paste no actualizados. | Trivial. |
| **Carpeta huérfana `ai-mode-projects/utils/validators.py`** (con guion) | Código muerto. | Trivial. |
| **Tabla `ai_mode_global_domains` no en script de creación** | El código usa try/except para tolerar ausencia. | Bajo. |
| **Columnas de pause-by-quota no en `CREATE TABLE` original** | Si se replica en entorno fresco, fallarán los UPDATEs. | Medio. |
| **Cron sin paralelismo / sin timeout por proyecto** | Un proyecto colgado bloquea todo. | Alto. |
| **6+ scripts con credenciales producción hardcodeadas** (`run_ai_mode_analysis_manual.py`, `inspect_ai_mode_structure.py`, etc.) | Riesgo si repo se hace público. | Alto. |
| **`raw_ai_mode_data` JSONB sin política de purga** | Crece sin límite. | Medio (largo plazo). |
| **`ai_mode_cron_function.js` postea alertas a `/api/llm-monitoring/cron/alert`** | Plumbing reusado de LLM. | Bajo (funciona). |
| **Sentimiento sólo en inglés** | Para clientes ESP siempre `neutral`. | Medio (UX). |
| **Sin tests unitarios formales** | Cobertura 0% real. | Alto. |

### Archivos `.md` sueltos del módulo

`ai_mode_projects/COMPLETION_SUMMARY.md`, `MIGRATION_COMPLETE.md`, `REFACTORING_GUIDE.md`, `SAFE_MIGRATION.md`, `README.md` — **todos hablan de "Manual AI System"** en el body aunque vivan en `ai_mode_projects/`. Reciclados de la refactorización de Manual AI.

**No hay docs específicos** de incidencias o fixes de AI Mode.

---

## 14. Operaciones manuales y troubleshooting

### Disparar manualmente el cron AI Mode

```bash
curl -X POST "$APP_URL/ai-mode-projects/api/cron/daily-analysis?async=0" \
  -H "Authorization: Bearer $CRON_TOKEN"
```

### Disparar análisis on-demand de un proyecto

Como user (con cookie de sesión), desde la UI o:

```bash
curl -X POST "$APP_URL/ai-mode-projects/api/projects/<id>/analyze" \
  -H "Cookie: session=..."
```

### "Un cliente dice que su proyecto AI Mode no se actualiza"

1. `GET /ai-mode-projects/api/health`.
2. Mirar `ai_mode_projects.is_paused_by_quota` y `paused_until`.
3. Si pausado por cuota: ver `CLAUDE-stripe-cuotas-crons.md`.
4. Comprobar resultados hoy en `ai_mode_results` para ese `project_id`.
5. Si todo OK pero no hay resultados → lanzar el cron manualmente.

### "El sistema dice 'AI Mode disabled'"

`USING_AI_MODE_SYSTEM=False` en el bridge. El import del paquete `ai_mode_projects` falló al arrancar la app. Mirar logs de arranque (`app.py:3811-3827` con try/except). Causa típica: error de sintaxis o import circular en algún archivo del paquete.

### "Detecta dominios pero no la marca"

Probable: la marca aparece sólo en `text_blocks` (no en references) y la regex word-boundary no la pilla. Verificar `raw_ai_mode_data` del resultado:
- Buscar manualmente la marca en el `snippet` de `text_blocks`.
- Si aparece como subcadena de otra palabra (ej. `quipu` dentro de `quipus`), es comportamiento esperado tras el fix de word boundaries.

### "Sentimiento siempre neutral"

Es **deuda conocida**: las listas de palabras positivas/negativas están sólo en inglés. Para clientes ESP, todo se queda en `neutral`. Consultar `_parse_ai_mode_response` para añadir palabras en otros idiomas.

---

## 15. Tests y diagnóstico

| Archivo | Cubre |
|---|---|
| `test_ai_mode_system.py` | Existencia de tablas + acceso. |
| `quick_test_ai_mode.py` | Smoke estructural (existencia de archivos). |
| `check_ai_mode_data.py` | Inspecciona datos por proyecto. |
| `check_ai_mode_snapshots_structure.py` | Diff `ai_mode_snapshots` vs `manual_ai_snapshots`. |
| `inspect_ai_mode_structure.py` | Lista esquema completo. ⚠️ creds hardcodeadas. |
| `clean_ai_mode_laserum.py` | Limpieza puntual. |
| `run_ai_mode_analysis_manual.py` | Disparar análisis CLI. ⚠️ creds hardcodeadas. |
| `verify_ai_mode_brand_detection.py` | Imprime detección de marca para `project_id` dado. |
| `verify_ai_mode_methods.py` | Verifica que ciertos métodos esperados existen. |

**No hay tests pytest**. Todo son scripts CLI sin asserts.

### Recomendación

Los `verify_ai_mode_*.py` son los mejores candidatos a convertirse en tests pytest reales con asserts y fixtures de `raw_ai_mode_data` JSON.

---

## TL;DR

1. **AI Mode = SerpAPI `google_ai_mode` + parser text_blocks/references.** No es Google AI Overviews (eso es Manual AI).
2. **Cron secuencial sin paralelismo ni timeout.** Un proyecto colgado bloquea todo. Advisory lock `4243` previene concurrencia.
3. **Idempotencia por UNIQUE `(project_id, keyword_id, analysis_date)`.** Sobreescribe sólo en modo manual `force_overwrite=True`.
4. **Quota = 1 RU/keyword.** No tiene caso "collapsed" como Manual AI.
5. **Detección de marca con word boundaries** (`\b...\b`) tras el FIX CRÍTICO. Soporta variantes `getbrand` → `brand` y URL match.
6. **Sentimiento sólo en inglés.** Deuda conocida (clientes ESP siempre `neutral`).
7. **Bridge se desactiva en silencio si import falla.** Mirar logs de arranque si "AI Mode no responde".
8. **Plumbing reusado de Manual AI**: README, plantillas y exports tienen strings copy-paste no actualizados.

— Fin del manual —
