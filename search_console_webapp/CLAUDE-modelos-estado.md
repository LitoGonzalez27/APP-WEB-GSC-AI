# CLAUDE-modelos-estado.md — Estado de los modelos LLM frente a lo que ven los usuarios (2026-09-13)

> Auditoría hecha el 2026-09-13 con las claves de Railway (prod) y la BD de producción (solo lectura). Regla de producto vigente
> (`CLAUDE-llm-monitoring.md` §5): el modelo "current" de cada proveedor debe ser el que ven los **usuarios gratuitos** de la app
> de consumo (ChatGPT, Claude.ai, Gemini app, Perplexity). Aquí se compara eso con lo que la app usa hoy y con lo que la API permite.
> **Actualización 2026-09-13 (tarde)**: aplicado en **staging** (`migrate_models_2026_09.py --apply`): Google current
> `gemini-3.6-flash` (0,75/3,75), `claude-sonnet-5` 2/10, `gpt-5.5` **5/30** (el registry tenía 2,5/10), `gpt-5.3-chat-latest`
> no disponible, Perplexity servido por Agent API. Descubierto y arreglado: `init_database()` volvía a poner
> `gemini-3.5-flash` como current en cada arranque (por eso 3.6/3.7 nunca se quedaban). **Producción: aplicado también el 2026-09-13 18:44** (misma migración, 6 cambios,
> copia previa del registry en `investigacion/query-fanout-2026-09-13/backup-prod-2026-09-13/`).

## 1. Resumen por proveedor

| Proveedor | Current en `llm_model_registry` | Lo que ve el usuario gratuito hoy | Lo más nuevo en la API con nuestra clave | Veredicto |
|---|---|---|---|---|
| OpenAI | `gpt-5.5` (desde 2026-08-31) | **GPT-5.6 Luna** (ChatGPT Free; OpenAI amplió Luna a usuarios free en agosto 2026). Plus usa GPT-5.6 Sol. | `gpt-5.5` / `gpt-5.5-pro`. La familia `gpt-5.6-*` y `gpt-6-astra` existen en docs pero **nuestro proyecto no tiene acceso** (403 "Project does not have access", preview limitado a partners con account rep). `gpt-5.3-chat-latest` deprecado (404). | Desactualizado sin remedio inmediato: hay que pedir acceso al preview de 5.6 o esperar GA. Mientras tanto `gpt-5.5` es lo más cercano. |
| Anthropic | `claude-sonnet-5` (aprobado por email 2026-08-01) | **Claude Sonnet 5** (default Free y Pro desde 2026-06-30, fuente Anthropic) | `claude-fable-5-1` (2026-08-28), `claude-opus-5` (Pro/Max), `claude-sonnet-5` | **Correcto**. Pero el precio en el registry está mal: BD `3.00 / 15.00`, oficial **2 / 10 USD por 1M**. Estamos sobreestimando el coste de Anthropic un 50 %. |
| Google | `gemini-3.5-flash` (desde 2026-05-20) | **Gemini 3.6 Flash** (Gemini app, "todos los usuarios", release notes 2026-07-21). 3.7 y 3.8 Flash solo AI Pro/Ultra (3.8 desde 2026-09-02). | `gemini-3.8-flash` (`gemini-flash-latest` apunta a él), `gemini-3.7-flash`, `gemini-3.6-flash` | Desactualizado un escalón. En el registry `gemini-3.6-flash` y `gemini-3.7-flash` están `pending_approval=true` desde el 01/08 y el 15/08 (el discovery los detectó; nadie los aprobó). Cambiar current a `gemini-3.6-flash`. |
| Perplexity | `sonar` vía `/chat/completions` | Perplexity free usa su búsqueda estándar; el Agent API preset `fast` es el equivalente de `sonar` | **Chat Completions con Sonar se retira el 2026-09-27**. Sustituto: Agent API `POST https://api.perplexity.ai/v1/agent` con `preset` (`fast`=sonar, `low`=sonar-pro, `medium`=sonar-reasoning-pro, `high`=deep-research). Probado con nuestra clave: funciona. | **URGENTE**: el provider deja de funcionar en 14 días si no se migra. |

## 2. Detalle Perplexity: Agent API (probado 2026-09-13)

