# CLAUDE-integraciones.md — Integraciones externas

> Manual de las **integraciones con APIs y servicios de terceros** que la app consume: Google Search Console, SerpAPI, LLMs, Stripe, Brevo, OAuth Google, reCAPTCHA, Jina.ai, GTM, y MCP de uso del usuario (Ahrefs, GA4, Notion, Figma, Hostinger).
>
> Última actualización: 2026-05-08.
>
> Manuales relacionados: `CLAUDE-stripe-cuotas-crons.md`, `CLAUDE-search-console.md`, `CLAUDE-llm-monitoring.md`, `CLAUDE-emails-alertas.md`, `CLAUDE-auth-usuarios.md`, `CLAUDE-brand-radar.md`. Índice maestro: `CLAUDE-INDEX.md`.

---

## Índice

1. [Visión general en 5 minutos](#1-visión-general-en-5-minutos)
2. [Tabla resumen de integraciones](#2-tabla-resumen-de-integraciones)
3. [Google Search Console](#3-google-search-console)
4. [SerpAPI](#4-serpapi)
5. [Stripe](#5-stripe)
6. [LLMs (OpenAI / Anthropic / Gemini / Perplexity)](#6-llms-openai--anthropic--gemini--perplexity)
7. [Brevo (email + contactos)](#7-brevo-email--contactos)
8. [Google OAuth](#8-google-oauth)
9. [Google Tag Manager (GTM)](#9-google-tag-manager-gtm)
10. [reCAPTCHA v3](#10-recaptcha-v3)
11. [Jina.ai Reader](#11-jinaai-reader)
12. [Tools MCP (Ahrefs, GA4, Notion, Figma, Hostinger)](#12-tools-mcp-ahrefs-ga4-notion-figma-hostinger)
13. [Servicios NO integrados](#13-servicios-no-integrados)
14. [Patrón común de integración](#14-patrón-común-de-integración)
15. [Webhooks entrantes y APIs expuestas](#15-webhooks-entrantes-y-apis-expuestas)
16. [Variables de entorno por integración](#16-variables-de-entorno-por-integración)
17. [Errores históricos](#17-errores-históricos)
18. [Tests de integración](#18-tests-de-integración)

---

## 1. Visión general en 5 minutos

**8 integraciones activas** que la app consume directamente:

1. **Google Search Console** — datos de SEO del cliente (clicks/impressions/position).
2. **SerpAPI** — SERPs de Google, AI Overviews, AI Mode, screenshots Playwright.
3. **Stripe** — billing y suscripciones.
4. **OpenAI / Anthropic / Google Gemini / Perplexity** — LLM providers.
5. **Brevo** — email transaccional + contactos.
6. **Google OAuth** — autenticación de usuario.
7. **Google reCAPTCHA v3** — anti-bot en login/signup.
8. **Jina.ai Reader** — scraping limpio de páginas competidoras (recomendaciones AIO).

**3 integraciones pasivas / frontend**:

- **Google Tag Manager** (`GTM-NXJS74ZQ`) — analytics frontend.
- **Logo.dev** — logos de dominios en la UI.
- **Google Fonts** (Inter Tight, Libre Baskerville) — solo en landing.

**Tools MCP** (no son integraciones de la app, son herramientas del usuario en Claude): Ahrefs, GA4, Notion, Figma, Hostinger.

**Reglas de oro:**

1. **Sin wrapper interno común**: cada integración implementa su propio retry / timeout / logging.
2. **Cliente HTTP estándar `requests==2.32.3`**, excepto SerpAPI (librería oficial `google-search-results`) y GSC (`googleapiclient`).
3. **Todas las llamadas tienen `timeout=` explícito** (5s, 10s, 20s).
4. **Solo Stripe es webhook entrante**. La app no recibe callbacks de ningún otro servicio.
5. **No hay API pública** que la app exponga a terceros (todos los endpoints están detrás de sesión Flask o Bearer `CRON_TOKEN`).

---

## 2. Tabla resumen de integraciones

| Integración | Para qué | Auth | Archivos | Env vars |
|---|---|---|---|---|
| **Google Search Console** | Datos SEO del cliente | OAuth scope `webmasters.readonly` | `services/search_console.py`, `auth.py` | `GOOGLE_CLIENT_*` |
| **SerpAPI** | SERPs Google, AI Overviews, AI Mode | API key | `services/serp_service.py`, `quota_middleware.py` | `SERPAPI_KEY` |
| **Stripe** | Billing | Secret key + webhook secret | `stripe_webhooks.py`, `billing_*.py` | `STRIPE_*` |
| **OpenAI** | LLM Monitoring | API key | `services/llm_providers/openai_provider.py` | `OPENAI_API_KEY` |
| **Anthropic** | LLM Monitoring | API key | `services/llm_providers/anthropic_provider.py` | `ANTHROPIC_API_KEY` |
| **Google Gemini** | LLM Monitoring | API key | `services/llm_providers/google_provider.py` | `GOOGLE_API_KEY` |
| **Perplexity** | LLM Monitoring | API key | `services/llm_providers/perplexity_provider.py` | `PERPLEXITY_API_KEY` |
| **Brevo SMTP** | Email transaccional | Username/password | `email_service.py` | `SMTP_*`, `FROM_*` |
| **Brevo API** | Contactos / listas | API key | `brevo_api_service.py` | `BREVO_*` |
| **Google OAuth** | Login | Client ID/Secret | `auth.py` | `GOOGLE_CLIENT_*` |
| **reCAPTCHA v3** | Anti-bot | Site key + secret | `auth.py` | `RECAPTCHA_*` |
| **Jina.ai Reader** | Scraping para recomendaciones AIO | API key | `services/aio_recommendations.py` | `JINA_API_KEY` |
| **GTM** | Analytics frontend | Container ID hardcoded | Plantillas Jinja | — |

---

## 3. Google Search Console

### Para qué

Leer datos de Search Console (clicks, impressions, CTR, position) para dashboards y para detectar la presencia de AI Overviews.

### Archivos

| Archivo | Rol |
|---|---|
| `services/search_console.py` | `authenticate()` y `fetch_searchconsole_data_single_call()`. Solo lee (`searchanalytics.query`). |
| `auth.py` | Flow OAuth, scope `webmasters.readonly`. |
| `app.py` | Múltiples llamadas a `fetch_searchconsole_data_single_call` (líneas 253, 758, 798, 828, 864, 1012, 1081, 1116, 2668, 2904) para `ai_overview_analysis`, dashboards, `analyze-ai-overview`. |

### Auth

OAuth2 Google. **Scopes** en `auth.py:117-121`:

```
https://www.googleapis.com/auth/webmasters.readonly
https://www.googleapis.com/auth/userinfo.email
https://www.googleapis.com/auth/userinfo.profile
```

OAuth se carga desde env (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`) o desde `client_secret.json` (fallback local).

### Librerías

```
google-auth==2.35.0
google-auth-oauthlib==1.2.1
google-api-python-client==2.147.0
```

### Rate limits

> ⚠️ **No hay retry específico** en `services/search_console.py`. El manejo de 429 es a posteriori en `app.py:3111` devolviendo JSON `error_type: rate_limit`. También hay manejo de 401/403/429 en `app.py:3095-3120`.

### Multi-cuenta

Un user puede tener N `oauth_connections` (UNIQUE por `google_account_id`). Cada conexión sincroniza sus `gsc_properties`. Ver `CLAUDE-auth-usuarios.md` y `CLAUDE-search-console.md`.

---

## 4. SerpAPI

### Para qué

Obtener SERPs de Google, AI Overviews, AI Mode, screenshots, organic results. **Toda llamada SerpAPI pasa por el quota middleware** (excepto AI Mode — ver deuda).

### Archivos

| Archivo | Rol |
|---|---|
| `services/serp_service.py` | `get_serp_json()`, `get_serp_html()`, `get_page_screenshot()`. Todas usan `quota_protected_serp_call`. |
| `quota_middleware.py` | `_execute_serp_call()` (cliente real con `serpapi.GoogleSearch`), retries y caché in-memory. |
| `ai_mode_projects/services/analysis_service.py:370` | Uso **directo** de `GoogleSearch` para `engine=google_ai_mode` (NO pasa por el middleware central; lee `SERPAPI_API_KEY` directamente). |

### Engines usados

| Engine | Uso |
|---|---|
| `google` | SERP estándar (`services/serp_service.py:138`). |
| `google_ai_mode` | Análisis Google AI Mode (`ai_mode_projects/services/analysis_service.py:362`). |
| (sin engine separado) | Google AI Overview se infiere del JSON con campos `ai_overview`, `generative_ai_overview`, `google_ai_overview`, `answer_box` (`app.py:3431`). |

### Quota cache (LRU + TTL)

En `quota_middleware.py`:

| Variable | Default |
|---|---|
| `SERP_CALL_CACHE_TTL_SECONDS` | `3600` |
| `SERP_CALL_CACHE_MAX` | `5000` |

Caché in-memory por params (excluyendo `api_key`); MD5 hash. **Hit = 0 RU**.

### Screenshot cache (separado)

En `services/serp_service.py`:

| Variable | Default |
|---|---|
| `SCREENSHOT_CACHE_TTL_SECONDS` | `3600` |
| `SCREENSHOT_CACHE_MAX` | `200` |

> ⚠️ `SCREENSHOT_CACHE` es **in-memory por proceso**, no compartida entre workers. Si Railway escala a >1 instancia, hay duplicación de capturas.

### Retry

`quota_middleware.py:293-294`:

| Variable | Default |
|---|---|
| `SERPAPI_RETRY_ATTEMPTS` | `3` |
| `SERPAPI_RETRY_BACKOFF_SECONDS` | `1.0` (exponencial: `delay * 2^(attempt-1)`) |

**Solo reintenta errores transitorios** (`_should_retry_serp_error`):
- `timeout`
- `429`, `502`, `503`, `504`
- `"rate limit"`, `"connection"`, `"network"`, `"reset"`, `"unavailable"`

**NO reintenta**: `invalid api key`.

### API key

| Variable | Notas |
|---|---|
| `SERPAPI_KEY` | Canónica (app principal). |
| `SERPAPI_API_KEY` | Alias usado por AI Mode service y `quick_test_ai_mode.py`. |

> ⚠️ **Inconsistencia de naming**: dos formas conviven. Configurar ambas para evitar gaps.

### Cliente HTTP

Librería oficial `google-search-results==2.4.2`.

### Patrón "reserve & confirm"

`quota_middleware.py:1-13`: pre-check → reserve RU → execute → confirm o devolver. Aplicado a todas las rutas `/api/serp*` y screenshots (Fase 4 quotas).

> ⚠️ **AI Mode NO pasa por el middleware central**: lee `SERPAPI_API_KEY` directo y usa `GoogleSearch` sin `quota_protected_serp_call`. Esto significa que las llamadas de AI Mode **no consumen RU del sistema de cuotas Fase 4** (puede ser intencional si AI Mode tiene su propia contabilidad — verificar).

---

## 5. Stripe

Ver `CLAUDE-stripe-cuotas-crons.md`. Resumen:

- Endpoint `POST /webhooks/stripe` registrado en `app.py:136` mediante `create_webhook_route(app)` (en `stripe_webhooks.py:763`).
- Verificación de firma con `stripe.Webhook.construct_event` (línea 40), soporta `webhook_secret` y `webhook_secret_alt`.
- Idempotencia vía tabla `stripe_webhook_events`.
- 6 eventos manejados: `checkout.session.completed`, `customer.subscription.created/updated/deleted`, `invoice.payment_succeeded`, `invoice.payment_failed`.

---

## 6. LLMs (OpenAI / Anthropic / Gemini / Perplexity)

Ver `CLAUDE-llm-monitoring.md`. Resumen:

- Providers en `services/llm_providers/`: `openai_provider.py`, `anthropic_provider.py`, `google_provider.py`, `perplexity_provider.py`, `provider_factory.py`, `retry_handler.py`.
- API keys cargadas como **fallback global** en `provider_factory.py:135-143`:
  - `OPENAI_API_KEY`
  - `ANTHROPIC_API_KEY`
  - `GOOGLE_API_KEY` o `GOOGLE_AI_API_KEY` (alias)
  - `PERPLEXITY_API_KEY`
- Claves por usuario encriptadas en BD con `ENCRYPTION_KEY` (tabla `user_llm_api_keys`, **no usada actualmente**).
- Sistema de retry de 5 capas con circuit breaker singleton.
- Modelos activos en `llm_model_registry` (single source of truth de pricing).

---

## 7. Brevo (email + contactos)

Ver `CLAUDE-emails-alertas.md`. Resumen:

### Dos vías

1. **API HTTPS** — `brevo_api_service.py`. Endpoints: `https://api.brevo.com/v3/smtp/email`, `…/v3/contacts`, `…/v3/contacts/lists`, `…/v3/contacts/folders`. Header `api-key`. Timeouts de `10s`.
2. **SMTP** — `email_service.py`. `smtp-relay.brevo.com:587` STARTTLS. Login `91d4f0001@smtp-brevo.com`-style.

### Env vars

`BREVO_API_KEY`, `BREVO_CONTACT_LIST_ID`, `BREVO_TARGET_LIST_NAME`, `BREVO_FOLDER_ID`, `FROM_EMAIL`, `FROM_NAME`, `PUBLIC_BASE_URL`, `ALERT_EMAIL_TO`, `ALERT_EMAIL_FROM`, `SMTP_SERVER`, `SMTP_PORT`, `USE_STARTTLS`, `SMTP_USERNAME`, `SMTP_PASSWORD`.

---

## 8. Google OAuth

Ver `CLAUDE-auth-usuarios.md`. Resumen:

| Variable | Para qué |
|---|---|
| `GOOGLE_CLIENT_ID` | OAuth client. |
| `GOOGLE_CLIENT_SECRET` | OAuth secret. |
| `GOOGLE_REDIRECT_URI` | Callback URL. |
| `OAUTHLIB_RELAX_TOKEN_SCOPE` | `'1'` (siempre). |
| `OAUTHLIB_INSECURE_TRANSPORT` | `'1'` solo en local (no Railway). |
| `TOKEN_ENCRYPTION_KEY` | Fernet key para `oauth_connections.refresh_token_encrypted`. |

Scopes en `auth.py:117-121`. Multi-cuenta soportado.

---

## 9. Google Tag Manager (GTM)

### Container ID

**`GTM-NXJS74ZQ`** (hardcoded en plantillas).

### Para qué

Contenedor único de GTM cargado en TODAS las páginas relevantes:
- `index.html`, `dashboard.html`, `landing.html`.
- `login.html`, `signup.html`, `forgot_password.html`, `reset_password.html`.
- `manual_ai_dashboard.html`, `ai_mode_dashboard.html`, `llm_monitoring.html`.

Carga `gtm.js` y noscript-iframe `ns.html` estándar.

### Uso

Tracking front-end. Lo que se haga dentro (GA4, Hotjar, etc.) está configurado **dentro de GTM**, no en código. La app **no envía `dataLayer.push` específicos** detectables; es GTM "vanilla loader" en cada template.

> ⚠️ **El ID está hardcoded en 10 templates**. Si se cambia el container, hay que tocar todos los archivos. Podría centralizarse en una variable de Flask context processor.

---

## 10. reCAPTCHA v3

### Para qué

Anti-bot en login y signup.

### Archivo

`auth.py`.

### Lógica (`verify_recaptcha`, líneas 78-114)

1. Lee `RECAPTCHA_SECRET_KEY`, `RECAPTCHA_MIN_SCORE` (default `0.5`).
2. POST a `https://www.google.com/recaptcha/api/siteverify` (timeout 5s).
3. Verifica `success`, `action` y `score >= min_score`.

### Fail-open

> ⚠️ **Si `RECAPTCHA_SECRET_KEY` no está, devuelve `True` (permite)** — fail-open. Decisión consciente para no bloquear desarrollo local sin captcha.

### Front

Env `RECAPTCHA_SITE_KEY` se pasa a templates `login.html` y `signup.html`.

### Aplicado en

| Endpoint | Aplica reCAPTCHA |
|---|:---:|
| Signup local (`/auth/email/signup`) | ✅ |
| Login local (`/auth/email/login`) | ✅ |
| Forgot password | ❌ |
| Reset password | ❌ |
| OAuth callback | ❌ |

---

## 11. Jina.ai Reader

### Para qué

Scrapear contenido limpio de páginas competidoras citadas en AI Overview, para que el motor de recomendaciones SEO razone con su texto real.

### Archivo

`services/aio_recommendations.py` — funciones `fetch_page_content()` (línea 86) y `fetch_multiple_pages()` (línea 152).

### Endpoint

```
GET https://r.jina.ai/<url-original>
Authorization: Bearer $JINA_API_KEY
Accept: application/json
```

Devuelve `{title, content, description}`.

### Concurrencia

`ThreadPoolExecutor(max_workers=4)`, hasta `max_pages=4`.

### Truncamiento

Contenido limitado a `CONTENT_MAX_CHARS=3000` (truncado en el word boundary más cercano).

### Robustez

`requests.get(timeout=20)`. Captura `Timeout`, `HTTPError`, genérico. Si `JINA_API_KEY` no está, devuelve `success=False` con error claro (no rompe el flujo).

### Env var

`JINA_API_KEY`.

---

## 12. Tools MCP (Ahrefs, GA4, Notion, Figma, Hostinger)

> **Estas NO son integraciones de la app.** Son herramientas disponibles en la sesión de Claude para que Carlos las use ad-hoc desde la conversación. La web app de ClicandSEO **no las consume**.

### Ahrefs MCP

- Namespace: `mcp__63aa9431-6a58-47b2-94d4-47263dcb780b__*`.
- ~70 tools (Brand Radar, Site Explorer, Keywords Explorer, Rank Tracker, Site Audit, Web Analytics, Social Media...).
- Ver `CLAUDE-brand-radar.md` para el detalle de Brand Radar.
- **Cero** integración HTTP en el código de la app.

### GA4 MCP

- Namespace: `mcp__GA4_*` y `mcp__ga4-*` (4 instancias distintas: GA4_Laserum, GA4_PT_Laserum, ga4-HMFC, ga4-analytics).
- Tools: `get_ga4_data`, `get_property_schema`, `search_schema`, etc.
- **NO se usa desde la app**. Sin imports `google-analytics-data`, sin env de `GA4_PROPERTY_ID`, sin envío de eventos `gtag('event'...)` en templates. Los eventos van por GTM (ver §9).

### Notion MCP

- Namespace: `mcp__d671b663...__notion-*`.
- Tools: `notion-search`, `notion-fetch`, `notion-create-pages`, etc.
- **NO se usa desde la app**.

### Figma MCP

- Namespace: `mcp__f016b035…__*`.
- Tools de design system, Code Connect, screenshots de Figma, etc.
- **NO se usa desde la app**. La carpeta `brandbook/` en raíz del repo contiene exports estáticos del styleguide (logos SVG, PDF, CSS), pero no llama a la API de Figma.

### Hostinger MCP

- Namespace: `mcp__hostinger-mcp__*`.
- VPS / DNS / Domains / Hosting / Reach / Billing.
- **NO se usa desde la app**.

---

## 13. Servicios NO integrados

Búsquedas exhaustivas (cero imports, cero env vars, cero `requests` a sus dominios):

- ❌ Twilio
- ❌ Slack (envío de mensajes)
- ❌ AWS / S3 / GCS
- ❌ Mailgun / SendGrid / Mailchimp
- ❌ Mixpanel / Segment / Hotjar
- ❌ Cloudflare API
- ❌ OpenRouter / Cohere
- ❌ Bing Search / Yandex / DuckDuckGo
- ❌ Sentry / Datadog / New Relic

---

## 14. Patrón común de integración

### Cliente HTTP estándar

- La mayoría usa **`requests==2.32.3`** directamente.
- SerpAPI usa la librería oficial `google-search-results`.
- GSC usa `googleapiclient`.

### Sin wrapper interno común

> ⚠️ **NO hay** `services/http_client.py` con retry global. Cada integración implementa su propio retry:

| Integración | Retry |
|---|---|
| **SerpAPI** | Exponencial en `quota_middleware.py:293-341`. Detector explícito `_should_retry_serp_error()`. |
| **LLM providers** | `services/llm_providers/retry_handler.py` (5 capas, circuit breaker). |
| **Brevo** | Timeout 10s, **sin retry** (un solo intento por llamada). |
| **Jina** | Timeout 20s, **sin retry**. |
| **reCAPTCHA** | Timeout 5s, **sin retry**. |
| **GSC** | **Sin retry**; el 429 se devuelve al frontend. |

### Logs

Cada integración usa `logger = logging.getLogger(__name__)` con su nombre de módulo. Mensajes con emojis (`✅`, `❌`, `⏳`, `🔍`) para rastreo visual rápido en Railway.

### Timeouts uniformemente aplicados

Todos los `requests.get/post` llevan `timeout=` explícito (5s, 10s, 20s) — buena práctica.

---

## 15. Webhooks entrantes y APIs expuestas

### Webhooks entrantes

| Endpoint | Servicio | Verificación |
|---|---|---|
| `POST /webhooks/stripe` | Stripe | Firma `stripe.Webhook.construct_event` con `webhook_secret` o `webhook_secret_alt` |

> **NO hay otros webhooks entrantes**. La app **no recibe** callbacks de Brevo, SerpAPI, LLMs, Jina, reCAPTCHA o GSC.

### APIs internas que la app expone a terceros

> **No hay API pública documentada.**

- Los endpoints `/api/*` están todos detrás de **sesión Flask** (login OAuth).
- Los endpoints `/api/cron/*` (definidos en `cron_routes.py`) usan **Bearer token** (`CRON_TOKEN`) — no son públicos, son para los servicios Bun de Railway.
- **Webhook signing saliente**: la app no firma ningún payload saliente (no HMAC custom, no JWT signing).
- **No hay API key system para clientes externos**. Lo único parecido es el `CRON_TOKEN` (interno).

---

## 16. Variables de entorno por integración

### Google OAuth / GSC

```
GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI
CLIENT_SECRETS_FILE, TOKEN_FILE  (fallback local)
OAUTHLIB_RELAX_TOKEN_SCOPE, OAUTHLIB_INSECURE_TRANSPORT (auto-set)
```

### SerpAPI

```
SERPAPI_KEY (canónica), SERPAPI_API_KEY (alias usado por AI Mode)
SERP_CALL_CACHE_TTL_SECONDS, SERP_CALL_CACHE_MAX
SCREENSHOT_CACHE_TTL_SECONDS, SCREENSHOT_CACHE_MAX
SERPAPI_RETRY_ATTEMPTS, SERPAPI_RETRY_BACKOFF_SECONDS
```

### Stripe

```
STRIPE_SECRET_KEY, STRIPE_PUBLISHABLE_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_WEBHOOK_SECRET_ALT
PRICE_ID_BASIC*, PRICE_ID_PREMIUM*, PRICE_ID_BUSINESS*, STRIPE_ENTERPRISE_PRODUCT_ID
CUSTOMER_PORTAL_RETURN_URL
```

### LLMs

```
OPENAI_API_KEY, ANTHROPIC_API_KEY
GOOGLE_API_KEY (alias GOOGLE_AI_API_KEY)
PERPLEXITY_API_KEY
ENCRYPTION_KEY (cifrado de las API keys de usuario en BD - tabla no usada)
```

### Brevo / email

```
BREVO_API_KEY, BREVO_CONTACT_LIST_ID, BREVO_TARGET_LIST_NAME, BREVO_FOLDER_ID
SMTP_SERVER, SMTP_PORT, USE_STARTTLS, SMTP_USERNAME, SMTP_PASSWORD
FROM_EMAIL, FROM_NAME, PUBLIC_BASE_URL
ALERT_EMAIL_TO, ALERT_EMAIL_FROM (mencionados en docs antiguos pero no usados)
```

### reCAPTCHA

```
RECAPTCHA_SECRET_KEY, RECAPTCHA_SITE_KEY, RECAPTCHA_MIN_SCORE
```

### Jina

```
JINA_API_KEY
```

### Crons

```
CRON_TOKEN, APP_URL
LLM_PROJECT_PARALLELISM, LLM_PROJECT_TIMEOUT_MINUTES
CRON_ALERTS_ENABLED, CRON_ALERT_*
```

### Otras infra

```
DATABASE_URL, DB_POOL_MIN, DB_POOL_MAX, DB_POOL_WAIT_SECONDS
FLASK_SECRET_KEY, SESSION_TIMEOUT_MINUTES, SESSION_WARNING_MINUTES
RAILWAY_ENVIRONMENT (detector)
```

### ⚠️ Vulnerabilidad

`/Users/carlosgonzalez/Desktop/app/APP-WEB-GSC-AI/search_console_webapp/RAILWAY_STAGING_VARIABLES.txt` contiene **secretos en claro** (Stripe test keys, BREVO_API_KEY, SERPAPI_KEY, OPENAI/ANTHROPIC/GOOGLE/PERPLEXITY keys, FLASK_SECRET_KEY, GOOGLE_CLIENT_SECRET, ENCRYPTION_KEY).

**El archivo está commited al repo**. Aunque solo son del entorno staging, es un riesgo conocido. Auditar `.gitignore` y rotar todas esas keys.

---

## 17. Errores históricos

Documentos `.md` de troubleshooting:

| Archivo | Cubre |
|---|---|
| `SOLUCION_OPENAI_GPT5.md` | GPT-5 cambió `max_tokens` por `max_completion_tokens`; precios incorrectos en BD; modelo `gpt-4o` vs `gpt-5` mal flaggeado. Fix en `openai_provider.py`. |
| `SOLUCION_QUERIES_INCOMPLETAS.md` | Discrepancia de número de queries entre Gemini/ChatGPT/Perplexity/Claude por timeouts y rate-limits diferentes por proveedor. |
| `FIX_DISCREPANCIA_MENCIONES_LLM.md` | Discrepancia de menciones detectadas (LLM). |
| `ANALISIS_RETRY_SYSTEM.md`, `IMPLEMENTACION_RETRY*.md` | Diseño/implementación del sistema de retry de LLM. |
| `MEJORAS_LLM_MONITORING.md`, `OPTIMIZACION_CRON_DIARIO.md` | Mejoras de rendimiento y paralelismo de crons. |
| `FIX_GRIDJS_ERROR.md` | Bug de frontend (no integración externa). |

> **NO hay incidentes documentados** de Brevo, Jina, GSC ni reCAPTCHA en archivos `.md`.

### Inconsistencia detectada

**SerpAPI usa dos nombres de env**: `SERPAPI_KEY` y `SERPAPI_API_KEY`. AI Mode lee `SERPAPI_API_KEY` directamente y NO pasa por el quota middleware central — esto significa que las llamadas de AI Mode **no consumen RU del sistema de cuotas Fase 4** (puede ser intencional si AI Mode tiene su propia contabilidad, pero merece verificación).

---

## 18. Tests de integración

### Tests con APIs reales

| Archivo | Cubre |
|---|---|
| `test_all_llm_providers.py` | Diagnóstico real contra OpenAI / Anthropic / Google / Perplexity (requiere API keys vivas; ejecutable como `railway run python …`). |
| `test_llm_providers.py` | Tests unitarios de providers. |
| `test_locale_fidelity.py` | Verifica fidelidad de locale en LLM responses. |
| `test_llm_cron_jobs.py`, `test_llm_monitoring_endpoints.py`, `test_llm_monitoring_frontend.py`, `test_llm_monitoring_service.py` | Cron y endpoints de LLM Monitoring. |
| `test_stripe_aware_reset.py`, `test_webhook_hardening.py` | Stripe (mocks de `stripe.Subscription.retrieve`). |
| `test_cron_alerts.py`, `test_cron_routes.py`, `test_db_pool.py`, `test_project_timeout.py`, `test_project_parallelism.py` | Infra/crons. |
| `test_ai_mode_system.py`, `quick_test_ai_mode.py` | AI Mode (incluye check de `SERPAPI_API_KEY`). |

`tests/` (carpeta) — tests más estructurados de LLM Monitoring (`test_llm_monitoring_e2e.py`, `…_performance.py`, `…_service.py`, `test_llm_providers.py`).

### Sin cobertura

> ⚠️ **NO hay tests de integración real** para:
> - Brevo (API ni SMTP).
> - Jina.
> - reCAPTCHA.
> - GSC.

Lo que existe es indirecto vía mocks.

---

## TL;DR

1. **8 integraciones activas**: GSC, SerpAPI, Stripe, OpenAI, Anthropic, Gemini, Perplexity, Brevo, OAuth Google, reCAPTCHA, Jina.
2. **Sin wrapper HTTP común**: cada integración tiene su propio retry/timeout. SerpAPI y LLMs los más sofisticados (5 capas).
3. **Solo Stripe es webhook entrante.** La app no recibe callbacks de ningún otro servicio.
4. **No hay API pública**: todos los endpoints están detrás de sesión Flask o Bearer `CRON_TOKEN`.
5. **GTM `GTM-NXJS74ZQ` hardcoded en 10 plantillas** — deuda.
6. **AI Mode salta el quota middleware** de SerpAPI (lee `SERPAPI_API_KEY` directo) — verificar si es intencional.
7. **Brevo, Jina, reCAPTCHA, GSC sin reintentos** — fallo único = error definitivo.
8. **`RAILWAY_STAGING_VARIABLES.txt` con secretos en plano commiteado** — vulnerabilidad. Rotar.
9. **Tools MCP de Ahrefs/GA4/Notion/Figma/Hostinger NO son integraciones de la app** — son del usuario en Claude.
10. **Servicios NO integrados**: Twilio, Slack, AWS/GCS, Mailgun, Mixpanel, Sentry, Bing.

— Fin del manual —
