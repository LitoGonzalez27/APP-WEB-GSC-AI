# CLAUDE.md — Manual de funcionamiento del sistema (ClicandSEO)

> Este documento describe cómo funciona toda la maquinaria de **Stripe, cuotas, usuarios, crons y código** del sistema. Está pensado para que:
> 1. **Carlos** (no técnico) pueda entender qué hace cada pieza y por qué.
> 2. **Una futura sesión de Claude** entre fría al proyecto y sepa orientarse sin tener que reconstruir el contexto.
>
> Última actualización: 2026-06-21 (fixes de junio: nombres de evento Stripe, cancelación que desactiva los 3 sistemas, alertas en reset fallido, `paused_until` / auto-reanudación).

---

## Índice

1. [Visión general en 5 minutos](#1-visión-general-en-5-minutos)
2. [Planes y precios](#2-planes-y-precios)
3. [Ciclo de vida de un usuario](#3-ciclo-de-vida-de-un-usuario)
4. [Stripe: webhooks y eventos](#4-stripe-webhooks-y-eventos)
5. [Sistema de cuotas](#5-sistema-de-cuotas)
6. [Arquitectura de crons (Bun + HTTP endpoints)](#6-arquitectura-de-crons)
7. [Defensa en profundidad: 3 capas](#7-defensa-en-profundidad-3-capas)
8. [Mapa de archivos](#8-mapa-de-archivos)
9. [Variables de entorno](#9-variables-de-entorno)
10. [Esquema de base de datos relevante](#10-esquema-de-base-de-datos-relevante)
11. [Operaciones manuales y troubleshooting](#11-operaciones-manuales-y-troubleshooting)
12. [Historia de incidencias y fixes (mayo–junio 2026)](#12-historia-de-incidencias-y-fixes-mayojunio-2026)

---

## 1. Visión general en 5 minutos

ClicandSEO es un **SaaS** con dos productos principales que consumen cuota:

- **LLM Monitoring** — analiza diariamente cómo aparece la marca del cliente en respuestas de modelos LLM (GPT, Claude, Gemini, Perplexity).
- **Manual AI Analysis** — análisis on-demand de visibilidad y SERPs.

El usuario paga una **suscripción mensual en Stripe**. La suscripción le otorga una **cuota mensual** (ej: 10.000 análisis). Cada análisis (LLM o Manual AI) consume cuota. Cuando llega a 0, los proyectos del usuario se **pausan automáticamente**. Cuando Stripe le cobra el siguiente mes, la cuota se **resetea** y los proyectos se **reactivan**.

Los análisis diarios los ejecuta un **cron en Railway** (servicios "Bun function") que llama por HTTP a la app Flask. El reset de cuota lo hace **otro cron similar** que también llama por HTTP a la app.

**Reglas de oro del sistema:**

1. La fecha de cobro y de reset NO es el día 1 de cada mes. Es **el aniversario mensual de cuando el usuario se suscribió** (anclado a Stripe).
2. La fuente canónica del periodo de facturación es **Stripe**. La base de datos solo cachea esa información (`current_period_start`, `current_period_end`).
3. Hay **3 capas de defensa** para que la cuota se resetee a tiempo: webhook → cron Stripe-aware → alerta por email si algo se queda colgado.
4. Todos los crons son **idempotentes** y tienen **timeout por proyecto** para que un proyecto roto no bloquee al resto.

---

## 2. Planes y precios

| Plan       | Precio (€/mes) | Cuota mensual    | Notas |
|------------|----------------|------------------|-------|
| Free       | 0              | Limitada (test)  | Modelos LLM gratuitos solamente |
| Basic      | 29,99          | Estándar         | |
| Premium    | 79,99 (49,99 grandfathered) | Estándar mayor   | |
| Business   | 229,99 (139,99 grandfathered) | Estándar grande  | |
| Enterprise | Custom (B2B)   | `custom_quota_limit` | Sin Stripe; gestión manual |

- Los precios y cuotas concretas viven en `stripe_config.py` (`PLAN_FEATURES`) y en la columna `users.quota_limit`.
- Para **Enterprise** (ej: la agencia NeoAttack si firma 20 proyectos), se usa `users.custom_quota_limit`. La aplicación toma `custom_quota_limit` con prioridad cuando existe.
- Los modelos LLM disponibles para **Free** están restringidos a versiones gratuitas: `gpt-5.3-chat-latest`, `claude-sonnet-4-6`, `gemini-3-flash-preview`, `sonar`. Esto evita coste para usuarios que no pagan.

---

## 3. Ciclo de vida de un usuario

```
┌─────────────────────────────────────────────────────────────────────┐
│  1. Registro                                                        │
│     → users.plan = 'free', billing_status = 'active', quota_used=0 │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  2. Compra suscripción                                              │
│     a) checkout.session.completed → solo graba stripe_customer_id   │
│        y subscription_id (NO fija plan ni quota_limit).             │
│     b) customer.subscription.created/updated → fija plan,           │
│        quota_limit, current_period_start/end, billing_status,       │
│        quota_reset_date.                                            │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  3. Uso normal (consume cuota)                                      │
│     Cada análisis LLM o Manual AI → quota_used += 1                 │
│     Si quota_used >= quota_limit → is_paused_by_quota = TRUE        │
│       (los proyectos se pausan, no se ejecutan los crons)           │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  4. Renovación mensual (Stripe)                                     │
│     a) Stripe cobra automáticamente en la fecha aniversario.        │
│     b) Webhook invoice.payment_succeeded:                           │
│        → quota_used = 0                                             │
│        → quota_reset_date = nuevo current_period_end                │
│        → resume_quota_pauses_for_user (despausar proyectos)         │
│     c) Si por algún motivo el webhook no actualiza, el cron diario  │
│        de quota-reset es la red de seguridad.                       │
│     d) Si tras el cron sigue habiendo usuarios atascados, se envía  │
│        un email de alerta a Carlos.                                 │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  5. Cancelación / impago                                            │
│     - cancellation requested → cancel_at_period_end = TRUE          │
│     - impago → billing_status = 'past_due'                          │
│     - cancelado de verdad (customer.subscription.deleted):          │
│         → plan = 'free', sub_id = NULL, quota_limit = 0             │
│         → is_active = false en los 3 sistemas (manual_ai_projects,  │
│           ai_mode_projects, llm_monitoring_projects)               │
└─────────────────────────────────────────────────────────────────────┘
```

**Punto crítico**: la fecha de renovación **no es** el día 1 ni el último día del mes. Es el **aniversario mensual** del momento exacto en que el usuario se suscribió. Stripe lo gestiona y nosotros lo cacheamos en `current_period_start` / `current_period_end`.

---

## 4. Stripe: webhooks y eventos

**Endpoint**: `POST /webhooks/stripe`
**Archivo**: `stripe_webhooks.py`
**Idempotencia**: tabla `stripe_webhook_events` (`INSERT … ON CONFLICT DO NOTHING RETURNING`). Si el mismo `event_id` llega dos veces, el segundo se ignora.

### Eventos manejados (6)

| Evento Stripe                        | Qué hace en BD |
|--------------------------------------|----------------|
| `checkout.session.completed`         | Solo graba `stripe_customer_id` y `subscription_id`. **No** fija plan ni `quota_limit` (eso lo hacen los eventos `created/updated`). |
| `customer.subscription.created`      | Fija `plan`, `quota_limit`, cachea `current_period_start/end`, `billing_status`, `subscription_id`, `quota_reset_date`. |
| `customer.subscription.updated`      | Sincroniza cambios de plan, periodo o estado (active/past_due/canceled). |
| `customer.subscription.deleted`      | Devuelve al usuario al plan `free`, `quota_limit = 0`, limpia `subscription_id` y periodo. Además pone `is_active = false` en los **3 sistemas** (`manual_ai_projects`, `ai_mode_projects`, `llm_monitoring_projects`) para que sus crons dejen de correr. |
| `invoice.payment_succeeded`          | **Resetea cuota**: `quota_used = 0`, actualiza `quota_reset_date`, llama a `resume_quota_pauses_for_user` para despausar proyectos. Si el `UPDATE … RETURNING` no toca filas (`stripe_customer_id` sin usuario) o el período es irresoluble, loguea un **🚨** y la cuota NO se resetea (ver abajo). |
| `invoice.payment_failed`             | Marca `billing_status = 'past_due'`. Stripe sigue reintentando. |

### Códigos de respuesta (importante)

- **200** — evento procesado correctamente o ya procesado anteriormente (idempotente).
- **503** — usuario no encontrado (`customer_not_found`). Devolver 503 hace que Stripe **reintente durante 3 días**, dándonos tiempo a corregir.
- **500** — excepción inesperada. Antes era un 200 silencioso; ahora se loguea y Stripe reintenta.

### Extracción robusta del periodo de facturación

Stripe ha movido los campos `period_start` / `period_end` dentro del objeto `invoice`. El código intenta múltiples rutas:

1. `invoice.period_start` / `invoice.period_end` (raíz, antiguo).
2. `invoice.lines.data[0].period.start/end` (nuevo, donde Stripe lo pone ahora).
3. **Fallback**: `stripe.Subscription.retrieve(subscription_id)` por API si nada de lo anterior está disponible.

Esto es lo que arregló el bug de los 7 usuarios atascados con `current_period_end = NULL`.

### Alerta de "customer no encontrado"

`_alert_unmatched_customer` envía un email a Carlos cuando un webhook llega para un `customer_id` que no está en BD. Hay rate-limit (tabla auxiliar) para no spamear.

### Alertas 🚨 en `invoice.payment_succeeded` (reset fallido)

`_handle_payment_succeeded` loguea un `logger.error` con prefijo **🚨** en dos casos en los que el cliente pagó pero la cuota NO se reseteó:

1. **Sin usuario**: el `UPDATE … RETURNING id` no tocó filas → no hay usuario con ese `stripe_customer_id`. Mensaje: *"cuota NO reseteada. Revisar reconciliación de cliente."*
2. **Sin período resoluble**: no se pudo obtener el período por ninguna vía (top-level, `lines.data`, ni la API live de Stripe). Se devuelve `success` para no forzar reintentos infinitos, pero se alerta: *"sin período resoluble, cuota NO reseteada. Revisar manualmente."*

Ambos quedan en logs como **🚨** para detectar clientes que pagaron pero podrían quedarse sin servicio.

---

## 5. Sistema de cuotas

### Conceptos

- **`quota_used`** — análisis consumidos en el ciclo actual (entero).
- **`quota_limit`** — tope del plan estándar.
- **`custom_quota_limit`** — tope personalizado para Enterprise (si existe, manda).
- **`quota_reset_date`** — fecha en la que se resetea (TIMESTAMPTZ). Se actualiza en cada renovación.
- **`is_paused_by_quota`** — booleano por proyecto. `TRUE` = el proyecto no se ejecuta hasta que la cuota se resetee.
- **`paused_until`** — fecha (por proyecto) hasta la que dura la pausa por cuota. Se fija al valor de `quota_reset_date` (la fecha de reset global del usuario), con fallback `NOW() + 30 días` si no hay `reset_date`.
- **Eventos**: la tabla `quota_events` registra cada incremento para auditoría.

### Auto-reanudación por `paused_until` (fixes junio 2026)

Cuando un proyecto se pausa por cuota, se le graba `paused_until`. Los crons de los **3 sistemas** (Manual AI, AI Mode, LLM Monitoring) incluyen en su filtro de elegibilidad la condición:

```
OR (p.paused_until IS NOT NULL AND p.paused_until <= NOW())
```

Es decir, un proyecto pausado vuelve a ser elegible **en cuanto `paused_until` queda en el pasado**, sin depender de que el webhook/cron de reset lo despause explícitamente. Esto es el modelo de los fixes de junio (commits `5cb1586`, `3504c78`, `d1923d5`): el LLM nunca queda colgado con `paused_until = NULL` y los 3 sistemas auto-reanudan de forma consistente.

### Cuándo se incrementa

Cada análisis LLM o Manual AI llama a `quota_manager.increment_quota()`, que:
1. Suma 1 a `quota_used`.
2. Inserta una fila en `quota_events`.
3. Si `quota_used >= effective_limit`, marca `is_paused_by_quota = TRUE` en los proyectos del usuario y devuelve "out of quota".

### Cuándo se resetea

Hay **dos rutas** que pueden resetear:

1. **Vía Stripe** (camino principal): el webhook `invoice.payment_succeeded` resetea inmediatamente cuando Stripe cobra.
2. **Vía cron diario** (red de seguridad): `daily_quota_reset_cron.py` corre cada día y resetea a usuarios cuyo `quota_reset_date <= NOW()`, **excluyendo** a los que tienen Stripe activo con `current_period_end > NOW()` (porque ahí manda el webhook).

### Cálculo de la próxima fecha de reset

Función `compute_next_quota_reset_date` en `quota_manager.py`. Lógica:

1. Si tenemos `period_end` de Stripe y está en el futuro → ese es el siguiente reset.
2. Si no, partimos del último reset y sumamos `interval_days` (típicamente 30).
3. **Safety net**: si por error el resultado queda en el pasado, se fuerza `now + interval_days` para garantizar siempre fecha futura.

### Despausar proyectos

`database.resume_quota_pauses_for_user(user_id)` despausa los **tres** sistemas y limpia el estado de pausa en `users`:
- `ai_mode_projects`, `llm_monitoring_projects` y `manual_ai_projects`: pone `is_paused_by_quota = FALSE` y limpia `paused_until / paused_at / paused_reason` a NULL.
- En `users`: resetea `ai_overview_paused_until / ai_overview_paused_at / ai_overview_paused_reason` a NULL.

`manual_ai_projects` va dentro de un **SAVEPOINT** (es la tabla menos universal): si esa tabla falla, solo se deshace ese paso y los demás módulos quedan despausados. Importante: se llama **después** del COMMIT del reset de cuota, en una conexión separada, para evitar self-deadlock por row-lock.

---

## 6. Arquitectura de crons

### Por qué Bun functions y no Python crons

Railway tiene en `railway.json` un array `crons` para schedules de la propia app, **pero en este proyecto no se ejecutan**. Por eso los crons reales corren como **servicios independientes "Bun function"** en Railway, que:

1. Disparan en su `cron schedule` propio.
2. Hacen una llamada HTTP autenticada a la app Flask.
3. La app es quien hace el trabajo real.

Esto separa "schedule" de "lógica" y permite reiniciar uno sin tocar el otro.

### Servicios cron en producción (Railway)

| Servicio Bun                   | Schedule       | Endpoint que llama                  | Qué hace |
|--------------------------------|----------------|-------------------------------------|----------|
| `function-bun-LLM-Monitoring`  | Diario         | `/api/cron/llm-monitoring/run`      | Ejecuta análisis LLM diario para todos los proyectos activos |
| `function-bun-Manual-AI`       | Diario         | (manual AI cron endpoint)           | Análisis Manual AI |
| `function-bun-AI-Mode`         | Diario         | (AI Mode cron endpoint)             | Análisis AI Mode |
| `function-bun-Quota-reset`     | Diario         | `/api/cron/quota-reset?async=1`     | Resetea cuota de usuarios elegibles + health-check post-reset |
| `function-bun-Model-Discovery` | Semanal        | (LLM model discovery)               | Descubre nuevos modelos LLM disponibles |

> Nomenclatura: hay convenciones mixtas en mayúsculas (`function-bun-Quota-reset` vs `function-bun-quota-reset`). Mantener una sola para evitar duplicados accidentales.

### Autenticación de crons

Todos los endpoints `/api/cron/*` requieren cabecera:

```
Authorization: Bearer <CRON_TOKEN>
```

`CRON_TOKEN` es una variable de entorno compartida entre la app Flask y los servicios Bun.

### Modos sync / async

Los endpoints aceptan `?async=1`. En modo async devuelven **HTTP 202** inmediato y arrancan un thread en background. En modo sync devuelven **HTTP 200** con el resumen al terminar.

Para crons largos (LLM Monitoring puede tardar 15-20 min) se usa async para que el servicio Bun no espere.

### Health-check posterior

Tras el reset de cuotas, `/api/cron/quota-reset` también ejecuta un **health-check** que detecta usuarios "atascados" (con `quota_reset_date` en el pasado pero todavía pausados, etc.). Si encuentra alguno, envía un email de alerta a Carlos.

### Alertas de cron (Manual AI / AI Mode) — NUEVO 2026-06-10

- `cron_alerts.send_simple_run_completion_email(module_label, stats)`: email de resumen
  (✅ OK / ⚠️ WARNING / 🚨 CRITICAL) al terminar cada run de Manual AI y AI Mode. Lo llaman
  los `CronService` de ambos módulos en éxito, "0 proyectos" y excepción global (nunca en
  skip por advisory lock). Mismo kill-switch `CRON_ALERTS_ENABLED`.
- `cron_routes._run_module_staleness_check()`: corre a diario tras el quota-reset. Alerta
  por email si Manual AI o AI Mode llevan > `CRON_STALENESS_MAX_DAYS` (default 4) sin
  producir resultados teniendo proyectos elegibles de frecuencia estándar (ignora los de
  `analysis_frequency_days > 1`, cuyos huecos son intencionados).
- Backfill en quota-reset (2026-06-10): cuando el live-check Stripe encuentra periodo
  activo para un usuario con `current_period_end` NULL, ahora cachea ese period_end y
  alinea `quota_reset_date` — antes el usuario quedaba marcado "stuck" por el health-check
  cada día indefinidamente.

### Alertas de cron (LLM Monitoring)

`cron_alerts.py` envía un email único cuando un run detecta:

- **Duración** > `CRON_ALERT_DURATION_MIN` (default 90 min).
- **Tasa de errores** > `CRON_ALERT_ERROR_RATE` (default 0.20 = 20%).
- **Coste** > `CRON_ALERT_COST_MULTIPLIER` × media de los últimos 7 días (default 2x).

`CRON_ALERTS_ENABLED=true` activa el sistema; `false` lo silencia.

### Paralelismo y timeout por proyecto

- `LLM_PROJECT_PARALLELISM` (default 2; en producción se ha subido a 3) — número de proyectos analizados a la vez.
- `LLM_PROJECT_TIMEOUT_MINUTES` (default 30) — un proyecto que tarde más se cancela y devuelve `{ success: False, timed_out: True }`. El resto sigue.
- `project_timeout.py` envuelve cada análisis con `daemon thread + join(timeout)`.

---

## 7. Defensa en profundidad: 3 capas

```
        STRIPE COBRA
              │
              ▼
   ┌──────────────────────────────────────────────────────┐
   │  CAPA 1: Webhook invoice.payment_succeeded           │
   │  ─ Resetea quota_used = 0                            │
   │  ─ Actualiza quota_reset_date                        │
   │  ─ Despausa proyectos                                │
   └──────────────────────────────────────────────────────┘
              │
              ▼ (si el webhook falla / llega tarde / period_end nulo)
   ┌──────────────────────────────────────────────────────┐
   │  CAPA 2: Cron diario quota-reset (Stripe-aware)      │
   │  ─ Excluye usuarios con periodo Stripe activo        │
   │  ─ Live-check vs Stripe API si period_end IS NULL    │
   │  ─ Resetea solo a quien le toca                      │
   └──────────────────────────────────────────────────────┘
              │
              ▼ (si tras el cron alguien sigue mal)
   ┌──────────────────────────────────────────────────────┐
   │  CAPA 3: Health-check post-cron + alerta email       │
   │  ─ Detecta usuarios atascados                        │
   │  ─ Envía email a Carlos vía Brevo SMTP               │
   └──────────────────────────────────────────────────────┘
```

Esto es lo que evita que vuelva a pasar lo de Driza UEMC (53 días sin servicio porque webhook no actualizó `current_period_end`).

---

## 8. Mapa de archivos

### Núcleo de billing y cuotas

| Archivo                          | Qué contiene |
|----------------------------------|--------------|
| `stripe_webhooks.py`             | Handler del endpoint `/webhooks/stripe`, los 6 eventos, idempotencia, alertas. |
| `stripe_config.py`               | `PLAN_FEATURES` (precios, cuotas, features por plan), constantes de Stripe. |
| `quota_manager.py`               | `increment_quota`, `compute_next_quota_reset_date`, `check_quota_available`. |
| `quota_middleware.py`            | Decoradores que se aplican a las rutas que consumen cuota. |
| `billing_routes.py`              | Rutas Flask para que el usuario gestione su suscripción (portal, upgrade…). |
| `admin_billing_routes.py`        | Rutas admin (Carlos) para ajustar planes, dar cuota custom, etc. |
| `admin_billing_panel.py`         | Vistas y backend del panel admin. |

### Crons (Python)

| Archivo                          | Qué contiene |
|----------------------------------|--------------|
| `daily_llm_monitoring_cron.py`   | Lógica del cron de LLM Monitoring (lo llama el endpoint HTTP). |
| `daily_ai_mode_cron.py`          | Cron de AI Mode. |
| `daily_analysis_cron.py`         | Cron Manual AI Analysis. |
| `daily_quota_reset_cron.py`      | Cron de reset de cuota Stripe-aware. |
| `weekly_model_discovery_cron.py` | Descubrimiento semanal de modelos LLM. |
| `cron_routes.py`                 | Blueprint Flask con `/api/cron/*` endpoints, auth Bearer, modos sync/async, health-check. |
| `cron_alerts.py`                 | Sistema de alertas (duración / errores / coste) por email. |
| `project_timeout.py`             | Wrapper `run_project_with_timeout` con daemon thread + join. |

### Crons (Bun functions JS)

| Archivo                                  | Qué contiene |
|------------------------------------------|--------------|
| `llm_monitoring_cron_function.js`        | Handler del servicio Bun que dispara LLM Monitoring por HTTP. |
| `ai_mode_cron_function.js`               | Handler Bun para AI Mode. |
| `quota_reset_cron_function.js`           | Handler Bun para quota-reset. |
| `llm_model_discovery_cron_function.js`   | Handler Bun para descubrimiento semanal. |

### Infraestructura

| Archivo                          | Qué contiene |
|----------------------------------|--------------|
| `app.py`                         | Punto de entrada Flask. Registra todos los blueprints (incluido `cron_routes`). |
| `database.py`                    | Pool de conexiones (`_PooledConnection` wrapper), `get_db_connection`, helpers (`resume_quota_pauses_for_user`, `release_analysis_lock`). |
| `auth.py`                        | OAuth Google, sesiones de usuario. |
| `services/llm_monitoring_service.py` | Lógica de análisis LLM (eligibility filter + parallel analysis). |
| `services/email_service.py`      | Envío de email vía Brevo SMTP. |

### Tests y diagnóstico

| Archivo                          | Qué contiene |
|----------------------------------|--------------|
| `test_cron_alerts.py`            | Tests de las alertas. |
| `test_cron_routes.py`            | Tests de los endpoints `/api/cron/*`. |
| `test_stripe_aware_reset.py`     | Tests del filtro Stripe-aware en el cron. |
| `test_webhook_hardening.py`      | Tests de idempotencia y extracción robusta del periodo. |
| `test_llm_cron_jobs.py`          | Tests del cron LLM completo. |
| `webhook_diagnostics.py`         | Script para inspeccionar webhooks recibidos. |
| `diagnose_cron_skip.py`          | Script para investigar por qué un cron saltó algún proyecto. |

---

## 9. Variables de entorno

### Stripe

| Variable                  | Para qué sirve |
|---------------------------|----------------|
| `STRIPE_SECRET_KEY`       | Llave secreta de Stripe (servidor). Necesaria para `Subscription.retrieve` (fallback API). |
| `STRIPE_WEBHOOK_SECRET`   | Verificación de firma de webhooks. |
| `STRIPE_PRICE_BASIC`      | ID del price del plan Basic. |
| `STRIPE_PRICE_PREMIUM`    | ID del price del plan Premium. |
| `STRIPE_PRICE_BUSINESS`   | ID del price del plan Business. |

### Crons

| Variable                       | Default | Para qué sirve |
|--------------------------------|---------|----------------|
| `CRON_TOKEN`                   | (oblig.)| Bearer token compartido entre Bun services y Flask. |
| `APP_URL`                      | (oblig.)| URL pública de la app, la usan los Bun functions. |
| `CRON_ALERTS_ENABLED`          | `true`  | Kill-switch global de alertas de cron. |
| `CRON_ALERT_DURATION_MIN`      | `90`    | Duración (min) que dispara alerta. |
| `CRON_ALERT_ERROR_RATE`        | `0.20`  | Tasa de errores que dispara alerta. |
| `CRON_ALERT_COST_MULTIPLIER`   | `2.0`   | Múltiplo del coste medio (7d) que dispara alerta. |
| `LLM_PROJECT_PARALLELISM`      | `2`     | Proyectos LLM analizados en paralelo (en prod = 3). |
| `LLM_PROJECT_TIMEOUT_MINUTES`  | `30`    | Timeout por proyecto LLM. |

### Base de datos

| Variable               | Para qué sirve |
|------------------------|----------------|
| `DATABASE_URL`         | URL completa de Postgres. |
| `DB_POOL_MIN`          | Conexiones mínimas en el pool (default 1). |
| `DB_POOL_MAX`          | Conexiones máximas (default 8). |
| `DB_POOL_WAIT_SECONDS` | Tiempo de espera ante pool agotado (default 10). |

### Email (alertas)

| Variable               | Para qué sirve |
|------------------------|----------------|
| `BREVO_SMTP_HOST`      | smtp-relay.brevo.com |
| `BREVO_SMTP_PORT`      | 587 |
| `BREVO_SMTP_USER`      | Usuario SMTP |
| `BREVO_SMTP_PASSWORD`  | Password SMTP |
| `ALERT_EMAIL_TO`       | Destinatario de alertas (Carlos). |
| `ALERT_EMAIL_FROM`     | Remitente. |

---

## 10. Esquema de base de datos relevante

### `users` (campos de billing/cuota)

```
id                    BIGSERIAL PK
email                 TEXT
plan                  TEXT          -- 'free' | 'basic' | 'premium' | 'business' | 'enterprise'
billing_status        TEXT          -- 'active' | 'trialing' | 'past_due' | 'canceled' | 'beta'
stripe_customer_id    TEXT          -- Stripe customer
subscription_id       TEXT          -- Stripe subscription
current_period_start  TIMESTAMPTZ   -- inicio del ciclo Stripe actual
current_period_end    TIMESTAMPTZ   -- fin del ciclo Stripe actual (= próxima cobranza)
quota_used            INTEGER       -- consumo del ciclo actual
quota_limit           INTEGER       -- tope del plan
custom_quota_limit    INTEGER NULL  -- tope custom (Enterprise); manda si no es NULL
quota_reset_date      TIMESTAMPTZ   -- cuándo se reseteará
cancel_at_period_end  BOOLEAN
updated_at            TIMESTAMPTZ
```

### `stripe_webhook_events` (idempotencia)

```
event_id     TEXT PK       -- ID del evento Stripe
event_type   TEXT
received_at  TIMESTAMPTZ DEFAULT NOW()
```

### `quota_events` (auditoría)

```
id          BIGSERIAL PK
user_id     BIGINT FK users
delta       INTEGER       -- normalmente +1
source      TEXT          -- 'llm_monitoring' | 'manual_ai' | …
created_at  TIMESTAMPTZ
```

### `manual_ai_projects` y `llm_monitoring_projects`

Ambas tienen:

```
is_paused_by_quota  BOOLEAN DEFAULT FALSE
```

Cuando `quota_used >= effective_limit`, ese campo se pone a TRUE. El cron diario respeta el flag y no analiza esos proyectos. Cuando se resetea cuota, se vuelve a FALSE.

### `cron_runs` (registro de ejecuciones)

Tabla de auditoría de cada ejecución de cron (run_id, start, end, ok/fail counts, cost). La usa `cron_alerts.py` para calcular media de coste de los últimos 7 días.

---

## 11. Operaciones manuales y troubleshooting

### Disparar manualmente un cron

**Reset de cuotas:**
```bash
curl -X POST "$APP_URL/api/cron/quota-reset?async=0" \
  -H "Authorization: Bearer $CRON_TOKEN"
```

**LLM Monitoring (síncrono, devuelve resumen):**
```bash
curl -X POST "$APP_URL/api/cron/llm-monitoring/run?async=0" \
  -H "Authorization: Bearer $CRON_TOKEN"
```

**Health-check de cuotas:**
```bash
curl -X POST "$APP_URL/api/cron/quota-health-check" \
  -H "Authorization: Bearer $CRON_TOKEN"
```

### "Un cliente dice que su proyecto no se actualiza"

Pasos:

1. Buscar el proyecto en BD por el dominio o user_id.
2. Comprobar `is_paused_by_quota` — si TRUE, mirar la cuota del usuario.
3. Comprobar `users.quota_used` vs `users.quota_limit` (o `custom_quota_limit`).
4. Comprobar `users.current_period_end` y `users.quota_reset_date`. Si están en el pasado, hubo un fallo de reset.
5. Mirar últimos eventos en `stripe_webhook_events` para ese `stripe_customer_id`.
6. Si todo está bien y simplemente le toca: lanzar el cron de LLM Monitoring manualmente.

### "Stripe ha cobrado pero la cuota no se ha reseteado"

1. Buscar el evento `invoice.payment_succeeded` en Stripe Dashboard → Webhooks.
2. ¿Llegó? ¿Devolvimos 200 / 503 / 500?
3. Si 503 (`customer_not_found`): hay desincronización; buscar al usuario por email y arreglar `stripe_customer_id`.
4. Si 500: revisar logs de la app, mirar excepción.
5. Como red de seguridad, lanzar `quota-reset` manualmente (paso anterior).

### "El cron LLM tarda demasiado"

1. Mirar logs del último run en Railway / `cron_runs`.
2. Si es un proyecto concreto el que dispara timeout: revisar logs de ese proyecto.
3. Subir temporalmente `LLM_PROJECT_PARALLELISM` (ojo al coste).
4. Si hay un proveedor LLM con rate-limit, bajar parallelism o el `max_workers` del semáforo.

### "Webhook recibido para customer_id desconocido"

Llega email de `_alert_unmatched_customer`. Pasos:

1. Abrir Stripe Dashboard → buscar el customer.
2. Cruzar email con la BD.
3. Si es un usuario que existe, asignarle el `stripe_customer_id` manualmente:
   ```sql
   UPDATE users SET stripe_customer_id = 'cus_...' WHERE email = '...';
   ```
4. Reintentar el webhook desde Stripe Dashboard.

---

## 12. Historia de incidencias y fixes (mayo–junio 2026)

Esta sesión arregló cosas serias. Lo dejo listado para que se entienda **por qué** el sistema tiene la pinta que tiene hoy.

### Fixes junio 2026 (commits `5cb1586`, `3504c78`, `d1923d5`)

- **Nombres de evento Stripe (punto → guion bajo)**: el webhook escuchaba `invoice.payment.succeeded` (con punto) en vez de `invoice.payment_succeeded` (guion bajo), así que el reset + despausa de clientes de pago **nunca corría**. Corregido a `_succeeded`.
- **Cancelación desactiva los 3 sistemas**: `customer.subscription.deleted` ahora, además de volver a `free`, pone `is_active = false` en `manual_ai_projects`, `ai_mode_projects` y `llm_monitoring_projects`.
- **Alertas 🚨 en reset fallido**: `_handle_payment_succeeded` loguea cuando el cliente pagó pero la cuota NO se reseteó (sin usuario para el `stripe_customer_id`, o período irresoluble).
- **`paused_until` / auto-reanudación**: la pausa por cuota graba `paused_until` (= `quota_reset_date`, fallback +30d) y los 3 sistemas auto-reanudan cuando `paused_until <= NOW()`. El LLM nunca queda colgado con `paused_until = NULL`.

### Bug: 7 usuarios con `current_period_end = NULL`

**Síntoma**: cliente Driza UEMC sin actualización 53 días.
**Causa**: Stripe movió `period_start/end` a `invoice.lines.data[0].period`. El código antiguo solo leía la raíz del `invoice`, así que cacheaba `NULL` y el cron no podía comparar fechas.
**Fix**:
- Extracción robusta multi-ruta en `stripe_webhooks.py`.
- Fallback a `stripe.Subscription.retrieve` si todo falla.
- Cron Stripe-aware con live-check para usuarios con `period_end = NULL`.
- Recuperación manual: reset + unpause de los 7 atascados.

### Bug: el cron Python en `railway.json` no se ejecutaba

**Causa**: el array `crons` de `railway.json` no se aplica en este proyecto. Solo corren los servicios "Bun function".
**Fix**: crear servicio `function-bun-Quota-reset` que llama a `/api/cron/quota-reset`. Añadir blueprint `cron_routes.py` a la app.

### Bug: `compute_next_quota_reset_date` podía devolver fecha pasada

**Causa**: si `period_end` ya había pasado, el cap lo dejaba en el pasado y el cron volvía a entrar en bucle.
**Fix**: safety net `if next_reset <= now: next_reset = now + interval_days`. Y skip del cap si `period_end <= now`.

### Bug: webhooks duplicados procesaban dos veces

**Causa**: Stripe reenvía webhooks. Sin idempotencia, una renovación podía resetear cuota dos veces (raro pero posible).
**Fix**: tabla `stripe_webhook_events`, `_claim_webhook_event` con `INSERT ... ON CONFLICT DO NOTHING RETURNING`.

### Bug: 200 OK silencioso en errores del webhook

**Causa**: try/except a lo bestia que devolvía 200 incluso en excepción.
**Fix**: `customer_not_found` → 503 (Stripe reintenta 3 días). Excepciones inesperadas → 500.

### Bug: pool de conexiones se agotaba en stress

**Causa**: muchos análisis en paralelo + crons + tráfico web.
**Fix**: `psycopg2.pool.ThreadedConnectionPool` con wrapper `_PooledConnection`. `.close()` redirige a `pool.putconn`. Retry con backoff hasta `DB_POOL_WAIT_SECONDS`.

### Bug: self-deadlock en `resume_quota_pauses_for_user`

**Causa**: el cron tomaba row-lock en `users.id=X` y luego llamaba a la función, que abría OTRA conexión y se quedaba esperando ese lock para siempre.
**Fix**: COMMIT del reset **antes** de llamar a `resume_quota_pauses_for_user`. Patrón "una conexión corta por usuario".

### Bug: un proyecto LLM colgado bloqueaba todo el cron

**Causa**: análisis sin timeout.
**Fix**: `project_timeout.py` con daemon thread + `join(timeout)`. Devuelve dict sintético `{ timed_out: True }` y el cron sigue.

### Mejora: paralelismo configurable

`LLM_PROJECT_PARALLELISM` controla con cuántos proyectos en paralelo se ejecuta el análisis (1 = secuencial; >1 = ThreadPoolExecutor con `as_completed`). Producción está en 3 actualmente.

### Mejora: alertas de cron por email

`cron_alerts.py` con 3 disparadores (duración, error rate, coste). Single batched email por run para no spamear.

---

## TL;DR para una futura sesión de Claude

1. **No metas mano sin entender el flujo de Stripe**. Webhook (capa 1) → cron diario Stripe-aware (capa 2) → health-check + email (capa 3).
2. **Toda escritura de cuota / despausa pasa por `quota_manager.py` y `database.py`**. No dupliques lógica.
3. **Los crons reales son servicios Bun en Railway**, no el array `crons` de `railway.json`. Si añades un cron nuevo, crea un Bun service que llame a un endpoint HTTP en `cron_routes.py`.
4. **Idempotencia siempre**: `INSERT … ON CONFLICT DO NOTHING RETURNING` para webhooks; cualquier handler debe tolerar reentradas.
5. **Timeout y parallelism son parámetros de runtime** (env vars), no constantes. No los hardcodees.
6. **Carlos no es técnico**. Cualquier cambio importante: explicar primero el "por qué" en lenguaje llano, después el "qué" en código.

— Fin del manual —
