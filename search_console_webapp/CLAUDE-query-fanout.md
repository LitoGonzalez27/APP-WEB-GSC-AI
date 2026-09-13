# CLAUDE-query-fanout.md — Query fan-out en LLM Monitoring

> Estado a 2026-09-13 (noche): **P0 y P2 en producción** (Perplexity Agent API, cuenta sin crédito, registry al día, esquema
> de fan-out). **Búsqueda web desactivada en todos los proyectos por decisión de Carlos**: se activará por proyecto solo para
> clientes que paguen el fan-out (el coste con búsqueda es ~×6, §1b). P1 cerrado. Plan en `PLAN-fanout-y-modelos-2026-09.md`.
>
> Estado a 2026-09-13 (mañana): investigación cerrada, sin código. Carlos quiere reportar en Clicandseo las sub-consultas
> ("query fan-out") que lanza cada modelo al buscar en la web para responder a un prompt. Este manual recoge qué expone
> cada proveedor (verificado con las claves de Railway), cómo está la app hoy y qué habría que tocar.
> Ficheros de prueba (respuestas JSON completas y scripts): `~/Desktop/proyectos/propio/clicandseo/investigacion/query-fanout-2026-09-13/`.

---

## 1. Qué expone cada proveedor

| Proveedor | Fan-out por API | Dónde viene | Atribución query → fuentes | Verificado |
|---|---|---|---|---|
| OpenAI (Responses API, tool `web_search`) | **Sí** | Items `output[].type == "web_search_call"` con `action.type` (`search` / `open_page` / `find_in_page`), `action.query` o `action.url`, y con `include: ["web_search_call.action.sources"]` la lista `action.sources` de cada búsqueda. Citas finales en `message.content[].annotations[]` (`url_citation`). | Sí | 2026-09-13, clave Railway, `gpt-5.5` y `gpt-5-mini` |
| Anthropic (tool `web_search_20250305`) | **Sí** | Bloques `server_tool_use` (`input.query`) seguidos de `web_search_tool_result` (lista de `{url, title, ...}`). `usage.server_tool_use.web_search_requests` da el número de búsquedas. | Sí | 2026-09-13, clave Railway, `claude-sonnet-4-6` |
| Google Gemini (tool `google_search`) | **Sí** | `candidates[0].groundingMetadata.webSearchQueries` (lista plana), `groundingChunks[].web.{uri,title}`, `groundingSupports`. Las URIs son redirecciones `vertexaisearch.cloud.google.com/grounding-api-redirect/...`; el dominio real está en `web.title`. | No (queries y chunks en listas separadas) | 2026-09-13, clave Railway (= vault Clicandseo), `gemini-2.5-flash`, `gemini-3.8-flash`, `gemini-3.1-pro-preview` |
| Perplexity `/chat/completions` (Sonar, **se retira 2026-09-27**) | No | Solo `citations`, `search_results` y `related_questions`. | — | 2026-09-13, clave Railway, `sonar` |
| Perplexity **Agent API** (`POST /v1/agent`, `preset`) | **Sí** | `output[]` con pasos `search_results` que traen **`queries`** (lista de sub-consultas de esa ronda) y `results[]` (`url`, `title`, `snippet`, `date`). `fast` = 1 query (el prompt literal); `low` = 5 queries en 2 rondas; `medium` = 12 queries en 6 rondas + `fetch_url_results` de páginas de marca. Modelo subyacente reportado: `openai/gpt-5.6-luna`. Coste en `usage.cost`. | Sí (por ronda) | 2026-09-13, clave Railway, presets `fast`, `low`, `medium` |
| Google AI Mode / AI Overviews | **No** | Sin API. SerpAPI `engine=google_ai_mode` devuelve solo `text_blocks`, `references`, `reconstructed_markdown`. Herramientas tipo Qforia lo **simulan** con Gemini: sería una estimación, no un dato observado. | — | 2026-09-13, SerpAPI |

### Comportamiento observado (mismo prompt: "¿Cuál es el mejor software de facturación para autónomos en España?")

