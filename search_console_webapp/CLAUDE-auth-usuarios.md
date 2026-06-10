# CLAUDE-auth-usuarios.md — Autenticación y Usuarios

> Manual del sistema de **autenticación, sesiones, roles y acceso compartido**: OAuth Google + email/password + `project_collaborators` + admin panel.
>
> Última actualización: 2026-05-08.
>
> Manuales relacionados: `CLAUDE-base-de-datos.md` (esquema de `users`, `oauth_connections`, `project_collaborators`), `CLAUDE-emails-alertas.md` (welcome, password reset, invitaciones). Índice maestro: `CLAUDE-INDEX.md`.

---

## Índice

1. [Visión general en 5 minutos](#1-visión-general-en-5-minutos)
2. [Mapa de archivos](#2-mapa-de-archivos)
3. [OAuth Google](#3-oauth-google)
4. [Password local](#4-password-local)
5. [Sesiones Flask](#5-sesiones-flask)
6. [Decoradores de autenticación](#6-decoradores-de-autenticación)
7. [Roles](#7-roles)
8. [Acceso compartido (`project_collaborators`)](#8-acceso-compartido-project_collaborators)
9. [Cifrado de tokens (Fernet)](#9-cifrado-de-tokens-fernet)
10. [Endpoints relacionados con auth](#10-endpoints-relacionados-con-auth)
11. [Variables de entorno](#11-variables-de-entorno)
12. [Operaciones administrativas](#12-operaciones-administrativas)
13. [Errores históricos y deuda técnica](#13-errores-históricos-y-deuda-técnica)
14. [Tests](#14-tests)

---

## 1. Visión general en 5 minutos

**Tres métodos de auth conviven:**

1. **Google OAuth 2.0** — login y signup. Pide scopes de Google Search Console + email/profile.
2. **Email + password local** — alternativa. Hashing PBKDF2-SHA256 (100k iteraciones, salt 32 bytes hex).
3. **Cron Bearer token** — solo para endpoints `/api/cron/*`. No es "auth de usuario" pero coexiste vía decorador `cron_or_auth_required`.

**No hay JWT.** Sesión Flask clásica con cookie firmada (`itsdangerous`). Toda la información persistente vive en `users` + tablas asociadas (`oauth_connections`, `gsc_properties`, `password_reset_tokens`).

**Roles** (`users.role`): solo dos tras la migración Fase 1B → `'user'` y `'admin'`. Antes existía `'AI User'`, eliminado. Ahora "puede usar AI" depende del **plan de pago**, no del rol.

**Acceso compartido**: el dueño de un proyecto puede invitar a otro usuario como `viewer` (read-only). Implementado con dos tablas (`project_collaborators`, `project_invitations`) y servicio `services/project_access_service.py`.

**Reglas de oro:**

1. **Plan y rol son dimensiones independientes.** El rol decide acceso a admin; el plan decide acceso a features.
2. **Solo el `refresh_token` se cifra** con Fernet en `oauth_connections.refresh_token_encrypted`. El `access_token` está en claro (corta vida).
3. **Toda fila de `users` es soft-checkable** con `is_active` (NULL legacy se trata como TRUE).
4. **OAuth callback** distingue entre 3 acciones: `login`, `signup`, `link` (multi-cuenta Google).
5. **`OAUTHLIB_INSECURE_TRANSPORT`** se setea solo en local (sin Railway). En producción hay ProxyFix para que `request.url` reciba HTTPS desde el proxy.

---

## 2. Mapa de archivos

### Núcleo

| Archivo | Líneas | Qué contiene |
|---|---:|---|
| `auth.py` | 2397 | **Archivo principal**. Decoradores, OAuth flow, rutas `/login`, `/signup`, `/auth/*`, panel admin, perfil. |
| `database.py` | 2742 | Funciones de BD: `create_user`, `authenticate_user`, `hash_password`, `verify_password`, `delete_user`, OAuth connections, password reset tokens, Fernet encrypt/decrypt. |
| `app.py` | 3968 | Wiring de Flask: `secret_key`, cookies, ProxyFix, registro de blueprints, hooks `before_request`, ruta `/project-invitations/accept`. |

### Acceso compartido (sharing)

| Archivo | Qué contiene |
|---|---|
| `services/project_access_service.py` (897 líneas) | **Servicio completo** de invitaciones y colaboradores. |
| `project_access_routes.py` | Blueprint `project_access_bp` con prefijo `/api/project-access`. |
| `migrate_project_access_control.py` | Migración de las dos tablas. |
| `manual_ai/utils/validators.py`, `ai_mode_projects/utils/validators.py` | Validan acceso por plan + acceso compartido. |

### Migraciones de roles

| Archivo | Qué hace |
|---|---|
| `migrate_roles_phase1b.py` | Migración formal `AI User` → `user`, añade CHECK `chk_user_role IN ('user','admin')`. |
| `migrate_roles_simple.py` | Versión rápida del mismo cambio (también asigna planes beta). |
| `verificacion_completa_fase1b.py` | Script de verificación post-migración. |

### Admin

| Archivo | Qué contiene |
|---|---|
| `admin_billing_panel.py` | `log_admin_action`, `get_users_with_billing`, `update_user_plan_manual`, `assign_custom_quota`, `remove_custom_quota`, `reset_user_quota_manual`, `get_user_billing_details`. |
| `admin_billing_routes.py` | Rutas adicionales del admin (dashboard de billing). |

### Diagnóstico/utilidades

`oauth_diagnostic.py`, `debug_oauth_flow.py`, `find_user_by_id.py`, `simple_user_diagnosis.py`, `check_environment_vars.py`, `check_production_ready.py`, `check_staging_config.py`, `check_setup.py`.

### Templates Jinja2 (todas en `/templates/`)

| Plantilla | Para qué |
|---|---|
| `login.html` | Login (Google OAuth + email/password + reCAPTCHA). |
| `signup.html` | Registro nuevo usuario. |
| `forgot_password.html` | Solicitar reset. |
| `reset_password.html` | Establecer nueva contraseña. |
| `user_profile.html` | Perfil del usuario. |
| `admin_simple.html` | Panel admin general. |
| `admin_billing.html` | Panel admin específico de billing. |
| `project_access.html` | UI compartir/invitar a proyectos. |
| `landing.html`, `dashboard.html`, `mobile_error.html` | Otras páginas. |

### Tests

> ⚠️ **No existen tests dedicados a auth** (`test_auth_*.py` no existe). Solo scripts de diagnóstico CLI sin asserts. Es un gap notable.

---

## 3. OAuth Google

### Flujo paso a paso

1. Usuario hace click en "Continuar con Google". JS redirige a `/auth/login` o `/auth/signup`.
2. Endpoint llama `create_flow()` (`auth.py:130-163`):
   - Lee `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` de env. Fallback a `client_secret.json` si existe.
   - `Flow.from_client_config(...)` con `redirect_uri = GOOGLE_REDIRECT_URI`.
3. Genera `state = secrets.token_urlsafe(32)`, lo guarda en `session['state']`. Marca `session['oauth_action'] = 'login' | 'signup' | 'link'`.
4. Redirige a `flow.authorization_url(access_type='offline', include_granted_scopes='true', state=...)`. Para signup y `start_google_link` se añade `prompt='consent'`.
5. Google redirige a `/auth/callback` (`auth.py:1109`).
6. Verifica `state`, extrae `code`, llama `flow.fetch_token(authorization_response=request.url)`.
7. Guarda credenciales temporalmente en `session['temp_credentials']`.
8. Pide info de usuario vía `oauth2 v2 userinfo`.
9. Según `oauth_action`:
   - **signup**: si email no existe, `create_user(...)` con `auto_activate=True`, manda welcome email (Brevo), upsert contacto en lista "Usuarios Registrados", auto-login. Si plan en sesión, redirige a checkout.
   - **login**: si usuario existe y activo → mueve `temp_credentials` a `session['credentials']`, llena `session['user_id']`, vincula `google_id` si faltaba, persiste conexión vía `create_or_update_oauth_connection`. Si no existe → redirige a `/login?auth_error=user_not_registered`.
   - **link**: usuario ya autenticado añade otra cuenta de Google (multi-GSC). Persiste vía `create_or_update_oauth_connection` y sincroniza `gsc_properties` llamando `sites().list()`.

### Scopes (`auth.py:117-121`)

```
https://www.googleapis.com/auth/webmasters.readonly
https://www.googleapis.com/auth/userinfo.email
https://www.googleapis.com/auth/userinfo.profile
```

### Almacenamiento de tokens

- **Sesión Flask**: `session['credentials']` (dict serializable) durante la sesión activa.
- **BD persistente** (`oauth_connections`): `access_token` plano, **`refresh_token_encrypted` con Fernet** (cifrado AES-128 + HMAC).
- Función `create_or_update_oauth_connection(user_id, google_account_id, google_email, creds)` en `database.py:539`. Cifra refresh token con `_encrypt`.

### Refresh

- **En sesión activa**: `refresh_credentials_if_needed(credentials)` (`auth.py:516`) reescribe `session['credentials']`.
- **Para conexiones persistidas**: `get_authenticated_service_for_connection(connection, ...)` (`auth.py:2363`). Descifra refresh token, refresca si expirado, persiste tokens nuevos vía `update_oauth_connection_tokens`.

### Si falla

- `temp_credentials` se descartan, `oauth_action` se borra.
- Logs detallados (`logger.error` con traceback).
- Redirect a `/login?auth_error=callback_failed`.

### `OAUTHLIB_INSECURE_TRANSPORT`

- Se setea solo si **no** estamos en Railway (`RAILWAY_ENVIRONMENT` vacío) — `auth.py:72-73` y `app.py:23-24`. Permite HTTP localhost solo en dev.
- En producción/staging Railway, **no se setea**. Se usa **ProxyFix** (`app.py:124-130`) para que `request.url` reciba `https` desde `X-Forwarded-Proto`. Sin esto, OAuth rompe con `InsecureTransportError`.
- También se fija siempre `OAUTHLIB_RELAX_TOKEN_SCOPE = '1'` para evitar errores cuando Google reordena scopes.

---

## 4. Password local

### Hashing — `database.py:976-992`

```python
def hash_password(password):
    salt = secrets.token_hex(32)             # 32 bytes hex = 64 chars
    h = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return salt + h.hex()                    # almacenamiento: salt|hash juntos

def verify_password(password, stored_hash):
    salt = stored_hash[:64]
    stored = stored_hash[64:]
    h = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return h.hex() == stored
```

**PBKDF2-HMAC-SHA256, 100.000 iteraciones**, salt único por contraseña embebido en el propio campo.

### Endpoints

| Endpoint | Método | Auth | Función |
|---|---|---|---|
| `/auth/email/signup` | POST | público | Verifica reCAPTCHA, crea usuario, manda welcome email, sincroniza con Brevo, auto-login. |
| `/auth/email/login` | POST | público | Verifica reCAPTCHA, llama `authenticate_user`, inicia sesión, actualiza `last_login_at`. |
| `/profile/change-password` | POST | `@auth_required` | Verifica contraseña actual + valida nueva password ≥ 8 chars. |

### Password reset (tabla `password_reset_tokens`)

Flujo:

1. `/forgot-password` (GET) → renderiza form.
2. `/auth/forgot-password` (POST) → `auth.py:638`. `create_password_reset_token(user_id)` (`database.py:830`):
   - Invalida tokens previos.
   - Genera `secrets.token_urlsafe(32)`.
   - Expira en **1 hora**.
3. Construye URL `request.url_root + reset-password?token=...`. Envía vía Brevo API (prioritario) o SMTP (fallback).
4. **Por seguridad siempre devuelve el mismo mensaje** independientemente de si el email existe o no.
5. `/reset-password?token=...` (GET) → renderiza form si token válido.
6. `/auth/reset-password` (POST) → `use_password_reset_token(token, new_password)`. Verifica token, hashea nueva pass, marca `used_at = NOW()`.
7. `cleanup_expired_reset_tokens()` borra tokens expirados ≥ 1 día.

> ⚠️ `cleanup_expired_reset_tokens` **no se llama desde un cron** automáticamente. Verificar.

### reCAPTCHA v3

- `verify_recaptcha(token, action)` — `auth.py:78`.
- Vars: `RECAPTCHA_SITE_KEY` (cliente), `RECAPTCHA_SECRET_KEY` (servidor), `RECAPTCHA_MIN_SCORE` (default `0.5`).
- Si `RECAPTCHA_SECRET_KEY` está vacío → permite siempre (logger.warning) — **fail-open**.
- Verifica `success`, action match, score ≥ min_score.
- **Aplicado en**: signup local + login local. **NO en**: forgot password, reset password, OAuth callback.

---

## 5. Sesiones Flask

### Configuración

```python
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here-change-in-production')
# ⚠️ default inseguro en código — debería rotarse en cada deploy
```

Cookies (`app.py:115-117`):
- `SESSION_COOKIE_SECURE = is_production or is_staging` (HTTPS only fuera de dev).
- `SESSION_COOKIE_HTTPONLY = True`.
- `SESSION_COOKIE_SAMESITE = 'Lax'`.
- `PREFERRED_URL_SCHEME = 'https'` en prod/staging.

### Datos guardados en session

| Clave | Para qué |
|---|---|
| `user_id`, `user_email`, `user_name` | Identidad del usuario. |
| `last_activity` | Timestamp ISO para timeout. |
| `state` | CSRF para OAuth. |
| `oauth_action` | `'login'` / `'signup'` / `'link'`. |
| `temp_credentials` | Credenciales OAuth durante el callback. |
| `credentials` | Credenciales OAuth en sesión activa. |
| `auth_next` | URL post-login (preserva flujos de invitación/checkout). |
| `signup_plan`, `signup_source`, `signup_interval`, `signup_tracking` | Flow de signup → checkout. |

### Timeout por inactividad

- `SESSION_TIMEOUT_MINUTES` (default 45).
- `SESSION_WARNING_MINUTES` (default 5).
- `update_last_activity()` en cada request autenticado.
- `is_session_expired()` compara `last_activity` con `timedelta(minutes=SESSION_TIMEOUT_MINUTES)`.
- `get_session_time_remaining()` retorna segundos restantes.
- Endpoint `/auth/keepalive` (POST) renueva sin actualizar (decorador `auth_required_no_activity_update`).
- Endpoint `/auth/status` consulta sin side-effects.

---

## 6. Decoradores de autenticación

Todos en `auth.py`:

| Decorador | Línea | Qué hace |
|---|---:|---|
| `auth_required(f)` | 230 | Authenticated + session not expired + user exists in DB + `is_active=True`. Llama `update_last_activity()`. Devuelve 401 JSON o redirect a `/login?...` según `Content-Type`. |
| `login_required` | 399 | Alias de `auth_required` (compatibilidad). |
| `cron_or_auth_required(f)` | 284 | Si header `Authorization: Bearer <CRON_TOKEN>` válido (`secrets.compare_digest`), pasa. Si no, fallback a `auth_required`. |
| `admin_required(f)` | 306 | Igual que `auth_required` + chequea `user['role'] == 'admin'`. Devuelve 403 si no admin. |
| `ai_user_required(f)` | 353 | **Deprecated** (rol AI eliminado). Solo loggea warning y aplica auth normal. |
| `auth_required_no_activity_update(f)` | 403 | Como `auth_required` pero NO actualiza `last_activity`. Para `/auth/keepalive`, `/auth/status`. |

### Hooks `before_request` adicionales

- **`enforce_llm_access`** (`llm_monitoring_routes.py:101`). Aplica al blueprint `llm_monitoring_bp`. Bloquea si `can_access_llm_monitoring(user)` es falso, **excepto** si el usuario tiene acceso compartido vía `user_has_any_module_access(user_id, 'llm_monitoring')`. Devuelve 402 con `{error:'paywall', upgrade_options}`.
- **`validate_project_ownership`** (`llm_monitoring_routes.py:128`). Owner puede todo. Colaborador `viewer` solo GET.
- **`_block_mobile_globally_except_login_signup`** (`app.py:190`). Bloquea móviles excepto `/static`, `/webhooks`, `/login`, `/signup`, `/auth/*`, `/mobile-not-supported`.

### Otros gates

- `_ensure_cron_token_or_admin()` (`llm_monitoring_routes.py:178`) — endpoints sensibles de cron exigen CRON_TOKEN o admin.

---

## 7. Roles

### Valores actuales (`users.role`)

- `'user'` (default).
- `'admin'`.
- Constraint `chk_user_role CHECK (role IN ('user','admin'))` añadido por `migrate_roles_phase1b.py`.
- **Histórico**: existía `'AI User'` que daba permisos AI sin pagar — **eliminado**.

### Cómo asignar admin

- **No hay UI de "promover a admin"**. Se hace por SQL directo o vía endpoint `/admin/users/<id>/update-role` (POST `{role:'admin'}`), que solo puede llamar otro admin.
- En `auth.py:1849-1887` el handler valida que `new_role in ['user','admin']`.
- `update_user_role(user_id, role)` (`database.py:1198`).

### Qué puede hacer un admin

Endpoints decorados `@admin_required`:

- `/admin/users` — listado paginado.
- `/admin/users/<id>/billing-details` — detalle billing.
- `/admin/users/<id>/toggle-status` — activar/desactivar.
- `/admin/users/<id>/update-role` — cambiar rol.
- `/admin/users/<id>/reset-password` — restablecer pass de otro usuario.
- `/admin/users/<id>/delete` — borrar usuario (con SAVEPOINTs).
- `/admin/users/<id>/change-plan` — `update_user_plan_manual`.
- `/admin/users/<id>/assign-custom-quota` — Enterprise.
- `/admin/users/<id>/remove-custom-quota`.
- `/admin/users/<id>/reset-quota` — reset manual.
- `/admin/users/<id>/invitations` — ver invitaciones de un usuario.
- `/admin/audit-log` — últimas 50 acciones.
- `/admin/stats/detailed`.
- `/admin/debug-stats`, `/admin/fix-dates`.

Adicionales en `admin_billing_routes.py`: `/admin/billing`, `/admin/billing-stats`, `/admin/users/<id>/update-plan`.

---

## 8. Acceso compartido (`project_collaborators`)

### Tabla `project_collaborators`

```sql
id                      SERIAL PK
module_name             VARCHAR(32) CHECK ('llm_monitoring' | 'manual_ai' | 'ai_mode')
project_id              INTEGER
owner_user_id           FK users CASCADE
user_id                 FK users CASCADE
role                    VARCHAR(20) CHECK ('viewer')
invited_by_user_id      FK users SET NULL
created_at, updated_at
UNIQUE (module_name, project_id, user_id)
```

### Tabla `project_invitations`

```sql
id                  SERIAL PK
module_name         VARCHAR(32)
project_id          INTEGER
owner_user_id       FK
inviter_user_id     FK
invitee_email       TEXT
invitee_name        TEXT
role                VARCHAR(20) CHECK ('viewer')
token_hash          TEXT UNIQUE NOT NULL  -- sha256 del token
status              VARCHAR CHECK ('pending'|'accepted'|'revoked'|'expired')
expires_at          TIMESTAMP
accepted_by_user_id FK SET NULL
accepted_at         TIMESTAMPTZ
created_at, updated_at
```

UNIQUE INDEX parcial: `(module_name, project_id, lower(invitee_email)) WHERE status='pending'` — permite reinvitar tras revocación.

### Flujo de invitar

1. Owner llama `POST /api/project-access/projects/<module>/<project_id>/invitations` con `{email, name?, role}`.
2. Servicio `create_project_invitation` (`services/project_access_service.py:456`):
   - Valida módulo y email regex.
   - Verifica que el solicitante es el owner (`user_is_project_owner`).
   - Comprueba que el invitado no se invita a sí mismo y no ya tiene acceso.
   - Genera `raw_token = secrets.token_urlsafe(32)`.
   - Almacena solo `token_hash = sha256(raw_token).hexdigest()` (no el token plano).
   - `expires_at = now + INVITATION_EXPIRY_DAYS` (env `PROJECT_INVITATION_EXPIRY_DAYS`, default 7).
   - Borra invitación pendiente previa para misma combinación, inserta nueva.
   - Construye link `_build_invitation_link(raw_token)` con prioridad: request host → `PROJECT_INVITATION_BASE_URL` → `PUBLIC_BASE_URL` → `https://app.clicandseo.com`.
   - Envía email vía `send_email` (Brevo).
3. Invitee abre link → `/project-invitations/accept?token=...` (`app.py:516`).
4. Si no autenticado → guarda `next` en `auth_next` y redirige a `/login`.
5. Si autenticado → llama `accept_project_invitation(token, user_id)`:
   - Compara `token_hash`.
   - Verifica `status == 'pending'`, no expirado.
   - **Verifica que `user.email == invitation.invitee_email`** (lower-case). Si no coincide, error 403.
   - INSERT en `project_collaborators` (UPSERT con `ON CONFLICT (module, project, user) DO UPDATE`).
   - UPDATE `project_invitations` → `status='accepted'`.
   - Redirige a `redirect_path` del módulo (`/llm-monitoring`, `/manual-ai/`, `/ai-mode-projects/`).

### Módulos soportados

| `module_name` | Tabla del módulo | Label | Path UI |
|---|---|---|---|
| `llm_monitoring` | `llm_monitoring_projects` | "LLM Monitoring" | `/llm-monitoring` |
| `manual_ai` | `manual_ai_projects` | "AI Overview Monitoring" | `/manual-ai/` |
| `ai_mode` | `ai_mode_projects` | "AI Mode Monitoring" | `/ai-mode-projects/` |

### Funciones helper (`services/project_access_service.py`)

| Función | Qué hace |
|---|---|
| `user_is_project_owner(user_id, module, project_id)` | Query a la tabla del módulo. |
| `_get_membership_role(user_id, module, project_id)` | Lee `project_collaborators`. |
| `user_can_view_project(user_id, module, project_id)` | Owner OR role en `ALLOWED_ROLES`. |
| `user_can_edit_project(...)` | Solo owner. |
| `user_can_manage_project_access(...)` | Solo owner. |
| `user_has_any_module_access(user_id, module)` | True si tiene al menos un proyecto compartido en el módulo (usado para abrir paywall). |
| `get_project_permissions(...)` | dict con `is_owner`, `can_view`, `can_edit`, `can_manage_access`. |
| `list_project_members(module, project_id)` | Owner + colaboradores. |
| `list_project_invitations(module, project_id)` | Pendientes/aceptadas. |
| `revoke_project_invitation(invitation_id, requester)` | Solo owner. DELETE (no soft-delete). |
| `remove_project_member(...)` | Solo owner. |
| `get_user_pending_invitations(user_id)` | Invitaciones pendientes para el email del user. |

### Endpoints (`project_access_routes.py`, prefijo `/api/project-access`)

- `GET /projects/<module>/<id>/permissions`
- `GET /projects/<module>/<id>/members`
- `POST /projects/<module>/<id>/invitations`
- `GET /projects/<module>/<id>/invitations`
- `DELETE /invitations/<id>`
- `DELETE /projects/<module>/<id>/members/<user_id>`
- `POST /invitations/accept` (alternativa a la ruta página)
- `GET /my-invitations` — pendientes del user actual.

### Plantilla UI

`templates/project_access.html` (vista compartida).

---

## 9. Cifrado de tokens (Fernet)

- `TOKEN_ENCRYPTION_KEY` (env). Si vacía o inválida, las funciones devuelven el texto **sin cifrar** (`logger.warning`).
- `database.py:500-533`:
  - `_get_fernet()` → instancia `Fernet(key)` o None.
  - `_encrypt(text)` → cifra UTF-8 → string. Si falla, retorna texto plano.
  - `_decrypt(text)` → análogo.
- Mismas helpers en `auth.py:534-553` (duplicadas — deuda).
- **Solo el `refresh_token` se cifra** (`refresh_token_encrypted` columna). `access_token` está en claro (es de corta vida).

### Rotación de clave

> ⚠️ **No hay procedimiento implementado** para rotar `TOKEN_ENCRYPTION_KEY`. Al cambiar la clave, los refresh tokens existentes ya no se podrán descifrar y cada usuario tendrá que re-conectar Google. **No hay script de re-encrypt batch**.

### Decisión de diseño

Las funciones tragan excepciones y devuelven el texto original — **prefiere disponibilidad sobre integridad criptográfica**. Si Fernet rompe, el sistema sigue funcionando con tokens en claro (con `logger.warning`).

---

## 10. Endpoints relacionados con auth

### Páginas

| Ruta | Decorador | Archivo |
|---|---|---|
| `GET /` | (público) | landing |
| `GET /login` | — | `auth.py:734` |
| `GET /signup` | — | `auth.py:786` |
| `GET /forgot-password` | — | `auth.py:629` |
| `GET /reset-password?token=...` | — | `auth.py:687` |
| `GET /profile` | `@auth_required` | `auth.py:1893` |
| `GET /admin/users` | `@admin_required` | `auth.py:1597` |
| `GET /project-invitations/accept` | — (redirige a login si hace falta) | `app.py:516` |

### OAuth Google

| Ruta | Función |
|---|---|
| `GET /auth/login` | Inicia flow OAuth para usuarios existentes. |
| `GET /auth/signup` | Inicia flow para nuevos usuarios. |
| `GET /auth/callback` | Callback Google: maneja login/signup/link. |
| `GET /connections/google/start` | `@auth_required`. Añadir nueva cuenta Google al usuario actual. |
| `GET /connections` | `@auth_required`. Lista conexiones del usuario (sin tokens). |
| `POST /connections/<id>/refresh` | `@auth_required`. Re-sincroniza propiedades GSC. |
| `DELETE /connections/<id>` | `@auth_required`. Borra conexión. |
| `GET /gsc/properties` | `@auth_required`. Propiedades agregadas. |

### Email/password

| Ruta | Método | Función |
|---|---|---|
| `POST /auth/email/signup` | POST | Crea cuenta + auto-login. |
| `POST /auth/email/login` | POST | Login email+pass. |
| `GET /auth/check-email` | GET | Existe email? |
| `POST /auth/forgot-password` | POST | Solicita reset. |
| `POST /auth/reset-password` | POST | Cambia con token. |

### Sesión

| Ruta | Decorador |
|---|---|
| `GET /auth/status` | — (consulta sin side-effects). |
| `POST /auth/keepalive` | `@auth_required_no_activity_update`. |
| `POST/GET /auth/logout` | — (limpia session). |
| `GET /auth/user` | `@auth_required`. |

### Profile

| Ruta | Decorador |
|---|---|
| `POST /profile/update` | `@auth_required`. |
| `POST /profile/change-password` | `@auth_required`. |

### Admin (`@admin_required`)

Ver §7.

### Project access (prefijo `/api/project-access`)

Ver §8.

---

## 11. Variables de entorno

| Variable | Default | Uso |
|---|---|---|
| `FLASK_SECRET_KEY` | `'your-secret-key-here-change-in-production'` ⚠️ inseguro | Firma de cookies de sesión. |
| `GOOGLE_CLIENT_ID` | — | OAuth. |
| `GOOGLE_CLIENT_SECRET` | — | OAuth. |
| `GOOGLE_REDIRECT_URI` | `http://localhost:5001/auth/callback` | OAuth callback. |
| `CLIENT_SECRETS_FILE` | `client_secret.json` | Fallback dev. |
| `OAUTHLIB_INSECURE_TRANSPORT` | `'1'` solo si no Railway | Permitir HTTP local. |
| `OAUTHLIB_RELAX_TOKEN_SCOPE` | `'1'` siempre | Tolerar reordenado de scopes. |
| `TOKEN_ENCRYPTION_KEY` | — | Fernet key para refresh tokens. |
| `RECAPTCHA_SITE_KEY` | — | Cliente (template). |
| `RECAPTCHA_SECRET_KEY` | — | Servidor (verify). |
| `RECAPTCHA_MIN_SCORE` | `0.5` | Umbral v3. |
| `SESSION_TIMEOUT_MINUTES` | `45` | Inactividad. |
| `SESSION_WARNING_MINUTES` | `5` | Aviso pre-expiración. |
| `RAILWAY_ENVIRONMENT` | — | `production`/`staging`/`""` controla cookies/HTTPS. |
| `CRON_TOKEN` / `CRON_SECRET` | — | Bearer en `cron_or_auth_required`. |
| `PROJECT_INVITATION_EXPIRY_DAYS` | `7` | Caducidad invitaciones. |
| `PROJECT_INVITATION_BASE_URL` | — | Construir links de invitación. |
| `PUBLIC_BASE_URL` | `https://app.clicandseo.com` | Fallback para links. |

---

## 12. Operaciones administrativas

### `delete_user(user_id)` (`database.py:1243-1307`)

Patrón "SAVEPOINT por dependencia" para no abortar todo si falla una. Borra en orden:

1. `ai_overview_analysis`
2. `quota_usage_events`
3. `password_reset_tokens`
4. `manual_ai_projects`
5. `gsc_properties`
6. `oauth_connections`
7. `subscriptions`
8. Finalmente `users`.

`safe_delete(...)` envuelve cada DELETE en `SAVEPOINT spX … RELEASE/ROLLBACK TO`. Usa `to_regclass` para verificar que la tabla existe antes.

> ⚠️ **No borra explícitamente `project_collaborators` y `project_invitations`** — las FKs `ON DELETE CASCADE`/`SET NULL` se encargan de los miembros del usuario. Pero si un día se añaden filas con FK no-cascada, podrían quedar huérfanas.

### Auditoría

- Tabla `admin_audit_log`.
- `log_admin_action(admin_id, action, target_user_id, details)` en `admin_billing_panel.py:19`.
- Cada acción admin (toggle status, role change, plan change, custom quota, delete user, quota reset) llama a esta función.
- Endpoint `/admin/audit-log` lista las últimas 50.

### `change_password` (`database.py:1386`)

Verifica con la actual + hashea nueva + UPDATE `users.password_hash`.

### `admin_reset_password` (`database.py:1430`)

Doble check: el `admin_user_id` debe ser admin, target user debe existir, hash + UPDATE.

> ⚠️ **No notifica por email** al usuario informándole. Gap potencial.

---

## 13. Errores históricos y deuda técnica

### Bugs históricos resueltos

#### ProxyFix + `OAUTHLIB_INSECURE_TRANSPORT` (`app.py:124-130`)

Comentario en código: *"Railway termina SSL y reenvía HTTP internamente. Sin ProxyFix, request.url devuelve http:// lo que rompe OAuth (InsecureTransportError). ProxyFix lee X-Forwarded-Proto/Host/For del proxy y corrige request.url automáticamente."*

#### `is_active` puede ser NULL en BD vieja

`get_user_by_*` normalizan a `True` cuando es None — backward-compat con usuarios pre-migración.

#### Comentarios `# FIX` / `# IMPORTANT` relevantes

- `auth.py:1817`: `# FIX: Aceptar estado deseado del body; fallback a toggle si no viene`.
- `auth.py:1437`: `# ✅ ELIMINADAS: Rutas innecesarias de pending-google-signup` — antes había rutas intermedias entre signup OAuth y dashboard.
- `auth.py:225-228`: `is_user_ai_enabled` deprecated, depende ahora del plan.

### Bugs históricos detectables

- Caso `existing_user` en signup OAuth pero **vinculado por email no por `google_id`**: `auth.py:1351-1365` actualiza `users.google_id` cuando no estaba seteado.
- `change_password` rechaza si el user no tiene `password_hash` (cuenta solo Google) con mensaje *"Usa login con Google"*.
- `update_user_profile` bloquea cambiar email si el usuario está vinculado a Google.
- En el callback OAuth signup, si user existe se pasa a flujo "ya registrado" preservando `signup_plan` para no perder la intención de checkout.

### Tablas con FKs y cascada

- `oauth_connections.user_id` → `users(id) ON DELETE CASCADE`.
- `gsc_properties.user_id`, `gsc_properties.connection_id` → CASCADE.
- `password_reset_tokens.user_id` → CASCADE.
- `project_collaborators.user_id`, `owner_user_id` → CASCADE (`invited_by_user_id` SET NULL).
- `project_invitations.owner_user_id`, `inviter_user_id` → CASCADE; `accepted_by_user_id` SET NULL.

### Deuda técnica

| Deuda | Impacto | Riesgo |
|---|---|---|
| **Sin tests de auth automatizados** | Cualquier cambio requiere test manual. | Alto. |
| **`FLASK_SECRET_KEY` con default inseguro** | En dev local sin la env, las cookies se firman con valor predecible. | Medio. |
| **Sin runbook de rotación de `TOKEN_ENCRYPTION_KEY`** | Tras rotación todos los users tendrían que reconectar Google. | Medio. |
| **`admin_reset_password` no envía email** | Usuario no se entera. | Medio (UX). |
| **Helpers Fernet duplicadas** en `database.py` y `auth.py` | DRY broken. | Bajo. |
| **`cleanup_expired_reset_tokens` sin cron** | Tabla crece. | Bajo. |
| **`delete_user` no limpia explícitamente `project_*`** | Depende de FKs. | Bajo (mientras se mantengan las cascadas). |

---

## 14. Tests

> ⚠️ **No existen `test_auth_*.py` ni `test_admin_*.py`**. Los tests del repo son: cron, db pool, LLM providers, webhooks Stripe, locale, project parallelism/timeout.

Solo scripts de diagnóstico (no son tests pytest):

- `oauth_diagnostic.py`
- `debug_oauth_flow.py`
- `find_user_by_id.py`
- `simple_user_diagnosis.py`
- `verificacion_completa_fase1b.py`
- `check_environment_vars.py`, `check_setup.py`, `check_production_ready.py`, `check_staging_config.py`.

Testing manual del flow de auth se hace contra staging Railway. **Es un gap notable** que conviene priorizar.

---

## TL;DR

1. **Tres métodos de auth**: Google OAuth (con scope GSC), email/password local (PBKDF2-SHA256, 100k iter), Cron Bearer token.
2. **Sesión Flask con cookie firmada**, sin JWT. Timeout de 45 min default.
3. **Solo 2 roles**: `'user'` y `'admin'`. El rol `'AI User'` fue eliminado en migración Fase 1B.
4. **Plan ≠ Rol.** El plan decide acceso a features; el rol decide acceso a admin.
5. **Acceso compartido** vía `project_collaborators` + `project_invitations` para los 3 módulos (Manual AI / AI Mode / LLM Monitoring). Solo rol invitado: `viewer` (read-only).
6. **OAuth multi-cuenta**: un user puede tener N `oauth_connections` (UNIQUE por `google_account_id`). Cada conexión sincroniza sus `gsc_properties`.
7. **Solo el `refresh_token` se cifra** con Fernet. Si Fernet falla → fail-soft (texto plano + warning).
8. **ProxyFix activo en Railway** para que OAuth funcione tras el SSL termination del proxy.
9. **Tokens de invitación**: solo se almacena `sha256(token)`, el plano nunca se guarda. Expiry 7 días default.
10. **Deuda principal**: sin tests de auth, `FLASK_SECRET_KEY` con default inseguro, sin runbook de rotación Fernet, `admin_reset_password` sin email al usuario.

— Fin del manual —
