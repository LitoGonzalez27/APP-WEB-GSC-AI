# CLAUDE-brand-radar.md — Brand Radar (NO es producto interno)

> Manual breve sobre **Brand Radar**: aclaración definitiva de que **NO es un producto interno** de la app, sino un conjunto de herramientas MCP externas de Ahrefs disponibles desde la sesión de Claude.
>
> Última actualización: 2026-05-08.
>
> Manuales relacionados: `CLAUDE-llm-monitoring.md` (que es el producto interno equivalente), `CLAUDE-integraciones.md` (otras MCP). Índice maestro: `CLAUDE-INDEX.md`.

---

## TL;DR

**Brand Radar NO es un producto del SaaS ClicandSEO.** No existe código fuente, modelo de datos, rutas Flask, frontend, ni cron asociado. Las únicas apariciones de "Brand Radar" en el repo son menciones en documentación que precisamente confirman que se refiere a las **herramientas MCP externas de Ahrefs** disponibles en la sesión de Claude.

**Si una futura sesión de Claude lee esto: no busques código de Brand Radar — no existe.**

---

## 1. ¿Qué es Brand Radar en este proyecto?

Es un **producto de Ahrefs** (la SaaS de SEO) llamado precisamente "Ahrefs Brand Radar". Mide cómo aparece una marca en respuestas de LLMs según los datos que **Ahrefs** recopila por su cuenta.

Carlos puede consultar Brand Radar **desde una sesión de Claude** (vía MCP de Ahrefs), pero **la web app de ClicandSEO no integra Brand Radar de ninguna forma**:

- Cero código `services/brand_radar*` o similar.
- Cero tablas `brand_radar_*` en la BD.
- Cero rutas Flask `/brand-radar/...`.
- Cero plantillas o JS frontend.
- Cero cron asociado.
- Cero variables de entorno `AHREFS_*`.

---

## 2. Verificación exhaustiva en el repo

Búsquedas realizadas en `/Users/carlosgonzalez/Desktop/app/APP-WEB-GSC-AI/search_console_webapp/`:

| Búsqueda | Resultado |
|---|---|
| Archivos `brand_radar*`, `brandradar*`, `brand-radar*` | **0** |
| Contenido `brand[ _-]radar`, `brandradar`, `BrandRadar` (case-insensitive) | 2 archivos `.md` (solo documentación) |
| Tablas `brand_radar_*` en SQL/migrations | **0** |
| Rutas Flask `/brand-radar/...` | **0** |
| Servicios `services/brand_radar*` | **0** |
| Templates `templates/brand_radar*.html` | **0** |
| Crons `daily_brand_radar*` | **0** |
| Env vars `AHREFS_*` | **0** |
| Cliente HTTP / SDK de Ahrefs | **0** (ningún `import` ni `requests` a `api.ahrefs.com`) |

### Las 3 únicas menciones en docs

| Archivo | Línea | Contexto |
|---|---:|---|
| `CLAUDE-INDEX.md` | 50 | Placeholder de manual pendiente: *"Brand Radar (Ahrefs MCP): módulos de citaciones, share of voice, impresiones, menciones — confirmar si es producto interno o sólo integración externa."* |
| `CLAUDE-llm-monitoring.md` | 886-888 | *"No es parte del módulo LLM Monitoring. 'Brand Radar' en este repo se refiere a las herramientas MCP de Ahrefs (servicio externo independiente), no al módulo LLM. No hay integración entre ambos."* |
| `CLAUDE-llm-monitoring.md` | 1084 | TL;DR: *"Brand Radar no es parte de LLM Monitoring (es Ahrefs MCP externo)."* |

### Otras menciones de "Ahrefs" en código

Solo aparecen como **strings de prueba** (competidores de ejemplo en tests):

- `tests/test_llm_monitoring_service.py` (líneas 81, 88, 125, 133, 144, 156, 162): `competitors=["Semrush", "Ahrefs"]` como fixture.
- `services/llm_monitoring_service.py:2377`: docstring con el mismo ejemplo.
- `llm_monitoring_routes.py:608`: `"competitor_keywords": ["semrush", "ahrefs"]` — keywords de detección de competidores en respuestas LLM.

**Ninguna indica integración con la API de Ahrefs.** Son simplemente el nombre de la marca como competidor en datos de demo.

### Directorio `brandbook/`

Existe pero **no tiene nada que ver** con Brand Radar. Es el styleguide visual de la marca **ClicandSEO** (logos SVG, `brand-tokens.css`, `Brandbook.md`, `brand-styleguide.html`, PDF comercial). Cero menciones de "radar" o "MCP" en este dir.

---

## 3. Herramientas MCP de Ahrefs disponibles

Cargadas en la sesión de Claude bajo el namespace `mcp__63aa9431-6a58-47b2-94d4-47263dcb780b__`. Las herramientas relacionadas con Brand Radar son:

### Brand Radar core (12 tools, par "main" + variante "entities")

| Tool | Para qué |
|---|---|
| `brand-radar-ai-responses` / `-entities` | Respuestas AI donde aparece la marca. |
| `brand-radar-cited-domains` / `-entities` | Dominios citados por LLMs. |
| `brand-radar-cited-pages` / `-entities` | Páginas concretas citadas. |
| `brand-radar-impressions-history` / `-entities` | Histórico de impresiones AI. |
| `brand-radar-impressions-overview` / `-entities` | Resumen de impresiones. |
| `brand-radar-mentions-history` / `-entities` | Histórico de menciones. |
| `brand-radar-mentions-overview` / `-entities` | Resumen de menciones. |
| `brand-radar-sov-history` / `-entities` | Histórico de Share of Voice. |
| `brand-radar-sov-overview` / `-entities` | Resumen SoV. |