| Modelo | Llamadas de búsqueda | Tokens totales | Tiempo |
|---|---|---|---|
| gpt-5.5 (run 1) | 10 (7 `search`, 3 `open_page`/`find_in_page`) | 71.529 | 55 s |
| gpt-5.5 (run 2) | 11 (4 `search`, 7 páginas) | 64.778 | 48 s |
| gpt-5-mini | 7 `search` | 37.459 | 54 s |
| claude-sonnet-4-6 | 2 `search` (7 resultados cada una) | 25.989 entrada + 1.649 salida | 39 s |
| gemini-2.5-flash | 3-10 queries; con instrucción "busca siempre" hasta 18 con repetidas | ~2.300 | 7-13 s |
| gemini-3.8-flash | **No busca en 4 de 6 llamadas** si no se le ordena; con `systemInstruction` 2-3 queries | ~2.000 | 7-17 s |
| gemini-3.1-pro-preview | 1-4 queries con operadores (`"..." OR ...`, `2025 OR 2026`) | — | 23-54 s |

- **No determinista**: el mismo prompt da queries distintas en cada ejecución. Reportar frecuencias acumuladas por prompt, no una lista fija.
- OpenAI usa operadores (`site:boe.es`, `site:holded.com/es/precios`) y abre páginas concretas de las marcas (getquipu.com/es/autonomos, billin.net/precios). Decidir si el fan-out del producto son solo las `search` o también `open_page` (señal de qué URL de la marca lee el modelo).
- Algunas citas de OpenAI llevan `?utm_source=openai`: normalizar antes de agregar.
- Gemini: deduplicar `webSearchQueries`; seguir la redirección para obtener la URL final.

## 1b. Validación P1 con los modelos current (2026-09-13)

Script y respuestas crudas: `~/Desktop/proyectos/propio/clicandseo/investigacion/query-fanout-2026-09-13/p1-modelos-actuales/`
(`probe_p1.py`, `raw/*.json`, `summary.json`). Fixtures copiados a `tests/fixtures/fanout/p1-*.json`.
Modo **auto** (herramienta disponible, sin instrucción de buscar), idioma/país del proyecto en la instrucción de sistema
y en `user_location`. 5 prompts: comercial ES, informativo ES, de marca ES, local ES, comercial IT.

| Modelo (tool) | Buscó | Búsquedas | Páginas abiertas | Tokens entrada | Tokens salida | Tiempo | Coste/prompt |
|---|---|---|---|---|---|---|---|
| `gpt-5.5` (`web_search`) | 5/5 | 1-7 llamadas, **2-28 queries** (media 13) | 0-4 | 15k-75k (media 39k) | 1,1k-3,2k | 16-61 s | 0,12-0,54 USD (media **0,30**) |
| `claude-sonnet-5` (`web_search_20250305`) | 5/5 | 2 siempre (en paralelo) | 0 | 20k-23k | 1,7k-2,9k | 22-31 s | 0,08-0,09 USD |
| `claude-sonnet-5` (`web_search_20260318`, filtrado dinámico) | 2/2 | 6-16 | 0 | 37k-59k | 3,1k-3,5k | 39-51 s | 0,17-0,31 USD |
| `gemini-3.6-flash` (`google_search`) | **4/5** (no busca en el informativo) | 0-2 | 0 | 94-544 | 1,8k-3,3k | 11-23 s | 0,007-0,04 USD |
| Perplexity Agent API `low` (medido antes) | siempre | 5 en 2 rondas | 1 | 19k | 1,1k | ~20 s | 0,013 USD |

Precios usados (páginas oficiales del 2026-09-13): `gpt-5.5` 5/30 USD por 1M y web search 10 USD/1.000 llamadas + tokens del
contenido; `claude-sonnet-5` 2/10 y 10 USD/1.000 búsquedas; `gemini-3.6-flash` 0,75/3,75 y grounding 5.000 búsquedas/mes gratis
(compartidas entre Gemini 3.x) y luego 14 USD/1.000.

