# CLAUDE-emails-alertas.md — Emails y Alertas

> Manual del **sistema de email transaccional y alertas** del proyecto: Brevo SMTP + API, alertas de cron, plantillas hardcoded, rate-limit.
>
> Última actualización: 2026-05-08.
>
> Manuales relacionados: `CLAUDE-stripe-cuotas-crons.md` (alertas Stripe webhook), `CLAUDE-llm-monitoring.md` (cron alerts y model approval), `CLAUDE-auth-usuarios.md` (welcome y password reset). Índice maestro: `CLAUDE-INDEX.md`.

---

## Índice

1. [Visión general en 5 minutos](#1-visión-general-en-5-minutos)
2. [Mapa de archivos](#2-mapa-de-archivos)
3. [Brevo SMTP (`email_service.py`)](#3-brevo-smtp-email_servicepy)
4. [Brevo API (`brevo_api_service.py`)](#4-brevo-api-brevo_api_servicepy)
5. [Sistema de alertas del cron LLM (`cron_alerts.py`)](#5-sistema-de-alertas-del-cron-llm-cron_alertspy)
6. [Alertas Stripe webhook](#6-alertas-stripe-webhook)
7. [Stuck Quota Alert](#7-stuck-quota-alert)
8. [Email de aprobación de modelos LLM](#8-email-de-aprobación-de-modelos-llm)
9. [Welcome y Password Reset](#9-welcome-y-password-reset)
10. [Plantillas de email](#10-plantillas-de-email)
11. [Variables de entorno](#11-variables-de-entorno)
12. [Endpoints relacionados](#12-endpoints-relacionados)
13. [Operaciones manuales](#13-operaciones-manuales)
14. [Errores históricos y deuda técnica](#14-errores-históricos-y-deuda-técnica)
15. [Tests](#15-tests)

---

## 1. Visión general en 5 minutos

**Proveedor único: Brevo** (ex Sendinblue). Se usa de **dos formas en paralelo**:

- **SMTP** (`smtp-relay.brevo.com:587` STARTTLS) vía `email_service.py` — envío puro de transaccionales.
- **API REST** (`https://api.brevo.com/v3/...`) vía `brevo_api_service.py` — envío rápido y, sobre todo, gestión de **contactos / listas / folders**.

**Casos de uso:**

| Caso | Trigger | Archivo |
|---|---|---|
| Welcome (registro) | signup local + signup Google | `email_service.send_welcome_email` desde `auth.py:884, 1201` |
| Password reset | endpoint forgot-password | `auth.py:660-673` |
| Inicio de trial 7d | webhook Stripe `subscription.created/updated` con `status=trialing` | `stripe_webhooks.py:567-592` |
| Alertas cron LLM (duración / error rate / cost spike) | tras `release_analysis_lock` | `cron_alerts.py` invocado desde `database.py:2710` |
| Webhook Stripe customer no encontrado | webhook con `customer_id` no asociado | `stripe_webhooks._alert_unmatched_customer` |
| Stuck quota (usuarios atascados >24h) | tras `daily_quota_reset_cron` | `cron_routes._send_stuck_quota_alert` |
| Aprobación de modelos LLM nuevos | model discovery semanal | `llm_monitoring_routes.py:8225-8359` |
| Confirmación tras aprobar modelo | endpoint `/models/approve` | `llm_monitoring_routes.py:8503-8522` |
| Alertas genéricas Bun → Flask | falla un Bun cron service | `llm_monitoring_routes.py:8717` (`POST /cron/alert`) |
| Notificación discovery (legacy) | clase `LLMModelDiscovery.send_notification` | `weekly_model_discovery_cron.py:312-345` |
| Invitaciones a proyectos | invitar viewer a un proyecto | `services/project_access_service.py:408-453` |

**Reglas de oro:**

1. **No hay templates Jinja externos para emails**: todo el HTML se construye **inline** en strings f"" dentro del código Python.
2. **Welcome/password reset usan API Brevo primero, SMTP como fallback** (más rápido y resiliente).
3. **Alertas internas siempre vía SMTP** (`cron_alerts`, stuck quota, unmatched customer, model approval, project invitations).
4. **Rate-limit en alertas Stripe** vía tabla `stripe_webhook_alerts_sent` (no spamear).
5. **Kill switch global `CRON_ALERTS_ENABLED`** silencia todas las alertas de cron.
6. **Idiomas mezclados** (deuda): emails de usuario en inglés, alertas internas en español.

---

## 2. Mapa de archivos

| Archivo | Rol |
|---|---|
| `email_service.py` | **SMTP wrapper Brevo** + plantillas (welcome, password reset, trial started, test). |
| `brevo_api_service.py` | **Brevo HTTP API**: `send_email_via_api`, `send_password_reset_via_api`, gestión de listas/contactos. |
| `cron_alerts.py` | Sistema de alertas del cron LLM (3 chequeos + email batched). |
| `sync_users_to_brevo.py` | Script CLI para volcar `users` BD → lista de Brevo. |
| `cron_routes.py` | Endpoints `/api/cron/quota-reset`, `/api/cron/quota-health-check` + `_send_stuck_quota_alert`. |
| `stripe_webhooks.py` | `_alert_unmatched_customer` (l. 209) + email trial-started (l. 567). |
| `llm_monitoring_routes.py` | Endpoints `/cron/alert`, `/models/approve`, `/models/reject`, `/cron/model-discovery` (~l. 7983-8800). |
| `weekly_model_discovery_cron.py` | Clase legacy `LLMModelDiscovery.send_notification` (l. 312). |
| `llm_monitoring_cron_function.js` | Bun cron — al fallar `fetch`, postea a `/cron/alert`. |
| `ai_mode_cron_function.js` | Idem para AI Mode. |
| `llm_model_discovery_cron_function.js` | Bun cron model discovery — postea a `/cron/alert` si falla. |
| `services/project_access_service.py` | `_send_project_invitation_email` (l. 408). |
| `auth.py` | Llama a `send_welcome_email`, `send_password_reset_email/_via_api`, sincroniza Brevo en signup. |
| `database.py:2710` | Hook a `cron_alerts.check_and_send_cron_alerts` tras `release_analysis_lock`. |
| `test_cron_alerts.py` | Test del módulo `cron_alerts`. |
| `test_cron_routes.py` | Test del health-check + stuck quota alert. |
| `email_preview.html` | Snapshot estático del HTML del password-reset (NO se sirve). |

> ⚠️ **No hay carpeta `/templates/email/`**. Todos los emails están **hardcoded** como f-strings.

---

## 3. Brevo SMTP (`email_service.py`)

### Vars de entorno

| Variable | Default | Notas |
|---|---|---|
| `SMTP_SERVER` | `smtp-relay.brevo.com` | |
| `SMTP_PORT` | `587` | |
| `USE_STARTTLS` | `true` | |
| `SMTP_USERNAME` | `info@clicandseo.com` | |
| `SMTP_PASSWORD` | (oblig.) | Si falta, `send_email` retorna `False` y loguea error. |
| `FROM_EMAIL` | `info@clicandseo.com` | |
| `FROM_NAME` | `ClicandSEO` | |
| `PUBLIC_BASE_URL` | `https://app.clicandseo.com` | Se usa para construir `LOGO_URL`. |

### Función central: `send_email`

```python
send_email(to_email, subject, html_body, text_body=None) -> bool
```

- Construye `MIMEMultipart("alternative")`, adjunta texto+HTML.
- Si `USE_STARTTLS or SMTP_PORT == 587` → STARTTLS; si no → SSL directo (puerto 465).
- Timeout SMTP fijo en **30 s** ("optimizado para Railway/Brevo").
- Manejo de errores: try/except global → log y `return False`. **Sin reintentos**.

### Funciones derivadas

| Función | Qué hace |
|---|---|
| `send_password_reset_email(to_email, reset_url, user_name)` | HTML rico con logo, botón verde lima `#D8F9B8`, fallback URL plana. |
| `send_welcome_email(to_email, user_name)` | Intenta API Brevo primero, fallback SMTP. |
| `send_trial_started_email(to_email, plan, trial_end)` | Idem. |
| `send_test_email(to_email)` | Utilidad. |

### Ejecutable directamente

```bash
python email_service.py
# pide email por stdin → manda send_test_email
```

---

## 4. Brevo API (`brevo_api_service.py`)

### Reparto API vs SMTP

- **API**: contactos / listas / folders + envío rápido de transaccional cuando hace falta velocidad (welcome, trial-started, password-reset).
- **SMTP**: fallback de envío + camino exclusivo para alertas internas (`cron_alerts`, stuck quota, unmatched customer, model approval, project invitations).

### Vars de entorno

| Variable | Default | Notas |
|---|---|---|
| `BREVO_API_KEY` | — | Sin ella, todas las funciones API retornan `False`. |
| `BREVO_CONTACT_LIST_ID` | — | Si está, se respeta antes de buscar por nombre. |
| `BREVO_FOLDER_ID` | — | Folder donde crear listas nuevas. |
| `BREVO_TARGET_LIST_NAME` | `Usuarios Registrados` | Usado por `sync_users_to_brevo.py`. |

### Endpoints Brevo

| Endpoint | Para qué |
|---|---|
| `POST /v3/smtp/email` | `send_email_via_api`. 201 = OK. Headers: `X-Mailer: ClicandSEO-App`, `List-Id: clicandseo.app`. |
| `GET /v3/contacts/lists` | Buscar lista por nombre (paginación). |
| `GET /v3/contacts/folders` | Descubrir folder por defecto. |
| `POST /v3/contacts/lists` | Crear lista nueva. |
| `POST /v3/contacts` | Upsert (`updateEnabled: True`). |
| `PUT /v3/contacts/{email}` | Refuerzo de atributos tras crear. |
| `POST /v3/contacts/lists/{id}/contacts/add` | Añadir email a lista. |

### Atributos de contacto Brevo

Mapeo en `_split_name` y `_normalize_brevo_attributes`:

```
FIRSTNAME, LASTNAME, FULL_NAME (split del name)
SOURCE          (db_sync / app_signup)
ROLE
PLAN, CURRENT_PLAN
LAST_LOGIN_AT   (fecha YYYY-MM-DD para Brevo `date` type)
ACTIVE          (yes/no)
```

### `sync_users_to_brevo.py`

- CLI standalone (`if __name__ == '__main__'`).
- Llama `database.get_all_users()` y hace `bulk_upsert_contacts` en la lista `BREVO_TARGET_LIST_NAME`.
- **No es automático**: requiere ejecución manual.

### Sincronización en signup

En signup (`auth.py:891-907` y 1207+), upsert individual con `SOURCE=app_signup` en la misma lista.

---

## 5. Sistema de alertas del cron LLM (`cron_alerts.py`)

### Punto de entrada

```python
check_and_send_cron_alerts(run_id, get_db_connection_fn=None) -> Dict
```

- Llamado desde `database.release_analysis_lock` (l. 2710) **después** del COMMIT de release.
- Envuelto en try/except → fallo aquí no afecta al lock.
- Lee la fila `llm_monitoring_analysis_runs` por `run_id`.

### Los 3 chequeos en serie

| Chequeo | Función | Umbral |
|---|---|---|
| **Duración** | `_check_duration(run, threshold_min)` | `(completed_at - started_at)` minutos vs `CRON_ALERT_DURATION_MIN` (default `90`). Severity `high` si >1.5×, sino `medium`. |
| **Error rate** | `_check_error_rate(run, threshold)` | `failed_projects / total_projects` vs `CRON_ALERT_ERROR_RATE` (default `0.20`). Severity `high` si >2× umbral. |
| **Cost spike** | `_check_cost_spike(get_db_connection_fn, multiplier)` | Suma `cost_usd` de `llm_monitoring_results` de hoy vs **media móvil 7 días** (excluyendo hoy). Si avg=0, devuelve `None` (no hay baseline). |

### Resultado

- Si NO hay alertas → `{'alerts_triggered': 0, 'email_sent': False, 'reason': 'no_breach'}`.
- Si SÍ hay → **un solo email** con tabla HTML batched (rojo `#dc2626`, naranja `#f59e0b`, gris).

### Configuración

`_get_config`, leída en cada llamada (sin caché):

| Variable | Default | Para qué |
|---|---|---|
| `CRON_ALERTS_ENABLED` | `true` | Kill switch global. |
| `CRON_ALERTS_EMAIL` | `info@soycarlosgonzalez.com` | Destinatario. |
| `CRON_ALERT_DURATION_MIN` | `90` | Umbral duración. |
| `CRON_ALERT_ERROR_RATE` | `0.20` | Umbral error rate. |
| `CRON_ALERT_COST_MULTIPLIER` | `2.0` | Multiplicador cost spike. |
| `APP_ENV` o `RAILWAY_ENVIRONMENT_NAME` | — | Mostrar entorno en subject. |

### Subject

```
[{ENV}] LLM Cron alerts: duration, error_rate, cost_spike
```

(tipos sorted).

---

## 6. Alertas Stripe webhook

### `stripe_webhooks._alert_unmatched_customer` (líneas 209-300)

**Trigger**: cualquier evento webhook que llegue con `customer_id` que **NO** está en BD.

### Rate-limit

Tabla auto-creada `stripe_webhook_alerts_sent`:

```sql
CREATE TABLE IF NOT EXISTS stripe_webhook_alerts_sent (
    id          SERIAL PK,
    alert_key   VARCHAR(200),
    sent_at     TIMESTAMPTZ DEFAULT NOW()
);
```

Antes de enviar, comprueba si en la **última hora** ya hay una fila con `alert_key = 'unmatched_customer:<customer_id>'`. Si sí → no envía. Si no → INSERT y envía.

### Configuración

- **Kill switch**: `CRON_ALERTS_ENABLED=false` lo silencia.
- **Destinatario**: `CRON_ALERTS_EMAIL` (default `info@soycarlosgonzalez.com`).
- **Subject**: `[{ENV}] Stripe webhook customer_not_found`.

### Cuerpo

Tabla con `customer_id`, `subscription_id`, `action` (ej. `subscription.updated`). Avisa que Stripe reintenta 3 días.

---

## 7. Stuck Quota Alert

### Trigger

Tras `daily_quota_reset_cron`, el endpoint `/api/cron/quota-reset` invoca `_run_health_check_and_alert()`. También se puede disparar standalone vía `/api/cron/quota-health-check` (GET o POST).

### Detección (`_run_health_check_and_alert`)

```sql
SELECT id, email, plan, quota_reset_date::date, quota_used, quota_limit
FROM users
WHERE plan != 'free'
  AND billing_status IN ('active', 'trialing', 'beta')
  AND quota_reset_date IS NOT NULL
  AND quota_reset_date < NOW() - INTERVAL '1 day'
ORDER BY quota_reset_date
```

Cualquier fila → "stuck". Se envía email con tabla HTML por usuario (id, email, plan, reset_date, quota_used/quota_limit).

### Configuración

- **Kill switch**: `CRON_ALERTS_ENABLED=false`.
- **Destinatario**: `CRON_ALERTS_EMAIL`.
- **Subject**: `[{ENV}] Quota reset stuck — N user(s)`.

---

## 8. Email de aprobación de modelos LLM

### Endpoint principal

`POST /api/llm-monitoring/cron/model-discovery` (`llm_monitoring_routes.py:7983`, decorador `@cron_or_auth_required`). Lo dispara el Bun service `function-bun-Model-Discovery` semanalmente.

### Flujo

1. Escanea proveedores LLM, detecta modelos nuevos de tipo "chat".
2. Para cada modelo nuevo:
   - Genera `approval_token = secrets.token_urlsafe(64)`.
   - Expira en 7 días.
   - Lo guarda en `llm_model_registry.approval_token` + `approval_token_expires_at`.
   - Marca `pending_approval = TRUE`.
3. Construye email con **botones HTML clicables**:
   - **Approve**: `{PUBLIC_BASE_URL}/api/llm-monitoring/models/approve?token=<token>` (verde `#22c55e`).
   - **Reject**: `{PUBLIC_BASE_URL}/api/llm-monitoring/models/reject?token=<token>` (rojo `#ef4444`).
4. `notify_email = request.args.get('notify_email', 'info@soycarlosgonzalez.com')` — el Bun pasa `MODEL_DISCOVERY_EMAIL` como query param.
5. Envío vía `email_service.send_email`.

### Endpoints de respuesta

| Endpoint | Qué hace |
|---|---|
| `GET /api/llm-monitoring/models/approve?token=...` (l. 8404) | Valida token (longitud ≥20), comprueba expiry. Activa el modelo, ejecuta validación pre-switch, dispara email de confirmación a `MODEL_DISCOVERY_EMAIL`, renderiza HTML de éxito. |
| `GET /api/llm-monitoring/models/reject?token=...` (l. 8538) | Marca `pending_approval=FALSE`, `is_available=FALSE`. Sin email de confirmación. |

Helper `_render_approval_result(status, message)` (l. 8601) — pintura HTML del resultado.

### Tabla

`llm_model_registry` tiene los campos:

```
approval_token              VARCHAR(128)
approval_token_expires_at   TIMESTAMP
pending_approval            BOOLEAN
```

Migración: `migrate_llm_model_discovery_v2.py`. Índice parcial `idx_model_approval_token`.

### Legacy

`weekly_model_discovery_cron.py:312` — clase `LLMModelDiscovery.send_notification` usa `os.getenv('NOTIFICATION_EMAIL')`. Es un **camino paralelo** (usado por scripts internos antiguos), no por el flujo Bun.

---

## 9. Welcome y Password Reset

### Welcome (`auth.py:884` y `auth.py:1201`)

Tras crear usuario en BD (signup local o Google OAuth):

1. `send_welcome_email(email, name)` — try API Brevo → fallback SMTP.
2. En paralelo: `upsert_brevo_contact(email, name, list_id, attributes={SOURCE:'app_signup', PLAN, CURRENT_PLAN}, update_enabled=True)` — añade a la lista `Usuarios Registrados`. **No bloquea el flujo** si falla.

**Subject**: `Welcome to ClicandSEO`. Botón "Go to the App" → `https://app.clicandseo.com/`.

### Password Reset (`auth.py:640-685`)

1. POST con email → `get_user_by_email`. **Por seguridad**, responde igual aunque el email no exista.
2. `database.create_password_reset_token(user_id)`:
   - Genera `secrets.token_urlsafe(32)`.
   - Expira en **1 hora** (`expires_at = datetime.now() + timedelta(hours=1)`).
   - **Invalida tokens previos** no usados del mismo user.
3. `reset_url = f"{request.url_root}reset-password?token={token}"`.
4. Envío: `send_password_reset_via_api` (Brevo API) → fallback `send_password_reset_email` (SMTP).
5. Validación: `validate_password_reset_token(token)` y `use_password_reset_token(token, new_password)`.

**Subject**: `Reset Your ClicandSEO Password`. Aviso "expires in 1 hour".

---

## 10. Plantillas de email

> ⚠️ **Todas hardcoded en Python como f-strings.** **NO hay Jinja para emails.** **NO hay templates `.html` separadas para email.**

### Estructura común

- HTML inline con `<style>` en `<head>`.
- Versión texto plano (`text_body`) **solo en**: `send_email` (genérico), `send_welcome_email`, `send_password_reset_email`, `send_trial_started_email`, `_send_project_invitation_email`.
- El resto (alertas internas, model approval, stuck quota) van **solo en HTML**.

### Branding

- Color principal: `#D8F9B8` (verde lima, botones).
- Texto oscuro: `#161616`.
- Fondo: `#F3F2F1` o `#f9fafb`.
- Logo: `{PUBLIC_BASE_URL}/static/images/logos/logo-clicandseo-light.svg`.
- Footer estándar: *"This email was sent by ClicandSEO"*.

### Idiomas mezclados (deuda)

| Idioma | Tipo de email |
|---|---|
| **Inglés** (cara al usuario) | welcome, password reset, trial started, project invitation |
| **Español** (alertas internas a Carlos) | cron alerts, stuck quota, unmatched customer, model approval (subject mezcla emoji + español) |

`email_service.send_test_email` está en inglés.

---

## 11. Variables de entorno

| Variable | Default | Usado en |
|---|---|---|
| `SMTP_SERVER` | `smtp-relay.brevo.com` | `email_service.py` |
| `SMTP_PORT` | `587` | `email_service.py` |
| `USE_STARTTLS` | `true` | `email_service.py` |
| `SMTP_USERNAME` | `info@clicandseo.com` | `email_service.py` |
| `SMTP_PASSWORD` | (oblig.) | `email_service.py` |
| `FROM_EMAIL` | `info@clicandseo.com` | `email_service.py`, `brevo_api_service.py` |
| `FROM_NAME` | `ClicandSEO` | `email_service.py`, `brevo_api_service.py` |
| `PUBLIC_BASE_URL` | `https://app.clicandseo.com` | logo + URLs aprobación modelo |
| `BREVO_API_KEY` | (oblig. para API) | `brevo_api_service.py` |
| `BREVO_CONTACT_LIST_ID` | — | `brevo_api_service.get_or_create_list_id` |
| `BREVO_FOLDER_ID` | — | `brevo_api_service._get_default_folder_id` |
| `BREVO_TARGET_LIST_NAME` | `Usuarios Registrados` | `sync_users_to_brevo.py` |
| `CRON_ALERTS_ENABLED` | `true` | `cron_alerts.py`, `cron_routes.py`, `stripe_webhooks.py` |
| `CRON_ALERTS_EMAIL` | `info@soycarlosgonzalez.com` | `cron_alerts.py`, `cron_routes.py`, `stripe_webhooks.py` |
| `CRON_ALERT_EMAIL` | — | `llm_monitoring_routes._cron_alert` (**singular**, distinto de `CRON_ALERTS_EMAIL`) y Bun functions |
| `CRON_ALERT_DURATION_MIN` | `90` | `cron_alerts.py` |
| `CRON_ALERT_ERROR_RATE` | `0.20` | `cron_alerts.py` |
| `CRON_ALERT_COST_MULTIPLIER` | `2.0` | `cron_alerts.py` |
| `MODEL_DISCOVERY_EMAIL` | `info@soycarlosgonzalez.com` | `llm_monitoring_routes.py:8505`, Bun functions |
| `NOTIFICATION_EMAIL` | — | `weekly_model_discovery_cron.py:314` (legacy) |
| `APP_ENV` / `RAILWAY_ENVIRONMENT_NAME` | `unknown` | label de entorno en alertas |
| `CRON_TOKEN` | (oblig.) | auth Bearer en `cron_routes.py`, `_ensure_cron_token_or_admin` |
| `APP_URL` | `https://clicandseo.up.railway.app` | Bun functions: target del fetch |
| `PROJECT_INVITATION_BASE_URL` | — | `services/project_access_service._build_invitation_link` |

### ⚠️ Doble naming (deuda)

- `CRON_ALERT_EMAIL` (singular, sin S).
- `CRON_ALERTS_EMAIL` (plural).

**Conviven**. El sistema de alertas LLM `cron_alerts.py` usa el **plural**; el endpoint `/cron/alert` (genérico Bun-failed) usa el **singular** como primera opción.

`ALERT_EMAIL_TO`/`ALERT_EMAIL_FROM` mencionados en docs históricos **NO se encuentran usados** en el código (solo aparecen en docs).

---

## 12. Endpoints relacionados

| Método + ruta | Auth | Propósito |
|---|---|---|
| `POST /webhooks/stripe` | firma Stripe | Procesa eventos. Si customer no encontrado → `_alert_unmatched_customer`. |
| `POST /api/cron/quota-reset?async=1` | Bearer `CRON_TOKEN` | Reset cuota + health-check + email stuck quota si procede. |
| `POST/GET /api/cron/quota-health-check` | Bearer `CRON_TOKEN` | Health-check standalone. |
| `POST /api/llm-monitoring/cron/daily-analysis?async=1` | Bearer `CRON_TOKEN` | Cron LLM (al terminar dispara `cron_alerts`). |
| `POST /api/llm-monitoring/cron/model-discovery` | `cron_or_auth_required` | Discovery semanal + email aprobación. |
| `GET /api/llm-monitoring/models/approve?token=...` | público (token-based) | Aprueba modelo + email confirmación. |
| `GET /api/llm-monitoring/models/reject?token=...` | público (token-based) | Rechaza modelo. |
| `POST /api/llm-monitoring/cron/alert` | `cron_or_auth_required` | Recibe alerta de un Bun service y manda email. |
| `POST /forgot-password` | público | Genera token + email password reset. |
| `GET /reset-password?token=...` | público | Página HTML para introducir nueva pwd. |

---

## 13. Operaciones manuales

### Email de prueba SMTP

```bash
python /Users/carlosgonzalez/Desktop/app/APP-WEB-GSC-AI/search_console_webapp/email_service.py
# pide email por stdin → manda send_test_email
```

### Silenciar alertas globalmente

```bash
# En Railway env vars:
CRON_ALERTS_ENABLED=false
```

### Forzar health-check de cuotas

```bash
curl -X POST "$APP_URL/api/cron/quota-health-check" \
  -H "Authorization: Bearer $CRON_TOKEN"
```

### Sincronizar usuarios a Brevo

```bash
python /Users/carlosgonzalez/Desktop/app/APP-WEB-GSC-AI/search_console_webapp/sync_users_to_brevo.py
```

### Test de cron alerts en staging

```bash
DATABASE_URL=<staging> CRON_ALERTS_EMAIL=... \
  python test_cron_alerts.py [--send-real-email]
```

---

## 14. Errores históricos y deuda técnica

### Bugs históricos resueltos

| Bug | Fix |
|---|---|
| **SMTP timeouts intermitentes en Railway** | Timeout fijo 30s + fallback API Brevo first. |
| **`trial_started_email_sent_at`** sin idempotencia | `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` cada vez que se procesa un trialing event (l. 575 `stripe_webhooks.py`). Idempotencia: solo se manda una vez por user. |

### Deuda técnica

| Deuda | Impacto | Riesgo |
|---|---|---|
| **Doble naming `CRON_ALERT_EMAIL` vs `CRON_ALERTS_EMAIL`** | Quien configure solo uno corre riesgo de no recibir según qué tipo de alerta. | Medio. |
| **Dos sistemas de discovery email**: Bun moderno (`/cron/model-discovery` con tokens) vs legacy `weekly_model_discovery_cron.LLMModelDiscovery.send_notification` (lee `NOTIFICATION_EMAIL`) | Pueden quedar desincronizados. | Medio. |
| **Idiomas mezclados**: emails de usuario en inglés, alertas internas en español | Sin política unificada. | Bajo (UX). |
| **Sin reintentos** en `email_service.send_email` | Si Brevo falla, simplemente loguea y devuelve `False`. No hay cola persistente, no hay backoff. | Medio. |
| **Plantillas inline** en Python | Cualquier cambio de branding requiere editar HTML en N archivos. | Medio. |
| **`email_preview.html`** en disco pero no se sirve | Confusión. | Trivial. |
| **Logger en español** en muchos sitios | Puede confundir si Railway parsea logs. | Bajo. |
| **`ALERT_EMAIL_TO`/`ALERT_EMAIL_FROM`** mencionados en docs antiguas pero no existen | Confusión. | Trivial. |

### Sin reintentos

`email_service.send_email`: **no hay reintentos**, cola persistente ni backoff. Si Brevo falla, loguea y devuelve `False`. Aceptable porque las alertas se vuelven a disparar al día siguiente; los emails de usuario son los que más sufren (welcome, password reset). Mejora futura: cola Redis con retry.

---

## 15. Tests

### Tests específicos

| Archivo | Cubre |
|---|---|
| `test_cron_alerts.py` | Inserta run sintético en `llm_monitoring_analysis_runs` (150 min, 30% fail), monkey-patch de `email_service.send_email`, asserts sobre `alerts_triggered`, tipos de alerta y destinatario. Flag `--send-real-email` para test e2e. |
| `test_cron_routes.py` | Test del `_run_health_check_and_alert` con stuck users mock + `send_email` mock. |

### Lo que NO está cubierto

> ⚠️ **No hay** tests unitarios para:
> - `email_service.send_email` (SMTP).
> - `brevo_api_service` (API/contactos).
> - Endpoints `/models/approve` o `/models/reject`.
> - `_alert_unmatched_customer`.
> - Password reset.
> - Welcome.

---

## TL;DR

1. **Brevo único proveedor**, dos vías: SMTP (`email_service.py`) + API REST (`brevo_api_service.py`).
2. **Welcome/password reset usan API primero, SMTP como fallback**. Alertas internas siempre SMTP.
3. **Todos los emails son f-strings hardcoded en Python**. No hay templates Jinja para emails.
4. **3 sistemas de alertas**:
   - Cron LLM (`cron_alerts.py`): duración / error rate / cost spike. Single batched email post-run.
   - Stripe webhook unmatched customer (`_alert_unmatched_customer`): rate-limit con `stripe_webhook_alerts_sent` (1/h).
   - Stuck quota (`_send_stuck_quota_alert`): post quota-reset cron, detecta usuarios con `quota_reset_date < ayer`.
5. **Model approval** vía email con tokens (`secrets.token_urlsafe(64)`, expiran 7 días). Botones HTML clicables que llaman a `/models/approve` o `/models/reject`.
6. **Kill switch global**: `CRON_ALERTS_ENABLED=false`.
7. **Doble naming `CRON_ALERT_EMAIL` (singular) vs `CRON_ALERTS_EMAIL` (plural)** = deuda. Configurar **ambas** para evitar gaps.
8. **Idiomas mezclados**: usuario en inglés, alertas internas en español.
9. **Sin reintentos en SMTP** (timeout 30s) y sin cola persistente.
10. **Cobertura tests baja**: solo `cron_alerts` y `quota-health-check` mockeados. Welcome, password reset, Brevo API y Stripe alerts sin cobertura.

— Fin del manual —