- Request: `{"preset": "fast", "input": "<prompt>"}`. Respuesta con `output[]` de pasos: `search_results` (con **`queries`** = lista de sub-consultas lanzadas y `results[]` con `url`, `title`, `snippet`, `date`, `source`), `fetch_url_results`, y `message` (texto). `usage.cost.total_cost` y `usage.tool_calls_details` traen el coste real por llamada.
- **Expone el query fan-out** (a diferencia de `/chat/completions`): ver `CLAUDE-query-fanout.md`. Con `fast` fue 1 query (el prompt literal); con `low` 5 queries en 2 rondas; con `medium` 12 queries en 6 rondas más 3 fetch de páginas de marca.
- Modelo subyacente reportado: `openai/gpt-5.6-luna` (presets `low` y `medium`). Es decir, Perplexity ya corre sobre el modelo que ChatGPT Free usa y al que nuestra clave OpenAI no llega.
- Coste medido por prompt: `fast` 0,0054 USD (igual que `sonar` hoy: 0,0054), `low` 0,0134, `medium` 0,0304.
- La sección `search_results.results[]` sustituye a `citations`; hay que adaptar `perplexity_provider.py` (hoy usa el SDK de OpenAI contra `/chat/completions` y lee `response.citations`). No comprobado si el SDK de OpenAI sirve para `/v1/agent`; con `urllib`/`requests` funciona.
- Fuentes: docs.perplexity.ai "Sonar will be supported until September 27, 2026" (página de modelos) y guía "Migrate from Sonar to the Agent API".

## 3. Cómo se actualiza (cuando Carlos lo ordene)

1. **BD** (`llm_model_registry`): `is_current` a `gemini-3.6-flash` (y `pending_approval=false`), corregir precio de `claude-sonnet-5` a 2/10, dar de alta `perplexity` `fast` (o mantener `sonar` como id lógico y mapear a preset en el provider), marcar `gpt-5.3-chat-latest` como `is_available=false`. Registrar en `llm_model_changelog`. Hay endpoint `PUT /api/llm-monitoring/models/<id>` y flujo de aprobación por email (`/models/approve`).
2. **Providers**: `perplexity_provider.py` → Agent API (obligatorio antes del 27/09). `google_provider.py` → SDK `google-genai` (necesario también para grounding). `openai_provider.py` → Responses API (necesario para `web_search`); el modelo sigue `gpt-5.5` hasta tener acceso a 5.6.
3. **UI**: el modal "Active LLM Models" lee `GET /api/llm-monitoring/models/current` y pinta `model_display_name` del registry, así que se actualiza solo al cambiar la BD. Revisar los textos "(Free Default)" en `model_display_name` y los mapas `display_names` hardcoded en cada provider (`get_model_display_name`), que se han quedado con nombres viejos (gpt-5.4, gemini-3-flash-preview...). El modal de Knowledge Cutoff usa `knowledge_cutoff_*` del registry: rellenar para 3.6 Flash y Sonnet 5.
4. **Docs**: `CLAUDE-llm-monitoring.md` §5 sigue diciendo `gpt-5.3-chat-latest` / `claude-sonnet-4-6` / `gemini-3-flash-preview`: actualizar.
5. **Discovery**: el cron detecta modelos nuevos (ver changelog: 3.6 y 3.7 Flash el 01/08 y 15/08) pero con `AUTO_UPDATE_MODELS=false` se quedan en `pending_approval` si nadie responde al email. Decidir si se aprueba desde el admin o se activa auto-update solo para Google Flash.

## 4. Incidencias vistas en esta auditoría

- **OpenAI sin crédito** 11-13/09: run del 11/09 con 38/240 errores openai. Carlos recargó el 13/09. `test_connection` (`models.list`) pasa sin crédito: el cron no excluye al proveedor. Propuesta: detectar `insufficient_quota` en el engine y pausar el proveedor + alerta por email.
- El registry tiene 100+ filas de OpenAI con ids no-chat (audio, realtime, transcribe) sin precio: ruido del discovery, no afecta pero ensucia el admin.
- `CRON_TOKEN` de `function-bun-model-discovery` apareció en una salida de terminal de esta sesión: rotarlo si se considera expuesto.