**Estructura real (cambios frente a §1)**
- OpenAI `gpt-5.5`: cada `web_search_call` de tipo `search` trae **`action.queries` (lista de 2-4 sub-consultas)** además de
  `action.query`; `action.sources` es por llamada, no por query. `find_in_page` trae `pattern`. Las citas finales van en
  `message.content[].annotations[]` (`url_citation`). `usage.output_tokens_details.reasoning_tokens` incluido en `output_tokens`.
- Anthropic: con `web_search_20250305` los bloques son `thinking`, `server_tool_use` (2 en paralelo), `web_search_tool_result`
  (8 resultados cada uno, atribuibles por `tool_use_id`) y muchos bloques `text` con `citations[]` (`web_search_result_location`).
  Hay que concatenar todos los `text`. `web_search_20260318` añade `code_execution_tool_result` y multiplica búsquedas y coste.
- Gemini: `groundingMetadata.webSearchQueries` + `groundingChunks` + `groundingSupports`. Las URIs de redirección se resuelven
  con un `HEAD` **sin seguir** la redirección: devuelve 302 con la URL final en `Location` en ~0,2 s.

**Decisiones técnicas que salen de P1**
- Anthropic: usar **`web_search_20250305`** (llamada directa). El filtrado dinámico triplica el coste y mezcla búsquedas hechas
  desde código, que no son comparables con las del resto de proveedores.
- Gemini en `auto` no busca en consultas informativas estables: es el comportamiento real y se registra como "no buscó".

**Coste proyectado por run** (producción hoy: **198 prompts activos, ~230 tareas por proveedor**, ~10 runs al mes; la cifra de
655 prompts de §2 incluía proyectos inactivos)

| Proveedor | Hoy (memoria, precios corregidos, aprox.) | Con búsqueda `auto` |
|---|---|---|
| OpenAI `gpt-5.5` | ~10 USD | ~68 USD |
| Anthropic `claude-sonnet-5` | ~2 USD | ~20 USD |
| Google `gemini-3.6-flash` | ~2 USD | ~4-7 USD (el grounding entra casi todo en las 5.000 gratis/mes) |
| Perplexity | ~1 USD (`fast`) | ~3 USD (`low`) |
| **Total por run** | **~15 USD** | **~95-100 USD** (~×6) |
| **Al mes (~10 runs)** | **~150 USD** | **~950-1.000 USD** |

OpenAI es el 70 % del coste con búsqueda: es el proveedor que más busca (13 queries y 39k tokens de contexto de media).

**Límites de uso de las cuentas** (cabeceras de respuesta): OpenAI 10.000 RPM y 4M TPM; Anthropic 10.000 RPM, 10M tokens de
entrada/min y 2M de salida/min. Gemini no expone límites en cabeceras. Con el paralelismo actual (hasta 24 tareas a la vez) y
~40k tokens por tarea de OpenAI, un pico ronda 1M tokens/min: dentro del límite pero sin mucho margen si crecen los prompts.

**Hallazgos colaterales corregidos en P0** (ver `CLAUDE-modelos-estado.md`): precios del registry mal en `gpt-5.5` (2,5/10 frente a
5/30), `claude-sonnet-5` (3/15 frente a 2/10) y `gemini-3.6-flash`; Gemini no contaba los tokens de razonamiento como salida;
`init_database()` forzaba `gemini-3.5-flash` como current en cada arranque.

## 1c. P3 en staging (2026-09-13, noche)

Implementado detrás de `search_mode` (código en `services/llm_providers/web_search.py` y un parser puro por provider; manual
en `CLAUDE-llm-monitoring.md` §3, §4, §8 y §9). Por REST en los tres proveedores: el SDK de Anthropic de prod (0.39) no puede
ni representar los bloques `thinking` de una respuesta con búsqueda. Primera medición real por el cron desplegado en staging
(3 prompts EN/FR × 4 LLMs, `auto`): 12/12 OK, coste 0,50 USD por prompt con los 4 proveedores (OpenAI 0,36, Claude 0,095,
Gemini 0,037, Perplexity `low` 0,009), en línea con el ×6 de P1. Con búsqueda, `sources` guarda solo las URLs citadas
(la detección de marca cuenta los enlaces como mención); todas las recuperadas quedan en el fan-out.

