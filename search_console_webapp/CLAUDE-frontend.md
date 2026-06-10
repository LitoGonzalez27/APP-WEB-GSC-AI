# CLAUDE-frontend.md — Frontend

> Manual del **frontend** del proyecto: stack vanilla JS + Jinja2, sin build system, plantillas por producto, módulos ES, charts y tablas, Quota UI.
>
> Última actualización: 2026-05-08.
>
> Manuales relacionados: `CLAUDE-manual-ai.md`, `CLAUDE-ai-mode.md`, `CLAUDE-llm-monitoring.md`, `CLAUDE-search-console.md`. Índice maestro: `CLAUDE-INDEX.md`.

---

## Índice

1. [Visión general en 5 minutos](#1-visión-general-en-5-minutos)
2. [Estructura de directorios](#2-estructura-de-directorios)
3. [Plantillas Jinja2](#3-plantillas-jinja2)
4. [Sistema de módulos JS](#4-sistema-de-módulos-js)
5. [Librerías externas (CDN)](#5-librerías-externas-cdn)
6. [CSS](#6-css)
7. [Sistema de Quota UI](#7-sistema-de-quota-ui)
8. [Sistema de Retry / Error Handling](#8-sistema-de-retry--error-handling)
9. [Charts (Chart.js)](#9-charts-chartjs)
10. [Tablas (Grid.js)](#10-tablas-gridjs)
11. [Modales](#11-modales)
12. [Sidebar / Navbar](#12-sidebar--navbar)
13. [Auto-refresh y polling](#13-auto-refresh-y-polling)
14. [Internacionalización](#14-internacionalización)
15. [Errores históricos y deuda técnica](#15-errores-históricos-y-deuda-técnica)
16. [Tests](#16-tests)

---

## 1. Visión general en 5 minutos

- **Multipage Flask app con SPA-ish dentro de cada producto.** Flask + Jinja2 sirve cada página como ruta independiente (`/`, `/login`, `/manual-ai/`, `/ai-mode-projects/`, `/api/llm-monitoring`, `/billing`...). Cada producto carga una sola plantilla pesada y dentro toma el control un sistema JS modular que cambia tabs, modales y secciones sin recargar.
- **Stack JS: Vanilla JavaScript ES2017+ con módulos ES nativos** (`<script type="module">`). **Sin React/Vue/Svelte/Angular.** Las clases JS principales (`ManualAISystem`, `AIModeSystem`, `LLMMonitoring`, `Navbar`, `SidebarNavigation`, `PaywallManager`) son `class { … }` puras.
- **No hay build process.** No existe `package.json`, `webpack.config.js`, `vite.config.js` ni `bun.lockb` (los `.js` "Bun functions" son los servicios cron en Railway, no compilación frontend). Los archivos JS y CSS se sirven tal cual desde `/static/…`. Cache-busting manual con query strings (`?v=8`, `?v=11`).
- **Templates Jinja2** clásicos. **Sin herencia** apreciable con `{% extends %}` / `{% block %}` — cada plantilla repite head/body porque el "shell" se duplica para cada producto. Variables al frontend: `user`, `authenticated`, `has_shared_access`, `access_blocked`, `upgrade_options`, `recaptcha_site_key`.
- **GTM `GTM-NXJS74ZQ`** se carga en casi todas las plantillas para analítica.

**Reglas de oro:**

1. **Sin build system**: debugging directo en DevTools, sin source maps, sin minificación.
2. **Cada producto tiene su entry-point JS**. Manual AI / AI Mode están modularizados; LLM Monitoring sigue monolítico (8.785 líneas).
3. **`window.QuotaUI` es el único módulo JS verdaderamente compartido** entre los 3 productos. El resto vive en su silo.
4. **Las restricciones por plan se hacen al clickar** (paywall modal) o vía `access_blocked` en backend. El menú HTML es el mismo para todos.
5. **No hay i18n**: la app es principalmente inglés con islas en español.

---

## 2. Estructura de directorios

```
templates/                  # 20 plantillas Jinja2 (root del repo)
static/                     # Frontend
├── *.css                   # ~37 archivos CSS planos (sin subcarpetas)
├── manifest.json
├── admin-fix-llm.html      # HTML "huérfano" servido como estático
├── images/
│   ├── favicons/
│   ├── logos/
│   └── social/
└── js/
    ├── *.js                # ~50 scripts vanilla
    ├── manual-ai/          # 11 submódulos del Manual AI (modular nuevo)
    │   └── manual-ai-{utils,core,projects,keywords,analysis,charts,
    │                    competitors,analytics,modals,exports,clusters}.js
    │   + manual-ai-clusters.js.backup2 + 6 .md de migración
    └── ai-mode-projects/   # 11 submódulos del AI Mode
        └── ai-mode-{utils,core,projects,keywords,analysis,charts,
                     competitors,analytics,modals,exports,clusters}.js
```

### Archivos JS más importantes (por tamaño / centralidad)

| Archivo | Líneas |
|---|---:|
| `static/js/llm_monitoring.js` | **8.785** (monolítico) |
| `static/js/manual-ai-system.js` | 5.449 (legacy, NO se carga) |
| `static/js/ui-render.js` | 2.560 |
| `static/js/app.js` | 1.801 |
| `static/js/manual-ai/manual-ai-analytics.js` | 1.660 |
| `static/js/ui-keywords-gridjs.js` | 1.527 |
| `static/js/ai-mode-projects/ai-mode-analytics.js` | 1.413 |
| `static/js/sidebar-navigation.js` | 1.216 |
| `static/js/quota-ui.js` | 437 |
| `static/js/manual-ai-system-modular.js` | 357 |
| `static/js/ai-mode-system-modular.js` | 348 |

---

## 3. Plantillas Jinja2

Total: **20 plantillas** (todas en root, sin subcarpetas). **No hay `/templates/email/` ni `/templates/admin/`** — los emails se construyen en código Python.

| Plantilla | Tamaño | Para qué sirve |
|---|---|---|
| `index.html` | 63 KB | Página `/app`: dashboard principal (GSC + AI Overview) con sidebar interno. Carga DataTables + Chart.js + Grid.js. |
| `index_tooltips_fixed.html` | 45 KB | Variante (probablemente legacy). |
| `dashboard.html` | 35 KB | Renderizado por `/dashboard` (tras login). Página puente. |
| `landing.html` | 8 KB | Marketing landing pública. |
| `login.html` | 21 KB | Login (Google OAuth + email/password + reCAPTCHA). |
| `signup.html` | 20 KB | Registro nuevo usuario. |
| `forgot_password.html` | 12 KB | Solicitar reset. |
| `reset_password.html` | 14 KB | Establecer nueva contraseña. |
| `manual_ai_dashboard.html` | 110 KB / 1.973+ líneas | Manual AI Analysis (tabs Projects, Keywords, Analytics, Modals). |
| `ai_mode_dashboard.html` | 104 KB | AI Mode Monitoring. |
| `llm_monitoring.html` | 144 KB / 2.473+ líneas | LLM Monitoring (GPT/Claude/Gemini/Perplexity). |
| `paywall_manual_ai.html` | 9 KB | Paywall para usuarios free intentando entrar a Manual AI. |
| `billing.html` | 10 KB | Gestión de suscripción Stripe (sin Stripe.js cliente; redirección al portal/checkout). |
| `billing_success.html` | 12 KB | Página de éxito tras checkout Stripe. |
| `admin_simple.html` | 121 KB | Panel admin general (Carlos). |
| `admin_billing.html` | 36 KB | Panel admin específico de billing. |
| `user_profile.html` | 74 KB | Perfil del usuario. |
| `project_access.html` | 17 KB | Gestión de acceso compartido a proyectos. |
| `mobile_error.html` | 7 KB | Bloqueo en móvil (la app no soporta móvil). |

**`email_preview.html`** (en root, no `/templates/`) es solo un mockup HTML estático — no es Jinja real.

---

## 4. Sistema de módulos JS

### 4.1 Manual AI (modular, en producción)

**Entry point**: `static/js/manual-ai-system-modular.js` (importado como `<script type="module">` en `manual_ai_dashboard.html:1809`).

Patrón:

```js
import { ManualAISystem } from './manual-ai/manual-ai-core.js';
import { loadProjects, renderProjects, … } from './manual-ai/manual-ai-projects.js';
// + 9 imports más
Object.assign(ManualAISystem.prototype, {
    escapeHtml, debounce, loadProjects, renderProjects,
    analyzeProject, runAnalysis, renderVisibilityChart, …
});
window.ManualAISystem = ManualAISystem;
// DOMContentLoaded → window.manualAI = new ManualAISystem()
```

**11 submódulos** en `static/js/manual-ai/`:

| Módulo | Líneas | Responsabilidad |
|---|---:|---|
| `manual-ai-utils.js` | 209 | `htmlLegendPlugin`, `escapeHtml`, `debounce`, `getDomainLogoUrl` (Logo.dev → Google s2 → Icon Horse → favicon directo), `isValidDomain`, `normalizeDomainString`, toasts, score utils. |
| `manual-ai-core.js` | 667 | `class ManualAISystem`, `init`, `clearObsoleteCache`, `cacheElements`, `setupEventListeners`, `setupAutoRefresh` (cada 2 min), config Chart.js, progress bar, toasts. |
| `manual-ai-projects.js` | 696 | CRUD proyectos, `loadProjects`, `renderProjects`, `pauseProject`, `resumeProject`, `deleteProjectPermanently`, validaciones de dominio, chips de competidores. |
| `manual-ai-keywords.js` | 285 | Keywords CRUD. |
| `manual-ai-analysis.js` | 203 | `analyzeProject` (POST con `AbortController` timeout 30 min) + manejo de 402 (paywall) y 429 (`quota_exceeded` → llama a `window.QuotaUI.showBlockModal`). |
| `manual-ai-charts.js` | 547 | `renderVisibilityChart`, `renderPositionsChart`, `createEventAnnotations`, `drawEventAnnotations`. Pinta canvas custom encima del chart. |
| `manual-ai-competitors.js` | 339 | Form chips, validación, charts comparativos. |
| `manual-ai-analytics.js` | **1.660** | La más grande. Top Domains, Global Domains Ranking, Top URLs, AI Overview Keywords (Grid.js), Comparative Charts, AIO vs Organic. |
| `manual-ai-modals.js` | 837 | Modal de proyecto, tabs internos (Settings, Keywords, Access). |
| `manual-ai-exports.js` | 250 | Excel + PDF. |
| `manual-ai-clusters.js` | 758 | Configuración y stats de topic clusters. |

**Convivencia legacy**: `static/js/manual-ai-system.js` (5.449 líneas) sigue en disco pero **no se carga**. La plantilla solo carga el modular. Hay un `manual-ai-clusters.js.backup2` y 6 markdown de progreso (`README.md`, `STATUS.md`, `SUMMARY.md`, `REFACTORING_PLAN.md`, `REFACTORING_COMPLETE.md`, `PROGRESS_CHECKPOINT.md`) en `static/js/manual-ai/`.

### 4.2 AI Mode (modular, en producción)

Misma arquitectura. Entry point `static/js/ai-mode-system-modular.js`. 11 submódulos en `static/js/ai-mode-projects/` con prefijo `ai-mode-`.

**Diferencias notables:**

- `analytics` tiene `showNoAiModeUrlsMessage`, `initAiModeUrlsFilter`, `filterAiModeUrlsByBrand` (por marca, no por dominio).
- `analyzeProject` (`ai-mode-analysis.js`) implementa **polling backup**: arranca un `setInterval` cada 30 s (línea 27) que hace `loadProjects()` y compara `total_results`. Para si detecta análisis completado o pasados 600 000 ms (10 min). Red de seguridad ante errores de red.
- Llama a `Chart.register(htmlLegendPlugin)` global tras DOMContentLoaded.

### 4.3 LLM Monitoring (monolítico)

**`static/js/llm_monitoring.js` — 8.785 líneas en una sola `class LLMMonitoring`. NO está modularizado.**

Mantiene state interno (`comparisonGrid`, `queriesGrid`, `historyChart`, paginación, chips de brand/competitors 1-4, `globalTimeRange`, `planLimits`, modal de confirm). Construye sus propios toast (`.llm-toast`) y modales nativos.

Cargado como **script clásico** (no `type="module"`) en `llm_monitoring.html:1791`. Pendiente de modularización (deuda).

### 4.4 Globals compartidos

| Global | Para qué |
|---|---|
| `window.QuotaUI` | Interfaz pública del módulo de cuota (ver §7). |
| `window.currentUser = { email, plan, role, has_shared_access }` | Inyectado por la plantilla. |
| `window.manualAI`, `window.aiModeSystem`, `window.navbar` | Instancias creadas en DOMContentLoaded. |
| `window.DISABLE_SIDEBAR_NAVIGATION = true` | Flag puesto por Manual AI / AI Mode para que `SidebarNavigation` no monte. |
| `window.initManualAIComponents` / `window.initAIModeComponents` | Hooks que la plantilla define y el módulo llama al final de la inicialización. |

> ⚠️ `window.QuotaUIShared` mencionado en docs históricas **no existe** en el código. Solo `window.QuotaUI`.

---

## 5. Librerías externas (CDN)

Cargadas vía `<script src="https://…">` directamente en cada plantilla. **No hay bundler.**

| Librería | Versión / CDN | Dónde |
|---|---|---|
| **Chart.js** | `cdn.jsdelivr.net/npm/chart.js` (latest) | index, manual-ai, ai-mode, llm-monitoring |
| **Grid.js** | `unpkg.com/gridjs/dist/gridjs.umd.js` + tema `mermaid.min.css` | manual-ai, ai-mode, llm-monitoring, index |
| **Font Awesome** | 6.0.0 (manual-ai/ai-mode/llm) y 6.4.0 (index) `cdnjs.cloudflare.com` | todas las plantillas |
| **jQuery** | 3.7.0 `code.jquery.com` | **solo `index.html`** |
| **DataTables** | 1.13.6 `cdn.datatables.net` | **solo `index.html`** (el dashboard de GSC) |
| **Google reCAPTCHA v3** | `google.com/recaptcha/api.js?render=…` | login.html, signup.html |
| **GTM** | `GTM-NXJS74ZQ` | landing, index, manual-ai, ai-mode, llm-monitoring, login, signup |
| **Inter Tight + Libre Baskerville** (Google Fonts) | `fonts.googleapis.com` | landing |
| **Logo.dev** | `img.logo.dev/{domain}?token=pk_a4PP_KI7Qj-y6MnQSvu-3A` | usado en `getDomainLogoUrl`. Fallbacks: Google s2 favicons, icon.horse, favicon directo |

**No usa**: Bootstrap, Tailwind, Vue, React, Stripe.js (cliente), Sentry. Stripe se gestiona 100% backend (los botones de upgrade redirigen a `/billing/checkout/...` Flask).

---

## 6. CSS

37 archivos CSS planos en `static/`. **Sin preprocesador**. Algunos tienen cache-busting `?v=N`.

| Archivo | KB | Para qué sirve |
|---|---|---|
| `estilos-principales.css` | 53 | Estilos globales del dashboard `/app`. |
| `base-y-componentes.css` | 35 | Reset + componentes (botones, cards, formularios). |
| `manual-ai.css` | 127 | Manual AI dashboard. Reutilizada por `paywall_manual_ai.html` y `billing.html`. |
| `llm-monitoring.css` | 117 | Estilos LLM Monitoring (`?v=8`). |
| `llm-monitoring-enhanced.css` | 19 | Refinamientos LLM (`?v=1`). |
| `ai-overview-section.css` | 39 | Sección AI Overview en `/app`. |
| `serp-modal.css` | 42 | Modal SERP. |
| `paywall.css` | 25 | Paywall genérico. |
| `keywords-section.css` | 41 | Sección keywords. |
| `tablas.css` | 27 | Tablas (compartido). |
| `modulos-especificos.css` | 44 | Estilos específicos de módulos. |
| `gridjs-styles.css` | 16 | Override del tema Grid.js. |
| `auth.css` | 15 | Auth pages. |
| `login.css` | 20 | Login específico. |
| `signup.css` | 9 | Signup específico. |
| `quota-ui.css` | 6 | Modales y banners de cuota. |
| `sov-metrics-ui.css` | 24 | Métricas Share of Voice (LLM). |
| `clusters-styles.css` | 10 | Topic clusters. |
| `navbar.css` | 19 | Navbar superior global. |
| `sidebar-navigation.css` | 10 | Sidebar lateral del dashboard. |
| `modales-datos.css` | 5 | Modales de datos compartidos. |
| `responsive-enhancements.css` | 9 | Tweaks responsive. |
| `billing-success.css` | 9 | Página tras checkout. |

Otros: `overview-section.css`, `pages-section.css`, `search-performance-styles.css`, `date-selector.css`, `response-modal.css`, `modal-progreso.css`, `aio-recommendations-modal.css`, `ai-overlay-styles.css`, `ai-typology-chart.css`, `ai-reset-styles.css`, `analysis-mode-styles.css`.

---

## 7. Sistema de Quota UI

### Archivos

- **CSS**: `static/quota-ui.css` (6 KB).
- **JS**: `static/js/quota-ui.js` (437 líneas, **no es módulo ES**; expone vía `window.QuotaUI`).

### Constantes

```js
QUOTA_MESSAGES = {
    softLimit: { /* 80% */ },
    hardLimit: { /* 100% */ },
    freeBlocked: { /* free no puede acceder */ },
    enterpriseBlocked: { /* contacto support */ }
}
UPGRADE_URLS = {
    free:       '/billing',
    basic:      '/billing/checkout/premium',
    premium:    '/billing/checkout/business',
    enterprise: '/contact'
}
```

### API expuesta en `window.QuotaUI`

| Método | Qué hace |
|---|---|
| `showWarning(quotaInfo)` | Banner modal preventivo. **Deshabilitado**: solo dispara si `>= 100%`. |
| `showBlockModal(errorData)` | Modal de bloqueo con CTA "Upgrade Now" o "Contact Support". |
| `handleApiError(response, data)` | Detecta `status===429 && data.quota_blocked`, dispara modal y devuelve `true`. |
| `quotaAwareFetch(url, options)` | Wrapper de `fetch` que tira `Error('QUOTA_BLOCKED')` si detecta bloqueo. |
| `checkStatus()` | Al cargar la página llama a `GET /api/quota/status`. |

### Disparadores adicionales

`window.dispatchEvent(new CustomEvent('quotaWarning'/'quotaBlocked', {detail:…}))`.

### Dismiss persistente por sesión

`sessionStorage.setItem('quotaWarningDismissed:<plan>:<used>:<limit>', '1')`.

### Activación

Solo se activa en rutas `manual-ai`, `ai-mode`, `ai-mode-projects`, `llm-monitoring` (función `isPaidFeatureSection`) y solo si `plan !== 'free'`.

### Integraciones

- `static/js/manual-ai/manual-ai-analysis.js:105`.
- `static/js/ai-mode-projects/ai-mode-analysis.js:105`.
- `static/js/ui-ai-overview-analysis.js:372`.
- `static/js/manual-ai-system.js:1381` (legacy).

> ⚠️ **LLM Monitoring (`llm_monitoring.js`) NO usa `QuotaUI`** — tiene su propio sistema de toasts y modales. Inconsistencia.

---

## 8. Sistema de Retry / Error Handling

### Backend retry (NO frontend)

El sistema de retry de LLM providers está implementado en backend (`services/llm_providers/retry_handler.py` con decorator `@with_retry`). El frontend solo recibe el resultado. Documentado en `IMPLEMENTACION_RETRY.md`, `IMPLEMENTACION_RETRY_SYSTEM.md`, `ANALISIS_RETRY_SYSTEM.md`.

### Polling backup en frontend

En `ai-mode-projects/ai-mode-analysis.js:27-53`:
- `setInterval(…, 30000)` cada 30 s.
- Recarga proyectos y compara `total_results > before`.
- Para si detecta completado o pasados 600.000 ms (10 min).

Replicado en `manual-ai/manual-ai-analysis.js`.

### AbortController + timeout 30 min

`manual-ai-analysis.js` y `ai-mode-analysis.js` envuelven el `fetch` con `AbortController` y timeout de 1.800.000 ms (30 min) para que la petición no se quede colgada eternamente.

### Recuperación tras errores de red mid-análisis

Si hay `Failed to fetch` / `ERR_NETWORK_CHANGED` ya en mitad del análisis, el frontend hace `await loadProjects()` para chequear si el backend completó pese al error de red, y muestra "Analysis may have completed despite network error".

### Toast / notificaciones — 3 implementaciones distintas

| Sistema | Implementación |
|---|---|
| **Manual AI / AI Mode** | `_showToastUI` en core (top-right, color por tipo, `setTimeout` 5s). |
| **Sidebar** | `_sidebarShowToast` en `sidebar-navigation.js`. |
| **LLM Monitoring** | `showToast` con clase `.llm-toast-{type}` y close button. |
| **Quota** | Modales bloqueantes (`quota-warning-modal-overlay`, `quota-block-modal-overlay`). |

> Deuda: 3 sistemas distintos de toast para hacer lo mismo.

---

## 9. Charts (Chart.js)

### Plugin custom `htmlLegendPlugin`

Definido en `static/js/manual-ai/manual-ai-utils.js:10` (y duplicado en `static/js/ai-mode-projects/ai-mode-utils.js`).

Genera la leyenda como `<ul>` HTML en un container externo (`getOrCreateLegendList(chart, id)`), con click handlers que togglean `dataset.visibility` o `dataVisibility` para pies/donuts, y caja de color con borde redondeado.

- AI Mode: registrado globalmente con `Chart.register(htmlLegendPlugin)` en `ai-mode-system-modular.js:335`.
- Manual AI: pasado per-chart vía `plugins: [htmlLegendPlugin]`.

### Tipos de gráficos

- `line` — visibility, positions.
- `bar` — compare visibility.
- `doughnut` — clusters distribution.
- `scatter` — comparativa de posiciones.

LLM Monitoring tiene además `historyChart` (línea de mention rate temporal) en el modal.

### Anotaciones de eventos custom

`createEventAnnotations`, `drawEventAnnotations` en `manual-ai-charts.js`. **No usan plugin oficial** (`chartjs-plugin-annotation`); hacen `ctx.beginPath()/stroke()` manual sobre el `chart.ctx` para pintar líneas verticales con icono y label en hover.

`getEventColor`/`getEventIcon` mapean tipos de eventos (`keywords_added`, `keywords_removed`, `competitor_added`, `manual_note`).

### Config base

Centralizada en `ManualAISystem.prototype.getModernChartConfig(useHtmlLegend, legendId)`:
- `responsive: true`.
- `maintainAspectRatio: false`.
- `interaction: { mode: 'index', intersect: false }`.
- Ejes con `grid.color: 'rgba(0,0,0,0.05)'`, ticks `font: 11px Inter`.

### Charts almacenados

`this.charts.{visibility, positions, comparativeVisibility, comparativePosition, …}` y destruidos con `.destroy()` antes de re-renderizar (limpieza de listeners de annotations primero con `clearEventAnnotations`).

---

## 10. Tablas (Grid.js)

### Setup

- Tema **`mermaid`** (`unpkg.com/gridjs/dist/theme/mermaid.min.css`).
- Override en `static/gridjs-styles.css`.
- 12+ instancias de `new gridjs.Grid({…})` en el repo.

### Patrón de re-render

```js
grid.updateConfig({ data: () => safeData }).forceRender()
```

### Patrón de hard rebuild

Cuando hay riesgo de stale state (`manual-ai-analytics.js:923`), reemplaza el nodo container completo (`replaceWith(newDiv)`) antes de instanciar nuevo `Grid`.

### Bug histórico (`FIX_GRIDJS_ERROR.md`, 2025-11-06)

- **Síntoma**: el endpoint `/api/llm-monitoring/projects/:id/comparison` no devolvía `total_mentions`. Al renderizar, la línea 1358 hacía `(item.total_mentions || 0)/(item.total_queries || 0)` con `undefined`.
- **Error**: `TypeError: Cannot read properties of undefined (reading 'length')` × 4.
- **Fix**: añadir `'total_mentions': c.get('total_mentions') or 0` al JSON del endpoint.

---

## 11. Modales

> **No hay sistema modal compartido.** Cada producto tiene el suyo.

| Sistema | Implementación |
|---|---|
| **Manual AI / AI Mode** | Clase CSS `.modal-overlay` (definida en `manual-ai.css:592`) + helpers `showElement`/`hideElement` y `hideAllModals()` en core. Los HTML de los modales están **inline en la plantilla**. |
| **LLM Monitoring** | Modales propios definidos inline en `llm_monitoring.html` y manejados con `class .modal-overlay` y métodos `openModal`/`closeModal`. Tiene además un *custom confirm* (`confirmResolver`) que retorna `Promise<bool>`. |
| **Quota UI** | Crea modales **dinámicamente** con `document.createElement('div')` y los inyecta en `body`, con styles incluidos vía `<style id="quota-modal-styles">` (función `ensureQuotaModalStyles`). |
| **Paywall** | `static/js/paywall.js` `class PaywallManager.showPaywallModal(upgradeOptions, featureName)` también inyecta dinámicamente. Auto-close en 30 s o click outside. |

**`static/modales-datos.css`** (5 KB) tiene los estilos compartidos de modales-de-datos del dashboard `/app`.

---

## 12. Sidebar / Navbar

### Navbar — `static/js/navbar.js` (741 líneas)

- `class Navbar` instanciada como `window.navbar`.
- Maneja: logo, menú móvil (hamburger), dropdown usuario (avatar, nombre, email), botones login/logout, toggle theme dark/light.
- 3 versiones del logout button: `logoutBtn`, `mobileLogoutBtn`, `dropdownLogoutBtn`.
- Cargado en TODAS las plantillas que necesiten navbar como script clásico (no module).

### Sidebar interno (solo `/app`) — `static/js/sidebar-navigation.js` (1.216 líneas)

- `class SidebarNavigation` con secciones fijas: `['configuration', 'performance', 'keywords', 'pages', 'ai-overview']`.
- Status dots (pending/running/complete) con animaciones.
- Móvil: `sidebarMobileOverlay` + `mobileSidebarToggle`.

### Bypass por flag

En `manual_ai_dashboard.html` (y `ai_mode_dashboard.html`) se setea `window.DISABLE_SIDEBAR_NAVIGATION = true` antes del DOMContentLoaded para que esta clase no se inicialice (Manual AI tiene su propia navegación interna).

### Permisos por plan

- El menú visible es el **mismo HTML para todos**.
- Las restricciones se hacen al *clickar* (paywall modal) o vía `access_blocked` en backend.
- En las plantillas se inyecta `window.currentUser = { plan, role, has_shared_access }` y el JS comprueba `window.currentUser.plan !== 'free'`.
- En la plantilla, si `access_blocked == True` (free sin shared access), Jinja renderiza un overlay `.llm-access-blocked-overlay` que cubre la página (visible en `manual_ai_dashboard.html:62-101`).

---

## 13. Auto-refresh y polling

| Caso | Frecuencia | Condiciones |
|---|---|---|
| **Auto-refresh de proyectos** (Manual AI / AI Mode) | Cada 2 min | Solo si `currentTab === 'projects'` Y (`plan !== 'free'` O `has_shared_access`). |
| **Polling backup durante análisis** (AI Mode) | Cada 30 s | Hasta 10 min timeout. Se desactiva al completar. |
| **Quota status** | 1× al cargar | No polling. |

---

## 14. Internacionalización

> ⚠️ **No hay i18n implementado.** No se usa `flask-babel`, `gettext`, ni `_()`. No hay archivos `.po`/`.mo`.

- La app es **principalmente inglés** en UI (mensajes de error, botones, títulos), pero hay strings y comentarios en español mezclados.
- `<html lang="es">` solo en `dashboard.html`, `login.html`, `admin_simple.html`. Resto en `lang="en"`.
- Formateo de fechas localizado a `'es-ES'` solo en 2 sitios. Resto usa `'en-US'`.
- DataTables tiene language URL apuntando a `en-GB.json`.

---

## 15. Errores históricos y deuda técnica

### Documentos `.md` con info frontend

- `FIX_GRIDJS_ERROR.md` — bug Grid.js descrito en §10.
- `static/js/manual-ai/{README.md, STATUS.md, SUMMARY.md, REFACTORING_PLAN.md, REFACTORING_COMPLETE.md, PROGRESS_CHECKPOINT.md}` — documentan la refactorización **frontend** Manual AI.
- `manual_ai/MIGRATION_COMPLETE.md`, `REFACTORING_GUIDE.md`, `SAFE_MIGRATION.md`, `COMPLETION_SUMMARY.md`, `README.md` — refactorización **backend** Manual AI.

### Cosas raras vivas en el repo

| Artefacto | Estado |
|---|---|
| `static/js/manual-ai-system.js` (5.449 líneas, monolítico legacy) | **No se carga** pero sigue en disco. Su `.backup` también. |
| `static/js/manual-ai/manual-ai-clusters.js.backup2` | Backup intermedio durante migración. |
| `templates/index_tooltips_fixed.html` (45 KB) | Variante de `index.html`, presunta versión alternativa. |
| `static/admin-fix-llm.html` | HTML estático servido desde `/static/`, no Jinja. |
| `static/ai-overview-section.css` + `static/ai-overlay-styles.css` + `static/ai-typology-chart.css` + `static/ai-reset-styles.css` | 5 archivos CSS de la sección AI del dashboard, fragmentación heredada. |
| `console-silencer.js` (2.4 KB) | Silencia logs verbosos del console (legacy o anti-noise). |
| `debug-logger.js`, `debug-number-formatting.js`, `session-manager-test.js` | Scripts de debug presentes pero no siempre cargados. |

### Deuda técnica

| Deuda | Impacto | Riesgo |
|---|---|---|
| **`llm_monitoring.js` monolítico** (8.785 líneas) | Pendiente de modularizar como Manual AI / AI Mode. | Alto. |
| **3 sistemas de toast distintos** | Inconsistencia UX. | Medio. |
| **LLM Monitoring no usa `window.QuotaUI`** | Implementación duplicada. | Medio. |
| **Sin build system / sin minificación** | Performance / seguridad (todo el código fuente expuesto). | Medio. |
| **Sin source maps** | Debugging más difícil. | Bajo. |
| **Sin tests JS** (Jest/Mocha/Vitest) | No hay tests funcionales del frontend. | Alto. |
| **Sin i18n** | Limita expansión a otros idiomas. | Medio. |
| **CSS sin preprocesador**, 37 archivos | Fragmentación. | Medio. |
| **Plantillas sin herencia Jinja**, head/body duplicados | DRY broken. | Bajo. |

---

## 16. Tests

### Tests "estáticos" en Python

| Archivo | Cubre |
|---|---|
| `test_llm_monitoring_frontend.py` (385 líneas aprox.) | **Test estático**: verifica que existan `templates/llm_monitoring.html`, `static/js/llm_monitoring.js`, `static/llm-monitoring.css`, y que el HTML contenga ciertos strings (`<!DOCTYPE html>`, `Chart.js`, `Grid.js`). **No es funcional**, solo valida presencia y tamaño. |
| `verify_manual_ai_js.sh` y `verify_manual_ai_refactoring.py` | Verifican que la refactorización Manual AI conserva todos los métodos del prototipo (matching de nombres entre el monolítico y los submódulos modulares). |

### Sin framework JS de testing

> ⚠️ **No hay** Jest, Mocha, Vitest, ni Playwright. **No hay `package.json`**. Tests funcionales del frontend = manuales.

`tests/` (carpeta) — solo tests de servicios Python LLM (`test_llm_monitoring_e2e.py`, `…performance.py`, `…service.py`, `…providers.py`).

---

## TL;DR

1. **Multipage Flask + Jinja2 + Vanilla JS ES2017+** con módulos ES nativos. Sin React/Vue/build system.
2. **3 olas de frontend conviven**:
   - Legacy (`index.html` con jQuery + DataTables).
   - Moderna modularizada (Manual AI + AI Mode con 11 submódulos cada uno).
   - Moderna monolítica (`llm_monitoring.js` 8.785 líneas, pendiente de modularizar).
3. **Sin build system**: archivos servidos tal cual desde `/static/`. Cache-busting manual con `?v=N`.
4. **`window.QuotaUI` es el único módulo verdaderamente compartido** entre los 3 productos. El resto vive en su silo.
5. **Charts con Chart.js**, tablas con Grid.js (tema `mermaid`), modales inline por producto, plugin custom `htmlLegendPlugin`.
6. **Polling backup en análisis manual**: 30s × 10 min como red de seguridad.
7. **`AbortController` con timeout 30 min** para `fetch` de análisis.
8. **Sin i18n**: principalmente inglés con islas en español.
9. **Sin tests JS**: solo tests "estáticos" en Python que verifican existencia de archivos.
10. **Deuda principal**: modularizar LLM Monitoring, unificar toasts, integrar Quota UI en LLM, añadir tests funcionales.

— Fin del manual —
