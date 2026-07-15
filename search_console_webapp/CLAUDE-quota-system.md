# CLAUDE-quota-system.md — Sistema de Cuotas (transversal)

> Manual del **sistema de cuotas transversal**: cómo se mide, consume, resetea y pausa la cuota a través de los 4 productos (Manual AI, AI Mode, LLM Monitoring, AI Overview legacy).
>
> Última actualización: 2026-06-21.
>
> Manuales relacionados: `CLAUDE-stripe-cuotas-crons.md` (renovación Stripe → reset), `CLAUDE-manual-ai.md` / `CLAUDE-ai-mode.md` / `CLAUDE-llm-monitoring.md` (consumidores), `CLAUDE-base-de-datos.md` (esquema). Índice maestro: `CLAUDE-INDEX.md`.

---

## Índice

1. [Visión general en 5 minutos](#1-visión-general-en-5-minutos)
2. [Los 2 contadores de cuota](#2-los-2-contadores-de-cuota)
3. [Archivos centrales](#3-archivos-centrales)
4. [Modelo de datos](#4-modelo-de-datos)
5. [Flujo de consumo](#5-flujo-de-consumo)
6. [Flujo de reset (3 vías)](#6-flujo-de-reset-3-vías)
7. [`compute_next_quota_reset_date`](#7-compute_next_quota_reset_date)
8. [Pause / Resume cross-module](#8-pause--resume-cross-module)
9. [Cuota custom (Enterprise)](#9-cuota-custom-enterprise)
10. [Plan free](#10-plan-free)
11. [Endpoints relacionados con cuota](#11-endpoints-relacionados-con-cuota)
12. [UI de cuota](#12-ui-de-cuota)
13. [Admin panel de billing](#13-admin-panel-de-billing)
14. [Variables de entorno](#14-variables-de-entorno)
15. [Errores históricos y deuda técnica](#15-errores-históricos-y-deuda-técnica)
16. [Tests](#16-tests)

---

## 1. Visión general en 5 minutos

**Qué es la cuota.** Cada usuario de pago tiene un **tope mensual** de operaciones que puede consumir. Cuando consume hasta el tope, sus proyectos se **pausan automáticamente**. Cuando Stripe le cobra el siguiente mes, la cuota se **resetea** y los proyectos se **despausan**.

**Punto crítico**: el sistema convive con **2 contadores distintos**, no uno solo:

1. **Cuota global "RU"** (`users.quota_used` / `users.quota_limit`) — la usan SerpAPI, Manual AI, AI Mode, AI Overview.
2. **Cuota mensual de LLM Monitoring** (counted from `llm_monitoring_results`) — específica del módulo LLM, no usa `quota_used`.

**Reglas de oro:**

1. La fuente canónica del periodo de facturación es **Stripe** (`current_period_start/end`). El contador y la fecha de reset (`quota_used`, `quota_reset_date`) son **caches locales**.
2. Hay **3 vías de reset** ordenadas por prioridad: webhook Stripe → cron diario Stripe-aware → health-check + email.
3. Toda escritura de cuota / despausa pasa por `quota_manager.py` y `database.py`. **No duplicar lógica.**
4. **`is_paused_by_quota=TRUE` en proyectos** se propaga a las 4 tablas (Manual AI, AI Mode, LLM Monitoring, AI Overview a nivel user). El despausa también.
5. **Consumir cuota es siempre incremental**: pre-validar → ejecutar → `track_quota_consumption` → si se acaba, pausar.

---

## 2. Los 2 contadores de cuota

### A) Cuota global "RU" (Recursos Únicos)

- **Vive en**: `users.quota_used` (entero) vs `users.quota_limit` (entero) o `users.custom_quota_limit` (override Enterprise).
- **1 RU = 1 keyword/operación**. Constantes:
  - `manual_ai/config.py`: `MANUAL_AI_KEYWORD_ANALYSIS_COST = 1`.
  - `ai_mode_projects/config.py`: `AI_MODE_KEYWORD_ANALYSIS_COST = 1`.
- **Consumido por**:
  - SerpAPI calls (vía `quota_middleware.py`).
  - Manual AI (1 RU/keyword + 1 RU si AIO collapsed).
  - AI Mode (1 RU/keyword).
  - AI Overview legacy (1 RU/keyword exitoso).
- **Origen**: contador principal/legado, anterior a LLM Monitoring.

### B) Cuota mensual de LLM Monitoring ("units")

- **No usa `quota_used`**. Se calcula al vuelo contando filas en `llm_monitoring_results` dentro de la ventana del periodo de cuota.
- **1 unit = 1 prompt × 1 LLM**. Implementado en `llm_monitoring_limits.py:104` (`get_user_monthly_llm_usage`).
- **Límites por plan** en `LLM_PLAN_LIMITS`:

| Plan | max_projects | max_prompts_per_project | max_monthly_units |
|---|---:|---:|---:|
| basic | 1 | 20 | 640 |
| premium | 3 | 30 | 2880 |
| business | 5 | 60 | 9600 |
| enterprise | None | None | None |

- **Custom**: `users.custom_llm_prompts_limit`, `users.custom_llm_monthly_units_limit`.

### C) Relación con Stripe

- La ventana de cuota es **el aniversario mensual del cobro Stripe**, no el día 1.
- Stripe escribe `users.current_period_start/end`; estas columnas dictan cuándo procede el reset.
- `QUOTA_RESET_INTERVAL_DAYS` (default 30) actúa como ancla cuando no hay periodo Stripe.

---

## 3. Archivos centrales

### `quota_manager.py` (608 líneas)

Funciones públicas:

| Función | Qué hace |
|---|---|
| `compute_next_quota_reset_date(period_start, period_end, last_reset, now)` | Devuelve `datetime` futuro de próximo reset. Detalle en §7. |
| `get_user_effective_quota_limit(user_id)` | int. Prioridad: `custom_quota_limit > quota_limit > PLAN_LIMITS[plan]`. |
| `get_user_quota_status(user_id)` | dict con `quota_limit`, `quota_used`, `remaining`, `percentage`, `can_consume`, `plan`, `is_custom`, `reset_date`. **Función canónica usada por todo el sistema.** |
| `can_user_consume_ru(user_id, ru_amount=1)` | bool. |
| `consume_user_quota(user_id, ru_amount, operation_type, metadata)` | dict (success/message/remaining). |
| `get_user_access_permissions(user_id)` | dict (`can_use_ai_overview`, `can_use_manual_ai`, `can_use_serp_api`). |
| `get_quota_statistics()` | Estadísticas globales (admin). |
| `record_quota_usage(user_id, ru_consumed, operation_type, metadata)` | bool. UPDATE `quota_used` + INSERT `quota_usage_events`. **Casi idéntica a `track_quota_consumption` de `database.py`** (deuda — duplicación). |
| `reset_user_quota(user_id, admin_id=None)` | bool. Resetea a 0, recalcula `quota_reset_date`, registra evento, llama a `resume_quota_pauses_for_user`. **`commit` ANTES de despausar** para evitar deadlock. |

Constantes:

```python
PLAN_LIMITS = {
    'free': 0,
    'basic': 1225,
    'premium': 2950,
    'business': 8000,
    'enterprise': 0
}
PLAN_PRICES = {
    'free': 0,
    'basic': 29.99,
    'premium': 79.99,   # subida 2026-07 (grandfathering vía PRICE_ID_LEGACY_MAP)
    'business': 229.99  # subida 2026-07
}
```

### `quota_middleware.py` (380 líneas)

| Función | Qué hace |
|---|---|
| `quota_protected_serp_call(params, call_type)` | Wrapper para llamadas a SerpAPI. Patrón "reserva y confirmación". |
| `validate_quota_access(user_id, operation_type)` | dict `{allowed, reason, quota_info, action_required}`. Lógica especial: para Free permite SERP sin consumo. |
| `get_quota_warning_info(user_id)` | dict con `type` (warning/danger), `percentage`, `message`. Soft limit al 80%. |
| `get_current_user_id()` | Lee `flask.g` o `flask.session`. |

**Patrón `quota_protected_serp_call`:**
1. Si `ENFORCE_QUOTAS=false` → ejecuta sin control.
2. Cache LRU+TTL (`SERP_CALL_CACHE_TTL_SECONDS=3600`, `SERP_CALL_CACHE_MAX=5000`) para no recobrar RU en repeticiones.
3. `validate_quota_access(user_id, operation_type)`.
4. Ejecuta `_execute_serp_call` con retry exponencial (`SERPAPI_RETRY_ATTEMPTS=3`).
5. Si éxito y plan != 'free': `track_quota_consumption(...)` con `update_user_quota=True`. Para Free, `update_user_quota=False` (registra evento, no incrementa contador).

> **No hay decorador `enforce_quota_for_module`** parametrizable. Los módulos hacen la validación inline en su `analysis_service.py`.

### `llm_monitoring_limits.py` (217 líneas)

Constantes:
```python
LLM_ALLOWED_PLANS = ['basic', 'premium', 'business', 'enterprise']
LLM_ALLOWED_STATUSES = ['active', 'trialing', 'beta']
LLM_PROVIDERS = ['openai', 'anthropic', 'google', 'perplexity']
LLM_PLAN_LIMITS = {...}  # ver tabla en §2.B
```

Funciones clave:

| Función | Qué hace |
|---|---|
| `get_llm_plan_limits(plan)` | dict de límites del plan. |
| `can_access_llm_monitoring(user)` | bool. Admin pasa siempre. Si no, exige `plan ∈ LLM_ALLOWED_PLANS` y `billing_status ∈ LLM_ALLOWED_STATUSES`. |
| `count_user_active_projects(user_id)` | int. |
| `count_project_active_queries(project_id)` | int. |
| `get_upgrade_options(plan)` | list de planes superiores. |
| `get_user_monthly_llm_usage(user_id, month_date=None)` | int. **Algoritmo importante**: usa la ventana derivada de `users.quota_reset_date - interval_days` o `current_period_start/end` o último fallback al mes calendario. Cuenta filas en `llm_monitoring_results r JOIN llm_monitoring_projects p WHERE r.analysis_date >= window_start AND < window_end`. |
| `get_llm_limits_summary(user)` | dict completo: `monthly_units_used`, `monthly_units_remaining`, `active_projects`, `allowed_llms`. Para enterprise aplica `custom_llm_prompts_limit` / `custom_llm_monthly_units_limit`. |

> El "decorador `enforce_llm_access`" **NO está aquí**. Está como `before_request` hook en `llm_monitoring_routes.py:101` y devuelve **HTTP 402 Payment Required** con `error: 'paywall'`. Excepciones: rutas `/cron/` y `/health`. Permite invitados con shared access vía `user_has_any_module_access`.

---

## 4. Modelo de datos

### `users` (campos relevantes para cuota)

| Campo | Para qué | Escribe | Lee |
|---|---|---|---|
| `plan` | Plan actual (`free`, `basic`, `premium`, `business`, `enterprise`) | webhooks Stripe, admin panel | todo |
| `current_plan` | Alias / espejo histórico (`COALESCE(current_plan, plan)`) | admin | UI |
| `billing_status` | `active`/`trialing`/`past_due`/`canceled`/`beta` | webhooks | filtros cron, paywall |
| `quota_used` | Contador RU consumidos en periodo actual | `track_quota_consumption`, webhooks (reset=0), cron reset | UI, validaciones |
| `quota_limit` | Tope RU del plan | webhooks (al cambiar plan), admin | `get_user_effective_quota_limit` |
| `custom_quota_limit` | Override Enterprise (NULL = no aplica) | admin (`assign_custom_quota`) | prioridad sobre `quota_limit` |
| `quota_reset_date` | Fecha futura próximo reset (TIMESTAMPTZ) | webhook payment_succeeded, cron, admin | filtro cron, UI |
| `current_period_start` | Inicio ciclo Stripe | webhooks | cron Stripe-aware |
| `current_period_end` | Fin ciclo Stripe = próx. cobro | webhooks (con extracción robusta multi-ruta + fallback API) | cron Stripe-aware (filtro), `compute_next_quota_reset_date` |
| `cancel_at_period_end` | Bool | webhooks | UI |
| `custom_llm_prompts_limit` | Override prompts LLM (Enterprise) | admin | `get_llm_limits_summary` |
| `custom_llm_monthly_units_limit` | Override units LLM/mes (Enterprise) | admin | idem |
| `custom_quota_notes`, `custom_quota_assigned_by`, `custom_quota_assigned_date` | Auditoría asignación custom | admin | admin |
| `pending_plan`, `pending_plan_date` | Cambio de plan diferido (downgrade al final del periodo) | webhooks | UI |
| `ai_overview_paused_until/at/reason` | Pausa AI Overview a nivel **usuario** | `pause_ai_overview_for_quota` | módulo AI Overview |

### `quota_usage_events` (auditoría)

`database.py:2325-2339`:

```sql
CREATE TABLE IF NOT EXISTS quota_usage_events (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER REFERENCES users(id) ON DELETE CASCADE,
    ru_consumed     INTEGER DEFAULT 1,
    source          VARCHAR(50),
    keyword         VARCHAR(255),
    country_code    VARCHAR(3),
    timestamp       TIMESTAMPTZ DEFAULT NOW(),
    metadata        JSONB,
    CONSTRAINT chk_ru_consumed CHECK (ru_consumed > 0),
    CONSTRAINT chk_source CHECK (source IN ('ai_overview', 'manual_ai', 'serp_api'))
);
```

Índices: por `(user_id, timestamp)`, `(source)`, `(timestamp)`, `(user_id, DATE_TRUNC('month', timestamp))`.

> 🚨 **Deuda crítica**: `chk_source` solo permite **3 valores** (`ai_overview`, `manual_ai`, `serp_api`). **No permite `ai_mode`, `quota_reset`, `admin_quota_reset`**. El código lo gestiona con SAVEPOINT/try-except, pero significa que **faltan eventos en la auditoría**:
> - AI Mode: `users.quota_used` se actualiza correctamente, pero el INSERT al log falla silenciosamente.
> - Resets admin: idem.

> 🚨 **`chk_ru_consumed > 0`** impide registrar resets como `ru_consumed=0`. Workaround con SAVEPOINT.

### Campos `is_paused_by_quota` en proyectos

Tres tablas tienen el mismo conjunto de campos:

```
is_paused_by_quota  BOOLEAN DEFAULT FALSE
paused_until        TIMESTAMPTZ
paused_at           TIMESTAMPTZ
paused_reason       TEXT
```

En:
- `manual_ai_projects` (migración `migrate_manual_ai_quota_pause_fields.py`).
- `ai_mode_projects` (sin migración explícita en el repo — aplicada manualmente).
- `llm_monitoring_projects` (migración `migrate_quota_pause_fields.py`).

### AI Overview se pausa a nivel **usuario**, no proyecto

Diferencia importante: AI Overview no tiene tabla de proyectos propia (`ai_overview_analysis` es histórica), así que la pausa va en `users.ai_overview_paused_*`.

---

## 5. Flujo de consumo

### 5.1 Manual AI / AI Mode / AI Overview

Patrón común (en `manual_ai/services/analysis_service.py`, `ai_mode_projects/services/analysis_service.py`, `app.py:2521-2545`):

1. **Pre-validación al entrar al análisis del proyecto:**
   - Si `project.is_paused_by_quota = TRUE` y `paused_until > NOW()` → return error `'project_paused_quota'`.
   - Si `paused_until <= NOW()` → auto-despausa ese proyecto (UPDATE local, sin tocar otros) y continúa.
   - `quota_info = get_user_quota_status(user_id)`.
   - Si `not can_consume` → llama a `pause_<module>_projects_for_quota(user_id, paused_until=quota_info['reset_date'] or NOW+30d)` y devuelve error con `paused_until`.

2. **Loop por keyword:**
   - **Re-valida cuota en CADA iteración** (`get_user_quota_status` cada vez): si `remaining < cost`, pausa los proyectos del user y `break`.
   - Ejecuta el análisis. Si éxito: `track_quota_consumption(user_id, ru_consumed=1, source='manual_ai|ai_mode|ai_overview', keyword=..., country_code=..., metadata={...})`.

3. **`track_quota_consumption`** (`database.py:2098`):
   - INSERT a `quota_usage_events`.
   - UPDATE `users.quota_used += ru_consumed` (a menos que `update_user_quota=False`, caso Free + SerpAPI).
   - Reintentos exponenciales para `DEADLOCK_DETECTED` y `SERIALIZATION_FAILURE` (`DB_RETRY_ATTEMPTS=3`).

4. **Si excepción tiene `is_quota_error`** (proveedor detectó hard-block): pausa proyectos del user, devuelve `quota_exceeded: True`, `action_required`, `paused_until`.

5. **HTTP**: el endpoint del módulo devuelve **429** + `quota_blocked: true` + `quota_info` + `action_required`. El frontend (`quota-ui.js`) detecta y muestra modal.

### 5.2 LLM Monitoring

Diferente patrón. Tras el refactor de LLM Monitoring (Fase 3), la lógica de cuota vive en `services/llm_monitoring/engine.py` (función `_analyze_one`, ~277-296); el filtro del cron está en `services/llm_monitoring_service.py:160-163`.

- **Pre-análisis** (`engine.py:277`): `get_user_monthly_llm_usage(user_id, analysis_date)` vs `max_units` (custom o de plan, `max_monthly_units`).
- Si `used >= max_units` o `used + expected > max_units` → llama a `pause_llm_projects_for_quota(user_id, paused_until)` (`engine.py:296`) y devuelve error de cuota.
- **`paused_until`**: misma regla unificada que Manual AI / AI Mode — `quota_status['reset_date']` global, con fallback `datetime.utcnow() + timedelta(days=30)` (`engine.py:293`) para **nunca** pausar con `paused_until=NULL` (que dejaría una pausa indefinida que ni el cron ni el gate per-proyecto reanudarían). Fix commit `3504c78`.
- **Auto-reanudación**: el filtro del cron (`llm_monitoring_service.py:160-163`) incluye proyectos cuyo `paused_until <= NOW()` aunque sigan con `is_paused_by_quota=TRUE`; al re-analizarse, el gate per-proyecto limpia el flag y continúa. Sin necesidad de pasar por `resume_quota_pauses_for_user`.
- **No hay tracking incremental**. Las "units" se miden contando `llm_monitoring_results` post-hoc.
- **No hay tabla `llm_quota_events`**.

### Diagrama de consumo

```
Usuario lanza análisis
        │
        ▼
┌─────────────────────────────────────┐
│ Pre-validación cuota                │
│ (get_user_quota_status / monthly)   │
└─────────────────────────────────────┘
        │
        ▼ (si tiene cuota)
┌─────────────────────────────────────┐
│ Loop por keyword/prompt:             │
│  - Re-valida cuota                   │
│  - Ejecuta operación                 │
│  - track_quota_consumption           │
│    (UPDATE users + INSERT events)    │
└─────────────────────────────────────┘
        │
        ▼ (si se queda sin cuota a mitad)
┌─────────────────────────────────────┐
│ pause_<module>_projects_for_quota   │
│ Marca is_paused_by_quota=TRUE       │
└─────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────┐
│ HTTP 429 + quota_blocked            │
│ Frontend muestra modal upgrade       │
└─────────────────────────────────────┘
```

---

## 6. Flujo de reset (3 vías)

### Vía 1 — Webhook Stripe `invoice.payment_succeeded`

`stripe_webhooks.py:599`:

1. Extrae `period_start/end` con cascada multi-ruta (raíz invoice → `invoice.lines.data[0].period` → fallback `stripe.Subscription.retrieve`).
2. `compute_next_quota_reset_date` con period_start como `now`.
3. UPDATE: `quota_used=0`, `quota_reset_date=next_reset`, `billing_status='active'`, `current_period_start/end=...` WHERE `stripe_customer_id=...` RETURNING id.
4. `conn.commit()` y luego `resume_quota_pauses_for_user(row['id'])` con conexión nueva (anti-deadlock).

### Vía 2 — Cron diario `daily_quota_reset_cron.py`

Disparado por servicio Bun "function-bun-Quota-reset" → `POST /api/cron/quota-reset` (`cron_routes.py:48`) con `Authorization: Bearer CRON_TOKEN`.

**Filtro Stripe-aware** (`daily_quota_reset_cron.py:74-86`):

```sql
WHERE plan != 'free'
  AND billing_status IN ('active', 'trialing', 'beta')
  AND (quota_reset_date IS NULL OR quota_reset_date <= NOW())
  AND (
      subscription_id IS NULL
      OR current_period_end IS NULL
      OR current_period_end <= NOW()
  )
```

Excluye usuarios con Stripe activo y periodo en futuro (esos los reseteará el webhook).

**Live check Stripe API** para casos legacy: si `subscription_id IS NOT NULL AND current_period_end IS NULL` (bug Driza), llama `_fetch_live_stripe_period_end(sub_id)` vía API. Si Stripe dice que el periodo todavía es futuro, **skip** (`skipped_stripe_active`).

**Patrón commit-por-usuario**: cada user en su propia conexión corta. UPDATE → commit → llamada a `resume_quota_pauses_for_user` en NUEVA conexión (evita self-deadlock).

### Vía 3 — Health check post-cron

`cron_routes.py:123` `_run_health_check_and_alert`:

- Detecta usuarios con `quota_reset_date < NOW() - 1 day` y plan de pago.
- Si encuentra alguno: `_send_stuck_quota_alert(stuck)` envía email a `CRON_ALERTS_EMAIL` con tabla de afectados.
- Silenciable con `CRON_ALERTS_ENABLED=false`.
- Endpoint independiente: `POST /api/cron/quota-health-check`.

### Diagrama de reset

```
        STRIPE COBRA
              │
              ▼
   ┌──────────────────────────────────────┐
   │ VÍA 1: Webhook payment_succeeded     │
   │  ─ quota_used = 0                    │
   │  ─ Update quota_reset_date           │
   │  ─ resume_quota_pauses_for_user      │
   └──────────────────────────────────────┘
              │
              ▼ (si webhook falla / period_end NULL)
   ┌──────────────────────────────────────┐
   │ VÍA 2: Cron diario quota-reset       │
   │  ─ Excluye Stripe activo             │
   │  ─ Live check si period_end NULL     │
   │  ─ Reset + unpause                   │
   └──────────────────────────────────────┘
              │
              ▼ (si tras cron sigue alguien atascado)
   ┌──────────────────────────────────────┐
   │ VÍA 3: Health check + email alerta   │
   │  ─ Detecta quota_reset_date < ayer   │
   │  ─ Email a Carlos via Brevo SMTP     │
   └──────────────────────────────────────┘
```

---

## 7. `compute_next_quota_reset_date`

`quota_manager.py:38-82`. Función crítica que calcula la próxima fecha de reset.

### Lógica

```python
1. interval_days = QUOTA_RESET_INTERVAL_DAYS  # default 30
2. now = now or datetime.utcnow()
3. base = last_reset or period_start or now
   (parsea ISO si es string, fallback a now)
4. next_reset = base + 30d
5. Si period_end > now y next_reset > period_end → cap a period_end
6. Si period_end ya pasó → ignorado (no usa cap a fecha pasada)
7. While next_reset <= now: avanza otros 30d hasta colocarlo en futuro
8. SAFETY NET: si tras todo next_reset <= now → next_reset = now + 30d
```

### Edge cases manejados

- `last_reset` y `period_*` todos NULL → base = now → next_reset = now + 30d.
- `period_end` muy pasado (legacy/beta) → ignorado, fallback al loop while.
- Un único `next_reset = period_end` que ya pasó → safety net.

### Bug histórico crítico (2026-05-07)

**Antes** del fix, podía retornar fecha pasada si `period_end` ya había pasado (cap a una fecha pasada). El cron resetearía el mismo user cada día → loop infinito.

**Fix**: safety net `if next_reset <= now: next_reset = now + interval_days` (línea 79-80).

> ⚠️ **`now` es naive (no tz-aware)** en la firma — pero el cron sí pasa tz-aware con `datetime.now(timezone.utc)`. Pequeña inconsistencia que funciona pero podría causar errores en otros callers.

---

## 8. Pause / Resume cross-module

### Funciones de pausa (en `database.py`)

| Función | Línea | Qué hace |
|---|---:|---|
| `pause_ai_overview_for_quota(user_id, paused_until, reason)` | 2446 | UPDATE `users.ai_overview_paused_*`. **Pausa a nivel usuario, no proyecto** (porque AI Overview no tiene tabla de proyectos). |
| `pause_ai_mode_projects_for_quota(user_id, paused_until, reason)` | 2473 | UPDATE `ai_mode_projects` WHERE `user_id` AND `is_active=TRUE`. |
| `pause_llm_projects_for_quota(user_id, paused_until, reason)` | 2502 | UPDATE `llm_monitoring_projects` WHERE `user_id` AND `is_active=TRUE`. |
| `pause_manual_ai_projects_for_quota(user_id, paused_until, reason)` | 2531 | UPDATE `manual_ai_projects` WHERE `user_id` AND `is_active=TRUE`. |

> **Asimetría pausa-vs-resume respecto a `is_active`**: las 3 funciones de pausa de proyectos filtran `... AND is_active = TRUE` (solo pausan proyectos activos). En cambio `resume_quota_pauses_for_user` **NO** filtra `is_active` (solo `WHERE user_id = %s`): nunca toca la columna `is_active`, así que "preserva `is_active`" significa que jamás la modifica, **no** que respete su valor al despausar.

### Quién llama a cada una

- `pause_manual_ai_projects_for_quota`: `manual_ai/services/analysis_service.py:132,166,294` (pre-validación, mid-loop y excepción de proveedor).
- `pause_ai_mode_projects_for_quota`: `ai_mode_projects/services/analysis_service.py:136,167,286`.
- `pause_llm_projects_for_quota`: `services/llm_monitoring/engine.py:296` (cuando `max_units` excedido). Tras el refactor Fase 3 la llamada está en el engine, no en `llm_monitoring_service.py`.
- `pause_ai_overview_for_quota`: **SÍ tiene llamadores activos** en `app.py:2285` y `app.py:2428` (ambos pasan `quota_status.get('reset_date')` como `paused_until`, `reason='quota_exceeded'`). No es dead code.

### `resume_quota_pauses_for_user(user_id)` (`database.py:2560`)

**Función única que despausa todos los módulos**. Patrón:

- 3 UPDATEs estables en una sola transacción: `users` (limpia `ai_overview_paused_*`), `ai_mode_projects`, `llm_monitoring_projects`.
- 4º UPDATE de `manual_ai_projects` envuelto en `SAVEPOINT before_manual_ai_resume` para tolerar deployments antiguos sin la columna (rollback parcial al savepoint, no a toda la transacción).
- `commit` al final.

### Quién llama a `resume_quota_pauses_for_user`

| Llamador | Cuándo |
|---|---|
| `quota_manager.reset_user_quota` (def línea 516, llamada a resume en 592) | Reset manual de admin. |
| `daily_quota_reset_cron.main` (línea 199) | Cron diario tras reset. |
| `stripe_webhooks._handle_payment_succeeded` (línea 685) | Tras pago Stripe. |
| `admin_billing_panel.reset_user_quota_manual` | Reset manual desde panel admin. |

> **Crítico**: todos hacen `commit` ANTES de llamar a esta función para evitar self-deadlock.

### Auto-reanudación por `paused_until` (sin pasar por resume)

Hay **dos** vías de despausa. `resume_quota_pauses_for_user` es la global (tras reset de cuota). La otra es la **auto-reanudación per-proyecto** que ocurre cuando vence la ventana `paused_until`, independiente del reset:

- **Manual AI / AI Mode** (`analysis_service.py` de cada módulo): al entrar al análisis de un proyecto, si `is_paused_by_quota=TRUE` pero `paused_until <= NOW()`, el gate **limpia `is_paused_by_quota`/`paused_*` SOLO de ese proyecto** (UPDATE local, sin tocar otros) y continúa. Si `paused_until > NOW()` (o `NULL`), bloquea con `project_paused_quota`.
- **LLM Monitoring**: doble mecanismo — el filtro del cron (`llm_monitoring_service.py:160-163`) reincluye proyectos con `paused_until <= NOW()` aunque sigan marcados, y el gate per-proyecto del engine (`engine.py:121-160`) limpia el flag al re-analizar.
- **Regla unificada de `paused_until`** (fix commit `3504c78`): al pausar, `paused_until = quota_reset_date` global (`get_user_quota_status()['reset_date']`), con fallback `datetime.utcnow() + timedelta(days=30)` si viene `NULL`. **Nunca se pausa con `paused_until=NULL`**, porque sería una pausa indefinida que ni el cron ni el gate per-proyecto auto-reanudarían. Aplica idéntico en Manual AI, AI Mode y LLM.

---

## 9. Cuota custom (Enterprise)

### Tres campos para overrides

| Campo | Para qué |
|---|---|
| `users.custom_quota_limit` | RU global. Prioridad: `custom_quota_limit > quota_limit > PLAN_LIMITS[plan]`. |
| `users.custom_llm_prompts_limit` | Max prompts/proyecto LLM. |
| `users.custom_llm_monthly_units_limit` | Max units/mes LLM. |

Los LLM aplican **solo cuando `plan == 'enterprise'`** (`llm_monitoring_limits.py:196-202`).

### Asignación

`admin_billing_panel.assign_custom_quota(user_id, custom_limit, notes, admin_id, custom_llm_prompts_limit=None, custom_llm_monthly_units_limit=None)` (línea 899).

Validaciones: tipos enteros, `>= 1`. Persiste también en `custom_quota_notes`, `custom_quota_assigned_by`, `custom_quota_assigned_date`.

### Endpoint admin

`POST /admin/users/<int:user_id>/update-plan` (`admin_billing_routes.py:198`).

### Eliminación

UPDATE a NULL en `admin_billing_panel.py:1037-1042`.

---

## 10. Plan free

### Reglas

- `users.plan = 'free'` con `PLAN_LIMITS['free'] = 0`.
- `quota_manager.get_user_access_permissions`: free → `can_use_ai_overview=False, can_use_manual_ai=False, can_use_serp_api=False`.
- **LLM Monitoring**: bloqueado en `before_request` hook (devuelve 402 + `error: 'paywall'`). Excepción: invitados con `user_has_any_module_access(user_id, 'llm_monitoring') = TRUE` (proyectos compartidos).
- **SerpAPI**: en `quota_middleware.validate_quota_access`, plan free es **permitido** sin consumo (línea 135-141): *"Plan Free: SERP permitido (sin consumo de RU)"*.
- En `quota_protected_serp_call:265`: `update_user_quota = enforce_quotas and status.get('plan') != 'free'` — para Free, registra evento sin tocar `quota_used`.

### UI para Free

`static/js/quota-ui.js:325-331`: para plan free el modal de quota **no se muestra** (`shouldShowQuotaUI` retorna false). Se ven mensajes de paywall ("upgrade to access") en su lugar.

---

## 11. Endpoints relacionados con cuota

| Endpoint | Función |
|---|---|
| `GET /api/quota/status` (`app.py:1615`) | `{quota_status, access_permissions, warning_info}`. Lo consume `quota-ui.js`. |
| `GET /api/llm-monitoring/usage` (`llm_monitoring_routes.py:581`) | `{success, limits}` con `get_llm_limits_summary(user)`. |
| `GET /api/llm-monitoring/projects` (línea 564) | Incluye `limits` en payload. |
| `POST /api/cron/quota-reset` (`cron_routes.py:48`) | Auth Bearer CRON_TOKEN. `?async=1` (202) o sync (200). Triggers cron + health-check. |
| `POST /api/cron/quota-health-check` (`cron_routes.py:108`) | Solo health (sin reset). |
| `POST /admin/users/<id>/reset-quota` (`admin_billing_routes.py:218`) | Admin manual reset. |
| `POST /admin/users/<id>/update-plan` (`admin_billing_routes.py:72,198`) | Cambia plan / asigna custom quota. |
| `GET /admin/billing` y `GET /admin/users/<id>/billing-details` | Vistas admin. |
| `POST /webhooks/stripe` | Handler en `stripe_webhooks.py`. Fuente principal de resets. |

---

## 12. UI de cuota

### Archivos

| Archivo | Qué contiene |
|---|---|
| `static/quota-ui.css` | Referenciado en `templates/index.html:51`, `llm_monitoring.html:32`, `ai_mode_dashboard.html:32`, `manual_ai_dashboard.html:32`. |
| `static/js/quota-ui.js` (429 líneas) | Expone `window.QuotaUI`. |

### `window.QuotaUI`

Métodos públicos:

| Método | Qué hace |
|---|---|
| `showQuotaWarning(quotaInfo)` | Banner soft limit (mostrado solo si percentage>=100; el 80% está deshabilitado a propósito, ver línea 392-393). |
| `showQuotaBlockModal(errorData)` | Modal de bloqueo (free → "premium feature", enterprise → "contact support", paid → "upgrade"). |
| `handleQuotaUpgrade(plan)` | Navega según `UPGRADE_URLS` (free→/billing, basic→/billing/checkout/premium, premium→/billing/checkout/business, enterprise→/contact). |
| `quotaAwareFetch(url, options)` | Wrapper que detecta 429 + `quota_blocked` y dispara modal. |
| `checkUserQuotaStatus()` | Auto-llamado al cargar; consulta `/api/quota/status`. |

### Llamadas desde módulos

- `static/js/manual-ai-system.js:1381`.
- `static/js/ui-ai-overview-analysis.js:372`.
- `static/js/ai-mode-projects/ai-mode-analysis.js:105`.
- `static/js/manual-ai/manual-ai-analysis.js:105`.

Todos llaman a `window.QuotaUI.showBlockModal(...)`.

---

## 13. Admin panel de billing

### `admin_billing_panel.py` — funciones clave

| Función | Línea | Qué hace |
|---|---:|---|
| `get_users_with_billing_info(limit, offset)` | ~530 | Lista usuarios con todos los campos billing/quota + métricas enriquecidas (`serp_ru_month`, `ru_month`, `llm_units_month`, `llm_cost_month`, `llm_active_projects`, `ai_mode_paused_projects`, `llm_paused_projects`, contadores de proyectos por módulo). |
| `get_user_billing_details(user_id)` | 644 | Detalles individuales. |
| `update_user_plan_manual(user_id, new_plan, admin_id)` | 746 | Cambio manual de plan. |
| `assign_custom_quota(user_id, custom_limit, notes, admin_id, ...)` | 899 | Asigna custom quota Enterprise. |
| `reset_user_quota_manual(user_id, admin_id)` | 1144 | Reset + recalc fecha + INSERT evento (con SAVEPOINT por el constraint chk_source) + commit + `resume_quota_pauses_for_user`. |
| `get_users_with_custom_quotas()` | ~1100 | Lista de Enterprise / con override. |

### Rutas admin

`admin_billing_routes.py` registra:
- `/admin/billing` (panel).
- `/admin/users/<id>/billing-details`.
- `/admin/users/<id>/update-plan`.
- `/admin/users/<id>/reset-quota`.
- `/admin/billing-stats`.

Decorador: `@admin_required`.

### Cómo Carlos puede operar

| Acción | Cómo |
|---|---|
| Ver cuota de un usuario | `/admin/users/<id>/billing-details`. |
| Cambiar plan | `/admin/users/<id>/update-plan` (POST). |
| Dar cuota custom | Misma ruta con `custom_quota_limit` en el body. |
| Resetear cuota manualmente | `/admin/users/<id>/reset-quota` (POST). |
| Despausar proyectos | Automático tras el reset (vía `resume_quota_pauses_for_user`). |

---

## 14. Variables de entorno

| Variable | Default | Uso |
|---|---|---|
| `QUOTA_RESET_INTERVAL_DAYS` | `30` | Días entre resets (`quota_manager.py:51`, `llm_monitoring_limits.py:122`). |
| `ENFORCE_QUOTAS` | `false` | **Master switch** para enforcement (`quota_middleware.py:223`, `stripe_config.py:56`). |
| `QUOTA_SOFT_LIMIT_PCT` | `80` | Umbral aviso soft (`stripe_config.py:60`) — pero el JS lo tiene deshabilitado. |
| `QUOTA_GRACE_PERIOD_HOURS` | `24` | Definido en `stripe_config.py:61` pero **no encontré uso real**. |
| `SERP_CALL_CACHE_TTL_SECONDS` | `3600` | TTL cache de llamadas SerpAPI. |
| `SERP_CALL_CACHE_MAX` | `5000` | Tamaño máximo cache LRU. |
| `SERPAPI_RETRY_ATTEMPTS` | `3` | Retry SerpAPI. |
| `SERPAPI_RETRY_BACKOFF_SECONDS` | `1.0` | Base delay. |
| `DB_RETRY_ATTEMPTS` | `3` | Retry para deadlocks en `track_quota_consumption`. |
| `DB_RETRY_BACKOFF_SECONDS` | `0.5` | Base delay. |
| `CRON_TOKEN` (o `CRON_SECRET`) | (oblig.) | Bearer auth `cron_routes.py:34`. |
| `CRON_ALERTS_ENABLED` | `true` | Silencia alertas stuck-quota. |
| `CRON_ALERTS_EMAIL` | `info@soycarlosgonzalez.com` | Destinatario. |
| `STRIPE_SECRET_KEY` | (oblig.) | Live API fallback en `daily_quota_reset_cron._fetch_live_stripe_period_end`. |

---

## 15. Errores históricos y deuda técnica

### Bugs históricos resueltos

#### 2026-06-20/21: pausas LLM/Stripe + auto-reanudación (commits `5cb1586`, `3504c78`, `d1923d5`)

- **Síntoma**: clientes de pago no se reseteaban ni despausaban tras el pago; proyectos LLM quedaban pausados de forma indefinida.
- **Causas**: (1) el dispatcher Stripe comprobaba `'invoice.payment.succeeded'` (con punto) en vez de `'invoice.payment_succeeded'` (guion bajo, el nombre real) → el reset+despausa de pago nunca corría; (2) el cron/engine de LLM no honraban `paused_until`, y la pausa LLM podía dejar `paused_until=NULL` → pausa indefinida que nada auto-reanudaba; (3) cancelación no desactivaba los 3 sistemas.
- **Fix**: nombres de evento con guion bajo; LLM honra `paused_until` (filtro cron + gate per-proyecto) y nunca pausa con NULL (fallback `+30d` unificado con Manual AI / AI Mode); cancelación desactiva los 3 sistemas + alertas en reset de pago fallido. Blindado por `tests/test_quota_pauses_regression.py`. En PROD desde 2026-06-20.

#### 2026-05-07: caso Driza UEMC (7 usuarios sin reset)

- **Síntoma**: cliente Driza UEMC sin actualización 53 días.
- **Causa**: Stripe movió `period_start/end` a `invoice.lines.data[0].period`. El código antiguo solo leía la raíz, lo que dejó 7 usuarios con `current_period_end=NULL` y sin reset.
- **Fix**: extracción multi-ruta + fallback `Subscription.retrieve` (`stripe_webhooks.py:613-641`). Cron Stripe-aware con live-check.

#### 2026-05-07: loop infinito en `compute_next_quota_reset_date`

- **Síntoma**: el cron resetearía el mismo user cada día y la alerta saltaría diariamente.
- **Causa**: la función podía retornar fecha pasada si `period_end` ya había pasado (cap a una fecha pasada).
- **Fix**: safety net `if next_reset <= now: next_reset = now + interval_days` (`quota_manager.py:79-80`).

#### 2026-04-08: deadlock en `reset_user_quota`

- **Causa**: `reset_user_quota` mantenía row-lock en `users.id=X` y luego llamaba a `resume_quota_pauses_for_user` que abría OTRA conexión y se quedaba esperando el lock para siempre.
- **Fix**: `commit` antes de despausar. Patrón replicado en `daily_quota_reset_cron`, `stripe_webhooks._handle_payment_succeeded`, `admin_billing_panel.reset_user_quota_manual`.

#### `idle_in_transaction_session_timeout` (15 min)

- Comentario en `manual_ai/services/analysis_service.py:141-147` — antes mantenían cursor abierto durante todo el loop de keywords; ahora abren conn local solo en la rama quota_error.

#### 2026-05-07: resume con SAVEPOINT

- **Causa**: `resume_quota_pauses_for_user` antes hacía rollback total y re-ejecutaba si `manual_ai_projects` no tenía la columna.
- **Fix**: SAVEPOINT y rollback solo de ese paso.

### Deuda técnica conocida

| Deuda | Impacto | Riesgo |
|---|---|---|
| **`chk_source` desactualizado en `quota_usage_events`** | AI Mode events y resets admin perdidos en log | Medio |
| **`chk_ru_consumed > 0`** impide insertar resets como `0` | Workaround con SAVEPOINT | Bajo |
| **Duplicación**: `quota_manager.record_quota_usage` vs `database.track_quota_consumption` | Confusión para futura sesión | Medio |
| **AI Overview pausa a nivel usuario (no proyecto)** vía `pause_ai_overview_for_quota` (`app.py:2285,2428`) | Modelo distinto al resto; no participa en la auto-reanudación per-proyecto de Manual AI/AI Mode/LLM | Bajo |
| **`get_user_monthly_llm_usage` cuenta filas, no eventos** | Si `force_overwrite` borra y reinserta, la cuenta cambia | Bajo |
| **AI Mode tracking pasa `source='ai_mode'`** que no está permitido | INSERT falla silenciosamente. `users.quota_used` se actualiza correctamente porque ese UPDATE es independiente | Medio |
| **`compute_next_quota_reset_date` mezcla naive/tz-aware** | Funciona pero podría causar errores | Bajo |
| **`QUOTA_GRACE_PERIOD_HOURS`** definido pero no usado | Trivial | Trivial |
| **No hay decorador `enforce_quota_for_module`** parametrizable | Validación inline en cada `analysis_service` (deuda de DRY) | Bajo |

### Discrepancias entre módulos

| Concepto | Manual AI | AI Mode | LLM Monitoring | AI Overview |
|---|---|---|---|---|
| **Pause level** | proyecto | proyecto | proyecto | usuario |
| **Quota counter** | `users.quota_used` | `users.quota_used` | counted from results | `users.quota_used` |
| **Re-validación mid-loop** | Sí | Sí | No (validación al inicio) | Sí |
| **Pausa parcial** | Sí (puede parar a mitad) | Sí | No (proyecto-completo) | Sí |
| **Source en `quota_usage_events`** | `'manual_ai'` ✅ | `'ai_mode'` ❌ (CHECK falla) | (no usa events) | `'ai_overview'` ✅ |

---

## 16. Tests

### Tests específicos de cuota

| Archivo | Cubre |
|---|---|
| `test_stripe_aware_reset.py` | Crea 4 usuarios test (no-sub, stripe-active, stripe-expired, stripe-legacy con NULL), corre `daily_quota_reset_cron.main()`, verifica que solo se resetean los correctos. Usa `unittest.mock.patch`. |
| `test_webhook_hardening.py` | Idempotencia (`stripe_webhook_events`) y extracción robusta del periodo desde `invoice.lines`. |
| `test_cron_routes.py` | Tests de los endpoints `/api/cron/*` (auth bearer, async/sync, health). |
| `test_cron_alerts.py` | Alerta de duración/error rate/coste. |
| `test_llm_cron_jobs.py` | Flujo completo del cron LLM (incluye eligibility filter). |
| `tests/test_quota_pauses_regression.py` | **Regresión del fix de pausas (commits `3504c78`/`d1923d5`)**: el dispatcher Stripe usa los nombres de evento reales con guion bajo (`invoice.payment_succeeded`) y no la variante con punto; el cron y el engine de LLM honran `paused_until` (auto-reanudan al expirar, mismo criterio que Manual AI); la pausa LLM nunca deja `paused_until=NULL` (fallback `+30d`). Asserts sobre el código fuente. |

### Scripts (no tests)

- `fix_quota_events_table.py` — script para arreglar la tabla `quota_usage_events` si tiene constraints viejos.

### Lo que NO está cubierto

- **Lógica de `compute_next_quota_reset_date`** con edge cases (period_end pasado, NULL, etc.) — solo cubierta indirectamente via `test_stripe_aware_reset.py`.
- **`track_quota_consumption` con retry para deadlocks** — sin test específico.
- **`resume_quota_pauses_for_user` con SAVEPOINT** — solo `test_webhook_hardening.py:121-123` valida que el código fuente contiene el `SAVEPOINT` (assertion sobre el código, no comportamiento).

---

## TL;DR

1. **Dos contadores**: RU global (`users.quota_used` para SerpAPI/Manual AI/AI Mode/AI Overview) y units mensuales (counted from `llm_monitoring_results` para LLM Monitoring). No están unificados.
2. **`get_user_quota_status(user_id)` es la función canónica.** Toda validación pasa por aquí.
3. **3 vías de reset**: webhook Stripe → cron diario Stripe-aware → health-check con email. Defensa en profundidad.
4. **`compute_next_quota_reset_date` tiene safety net** que garantiza fecha futura — fix crítico del 2026-05-07.
5. **Pause/Resume cross-module**: `pause_<module>_projects_for_quota` por módulo + `resume_quota_pauses_for_user` que limpia las 4 ubicaciones (con SAVEPOINT para Manual AI).
6. **Plan free no consume cuota** (SerpAPI permitido sin consumo, LLM bloqueado, Manual AI / AI Mode con paywall blando).
7. **Enterprise = `custom_quota_limit`, `custom_llm_prompts_limit`, `custom_llm_monthly_units_limit`** sobreescriben los valores del plan.
8. **`chk_source` en `quota_usage_events` está desactualizado** — eventos `'ai_mode'`, `'quota_reset'`, `'admin_quota_reset'` no se persisten en log (deuda).
9. **Todos los resets hacen `commit` ANTES de llamar a `resume_quota_pauses_for_user`** para evitar self-deadlock.
10. **Diferencia clave LLM vs resto**: LLM pausa proyecto-completo (no a mitad de prompts), no escribe en `quota_usage_events`, cuenta consumo post-hoc desde `llm_monitoring_results`.

— Fin del manual —