## 2. Cómo estaba la app antes del fan-out (2026-09-13)

- `services/llm_providers/openai_provider.py`: Chat Completions **sin tools**.
- `services/llm_providers/anthropic_provider.py`: `messages.create` **sin tools**.
- `services/llm_providers/google_provider.py`: `generate_content` **sin tools**, y usa el SDK legacy `google-generativeai==0.8.5`, cuyo `Tool` **no tiene** `google_search` (comprobado). Para grounding hay que migrar a `google-genai`.
- `services/llm_providers/perplexity_provider.py`: búsqueda nativa; guarda `citations` como `sources` (`provider: "perplexity"`).
- `sources` de openai/anthropic/google salen de `extract_urls_from_text` (regex sobre el texto; en BD `provider: "extracted"`). Muestra BD últimos 14 días: perplexity 100 % de filas con sources, google ~27 %, anthropic ~25 %, openai ~13 %.
- **Conclusión**: en tres de los cuatro proveedores la app mide hoy la memoria del modelo, no una respuesta con búsqueda. No existe ningún campo para sub-consultas porque nunca se piden.
- `llm_monitoring_results`: una fila por (project, query, provider, día) con `sources JSONB` y `execution_metadata JSONB`; UPSERT en `services/llm_monitoring/engine.py` (~línea 1016).
- Frontend: `static/js/llm_monitoring/llm-monitoring-responses.js` pinta `response.sources` ("Sources & Links"); `llm-monitoring-urls.js` + `services/llm_monitoring_stats.get_project_urls_ranking` agregan URLs. Endpoints `/projects/<id>/responses` y `/projects/<id>/urls-ranking`.
- Volumen: 22 proyectos (10 activos), 655 prompts activos, ~240 filas por proveedor y run.

## 3. Plan de implementación (pendiente de decisión de Carlos)

1. **Providers**: cada `execute_query` devuelve además `search_queries: [{type, query|url, sources:[url...]}]` y `sources` reales (no regex).
   - OpenAI: `client.responses.create(model, input, tools=[{"type":"web_search"}], include=["web_search_call.action.sources"])`. Opcional `user_location` en la tool para el locale.
   - Anthropic: `tools=[{"type":"web_search_20250305","name":"web_search","max_uses":5,"user_location":{"type":"approximate","country":<cc>}}]`.
   - Google: migrar a `google-genai`; `tools=[{"google_search":{}}]` + instrucción de sistema "busca siempre" (los 3.x deciden no buscar en muchos prompts).
   - Perplexity: migrar a Agent API (obligatorio antes del 2026-09-27, ver `CLAUDE-modelos-estado.md`) y guardar `search_results[].queries` y `results` de cada ronda.
2. **BD**: columna `search_queries JSONB` en `llm_monitoring_results` (migración `migrate_add_search_queries.py` + UPSERT). Opcional: tabla normalizada `llm_monitoring_fanout_queries (result_id, position, action_type, query, url, sources JSONB)` para agregar.
3. **Endpoints**: exponer `search_queries` en `/projects/<id>/responses`; nuevo `/projects/<id>/fanout` con sub-consultas más frecuentes por prompt / cluster, % de runs en que aparecen y cuáles citan `brand_domain` (solo atribuible en OpenAI y Anthropic).
4. **Frontend**: bloque "Búsquedas que hizo el modelo" en cada respuesta y vista agregada por prompt.
5. **Coste**: el uso de la tool se cobra aparte de los tokens. Añadir al cálculo de `cost_usd`: nº de `web_search_call` (OpenAI), `usage.server_tool_use.web_search_requests` (Anthropic), prompts con grounding (Gemini). Consultar precios vigentes antes de activar. Los tokens por prompt se multiplican por 20-30 (OpenAI) y por ~80 (Anthropic) frente a la llamada sin búsqueda.
6. **Decisión de producto previa**: activar búsqueda cambia lo que mide la app (menciones y citas con navegación frente a memoria del modelo) y el coste por run con 655 prompts × 3 proveedores. Opciones: activar para todos, solo en planes/proyectos concretos, o como segundo "modo" comparable (`search_mode` en proyecto).

