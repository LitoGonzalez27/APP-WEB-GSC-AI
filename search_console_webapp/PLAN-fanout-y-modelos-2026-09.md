# PLAN-fanout-y-modelos-2026-09.md — Query fan-out fidedigno + modelos al día en LLM Monitoring

> **v2 — 2026-09-13.** Sustituye a la v1 del mismo día. Incorpora las decisiones de Carlos tras la revisión:
> modo `auto` como principal, modo `memory` periódico aparte, piloto antes del rollout, normalización de sub-consultas,
> capacidad del cron y ruptura de series históricas. Contexto de fondo en `CLAUDE-query-fanout.md` y
> `CLAUDE-modelos-estado.md`; manual del módulo en `CLAUDE-llm-monitoring.md`; entorno en `CLAUDE-staging.md` y
> `CLAUDE-deploy-railway.md`.

---

## Estado de ejecución — LEER PRIMERO (actualizado 2026-09-13 19:05)

> Para retomar en otra sesión: lee esta sección, luego `CLAUDE-query-fanout.md` (§1b coste) y el `HISTORIAL.md` de
> `~/Desktop/proyectos/propio/clicandseo/`. Lo que viene después (§0 en adelante) es el plan original; donde choque con esta
> sección, manda esta sección.

### Decisiones de Carlos (2026-09-13)
- **La búsqueda web / query fan-out queda SIEMPRE desactivada** (`llm_monitoring_projects.search_mode='off'`) y preparada.
  Se activa **proyecto a proyecto desde el admin** solo para el cliente que la pague. **No se suben precios** a los clientes
  actuales (ni ×6 ni ×2).
- Consecuencia: el "modo memoria" (§1, bloque I) deja de ser un bloque aparte: los proyectos en `off` ya son modo memoria.
  Solo haría falta si un proyecto con búsqueda quiere también la serie sin búsqueda.
- El piloto (bloque F) se hará con el primer cliente que contrate el fan-out, no con proyectos propios.

### Hecho
| Qué | Dónde | Evidencia |
|---|---|---|
| P0 · Perplexity → Agent API (preset `fast`, idioma como mensaje system, país en `user_location`, coste real de `usage.cost`) | staging + **prod** | Staging runs 63-65 100 % OK; E2E prod 8/8 |
| P0 · Cuenta sin crédito (`billing_exhausted`, breaker 30 min, sin reintentos, alerta `provider_billing_exhausted`, health-check OpenAI real) | staging + **prod** | 16 tests |
| P0 · Registry: `gemini-3.6-flash` current; precios oficiales `gpt-5.5` 5/30, `claude-sonnet-5` 2/10, `gemini-3.6-flash` 0,75/3,75; `gpt-5.3-chat-latest` no disponible | staging + **prod** | `migrate_models_2026_09.py --apply`, 6 cambios en changelog |
| P0 · `init_database()` ya no fuerza `gemini-3.5-flash` en cada arranque | staging + **prod** | test de regresión + `updated_at` intacto tras deploy |
| P0 · Gemini cuenta el razonamiento como tokens de salida | staging + **prod** | coste Gemini ~0,01/respuesta |
| P1 · Validación con modelos current y coste proyectado (~×6 con búsqueda) | docs | `CLAUDE-query-fanout.md` §1b |
| P2 · Esquema fan-out (`search_mode`, `search_enabled_at`, `search_queries`, tabla `llm_monitoring_fanout_queries`) + `fanout_store` + `fanout_utils` | staging + **prod** | Perplexity ya guarda sus sub-consultas |
| P2 · UPSERT limpia `has_error` al reintentar con éxito | staging + **prod** | test + 0 respuestas válidas marcadas como error |
| Reparación en prod de 31 respuestas válidas marcadas como error (2026-02-26 … 2026-09-11) | **prod** | Solo `has_error=FALSE`, `error_message=NULL`; snapshots ya las incluían (totales = filas válidas). Copia en `backup-prod-2026-09-13/31_filas_has_error_antes.json` |
| Proyecto de prueba prod id 39 borrado (con sus 2 prompts, 8 resultados, 4 snapshots, 2 filas fan-out) | **prod** | Copia en `backup-prod-2026-09-13/proyecto_39_test_antes_de_borrar.json` |

Commits: staging `a066b4c` `71b252b` `145d329` `58717f7` `8c2c6fc`; main (cherry-pick) `42964e7` `5f79409` `6070329` `ce18723` `5018e88`.
Tests: 336 OK; los 26 fallos + 5 errores restantes son previos y necesitan BD local (`test_llm_monitoring_service`, `e2e`, `performance`).
Huella de datos prod (users, proyectos, prompts, resultados, snapshots, Manual AI, AI Mode + md5 de resultados, proyectos y
usuarios) idéntica antes y después; únicos cambios: errores 213→182 (reparación) y changelog +6 (migración).
Backups y scripts: `~/Desktop/proyectos/propio/clicandseo/investigacion/query-fanout-2026-09-13/`
(`backup-prod-2026-09-13/`, `p1-modelos-actuales/`, `verificar_cron_llm_prod.py`).

