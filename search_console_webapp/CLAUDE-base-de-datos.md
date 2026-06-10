# CLAUDE-base-de-datos.md — Base de Datos

> Manual de la **Base de Datos** del proyecto: PostgreSQL + `psycopg2` con pool, sin ORM, esquema completo, patrones transversales (advisory locks, SAVEPOINT, idempotencia), migraciones manuales y troubleshooting.
>
> Última actualización: 2026-05-08.
>
> Manuales relacionados: `CLAUDE-stripe-cuotas-crons.md`, `CLAUDE-manual-ai.md`, `CLAUDE-ai-mode.md`, `CLAUDE-llm-monitoring.md`, `CLAUDE-quota-system.md`. Índice maestro: `CLAUDE-INDEX.md`.

---

## Índice

1. [Visión general en 5 minutos](#1-visión-general-en-5-minutos)
2. [Pool de conexiones (`database.py`)](#2-pool-de-conexiones-databasepy)
3. [Esquema completo de la BD](#3-esquema-completo-de-la-bd)
4. [Migraciones](#4-migraciones)
5. [Patrones transversales](#5-patrones-transversales)
6. [Helpers más importantes en `database.py`](#6-helpers-más-importantes-en-databasepy)
7. [Variables de entorno](#7-variables-de-entorno)
8. [Operaciones administrativas](#8-operaciones-administrativas)
9. [Errores históricos y deuda técnica](#9-errores-históricos-y-deuda-técnica)
10. [Tests](#10-tests)

---

## 1. Visión general en 5 minutos

- **Motor**: PostgreSQL gestionado por Railway (la versión exacta no se fuerza en código).
- **Driver**: `psycopg2` con `RealDictCursor` (rows como `dict`). **Sin ORM** — todo es SQL plano. Migraciones, helpers y queries se escriben a mano.
- **Pool**: `psycopg2.pool.ThreadedConnectionPool` con un wrapper transparente `_PooledConnection` que intercepta `.close()` y la redirige a `pool.putconn`.
- **Staging vs producción**: dos BDs separadas, distinguidas por `RAILWAY_ENVIRONMENT` (`staging` | `production`). URLs reales con credenciales hardcodeadas en `migrate_llm_staging_to_production.py:11-12` (deuda).
- **Cifrado opcional**: `cryptography.fernet.Fernet` para `oauth_connections.refresh_token_encrypted` cuando hay `TOKEN_ENCRYPTION_KEY`. Sin clave → almacenamiento en claro.
- **Sin migraciones formales** (alembic/flyway). Cada migración es un script Python idempotente (`ADD COLUMN IF NOT EXISTS`, `CREATE TABLE IF NOT EXISTS`). Algunas se ejecutan automáticamente al startup vía `init_database.main()`; el resto son one-shots manuales.

**Reglas de oro:**

1. **Siempre** usar `database.get_db_connection()`. Nunca `psycopg2.connect()` directo (excepto en migraciones one-shot).
2. **Conexiones cortas**: abrir → trabajar → cerrar. Para crons largos: `autocommit=True` para evitar `idle_in_transaction_session_timeout`.
3. **`.close()` no destruye la conexión**, la devuelve al pool. Es idempotente.
4. **Idempotencia siempre**: `INSERT ... ON CONFLICT DO NOTHING/UPDATE RETURNING` para webhooks/eventos externos.
5. **SAVEPOINT** para recuperación parcial cuando no quieres que un fallo en una tabla aborte el resto.
6. **Advisory locks** para cron exclusivo entre runs simultáneos.

---

## 2. Pool de conexiones (`database.py`)

Archivo central: `/Users/carlosgonzalez/Desktop/app/APP-WEB-GSC-AI/search_console_webapp/database.py` (~2742 líneas).

### `_PooledConnection` — wrapper transparente

Líneas 103-175. `__slots__ = ('_conn', '_pool', '_returned')`.

- **`close()`** (línea 122): si no devuelta ya, hace rollback implícito y `pool.putconn(self._conn)`. Si la conn física está cerrada (Postgres la mató por timeout), llama `pool.putconn(self._conn, close=True)` para descartarla.
- **Idempotente**: segunda llamada a `close()` es no-op.
- **`__getattr__` proxy** a la conn real (cursor, commit, rollback, autocommit…).
- **`__setattr__` proxy** también → `conn.autocommit = True` funciona (necesario para advisory locks).
- **`__enter__` / `__exit__`** para `with get_db_connection() as conn:`. En `__exit__` con excepción hace rollback antes del `close()`.

### Pool global

Líneas 61-100:

- `_pool` global + `_pool_lock` (threading.Lock) → init lazy con `_get_or_init_pool()`.
- `_build_pool()` crea `psycopg2.pool.ThreadedConnectionPool(minconn, maxconn, DATABASE_URL, **_connect_kwargs())`.
- **Defaults reales** (verificados en código):
  - `DB_POOL_MIN = 2`
  - `DB_POOL_MAX = 20`
  - `DB_POOL_WAIT_SECONDS = 10.0`
  - (CLAUDE.md general decía `1/8` — está obsoleto. La verdad operativa es `2/20`.)

### `_connect_kwargs()` siempre incluye:

```python
cursor_factory=RealDictCursor
connect_timeout=10
options='-c idle_in_transaction_session_timeout=900000'   # 15 min
keepalives=1
keepalives_idle=30
keepalives_interval=10
keepalives_count=5    # detecta conexiones muertas en ~80s
```

### `get_db_connection()` — retry con backoff

Líneas 178-245.

- Si `DB_POOL_DISABLED=true` → bypass del pool, `psycopg2.connect()` directo (escape hatch).
- Si pool init falla → fallback directo (no rompe la app).
- Loop con deadline `DB_POOL_WAIT_SECONDS` (default 10s). Backoff exponencial empezando en 50ms, cap a 1s.
- Si `pool.getconn()` devuelve una conn ya cerrada → la descarta con `putconn(close=True)` y reintenta.
- En `PoolError` (pool agotado) → reintenta hasta deadline; si se agota → `log.error` + `return None`.

### Inicialización en arranque

- `app.py:3829-3843` define `initialize_database_on_startup()` que llama `init_database.main()`.
- `init_database.main()` ejecuta secuencialmente:
  1. `init_database()` (línea 265) — crea tablas base.
  2. `migrate_user_timestamps()`.
  3. `ensure_sample_data()`.
  4. `init_ai_overview_tables()`.
  5. `create_manual_ai_tables()`.
  6. `migrate_project_access_control.run_migration()`.
- El pool se crea **lazy** en el primer `get_db_connection()`.

### Apagado del pool

> ⚠️ **No hay `atexit.register(close_db_pool)` ni hooks Flask de teardown**. El pool simplemente desaparece con el proceso. `close_db_pool()` existe pero solo se usa en tests.

### Manejo de `idle_in_transaction_session_timeout`

Postgres mata conexiones idle dentro de una transacción tras 15 min (forzado por nosotros vía `options='-c idle_in_transaction_session_timeout=900000'`).

**Patrón "conexión corta"**: cada handler abre, hace su trabajo, cierra.

**Patrón "autocommit para advisory locks"**: para crons que mantienen lock toda la ejecución, `lock_conn.autocommit = True` evita que la conn quede idle-in-transaction.

Casos donde se aplica:
- `manual_ai/services/cron_service.py:63`.
- `daily_quota_reset_cron.py:63`.

---

## 3. Esquema completo de la BD

### Tablas ya documentadas en otros manuales

Las listo aquí con un line each — el detalle está en su manual respectivo:

**Stripe / Billing** (ver `CLAUDE-stripe-cuotas-crons.md`):
- `users` — billing/cuotas (esquema completo en §3.1 más abajo).
- `stripe_webhook_events` — idempotencia webhooks.
- `stripe_webhook_alerts_sent` — rate-limit de alertas.
- `subscriptions` — opcional, histórico (en producción tiene 0 filas; la fuente canónica es `users` + Stripe API).

**Manual AI** (ver `CLAUDE-manual-ai.md`):
- `manual_ai_projects`, `manual_ai_keywords`, `manual_ai_results`, `manual_ai_snapshots`, `manual_ai_events`, `manual_ai_global_domains`.

**AI Mode** (ver `CLAUDE-ai-mode.md`):
- `ai_mode_projects`, `ai_mode_keywords`, `ai_mode_results`, `ai_mode_snapshots`, `ai_mode_events`, `ai_mode_global_domains`.

**LLM Monitoring** (ver `CLAUDE-llm-monitoring.md`):
- `llm_monitoring_projects`, `llm_monitoring_queries`, `llm_monitoring_results`, `llm_monitoring_snapshots`, `llm_model_registry`, `llm_model_changelog`, `user_llm_api_keys` (definida pero no usada).
- `llm_monitoring_analysis_lock` (singleton fila para lock global).
- `llm_monitoring_analysis_runs` (auditoría de runs — **lo que CLAUDE.md general llama "cron_runs"**, esa tabla NO existe).

### 3.1 `users` (esquema completo)

Definida en `database.py:275-288` + ALTERs incrementales:

**Base** (init_database):
```
id              SERIAL PK
google_id       TEXT UNIQUE
email           TEXT UNIQUE NOT NULL
name            TEXT NOT NULL
picture         TEXT
password_hash   TEXT
role            TEXT DEFAULT 'user'
is_active       BOOLEAN DEFAULT FALSE
created_at      TIMESTAMP
updated_at      TIMESTAMP
last_login_at   TIMESTAMP
```

**Billing** (`migrate_billing_phase1.py`):
```
stripe_customer_id      TEXT
plan                    VARCHAR(20) DEFAULT 'free'
billing_status          VARCHAR(20) DEFAULT 'active'
quota_limit             INTEGER DEFAULT 0
quota_used              INTEGER DEFAULT 0
quota_reset_date        TIMESTAMPTZ
subscription_id         VARCHAR(255)
current_period_start    TIMESTAMPTZ
current_period_end      TIMESTAMPTZ
current_plan            VARCHAR(20)
pending_plan            VARCHAR(20)
pending_plan_date       TIMESTAMPTZ
cancel_at_period_end    BOOLEAN
```

**Pausas por cuota** (`migrate_quota_pause_fields.py`):
```
ai_overview_paused_until    TIMESTAMPTZ
ai_overview_paused_at       TIMESTAMPTZ
ai_overview_paused_reason   TEXT
```

**Trial**:
```
trial_used              BOOLEAN DEFAULT FALSE
```

**Enterprise quota** (`migrate_enterprise_quotas.py`):
```
custom_quota_limit          INTEGER
custom_quota_notes          TEXT
custom_quota_assigned_by    VARCHAR(255)
custom_quota_assigned_date  TIMESTAMP
```

**LLM custom limits** (`migrate_llm_enterprise_support.py`):
```
custom_llm_prompts_limit        INTEGER
custom_llm_monthly_units_limit  INTEGER
```

**CHECK constraints**:
- `chk_plan` → `free | basic | premium | enterprise` (también se permite `business` tras migración).
- `chk_billing_status` → `active | past_due | canceled | beta`.
- `chk_current_plan`, `chk_pending_plan` (mismas listas).
- `chk_quota_limit/used >= 0`.

> El constraint de `plan` se reemplaza dinámicamente al añadir `enterprise` (`migrate_enterprise_quotas.py:65-72`) — patrón `DROP CONSTRAINT IF EXISTS` + `ADD CONSTRAINT`.

### 3.2 `oauth_connections`

`database.py:304-322`. Conexiones OAuth Google de cada usuario.

```
id                          SERIAL PK
user_id                     FK users(id) ON DELETE CASCADE
provider                    TEXT DEFAULT 'google'
google_account_id           TEXT
google_email                TEXT
access_token                TEXT
refresh_token_encrypted     TEXT NOT NULL  -- cifrado con Fernet si hay TOKEN_ENCRYPTION_KEY
token_uri                   TEXT
client_id                   TEXT
client_secret               TEXT
scopes                      TEXT[]
expires_at                  TIMESTAMPTZ
created_at, updated_at
UNIQUE (user_id, provider, google_account_id)
```

Helpers `_encrypt`/`_decrypt` en `database.py:513-533`. Si Fernet no está disponible o no hay clave → guarda en claro.

### 3.3 `gsc_properties`

`database.py:327-340`. Sites verificados en Google Search Console.

```
id                  SERIAL PK
user_id             FK users
connection_id       FK oauth_connections ON DELETE CASCADE
site_url            TEXT
permission_level    TEXT
verified            BOOLEAN
last_seen           TIMESTAMP
UNIQUE (user_id, site_url)
```

### 3.4 `password_reset_tokens`

`database.py:384-393`. Reset de contraseña.

```
id              SERIAL PK
user_id         FK users CASCADE
token           VARCHAR(255) UNIQUE
expires_at      TIMESTAMP
used_at         TIMESTAMP NULL
```

Helpers: `create_password_reset_token`, `validate_password_reset_token`, `use_password_reset_token`, `cleanup_expired_reset_tokens`.

### 3.5 `quota_usage_events`

`database.py:2325-2339`. Auditoría de consumo de cuota — detalle completo en `CLAUDE-quota-system.md`.

```
id              SERIAL PK
user_id         FK users CASCADE
ru_consumed     INTEGER DEFAULT 1
source          VARCHAR(50)        -- CHECK: 'ai_overview' | 'manual_ai' | 'serp_api'
keyword         VARCHAR(255)
country_code    VARCHAR(3)
timestamp       TIMESTAMPTZ DEFAULT NOW()
metadata        JSONB
CHECK (ru_consumed > 0)
CHECK (source IN ('ai_overview', 'manual_ai', 'serp_api'))
```

> ⚠️ **El CHECK `chk_source` está desactualizado**: no permite `'ai_mode'`, `'quota_reset'`, `'admin_quota_reset'`. El código lo gestiona con SAVEPOINT/try-except, pero significa que faltan eventos en la auditoría. Deuda conocida.
>
> ⚠️ **`chk_ru_consumed > 0`** impide insertar resets con `ru_consumed=0`. Mismo workaround.

### 3.6 `ai_overview_analysis`

`database.py:347-372`. Tabla histórica del AI Overview (no proyecto-based — anterior a Manual AI).

```
id, site_url, keyword, analysis_date
M1_clicks, M1_impressions, M1_ctr, M1_position
M2_clicks, M2_impressions, M2_ctr, M2_position
raw_data JSONB
user_id FK
```

Sigue usándose para `user_owns_site_url` pero la lógica principal del producto migró a `manual_ai_*`/`ai_mode_*`/`llm_monitoring_*`.

### 3.7 `admin_audit_log`

`database.py:472-481`. Auditoría de acciones admin.

```
admin_user_id   FK
action          TEXT
target_user_id  INTEGER
details         JSONB
created_at      TIMESTAMP
```

### 3.8 `project_collaborators` — tabla cross-módulo

`migrate_project_access_control.py:32-44`. **Crucial para el sistema de invitaciones / acceso compartido**.

```
id                      SERIAL PK
module_name             VARCHAR(32) CHECK ('llm_monitoring' | 'manual_ai' | 'ai_mode')
project_id              INTEGER
owner_user_id           FK users CASCADE
user_id                 FK users CASCADE
role                    VARCHAR(20) CHECK ('viewer')
invited_by_user_id      FK users SET NULL
UNIQUE (module_name, project_id, user_id)
```

Los 3 módulos (Manual AI / AI Mode / LLM Monitoring) consultan esta tabla para decidir si un user free puede ver un proyecto compartido.

### 3.9 `project_invitations`

`migrate_project_access_control.py:50-66`. Invitaciones pendientes (acceso compartido).

```
id                  SERIAL PK
module_name         VARCHAR(32)
project_id          INTEGER
token_hash          VARCHAR UNIQUE
invitee_email       TEXT
status              VARCHAR CHECK ('pending' | 'accepted' | 'revoked' | 'expired')
expires_at          TIMESTAMP
```

UNIQUE INDEX parcial: `(module_name, project_id, lower(invitee_email)) WHERE status='pending'` — permite reinvitar tras revocación.

### 3.10 Tablas legacy / no usadas

- **`llm_models`** — aparece en grep pero no se usa activamente; reemplazada por `llm_model_registry`.
- **`subscriptions`** — creada pero el backup de prod (oct-2025) la muestra con 0 filas. La fuente canónica de billing es `users` + Stripe API.
- **Campos legacy `competitor_domains`/`competitor_keywords`** en `llm_monitoring_projects` (deprecados, sustituidos por `selected_competitors` con estructura unificada).
- **`user_llm_api_keys`** — creada pero el modelo de negocio actual usa API keys globales del operador, no per-user.

---

## 4. Migraciones

### Sistema

- **No hay framework formal** (alembic/flyway). Cada migración es un script Python independiente, idempotente, con su propia función `main()` y `if __name__ == "__main__"`.
- **Patrón estándar**:
  - `ADD COLUMN IF NOT EXISTS`.
  - `CREATE TABLE IF NOT EXISTS`.
  - `CREATE INDEX IF NOT EXISTS`.
  - Para CHECK constraints que evolucionan: `DROP CONSTRAINT IF EXISTS` + `ADD CONSTRAINT`.
- Casi todos usan `from database import get_db_connection`. Algunos (e.g. `migrate_selected_competitors.py`, `migrate_roles_phase1b.py`, `migrate_llm_staging_to_production.py`) abren conexión directa con `psycopg2.connect(os.getenv('DATABASE_URL'))`.

### Cómo se ejecutan

**Manuales** (la mayoría):
```bash
railway run --service Clicandseo python3 migrate_xxx.py
```
No hay un release-step automático que las dispare en cada deploy.

**Automáticas en startup** vía `init_database.main()`:
- `init_database()` (idempotente, recrea schema base).
- `migrate_user_timestamps()`.
- `init_ai_overview_tables()`.
- `create_manual_ai_tables()`.
- `migrate_project_access_control.run_migration()`.

### Lista completa (40+ scripts en raíz)

**`migrate_*.py`** (migraciones puras):
- `migrate_add_error_fields.py`, `migrate_add_position_source.py`, `migrate_add_sources_field.py`, `migrate_add_trial_used.py`, `migrate_add_weighted_sov.py`, `migrate_add_weighted_sov_columns.py`.
- `migrate_admin_perf_indexes.py` — `CREATE INDEX CONCURRENTLY` (requiere `autocommit=True`).
- `migrate_billing_phase1.py`, `migrate_billing_simple.py`.
- `migrate_competitors_structure.py`, `migrate_enterprise_quotas.py`.
- `migrate_llm_add_country.py`, `migrate_llm_brand_fields.py`, `migrate_llm_enterprise_support.py`, `migrate_llm_execution_metadata.py`, `migrate_llm_model_discovery_v2.py`, `migrate_llm_prompt_limits.py`, `migrate_llm_queries_unique_constraint.py`, `migrate_llm_query_min_length.py`.
- `migrate_llm_staging_to_production.py` — copia datos staging → prod (no migración de schema).
- `migrate_manual_ai_quota_pause_fields.py`, `migrate_quota_pause_fields.py`.
- `migrate_project_access_control.py` (acceso compartido).
- `migrate_roles_phase1b.py`, `migrate_roles_simple.py`.
- `migrate_selected_competitors.py`.

**`add_*.py`** (ALTER TABLE simples):
- `add_competitors_fields.py`, `add_missing_columns_production.py`, `add_prompt_clusters_to_llm_monitoring.py`, `add_selected_competitors_to_ai_mode.py`, `add_topic_clusters_field.py`, `add_topic_clusters_to_ai_mode.py`, `add_updated_at_field.py`.

**`create_*.py`** (creación de tablas en bloque):
- `create_ai_mode_tables.py`, `create_ai_mode_tables_production.py`, `create_ai_table.py`, `create_global_domains_table.py`, `create_llm_monitoring_tables.py`, `create_manual_ai_tables.py`.

**Bootstrap**: `init_database.py`.

**SQL puros** (`*.sql`):
- `migrate_to_gemini_flash.sql` — switch de modelo Google a Gemini 3 Flash (BEGIN/COMMIT explícitos).
- `update_llm_models.sql` — actualiza modelos (GPT-5/Gemini 3/Claude Sonnet 4.5/Sonar) — Diciembre 2025.
- `update_llm_models_freetier_may2026.sql` — modelos free-tier (mayo 2026).
- `update_llm_pricing_2026.sql` — pricing en `llm_model_registry` (febrero 2026).
- `production_backup_20251019_230248.sql` — backup puntual (no es script ejecutable).

---

## 5. Patrones transversales

### 5.1 Pool wrapper `_PooledConnection`

Patrón estándar en todo el código:

```python
conn = get_db_connection()
if not conn:
    return ...  # fail-soft
try:
    cur = conn.cursor()
    cur.execute(...)
    conn.commit()
finally:
    if conn:
        conn.close()  # devuelve al pool, NO destruye
```

### 5.2 `with` context manager (alternativa)

```python
with get_db_connection() as conn:
    cur = conn.cursor()
    cur.execute(...)
    conn.commit()
```

`__exit__` hace rollback si hubo excepción y siempre devuelve al pool. Patrón secundario, menos usado que el `try/finally` explícito.

### 5.3 SAVEPOINT para recuperación parcial

Permite que un fallo en una operación no aborte toda la transacción.

**Usos reales:**

- `database.py:2538-2555` (`resume_quota_pauses_for_user`):
  ```python
  cur.execute("SAVEPOINT before_manual_ai_resume")
  try:
      cur.execute("UPDATE manual_ai_projects SET is_paused_by_quota = FALSE...")
      cur.execute("RELEASE SAVEPOINT before_manual_ai_resume")
  except Exception as e:
      cur.execute("ROLLBACK TO SAVEPOINT before_manual_ai_resume")
      logger.warning(...)
  ```
- `database.py:1252-1300` (`delete_user`): helper `safe_delete()` envuelve cada DELETE en su propio SAVEPOINT.
- `admin_billing_panel.py:1199-1227`: SAVEPOINT alrededor de `INSERT INTO quota_usage_events` para tolerar el fallo del CHECK constraint.

### 5.4 Advisory locks (`pg_try_advisory_lock`)

**Class IDs canónicos:**

| Module | Class ID | Lock object_id |
|---|---:|---|
| Manual AI cron | `4242` | `int(date.today().strftime('%Y%m%d'))` |
| AI Mode cron | `4243` | idem |
| LLM Monitoring | — | usa `llm_monitoring_analysis_lock` (tabla, no advisory) |

**Patrón típico:**

```python
lock_conn = get_db_connection()
lock_conn.autocommit = True  # CRÍTICO: ver §5.5
lock_cur = lock_conn.cursor()
lock_cur.execute(
    "SELECT pg_try_advisory_lock(%s, %s)",
    (CRON_LOCK_CLASS_ID, today_yyyymmdd)
)
acquired = lock_cur.fetchone()[0]
if not acquired:
    return  # otro run en curso
try:
    # ... procesar ...
finally:
    lock_cur.execute(
        "SELECT pg_advisory_unlock(%s, %s)",
        (CRON_LOCK_CLASS_ID, today_yyyymmdd)
    )
    lock_conn.close()
```

### 5.5 `autocommit=True` para advisory locks

**Crítico**: `lock_conn.autocommit = True` antes de adquirir el lock para que la conn no quede idle-in-transaction y Postgres la mate a los 15 min, liberando la advisory lock y permitiendo que otro cron arranque en paralelo.

Solo se usa en 3 sitios:
- `manual_ai/services/cron_service.py:63` (advisory lock).
- `daily_quota_reset_cron.py:63` (advisory lock).
- `migrate_admin_perf_indexes.py:44` — para `CREATE INDEX CONCURRENTLY` (no se puede dentro de transacción).

### 5.6 Idempotencia con `INSERT ... ON CONFLICT`

| Tabla | Patrón | Uso |
|---|---|---|
| `stripe_webhook_events` | `ON CONFLICT (event_id) DO NOTHING RETURNING event_id` | Si `RETURNING` no devuelve nada, el evento ya estaba. |
| `gsc_properties` | `ON CONFLICT (user_id, site_url) DO UPDATE SET ...` | Upsert. |
| `llm_model_registry` | `ON CONFLICT (llm_provider, model_id) DO UPDATE` | Upsert. |
| `llm_monitoring_analysis_lock` | `ON CONFLICT (id) DO NOTHING` | Asegurar fila singleton. |
| `llm_monitoring_queries` | `ON CONFLICT (project_id, query_text) DO NOTHING` | Evita duplicados. |
| `manual_ai_results` / `ai_mode_results` / `llm_monitoring_results` | UNIQUE `(project_id, ..., analysis_date)` + `INSERT ... ON CONFLICT DO UPDATE` | Idempotencia diaria. |

### 5.7 Conexiones cortas vs largas

- **Cortas** (patrón normal): abrir → trabajo → cerrar. Idiom en >100 sitios.
- **Largas con autocommit**: solo para advisory locks (sesión Postgres dura todo el cron pero no transacción).
- **Patrón "una conn por usuario"** en `daily_quota_reset_cron.py`: en lugar de una transacción gigante para todos los usuarios, listar usuarios en una conn corta, cerrar, y procesar cada uno en su propia conexión. Evita self-deadlock + transacciones zombie + permite progreso parcial si el proceso muere.

### 5.8 UNIQUE constraints estratégicas

Garantizan idempotencia por contenido:

- `users.email`, `users.google_id`.
- `oauth_connections (user_id, provider, google_account_id)`.
- `gsc_properties (user_id, site_url)`.
- `project_collaborators (module_name, project_id, user_id)`.
- `password_reset_tokens.token`.
- UNIQUE INDEX parcial: `project_invitations` solo `WHERE status='pending'` — permite reinvitar tras revocación.

---

## 6. Helpers más importantes en `database.py`

Todas en `/Users/carlosgonzalez/Desktop/app/APP-WEB-GSC-AI/search_console_webapp/database.py`:

### Pool & init
- `get_db_connection()` (178) — entrega un `_PooledConnection` con retry-backoff.
- `close_db_pool()` (248) — cierra el pool global.
- `init_database()` (265) — crea tablas base + migración Gemini 3 Flash.

### Cifrado (opcional)
- `_get_fernet/_encrypt/_decrypt` (500-533) — cifrado de tokens OAuth.

### OAuth
- `create_or_update_oauth_connection`, `get_oauth_connections_for_user`, `get_oauth_connection_by_id`, `update_oauth_connection_tokens`.

### GSC
- `upsert_gsc_properties_for_connection`, `list_gsc_properties_for_user`, `get_connection_for_site`, `user_owns_site_url`.

### Password reset
- `create_password_reset_token`, `validate_password_reset_token`, `use_password_reset_token`, `cleanup_expired_reset_tokens`.

### Hashing
- `hash_password` (PBKDF2-SHA256, 100k iters, salt:hash hex).
- `verify_password`.

### Users CRUD
`create_user`, `get_user_by_email`, `get_user_by_google_id`, `get_user_by_id`, `update_user_activity`, `get_all_users`, `update_user_role`, `authenticate_user`, `delete_user` (con SAVEPOINTs por tabla), `get_user_stats`, `change_password`, `admin_reset_password`, `update_user_profile`, `get_user_activity_log`, `get_detailed_user_stats`, `migrate_user_timestamps`, `ensure_sample_data`.

### AI Overview (legacy)
`init_ai_overview_tables`, `save_ai_overview_analysis`, `get_ai_overview_stats`, `get_ai_overview_history`.

### Quota
- `track_quota_consumption` (línea 2098) — INSERT evento + UPDATE `users.quota_used`. Reintentos para deadlock/serialization.
- `get_user_quota_usage` (consulta).
- `get_user_llm_monthly_cost`.
- `ensure_quota_table_exists`.

### Pausas por cuota cross-module
- `pause_ai_overview_for_quota` (2371) — UPDATE `users.ai_overview_paused_*`.
- `pause_ai_mode_projects_for_quota` (2398).
- `pause_llm_projects_for_quota` (2427).
- `pause_manual_ai_projects_for_quota` (2456).
- **`resume_quota_pauses_for_user`** (2485-2572) — limpia las 4 tablas en una transacción, con SAVEPOINT alrededor de `manual_ai_projects` por compat con deployments antiguos.

### Analysis lock (LLM Monitoring)
- `acquire_analysis_lock` (2579) — lock fila-singleton con `FOR UPDATE`, stale recovery > 30 min.
- `release_analysis_lock` (libera + actualiza run + dispara `cron_alerts.check_and_send_cron_alerts`).
- `get_latest_analysis_run`.

---

## 7. Variables de entorno

| Variable | Default | Uso |
|---|---|---|
| `DATABASE_URL` | (oblig.) | URL completa de Postgres. `database.py:31-33` lanza `RuntimeError` si falta. |
| `DB_POOL_MIN` | `2` | Mínimo de conexiones en `ThreadedConnectionPool`. |
| `DB_POOL_MAX` | `20` | Máximo. |
| `DB_POOL_WAIT_SECONDS` | `10.0` | Tiempo de espera para `getconn()` ante pool exhaustion. |
| `DB_POOL_DISABLED` | `false` | `true` → bypass del pool, conn directa (escape hatch). |
| `DB_RETRY_ATTEMPTS` | `3` | Reintentos en `track_quota_consumption` ante deadlock/serialization. |
| `DB_RETRY_BACKOFF_SECONDS` | `0.5` | Backoff inicial (exponencial). |
| `TOKEN_ENCRYPTION_KEY` | (opc.) | Clave Fernet para `oauth_connections.refresh_token_encrypted`. Sin clave → almacenamiento en claro. |
| `RAILWAY_ENVIRONMENT` | (Railway) | `production` | `staging` | otro. |

> ⚠️ La doc histórica (CLAUDE.md general original) decía `DB_POOL_MIN=1` y `DB_POOL_MAX=8`. **El código actual usa `2/20`** — la doc estaba obsoleta.

---

## 8. Operaciones administrativas

### Conexión a producción

- **Vía Railway dashboard**: `psql` integrado o copia/pega de `DATABASE_URL`.
- **Vía Railway CLI**:
  ```bash
  railway connect Postgres
  ```
- **Manualmente**:
  ```bash
  psql "$DATABASE_URL"
  ```

URLs (con credenciales) hardcodeadas en `migrate_llm_staging_to_production.py:11-12` (deuda — debería usar env vars).

### Backups

- **Manual**: `pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql`.
- **No hay script automático** en el repo.
- Existe `production_backup_20251019_230248.sql` como ejemplo de un backup puntual de oct-2025.
- **No hay scheduled backups en Railway** verificados — confirmar con Railway dashboard.

### Restore

```bash
psql "$DATABASE_URL" < production_backup_20251019_230248.sql
```

### Migración en caliente (zero downtime)

Patrón:
1. `ADD COLUMN IF NOT EXISTS` con `DEFAULT NULL` o valor seguro.
2. Backfill posterior si hace falta (en otro script).
3. Para `CREATE INDEX` en tablas grandes: `CONCURRENTLY` con `autocommit=True` (`migrate_admin_perf_indexes.py:44`).

`migrate_llm_execution_metadata.py:20` lo documenta como zero-downtime.

### Auditoría manual

| Script | Para qué |
|---|---|
| `audit_manual_ai_system.py` | Estado de Manual AI. |
| `check_billing_migration.py` | Estado migración billing. |
| `check_llm_models_config.py` | Modelos LLM activos. |
| `check_llm_project_config.py` | Config de un proyecto LLM. |
| `check_llm_tables.py` | Tablas LLM. |
| `check_manual_ai_system.py` | Sistema Manual AI. |
| `check_production_ready.py` | Pre-deploy check. |
| `check_projects_confusion.py` | Conflictos cross-módulo. |
| `check_setup.py` | Setup general. |
| `check_staging_config.py` | Diff staging vs prod. |
| `check_environment_vars.py` | Env vars críticas. |
| `webhook_diagnostics.py` | Inspeccionar webhooks recibidos. |
| `diagnose_cron_skip.py` | Por qué un cron saltó algún proyecto. |
| `find_user_by_id.py` | Buscar usuario. |
| `diagnostic_endpoint.py` | HTTP `/diagnostic/imports`. |

---

## 9. Errores históricos y deuda técnica

### Bugs históricos resueltos

#### Self-deadlock en `resume_quota_pauses_for_user` (2026-04-08)

**Causa**: una conn tomaba row-lock en `users.id=X`, llamaba a la función que abría OTRA conn con UPDATE sobre la misma fila → deadlock infinito.

**Fix**: COMMIT antes de llamar; patrón "commit-por-usuario" en el cron. Documentado en `admin_billing_panel.py:1229-1234` y `daily_quota_reset_cron.py:31-34`.

#### Pool exhaustion bajo carga (2026-05-05)

**Causa**: muchos análisis paralelos + crons + tráfico web saturaban Postgres.

**Fix**: `ThreadedConnectionPool` + wrapper `_PooledConnection`. Comentario completo en `database.py:43-59`.

#### `idle_in_transaction_session_timeout` matando conexiones de cron (2026-04-08)

**Causa**: conn que mantenía advisory lock quedaba idle in transaction → Postgres la mataba a los 15min → lock liberado → otro cron arrancaba en paralelo.

**Fix**: `lock_conn.autocommit = True` (`daily_quota_reset_cron.py:56-63` documenta el caso). El timeout de 15 min está forzado por nosotros vía `options='-c idle_in_transaction_session_timeout=900000'`.

#### Webhooks duplicados procesados dos veces (2026-05-07)

**Causa**: Stripe reenvía webhooks. Sin idempotencia, `payment_succeeded` podía resetear cuota dos veces.

**Fix**: tabla `stripe_webhook_events` + `_claim_webhook_event` con `INSERT ... ON CONFLICT DO NOTHING RETURNING` (`stripe_webhooks.py:142-179`).

#### CHECK constraint roto al insertar quota_usage_events de reset admin

**Causa**: `chk_source` solo aceptaba `ai_overview|manual_ai|serp_api`. Si admin reseteaba con `'admin_quota_reset'` la transacción entera abortaba.

**Fix**: SAVEPOINT alrededor del INSERT (`admin_billing_panel.py:1199-1227`).

#### Manual AI quota-resume rompía en deployments antiguos sin columna

**Causa**: `is_paused_by_quota` no existía en bases legacy.

**Fix**: SAVEPOINT antes del UPDATE en `resume_quota_pauses_for_user` (`database.py:2538-2555`).

#### `current_period_end IS NULL` por extracción incorrecta

Ver `CLAUDE-stripe-cuotas-crons.md` §12. Motivó el cron Stripe-aware con live-check API.

### Deuda técnica conocida

| Deuda | Impacto | Riesgo |
|---|---|---|
| **CHECK `chk_source` desactualizado** (no permite `ai_mode`, `quota_reset`, etc.) | Eventos de auditoría perdidos. | Medio. |
| **CHECK `chk_ru_consumed > 0`** impide insertar resets como `0`. | Workaround con SAVEPOINT. | Bajo. |
| **No hay `atexit.register(close_db_pool)`** | Conexiones zombies si proceso muere mal. | Bajo. |
| **URLs con credenciales hardcodeadas** en `migrate_llm_staging_to_production.py` y otros | Riesgo si repo se hace público. | Alto. |
| **Sin migraciones formales** (alembic) | Orden de migraciones no se garantiza. | Medio. |
| **Sin backup automático** verificado | Pérdida de datos en caso catástrofe. | Alto. |
| **Tabla `cron_runs` mencionada en docs no existe** | Confusión. La real es `llm_monitoring_analysis_runs`. | Trivial (solo doc). |
| **`subscriptions`, `user_llm_api_keys`, `llm_models`** definidas pero no usadas | Código muerto. | Trivial. |

### Documentos `.md` históricos relacionados con BD

- `OPTIMIZACION_CRON_DIARIO.md` — fixes del pool y el cron LLM.
- `IMPLEMENTACION_RETRY_SYSTEM.md` — retry para deadlocks.
- `MEJORAS_LLM_MONITORING.md` — cambios de schema.
- `FIX_DISCREPANCIA_MENCIONES_LLM.md` — query de menciones.

---

## 10. Tests

### Tests específicos de BD

| Archivo | Qué cubre |
|---|---|
| `test_db_pool.py` | **Suite explícita del pool**. 12 tests: init con minconn/maxconn, get/use/close, reuso de conn física entre ciclos, RealDictCursor preservado, context manager con rollback, **50 threads concurrentes**, `DB_POOL_DISABLED=true` bypass, patrón legacy try/finally, `close()` doble es harmless. |
| `test_webhook_hardening.py` | Idempotencia de `stripe_webhook_events`, extracción robusta del periodo, **patrón SAVEPOINT** en `resume_quota_pauses_for_user` (verifica que el código fuente contiene `SAVEPOINT before_manual_ai_resume`). |
| `test_stripe_aware_reset.py` | Filtro Stripe-aware en cron de cuotas. |

### Tests adicionales que tocan BD

- `test_cron_alerts.py` — alertas leyendo `llm_monitoring_analysis_runs`.
- `test_cron_routes.py` — endpoints `/api/cron/*`.
- `test_llm_cron_jobs.py`, `test_project_parallelism.py`, `test_project_timeout.py` — cron LLM.
- `test_ai_mode_system.py`, `test_locale_fidelity.py`, `test_llm_monitoring_*`, `test_all_llm_providers.py`.

### Lo que NO está cubierto

- **No hay test de migraciones**. La idempotencia se prueba implícitamente al ejecutar el script dos veces sin errores.
- **No hay test de schema** que valide que el esquema actual coincide con lo que espera el código.

---

## TL;DR

1. **PostgreSQL + psycopg2 + pool transparente.** No ORM. Todo SQL plano.
2. **`_PooledConnection` intercepta `.close()`** y la redirige al pool. Idempotente.
3. **Defaults reales del pool: `2/20`** (no `1/8` como decía la doc histórica).
4. **`autocommit=True` solo para advisory locks** (cron Manual AI clase `4242`, AI Mode `4243`, LLM usa tabla singleton).
5. **SAVEPOINT** para tolerar fallos parciales (especialmente en `resume_quota_pauses_for_user` por compat con deployments antiguos).
6. **`INSERT ... ON CONFLICT DO NOTHING/UPDATE RETURNING`** = patrón estándar de idempotencia.
7. **Sin migraciones formales**: scripts Python idempotentes manuales. Algunos automáticos en `init_database.main()`.
8. **`cron_runs` no existe** — la tabla real es `llm_monitoring_analysis_runs`.
9. **Deuda principal**: `chk_source` desactualizado en `quota_usage_events`, credenciales hardcodeadas en scripts puntuales, sin backup automático verificado.

— Fin del manual —