## 4. Incidencias detectadas durante la investigación

- **OpenAI sin crédito** (2026-09-11 a 13): `OPENAI_API_KEY` de Railway devolvía `credit_balance_exhausted`; run del 11/09 con 38/240 errores openai (5 × 429 + 33 circuit breaker). Carlos recargó el 13/09. El health-check (`models.list`) **pasa sin crédito**, así que el cron no excluye a OpenAI y falla prompt a prompt: conviene que `test_connection` haga una llamada mínima real o que el engine detecte `insufficient_quota` y pause el proveedor.
- `gpt-5.3-chat-latest` (el que cita `CLAUDE-llm-monitoring.md` §5) está **deprecado** (404). El current real en `llm_model_registry` es `gpt-5.5` desde 2026-08-31.

## 5. Plan de trabajo propuesto (2026-09-13, pendiente de aprobación)

Objetivo de Carlos: sacar el fan-out de forma fidedigna y que la app use los modelos que los usuarios ven por defecto.

**Límite de fidelidad que hay que asumir y mostrar en la UI**: medimos la API de cada proveedor, no la app de consumo. ChatGPT/Gemini app añaden system prompt propio, memoria y personalización, y ChatGPT Free corre GPT-5.6 Luna, al que la API no nos da acceso. Etiquetar siempre "fan-out observado en la API de <proveedor> con <modelo>", nunca "lo que hizo ChatGPT".

| Fase | Qué | Por qué | Tamaño |
|---|---|---|---|
| 0. Estabilidad (esta semana) | Perplexity → Agent API (`preset fast`), guardando `search_results.queries` + `results`. Engine: detectar `insufficient_quota` y pausar proveedor + alerta. Registry: Google current → `gemini-3.6-flash`, precio Sonnet 5 → 2/10, `gpt-5.3-chat-latest` no disponible. Docs. | Sonar chat completions muere el 27/09; OpenAI se quedó sin crédito sin que nadie lo viera. | 2-3 días |
| 1. Búsqueda real en los providers | OpenAI → Responses API + `web_search` (`tool_choice: auto`, `user_location` por país). Anthropic → `web_search_20250305` + `user_location`. Google → SDK `google-genai` + `google_search`. Cada provider devuelve `search_queries`, `search_mode` y `sources` reales. Columna `search_queries JSONB` + campos en `execution_metadata` (modo, país, modelo). Tests. | Sin búsqueda no hay fan-out y las citas son regex. | 4-6 días |
| 2. Producto | Endpoint `/projects/<id>/fanout` (frecuencia de sub-consultas por prompt/cluster, % de runs, cuáles citan el dominio, comparativa por proveedor). UI: bloque en cada respuesta + vista agregada. Banner de fidelidad (modelo API vs modelo consumer). | Es lo que se vende. | 4-6 días |
| 3. Coste y cuotas | Coste por búsqueda en `cost_usd` y en el registry; unidades por prompt según modo; alerta de cost spike recalibrada; decidir plan/gating. | Tokens ×20-30 en OpenAI, ×80 en Anthropic; 655 prompts activos. | 2 días |
| 4. Modelos por defecto | Pedir acceso al preview GPT-5.6 (account rep); auto-aprobar familia Flash de Google o revisar pendientes cada semana; rellenar knowledge cutoff. | Fidelidad con lo que ve el usuario. | continuo |

**Decisiones de Carlos antes de la fase 1**
1. Modo de búsqueda: `auto` (el modelo decide, más fiel; en Gemini 3.x a veces no busca y eso se registra como dato) frente a forzada (siempre hay fan-out, menos fiel). Propuesta: `auto` + registrar "no buscó".
2. Alcance: todos los proyectos, o solo planes/proyectos concretos (`search_mode` por proyecto).
3. Repeticiones: 1 run por prompt y día (frecuencia acumulada entre días) o N runs el mismo día (coste ×N).
4. Presupuesto: aceptar el aumento de coste por run.