### En curso
- **Verificación del primer cron real de prod (martes 2026-09-15, 06:00 Madrid)**: tarea programada
  `clicandseo-verificar-cron-llm-2026-09-15` (09:00 Madrid) que ejecuta `verificar_cron_llm_prod.py 2026-09-15` en solo lectura,
  anota el resultado en `HISTORIAL.md` y en esta tabla. Si no se ejecutó (app cerrada), lanzarlo a mano. Esperado: 4
  proveedores sin errores, modelos nuevos, Perplexity con `model_reported` `openai/...` y filas de fan-out, coste ~15-20 USD
  (sube por la corrección de precios, no por gasto nuevo).

### Pendiente (en orden)
1. **Resultado de la verificación del 15/09** (arriba).
2. **P3 detrás del interruptor**: búsqueda en OpenAI (Responses API + `web_search`), Anthropic (`web_search_20250305`) y Gemini
   (REST `generateContent` + `google_search`, sin `google-genai`) que **solo** se ejecuta si `search_mode='auto'`. Subir
   `anthropic` en `requirements.txt` junto con ese código. Perplexity `low` para proyectos con búsqueda (`fast` da 1 sola query).
3. **Interruptor en el admin** (activar/desactivar `search_mode` por proyecto y fijar `search_enabled_at`) + **ponderación de
   unidades**: un prompt con búsqueda consume más unidades (orientativo: OpenAI ×6, Anthropic ×8, Gemini ×3, Perplexity ×2-3,
   a recalcular con datos reales). Sin esto, activar a un cliente le come el margen.
4. **Capacidad del cron con búsqueda** (bloque E) y **UI de fan-out** (bloque H: bloque en la respuesta, pestaña Fan-out,
   marca de cambio de metodología en gráficos): cuando haya un cliente que lo contrate.
5. **Opcional**: probar "fan-out estimado" barato (herramienta de búsqueda propia sin ejecutar; solo primera ronda, sin fuentes,
   etiquetado como estimado) con los 5 prompts de P1 (<1 USD) para valorar si sirve de gancho en todos los planes.
6. **Negocio**: revisar pricing aun sin búsqueda — con precios corregidos, Business a uso máximo cuesta ~179 USD de LLM de
   229,99 € (sin contar SerpAPI).
7. **Mantenimiento** (bloque K): rotar `CRON_TOKEN` de `function-bun-model-discovery`; pedir acceso a GPT-5.6 (ChatGPT Free);
   Gemini 3.6 Flash sube a 1,50/7,50 el 2027-01-01; limpiar filas no-chat de OpenAI en el registry; knowledge cutoff de
   `gemini-3.6-flash` y `claude-sonnet-5`.

### Cambios técnicos sobre el plan original surgidos al ejecutar
- **Sin `google-genai`**: exige `httpx>=0.28.1` y `google-auth>=2.47`, incompatibles con los pines de GSC/OAuth
  (`httpx==0.27.2`, `google-auth==2.35.0`). Grounding de Gemini por REST (probado en P1). El SDK legacy se queda.
- **Anthropic `web_search_20250305`** (no las versiones con filtrado dinámico, que triplican coste).
- **OpenAI `gpt-5.5`**: cada `web_search_call` trae `action.queries` (lista), no solo `action.query`.
- **Perplexity**: `instructions` sustituye el prompt del preset y el modelo deja de citar; el idioma va como mensaje `system`.
- `sources[].provider` conserva el nombre del proveedor (`perplexity`) por compatibilidad con la UI; `'extracted'` = regex.
- Orden de despliegue usado: esquema → código → registry (el registry tras el deploy para que ningún arranque antiguo lo pise).
- `railway redeploy` no acepta `--environment`: el enlace local de la CLI apunta a producción; cambiar a staging y volver.

## 0. Reglas para quien ejecute esto

1. **Rama de trabajo: `staging`.** Nada a `main` sin orden explícita de Carlos. Subidas a `main` = cherry-pick (ramas divergidas).
2. **Leer antes de tocar**: `CLAUDE-INDEX.md`, `CLAUDE-llm-monitoring.md` (§3 mapa, §4 datos, §6 flujo, §13 retry), `CLAUDE-query-fanout.md`, `CLAUDE-modelos-estado.md`, `CLAUDE-base-de-datos.md`, `CLAUDE-staging.md`.
3. **Secretos**: claves en variables de Railway (`railway variables --environment staging --service Clicandseo --kv`). Nunca imprimirlas enteras, ni en ficheros del repo, ni en logs.
4. **Verificación con evidencia**: "hecho" = acción real ejecutada y resultado comprobado (test, fila en BD, respuesta HTTP, captura). Si algo no se pudo verificar, decirlo.
5. **Tests**: `python3 -m pytest tests/ -q` en verde. Los tests de parseo usan JSON reales en `tests/fixtures/fanout/`.
6. **No machacar APIs**: pruebas manuales con un proyecto de staging de 3-5 prompts. Nunca el cron completo de staging.
7. **Precios y versiones de tools**: siempre desde la documentación oficial el día que se implementa. No dar por buenas cifras de este documento.
8. **Al cerrar cada bloque**: actualizar `CLAUDE-llm-monitoring.md`, entrada en `~/Desktop/proyectos/propio/clicandseo/HISTORIAL.md` y reporte a Carlos (commits, pytest, evidencia, coste medido, pendientes).

