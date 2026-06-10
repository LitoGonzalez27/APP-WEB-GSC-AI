# CLAUDE-search-console.md — Google Search Console (producto histórico)

> Manual del **producto histórico** que da nombre al repositorio (`search_console_webapp`): integración con Google Search Console + dashboards GSC + AI Overview detection legacy. Convive con los productos posteriores (Manual AI, AI Mode, LLM Monitoring) y sigue **plenamente activo**.
>
> Última actualización: 2026-05-08.
>
> Manuales relacionados: `CLAUDE-manual-ai.md` (evolución del análisis AIO), `CLAUDE-auth-usuarios.md` (OAuth multi-cuenta), `CLAUDE-quota-system.md` (consumo RU). Índice maestro: `CLAUDE-INDEX.md`.

---

## Índice

1. [Visión general en 5 minutos](#1-visión-general-en-5-minutos)
2. [Mapa de archivos](#2-mapa-de-archivos)
3. [Modelo de datos](#3-modelo-de-datos)
4. [Flujo OAuth para GSC](#4-flujo-oauth-para-gsc)
5. [Funcionalidades principales](#5-funcionalidades-principales)
6. [AI Overview legacy](#6-ai-overview-legacy)
7. [Endpoints HTTP principales](#7-endpoints-http-principales)
8. [Frontend](#8-frontend)
9. [Integración con cuota](#9-integración-con-cuota)
10. [Variables de entorno](#10-variables-de-entorno)
11. [Cron / análisis periódico](#11-cron--análisis-periódico)
12. [Multi-account / múltiples conexiones OAuth](#12-multi-account--múltiples-conexiones-oauth)
13. [Errores históricos y deuda](#13-errores-históricos-y-deuda)
14. [Relación con los productos nuevos](#14-relación-con-los-productos-nuevos)
15. [Tests](#15-tests)

---

## 1. Visión general en 5 minutos

**Producto de análisis SEO sobre datos de Google Search Console** para una propiedad verificada del usuario. Combina:

- **Dashboard de GSC** (clicks / impressions / CTR / position) por URL y por keyword.
- **Comparativa de dos periodos** (M1 vs M2) con deltas absolutos y porcentuales.
- **Análisis on-demand de AI Overview** sobre las keywords devueltas por GSC, usando SerpAPI para detectar si Google muestra AIO y si el dominio del usuario aparece como fuente.
- **SERP modal** con posición orgánica + screenshot resaltado (Playwright).
- **Recomendaciones AIO** (Jina + Gemini) para keywords donde el usuario no aparece.
- **Excel export** de toda la tabla.

### Diferencias con Manual AI / AI Mode

| Dimensión | GSC histórico | Manual AI / AI Mode |
|---|---|---|
| **Concepto** | Informe interactivo on-demand | Proyectos persistentes con seguimiento histórico |
| **Estructura** | Sin "proyecto"; análisis sobre la propiedad GSC + rango de fechas | Proyecto = (dominio, país, keywords) |
| **Frecuencia** | On-demand (botón en UI) | Cron diario automático |
| **Tabla principal** | `ai_overview_analysis` (UPSERT por día) | `manual_ai_results` / `ai_mode_results` |

### Estado

**Activo y en uso.** Es la primera pantalla que ve un usuario logueado (`/dashboard` → `/app`). Tiene paywall (`free` no entra), cuotas y checks de pausa por cuota como los nuevos módulos.

**Reglas de oro:**

1. **No hay cron**. Todo es on-demand.
2. **Reusa código con Manual AI / AI Mode** vía `services/ai_analysis.py`, `services/utils.urls_match`, `services/country_config`.
3. **Multi-account OAuth Google**: un user puede conectar varias cuentas para acceder a más propiedades.
4. **Caché Redis 24h** para AIO detectado, 6h para no-AIO.
5. **UPSERT diario** en `ai_overview_analysis` — repetir el mismo análisis el mismo día no consume nuevas RU.

---

## 2. Mapa de archivos

### Backend núcleo

| Archivo | Líneas | Rol |
|---|---:|---|
| `app.py` | 3968 | **Punto de entrada Flask**. Contiene la mayoría de las rutas GSC. |
| `auth.py` | 2397 | OAuth2 Google, SCOPES, callback, gestión multi-conexión, helpers `get_authenticated_service*`. |
| `services/search_console.py` | 50 | Wrapper minimalista: `authenticate()` y `fetch_searchconsole_data_single_call()`. |
| `services/ai_analysis.py` | 685 | **`detect_ai_overview_elements()`** — núcleo de detección AIO sobre payload SerpAPI; `extract_brand_variations`, `check_brand_mention`, `_extract_full_aio_content`, `_detect_aio_serp_position`. |
| `services/ai_cache.py` | 250 | `AIOverviewCache` — Redis (24h hits / 6h misses). Instancia global `ai_cache`. |
| `services/serp_service.py` | 286 | `get_serp_json`, `get_serp_html`, `get_page_screenshot` (Playwright), screenshot LRU+TTL en memoria. |
| `services/aio_recommendations.py` | 489 | Jina.ai + Gemini para generar recomendaciones SEO; cache LRU 24h. |
| `services/utils.py` | 153 | `extract_domain`, `normalize_search_console_url`, `urls_match` (matching SERP↔SC con varias estrategias). |
| `services/country_config.py` | — | `COUNTRY_MAPPING` con `serp_location`, `serp_gl`, `serp_hl`, `google_domain`. |
| `excel_generator.py` | — | Genera el Excel multi-hoja del informe. |
| `database.py` | 2700+ | DDL de `oauth_connections`, `gsc_properties`, `ai_overview_analysis`. Funciones `save_ai_overview_analysis`, `get_ai_overview_stats`, `get_ai_overview_history`, `pause_ai_overview_for_quota`, `resume_quota_pauses_for_user`. |

### Frontend

#### Templates (`/templates/`)

| Plantilla | Para qué |
|---|---|
| `landing.html` | Pública. |
| `login.html`, `signup.html` | Auth. |
| `dashboard.html` (993 líneas) | Selector de propiedad, fechas, navegación a `/app`. |
| `index.html` (1383 líneas) | **La app de análisis GSC**; carga toda la cadena de scripts. |

#### JS principal (`/static/js/`)

| Archivo | Líneas | Rol |
|---|---:|---|
| `app.js` | 1801 | Orquestador del front. |
| `data.js` / `data-validator.js` | — | POST a `/get-data`. |
| `ui-render.js` | 2560 | Render principal; también llama `/api/url-keywords`. |
| `ui-keywords-gridjs.js` | 1527 | Tabla keywords. |
| `ui-urls-gridjs.js`, `ui-url-keywords-gridjs.js` | — | Otras tablas Grid.js. |
| `ui-keyword-comparison-table.js`, `ui-detailed-results-gridjs.js` | — | Tablas adicionales. |
| `ui-overview-movers.js` | — | Sección "movers" (deltas grandes). |
| `ui-ai-overview*.js` | — | Todo el módulo AIO (analysis, display, modals, gridjs, pdf, download, utils, main, overlay). |
| `ui-aio-recommendations-modal.js` | — | Modal de Jina/Gemini. |
| `ui-serp-modal.js` | — | Modal SERP/screenshot/posición. |
| `ui-date-selector.js` | — | Selector de fechas (M1/M2). |
| `competitor-analysis.js`, `keyword-exclusion.js`, `topic-clusters.js` | — | Controles del panel AIO. |
| `gsc-connect-modal.js` | — | Modal "conecta tu Google Search Console". |
| `quota-ui.js`, `paywall.js`, `ai-reset-manager.js`, `sidebar-navigation.js`, `onboarding-popups.js`, `tooltips-fix.js` | — | UX. |

> El usuario antiguamente hablaba de `api-handler.js` y `state-manager.js`: **no existen** con esos nombres. Sus equivalentes son `data.js`/`data-validator.js` (handler de `/get-data`) y partes de `app.js` + `ui-render.js` para estado.

---

## 3. Modelo de datos

DDL en `database.py` (líneas 300–381 y 1760–1840).

### `oauth_connections`

Conexiones OAuth Google por usuario. **Soporta multi-cuenta** vía UNIQUE `(user_id, provider, google_account_id)`.

```
id                          SERIAL PK
user_id                     FK users
provider                    DEFAULT 'google'
google_account_id           TEXT
google_email                TEXT
access_token                TEXT
refresh_token_encrypted     TEXT  -- cifrado con Fernet si TOKEN_ENCRYPTION_KEY
token_uri, client_id, client_secret, scopes, expires_at
```

Ver `CLAUDE-auth-usuarios.md` para detalle.

### `gsc_properties`

```
id, user_id, connection_id (FK oauth_connections ON DELETE CASCADE)
site_url            -- puede ser https://... o sc-domain:...
permission_level
verified
last_seen
UNIQUE (user_id, site_url)
```

### `ai_overview_analysis` (la tabla legacy histórica del producto GSC)

```
id, site_url, keyword, analysis_date
has_ai_overview, domain_is_ai_source, impact_score
country_code, keyword_word_count
clicks_m1, clicks_m2, delta_clicks_absolute, delta_clicks_percent
impressions_m1/m2
ctr_m1/m2
position_m1/m2
ai_elements_count
domain_ai_source_position
aio_serp_position    -- 'top' | 'middle' | 'bottom'
raw_data JSONB
user_id, created_at
```

**UPSERT por `(site_url, keyword, country_code, DATE(analysis_date), user_id)`** mediante DELETE+INSERT (`save_ai_overview_analysis`, líneas 1851–1949). Índice único `idx_ai_analysis_upsert`. Tras crearlo se hizo deduplicación de filas históricas (líneas 1816–1828).

### Columnas en `users` para pausa AIO

Migración `migrate_quota_pause_fields.py`:

```
ai_overview_paused_until    TIMESTAMPTZ
ai_overview_paused_at       TIMESTAMPTZ
ai_overview_paused_reason   TEXT
```

> ⚠️ **AI Overview se pausa a nivel USUARIO**, no proyecto, porque no hay tabla `ai_overview_projects`. Diferente patrón al resto de módulos.

---

## 4. Flujo OAuth para GSC

`SCOPES` definidos en `auth.py:117-121`:

```
https://www.googleapis.com/auth/webmasters.readonly
https://www.googleapis.com/auth/userinfo.email
https://www.googleapis.com/auth/userinfo.profile
```

### Rutas

`/auth/login`, `/auth/signup`, `/auth/callback`. El callback distingue `oauth_action` ∈ {`login`, `signup`, `link`}:

| Acción | Qué hace |
|---|---|
| **login** | Usuario existente; copia `temp_credentials` a `session['credentials']` y crea/actualiza `oauth_connections`. |
| **signup** | Registra usuario nuevo, plan `free`. |
| **link** | Usuario logueado añade una nueva cuenta Google. Crea/actualiza `oauth_connections` y sincroniza propiedades llamando `searchconsole.sites().list()` + `upsert_gsc_properties_for_connection`. |

### Helpers para servicio autenticado

| Helper | Uso |
|---|---|
| `get_authenticated_service('searchconsole', 'v1')` | Usa `session['credentials']`. |
| `get_authenticated_service_for_connection(conn, ...)` (auth.py:2363–2397) | Usa una `oauth_connections` específica. Descifra `refresh_token_encrypted`, refresca si caducado, persiste el nuevo token vía `update_oauth_connection_tokens`. |

### ProxyFix activo en producción/staging

`app.py:127–130` — para que `request.url` sea HTTPS y no rompa OAuth. Sin esto `InsecureTransportError`.

---

## 5. Funcionalidades principales

Implementadas en `app.py`:

### Listado de propiedades

`GET /get-properties` — agrega propiedades de **todas** las conexiones del usuario (`app.py:459–486`).

### Países disponibles

`POST /get-available-countries` — consulta GSC los últimos 3 meses (`app.py:2637+`).

### Datos GSC

`POST /get-data` (`app.py:609-1395`) — **800 líneas de lógica**:

- Modo `property` (sin URLs en form) o `page` (con URLs y `match_type`).
- Recoge dimensiones `page`, `query`, opcional filtro de `country`.
- Calcula M1 y M2 si `has_comparison=true`, deltas absolutos y porcentuales.
- **Validaciones**:
  - Rango ≤ 16 meses.
  - Fechas en orden.
  - Móvil ≤ 90 días y ≤ 10 URLs.
- Resuelve la conexión OAuth correcta usando `get_connection_for_site(user_id, site_url)`.

### Excel

`POST /download-excel` — usa `excel_generator.generate_excel_from_data()` (`app.py:1397–1442`).

### AI Overview

`POST /api/analyze-ai-overview` (`app.py:2239–2607`) — paywall, quota, paralelismo, exclusiones, topic clusters, competitor analysis (manual + auto), URLs más citadas.

### Recomendaciones AIO

`POST /api/ai-recommendations` (`app.py:3134–3206`) — Jina + Gemini.

### Estadísticas y typology

| Endpoint | Para qué |
|---|---|
| `GET /api/ai-overview-stats` | Stats agregadas. |
| `GET /api/ai-overview-typology` | Tipología de AIOs (informacional / transaccional / etc.). |
| `GET /api/ai-overview-history` | Histórico. |

### Cache management

`POST /api/cache-management` (admin only).

### SERP

| Endpoint | Para qué |
|---|---|
| `GET /api/serp` | Datos SERP. |
| `GET /api/serp/position` | Posición orgánica. |
| `GET /api/serp/screenshot` | Screenshot Playwright resaltado. |

### Quick wins / movers

Front-end (`ui-overview-movers.js`) calcula sobre la respuesta de `/get-data`.

### Detección dinámica de país

`get_top_country_for_site` (`app.py:226–281`): si el usuario no fija país, consulta GSC últimos 3 meses y usa el de más clics como geolocalización SerpAPI.

---

## 6. AI Overview legacy

Núcleo en `services/ai_analysis.py:308-666` (`detect_ai_overview_elements`).

### Lógica

1. Recibe payload SerpAPI y `site_url`.
2. **Caso especial**: AI Overview "collapsed" con `page_token` → marca `has_ai_overview = True` pero requiere segunda llamada (no se hace aquí, se loguea — Manual AI sí lo expande).
3. Detecta posición en SERP (`top`/`middle`/`bottom`) — `_detect_aio_serp_position` (líneas 64–132).
4. Itera `text_blocks`, recoge `reference_indexes` y busca menciones de marca con `extract_brand_variations` + `check_brand_mention`.
5. **3 métodos** para decidir si el dominio aparece en AIO:

| Método | Detalle |
|---|---|
| **Método 1 (oficial)** | `ai_overview.references[]` con `urls_match`. |
| **Método 1.5 (fallback)** | Menciones de marca en el contenido de los `text_blocks` (`text_content_*`). |
| **Método 2 (ultra-estricto)** | `organic_results[ref_idx]` validado contra `references[ref_idx].link` (`hybrid_ultra_strict_validated`). |

6. Devuelve dict con `has_ai_overview`, `domain_is_ai_source`, `domain_ai_source_position`, `domain_ai_source_link`, `aio_serp_position`, `total_elements`, `impact_score`, y `debug_info` con todos los metadatos (incluido `aio_content_preview` extraído por `_extract_full_aio_content`).

### Variaciones de marca

`extract_brand_variations` (líneas 154–257) — incluye:
- Variaciones con tildes españolas.
- Combinaciones get/and/clinica/centro/etc.
- Lowercase, sin espacios, sin guiones.

### Caché Redis (`services/ai_cache.py`)

```
key = f"ai_analysis:<md5_hash>:<keyword[:20]>"
hash = md5((keyword, site_url, country))
TTL = 24h si has_ai_overview=True, 6h si no
```

`cache_analysis_batch` para guardar todo el batch tras un análisis.

### Persistencia

Tras `analyze-ai-overview`, app.py llama:
1. `save_ai_overview_analysis` con UPSERT por día (database.py:1851–1949).
2. `track_quota_consumption` con `source='ai_overview'`.

### Reuso vs Manual AI

Manual AI tiene su propia copia/refactor en `manual_ai/services/analysis_service.py` con su propia llamada a SerpAPI.

**Comparten**:
- `services/utils.urls_match`.
- `services/country_config`.
- `services/ai_analysis.detect_ai_overview_elements`.
- `services/utils.extract_domain`.

**Pero la base de datos y el flujo son independientes** (Manual AI usa `manual_ai_*` tables, no `ai_overview_analysis`).

---

## 7. Endpoints HTTP principales

Todos en `app.py`. Resumen con líneas:

### Páginas

| Endpoint | Línea |
|---|---:|
| `GET /` | landing (508) |
| `GET /dashboard` | `@auth_required` (547) |
| `GET /app` | `@auth_required` (585) |
| `GET /mobile-not-supported` | (488) |
| `GET /project-access` | (574) |
| `GET /project-invitations/accept` | (516) |
| `GET /llm-monitoring` | (3894) |

### GSC core

| Endpoint | Línea |
|---|---:|
| `GET /get-properties` | (459) |
| `POST /get-data` | (609) |
| `POST /download-excel` | (1397) |
| `POST /get-available-countries` | (2637) |
| `POST /api/url-keywords` | (2780) |

### SERP

| Endpoint | Línea |
|---|---:|
| `GET /api/serp` | (1445) |
| `GET /api/serp/position` | (1490) |
| `GET /api/serp/screenshot` | (1591) |

### AI Overview / quota

| Endpoint | Línea |
|---|---:|
| `POST /api/analyze-ai-overview` | (2239) — paywall + quota + parallel |
| `GET /api/quota/status` | (1615) |
| `POST /api/ai-recommendations` | (3134) — Jina+Gemini |
| `GET /api/ai-overview-stats` | (3213) |
| `GET /api/ai-overview-typology` | (3241) |
| `GET /api/ai-overview-history` | (3292) |

### Admin / debug

| Endpoint | Línea |
|---|---:|
| `POST /api/cache-management` | (3330) — admin only |
| `POST /api/test-url-matching` | (2611) — público |
| `GET /debug-serp-params` | (2724) |
| `POST /debug-ai-detection` | (3381) |
| `GET /__routes` | (208) |

### OAuth/Sesión (en `auth.py`)

`/auth/login`, `/auth/signup`, `/auth/callback`, `/auth/logout`, `/auth/status`, `/auth/keepalive`, `/auth/user`, `/auth/forgot-password`, `/auth/reset-password`, `/auth/email/login`, `/auth/email/signup`, `/auth/check-email`, `/connections`, `/connections/<id>/refresh`, `/connections/<id>` (DELETE).

---

## 8. Frontend

### Carga de scripts en `templates/index.html`

**Orden importante:**

1. **CDNs**: jQuery + DataTables + Chart.js + Grid.js.
2. **Módulos no-module**: `mobile-detector`, `navbar`, `competitor-analysis`, `keyword-exclusion`, `topic-clusters` + visualization, `collapsible-sections`, `session-manager`, `session-init`, `quota-ui`, `paywall`, `gsc-connect-modal`, `ai-reset-manager`, `tooltips-fix`, `onboarding-popups`.
3. **ES modules**: `ui-aio-recommendations-modal`, `ui-ai-overview-gridjs`, `ui-detailed-results-gridjs`, `number-utils`, `debug-number-formatting`, `ui-serp-modal`, `ui-overview-movers`, `ui-keywords-gridjs`, `ui-keyword-comparison-table`, `ui-date-selector`, `sidebar-navigation`, `app.js`, `ui-ai-overview`, `ui-ai-overlay`, `ui-table-enhancements`.

### CSS modular

~20 archivos: `ai-overview-section.css`, `ai-typology-chart.css`, `ai-overlay-styles.css`, `aio-recommendations-modal.css`, `serp-modal.css`, `keywords-section.css`, `pages-section.css`, `overview-section.css`, `quota-ui.css`, `paywall.css`, etc.

### Filtros

- `ui-date-selector.js` permite elegir M1 y opcional M2 (deltas).
- Dropdown de país se rellena desde `/get-available-countries`.
- Lista de URLs (textarea) y `match_type` (`contains` / `notContains`) se pasan al backend.

### Tablas

Todo Grid.js. Hay vistas separadas para "URLs", "Keywords", "URL→Keywords", "Detailed results" y "AI Overview".

### Charts

Chart.js para typology bar chart (basado en `/api/ai-overview-typology`).

---

## 9. Integración con cuota

Reglas en `app.py:2253-2297` para `/api/analyze-ai-overview`:

| Check | Resultado si falla |
|---|---|
| **Paywall**: `user.plan == 'free'` | 402 `paywall` |
| **Pausa por cuota**: `user.ai_overview_paused_until > NOW()` | 429 `quota_paused` |
| **Quota check**: `quota_used >= quota_limit` | Llama `pause_ai_overview_for_quota` y devuelve 429 `quota_exceeded` |

### Tracking

Tras análisis exitoso (`app.py:2522–2549`):

```python
track_quota_consumption(user_id, ru_consumed=successful_keywords, source='ai_overview')
# 1 RU por keyword analizada con éxito
```

### Permisos por plan (`quota_manager.py:307`)

| Plan | `can_use_ai_overview` |
|---|:---:|
| `free` | ❌ |
| `basic` / `premium` / `business` / `enterprise` | ✅ (si hay quota) |

### Kill switch

`AIO_MODULE_ENABLED` (env, default `true`) en `stripe_config.py:57` — kill switch global del módulo.

### Despausar

En webhook Stripe `invoice.payment_succeeded` se llama a `resume_quota_pauses_for_user` que limpia `ai_overview_paused_*` (database.py:2485+).

---

## 10. Variables de entorno

### Específicas del módulo GSC y AIO

| Variable | Default | Para qué |
|---|---|---|
| `SERPAPI_KEY` | (oblig.) | API key SerpAPI. |
| `JINA_API_KEY` | — | Jina.ai Reader (recomendaciones AIO). |
| `AIO_MODULE_ENABLED` | `true` | Habilita/deshabilita módulo AI Overview. |
| `AI_OVERVIEW_MAX_DURATION_SECONDS` | `1800` | Timeout global de un batch de análisis paralelo. |
| `SCREENSHOT_CACHE_TTL_SECONDS` | `3600` | TTL de la caché LRU de screenshots Playwright. |
| `SCREENSHOT_CACHE_MAX` | `200` | Tamaño máximo de la caché de screenshots. |
| `AIO_RECS_CACHE_TTL` | `86400` | TTL cache recomendaciones Jina/Gemini. |
| `CLIENT_SECRETS_FILE` | `client_secret.json` | Fallback si no hay env vars de OAuth. |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | — | OAuth (producción Railway). |
| `GOOGLE_REDIRECT_URI` | `http://localhost:5001/auth/callback` | Callback OAuth. |
| `TOKEN_ENCRYPTION_KEY` | — | Fernet key para cifrar `refresh_token`. |
| `TOKEN_FILE` | `token.json` | Solo se usa en `services/search_console.authenticate()` (legacy local). |

### Generales relacionadas

`RATE_LIMIT_DEFAULT`, `RATE_LIMIT_STORAGE_URL`, `FLASK_SECRET_KEY`, `OAUTHLIB_RELAX_TOKEN_SCOPE`, `SESSION_TIMEOUT_MINUTES`.

### Redis para cache AIO

`services/ai_cache.py` está hardcodeado a `localhost:6379`. **No tiene env var** — si Redis no está, falla silenciosamente (`cache_available = False`) y todo sigue funcionando sin caché.

---

## 11. Cron / análisis periódico

> **No hay cron específico de GSC.** Todo el flujo es **on-demand**.

Flujo:
1. El usuario abre `/app`, selecciona propiedad y fechas → `POST /get-data` → render.
2. Pulsa "Analizar Visibilidad AI" → `POST /api/analyze-ai-overview`.

A diferencia de Manual AI / AI Mode / LLM Monitoring (que tienen Bun service + cron diario), aquí no hay agendamiento. **La razón es que el producto está pensado como "informe interactivo"** y el coste de SerpAPI hace inviable un análisis pasivo de TODAS las keywords de la propiedad (que pueden ser miles).

### Cachés que reducen el coste

- **Redis 24h** para AIO detectado, 6h para no-AIO.
- **`ai_overview_analysis` UPSERT diario** — repetir el mismo análisis el mismo día no consume nuevas RU.

---

## 12. Multi-account / múltiples conexiones OAuth

Soportado por diseño desde la migración a `oauth_connections` + `gsc_properties`.

### Reglas

- Un `users.id` puede tener N `oauth_connections` (UNIQUE por `(user_id, provider, google_account_id)`).
- Cada conexión sincroniza sus `gsc_properties` (UNIQUE por `(user_id, site_url)` — si dos cuentas Google del mismo usuario tuvieran la misma propiedad, gana la última que escribe `connection_id`).
- `list_gsc_properties_for_user` (`database.py:741–762`) hace `JOIN oauth_connections` y devuelve `google_email` + `google_account_id` por propiedad → la UI puede mostrar a qué cuenta Google pertenece cada site.

### Selección automática

`get_connection_for_site(user_id, site_url)` (`database.py:764–783`) busca la fila en `gsc_properties` y devuelve la `oauth_connections` ligada.

Patrón estándar en cualquier ruta que necesite servicio autenticado:

```python
mapping_conn = get_connection_for_site(user_id, site_url)
if mapping_conn:
    gsc_service = get_authenticated_service_for_connection(mapping_conn, ...)
if not gsc_service:
    gsc_service = get_authenticated_service('searchconsole', 'v1')   # fallback a sesión
```

### UI

El usuario puede listar/refrescar/borrar conexiones desde:
- `GET /connections`
- `POST /connections/<id>/refresh`
- `DELETE /connections/<id>` (`auth.py:1924–1985`)

### Migración suave

Cuando el usuario hace login con Google, también se "upserta" la conexión con `create_or_update_oauth_connection` (`auth.py:1387`) para migración suave de cuentas que existían antes de la tabla.

---

## 13. Errores históricos y deuda

### Comentarios `# FIX` en código

| Fix | Detalle |
|---|---|
| **Fix #2** | (ai_analysis.py:64–132 y database.py:1804) — añadir columna `aio_serp_position` (top/middle/bottom). |
| **Fix #3** | (database.py:1808–1838 y 1903–1932) — índice único `idx_ai_analysis_upsert` + dedup previa para evitar duplicados por día. |

### Funciones LEGACY

En `services/ai_analysis.py` hay funciones marcadas como `LEGACY` y mantenidas por compatibilidad:
- `check_domain_in_references` (líneas 669–684).
- `check_domain_in_reference_indexes`.

### Caso especial documentado

`services/utils.urls_match`: hardcoded handling para `hmfertilitycenter.com` y subdominios (líneas 130–137).

### Migraciones

`migrate_quota_pause_fields.py` añade columnas `ai_overview_paused_*` a `users`.

### Documentos `.md`

`SOLUCION_QUERIES_INCOMPLETAS.md` está en la raíz pero **es de LLM Monitoring, no de GSC**.

**No hay archivo `.md` específico de GSC en la raíz.**

### Deuda técnica

| Deuda | Impacto | Riesgo |
|---|---|---|
| **`services/search_console.authenticate()`** (50 líneas) es legacy pre-multi-account: usa `InstalledAppFlow` y `token.json`. **No se invoca en producción**; existe como artefacto histórico. | Confusión para futura sesión. | Trivial. |
| **`SCREENSHOT_CACHE` in-memory por proceso** | Si Railway escala a >1 instancia, hay duplicación de capturas. | Medio. |
| **El paquete `serpapi` se importa en 3 sitios** (`services/serp_service.py`, `manual_ai/`, `ai_mode_projects/`) | Cualquier cambio de "engine" o `num` debe revisarse en los 3. | Medio. |
| **El paywall en `/api/analyze-ai-overview` y `/api/ai-recommendations` es duplicado** (mismas líneas casi idénticas en `app.py:2253-2297` y `app.py:3143-3165`) | Si se cambia la política, ambas rutas deben actualizarse. | Medio. |
| **AI Overview se pausa a nivel USUARIO** (no proyecto) | Patrón distinto al resto de módulos. | Bajo (intencional). |
| **`pause_ai_overview_for_quota` no tiene llamadores activos** verificados | Posible dead code. | Bajo. |
| **Redis hardcodeado a `localhost:6379`** sin env var | No portable. | Medio. |

---

## 14. Relación con los productos nuevos

| Producto | Origen | Relación con GSC |
|---|---|---|
| **Manual AI** (`/manual_ai/`) | **Evolución del análisis AIO de GSC.** | Reusa `services/ai_analysis.detect_ai_overview_elements`, `services/utils.urls_match`, `services/country_config`. Tablas propias `manual_ai_*` (no `ai_overview_analysis`). |
| **AI Mode** (`/ai_mode_projects/`) | Mismo patrón que Manual AI. | Replica arquitectura, distinto engine SerpAPI (`google_ai_mode`). |
| **LLM Monitoring** (`/llm_monitoring_*`) | Independiente. | No usa SerpAPI; consulta directamente APIs de OpenAI/Anthropic/Gemini/Perplexity. |

### Estado actual

El módulo GSC sigue **plenamente activo** y es la primera pantalla que ve un usuario logueado (`/dashboard` → `/app`). Coexiste con los otros módulos en la sidebar y comparte el mismo sistema de cuotas/RU.

---

## 15. Tests

> ⚠️ **No hay archivo de tests dedicado al módulo GSC** ni a `services/search_console.py`, `services/ai_analysis.py`, `services/ai_cache.py`, `services/serp_service.py`, `services/aio_recommendations.py`.

Los tests presentes en raíz y en `tests/` cubren: webhooks Stripe, db pool, LLM Monitoring (servicio, providers, frontend, endpoints, e2e, performance), AI Mode, project parallelism/timeout, cron alerts/routes, locale fidelity, stripe-aware reset.

Pueden tocar GSC tangencialmente pero **no es la cobertura principal**.

### Scripts ad-hoc útiles para diagnóstico

| Script | Para qué |
|---|---|
| `webhook_diagnostics.py` | Inspeccionar webhooks recibidos. |
| `oauth_diagnostic.py` | Diagnóstico OAuth. |
| `debug_oauth_flow.py` | Trazado del flow OAuth. |
| `debug_ai_structure.py` | Inspecciona estructura SerpAPI AIO. |
| `debug_qipu_detection.py` | Diagnóstico de detección de marca específica. |
| `debug_connection.py` | Diagnóstico de conexiones OAuth. |
| `diagnose_user_payment.py` | Diagnóstico billing. |
| `diagnostic_endpoint.py` | HTTP `/diagnostic/imports`. |

---

## TL;DR

1. **Producto histórico que da nombre al repo.** Sigue plenamente activo. Primera pantalla post-login (`/dashboard` → `/app`).
2. **OAuth Google con scope `webmasters.readonly`** + multi-cuenta soportado vía `oauth_connections`.
3. **Análisis AI Overview on-demand**: SerpAPI + 3 métodos de detección (oficial / fallback texto / ultra-estricto).
4. **No hay cron**: todo es interactivo. Cachés Redis 24h + UPSERT diario en `ai_overview_analysis` evitan recobros.
5. **Reusa código con Manual AI / AI Mode** (`services/ai_analysis`, `services/utils`, `services/country_config`).
6. **AI Overview se pausa a nivel USUARIO** (no proyecto), patrón distinto al resto de módulos.
7. **Tabla principal `ai_overview_analysis`** con UPSERT por `(site_url, keyword, country_code, DATE(analysis_date), user_id)`.
8. **Manual AI nació como evolución** de este AIO histórico (proyectos persistentes con cron diario).
9. **Sin tests dedicados** para este módulo (gap notable).
10. **Deuda principal**: `services/search_console.authenticate()` legacy, `SCREENSHOT_CACHE` no compartida entre workers, paywall duplicado, Redis hardcodeado.

— Fin del manual —