### Management asociado

| Tool | Para qué |
|---|---|
| `management-brand-radar-prompts` | Prompts configurados en Brand Radar (en Ahrefs). |
| `management-brand-radar-reports` | Reports configurados en Ahrefs. |

### Para qué se usan

Son herramientas de **consulta a la plataforma Ahrefs Brand Radar** (producto SaaS de Ahrefs). Permiten leer telemetría sobre cómo aparece una marca en respuestas de LLMs según los datos que **Ahrefs** recopila por su cuenta.

**No tienen nada que ver con `llm_monitoring_*` interno** (que sí ejecuta los análisis con APIs de OpenAI/Anthropic/Google/Perplexity y persiste en BD propia).

---

## 4. Brand Radar (Ahrefs) vs LLM Monitoring (interno)

| Dimensión | Brand Radar (Ahrefs) | LLM Monitoring (interno) |
|---|---|---|
| **Origen de datos** | Ahrefs (SaaS externo) | APIs de OpenAI / Anthropic / Google / Perplexity (directas) |
| **Coste** | Suscripción a Ahrefs | Tokens de cada LLM |
| **Cómo se accede** | Tools MCP en sesión de Claude | UI propia en `/llm-monitoring` + cron diario automático |
| **Persistencia** | Datos en Ahrefs | Tablas `llm_monitoring_*` en nuestra BD |
| **Configurable por usuario final** | No (Carlos opera ad-hoc desde Claude) | Sí (cada usuario configura proyectos, prompts, modelos) |
| **Histórico** | El que mantenga Ahrefs | El que escribimos en `llm_monitoring_results` y `llm_monitoring_snapshots` |
| **Frecuencia** | Cuando Carlos lo consulte | Diario automático |

> **Carlos NO tiene producto interno Brand Radar.** Si quiere "Brand Radar" propio, **es LLM Monitoring** (que ya está construido). Si quiere los datos de Brand Radar de Ahrefs, los consume desde Claude.

---

## 5. ¿Tiene sentido construir Brand Radar interno?

Posibles escenarios futuros:

### Opción A — Reusar LLM Monitoring (actual)

LLM Monitoring **ya hace lo que hace Brand Radar conceptualmente**: monitorizar cómo aparece la marca en respuestas LLM. Las diferencias son:

- **Ahrefs Brand Radar** es passive — Ahrefs recolecta datos por su cuenta y los expone.
- **LLM Monitoring** es active — el sistema lanza prompts configurados a mano contra los LLMs.

Si Carlos quiere "lo mismo que Brand Radar pero propio", **ya lo tiene**.

### Opción B — Consumir Ahrefs API e integrarla

Tendría sentido si Carlos quiere:
- Mostrar a sus clientes datos que Ahrefs ya recopila (sin disparar prompts propios).
- Pagar Ahrefs por enriquecimiento.

Requeriría:
- Env var `AHREFS_API_KEY`.
- Servicio `services/ahrefs_brand_radar.py`.
- Tablas `brand_radar_results`, `brand_radar_snapshots`, etc.
- Cron diario `daily_brand_radar_cron.py`.
- Bun service `function-bun-Brand-Radar`.
- UI propia.

**Esto sería un proyecto grande** (similar a LLM Monitoring pero sin el motor de prompts).

### Opción C — No hacer nada

La opción actual: las tools MCP de Ahrefs siguen disponibles cuando Carlos abre Claude para análisis ad-hoc. No hay integración formal en la app.

---

## 6. Para una futura sesión de Claude

Si una futura sesión llega aquí buscando "Brand Radar":

1. **No busques código de Brand Radar dentro de la app**. No existe.
2. Si el usuario pide "construir Brand Radar":
   - Pregunta si lo que quiere es **realmente algo distinto a LLM Monitoring**.
   - Si la respuesta es "sí, quiero los datos de Ahrefs Brand Radar dentro de mi app", es un proyecto nuevo desde cero (Opción B arriba).
   - Si la respuesta es "quiero que mis clientes vean lo que aparece de su marca en LLMs", **ya está hecho** — es LLM Monitoring (`CLAUDE-llm-monitoring.md`).
3. Si el usuario pide "consultar Brand Radar":
   - Usa las tools MCP `mcp__63aa9431-...__brand-radar-*` directamente.
   - No hay endpoint de la app que lo encapsule.

---

## 7. Resumen ejecutivo

| Pregunta | Respuesta |
|---|---|
| ¿Brand Radar es un producto del SaaS ClicandSEO? | **No.** |
| ¿Hay código de Brand Radar en este repo? | **No.** |
| ¿Hay tabla, ruta, cron, frontend, env var? | **Nada.** |
| ¿Qué es Brand Radar entonces? | Un producto de Ahrefs accesible vía MCP desde sesiones de Claude. |
| ¿Qué tiene Carlos equivalente dentro de su app? | LLM Monitoring (`CLAUDE-llm-monitoring.md`). |
| ¿Hace falta construir Brand Radar interno? | Probablemente no — LLM Monitoring ya cubre el caso de uso. |

— Fin del manual —