## 1. Decisiones tomadas

| Tema | Decisión | Motivo |
|---|---|---|
| Qué se mide | La API de cada proveedor con la herramienta de búsqueda **disponible**. El modelo decide si busca (`auto`). Si no busca, la respuesta es de memoria y se guarda así. | Es lo más parecido a un usuario real, que a veces obtiene búsqueda y a veces no. |
| Modo forzado | **No se implementa.** Nada de "busca siempre" en instrucciones (tampoco en Gemini). | Fuerza un comportamiento que el modelo no elegiría: menos fiel. |
| Modo memoria | Ejecución **aparte y periódica** (1 vez al mes + al crear el proyecto), sin tools, en tabla propia. Alimenta el indicador "Conocimiento de marca del modelo". **Nunca se mezcla** con las métricas principales. | Responde a "si el modelo no busca, ¿sabe quién eres?", que el modo `auto` no contesta en prompts comerciales. |
| Repeticiones | 1 ejecución por prompt, proveedor y día (como hoy). Frecuencias acumuladas entre días. | Coste. |
| Rollout | Piloto de 1 semana con 2-3 proyectos → decisión de Carlos con datos reales → resto de proyectos. | El coste y la duración del cron no se conocen hasta medirlos. |
| Etiquetado | Siempre "observado en la API de <proveedor> con <modelo>", nunca "lo que hizo ChatGPT". | La app de consumo tiene su propio system prompt, memoria y router de búsqueda. |
| Fan-out | Se guardan búsquedas **y** páginas abiertas (`open_page`, `find_in_page`, `fetch_url`). En la UI se muestran separadas. | Qué URL de la marca lee el modelo es una señal SEO de primer nivel. |

## 2. Orden de prioridad (resumen)

| Prio | Bloque | Por qué va aquí | Tamaño | Bloqueado por |
|---|---|---|---|---|
| **P0** | A. Estabilidad: Perplexity → Agent API, detección de "sin crédito", registry | Perplexity deja de funcionar el **2026-09-27**; OpenAI se quedó sin crédito sin que nadie lo viera | 2-2,5 días | — |
| **P1** | B. Validación previa: re-prueba con los modelos actuales, versiones de tools, precios, límites de rate | La investigación usó `claude-sonnet-4-6` y `gemini-3.8-flash`, no los current | 0,5 día | A.3 |
| **P2** | C. Cimientos de datos: esquema, tabla normalizada, utilidades de normalización | Todo lo demás escribe aquí | 1 día | B |
| **P3** | D. Búsqueda en providers (OpenAI, Anthropic, Google) en modo `auto` | Sin esto no hay fan-out | 2,5-3 días | C |
| **P4** | E. Capacidad del cron y rate limits | Con búsqueda cada tarea tarda 3-5 veces más y consume 20-80 veces más tokens | 1 día | D |
| **P5** | F. Piloto en producción (2-3 proyectos, 1 semana) + **decisión de Carlos** | Coste y duración reales antes de extender | 0,5 día + 7 días de espera | E, orden de Carlos |
| **P6** | G. Coste, cuotas y alertas | Necesario antes del rollout general | 1 día | F (datos) |
| **P7** | H. Producto: endpoints, normalización semántica, UI, marca de cambio de metodología | Es lo que se vende | 4-5 días | D (puede avanzar durante el piloto) |
| **P8** | I. Modo memoria + indicador "Conocimiento de marca" | Valor añadido, no bloquea nada | 2 días | C |
| **P9** | J. Rollout a todos los proyectos | — | 0,5 día | F, G, H, orden de Carlos |
| **P10** | K. Fidelidad de modelos (continuo) | Acercar el modelo de la API al de consumo | 1 día + continuo | — |

Tiempo total estimado: **15-17 días de trabajo** más la semana de piloto. H e I pueden avanzar en paralelo durante el piloto.

---

## 3. Contrato de datos (común a todos los providers)

`execute_query(self, query, *, locale=None, search_mode='auto')` devuelve, además de los campos actuales (`base_provider.py`):

