# CLAUDE-INDEX.md — Índice maestro de manuales del sistema (ClicandSEO)

> Este archivo es el **mapa** de toda la documentación interna del proyecto.
> Cada `CLAUDE-<area>.md` cubre un dominio funcional y se puede leer de forma independiente.
>
> **Para una futura sesión de Claude**: empieza siempre por aquí para orientarte. Lee solo el archivo que toque según la tarea — no hace falta cargar todos.
>
> **Para Carlos**: si quieres entender una parte concreta del sistema, abre el archivo cuyo nombre coincida con esa parte.
>
> Última actualización: 2026-05-08. **Documentación completa**: 13 manuales cubriendo todos los dominios del sistema.

---

## Convención de nombres

Patrón: `CLAUDE-<area>.md`, en español, con guiones, todo minúsculas excepto el prefijo `CLAUDE-`.

- Cada archivo cubre **un dominio funcional bien definido**.
- Si un dominio crece demasiado, se parte en `CLAUDE-<area>-<subarea>.md`.
- Ningún archivo debe duplicar contenido de otro: si algo es transversal, vive en su propio archivo y los demás lo enlazan.

---

## Manuales actuales

### 📦 Productos (los 3 motores de análisis)

| Archivo | Estado | Cubre |
|---------|--------|-------|
| [`CLAUDE-manual-ai.md`](./CLAUDE-manual-ai.md) | ✅ | **Manual AI Analysis** (AI Overview Monitoring): SerpAPI `engine=google`, detección de AIO, expansión "collapsed" con `page_token`, ranking de dominios citados, AIO vs Organic, cron secuencial con advisory lock `4242`. |
| [`CLAUDE-ai-mode.md`](./CLAUDE-ai-mode.md) | ✅ | **AI Mode** (Google AI Mode): SerpAPI `engine=google_ai_mode`, detección de marca con word boundaries, sentimiento (sólo EN), cron secuencial con advisory lock `4243`, Bun service `function-bun-AI-Mode`. |
| [`CLAUDE-llm-monitoring.md`](./CLAUDE-llm-monitoring.md) | ✅ | **LLM Monitoring** (LLM Visibility Monitor): APIs directas de GPT/Claude/Gemini/Perplexity, `llm_model_registry`, cron paralelo con timeout por proyecto, retry de 5 capas, SoV ponderado, locale fidelity, model discovery v2 con aprobación por email. |
| [`CLAUDE-search-console.md`](./CLAUDE-search-console.md) | ✅ | **Google Search Console** (producto histórico): integración GSC + dashboards + AI Overview detection legacy. Pre-cursor de Manual AI. Tabla `ai_overview_analysis` con UPSERT diario. Análisis on-demand (sin cron). |

### 🏗️ Infraestructura y sistemas transversales

| Archivo | Estado | Cubre |
|---------|--------|-------|
| [`CLAUDE-INDEX.md`](./CLAUDE-INDEX.md) | ✅ | Este índice. |
| [`CLAUDE-stripe-cuotas-crons.md`](./CLAUDE-stripe-cuotas-crons.md) | ✅ | Stripe (webhooks, eventos), ciclo de vida del usuario, arquitectura de crons (Bun + HTTP), 3 capas de defensa de billing, troubleshooting Stripe. |
| [`CLAUDE-base-de-datos.md`](./CLAUDE-base-de-datos.md) | ✅ | PostgreSQL + psycopg2, pool `_PooledConnection`, esquema completo (tablas `users`, `oauth_connections`, `quota_usage_events`, `project_collaborators`...), migraciones manuales, patrones (SAVEPOINT, advisory locks `4242`/`4243`, idempotencia con `ON CONFLICT`). |
| [`CLAUDE-deploy-railway.md`](./CLAUDE-deploy-railway.md) | ✅ | Servicios Railway (app + Postgres + 5 Bun functions), `railway.json`/`Procfile`/`nixpacks.toml`, env vars completas, deploy por git push, MCP Railway, troubleshooting deploy. |
| [`CLAUDE-quota-system.md`](./CLAUDE-quota-system.md) | ✅ | Sistema de cuotas transversal: 2 contadores (RU global + units LLM), `quota_manager.py` / `quota_middleware.py` / `llm_monitoring_limits.py`, pause/resume cross-module, plan free, Enterprise custom, admin panel. |
| [`CLAUDE-auth-usuarios.md`](./CLAUDE-auth-usuarios.md) | ✅ | OAuth Google + email/password local (PBKDF2-SHA256), sesiones Flask, roles (`user`/`admin`), `project_collaborators` (acceso compartido cross-módulo), Fernet token encryption, password reset, panel admin. |
| [`CLAUDE-frontend.md`](./CLAUDE-frontend.md) | ✅ | Vanilla JS ES2017+ sin build system, plantillas Jinja2 por producto, módulos ES (Manual AI / AI Mode modulares; LLM monolítico 8.785 líneas), Chart.js + Grid.js, `window.QuotaUI`, sin i18n. |
| [`CLAUDE-emails-alertas.md`](./CLAUDE-emails-alertas.md) | ✅ | Brevo SMTP + API REST, `email_service.py` / `brevo_api_service.py` / `cron_alerts.py`, alertas (duración / error rate / cost spike / stuck quota / unmatched customer), aprobación de modelos LLM por email, plantillas hardcoded. |
| [`CLAUDE-integraciones.md`](./CLAUDE-integraciones.md) | ✅ | Mapa exhaustivo de APIs externas: GSC, SerpAPI, Stripe, OpenAI/Anthropic/Gemini/Perplexity, Brevo, OAuth Google, reCAPTCHA v3, Jina.ai Reader, GTM. Tools MCP del usuario (Ahrefs, GA4, Notion, Figma, Hostinger). Servicios NO integrados. |
| [`CLAUDE-brand-radar.md`](./CLAUDE-brand-radar.md) | ✅ | **Aclaración**: Brand Radar NO es producto interno. Son las herramientas MCP de Ahrefs disponibles desde sesiones de Claude. El equivalente interno es LLM Monitoring. |