```python
'search_mode': 'auto'|'memory',
'search_used': bool,                 # lanzó al menos una búsqueda
'search_tool': str|None,             # 'openai_web_search' | 'anthropic_web_search' | 'gemini_google_search' | 'perplexity_agent'
'search_tool_version': str|None,     # p. ej. 'web_search_20250305' o la versión que se valide en B
'search_country': str|None,          # ISO-2 pasado a la tool
'search_calls': int,                 # nº de búsquedas (no cuenta aperturas de página)
'page_opens': int,                   # nº de open_page / find_in_page / fetch_url
'search_cost_usd': float,            # coste de la tool aparte de tokens
'api_model_reported': str|None,      # campo `model` de la respuesta
'search_queries': [                  # orden cronológico
    {'round': int, 'action': 'search'|'open_page'|'find_in_page'|'fetch_url',
     'query': str|None, 'url': str|None,
     'sources': [str]}               # URLs devueltas por ESA búsqueda; [] en Gemini (no atribuye)
],
'sources': [
    {'url': str, 'provider': 'openai_web_search'|'anthropic_web_search'|'gemini_grounding'|'perplexity_agent'|'extracted',
     'title': str|None, 'query_round': int|None, 'cited': bool}   # cited = aparece como cita en el texto final
],
```

Si `search_used=false`: `search_queries=[]` y `sources` sale de `extract_urls_from_text` con `provider='extracted'` (como hoy).

---

## P0 — Bloque A: Estabilidad (antes del 2026-09-27)

### A.1 Perplexity → Agent API

**Fichero**: `services/llm_providers/perplexity_provider.py` (reescribir `execute_query` y `test_connection`; mantener clase, `@with_retry` y contrato).

- `POST https://api.perplexity.ai/v1/agent` con `requests` y `timeout=RetryConfig.PROVIDER_TIMEOUTS['perplexity']`.
- **Preset**: nuevo campo en el registry o mapeo en el provider. Por defecto `fast` (mismo coste que hoy, 0,0054 USD/prompt medido). **Ojo: `fast` lanza 1 sola query, que es el prompt literal, así que no aporta fan-out.** Los proyectos con fan-out activado (piloto y rollout) usan `low` (5 queries en 2 rondas, 0,0134 USD/prompt medido). El preset se decide con el `search_mode` del proyecto: `off` → `fast`, `auto` → `low`.
- Locale: `instructions` para el system prompt; buscar en la guía de migración el equivalente de `user_location`. Si no existe, país en `instructions`.
- Parseo (`tests/fixtures/fanout/app-perplexity-agent-api-{fast,low,medium}.json`):
  - `output[]` → `search_results` (`queries`, `results[]`), `fetch_url_results`, `message`.
  - `search_queries`: un elemento por query de cada paso (`round` = índice del paso, `sources` = URLs de `results` de ese paso) + `fetch_url` por cada fetch.
  - `sources`: unión de `results[].url`, `provider='perplexity_agent'`.
  - Tokens `usage.*_tokens`; `cost_usd = usage.cost.total_cost`; `search_cost_usd = usage.cost.tool_calls_cost`; `search_calls = usage.tool_calls_details.search_web.invocation`.
  - `model_used` = campo `model` (ej. `openai/gpt-5.6-luna`), también en `api_model_reported`.
- `test_connection`: `{"preset":"fast","input":"Hi","max_output_tokens":20}`.
- `weekly_model_discovery_cron.py` `discover_perplexity_models`: lista fija de presets.
- Mientras no exista la columna `search_queries` (bloque C), el provider devuelve los campos y el engine los ignora. Así A.1 sale a producción sin esperar a C.

**Tests**: `tests/test_llm_providers.py` con los 3 fixtures: nº de `search_queries` (1/5/12), `search_calls`, `cost_usd`, `sources` normalizadas.
**Aceptación en staging**: proyecto de 3 prompts solo con `perplexity` → `run-initial-analysis` → 3 filas sin `has_error`, `model_used` real, coste > 0, menciones y citas detectadas como antes.

### A.2 Detección de "sin crédito"

- `openai_provider.py` `test_connection`: llamada mínima real (`max_output_tokens=16`) en lugar de `models.list()`. Igual en los demás providers si su health-check no consume.
- `retry_handler.py` `classify_error`: `insufficient_quota`, `credit_balance_exhausted`, `no credits remaining`, `billing` → `quota_exhausted` (no reintentable).
- `engine.py`: al primer `quota_exhausted` de un proveedor, marcarlo `exhausted` para el resto del run, guardar sus tareas pendientes como error `provider_quota_exhausted` sin llamar a la API y devolver `exhausted_providers`. Esto evita los 33 errores de circuit breaker del 11/09.
- `cron_alerts.py`: alerta `PROVIDER_QUOTA_EXHAUSTED` (severidad high, email).
- **Tests**: clasificación del mensaje real y un test del engine con provider mock en el que las tareas 2..n no llaman a `execute_query`.

### A.3 Registry de modelos al día

Script idempotente `migrate_models_2026_09.py`:
- Google: current `gemini-3.5-flash` → `gemini-3.6-flash` (`pending_approval=false`). Verificar precio en ai.google.dev.
- Anthropic: comprobar el precio oficial de `claude-sonnet-5` y corregir si no coincide con BD (hoy 3/15; la auditoría indica 2/10).
- OpenAI: `gpt-5.3-chat-latest` → `is_available=false`. `gpt-5.5` sigue current.
- Perplexity: display `Perplexity (Agent API)`.
- Una fila por cambio en `llm_model_changelog` (`changed_by='migration:2026-09'`).
- Mapas `display_names` hardcoded de los 4 providers, `MODEL_FALLBACKS` en `llm_monitoring_routes.py` y fallbacks de constructores.
- `CLAUDE-llm-monitoring.md` §5 actualizado.

### A.4 Promoción a producción del bloque A

pytest verde → staging verificado → **orden de Carlos** → cherry-pick a `main` → migración contra prod → `GET /models/current` en `app.clicandseo.com` → tras el siguiente cron: `SELECT llm_provider, count(*), sum(has_error::int) FROM llm_monitoring_results WHERE analysis_date=CURRENT_DATE GROUP BY 1`.

**Fecha límite: en producción antes del 2026-09-25** (margen de 2 días sobre el 27).

---

## P1 — Bloque B: Validación previa (antes de escribir código de búsqueda)

Scripts en `~/Desktop/proyectos/propio/clicandseo/investigacion/query-fanout-2026-09-13/`, no en el repo.

1. **Re-probar con los modelos current**: `gpt-5.5`, `claude-sonnet-5`, `gemini-3.6-flash`, con 5 prompts reales de proyectos distintos (comercial, informativo, de marca, local, en otro idioma: IT/FR). Todo en modo `auto`, sin instrucción de búsqueda.
2. Anotar por modelo y prompt: si buscó, nº de búsquedas y de páginas abiertas, tokens, tiempo y coste.
3. **Versión de la tool de Anthropic**: comprobar en la documentación si hay una versión más nueva que `web_search_20250305` compatible con Sonnet 5 y qué cambia (filtrado dinámico, precio). Elegir una y anotarla.
4. **OpenAI**: confirmar que `include: ["web_search_call.action.sources"]` y `user_location` funcionan con `gpt-5.5`.
5. **Gemini con `google-genai`**: confirmar `grounding_metadata` con `gemini-3.6-flash` y cuánto duran las URLs de redirección.
6. **Precios oficiales** de la tool de búsqueda de cada proveedor, con URL y fecha.
7. **Rate limits** del tier actual de cada cuenta (TPM/RPM de `gpt-5.5`, `claude-sonnet-5` y `gemini-3.6-flash`) y consumo de tokens por tarea con búsqueda.
8. Guardar las respuestas JSON como nuevos fixtures en `tests/fixtures/fanout/` (sin claves).

**Entregable**: tabla en `CLAUDE-query-fanout.md` §1b con los datos medidos y la estimación de coste por run completo (655 prompts). **Punto de control con Carlos** si el coste estimado sale desproporcionado.

---

## P2 — Bloque C: Cimientos de datos

### C.1 Dependencias
- `openai` y `anthropic` en versiones con Responses API y bloques `server_tool_use` tipados.
- **Añadir** `google-genai` **sin retirar** `google-generativeai`: el SDK viejo lo usan también `agent_scanner/agents.py`, `services/aio_recommendations.py`, `weekly_model_discovery_cron.py`, `weekly_model_check_cron.py`, `update_current_llm_models.py` y `llm_monitoring_routes.py`. Migrarlos queda fuera de este plan.
- Venv limpio: `pip install -r requirements.txt` y comprobar compatibilidad con `httpx`.

### C.2 Esquema (`migrate_llm_fanout_schema.py`, idempotente)
- `llm_monitoring_projects.search_mode VARCHAR(10) DEFAULT 'off' CHECK (search_mode IN ('off','auto'))`. **Default `off`**: activar es una decisión explícita (piloto y luego rollout).
- `llm_monitoring_projects.search_enabled_at TIMESTAMPTZ`: fecha del cambio de metodología, para marcarla en los gráficos.
- `llm_monitoring_results.search_queries JSONB DEFAULT '[]'::jsonb` (detalle por respuesta, para el modal).
- Campos nuevos en `execution_metadata`: los del §3 excepto `search_queries` y `sources`.
- **Tabla normalizada** `llm_monitoring_fanout_queries` (para agregar):
  ```sql
  id BIGSERIAL PK,
  result_id BIGINT REFERENCES llm_monitoring_results(id) ON DELETE CASCADE,
  project_id INT, query_id INT, llm_provider VARCHAR, analysis_date DATE,
  round SMALLINT, position SMALLINT,
  action VARCHAR(16),               -- search | open_page | find_in_page | fetch_url
  query_text TEXT, query_normalized TEXT, query_cluster_id INT NULL,
  url TEXT, url_host TEXT,
  sources JSONB DEFAULT '[]',
  brand_in_sources BOOLEAN NULL,    -- NULL en Gemini (no atribuible)
  competitor_hosts TEXT[] NULL
  ```
  Índices: `(project_id, analysis_date)`, `(project_id, query_normalized)`, `(project_id, url_host)`.
  Escritura: en el mismo UPSERT del engine (`engine.py` ~1016), `DELETE` de las filas del `result_id` y luego `INSERT` en lote. El `result_id` se obtiene con `RETURNING id`.