---

## Cómo usar este índice

### Si Carlos quiere entender algo

1. Mira la tabla "Manuales actuales".
2. Abre el archivo cuyo título encaje con tu duda.
3. Cada manual empieza con un **TL;DR** o "visión general en 5 minutos".

### Si una nueva sesión de Claude llega al proyecto

1. **Lee primero este `CLAUDE-INDEX.md`** para tener el mapa.
2. Identifica qué área toca la tarea del usuario.
3. Carga **solo** el manual relevante (no todos — son largos).
4. Si la tarea cruza varias áreas, carga los manuales en orden de relevancia.
5. **Antes de escribir código nuevo**, comprueba si el manual ya describe el patrón a seguir (idempotencia, pool de conexiones, alertas, etc.).

### Mapa rápido por tipo de tarea

| Si la tarea es… | Cargar primero |
|---|---|
| Tocar Stripe / billing / cuotas | `CLAUDE-stripe-cuotas-crons.md` + `CLAUDE-quota-system.md` |
| Tocar Manual AI / AI Overview | `CLAUDE-manual-ai.md` |
| Tocar AI Mode | `CLAUDE-ai-mode.md` |
| Tocar LLM Monitoring | `CLAUDE-llm-monitoring.md` |
| Tocar Search Console / dashboard `/app` | `CLAUDE-search-console.md` |
| Crear migración / cambiar esquema | `CLAUDE-base-de-datos.md` |
| Configurar deploy / env vars / Railway | `CLAUDE-deploy-railway.md` |
| Tocar OAuth, login, sesión, roles | `CLAUDE-auth-usuarios.md` |
| Tocar HTML / JS / CSS / dashboards | `CLAUDE-frontend.md` |
| Añadir alerta o email | `CLAUDE-emails-alertas.md` |
| Integrar API externa nueva | `CLAUDE-integraciones.md` |
| El usuario pregunta por "Brand Radar" | `CLAUDE-brand-radar.md` (= no es producto interno) |

### Si añades un manual nuevo

1. Crea el archivo siguiendo la convención `CLAUDE-<area>.md`.
2. Añade una fila en la tabla "Manuales actuales" de este índice.
3. Mantén el patrón: TL;DR arriba, secciones numeradas, mapa de archivos, env vars relevantes, troubleshooting.

---

## Reglas de oro (transversales a todos los manuales)

Estas reglas valen para **cualquier área del sistema** y no se repiten en cada manual:

1. **Idempotencia siempre**. Cualquier handler que reciba eventos externos (webhooks, crons, jobs) debe tolerar reentradas sin duplicar efectos. Patrones canónicos: `INSERT … ON CONFLICT DO NOTHING/UPDATE RETURNING`, UNIQUE constraints estratégicas, advisory locks.
2. **No hardcodear timeouts ni paralelismo**. Todo lo que dependa de carga va por env vars con defaults sensatos.
3. **Pool de conexiones**: usar `database.get_db_connection()` siempre. Nunca `psycopg2.connect()` directo (excepto en migraciones one-shot).
4. **Locks cortos**: una conexión por unidad de trabajo. COMMIT antes de llamar a funciones que abran otra conexión sobre el mismo recurso (evita self-deadlock).
5. **Alertas por excepción, no por norma**. El sistema avisa cuando algo se sale de lo esperado; no spamea con cada run normal.
6. **Carlos no es técnico**. Cualquier cambio que cambie el comportamiento debe explicarse en lenguaje llano antes de mostrar el código.
7. **`autocommit=True` solo para advisory locks**. Si un cron mantiene una sesión Postgres abierta >15 min sin autocommit, Postgres mata la conexión por `idle_in_transaction_session_timeout`.
8. **Toda escritura de cuota / despausa pasa por `quota_manager.py` y `database.py`**. No duplicar lógica.
9. **Webhooks Stripe**: 200 = OK, 503 = customer_not_found (Stripe reintenta 3 días), 500 = excepción. Nunca 200 silencioso.
10. **Los crons reales son Bun services en Railway**, no el array `crons` de `railway.json` (que NO se ejecuta).

---

## Stats de la documentación

```
13 archivos CLAUDE-*.md
~7.500 líneas de documentación
~250 KB de markdown
```

Cobertura completa: **productos** (Manual AI, AI Mode, LLM Monitoring, Search Console legacy), **billing** (Stripe + cuotas), **infra** (BD, deploy Railway, frontend, auth, emails), **integraciones** (GSC, SerpAPI, LLMs, Brevo, OAuth, reCAPTCHA, Jina, GTM), **clarificaciones** (Brand Radar).

— Fin del índice —