### C.3 `services/llm_providers/fanout_utils.py` (nuevo)
- `normalize_url(url)`: quitar `utm_*` (incluido `utm_source=openai`), fragmento, barra final; host en minúsculas.
- `resolve_redirects(urls)`: para las URIs `vertexaisearch.cloud.google.com/grounding-api-redirect/...`, `HEAD` con `allow_redirects`, timeout 5 s, máximo 20 por respuesta, en paralelo. **Resolver al guardar** porque caducan (mismo patrón que `google.com/goto`). Si falla: guardar la redirección y `title`.
- `normalize_query(text)`: minúsculas, sin tildes duplicadas ni espacios extra, sin operadores (`site:`, comillas, `OR`, `-término`), sin años sueltos (`2025`, `2026`). Devuelve `query_normalized`. Guardar siempre también el texto original.
- `dedupe_queries(list)`: quita repetidas exactas conservando la primera.
- Tests unitarios con casos reales de los fixtures.

---

## P3 — Bloque D: Búsqueda en los providers (modo `auto`)

Regla común: con `search_mode='memory'` o `'off'` no se envían tools. Con `'auto'` se envían sin forzarlas y sin instrucciones de búsqueda.

### D.1 OpenAI (`openai_provider.py`)
- Chat Completions → `client.responses.create(model, input, instructions=<locale>, max_output_tokens, tools=[{"type":"web_search", "user_location":{"type":"approximate","country":cc}}], include=["web_search_call.action.sources"], tool_choice="auto")`.
- Parseo: `output_text`; items `web_search_call` → `action.type/query/url/sources`; `url_citation` de `annotations` → `sources` con `cited=true`. Tokens de `usage`. `model_used=response.model`.
- Fallback a `OPENAI_FALLBACK_MODEL` también con Responses API.

### D.2 Anthropic (`anthropic_provider.py`)
- `tools=[{"type": <versión elegida en B>, "name":"web_search", "max_uses":5, "user_location":{"type":"approximate","country":cc}}]`.
- Parseo: **concatenar todos los bloques `text`** (hoy solo se lee `content[0]`, que con búsqueda se queda corto); `server_tool_use` → búsqueda; `web_search_tool_result` → `sources` de esa búsqueda; `citations[]` de los bloques de texto → `cited=true`; `search_calls = usage.server_tool_use.web_search_requests`.
- Controlar `stop_reason == "pause_turn"` (búsquedas largas): continuar el turno según la documentación.

### D.3 Google (`google_provider.py`)
- Migrar a `google-genai`: `client.models.generate_content(model, contents, config=GenerateContentConfig(system_instruction=<locale>, tools=[Tool(google_search=GoogleSearch())]))`. `prompt_strategy` pasa a `system_user`.
- Parseo: `grounding_metadata.web_search_queries` → `dedupe_queries`, `round=1`, `sources=[]`; `grounding_chunks[].web` → `sources` (URI resuelta, `title`); `grounding_supports` → marcar `cited=true` en los chunks referenciados. `search_used = bool(queries)`.
- `model_used = response.model_version`.

### D.4 Engine
- Pasar `search_mode` del proyecto a cada tarea.
- UPSERT: `search_queries`, metadata ampliada, escritura en `llm_monitoring_fanout_queries` con `brand_in_sources` y `competitor_hosts` calculados con la misma normalización de host que ya usa la detección.
- `analyze_brand_mention` sin cambios de lógica. Con búsqueda real, las `sources` dejan de ser regex.
- Log `🧪 task analyzed`: añadir `search_used`, `search_calls`, `page_opens`.

### D.5 Tests y verificación
- Un test de parseo por provider con los fixtures de B (contrato del §3 campo a campo), incluidos casos "no buscó".
- Test del UPSERT: `search_queries` y filas en `llm_monitoring_fanout_queries`; re-ejecutar el mismo día no duplica filas.
- Staging: proyecto de 5 prompts, 4 proveedores, `search_mode='auto'` → 20 filas; comprobar `search_used` por proveedor, `sources[].provider != 'extracted'` cuando buscó, filas en la tabla normalizada y URLs de Gemini resueltas.

---

## P4 — Bloque E: Capacidad del cron y rate limits

Situación actual: `LLM_PROJECT_PARALLELISM` (3 en prod) × `max_workers=8` = hasta 24 tareas simultáneas; timeout **por proyecto** (`project_timeout.py`); alerta de run a los 150 min.

- **Estimación con los datos de B**: duración por proyecto = tareas × tiempo medio con búsqueda / 8. Comprobar los proyectos más grandes (Manual AI no cuenta, solo LLM: Fini 59 prompts, Elha IT 34, etc.) contra el timeout por proyecto.
- **Rate limits por proveedor**: con 8 workers y ~70k tokens por tarea en OpenAI, un solo proyecto puede superar el TPM del tier. Añadir un **semáforo global por proveedor** (`LLM_PROVIDER_CONCURRENCY_OPENAI=4`, etc., por env var) compartido entre proyectos, para no depender del paralelismo por proyecto.
- Ajustar por env var (sin código si basta): timeout por proyecto proporcional al nº de prompts, umbral de alerta de duración.
- Los 429 por TPM deben clasificarse como `rate_limit` con backoff largo, no abrir el circuit breaker del proveedor entero.
- **Verificación**: simular en staging un proyecto de 30 prompts × 4 proveedores en `auto` y medir duración, 429 y huecos (con la pasada de completitud activa).

---

## P5 — Bloque F: Piloto (1 semana) y decisión

1. **Orden de Carlos** para subir los bloques C, D y E a producción con todos los proyectos en `search_mode='off'`. Resultado: nada cambia para nadie.
2. Carlos elige 2-3 proyectos piloto (propuesta: uno propio o de confianza con muchos prompts comerciales, uno en otro idioma y uno pequeño). `search_mode='auto'` y `search_enabled_at=now()`.
3. Durante 7 días, informe diario automático o por consulta:
   - % de respuestas con búsqueda por proveedor y prompt.
   - Búsquedas y páginas abiertas medias.
   - `cost_usd` por proveedor y prompt: tokens frente a tool.
   - Duración por proyecto, 429 y huecos.
   - Cambio en tasa de mención y citas frente a la semana anterior (la ruptura esperada).
4. **Entregable**: `CLAUDE-query-fanout.md` §6 "Resultados del piloto" con coste mensual proyectado para 655 prompts.
5. **Decisión de Carlos**: presupuesto; en qué planes se activa (todos, Business/Enterprise, add-on); cuántas unidades de cuota consume un prompt con búsqueda; fecha de rollout.

---

## P6 — Bloque G: Coste, cuotas y alertas

- `llm_model_registry.cost_per_search_call NUMERIC(10,6)` con los precios oficiales de B. Si falta: NULL, `search_cost_usd=0` y warning.
- Providers: `cost_usd = tokens × precio + search_cost_usd` (Perplexity: `usage.cost`).
- `admin_cost_panel.py` (`/admin/api/costs`): desglose tokens frente a búsqueda por proveedor y simulador con modo `auto`.
- `cron_alerts.py`: recalibrar `CRON_ALERT_COST_MULTIPLIER`. **Avisar a Carlos antes del primer run con búsqueda**, que disparará el cost spike por diseño.
- `llm_monitoring_limits.py` y `enterprise_limits.py`: aplicar la decisión de F sobre unidades por prompt. Revisar las recetas de alta Enterprise (2.400 unidades LLM).
- Gating por plan si Carlos lo decide: `search_mode` solo editable en los planes permitidos (backend + UI).

---

## P7 — Bloque H: Producto

### H.1 Endpoint de detalle
`GET /projects/<id>/responses`: añadir `search_queries`, `search_used`, `search_calls`, `page_opens`, `search_tool`, `api_model_reported`.

### H.2 Endpoint de agregación `GET /projects/<id>/fanout`
Filtros: `days`, `llm_provider`, `cluster`, `query_id` (reutilizar `_parse_report_filters` / `_resolve_filtered_query_ids`). Solo sobre filas con `search_mode='auto'`.
```json
{
  "summary": {"runs": 120, "runs_with_search": 96, "search_rate": 0.8, "avg_searches": 4.2, "avg_page_opens": 1.3,
              "by_provider": {"openai": {"search_rate": 1.0, "attributable": true}, "google": {"search_rate": 0.4, "attributable": false}}},
  "top_queries": [{"query": "mejor software facturación autónomos", "cluster_id": 7, "variants": 5, "count": 14,
                   "runs_share": 0.12, "providers": {"openai": 9, "perplexity": 5}, "brand_in_sources_share": 0.43}],
  "brand_pages_opened": [{"url": "https://cliente.com/precios", "count": 6, "providers": {"openai": 6}}],
  "competitor_pages_opened": [...],
  "by_prompt": [{"query_id": 12, "search_rate": 0.9, "top_queries": [...]}]
}
```
`brand_in_sources_share` solo para OpenAI, Anthropic y Perplexity; `null` en Gemini con nota "Gemini no atribuye fuentes a cada búsqueda".

### H.3 Agrupación semántica de sub-consultas
- El texto exacto casi nunca se repite entre runs. Agrupar `query_normalized` por proyecto en clusters (`query_cluster_id`).
- Opción recomendada: embeddings baratos (OpenAI `text-embedding-3-small` o el de Gemini) + umbral de similitud, en un job diario tras el cron que solo procesa las queries nuevas. Tabla `llm_monitoring_fanout_clusters (id, project_id, label, centroid VECTOR o JSONB, created_at)`. La etiqueta es la variante más frecuente.
- Validar el umbral a mano con los datos del piloto (una muestra de 100 queries).

### H.4 UI
- **Modal de respuesta** (`llm-monitoring-responses.js`, antes de "Sources & Links"): dos secciones, "Búsquedas del modelo (N)" y "Páginas que abrió (N)". Cada búsqueda lleva chips de dominio de sus fuentes (marca y competidores resaltados con `isUrlFromBrand` / `isUrlFromCompetitor`). Si no buscó: "El modelo respondió sin buscar en la web (memoria)".
- **Pestaña Fan-out** (nuevo mixin `llm-monitoring-fanout.js`, cargado en orden tras `responses`): KPIs (tasa de búsqueda por proveedor), tabla de sub-consultas agrupadas (expandible a variantes), tabla "Páginas de tu marca que leen los modelos" y tabla por prompt. Brandbook `--cs-`, sin emojis.
- **Marca de cambio de metodología**: línea vertical en los gráficos de evolución (mención, SOV, sentimiento) en `search_enabled_at` con tooltip "Desde aquí los modelos pueden buscar en la web". Aviso en los KPIs que comparan periodos cuando el rango cruza esa fecha.
- **Banner de fidelidad**: "Observado en la API de OpenAI (gpt-5.5). ChatGPT Free usa GPT-5.6 Luna, sin acceso por API." Texto desde el registry (bloque K).
- **Exportaciones**: Excel/PDF con hoja o sección de fan-out, reutilizando los helpers compartidos panel↔export.

### H.5 Verificación
Chrome MCP sobre staging: modal con búsqueda y sin búsqueda, pestaña Fan-out con datos, marca en gráficos, export. Sin errores en consola. Capturas a Carlos.

---

## P8 — Bloque I: Modo memoria y "Conocimiento de marca"

- **Tabla propia** `llm_monitoring_memory_results` con la misma forma básica que `results` (proyecto, prompt, proveedor, fecha, respuesta, menciones, posición, sentimiento, modelo). No se reutiliza `llm_monitoring_results` porque su clave única `(project_id, query_id, llm_provider, analysis_date)` chocaría con el run `auto` del mismo día y contaminaría todas las métricas existentes.
- Ejecución: `search_mode='memory'` (sin tools), reutilizando `execute_query` y la detección de marca. Se dispara:
  - al crear un proyecto (junto al análisis inicial);
  - mensualmente, en un cron Bun nuevo (día 1) o como paso opcional del cron LLM existente.
- Cuota: decidir con Carlos si consume unidades. Con prompts sin búsqueda el coste es bajo.
- UI: tarjeta "Conocimiento de marca del modelo" (% de prompts en los que el modelo menciona la marca sin buscar, por proveedor, evolución mensual) y comparativa "sin buscar frente a buscando".
- En `/ai-summary`: decidir si entra en el score o solo se muestra como dato aparte (propuesta: aparte).

---

## P9 — Bloque J: Rollout general

- Con la decisión de F aplicada: `UPDATE llm_monitoring_projects SET search_mode='auto', search_enabled_at=now() WHERE <planes decididos>`.
- Comunicación a usuarios (email o banner in-app) explicando el cambio de metodología y la ruptura de series.
- Vigilar los 2 primeros runs: coste, duración, errores y alerta de cost spike.
- Actualizar `CLAUDE-llm-monitoring.md` (flujo, datos, costes) y el `AGENTS.md` de Clicandseo.

---

## P10 — Bloque K: Fidelidad de modelos (continuo)

- Registry: `consumer_default_model` y `consumer_default_source` (URL + fecha). `GET /models/current` devuelve `matches_consumer_default`. El modal "Active LLM Models" muestra "Lo que ven los usuarios: …".
- OpenAI: pedir acceso al preview de GPT-5.6 (account rep). Cuando llegue, pasar a `gpt-5.6-luna` como current y **anotarlo como otro cambio de metodología** en los gráficos.
- Discovery: auto-aprobar por patrón `^gemini-\d+\.\d+-flash$` para Google (excluir `-lite`, `-live`, `-tts`, `-eap`) y alerta semanal en el admin con los pendientes del resto.
- Rellenar `knowledge_cutoff_*` de `gemini-3.6-flash` y `claude-sonnet-5` desde las páginas oficiales.
- Limpieza: filas no-chat de OpenAI en el registry (audio, realtime, transcribe).
- Seguridad: rotar `CRON_TOKEN` de `function-bun-model-discovery` (expuesto en una salida de terminal el 2026-09-13).

---

## 4. Puntos de decisión de Carlos (en orden)

| Cuándo | Decisión |
|---|---|
| Fin de A | Subir el bloque A a producción (antes del 25/09) |
| Fin de B | Seguir adelante si el coste estimado por run es asumible |
| Inicio de F | Qué 2-3 proyectos son piloto; subir C-E a prod con todo en `off` |
| Fin de F | Presupuesto, planes con búsqueda, unidades por prompt, fecha de rollout |
| Bloque I | Si el modo memoria consume cuota y si entra en el score de `/ai-summary` |
| Bloque J | Texto de la comunicación a usuarios |
