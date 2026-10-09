/**
 * CLICANDSEO — Agent Readiness (panel del Agent-Ready Scanner)
 *
 * Sustituye al single-page oscuro de agent_scanner/web/index.html, que vivía
 * fuera del esqueleto de la app. Mismo comportamiento y mismas garantías que
 * aquel (están blindadas en agent_scanner/selftest.py, que lee este archivo):
 *
 *  - El sondeo distingue un 429 (nuestro limitador: se reintenta más despacio)
 *    de un 404 (el análisis ya no existe) y espacia las peticiones.
 *  - Al abandonar la página con un análisis en curso se avisa por sendBeacon
 *    para que el servidor corte el hilo.
 *  - Con tipologías mezcladas la comparativa NO corona a nadie.
 *  - El aviso de acceso degradado sale del veredicto (level.name / level.msg),
 *    informa sin alarmar y ofrece el prompt de rescate.
 *  - La simulación agéntica se lanza bajo demanda y nunca se afirma completada
 *    si no lo está (lo decide el backend).
 *
 * Novedades: historial de informes (antes la API existía pero la UI no la
 * usaba, y un informe de ayer no se podía reabrir porque /status ya no lo
 * conoce), pestaña de accesos para admins y pantalla de espera didáctica.
 *
 * Vanilla JS sin módulos, como el resto de paneles. Iconos con
 * <i data-lucide> + lucide.createIcons().
 */
(function () {
    'use strict';

    /* ───────────────────────────── utilidades ───────────────────────────── */

    const $ = (q, root) => (root || document).querySelector(q);
    const $$ = (q, root) => Array.from((root || document).querySelectorAll(q));
    // escapado único de la app (static/js/html-escape.js, cargado antes que este)
    const esc = window.ClicandseoHtml.escapeHtml;
    const ic = (name, cls) => `<i data-lucide="${name}"${cls ? ` class="${cls}"` : ''}></i>`;
    const pct = v => Math.round((v || 0) * 100);
    const APP = $('#agApp');
    const IS_ADMIN = APP && APP.dataset.isAdmin === 'true';

    let iconTimer = null;
    function refreshIcons() {
        clearTimeout(iconTimer);
        iconTimer = setTimeout(() => {
            if (window.lucide && typeof window.lucide.createIcons === 'function') {
                window.lucide.createIcons({ attrs: { 'stroke-width': 2 } });
            }
        }, 0);
    }

    function cssVar(name, fallback) {
        const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
        return v || fallback;
    }

    // Paleta de datos del brandbook. Slot 1 = tu web, siempre. Los
    // competidores van en violeta y magenta (slots 4 y 6) y no en aqua/naranja:
    // el verde, el naranja y el rojo quedan reservados para el semáforo de
    // estado (bien / regular / mal), y un color de serie nunca puede parecer
    // un color de estado (Brandbook § Paleta de datos).
    const SERIES = [
        cssVar('--cs-series-1', '#2a78d6'),
        cssVar('--cs-series-4', '#4a3aa7'),
        cssVar('--cs-series-6', '#e87ba4'),
    ];
    const C = {
        text: cssVar('--cs-text-primary', '#0F172A'),
        text2: cssVar('--cs-text-secondary', '#64748B'),
        text3: cssVar('--cs-text-tertiary', '#94A3B8'),
        grid: cssVar('--cs-chart-grid', '#EEF2F7'),
        border: cssVar('--cs-border', '#E2E8F0'),
        ok: cssVar('--cs-success', '#3CB371'),
        bad: cssVar('--cs-error', '#E05252'),
        accent: cssVar('--cs-accent', '#d9f9b8'),
        okText: cssVar('--cs-success-text', '#287A4C'),
        badText: cssVar('--cs-error-text', '#D13B3B'),
        warn: '#FF9A3C',          // naranja vivo y claro del semáforo (ver agent-scanner.css)
        warnText: '#A55409',
    };
    // Semáforo: ≥75 bien, 50-74 regular, <50 mal (porcentajes de categoría).
    const toneOf = p => (p >= 75 ? 'good' : p >= 50 ? 'warn' : 'bad');
    // Nota global por tramos de la escala: 0-50 mal, 51-75 regular, 76-100 bien.
    const scoreTone = s => (s > 75 ? 'good' : s > 50 ? 'warn' : 'bad');
    const TONE_HEX = { good: C.ok, warn: C.warn, bad: C.bad };
    const TONE_TEXT = { good: C.okText, warn: C.warnText, bad: C.badText };

    function fmtDate(iso) {
        if (!iso) return '';
        const d = new Date(iso);
        if (isNaN(d)) return String(iso).slice(0, 10);
        return d.toLocaleDateString('es-ES', { day: 'numeric', month: 'short', year: 'numeric' });
    }

    function fmtDateTime(iso) {
        if (!iso) return '';
        const d = new Date(iso);
        if (isNaN(d)) return String(iso).slice(0, 16).replace('T', ' ');
        return d.toLocaleDateString('es-ES', { day: 'numeric', month: 'short' }) + ' · '
            + d.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
    }

    const TYPOLOGY = { ecommerce: 'E-commerce', saas: 'SaaS', corporativo: 'Corporativo' };
    const AGENT_NAMES = { chatgpt: 'ChatGPT', claude: 'Claude', gemini: 'Gemini', perplexity: 'Perplexity' };
    // El motor guarda los nombres de check sin tildes ("robots.txt valido");
    // el catálogo los tiene bien escritos y es la fuente de verdad del texto.
    const CHECK_NAMES = {};
    const CATALOG_P = fetch('/agent/api/catalog').then(r => r.json()).then(d => {
        (d.categorias || []).forEach(g => g.factores.forEach(f => { CHECK_NAMES[f.id] = f.nombre; }));
        return d;
    }).catch(() => ({ categorias: [] }));
    const nameOf = c => CHECK_NAMES[c.id] || c.name;
    const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`;
    const typ = t => TYPOLOGY[t] || t || '—';

    /* ───────────────────────────── catálogo ───────────────────────────── */

    const CATS = {
        C1: 'Descubribilidad y acceso', C2: 'Identidad y control de bots', C3: 'Datos estructurados',
        C4: 'Renderizado y arquitectura', C5: 'Contenido para LLMs', C6: 'Capacidades y acciones',
        C7: 'Comercio agéntico'
    };
    const CAT_DESC = {
        C1: '¿Pueden los sistemas de IA encontrarte y entrar? Mide robots.txt, sitemap, bloqueos reales del firewall y acceso sin login.',
        C2: '¿Controlas qué bots entran y qué pueden hacer? Mide Content Signals, gestión del crawl y verificación de identidad de agentes.',
        C3: '¿Tus datos están marcados para que la IA no tenga que adivinar? Mide JSON-LD, tu entidad de marca, atributos de producto y HTML semántico.',
        C4: '¿Tu contenido existe sin ejecutar JavaScript y responde rápido? Es lo que ven los rastreadores de ChatGPT, Claude o Perplexity, que no ejecutan JS.',
        C5: '¿Tu contenido está escrito para ser citado? Mide respuesta directa, secciones autocontenidas, autoría verificable y versión Markdown.',
        C6: '¿Ofreces capacidades que un agente pueda usar, no solo leer? Mide MCP/A2A, APIs y formularios operables.',
        C7: '¿Puede un asistente de compra vender tus productos? Mide catálogo estructurado, fiabilidad de precios y checkout agéntico (ACP).'
    };
    const IMPORD = {
        'Crítico': 0, 'Alto': 1, 'Alto (apuesta de futuro)': 1, 'Alto (ventana de oportunidad)': 1,
        'Medio': 2, 'Medio (creciente)': 2, 'Bajo': 3, 'Bajo (hoy)': 3, 'Diagnóstico': 4
    };
    /* metodología de cada check (matriz de fiabilidad y detalle check a check) */
    const METHODS = {
        '1.1': 'GET /robots.txt y validación de sintaxis (texto plano parseable, no HTML)',
        '1.2': 'Parseo de reglas por user-agent de IA; penaliza bloquear los bots de búsqueda en vivo',
        '1.3': 'Peticiones reales con el UA oficial de cada bot, contrastadas con lo declarado en robots.txt',
        '1.4': 'GET de sitemap(s) e índices, conteo de URLs y frescura de lastmod (<90 días)',
        '1.5': 'Inspección de cabeceras Link (RFC 8288) en la respuesta HTTP',
        '1.6': 'Fetch anónimo de las páginas muestreadas: ¿hay contenido útil sin sesión?',
        '1.7': 'Consulta DNS TXT a _aid/_agent con dig (estándar experimental)',
        '2.1': 'Parseo de Content Signals (search / ai-input / ai-train) en robots.txt',
        '2.2': 'Detección de CDN/WAF por cabeceras + respuestas 402 observadas a bots',
        '2.3': 'GET /.well-known/http-message-signatures-directory con validación JWKS',
        '2.4': '10 peticiones consecutivas como GPTBot: patrón de códigos de respuesta',
        '3.1': 'Extracción y parseo de todos los bloques JSON-LD de las páginas muestreadas',
        '3.2': 'Validación de campos de Organization/LocalBusiness en la home',
        '3.3': 'Validación de Product/Offer (price, priceCurrency, availability) en fichas',
        '3.4': 'Conteo de atributos ricos (GTIN, brand, rating, fechas…) en el marcado',
        '3.5': 'Análisis del DOM: jerarquía de headings, landmarks, button vs div-onclick',
        '3.6': 'Conteo de div/span clicables sin semántica vs controles nativos y mitigados (role+tabindex)',
        '4.1': 'Comparación del texto visible: HTML crudo (curl) vs renderizado con JS (Camoufox)',
        '4.2': 'Búsqueda de precio y CTA de compra sobre el HTML sin ejecutar JS',
        '4.3': 'TTFB medido con curl en todas las páginas muestreadas',
        '4.4': 'GET directo y sin sesión de cada URL profunda muestreada',
        '4.5': 'Sondeo de /openapi.json, /swagger.json y /api-docs',
        '4.6': 'CLS vía PageSpeed Insights API (requiere --psi y key en el vault)',
        '5.1': 'Análisis determinista del bloque tras el H1: densidad de datos vs léxico de relleno',
        '5.2': 'Sección a sección H2/H3: título descriptivo + cuerpo 25-450 palabras + saltos de jerarquía',
        '5.3': 'Autoría y fechas verificables en schema/HTML de los artículos muestreados',
        '5.5': 'GET /llms.txt y /llms-full.txt con validación de contenido (anti soft-404)',
        '5.6': 'Petición real con Accept: text/markdown y análisis del Content-Type/cuerpo devuelto',
        '6.1': 'Sondeo de 12 rutas agénticas (MCP/A2A/OAuth/Skills) con validación de contenido',
        '6.2': 'Análisis por formulario: vinculación for=id verificada contra los id reales, autocomplete, submit real y CAPTCHA. No se envían formularios (ética)',
        '6.3': 'ChatGPT, Gemini y Claude pilotan un navegador real, varias pasadas por agente para medir consistencia. En e-commerce: producto→carrito→checkout con datos de contacto y envío rellenos. Los campos de tarjeta están bloqueados por código: nunca se paga, nunca se crean cuentas. El envío de formularios solo ocurre una vez y solo en el dominio del cliente, con autorización expresa',
        '7.1': 'Detección de plataforma e-commerce + Product schema en las fichas muestreadas',
        '7.2': 'Comparación del precio del JSON-LD contra el precio visible de la misma ficha',
        '7.3': 'Detección de PSP compatible con ACP (Stripe / Shopify)',
        '7.4': 'Sondeo informativo de x402/UCP/MPP + señales HTTP 402 (no puntúa, tampoco en Cloudflare)'
    };
    const CHECK_LINKS = {
        '1.1': '/robots.txt', '1.2': '/robots.txt', '2.1': '/robots.txt',
        '1.4': '/sitemap.xml', '5.5': '/llms.txt', '2.3': '/.well-known/http-message-signatures-directory'
    };
    const STAGES = [
        { name: '¿Te leen?', desc: 'Acceso y rastreo', cats: ['C1', 'C2'] },
        { name: '¿Te entienden?', desc: 'Datos y contenido', cats: ['C3', 'C4', 'C5'] },
        { name: '¿Pueden usarte?', desc: 'Acciones y compra', cats: ['C6', 'C7'] }
    ];
    const TIERS = [
        { ord: 0, title: 'Crítico', hint: 'Está frenando a los agentes hoy. Arreglar lo primero.' },
        { ord: 1, title: 'Importante', hint: 'Alto impacto en tu visibilidad y en la capacidad de ser usado.' },
        { ord: 2, title: 'Mejoras recomendadas', hint: 'Suman puntos y pulen la experiencia del agente.' },
        { ord: 3, title: 'Menor', hint: 'Poca urgencia: para cuando el resto esté hecho.' }
    ];
    const SCALE = [
        { from: 0, to: 25, name: 'Invisible para agentes' },
        { from: 26, to: 50, name: 'Legible, no operable' },
        { from: 51, to: 75, name: 'Agent-aware' },
        { from: 76, to: 100, name: 'Agent-ready' }
    ];
    const bandOf = s => (s <= 25 ? 0 : s <= 50 ? 1 : s <= 75 ? 2 : 3);

    /* ───────────────────────────── tooltips ─────────────────────────────
       Cualquier elemento con data-tip="Título||Explicación". */
    const tipBox = document.createElement('div');
    tipBox.className = 'ag-tooltip';
    tipBox.setAttribute('role', 'tooltip');
    document.body.appendChild(tipBox);
    document.addEventListener('pointermove', e => {
        const t = e.target && e.target.closest ? e.target.closest('[data-tip]') : null;
        if (t && t.dataset.tip) {
            const [head, ...rest] = t.dataset.tip.split('||');
            tipBox.innerHTML = `<b>${esc(head)}</b>` + (rest.length ? esc(rest.join('||')) : '');
            const w = Math.min(tipBox.offsetWidth || 300, 320), h = tipBox.offsetHeight || 60;
            let x = e.clientX + 16, y = e.clientY + 18;
            if (x + w > innerWidth - 12) x = e.clientX - w - 16;
            if (y + h > innerHeight - 12) y = e.clientY - h - 14;
            tipBox.style.left = x + 'px';
            tipBox.style.top = y + 'px';
            tipBox.style.opacity = 1;
        } else if (!(document.activeElement && document.activeElement.closest && document.activeElement.closest('[data-tip]'))) {
            tipBox.style.opacity = 0;
        }
    });
    // Teclado: el mismo detalle al enfocar (las burbujas del mapa son enfocables)
    document.addEventListener('focusin', e => {
        const t = e.target.closest && e.target.closest('[data-tip]');
        if (!t) { tipBox.style.opacity = 0; return; }
        const [head, ...rest] = t.dataset.tip.split('||');
        tipBox.innerHTML = `<b>${esc(head)}</b>` + (rest.length ? esc(rest.join('||')) : '');
        const r = t.getBoundingClientRect(), w = Math.min(tipBox.offsetWidth || 300, 320);
        let x = r.right + 12, y = r.top;
        if (x + w > innerWidth - 12) x = Math.max(12, r.left - w - 12);
        tipBox.style.left = x + 'px';
        tipBox.style.top = Math.max(12, y) + 'px';
        tipBox.style.opacity = 1;
    });
    document.addEventListener('focusout', () => { tipBox.style.opacity = 0; });

    /* ───────────────────────────── vistas ───────────────────────────── */

    const VIEWS = ['#agHome', '#agRunning', '#agReport', '#agMissing'];
    function show(view) {
        VIEWS.forEach(v => { const el = $(v); if (el) el.hidden = v !== view; });
        window.scrollTo({ top: 0, behavior: 'auto' });
        refreshIcons();
    }

    function setUrl(params, replace) {
        const qs = new URLSearchParams(params).toString();
        const url = '/agent/' + (qs ? '?' + qs : '');
        if (url === location.pathname + location.search) return;
        history[replace ? 'replaceState' : 'pushState'](null, '', url);
    }

    function switchTab(name, opts) {
        const tab = $(`[data-ag-tab="${name}"]`) ? name : 'nuevo';
        $$('[data-ag-tab]').forEach(b => {
            const on = b.dataset.agTab === tab;
            b.classList.toggle('active', on);
            b.setAttribute('aria-selected', on ? 'true' : 'false');
            b.tabIndex = on ? 0 : -1;
        });
        $$('#agHome .tab-content').forEach(s => s.classList.toggle('active', s.id === 'agTab-' + tab));
        show('#agHome');
        if (!(opts && opts.keepUrl)) setUrl(tab === 'nuevo' ? {} : { tab }, opts && opts.replace);
        if (tab === 'informes') loadHistory();
        if (tab === 'accesos') loadAccess();
    }

    document.addEventListener('click', e => {
        const t = e.target.closest('[data-ag-tab]');
        if (t) { switchTab(t.dataset.agTab); return; }
        const g = e.target.closest('[data-ag-goto]');
        if (g) { switchTab(g.dataset.agGoto); }
    });

    /* ───────────────────────────── nuevo análisis ───────────────────────────── */

    $('#agCats').innerHTML = Object.entries(CATS).map(([k, v]) => `
        <label class="ag-check">
            <input type="checkbox" class="ag-box" value="${k}" checked data-cat-toggle>
            <span><span class="ag-cid">${k}</span>${esc(v)}</span>
        </label>`).join('');

    $('#agOptAgents').addEventListener('change', e => {
        $('#agRowSubmit').hidden = !e.target.checked;
        $('#agRowReps').hidden = !e.target.checked;
        if (!e.target.checked) $('#agOptSubmit').checked = false;
    });

    const catToggle = c => $(`#agCats input[value="${c}"]`);
    const facsOf = c => $$(`.ag-fac-item input[data-cat="${c}"]`);

    function updateFacSummary() {
        const all = $$('.ag-fac-item input[data-cat]');
        const on = all.filter(i => i.checked).length;
        const el = $('#agFacSummary');
        if (!all.length) {
            const cats = $$('#agCats input:checked').length;
            el.textContent = cats === 7 ? 'Auditoría completa' : `${cats} de 7 categorías`;
            return;
        }
        el.textContent = on === all.length ? 'Auditoría completa' : `${on} de ${all.length} factores`;
    }

    function syncGroup(cat) {          // hijos -> cabecera de grupo + casilla de categoría
        const kids = facsOf(cat), on = kids.filter(k => k.checked).length;
        const head = $(`#agGrp-${cat}`), chip = catToggle(cat);
        if (head) { head.checked = on === kids.length && on > 0; head.indeterminate = on > 0 && on < kids.length; }
        if (chip && kids.length) { chip.checked = on > 0; chip.indeterminate = on > 0 && on < kids.length; }
        const cnt = $(`#agCnt-${cat}`);
        if (cnt) cnt.textContent = `${on}/${kids.length}`;
        updateFacSummary();
    }
    function setCat(cat, val) {        // categoría -> todos sus hijos
        facsOf(cat).forEach(k => { k.checked = val; });
        syncGroup(cat);
    }

    CATALOG_P.then(d => {
        const groups = (d.categorias || []).filter(g => g.factores.length);
        const total = groups.reduce((n, g) => n + g.factores.length, 0);
        $('#agFacCount').textContent = total;
        $('#agFacList').innerHTML = groups.map(g => `
            <div class="ag-fac-group">
                <div class="ag-fac-head">
                    <input type="checkbox" class="ag-box" id="agGrp-${g.categoria}" data-group="${g.categoria}" checked>
                    <label for="agGrp-${g.categoria}">${g.categoria} · ${esc(g.nombre)}</label>
                    <span class="ag-fac-count" id="agCnt-${g.categoria}">${g.factores.length}/${g.factores.length}</span>
                </div>
                ${g.factores.map(f => `
                <div class="ag-fac-item">
                    <input type="checkbox" class="ag-box" id="agFac-${f.id}" data-cat="${g.categoria}" value="${f.id}" checked>
                    <label for="agFac-${f.id}"><span class="ag-fid">${f.id}</span>${esc(f.nombre)}
                        <span class="ag-fdesc">${esc(f.descripcion)}</span></label>
                </div>`).join('')}
            </div>`).join('');
        updateFacSummary();
        if (!groups.length) $('#agFacList').innerHTML = '<p class="ag-help">No se pudo cargar la lista de factores. Puedes lanzar el análisis igualmente: se comprobarán las categorías marcadas.</p>';
    });

    document.addEventListener('change', e => {
        const chip = e.target.closest('#agCats input[data-cat-toggle]');
        if (chip) { setCat(chip.value, chip.checked); updateFacSummary(); return; }
        const head = e.target.closest('input[data-group]');
        if (head) { setCat(head.dataset.group, head.checked); return; }
        const fac = e.target.closest('.ag-fac-item input[data-cat]');
        if (fac) syncGroup(fac.dataset.cat);
    });
    $('#agFacAll').addEventListener('click', e => { e.preventDefault(); Object.keys(CATS).forEach(c => { setCat(c, true); const t = catToggle(c); if (t) { t.checked = true; t.indeterminate = false; } }); updateFacSummary(); });
    $('#agFacNone').addEventListener('click', e => { e.preventDefault(); Object.keys(CATS).forEach(c => { setCat(c, false); const t = catToggle(c); if (t) { t.checked = false; t.indeterminate = false; } }); updateFacSummary(); });

    $('#agGo').addEventListener('click', async () => {
        const urls = ['#agU0', '#agU1', '#agU2'].map(q => $(q).value.trim()).filter(Boolean);
        const err = $('#agErr');
        if (!$('#agU0').value.trim()) { err.textContent = 'Escribe la URL de tu web para empezar.'; $('#agU0').setAttribute('aria-invalid', 'true'); $('#agU0').focus(); return; }
        // factores concretos seleccionados; si el catálogo no cargó, se cae a categorías
        const checks = $$('.ag-fac-item input[data-cat]:checked').map(i => i.value);
        const cats = checks.length
            ? [...new Set($$('.ag-fac-item input[data-cat]:checked').map(i => i.dataset.cat))]
            : $$('#agCats input:checked').map(i => i.value);
        if (!cats.length) { err.textContent = 'Marca al menos un factor o categoría a analizar.'; return; }
        const btn = $('#agGo');
        btn.disabled = true;
        err.textContent = '';
        const payload = {
            urls, cats, checks, render: $('#agOptRender').checked, type: $('#agTyp').value || null,
            agents: $('#agOptAgents').checked,
            allow_submit: $('#agOptAgents').checked && $('#agOptSubmit').checked,
            ua_googlebot: $('#agOptGooglebot').checked,
            agent_reps: parseInt($('#agOptReps').value || '3', 10)
        };
        try {
            const r = await fetch('/agent/api/scan', {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
            });
            const j = await r.json();
            if (!r.ok) throw new Error(j.error || 'error');
            setUrl({ job: j.id });
            startRunning(j.id, urls, { ids: new Set(checks), cats: new Set(cats) });
        } catch (e) {
            showFormError(e.message);
        } finally {
            btn.disabled = false;
        }
    });

    /* El backend responde "URL no permitida (x): el dominio no resuelve: x".
       Se traduce a qué falló y qué hacer, y se marca el campo afectado. */
    function showFormError(raw) {
        const err = $('#agErr');
        ['#agU0', '#agU1', '#agU2'].forEach(q => { $(q).removeAttribute('aria-invalid'); });
        const m = String(raw || '').match(/URL no permitida \(([^)]*)\):\s*(.*)$/);
        if (m) {
            const field = ['#agU0', '#agU1', '#agU2'].map(q => $(q)).find(i => i.value.trim() === m[1]);
            if (field) { field.setAttribute('aria-invalid', 'true'); field.focus(); }
            const why = /no resuelve|resolve/i.test(m[2])
                ? 'No encontramos ese dominio. Revisa que esté bien escrito, por ejemplo https://tumarca.com.'
                : /privad|interna|local/i.test(m[2])
                    ? 'Es una dirección interna o privada: solo se pueden analizar webs públicas.'
                    : m[2];
            err.textContent = `«${m[1]}»: ${why}`;
            return;
        }
        if (/en curso/i.test(raw)) { err.textContent = 'Ya hay un análisis en marcha. Espera a que termine o cancélalo desde su pantalla.'; return; }
        err.textContent = 'No pudimos lanzar el análisis: ' + raw;
    }
    ['#agU0', '#agU1', '#agU2'].forEach(q => $(q).addEventListener('input', e => {
        e.target.removeAttribute('aria-invalid');
        if ($('#agErr').textContent) $('#agErr').textContent = '';
    }));

    /* ───────────────────────────── análisis en curso ─────────────────────────────
       Si el usuario abandona (cierra, recarga, vuelve atrás) se avisa al servidor
       para que corte el trabajo: corre en un hilo que si no seguiría gastando red
       y bloqueando el siguiente análisis. sendBeacon se entrega aunque la página
       se esté descargando. */
    let ANALISIS_EN_CURSO = null, JUST_FINISHED = null;
    function cancelarAnalisis() {
        if (!ANALISIS_EN_CURSO) return;
        try { navigator.sendBeacon('/agent/api/cancel/' + ANALISIS_EN_CURSO); } catch (e) { /* nada */ }
        ANALISIS_EN_CURSO = null;
    }
    // pagehide cubre cerrar pestaña, navegar fuera y el botón "atrás"
    window.addEventListener('pagehide', cancelarAnalisis);
    window.addEventListener('beforeunload', cancelarAnalisis);

    $('#agCancel').addEventListener('click', () => {
        const b = $('#agCancel');
        if (b.dataset.confirm !== '1') {
            b.dataset.confirm = '1';
            b.classList.add('btn-danger-confirm');
            b.innerHTML = `${ic('x')} ¿Cancelar de verdad?`;
            refreshIcons();
            setTimeout(() => {
                if (b.dataset.confirm === '1') {
                    b.dataset.confirm = '0';
                    b.classList.remove('btn-danger-confirm');
                    b.innerHTML = `${ic('x')} Cancelar análisis`;
                    refreshIcons();
                }
            }, 4000);
            return;
        }
        b.dataset.confirm = '0';
        b.classList.remove('btn-danger-confirm');
        b.innerHTML = `${ic('x')} Cancelar análisis`;
        const id = ANALISIS_EN_CURSO;
        ANALISIS_EN_CURSO = null;
        if (id) fetch('/agent/api/cancel/' + id, { method: 'POST' }).catch(() => {});
        stopLearn();
        switchTab('nuevo');
    });

    /* Radar sin degradados: un barrido de cuñas planas con opacidad decreciente
       (textura por opacidad, Brandbook §15) que gira, y ecos que parpadean. */
    function drawRadar() {
        const svg = $('#agRadar');
        if (!svg || svg.childNodes.length) return;
        const cx = 120, cy = 120, R = 112;
        const pt = (deg, r) => {
            const a = (deg - 90) * Math.PI / 180;
            return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
        };
        const wedge = (a0, a1) => {
            const [x0, y0] = pt(a0, R), [x1, y1] = pt(a1, R);
            return `M${cx},${cy} L${x0.toFixed(2)},${y0.toFixed(2)} A${R},${R} 0 0 1 ${x1.toFixed(2)},${y1.toFixed(2)} Z`;
        };
        let s = '';
        [112, 84, 56, 28].forEach(r => { s += `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="rgba(255,255,255,0.12)" stroke-width="1"/>`; });
        s += `<line x1="8" y1="${cy}" x2="232" y2="${cy}" stroke="rgba(255,255,255,0.06)"/>`;
        s += `<line x1="${cx}" y1="8" x2="${cx}" y2="232" stroke="rgba(255,255,255,0.06)"/>`;
        let sweep = '';
        const ops = [0.22, 0.16, 0.11, 0.07, 0.04, 0.02];
        ops.forEach((o, i) => { sweep += `<path d="${wedge(-(i + 1) * 9, -i * 9)}" fill="${C.accent}" fill-opacity="${o}"/>`; });
        const [ex, ey] = pt(0, R);
        sweep += `<line x1="${cx}" y1="${cy}" x2="${ex.toFixed(2)}" y2="${ey.toFixed(2)}" stroke="${C.accent}" stroke-width="2" stroke-linecap="round"/>`;
        s += `<g class="ag-radar-sweep">${sweep}</g>`;
        // ecos: aparecen cuando el barrido pasa por su ángulo (3s por vuelta)
        [[52, 70], [148, 92], [236, 58], [305, 98], [110, 34]].forEach(([deg, r]) => {
            const [x, y] = pt(deg, r);
            s += `<circle class="ag-radar-blip" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3.5" fill="${C.accent}" style="animation-delay:${(deg / 360 * 3).toFixed(2)}s"/>`;
        });
        s += `<circle cx="${cx}" cy="${cy}" r="3" fill="${C.accent}"/>`;
        svg.innerHTML = s;
    }

    /* «Mientras esperas» sigue al análisis en directo. El motor no dice en qué
       factor está, pero cada paso escribe una línea fija en el registro
       (engine.py: "robots.txt…", "sitemap…", "render de la home…"). Cada paso
       se asocia aquí a los factores cuyos DATOS recoge (qué claves de ctx lee
       cada check en checks.py y qué paso las rellena en engine.py).
       Ojo: ningún factor se puntúa durante la recogida; todos se evalúan juntos
       al final (checks.run_all). Por eso la tarjeta dice «datos recogidos», no
       «revisado», y muestra la evaluación como último paso. Un factor tiene sus
       datos cuando empieza un paso POSTERIOR al suyo (los pasos condicionales
       que se saltan, como el render, no bloquean). Orden = orden del motor. */
    const LIVE_STEPS = [
        { re: /(^|:\s*)robots\.txt/i, ids: ['1.1', '1.2', '2.1'] },
        { re: /sitemap/i, ids: ['1.4'] },
        { re: /(^|:\s*)home…/i, ids: ['1.5', '1.8', '3.2', '3.5'] },
        { re: /matriz de acceso/i, ids: ['1.3', '2.2'] },
        { re: /superficie agéntica/i, ids: ['2.3', '4.5', '5.5', '6.1', '7.4'] },
        { re: /muestreo/i, ids: ['1.6', '3.1', '3.4', '4.3', '4.4', '4.9', '5.1', '5.2', '5.3', '5.8', '6.2'] },
        { re: /fichas de producto/i, ids: ['3.3', '4.2', '7.1', '7.2', '7.3', '7.5', '7.6'] },
        { re: /render de la home/i, ids: ['3.6', '4.1'] },
        { re: /zonas de clic en otras/i, ids: ['4.7'] },
        { re: /área de acceso/i, ids: ['6.4'] },
        { re: /estados de error/i, ids: ['4.8'] },
        { re: /markdown|dns-aid/i, ids: ['1.7', '5.6'] },
        { re: /wikidata|páginas de confianza/i, ids: ['3.7', '5.7'] },
        { re: /vista LLM|jina/i, ids: ['4.6'] },
        { re: /pruebas agénticas/i, ids: [] },
        { re: /rate limiting/i, ids: ['2.4'] }
    ];
    // Solo puntúan en e-commerce (checks.py: 3.3, 4.2 y C7 salvo 7.4)
    const ECOM_ONLY = ['3.3', '4.2', '7.1', '7.2', '7.3', '7.5', '7.6'];
    const CAT_KEYS = Object.keys(CATS);
    const catOfId = id => 'C' + String(id).split('.')[0];
    let CATALOG = null, LEARN_IDX = 0, LEARN_MANUAL_UNTIL = 0, LOG_OPEN = false;
    // selección del lanzamiento ({ids, cats}); null = todo (p. ej. al retomar un análisis tras recargar)
    let LIVE_SEL = null;
    const nuevoLive = (domain, host) => ({ domain, done: new Set(), current: [], step: '', host, last: -1, typ: null, fichas: false, finished: false });
    let LIVE = nuevoLive(-1, '');

    function resetLive() { LIVE = nuevoLive(-1, ''); }

    /* Por qué un factor no cuenta en este análisis ('' = sí cuenta). */
    function skipOf(f) {
        if (f.id === '6.3') return 'se completa aparte';
        if (LIVE_SEL && (LIVE_SEL.ids.size ? !LIVE_SEL.ids.has(f.id) : !LIVE_SEL.cats.has(catOfId(f.id)))) return 'no seleccionado';
        if (ECOM_ONLY.includes(f.id) && LIVE.typ && LIVE.typ !== 'ecommerce' && !LIVE.fichas) return 'no aplica: no es e-commerce';
        return '';
    }
    const enJuego = () => Object.values(CATALOG || {}).flat().filter(f => !skipOf(f));

    function updateLive(s) {
        const domains = s.domains || [];
        let idx = domains.findIndex(d => d.state === 'running');
        if (idx < 0) idx = domains.length - 1;
        if (idx !== LIVE.domain) LIVE = nuevoLive(idx, (domains[idx] || {}).host || '');
        const log = s.log || [];
        // solo las líneas del dominio en curso: empiezan en su "robots.txt…"
        let start = 0;
        for (let k = log.length - 1; k >= 0; k--) { if (LIVE_STEPS[0].re.test(log[k])) { start = k; break; } }
        const seg = log.slice(start);
        const typLine = seg.find(l => /tipología:\s*\S/i.test(l));
        if (typLine) LIVE.typ = typLine.replace(/^.*tipología:\s*/i, '').trim().toLowerCase();
        LIVE.fichas = seg.some(l => /fichas de producto/i.test(l));
        if ((domains[idx] || {}).state === 'done') {
            enJuego().forEach(f => LIVE.done.add(f.id));
            LIVE.current = []; LIVE.step = ''; LIVE.finished = true;
            return;
        }
        let last = -1, lastLine = '';
        seg.forEach(line => {
            const k = LIVE_STEPS.findIndex(r => r.re.test(line));
            if (k > last) { last = k; lastLine = line; }
        });
        if (last < 0) return;
        LIVE.last = last;
        LIVE_STEPS.slice(0, last).forEach(st => st.ids.forEach(id => LIVE.done.add(id)));
        LIVE.current = LIVE_STEPS[last].ids.filter(id => !LIVE.done.has(id));
        LIVE.step = lastLine.replace(/^[^:]*:\s*(?=\S)/, m => (m.includes('.') ? '' : m)).replace(/…$/, '');
    }

    function catState(k) {
        const fs = ((CATALOG && CATALOG[k]) || []).filter(f => !skipOf(f));
        if (!(CATALOG && CATALOG[k] || []).length) return 'pending';
        if (!fs.length) return 'skip';
        if (fs.some(f => LIVE.current.includes(f.id))) return 'current';
        if (fs.every(f => LIVE.done.has(f.id))) return 'done';
        return fs.some(f => LIVE.done.has(f.id)) ? 'partial' : 'pending';
    }

    function renderLearn(i) {
        LEARN_IDX = i;
        const k = CAT_KEYS[i];
        $$('#agLearnDots button').forEach((b, j) => {
            const st = catState(CAT_KEYS[j]);
            b.className = 'is-' + st + (j === i ? ' is-active' : '');
            b.setAttribute('aria-pressed', j === i ? 'true' : 'false');
            b.setAttribute('aria-label', `${CATS[CAT_KEYS[j]]}: ${{ done: 'datos recogidos', current: 'recogiendo datos', partial: 'datos en parte', pending: 'pendiente', skip: 'no se analiza' }[st]}`);
        });
        const facs = (CATALOG && CATALOG[k]) || [];
        const juego = enJuego();
        const total = juego.length;
        const hechos = juego.filter(f => LIVE.done.has(f.id)).length;
        // último paso: la evaluación de todos los factores, cuando ya están todos los datos
        const ultimo = LIVE.last === LIVE_STEPS.length - 1;
        const evalSt = LIVE.finished ? 'done' : ultimo ? 'next' : 'pending';
        const evalTxt = { done: `${total} factores evaluados`, next: `A continuación: evaluando los ${total} factores`, pending: `Último paso: evaluando los ${total} factores` }[evalSt];
        $('#agLearnStatus').innerHTML = CATALOG
            ? `<div class="ag-learn-progress"><span>${LIVE.host ? `Recogiendo datos de <b>${esc(LIVE.host)}</b>` : 'Preparando la recogida de datos'}</span><span><b>${hechos}</b> de ${total} factores con datos</span></div>
               <div class="ag-bar ag-bar-sm"><i style="width:${total ? Math.round(hechos / total * 100) : 0}%"></i></div>
               ${LIVE.step ? `<p class="ag-learn-now">${ic('loader-circle', 'ag-spin')} Ahora: ${esc(LIVE.step)}</p>` : ''}
               <p class="ag-learn-final is-${evalSt}">${ic(evalSt === 'done' ? 'check' : 'list-checks')} ${esc(evalTxt)}</p>`
            : '';
        const fstate = f => skipOf(f) ? 'skip' : LIVE.done.has(f.id) ? 'done' : LIVE.current.includes(f.id) ? 'current' : 'pending';
        const ficon = { done: ic('database'), current: ic('loader-circle', 'ag-spin'), pending: ic('circle-dashed'), skip: ic('minus') };
        $('#agLearnBody').innerHTML = `
            <div>
                <h3>${esc(CATS[k])}</h3>
                <p class="ag-learn-meta">Categoría ${i + 1} de 7 · ${k}</p>
                <p>${esc(CAT_DESC[k])}</p>
            </div>
            <ul class="ag-learn-checks">${facs.map(f => {
                const st = fstate(f);
                const nota = st === 'skip' ? `<span class="ag-learn-skip">${esc(skipOf(f))}</span>` : '';
                const sr = { done: ' (datos recogidos)', current: ' (recogiendo datos)', pending: ' (pendiente)', skip: '' }[st];
                return `<li class="is-${st}"><span class="ag-learn-ic">${ficon[st]}</span><span class="ag-learn-name">${esc(f.nombre)}</span>${nota}${sr ? `<span class="ag-sr">${sr}</span>` : ''}</li>`;
            }).join('') || '<li>Cargando factores…</li>'}</ul>`;
        refreshIcons();
    }

    /* Tras cada sondeo: la tarjeta salta sola a la categoría en curso, salvo
       que el usuario acabe de elegir otra (se respeta 20 s). */
    function syncLearn(s) {
        if (!CATALOG) return;
        updateLive(s);
        const cur = CAT_KEYS.findIndex(k => catState(k) === 'current');
        const target = Date.now() < LEARN_MANUAL_UNTIL || cur < 0 ? LEARN_IDX : cur;
        const prev = LEARN_IDX;
        renderLearn(target);
        if (target !== prev) {
            const body = $('#agLearnBody');
            body.style.animation = 'none'; void body.offsetWidth; body.style.animation = '';
        }
    }

    function startLearn() {
        resetLive();
        LEARN_MANUAL_UNTIL = 0;
        $('#agLearnDots').innerHTML = CAT_KEYS.map((k, i) =>
            `<button type="button" data-learn="${i}" aria-label="${esc(CATS[k])}" aria-pressed="false">${k}</button>`).join('');
        CATALOG_P.then(d => {
            if (!CATALOG) {
                CATALOG = {};
                (d.categorias || []).forEach(g => { CATALOG[g.categoria] = g.factores; });
            }
            renderLearn(LEARN_IDX);
        });
        renderLearn(0);
    }
    function stopLearn() { /* la tarjeta ya no rota sola: sigue al análisis */ }
    document.addEventListener('click', e => {
        const b = e.target.closest('[data-learn]');
        if (b) {
            LEARN_MANUAL_UNTIL = Date.now() + 20000;
            renderLearn(parseInt(b.dataset.learn, 10));
            return;
        }
        const t = e.target.closest('#agLogToggle');
        if (t) {
            LOG_OPEN = !LOG_OPEN;
            t.setAttribute('aria-expanded', String(LOG_OPEN));
            t.querySelector('span').textContent = LOG_OPEN ? 'Ver solo lo último' : 'Ver registro completo';
            $('#agConsole').classList.toggle('is-open', LOG_OPEN);
            renderConsole(LAST_LOG);
        }
    });

    // Registro: por defecto las últimas líneas; completo bajo demanda
    let LAST_LOG = [];
    function renderConsole(lines) {
        LAST_LOG = lines || [];
        const con = $('#agConsole');
        const vis = LOG_OPEN ? LAST_LOG : LAST_LOG.slice(-5);
        con.innerHTML = vis.map(l => `<div>${esc(l)}</div>`).join('');
        con.scrollTop = con.scrollHeight;
    }

    function startRunning(id, urls, sel) {
        ANALISIS_EN_CURSO = id;
        LIVE_SEL = sel || null;
        const first = (urls && urls[0]) || '';
        $('#agRunHost').textContent = first.replace(/^https?:\/\//, '').replace(/^www\./, '').replace(/\/$/, '') || 'tu web';
        $('#agPhase').textContent = 'Preparando análisis…';
        $('#agElapsed').textContent = '0:00';
        $('#agRunDomains').innerHTML = '';
        LOG_OPEN = false;
        renderConsole([]);
        drawRadar();
        startLearn();
        show('#agRunning');
        poll(id);
    }

    function renderRunDomains(domains) {
        $('#agRunDomains').innerHTML = (domains || []).map((d, i) => {
            const st = d.state === 'done'
                ? `${ic('check')} ${d.score} / 100`
                : d.state === 'running' ? `${ic('loader-circle', 'ag-spin')} analizando`
                    : d.state === 'error' ? `${ic('circle-x')} error` : `${ic('clock')} en cola`;
            return `<li class="is-${esc(d.state)}">
                <span class="ag-run-host"><span class="ag-dot" style="background:${SERIES[i % 3]}"></span>${esc(d.host)}
                <span class="ag-run-role">${i === 0 ? 'tu web' : 'competidor'}</span></span>
                <span class="ag-run-state">${st}</span></li>`;
        }).join('');
    }

    /* Espaciado progresivo: un análisis puede durar 15 min y sondear cada 1.5s
       todo el rato son 600 peticiones. */
    function _esperaSondeo(intentos) {
        if (intentos < 20) return 1500;      // primeros ~30s: progreso al detalle
        if (intentos < 60) return 3000;      // hasta ~2,5 min
        return 6000;                         // a partir de ahí, análisis largo
    }
    async function poll(id, intentos) {
        intentos = intentos || 0;
        if (ANALISIS_EN_CURSO !== id) return;   // cancelado o sustituido
        try {
            const r = await fetch('/agent/api/status/' + id);
            /* Un 429 es nuestro propio limitador, NO un análisis perdido: se
               reintenta más despacio en vez de matar el sondeo. */
            if (r.status === 429) {
                $('#agPhase').textContent = 'Análisis en curso (esperando al servidor)…';
                setTimeout(() => poll(id, intentos + 1), 10000); return;
            }
            if (r.status === 404) {
                // el job ya no está en memoria: quizá terminó y está guardado
                ANALISIS_EN_CURSO = null; stopLearn();
                openSaved(id, 'Análisis no encontrado (¿servidor reiniciado?)');
                return;
            }
            if (!r.ok) { setTimeout(() => poll(id, intentos + 1), 5000); return; }
            const s = await r.json();
            $('#agPhase').textContent = s.phase || '…';
            const m = Math.floor(s.elapsed / 60), sec = String(s.elapsed % 60).padStart(2, '0');
            $('#agElapsed').textContent = `${m}:${sec}`;
            renderRunDomains(s.domains);
            renderConsole(s.log || []);
            syncLearn(s);
            refreshIcons();
            if (s.status === 'done') {
                ANALISIS_EN_CURSO = null; stopLearn();
                JUST_FINISHED = s.elapsed || 0;
                const rr = await fetch('/agent/api/result/' + id);
                renderReport(await rr.json(), id);
                HISTORY_LOADED = false;
                return;
            }
            if (s.status === 'cancelled') { ANALISIS_EN_CURSO = null; stopLearn(); showMissing('Análisis cancelado', 'Se canceló porque nadie lo estaba mirando o porque lo cancelaste. Puedes lanzarlo de nuevo.'); return; }
            if (s.status === 'error') { ANALISIS_EN_CURSO = null; stopLearn(); showMissing('No pudimos completar el análisis', s.error || 'Error en el análisis'); return; }
            setTimeout(() => poll(id, intentos + 1), _esperaSondeo(intentos));
        } catch (e) {
            setTimeout(() => poll(id, intentos + 1), 5000);
        }
    }

    function showMissing(title, msg) {
        $('#agMissingTitle').textContent = title;
        $('#agMissingMsg').textContent = msg;
        show('#agMissing');
    }

    async function openSaved(id, notFoundTitle) {
        try {
            const r = await fetch('/agent/api/result/' + id);
            if (r.ok) { renderReport(await r.json(), id); return; }
        } catch (e) { /* cae al estado vacío */ }
        showMissing(notFoundTitle || 'No encontramos este informe',
            'Puede que se cancelara, que el servidor se reiniciara antes de terminar o que se borrara del historial.');
    }

    /* Al abrir /agent/?job=… se mira primero si sigue corriendo; si el proceso
       ya no lo conoce (deploy, reinicio, informe de otro día) se busca guardado. */
    async function openJob(id) {
        try {
            const r = await fetch('/agent/api/status/' + id);
            if (r.ok) {
                const s = await r.json();
                if (s.status === 'running') {
                    startRunning(id, (s.domains || []).map(d => d.url));
                    return;
                }
                if (s.status === 'cancelled') { showMissing('Análisis cancelado', 'Se canceló porque nadie lo estaba mirando o porque lo cancelaste. Puedes lanzarlo de nuevo.'); return; }
                if (s.status === 'error') { showMissing('No pudimos completar el análisis', s.error || 'Error en el análisis'); return; }
            }
        } catch (e) { /* se intenta el guardado */ }
        openSaved(id);
    }

    /* ───────────────────────────── informes (historial) ───────────────────────────── */

    let HISTORY_LOADED = false;
    async function loadHistory(force) {
        if (HISTORY_LOADED && !force) return;
        const body = $('#agHistBody');
        try {
            const r = await fetch('/agent/api/historial');
            const j = await r.json();
            HISTORY_LOADED = true;
            const items = j.informes || [];
            $('#agHistCount').textContent = items.length ? String(items.length) : '';
            if (IS_ADMIN) $('#agHistScope').textContent = 'Como administrador ves los informes de todos los usuarios con acceso.';
            if (j.persistencia === false) {
                body.innerHTML = emptyState('database', 'El historial no está disponible',
                    'La base de datos de informes no responde ahora mismo. Los análisis siguen funcionando, pero no se pueden listar.');
                refreshIcons(); return;
            }
            if (!items.length) {
                body.innerHTML = emptyState('folder-open', 'Todavía no hay informes',
                    'Cuando lances tu primer análisis aparecerá aquí, listo para reabrirlo o descargarlo.',
                    `<button type="button" class="btn-primary" data-ag-goto="nuevo">${ic('plus')} Nuevo análisis</button>`);
                refreshIcons(); return;
            }
            body.innerHTML = `<div class="ag-card ag-table-wrap"><table class="ag-table ag-stack">
                <thead><tr><th>Dominio</th><th>Fecha</th><th>Tipología</th><th>Agentes</th><th class="ag-num">Puntuación</th><th><span class="ag-sr">Acciones</span></th></tr></thead>
                <tbody>${items.map(histRow).join('')}</tbody></table></div>`;
            refreshIcons();
        } catch (e) {
            body.innerHTML = emptyState('circle-alert', 'No se pudo cargar el historial', 'Reintenta en unos segundos.');
            refreshIcons();
        }
    }

    function histRow(it) {
        const s = typeof it.score === 'number' ? Math.round(it.score * 10) / 10 : null;
        const agentes = { completado: 'Simulados', pendiente: 'Por lanzar', corriendo: 'En curso', error: 'Fallaron', desactivadas: 'No pedidos' }[it.agentes] || 'No pedidos';
        const fiable = it.fiable === false
            ? `<span class="ag-hist-comp is-warn-text" data-tip="Lectura limitada||El sitio bloqueó parte del acceso: hay factores que no se pudieron verificar.">${ic('triangle-alert')} lectura limitada</span>` : '';
        return `<tr class="ag-hist-row">
            <td class="c-main"><span class="ag-hist-host">${esc(it.host)}</span>
                ${it.competidores ? `<span class="ag-hist-comp">frente a ${esc(it.competidores)}</span>` : ''}${fiable}</td>
            <td class="c-meta" data-label="Fecha" style="white-space:nowrap">${esc(fmtDateTime(it.fecha))}</td>
            <td class="c-meta" data-label="Tipología">${esc(typ(it.tipologia))}</td>
            <td class="c-meta" data-label="Agentes">${esc(agentes)}</td>
            <td class="ag-num c-score"><span class="ag-hist-score">${s !== null ? `<span class="ag-bar ag-bar-sm"><i class="is-${scoreTone(s)}" style="width:${Math.max(0, Math.min(100, s))}%"></i></span><b class="is-${scoreTone(s)}-text">${s}</b>` : '—'}</span></td>
            <td class="c-actions"><div class="ag-hist-actions">
                <button type="button" class="btn-secondary ag-btn-sm" data-open="${esc(it.id)}">Abrir</button>
                <button type="button" class="btn-ghost ag-btn-sm" data-del="${esc(it.id)}" aria-label="Borrar informe de ${esc(it.host)}">${ic('trash-2')}</button>
            </div></td></tr>`;
    }

    function emptyState(icon, title, msg, action) {
        return `<div class="empty-state ag-empty"><div class="empty-icon">${ic(icon)}</div>
            <h2>${esc(title)}</h2><p>${esc(msg)}</p>${action || ''}</div>`;
    }

    document.addEventListener('click', async e => {
        const o = e.target.closest('[data-open]');
        if (o) { setUrl({ job: o.dataset.open }); openSaved(o.dataset.open); return; }
        const d = e.target.closest('[data-del]');
        if (!d) return;
        // confirmación de dos clics, sin popup nativo
        if (d.dataset.confirm !== '1') {
            d.dataset.confirm = '1';
            d.classList.add('btn-danger-confirm');
            d.innerHTML = '¿Borrar?';
            setTimeout(() => {
                if (d.dataset.confirm === '1') {
                    d.dataset.confirm = '0'; d.classList.remove('btn-danger-confirm');
                    d.innerHTML = ic('trash-2'); refreshIcons();
                }
            }, 3500);
            return;
        }
        d.disabled = true;
        d.textContent = 'Borrando…';
        try {
            const r = await fetch('/agent/api/historial/' + encodeURIComponent(d.dataset.del), { method: 'DELETE' });
            const j = await r.json();
            if (!j.borrado) throw new Error('no borrado');
        } catch (err) {
            d.textContent = 'No se pudo';
        }
        loadHistory(true);
    });

    /* ───────────────────────────── accesos (solo admin) ───────────────────────────── */

    let ACCESS_LOADED = false;
    async function loadAccess(force) {
        if (!IS_ADMIN || (ACCESS_LOADED && !force)) return;
        const list = $('#agAccList');
        try {
            const j = await (await fetch('/agent/api/access/list')).json();
            ACCESS_LOADED = true;
            const emails = j.emails || [];
            if (!emails.length) {
                list.innerHTML = '<p class="ag-help">Todavía no has dado acceso a ningún email. Los administradores ya entran por defecto.</p>';
                return;
            }
            list.innerHTML = `<div class="ag-table-wrap"><table class="ag-table"><thead><tr><th>Email</th><th>Añadido</th><th></th></tr></thead><tbody>` +
                emails.map(e => `<tr class="ag-hist-row">
                    <td><b>${esc(e.email)}</b></td>
                    <td class="ag-muted">${esc(e.added_at || '')}${e.added_by ? ` · por ${esc(e.added_by)}` : ''}</td>
                    <td><div class="ag-hist-actions">
                        <button type="button" class="btn-secondary ag-btn-sm" data-resend="${esc(e.email)}">Reenviar invitación</button>
                        <button type="button" class="btn-ghost ag-btn-sm" data-revoke="${esc(e.email)}">Quitar acceso</button>
                    </div></td></tr>`).join('') + '</tbody></table></div>';
        } catch (e) {
            list.innerHTML = '<p class="ag-help">No se pudo cargar la lista.</p>';
        }
    }

    function accMsg(msg, ok) {
        const t = $('#agAccMsg');
        t.className = 'ag-feedback' + (ok ? ' is-ok' : '');
        t.textContent = msg;
        if (msg) setTimeout(() => { if (t.textContent === msg) t.textContent = ''; }, 6000);
    }

    if (IS_ADMIN) {
        $('#agAccAdd').addEventListener('click', async () => {
            const email = $('#agAccEmail').value.trim();
            $('#agAccErr').textContent = '';
            accMsg('');
            if (!email) { $('#agAccErr').textContent = 'Escribe un email.'; return; }
            $('#agAccAdd').disabled = true;
            try {
                const r = await fetch('/agent/api/access/add', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email })
                });
                const j = await r.json();
                if (!r.ok) throw new Error(j.error || 'error');
                $('#agAccEmail').value = '';
                if (j.email_sent) accMsg('Acceso concedido. Hemos enviado la invitación a ' + j.email + '.', true);
                else accMsg('Acceso concedido, pero la invitación no se pudo enviar. Prueba «Reenviar invitación» en la lista.');
                loadAccess(true);
            } catch (e) {
                $('#agAccErr').textContent = e.message;
            } finally {
                $('#agAccAdd').disabled = false;
            }
        });
        document.addEventListener('click', async e => {
            const rs = e.target.closest('[data-resend]');
            if (rs) {
                const email = rs.dataset.resend, old = rs.textContent;
                rs.textContent = 'Enviando…'; rs.disabled = true;
                try {
                    const j = await (await fetch('/agent/api/access/resend', {
                        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email })
                    })).json();
                    accMsg(j.email_sent ? 'Invitación reenviada a ' + email + '.' : 'No se pudo enviar el email (revisa la configuración SMTP del entorno).', j.email_sent);
                } catch (_) { accMsg('Error al reenviar.'); }
                finally { rs.textContent = old; rs.disabled = false; }
                return;
            }
            const b = e.target.closest('[data-revoke]');
            if (!b) return;
            if (b.dataset.confirm !== '1') {
                b.dataset.confirm = '1';
                b.textContent = '¿Confirmar?';
                b.classList.add('btn-danger-confirm');
                setTimeout(() => {
                    if (b.dataset.confirm === '1') { b.dataset.confirm = '0'; b.textContent = 'Quitar acceso'; b.classList.remove('btn-danger-confirm'); }
                }, 3500);
                return;
            }
            b.textContent = 'Quitando…'; b.disabled = true;
            await fetch('/agent/api/access/remove', {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: b.dataset.revoke })
            }).catch(() => {});
            loadAccess(true);
        });
    }

    /* ───────────────────────────── piezas del informe ───────────────────────────── */

    // Resultado de un check: icono + color de estado + nombre accesible. Antes
    // eran glifos unicode (✓ ◐ ✕), que no son un sistema de iconos.
    const MARKS = {
        ok: ['check', 'cumple'], part: ['contrast', 'parcial'], bad: ['x', 'falla'], na: ['minus', 'no aplica']
    };
    const markOf = k => `<span class="ag-mark is-${k}" role="img" aria-label="${MARKS[k][1]}">${ic(MARKS[k][0])}</span>`;
    const mark = s => markOf(s == null ? 'na' : s >= 1 ? 'ok' : s > 0 ? 'part' : 'bad');

    const MARK_LEGEND = `<div class="ag-legend">
        <span>${mark(1)} cumple</span><span>${mark(0.5)} parcial</span>
        <span>${mark(0)} falla</span><span>${mark(null)} no aplica / no medido</span></div>`;

    const stateOf = p => p >= 75 ? ['Fuerte', 'is-good'] : p >= 50 ? ['Mejorable', 'is-warn'] : p >= 25 ? ['Flojo', 'is-bad'] : ['Crítico', 'is-bad'];

    function gaugeSVG(score, parcial) {
        const W = 240, H = 150, r = 96, cx = W / 2, cy = 128, L = Math.PI * r;
        const frac = Math.max(0, Math.min(1, (score || 0) / 100));
        const col = parcial ? C.text3 : TONE_HEX[scoreTone(score || 0)];
        const arc = `M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`;
        let ticks = '';
        for (const t of [25, 50, 75]) {
            const a = Math.PI * (1 - t / 100);
            ticks += `<line x1="${(cx + (r - 9) * Math.cos(a)).toFixed(1)}" y1="${(cy - (r - 9) * Math.sin(a)).toFixed(1)}" x2="${(cx + (r + 9) * Math.cos(a)).toFixed(1)}" y2="${(cy - (r + 9) * Math.sin(a)).toFixed(1)}" stroke="#FFFFFF" stroke-width="3"/>`;
        }
        return `<svg class="ag-gauge" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="Puntuación ${score} de 100">
            <path d="${arc}" fill="none" stroke="${C.grid}" stroke-width="16" stroke-linecap="round"/>
            <path d="${arc}" fill="none" stroke="${col}" stroke-width="16" stroke-linecap="round"
                stroke-dasharray="${(frac * L).toFixed(1)} ${L.toFixed(1)}" style="transition:stroke-dasharray .9s cubic-bezier(0.2,0.8,0.2,1)"/>
            ${ticks}
            <text x="${cx}" y="${cy - 24}" text-anchor="middle" fill="${C.text}" font-family="Inter Tight, sans-serif" font-size="48" font-weight="800" letter-spacing="-2">${score}</text>
            <text x="${cx}" y="${cy}" text-anchor="middle" fill="${C.text3}" font-family="Inter Tight, sans-serif" font-size="12" font-weight="600">${parcial ? 'nota parcial' : 'de 100'}</text>
        </svg>`;
    }

    function scaleHTML(score) {
        const b = bandOf(score);
        const pos = Math.max(0, Math.min(100, score));
        return `<div class="ag-scale" data-tip="Escala de preparación agéntica||0-25 invisible para agentes · 26-50 legible pero no operable · 51-75 agent-aware · 76-100 agent-ready.">
            <div class="ag-scale-track">${SCALE.map((s, i) => `<i class="${i === b ? 'is-active is-' + scoreTone(score) : ''}"></i>`).join('')}
                <span class="ag-scale-marker" style="left:${pos}%"></span></div>
            <div class="ag-scale-labels">${SCALE.map((s, i) => `<span class="${i === b ? 'is-active' : ''}">${s.from}–${s.to}<br>${esc(s.name)}</span>`).join('')}</div>
        </div>`;
    }

    function balanceHTML(a) {
        const ch = a.checks || [];
        const n = {
            ok: ch.filter(x => x.score >= 1).length, part: ch.filter(x => x.score > 0 && x.score < 1).length,
            bad: ch.filter(x => x.score === 0).length, na: ch.filter(x => x.score == null).length
        };
        const tot = ch.length || 1;
        const seg = (k) => n[k] ? `<i class="is-${k}" style="flex:${n[k] / tot}"></i>` : '';
        return `<div class="ag-balance">
            <div class="ag-balance-bar" role="img" aria-label="${n.ok} cumplen, ${n.part} parciales, ${n.bad} fallan, ${n.na} no aplican">${seg('ok')}${seg('part')}${seg('bad')}${seg('na')}</div>
            <div class="ag-balance-legend">
                <span><span class="ag-sw is-ok"></span><b>${n.ok}</b> cumplen</span>
                <span><span class="ag-sw is-part"></span><b>${n.part}</b> parciales</span>
                <span><span class="ag-sw is-bad"></span><b>${n.bad}</b> fallan</span>
                <span><span class="ag-sw is-na"></span><b>${n.na}</b> no aplican</span>
            </div></div>`;
    }

    function catRows(a, color) {
        return Object.keys(CATS).filter(c => a.category_scores && a.category_scores[c] != null).map(c => {
            const p = pct(a.category_scores[c]);
            const [st, cls] = stateOf(p);
            return `<div class="ag-catrow" data-tip="${esc(c + ' · ' + CATS[c] + '||' + CAT_DESC[c] + ' El % son los checks superados, ponderados por importancia.')}">
                <div class="ag-catrow-name"><b>${c}</b>${esc(CATS[c])}</div>
                <div class="ag-bar"><i class="${color ? '' : 'is-' + toneOf(p)}" style="width:${p}%;${color ? 'background:' + color : ''}"></i></div>
                <div class="ag-catrow-val is-${toneOf(p)}-text">${p}%</div>
                <div class="ag-state ${cls}">${st}</div></div>`;
        }).join('');
    }

    function stagesOf(a) {
        return STAGES.map(s => {
            const vals = s.cats.map(c => a.category_scores?.[c]).filter(v => v != null);
            if (!vals.length) return null;
            return { ...s, p: Math.round(vals.reduce((x, y) => x + y, 0) / vals.length * 100) };
        }).filter(Boolean);
    }

    /* El viaje es una cadena, no tres tarjetas iguales: un único carril con
       los tres tramos unidos, y solo el eslabón más débil se rellena. */
    function journeyHTML(a) {
        const st = stagesOf(a);
        if (!st.length) return '';
        const weakest = st.length > 1 ? st.reduce((m, s) => (s.p < m.p ? s : m), st[0]) : null;
        return `<ol class="ag-chain">${st.map((s, i) => {
            const tone = toneOf(s.p), weak = s === weakest;
            const cats = s.cats.filter(c => a.category_scores?.[c] != null).map(c => `${esc(CATS[c])}`).join(' · ');
            return `<li class="ag-link is-${tone}${weak ? ' is-weak' : ''}">
                <div class="ag-link-top"><span class="ag-link-step">${i + 1}</span><span class="ag-link-q">${s.name}</span>
                    <span class="ag-link-pct is-${tone}-text">${s.p}%</span></div>
                <div class="ag-bar"><i class="is-${tone}" style="width:${s.p}%"></i></div>
                <p class="ag-link-desc">${cats}</p>
                ${weak ? `<p class="ag-link-flag">${ic('link-2-off')} Eslabón más débil: empieza por aquí</p>` : ''}
            </li>`;
        }).join('')}</ol>`;
    }

    function alertHTML(opts) {
        return `<div class="ag-alert${opts.tone ? ' is-' + opts.tone : ''}">
            <span class="ag-alert-ic">${ic(opts.icon || 'info')}</span>
            <div><p class="ag-alert-title">${opts.title}</p><div class="ag-alert-body">${opts.body}</div>
            ${opts.actions ? `<div class="ag-alert-actions">${opts.actions}</div>` : ''}</div></div>`;
    }

    /* ───── Resumen ───── */
    function paneResumen(d) {
        const c = d.client;
        const parcial = !!(c.level && c.level.cobertura_parcial);
        const qwAll = (c.checks || []).filter(x => x.advice && x.advice.esfuerzo === 'Bajo' && (IMPORD[x.advice.impacto] ?? 3) <= 2 && x.score < 1)
            .sort((a, b) => (IMPORD[a.advice.impacto] ?? 3) - (IMPORD[b.advice.impacto] ?? 3));
        // Tres como mucho: más de cuatro opciones a la vez ya no es "por dónde empezar"
        const qw = qwAll.slice(0, 3);
        /* Aviso de acceso degradado. Título y cuerpo salen del propio veredicto
           (scoring.py), así web, PDF y JSON cuentan lo mismo. Informa sin
           alarmar: no es rojo de error, es lo que sí y lo que no se verificó. */
        const deg = c.acceso_degradado;
        let aviso = '';
        if (deg && c.level.cobertura_parcial) {
            aviso = alertHTML({
                tone: 'warn',
                icon: 'shield-alert',
                title: esc(c.level.name),
                body: `${esc(c.level.msg)}
                    ${deg.degradados ? ` Hay <b>${deg.degradados}</b> factores marcados como «no verificable» porque no se pudieron comprobar: no cuentan como fallo.` : ''}
                    ${c.cobertura_score != null ? ` Esta nota cubre el <b>${pct(c.cobertura_score)}%</b> del modelo.` : ''}
                    Puedes reintentar más tarde: si el sitio solo estaba limitando el ritmo, el siguiente análisis saldrá completo.
                    <br><br>Aunque nuestra red esté bloqueada, tú sí puedes completar la auditoría: copia este prompt, pégalo en ChatGPT o Claude y trae los factores que faltan con la garantía de que no se inventa nada.`,
                actions: `<button type="button" class="btn-primary ag-btn-sm js-superprompt">${ic('clipboard-copy')} <span>Copiar prompt para completar con IA</span></button>`
            });
        } else if (c.score_fiable === false && deg) {
            aviso = alertHTML({
                tone: 'warn',
                icon: 'shield-alert',
                title: 'Lectura limitada',
                body: `${esc(deg.motivo)}. Hay <b>${deg.degradados}</b> factores marcados como «no verificable» porque no se pudieron comprobar: no cuentan como fallo. Puedes repetir el análisis más tarde o desde otra red.`
            });
        }
        const pens = (c.penalties || []).map(p =>
            `<div class="ag-penalty">${ic('circle-minus')}<span>Penalización aplicada: <b>${esc(p[0])}</b> (${p[1]} puntos)</span></div>`).join('');
        const via = (c.via_lectura && c.via_lectura !== 'http')
            ? `<p class="ag-score-note">Contenido leído vía <b>${esc(c.via_lectura.replace('ua:', ''))}</b>${c.via_lectura.startsWith('ua:') ? ': el acceso normal estaba bloqueado; el acceso real de cada bot de IA se mide aparte' : ''}.</p>` : '';
        const cobertura = parcial && c.cobertura_score != null
            ? `<p class="ag-score-note">Cubre el <b>${pct(c.cobertura_score)}%</b> del modelo: solo lo que se pudo verificar.</p>` : '';

        return `<div class="ag-pane">${aviso}
            <div class="ag-grid-score">
                <div class="ag-card ag-score-card">
                    <h2 class="ag-card-title ag-score-title">${parcial ? 'Puntuación parcial' : 'Puntuación global'}</h2>
                    ${gaugeSVG(c.score, parcial)}
                    ${via}${cobertura}
                    <div class="ag-level ${parcial ? '' : 'is-' + scoreTone(c.score)}">${esc(c.level.name)}</div>
                    ${aviso && parcial ? '' : `<p class="ag-level-msg">${esc(c.level.msg)}</p>`}
                    ${scaleHTML(c.score)}
                    ${balanceHTML(c)}
                    ${pens}
                </div>
                <div class="ag-card">
                    <div class="ag-card-head"><h2 class="ag-card-title">Desglose por categoría</h2>
                        <span class="ag-muted">${(c.checks || []).length} comprobaciones</span></div>
                    <div class="ag-catrows" style="margin-top:var(--cs-space-sm)">${catRows(c, null)}</div>
                </div>
            </div>
            ${agentsSummaryHTML(d)}
            <div class="ag-card ag-section">
                <h2 class="ag-card-title">El viaje del agente por tu web</h2>
                <p class="ag-card-sub">Un agente primero tiene que poder <b>leerte</b>, luego <b>entenderte</b> sin equivocarse, y solo entonces puede <b>usarte</b> (comprar, reservar, contactar). La cadena se rompe en el eslabón más débil.</p>
                ${journeyHTML(c)}
            </div>
            <div class="ag-card ag-section">
                <h2 class="ag-card-title">Por dónde empezar</h2>
                <p class="ag-card-sub">Los arreglos que más rinden con menos esfuerzo, de más a menos urgente.</p>
                ${qw.length ? `<ol class="ag-steps">${qw.map((x, i) => `
                    <li class="ag-step t${Math.min(IMPORD[x.advice.impacto] ?? 3, 3)}"><span class="ag-qn" aria-hidden="true">${i + 1}</span>
                    <div><div class="ag-step-title">${esc(x.advice.titulo)}</div><div class="ag-step-body">${esc(x.advice.como)}</div>
                    <div class="ag-step-meta">Impacto <b>${esc(String(x.advice.impacto).toLowerCase())}</b> · esfuerzo <b>${esc(String(x.advice.esfuerzo).toLowerCase())}</b></div></div></li>`).join('')}</ol>`
                : '<p class="ag-help">No quedan arreglos rápidos: lo que falta requiere más trabajo y está en el plan de acción.</p>'}
                <div class="ag-cta-row"><button type="button" class="btn-secondary" data-rep-tab="2">${qwAll.length > qw.length ? `Ver los ${qwAll.length - qw.length} siguientes y el plan completo` : 'Ver el plan de acción completo'} ${ic('arrow-right')}</button></div>
            </div></div>`;
    }

    /* ───── Comparativa ───── */
    function radarSVG(audits, size) {
        size = size || 360;
        const cats = Object.keys(CATS).filter(c => audits.some(a => a.category_scores && a.category_scores[c] != null));
        if (cats.length < 3) return '';
        const cx = size / 2, cy = size / 2, rad = size / 2 - 44, n = cats.length;
        const pt = (i, r) => { const a = -Math.PI / 2 + 2 * Math.PI * i / n; return [cx + r * Math.cos(a), cy + r * Math.sin(a)]; };
        let out = `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" role="img" aria-label="Radar de categorías">`;
        for (const ring of [0.25, 0.5, 0.75, 1]) {
            out += `<polygon points="${cats.map((_, i) => pt(i, rad * ring).map(v => v.toFixed(1)).join(',')).join(' ')}" fill="none" stroke="${C.grid}" stroke-width="1"/>`;
        }
        cats.forEach((c, i) => {
            const [x, y] = pt(i, rad), [lx, ly] = pt(i, rad + 22);
            const anchor = lx < cx - 8 ? 'end' : lx > cx + 8 ? 'start' : 'middle';
            out += `<line x1="${cx}" y1="${cy}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}" stroke="${C.grid}"/>
                <text x="${lx.toFixed(1)}" y="${ly.toFixed(1)}" fill="${C.text2}" font-family="Inter Tight, sans-serif" font-size="12" font-weight="600" text-anchor="${anchor}" dominant-baseline="middle">${c}</text>`;
        });
        audits.forEach((a, idx) => {
            const col = SERIES[idx % 3], cs = a.category_scores || {};
            const pts = cats.map((c, i) => pt(i, rad * (cs[c] || 0)).map(v => v.toFixed(1)).join(',')).join(' ');
            const resume = cats.map(c => c + ' ' + pct(cs[c]) + '%').join(' · ');
            out += `<polygon points="${pts}" fill="${col}" fill-opacity="${idx === 0 ? 0.14 : 0.06}" stroke="${col}" stroke-width="${idx === 0 ? 2.5 : 1.75}" stroke-linejoin="round" data-tip="${esc(a.host + '||Cuanto más grande y regular el polígono, mejor preparación en todas las categorías. ' + resume)}"/>`;
        });
        return out + '</svg>';
    }

    function gapsOf(client, comps) {
        const out = [];
        Object.keys(CATS).forEach(c => {
            const mine = client.category_scores?.[c];
            if (mine == null) return;
            comps.forEach(comp => {
                const v = comp.category_scores?.[c];
                if (v != null && v - mine >= 0.15) out.push({ c, host: comp.host, diff: pct(v - mine), v: pct(v), mine: pct(mine) });
            });
        });
        return out.sort((a, b) => b.diff - a.diff);
    }

    function paneComparativa(d) {
        const audits = [d.client, ...(d.competitors || []).filter(a => !a.error)];
        if (audits.length < 2) {
            return `<div class="ag-pane">${emptyState('swords', 'Sin competidores en este análisis',
                'Añade uno o dos competidores al lanzar el análisis para ver la comparativa con la misma vara de medir.',
                `<button type="button" class="btn-primary" data-ag-goto="nuevo">${ic('plus')} Nuevo análisis</button>`)}</div>`;
        }
        /* Un dominio sin nota (nos cerró la puerta) no compite por "el mejor":
           su número no mide lo mismo que el de los demás. */
        const conNota = audits.filter(a => !a.level.cobertura_parcial);
        /* Tipologías distintas NO se coronan entre sí. Al validar el modelo con
           agentes reales (21 dominios, jul 2026) la tarea de e-commerce resultó
           mucho más dura que la de SaaS, y los pesos tampoco coinciden (C7 solo
           puntúa en e-commerce). Coronar a la mejor de una mezcla le daba al
           cliente un ganador que no significaba nada. */
        const tipos = [...new Set(audits.map(a => a.typology))];
        const mixto = tipos.length > 1;
        const best = (!mixto && conNota.length) ? Math.max(...conNota.map(a => a.score)) : null;
        const avisoMixto = mixto ? alertHTML({
            tone: 'warn',
            icon: 'scale',
            title: 'Tipologías distintas: las notas no son comparables',
            body: `Estás comparando ${tipos.map(t => `<b>${esc(typ(t))}</b>`).join(' y ')}. Cada tipología se puntúa con pesos distintos (la categoría de ficha de producto solo cuenta en e-commerce) y la tarea que un agente debe completar no tiene la misma dificultad: al validar con agentes reales, los SaaS completaron entre el 25% y el 100% del recorrido y las tiendas entre el 0% y el 55%. Por eso <b>no se señala una ganadora</b>. Compara cada dominio con otros de su misma tipología, o quédate con el desglose por categoría, que sí es comparable.`
        }) : '';

        const ranking = audits.map((a, i) => {
            const win = !a.level.cobertura_parcial && best !== null && a.score === best;
            return `<tr class="ag-hist-row${win ? ' win' : ''}">
                <td class="c-main"><span class="ag-entity"><span class="ag-dot" style="background:${SERIES[i % 3]}"></span>${esc(a.host)}</span></td>
                <td class="c-meta ag-muted" data-label="Rol">${i === 0 ? 'Tu web' : 'Competidor ' + i}</td>
                <td class="c-meta" data-label="Tipología">${esc(typ(a.typology))}</td>
                <td class="c-meta" data-label="Nivel">${esc(a.level.name)}${win ? ` <span class="ag-best" role="img" aria-label="mejor puntuación" data-tip="Mejor puntuación||Entre dominios de la misma tipología y con nota completa.">${ic('trophy')}</span>` : ''}</td>
                <td class="ag-num c-score"><span class="ag-hist-score"><span class="ag-bar ag-bar-sm"><i style="width:${a.score}%;background:${SERIES[i % 3]}"></i></span><b class="is-${scoreTone(a.score)}-text">${a.score}</b></span></td>
            </tr>`;
        }).join('');

        /* Matriz categoría × dominio: cifra + mini barra en el color de cada
           dominio; la mejor de cada fila en negrita. Sustituye al mapa de calor
           rojo/ámbar/verde, que inventaba colores fuera de la paleta. */
        const heatCats = Object.keys(CATS).filter(c => audits.some(a => a.category_scores?.[c] != null));
        const matrix = heatCats.map(cat => {
            const vals = audits.map(a => a.category_scores?.[cat]);
            const conValor = vals.filter(v => v != null);
            const mx = Math.max(...conValor);
            // resaltar la mejor solo si hay con quién comparar y no es un 0
            const resalta = conValor.length > 1 && mx > 0;
            return `<tr><td><b>${cat}</b> <span class="ag-muted">${esc(CATS[cat])}</span></td>${audits.map((a, i) => {
                const v = vals[i];
                if (v == null) return '<td class="ag-num ag-muted">n/a</td>';
                const p = pct(v);
                const best = v === mx && resalta;
                return `<td class="ag-num"><span class="ag-cell"><span class="ag-bar ag-bar-sm"><i style="width:${p}%;background:${SERIES[i % 3]}"></i></span><b class="v is-${toneOf(p)}-text">${p}</b>${best ? `<span class="ag-best" role="img" aria-label="mejor de la fila">${ic('trophy')}</span>` : '<span class="ag-best"></span>'}</span></td>`;
            }).join('')}</tr>`;
        }).join('');

        const gaps = gapsOf(d.client, audits.slice(1));
        const gapsHTML = gaps.length
            ? `<ul class="ag-list">${gaps.map(g => `<li><span class="ag-list-ic">${ic('trending-down')}</span><div>
                <div class="ag-list-title">${g.c} · ${esc(CATS[g.c])}</div>
                <div class="ag-list-body">${esc(g.host)} te saca <b>${g.diff} puntos</b> (${g.v}% frente a tu ${g.mine}%).</div></div></li>`).join('')}</ul>`
            : '<p class="ag-help">Sin brechas relevantes: ninguna categoría con desventaja de 15 puntos o más.</p>';

        // Detalle check a check: por defecto solo donde los dominios difieren
        const markKey = sc => sc == null ? 'na' : sc >= 1 ? 'ok' : sc > 0 ? 'part' : 'bad';
        const differs = c => new Set(audits.map(a => markKey(((a.checks || []).find(x => x.id === c.id) || {}).score))).size > 1;
        const nDiff = d.client.checks.filter(differs).length;
        const rows = d.client.checks.map((c, ri) => {
            if (!CMP_ALL && !differs(c)) return '';
            const cells = audits.map(a => { const m = (a.checks || []).find(x => x.id === c.id); return `<td class="ag-center">${mark(m ? m.score : null)}</td>`; }).join('');
            const detail = audits.map((a, i) => {
                const m = (a.checks || []).find(x => x.id === c.id);
                const link = CHECK_LINKS[c.id]
                    ? ` <a href="https://${esc(a.host)}${CHECK_LINKS[c.id]}" target="_blank" rel="noopener">abrir ${CHECK_LINKS[c.id]} ${ic('external-link')}</a>` : '';
                return `<div class="ag-ev-item"><div class="ag-ev-head"><span class="ag-dot" style="background:${SERIES[i % 3]}"></span>${esc(a.host)}${link}</div>
                    <div class="ag-evidence-box">${esc(m ? m.evidence : 'no analizado en este dominio')}</div></div>`;
            }).join('');
            return `<tr class="ag-row-click" data-r="${ri}"><td><button type="button" class="ag-row-toggle" aria-expanded="false" aria-controls="agChk-${ri}">${ic('chevron-right', 'ag-caret')}<span>${esc(nameOf(c))}</span></button></td>${cells}</tr>
                <tr class="ag-row-detail" id="agChk-${ri}" hidden><td colspan="${audits.length + 1}">
                    <p class="ag-help" style="margin:0 0 var(--cs-space-sm)"><b>Cómo se mide:</b> ${esc(METHODS[c.id] || '')}</p>${detail}</td></tr>`;
        }).join('');

        const head = audits.map((a, i) => `<th class="ag-num"><span class="ag-entity" style="justify-content:flex-end"><span class="ag-dot" style="background:${SERIES[i % 3]}"></span>${esc(a.host)}</span></th>`).join('');
        const headC = audits.map((a, i) => `<th class="ag-center"><span class="ag-entity"><span class="ag-dot" style="background:${SERIES[i % 3]}"></span>${esc(a.host)}</span></th>`).join('');

        return `<div class="ag-pane">${avisoMixto}
            <div class="ag-card">
                <h2 class="ag-card-title">Puntuación por dominio</h2>
                <div class="ag-table-wrap"><table class="ag-table ag-stack"><thead><tr><th>Dominio</th><th><span class="ag-sr">Rol</span></th><th>Tipología</th><th>Nivel</th><th class="ag-num">Puntuación</th></tr></thead>
                <tbody>${ranking}</tbody></table></div>
            </div>
            <div class="ag-grid-2">
                <div class="ag-card">
                    <h2 class="ag-card-title">Perfil por categoría</h2>
                    <div class="ag-chart-scroll" style="display:flex;justify-content:center">${radarSVG(audits)}</div>
                    <div class="ag-legend" style="justify-content:center">${audits.map((a, i) => `<span><span class="ag-dot" style="background:${SERIES[i % 3]}"></span>${esc(a.host)}</span>`).join('')}</div>
                </div>
                <div class="ag-card">
                    <h2 class="ag-card-title">Dónde te sacan ventaja</h2>
                    <p class="ag-card-sub">Categorías en las que un competidor te supera por 15 puntos o más.</p>
                    ${gapsHTML}
                </div>
            </div>
            <div class="ag-card ag-section">
                <h2 class="ag-card-title">Categoría a categoría</h2>
                <p class="ag-card-sub">Mismos checks y mismos pesos para todos. Cifra en verde (75 o más), naranja (50-74) o rojo (menos de 50); el trofeo marca el mejor de cada fila.</p>
                <div class="ag-table-wrap"><table class="ag-table ag-matrix"><thead><tr><th>Categoría</th>${head}</tr></thead><tbody>${matrix}</tbody></table></div>
            </div>
            <div class="ag-card ag-section">
                <div class="ag-card-head"><h2 class="ag-card-title">Detalle check a check</h2>
                    <div class="ag-switcher ag-filter" role="group" aria-label="Filtrar checks">
                        <button type="button" class="btn-secondary ag-btn-sm${CMP_ALL ? '' : ' is-active'}" data-cmp="diff" aria-pressed="${!CMP_ALL}">Solo diferencias (${nDiff})</button>
                        <button type="button" class="btn-secondary ag-btn-sm${CMP_ALL ? ' is-active' : ''}" data-cmp="all" aria-pressed="${CMP_ALL}">Todos (${d.client.checks.length})</button>
                    </div></div>
                <p class="ag-card-sub">Abre un check para ver la evidencia de cada dominio y el enlace al recurso.</p>
                <div class="ag-table-wrap"><table class="ag-table"><thead><tr><th>Check</th>${headC}</tr></thead><tbody>${rows}</tbody></table></div>
                ${MARK_LEGEND}
            </div></div>`;
    }

    // expandir/contraer filas de check (delegado: sobrevive a re-renders)
    document.addEventListener('click', e => {
        const r = e.target.closest('.ag-row-click');
        if (!r || e.target.closest('a')) return;
        const det = document.getElementById('agChk-' + r.dataset.r);
        if (!det) return;
        det.hidden = !det.hidden;
        r.classList.toggle('is-open', !det.hidden);
        const tg = r.querySelector('.ag-row-toggle');
        if (tg) tg.setAttribute('aria-expanded', String(!det.hidden));
    });

    /* ───── Hallazgos ───── */
    function bubbleChart(a) {
        const items = (a.checks || []).filter(c => c.score != null && c.score < 1 && c.advice);
        if (!items.length) return '';
        // A ancho completo: el SVG escala con la tarjeta (viewBox + width 100%).
        const W = 1120, H = 560, padL = 110, padB = 70, padT = 20, padR = 20;
        const plotW = W - padL - padR, plotH = H - padT - padB;
        const cw = plotW / 3, ch = plotH / 4;
        const effOf = e => (e === 'Bajo' ? 0 : e === 'Medio' ? 1 : 2);
        const impOf = i => 3 - Math.min(IMPORD[i] ?? 3, 3);          // Crítico arriba
        const tierOf = c => Math.min(IMPORD[c.advice.impacto] ?? 3, 3);
        // tamaño = puntos de score recuperables (peso de su categoría repartido)
        const scoredInCat = {};
        (a.checks || []).forEach(c => { if (c.score != null) scoredInCat[c.cat] = (scoredInCat[c.cat] || 0) + 1; });
        const rec = c => { const catw = a.category_weights?.[c.cat] ?? 14; return catw / (scoredInCat[c.cat] || 1) * (1 - c.score); };

        // Agrupar por celda y colocar SIN solapes: filas centradas dentro de la
        // celda; si no caben, se reduce el radio de toda la celda.
        const cells = {};
        items.forEach(c => {
            const k = effOf(String(c.advice.esfuerzo).split(' ')[0]) + '-' + impOf(c.advice.impacto);
            (cells[k] = cells[k] || []).push(c);
        });
        const GAP = 8, PADC = 12;
        function layout(list, scale) {
            const rows = [[]];
            let x = 0;
            const maxW = cw - PADC * 2;
            list.forEach(c => {
                const d = 2 * Math.max(20, Math.min(40, 17 + rec(c) * 4)) * scale;
                if (x > 0 && x + d > maxW) { rows.push([]); x = 0; }
                rows[rows.length - 1].push({ c, d });
                x += d + GAP;
            });
            const h = rows.reduce((t, r) => t + Math.max(...r.map(o => o.d)), 0) + GAP * (rows.length - 1);
            return { rows, h };
        }
        // Cada burbuja es un fallo: nunca verde. Crítico/Importante rojo,
        // Mejoras ámbar, Menor neutro (mismo código que el plan de acción).
        const TIER_FILL = [C.bad, C.bad, C.warn, C.text3];
        const TIER_STROKE = [C.badText, C.badText, C.warnText, C.text2];
        const TIER_FILL_OP = [0.22, 0.14, 0.18, 0.18];
        let bubbles = '';
        Object.entries(cells).forEach(([k, list]) => {
            const [e, im] = k.split('-').map(Number);
            list.sort((x, y) => rec(y) - rec(x));
            let scale = 1, L = layout(list, scale);
            while (L.h > ch - PADC * 2 && scale > 0.45) { scale -= 0.05; L = layout(list, scale); }
            const x0 = padL + e * cw, yTop = padT + (3 - im) * ch;
            let y = yTop + (ch - L.h) / 2;
            L.rows.forEach(row => {
                const rh = Math.max(...row.map(o => o.d));
                const rw = row.reduce((t, o) => t + o.d, 0) + GAP * (row.length - 1);
                let x = x0 + (cw - rw) / 2;
                row.forEach(({ c, d }) => {
                    const cx = x + d / 2, cy = y + rh / 2, r = d / 2, t = tierOf(c);
                    bubbles += `<circle class="ag-bubble" tabindex="0" role="img" cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="${r.toFixed(1)}" fill="${TIER_FILL[t]}" fill-opacity="${TIER_FILL_OP[t]}" stroke="${TIER_STROKE[t]}" stroke-width="1.5"
                        aria-label="${esc(c.advice.titulo + '. Impacto ' + c.advice.impacto + ', esfuerzo ' + c.advice.esfuerzo)}"
                        data-tip="${esc(c.advice.titulo + '||Impacto ' + c.advice.impacto + ' · esfuerzo ' + c.advice.esfuerzo + ' · arreglarlo recupera unos ' + rec(c).toFixed(1) + ' puntos. Cómo: ' + c.advice.como)}"/>
                        <text x="${cx.toFixed(1)}" y="${cy.toFixed(1)}" text-anchor="middle" dy="4" fill="${TIER_STROKE[t]}" font-family="Inter Tight, sans-serif" font-size="${r < 18 ? 11 : 13}" font-weight="700" style="pointer-events:none">${c.id}</text>`;
                    x += d + GAP;
                });
                y += rh + GAP;
            });
        });
        // Cuadrantes: «Hazlo ya» (esfuerzo bajo-medio × impacto alto-crítico)
        // en lima de marca; el resto rotulado en gris para orientar la lectura.
        const zone = (x, y, w, h, fill, op) => `<rect x="${x + 3}" y="${y + 3}" width="${w - 6}" height="${h - 6}" rx="14" fill="${fill}" fill-opacity="${op}"/>`;
        const label = (x, y, t, col) => `<text x="${x}" y="${y}" fill="${col}" font-family="Inter Tight, sans-serif" font-size="11" font-weight="700" letter-spacing="1.4">${t}</text>`;
        const zones = zone(padL, padT, cw * 2, ch * 2, C.accent, 0.45)
            + zone(padL + cw * 2, padT, cw, ch * 2, C.grid, 0.9)
            + zone(padL, padT + ch * 2, cw * 2, ch * 2, C.grid, 0.5)
            + label(padL + 16, padT + 24, 'HAZLO YA', C.text)
            + label(padL + cw * 2 + 16, padT + 24, 'PLANIFÍCALO', C.text2)
            + label(padL + 16, padT + ch * 2 + 24, 'CUANDO PUEDAS', C.text3)
            + label(padL + cw * 2 + 16, padT + ch * 2 + 24, 'AL FINAL', C.text3);
        const xLabels = ['BAJO', 'MEDIO', 'ALTO'].map((t, i) =>
            `<text x="${padL + (i + 0.5) * cw}" y="${H - padB + 26}" text-anchor="middle" fill="${C.text3}" font-family="Inter Tight, sans-serif" font-size="11" font-weight="600">${t}</text>`).join('');
        const yLabels = ['BAJO', 'MEDIO', 'ALTO', 'CRÍTICO'].map((t, i) =>
            `<text x="${padL - 14}" y="${padT + (3 - i + 0.5) * ch}" text-anchor="end" dy="4" fill="${C.text3}" font-family="Inter Tight, sans-serif" font-size="10" font-weight="600">${t}</text>`).join('');
        const grid = [1, 2].map(i => `<line x1="${padL + i * cw}" y1="${padT}" x2="${padL + i * cw}" y2="${H - padB}" stroke="${C.border}" stroke-dasharray="3 4"/>`).join('')
            + [1, 2, 3].map(i => `<line x1="${padL}" y1="${padT + i * ch}" x2="${W - padR}" y2="${padT + i * ch}" stroke="${C.border}" stroke-dasharray="3 4"/>`).join('');
        const legend = TIERS.filter(t => items.some(c => tierOf(c) === t.ord)).map(t =>
            `<span><span class="ag-dot" style="background:${TIER_FILL[t.ord]}"></span>${t.title}</span>`).join('');
        return `<div class="ag-card">
            <h2 class="ag-card-title">Mapa de prioridades</h2>
            <p class="ag-card-sub">Cada burbuja es un problema. Cuanto más arriba, más impacto en el negocio; cuanto más a la derecha, más esfuerzo; cuanto más grande, más puntos recuperas. <b>Empieza por la zona «Hazlo ya».</b> Pasa el ratón o el foco por una burbuja para ver el detalle; la lista completa está debajo.</p>
            <div class="ag-chart-full"><svg viewBox="0 0 ${W} ${H}" role="group" aria-label="Mapa de prioridades: ${plural(items.length, 'problema', 'problemas')} por impacto y esfuerzo">
                ${zones}${grid}
                <line x1="${padL}" y1="${H - padB}" x2="${W - padR}" y2="${H - padB}" stroke="${C.border}"/>
                <line x1="${padL}" y1="${padT}" x2="${padL}" y2="${H - padB}" stroke="${C.border}"/>
                <text x="${padL + plotW / 2}" y="${H - 14}" text-anchor="middle" fill="${C.text2}" font-family="Inter Tight, sans-serif" font-size="11" font-weight="600" letter-spacing="1">ESFUERZO DE ARREGLO →</text>
                <text transform="rotate(-90 26 ${padT + plotH / 2})" x="26" y="${padT + plotH / 2}" text-anchor="middle" fill="${C.text2}" font-family="Inter Tight, sans-serif" font-size="11" font-weight="600" letter-spacing="1">IMPACTO EN EL NEGOCIO →</text>
                ${xLabels}${yLabels}${bubbles}
            </svg></div>
            <div class="ag-legend">${legend}</div></div>`;
    }

    // El bloque ya dice la prioridad: el título de cada acción lleva su color
    // (rojo en Crítico e Importante, naranja en Mejoras) y sobra repetir
    // impacto y esfuerzo en cada una. Solo se marca lo que se arregla rápido.
    function findingHTML(c, ord) {
        const a = c.advice;
        const qw = a.esfuerzo === 'Bajo' && (IMPORD[a.impacto] ?? 3) <= 2;
        return `<article class="ag-finding">
            <div class="ag-finding-top"><h3 class="ag-finding-title t${ord}">${esc(a.titulo)}</h3>
                ${qw ? `<span class="ag-qw">${ic('zap')} Arreglo rápido</span>` : ''}</div>
            <div class="ag-finding-cols">
                <div><div class="ag-subhead">Por qué te importa</div><p>${esc(a.por_que)}</p></div>
                <div class="is-fix"><div class="ag-subhead">Cómo se arregla</div><p>${esc(a.como)}</p></div>
            </div>
            <details class="ag-details"><summary>${ic('chevron-right', 'ag-caret')} Evidencia técnica · ${esc(nameOf(c))} (check ${esc(c.id)})</summary>
                <div class="ag-evidence-box">${esc(c.evidence)}</div></details>
        </article>`;
    }

    function paneHallazgos(d) {
        const items = d.client.checks.filter(c => c.score != null && c.score < 1 && c.advice)
            .sort((a, b) => (IMPORD[a.advice.impacto] ?? 3) - (IMPORD[b.advice.impacto] ?? 3) || a.score - b.score
                || (a.advice.esfuerzo === 'Bajo' ? -1 : 1) - (b.advice.esfuerzo === 'Bajo' ? -1 : 1));
        if (!items.length) {
            return `<div class="ag-pane">${emptyState('circle-check', 'Todos los checks puntuables pasan', 'No hay nada pendiente que arreglar en este análisis.')}</div>`;
        }
        const groups = TIERS.map((t, gi) => {
            const inTier = items.filter(c => Math.min(IMPORD[c.advice.impacto] ?? 3, 3) === t.ord);
            if (!inTier.length) return '';
            return `<details class="ag-tier t${t.ord}"${gi < 2 ? ' open' : ''}>
                <summary><span class="ag-tier-mark t${t.ord}"></span>
                    <span class="ag-tier-name">${t.title}</span>
                    <span class="ag-tier-count">${plural(inTier.length, 'punto', 'puntos')}</span>
                    <span class="ag-tier-hint">${t.hint}</span>
                    ${ic('chevron-right', 'ag-caret')}</summary>
                <div class="ag-tier-body">${inTier.map(c => findingHTML(c, t.ord)).join('')}</div>
            </details>`;
        }).join('');
        return `<div class="ag-pane">${bubbleChart(d.client)}
            <div class="ag-section"><p class="ag-help">Agrupado por prioridad. Cada punto explica qué falla, por qué le importa al negocio y cómo se arregla; esta última parte puede ir directa al equipo técnico.</p></div>
            ${groups}</div>`;
    }

    /* ───── Evidencias ───── */
    function outcomeOf(r) {
        const o = r.outcome || '?';
        const label = o.replace(/_/g, ' ');
        if (o === 'conseguido') return [`${ic('circle-check')} ${esc(label)}`, 'is-ok'];
        if (o === 'conseguido_con_friccion') return [`${ic('circle-check')} ${esc(label)}`, 'is-warn'];
        if (o === 'inconsistente') return [`${ic('circle-dashed')} ${esc(label)}`, 'is-warn'];
        if (o === 'no_disponible') return [`${ic('circle-slash')} ${esc(label)}`, 'is-na'];
        return [`${ic('circle-x')} ${esc(label)}`, 'is-bad'];
    }

    function agentPanelHTML(a) {
        if (!(a.agent_tests && a.agent_tests.agents)) return '';
        const at = a.agent_tests;
        const agents = Object.entries(at.agents).map(([name, r]) => {
            const [txt, cls] = outcomeOf(r);
            let cons = '';
            if (r.intentos > 1) {
                cons = `<div class="ag-runs"><span>Consistencia</span>${(r.runs || []).map((x, i) => {
                    const okr = String(x.outcome || '').startsWith('conseguido');
                    return `<span class="ag-run ${okr ? 'is-ok' : 'is-bad'}" title="Intento ${i + 1}: ${esc(x.outcome || '?')}">${ic(okr ? 'check' : 'x')}</span>`;
                }).join('')}<b>${r.exitos}/${r.intentos} intentos</b></div>`;
            }
            const p = r.progreso || {};
            let ruta = '';
            if (p.total) {
                const hechos = new Set((p.hitos || []).map(h => h.nombre));
                const todos = (at.hitos_tarea || []).length ? at.hitos_tarea
                    : [...(p.hitos || []).map(h => h.nombre), ...(p.pendientes || [])];
                ruta = `<p class="ag-help" style="margin-top:var(--cs-space-md)">Recorrido de la tarea: <b>${p.alcanzados}/${p.total}</b> pasos</p>
                    <ol class="ag-path">${todos.map(n => {
                        const done = hechos.has(n), stuck = !done && n === (p.pendientes || [])[0];
                        return `<li class="${done ? 'is-done' : stuck ? 'is-stuck' : ''}"><span class="ag-path-dot"></span>${esc(n)}${stuck ? '<span class="ag-path-note">se atascó aquí</span>' : ''}<span class="ag-sr">${done ? ' (completado)' : ' (no alcanzado)'}</span></li>`;
                    }).join('')}</ol>`;
            }
            return `<div class="ag-agent">
                <div class="ag-agent-top"><span class="ag-agent-name">${esc(AGENT_NAMES[name] || name)}</span>
                    <span class="ag-outcome ${cls}">${txt}</span>
                    ${r.steps ? `<span class="ag-muted">· ${plural(r.steps, 'paso', 'pasos')}</span>` : ''}</div>
                ${r.detail ? `<p class="ag-agent-detail">${esc(r.detail)}</p>` : ''}
                ${cons}${ruta}
                ${r.action_log && r.action_log.length ? `<details class="ag-details"><summary>${ic('chevron-right', 'ag-caret')} Registro de acciones del agente</summary>
                    <div class="ag-evidence-box">${r.action_log.map(esc).join('\n')}</div></details>` : ''}
            </div>`;
        }).join('');
        return `<div class="ag-card">
            <h2 class="ag-card-title">Prueba con agentes reales</h2>
            <p class="ag-card-sub">Tarea de tipología <b>${esc(typ(at.typology))}</b>${at.allow_submit ? ' · envío de formularios autorizado en este dominio' : ' · sin envíos (solo llegar y rellenar)'}. Cada agente controla un navegador real e intenta completarla; nunca se pagan compras ni se crean cuentas.</p>
            ${agents}</div>`;
    }

    /* La prueba más contundente del informe (ver a ChatGPT, Claude y Gemini
       intentarlo en tu web) estaba en la cuarta pestaña. Aquí, un resumen. */
    function agentsSummaryHTML(d) {
        const audits = [d.client, ...(d.competitors || []).filter(a => !a.error)];
        const conAgentes = audits.map((a, i) => ({ a, i })).filter(x => x.a.agent_tests && x.a.agent_tests.agents);
        if (!conAgentes.length) return '';
        // con un solo dominio probado, la columna "Web" solo repetiría su nombre
        const varias = conAgentes.length > 1;
        const rows = conAgentes.map(({ a, i }) => Object.entries(a.agent_tests.agents).map(([name, r]) => {
            const [txt, cls] = outcomeOf(r);
            const p = r.progreso || {};
            const atasco = (p.pendientes || [])[0];
            return `<tr>${varias ? `<td><span class="ag-entity"><span class="ag-dot" style="background:${SERIES[i % 3]}"></span>${esc(a.host)}</span></td>` : ''}
                <td><b>${esc(AGENT_NAMES[name] || name)}</b></td>
                <td><span class="ag-outcome ${cls}">${txt}</span></td>
                <td class="ag-muted">${p.total ? `${p.alcanzados}/${p.total} pasos${atasco ? ` · se atascó en «${esc(atasco)}»` : ''}` : ''}</td></tr>`;
        }).join('')).join('');
        return `<div class="ag-card ag-section">
            <div class="ag-card-head"><h2 class="ag-card-title">Qué pasó cuando los agentes lo intentaron</h2>
                <button type="button" class="ag-link-btn" data-rep-tab="3">Ver cada intento ${ic('arrow-right')}</button></div>
            <p class="ag-card-sub">ChatGPT, Claude y Gemini pilotaron un navegador real e intentaron completar una tarea${varias ? '' : ` en <b>${esc(conAgentes[0].a.host)}</b>`}. Nunca se paga ni se crean cuentas.</p>
            <div class="ag-table-wrap"><table class="ag-table ag-stack"><thead><tr>${varias ? '<th>Web</th>' : ''}<th>Agente</th><th>Resultado</th><th>Recorrido</th></tr></thead>
            <tbody>${rows}</tbody></table></div></div>`;
    }

    function domainSwitcher(audits, sel, attr) {
        return `<div class="ag-switcher" role="tablist">${audits.map((a, i) =>
            `<button type="button" class="btn-secondary ag-btn-sm${i === sel ? ' is-active' : ''}" ${attr}="${i}" role="tab" aria-selected="${i === sel}">
                <span class="ag-dot" style="background:${SERIES[i % 3]}"></span>${esc(a.host)}</button>`).join('')}</div>`;
    }

    let EV_SEL = 0, FB_SEL = 0, REPORT = null, EV_ALL = false, CMP_ALL = false;

    /* Señales de tipología en lista legible. Antes se pintaba el JSON crudo
       y se salía de la tarjeta. */
    const SIGNAL_NAMES = {
        schema_offer: 'schema Offer', schema_product: 'schema Product', schema_software: 'schema SoftwareApplication',
        add_to_cart: 'botón añadir al carrito', cart_url: 'URL de carrito', checkout_url: 'URL de checkout',
        login_url: 'URL de login', pricing_url: 'página de precios', signup_url: 'página de registro',
        free_trial: 'prueba gratuita', no_card: '«sin tarjeta»', saas_words: 'vocabulario SaaS'
    };
    function typologyHTML(a) {
        const ev = a.typology_evidence || {};
        const tipos = Object.entries(ev).filter(([, v]) => v && typeof v === 'object');
        if (!tipos.length) return '<p class="ag-help">Sin señales registradas.</p>';
        const sig = arr => (arr || []).map(x => SIGNAL_NAMES[x] || String(x).replace(/_/g, ' ')).join(', ');
        return `<ul class="ag-typo">${tipos.map(([t, v]) => `
            <li class="${t === a.typology ? 'is-picked' : ''}"><b>${esc(typ(t))}</b> · ${esc(v.puntos ?? 0)} ${(v.puntos === 1) ? 'punto' : 'puntos'}
                ${(v.fuertes || []).length ? `<span class="ag-typo-sig">Fuertes: ${esc(sig(v.fuertes))}</span>` : ''}
                ${(v.debiles || []).length ? `<span class="ag-typo-sig">Débiles: ${esc(sig(v.debiles))}</span>` : ''}
                ${!(v.fuertes || []).length && !(v.debiles || []).length ? '<span class="ag-typo-sig">Ninguna señal</span>' : ''}</li>`).join('')}</ul>`;
    }

    function paneEvidencias(d) {
        const audits = [d.client, ...(d.competitors || []).filter(a => !a.error)];
        const a = audits[EV_SEL] || audits[0];
        const bots = Object.entries(a.bot_matrix || {}).map(([b, c]) => {
            const cls = c === 200 ? 'is-ok' : (c === 0 || c === 403 || c === 429) ? 'is-bad' : 'is-part';
            const k = cls.replace('is-', '');
            return `<tr><td>${esc(b === '_human' ? 'Navegador humano' : b)}</td><td class="ag-num"><span class="ag-mark is-${k}">${ic(MARKS[k][0])} ${c === 0 ? 'sin respuesta' : c === 200 ? '200 · entra' : c}</span></td></tr>`;
        }).join('');
        const pages = (a.pages_sampled || []).map(p =>
            `<tr><td>${esc(p.bucket)}</td><td style="word-break:break-all">${esc(p.url)}</td><td class="ag-num">${esc(p.status)}</td><td>${esc(p.via)}</td></tr>`).join('');
        const wk = Object.keys(a.wellknown || {}).length
            ? `<ul class="ag-list">${Object.keys(a.wellknown).map(p => `<li><span class="ag-list-ic">${ic('plug')}</span><div class="ag-mono" style="align-self:center">${esc(p)}</div></li>`).join('')}</ul>`
            : '<p class="ag-help">Ninguna superficie agéntica expuesta.</p>';
        const fallos = (a.checks || []).filter(c => c.score != null && c.score < 1);
        const lista = EV_ALL ? (a.checks || []) : fallos;
        const checks = lista.map(c =>
            `<tr><td style="min-width:200px"><b>${esc(nameOf(c))}</b><span class="ag-hist-comp">check ${c.id}${c.manual ? ' · requiere revisión humana' : ''}</span></td>
            <td class="ag-center">${mark(c.score)}</td><td class="ag-evidence">${esc(c.evidence)}</td></tr>`).join('')
            || '<tr><td colspan="3" class="ag-muted">Ningún check falla en este dominio.</td></tr>';
        const ag = d.agentes || {};
        const sinAgentes = !(a.agent_tests && a.agent_tests.agents) && ag.solicitados && (ag.estado === 'completado' || ag.estado === 'error')
            ? alertHTML({ tone: 'warn', icon: 'bot-off', title: 'Sin evidencia agéntica en este dominio',
                body: 'La simulación con agentes no pudo completarse aquí, así que el check 6.3 de ' + esc(a.host) + ' sigue sin comprobar. No cuenta como fallo.' })
            : '';
        return `<div class="ag-pane">${domainSwitcher(audits, EV_SEL, 'data-ev')}
            ${agentPanelHTML(a)}${sinAgentes}
            <div class="ag-grid-2">
                <div class="ag-card">
                    <h2 class="ag-card-title">Acceso real de bots de IA</h2>
                    <p class="ag-card-sub">Peticiones reales con el user-agent oficial de cada bot.</p>
                    <div class="ag-table-wrap"><table class="ag-table"><thead><tr><th>User-agent</th><th class="ag-num">Respuesta</th></tr></thead><tbody>${bots}</tbody></table></div>
                </div>
                <div class="ag-card">
                    <h2 class="ag-card-title">Superficie agéntica encontrada</h2>
                    ${wk}
                    <h2 class="ag-card-title" style="margin-top:var(--cs-space-lg)">Tipología detectada</h2>
                    <p class="ag-help" style="margin-top:0">Clasificada como <b>${esc(typ(a.typology))}</b> por estas señales:</p>
                    ${typologyHTML(a)}
                    <p class="ag-help">Render JS: ${a.render_ok ? 'ejecutado' : 'no ejecutado'} · Vista LLM (Jina): ${a.jina_ok ? 'sí' : 'no'}</p>
                </div>
            </div>
            <div class="ag-card ag-section">
                <h2 class="ag-card-title">Páginas muestreadas</h2>
                <div class="ag-table-wrap"><table class="ag-table"><thead><tr><th>Plantilla</th><th>URL</th><th class="ag-num">HTTP</th><th>Vía</th></tr></thead><tbody>${pages}</tbody></table></div>
            </div>
            <div class="ag-card ag-section">
                <div class="ag-card-head"><h2 class="ag-card-title">Checks y su evidencia</h2>
                    <div class="ag-switcher ag-filter" role="group" aria-label="Filtrar checks">
                        <button type="button" class="btn-secondary ag-btn-sm${EV_ALL ? '' : ' is-active'}" data-evf="fail" aria-pressed="${!EV_ALL}">Fallos y parciales (${fallos.length})</button>
                        <button type="button" class="btn-secondary ag-btn-sm${EV_ALL ? ' is-active' : ''}" data-evf="all" aria-pressed="${EV_ALL}">Todos (${(a.checks || []).length})</button>
                    </div></div>
                <div class="ag-table-wrap"><table class="ag-table"><thead><tr><th>Check</th><th class="ag-center">Resultado</th><th>Evidencia</th></tr></thead><tbody>${checks}</tbody></table></div>
                ${MARK_LEGEND}
            </div></div>`;
    }

    /* ───── Fiabilidad ───── */
    function paneFiabilidad(d) {
        const audits = [d.client, ...(d.competitors || []).filter(a => !a.error)];
        const a = audits[FB_SEL] || audits[0];
        const statusFor = (au, id) => {
            const m = (au.checks || []).find(x => x.id === id);
            const lbl = (k, t) => `<span class="ag-mark is-${k}">${ic(MARKS[k][0])} ${t}</span>`;
            if (!m) return lbl('na', '');
            if ((m.evidence || '').startsWith('N/A')) return lbl('na', 'no aplica');
            if (m.score == null && m.manual) return lbl('part', 'criterio humano');
            if (m.score == null) return lbl('na', 'informativo');
            if (m.manual) return lbl('part', 'heurístico');
            return lbl('ok', 'medido');
        };
        const matrixRows = d.client.checks.map(c =>
            `<tr><td><b>${esc(nameOf(c))}</b><span class="ag-hist-comp">check ${c.id}</span></td>
            <td class="ag-muted" style="font-size:var(--cs-text-xs);min-width:260px">${esc(METHODS[c.id] || '')}</td>
            ${audits.map(au => `<td style="white-space:nowrap;font-size:var(--cs-text-xs)">${statusFor(au, c.id)}</td>`).join('')}</tr>`).join('');

        let body;
        if (!a.trail) {
            body = alertHTML({ icon: 'history', title: 'Sin registro de procesos', body: 'Este análisis se generó con una versión anterior del motor. Relanza el análisis para tener el panel de fiabilidad.' });
        } else {
            const n = { ok: 0, warn: 0, fail: 0, skipped: 0 };
            a.trail.forEach(t => { n[t.status] = (n[t.status] || 0) + 1; });
            const manual = (a.checks || []).filter(x => x.manual);
            const informational = (a.checks || []).filter(x => x.score == null && !x.manual);
            let v;
            if (n.fail > 0) v = { tone: 'bad', icon: 'circle-x', title: 'Análisis incompleto', msg: `${n.fail} proceso(s) fallaron y hay checks sin evidencia. No entregar sin revisar o relanzar.` };
            else if (n.warn > 0 || n.skipped > 0) v = { tone: 'warn', icon: 'triangle-alert', title: 'Fiable con avisos', msg: `Todos los procesos corrieron, pero ${n.warn} con evidencia degradada y ${n.skipped} desactivados. Revisa los avisos antes de entregar.` };
            else v = { tone: 'good', icon: 'circle-check', title: 'Análisis completo y fiable', msg: 'Todos los procesos se ejecutaron con evidencia directa. Lo que dice el informe está respaldado.' };
            const IC = { ok: 'ok', warn: 'part', fail: 'bad', skipped: 'na' };
            const steps = a.trail.map(t => {
                return `<tr><td class="ag-center">${markOf(IC[t.status] || 'na')}</td>
                    <td style="font-weight:600;white-space:nowrap">${esc(t.step)}</td><td class="ag-muted">${esc(t.detail)}</td></tr>`;
            }).join('');
            const cov = a.coverage || {};
            const buckets = Object.entries(cov.buckets || {}).map(([b, total]) => {
                const sampled = (a.pages_sampled || []).filter(p => p.bucket === b).length;
                return `<tr><td>${esc(b)}</td><td class="ag-num">${total}</td><td class="ag-num">${sampled}</td></tr>`;
            }).join('');
            body = alertHTML({ tone: v.tone, icon: v.icon, title: v.title, body: `${v.msg} ${manual.length} checks marcados para criterio humano.` }) + `
                <div class="ag-card">
                    <h2 class="ag-card-title">Procesos ejecutados <span class="ag-muted">${a.trail.length}</span></h2>
                    <div class="ag-table-wrap"><table class="ag-table"><thead><tr><th></th><th>Proceso</th><th>Resultado / evidencia</th></tr></thead><tbody>${steps}</tbody></table></div>
                    <div class="ag-legend"><span>${markOf('ok')} ejecutado con evidencia</span><span>${markOf('part')} evidencia degradada</span><span>${markOf('bad')} el proceso falló</span><span>${markOf('na')} desactivado</span><span>Un 404 del sitio es un hallazgo, no un fallo del análisis.</span></div>
                </div>
                <div class="ag-grid-2">
                    <div class="ag-card">
                        <h2 class="ag-card-title">Cobertura del muestreo</h2>
                        <p class="ag-help" style="margin-top:0"><b>${cov.sampled_ok ?? '?'}/${cov.sampled ?? '?'}</b> páginas accesibles de ${cov.sitemap_urls ?? '?'} URLs del sitemap (tope 800) · ${cov.fallbacks ?? 0} vía fallback</p>
                        ${buckets ? `<div class="ag-table-wrap"><table class="ag-table"><thead><tr><th>Plantilla</th><th class="ag-num">Encontradas</th><th class="ag-num">Muestreadas</th></tr></thead><tbody>${buckets}</tbody></table></div>` : ''}
                        <p class="ag-help">Muestreo representativo, no exhaustivo: hasta 2 páginas por plantilla.</p>
                    </div>
                    <div class="ag-card">
                        <h2 class="ag-card-title">Requieren criterio humano <span class="ag-muted">${manual.length}</span></h2>
                        <ul class="ag-learn-checks">${manual.map(x => `<li><span>${x.id}</span>${esc(nameOf(x))}</li>`).join('') || '<li>Ninguno</li>'}</ul>
                        <h2 class="ag-card-title" style="margin-top:var(--cs-space-lg)">Informativos, no puntúan <span class="ag-muted">${informational.length}</span></h2>
                        <ul class="ag-learn-checks">${informational.map(x => `<li><span>${x.id}</span>${esc(nameOf(x))}</li>`).join('') || '<li>Ninguno</li>'}</ul>
                    </div>
                </div>`;
        }
        return `<div class="ag-pane">
            <p class="ag-help ag-pane-intro">Comprueba aquí que el análisis se hizo completo antes de compartir el informe: qué procesos corrieron, con qué evidencia y qué no se pudo verificar.</p>
            ${domainSwitcher(audits, FB_SEL, 'data-fb')}
            ${body}
            <details class="ag-card ag-section ag-fold">
                <summary><h2 class="ag-card-title">Matriz de factores</h2><span class="ag-muted">Qué revisamos, cómo, y si se pudo medir en cada dominio</span>${ic('chevron-down', 'ag-fold-caret')}</summary>
                <div class="ag-table-wrap"><table class="ag-table"><thead><tr><th>Factor</th><th>Metodología</th>${audits.map((au, i) => `<th><span class="ag-entity"><span class="ag-dot" style="background:${SERIES[i % 3]}"></span>${esc(au.host)}</span></th>`).join('')}</tr></thead>
                <tbody>${matrixRows}</tbody></table></div>
                <div class="ag-legend"><span>Medido: evidencia directa</span><span>Heurístico: evidencia parcial</span><span>Criterio humano: lo decide el analista</span><span>Informativo: se comprueba pero no puntúa</span></div>
            </details></div>`;
    }

    document.addEventListener('click', e => {
        const ev = e.target.closest('[data-ev]');
        if (ev && REPORT) { EV_SEL = +ev.dataset.ev; repaint(3); return; }
        const fb = e.target.closest('[data-fb]');
        if (fb && REPORT) { FB_SEL = +fb.dataset.fb; repaint(4); return; }
        const evf = e.target.closest('[data-evf]');
        if (evf && REPORT) { EV_ALL = evf.dataset.evf === 'all'; repaint(3); return; }
        const cmp = e.target.closest('[data-cmp]');
        if (cmp && REPORT) { CMP_ALL = cmp.dataset.cmp === 'all'; repaint(1); }
    });

    /* ───── Metodología ───── */
    function paneMetodologia(d) {
        const c = d.client;
        const w = Object.entries(c.category_weights || {}).map(([k, v]) =>
            `<tr><td><b>${k}</b> <span class="ag-muted">${esc(CATS[k] || '')}</span></td>
             <td style="width:40%"><div class="ag-bar ag-bar-sm"><i style="width:${Math.min(100, v * 3)}%"></i></div></td>
             <td class="ag-num"><b>${v}%</b></td></tr>`).join('');
        const manual = (c.checks || []).filter(x => x.manual).map(x => `<li><span>${x.id}</span>${esc(nameOf(x))}</li>`).join('');
        const b = bandOf(c.score);
        return `<div class="ag-pane"><div class="ag-grid-2" style="margin-top:0">
            <div class="ag-card">
                <h2 class="ag-card-title">Pesos aplicados <span class="ag-muted">${esc(typ(c.typology))}</span></h2>
                <div class="ag-table-wrap"><table class="ag-table"><tbody>${w}</tbody></table></div>
                <p class="ag-help">Cada check puntúa 0, 0,5 o 1 y pondera dentro de su categoría. Los checks críticos pesan más. Las categorías sin datos redistribuyen su peso.</p>
            </div>
            <div class="ag-card">
                <h2 class="ag-card-title">Escala</h2>
                <ul class="ag-list">${[
                    ['0–25', 'Invisible para agentes', 'Ni te leen ni te usan.'],
                    ['26–50', 'Legible, no operable', 'Te leen, no te entienden bien, no te usan.'],
                    ['51–75', 'Agent-aware', 'Bien posicionado; faltan capacidades ejecutables.'],
                    ['76–100', 'Agent-ready', 'Ventaja competitiva real.']
                ].map((s, i) => `<li><span class="ag-list-ic" style="width:56px;font-size:var(--cs-text-xs);font-weight:700;${i === b ? `background:${C.text};color:#FFFFFF` : ''}">${s[0]}</span>
                    <div><div class="ag-list-title">${s[1]}${i === b ? ' <span class="ag-muted">· este informe</span>' : ''}</div><div class="ag-list-body">${s[2]}</div></div></li>`).join('')}</ul>
            </div></div>
            <div class="ag-card ag-section">
                <h2 class="ag-card-title">Checks que requieren revisión humana</h2>
                <ul class="ag-learn-checks">${manual || '<li>Ninguno</li>'}</ul>
                <p class="ag-help">Metodología v${esc(String(d.framework_version || '').split(' ')[0] || '2.0')} · basada en estándares abiertos (RFC 9421, MCP, ACP, Schema.org) y el Agent Readiness score de Cloudflare. El campo evoluciona por trimestres: re-auditar cada 90 días.</p>
            </div></div>`;
    }

    /* ───────────────────────────── informe ───────────────────────────── */

    let CURRENT_JOB = null, ACTIVE_TAB = 0;
    const TABS = [
        ['Resumen', 'layout-dashboard', paneResumen],
        ['Comparativa', 'swords', paneComparativa],
        ['Plan de acción', 'list-checks', paneHallazgos],
        ['Evidencias', 'microscope', paneEvidencias],
        ['Fiabilidad', 'shield-check', paneFiabilidad],
        ['Metodología', 'book-open', paneMetodologia]
    ];

    function repaint(i) {
        ACTIVE_TAB = i;
        $$('#agRepTabs .nav-tab').forEach((b, j) => {
            b.classList.toggle('active', j === i);
            b.setAttribute('aria-selected', j === i ? 'true' : 'false');
            b.tabIndex = j === i ? 0 : -1;
        });
        $('#agPanes').setAttribute('aria-labelledby', 'agRepTab-' + i);
        $('#agPanes').innerHTML = TABS[i][2](REPORT);
        // los avisos informativos de la simulación viven en el Resumen; el
        // progreso (en curso, error, recién terminada) se ve en cualquier pestaña
        const bn = $('#agAgentsBanner');
        if (bn.dataset.scope === 'resumen') bn.hidden = i !== 0;
        refreshIcons();
    }

    // Navegación con flechas entre pestañas (patrón WAI-ARIA)
    document.addEventListener('keydown', e => {
        const tab = e.target.closest && e.target.closest('[role="tab"]');
        if (!tab || !['ArrowRight', 'ArrowLeft', 'Home', 'End'].includes(e.key)) return;
        const list = $$('[role="tab"]', tab.parentElement);
        let k = list.indexOf(tab);
        k = e.key === 'Home' ? 0 : e.key === 'End' ? list.length - 1 : (k + (e.key === 'ArrowRight' ? 1 : -1) + list.length) % list.length;
        e.preventDefault();
        list[k].focus();
        list[k].click();
    });

    document.addEventListener('click', e => {
        const t = e.target.closest('[data-rep-tab]');
        if (!t || !REPORT) return;
        repaint(+t.dataset.repTab);
        window.scrollTo({ top: 0, behavior: 'auto' });
    });

    function renderReport(d, jobId) {
        if (jobId) CURRENT_JOB = jobId;
        if (REPORT !== d && (!REPORT || REPORT.client?.host !== d.client?.host)) { EV_SEL = 0; FB_SEL = 0; ACTIVE_TAB = 0; }
        REPORT = d;
        const c = d.client;
        const comps = (d.competitors || []).filter(a => !a.error).map(a => a.host);
        $('#agRepTitle').innerHTML = `¿Está <span class="ag-hl">${esc(c.host)}</span> lista para la IA?`;
        $('#agRepSub').textContent = [fmtDate(d.generated), typ(c.typology),
            comps.length ? 'frente a ' + comps.join(' y ') : 'sin competidores'].filter(Boolean).join(' · ');
        $('#agRepTabs').innerHTML = TABS.map((t, i) =>
            `<button type="button" class="nav-tab${i === ACTIVE_TAB ? ' active' : ''}" id="agRepTab-${i}" data-rep-tab="${i}" role="tab" aria-controls="agPanes" aria-selected="${i === ACTIVE_TAB}" tabindex="${i === ACTIVE_TAB ? 0 : -1}">${t[0]}</button>`).join('');
        document.title = `${c.host} · Agent Readiness - ClicAndSEO`;
        show('#agReport');
        repaint(ACTIVE_TAB);
        // los nombres con tildes vienen del catálogo: si aún no había llegado,
        // se repinta cuando llegue
        if (!Object.keys(CHECK_NAMES).length) CATALOG_P.then(() => { if (REPORT === d) repaint(ACTIVE_TAB); });
        // Lo que la simulación NO llegó a comprobar se dice, no se calla: el
        // botón dice "Agentes simulados" aunque solo funcionara en 1 de 3.
        const ag = d.agentes || {};
        if (!AGENTS_POLL) {
            if (JUST_FINISHED != null) {
                const m = Math.floor(JUST_FINISHED / 60), sg = String(JUST_FINISHED % 60).padStart(2, '0');
                bannerAgentes(`<b>Análisis completado en ${m}:${sg}.</b> Esto es lo que hemos encontrado; el informe queda guardado en Informes.`, 'done', 'resumen');
                JUST_FINISHED = null;
            } else if (ag.detalle && (ag.estado === 'completado' || ag.estado === 'error')) {
                bannerAgentes(`<b>Simulación con agentes:</b> ${esc(ag.detalle)}`, ag.estado === 'error' ? 'error' : 'warn', 'resumen');
            } else {
                $('#agAgentsBanner').hidden = true;
                $('#agAgentsBanner').dataset.scope = '';
            }
            const bn = $('#agAgentsBanner');
            if (bn.dataset.scope === 'resumen') bn.hidden = ACTIVE_TAB !== 0;
        }
        pintarBotonAgentes(d);
    }

    $('#agBack').addEventListener('click', () => {
        document.title = 'Agent Readiness - ClicAndSEO';
        switchTab('informes');
    });

    /* Botón «Copiar prompt IA»: siempre en la barra de acciones del informe y,
       además, dentro del aviso de cobertura parcial. Trae el super prompt del
       servidor (construido desde lo ya verificado + la metodología) y lo copia. */
    document.addEventListener('click', async ev => {
        const b = ev.target.closest('.js-superprompt');
        if (!b) return;
        if (!CURRENT_JOB) return;
        const label = b.querySelector('span') || b;
        const orig = label.textContent;
        b.disabled = true;
        label.textContent = 'Generando…';
        try {
            const r = await fetch('/agent/api/prompt/' + CURRENT_JOB);
            const j = await r.json();
            if (!r.ok || !j.prompt) throw new Error(j.error || 'error');
            await navigator.clipboard.writeText(j.prompt);
            label.textContent = 'Copiado: pégalo en ChatGPT o Claude';
            setTimeout(() => { label.textContent = orig; b.disabled = false; }, 4000);
        } catch (e) {
            label.textContent = 'No se pudo copiar';
            b.disabled = false;
            setTimeout(() => { label.textContent = orig; }, 3000);
        }
    });

    /* Descargas: PDF (informe para dirección) y JSON (datos completos para IA) */
    async function download(kind, btn) {
        if (!CURRENT_JOB) return;
        const label = btn.querySelector('span') || btn;
        const old = label.textContent;
        btn.disabled = true;
        label.textContent = kind === 'pdf' ? 'Generando PDF…' : 'Preparando JSON…';
        try {
            const r = await fetch(`/agent/api/report/${CURRENT_JOB}.${kind}`);
            if (!r.ok) {
                let m = 'error';
                try { m = (await r.json()).error || m; } catch (_) { /* cuerpo no JSON */ }
                throw new Error(m);
            }
            const blob = await r.blob();
            const cd = r.headers.get('Content-Disposition') || '';
            // Flask manda filename=… sin comillas para el PDF y con comillas para el JSON
            const mm = cd.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = mm ? mm[1] : `agent-readiness.${kind}`;
            document.body.appendChild(a);
            a.click();
            setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1500);
        } catch (e) {
            alert('No se pudo descargar: ' + e.message);
        } finally {
            label.textContent = old;
            btn.disabled = false;
        }
    }
    $('#dlPdf').addEventListener('click', e => download('pdf', e.currentTarget));
    $('#dlJson').addEventListener('click', e => download('json', e.currentTarget));

    /* ───────────────────────────── simulación agéntica bajo demanda ─────────────
       El 6.3 es lo más lento (10-15 min): el análisis de factores termina primero
       y los agentes se lanzan desde aquí, en segundo plano. */
    let AGENTS_POLL = null;
    function setAgentsBtn(state) {
        const b = $('#btnAgents');
        const map = {
            idle: ['bot', 'Simular agentes', false],
            launching: ['loader-circle', 'Lanzando…', true],
            running: ['loader-circle', 'Simulando agentes…', true],
            done: ['circle-check', 'Agentes simulados', true],
            error: ['rotate-ccw', 'Reintentar simulación', false]
        };
        const [icon, txt, dis] = map[state] || map.idle;
        b.disabled = dis;
        b.className = state === 'done' ? 'btn-secondary' : 'btn-accent';
        b.innerHTML = `${ic(icon, icon === 'loader-circle' ? 'ag-spin' : '')} <span>${txt}</span>`;
        refreshIcons();
    }

    function pintarBotonAgentes(d) {
        const b = $('#btnAgents'), ag = d.agentes || {};
        if (!ag.solicitados) { b.hidden = true; return; }
        b.hidden = false;
        const est = ag.estado;
        if (est === 'corriendo') { setAgentsBtn('running'); arrancarPollAgentes(d); }
        else if (est === 'completado') { b.hidden = true; return; }
        else if (est === 'error') setAgentsBtn('error');
        else setAgentsBtn('idle');
        b.onclick = async () => {
            if (b.disabled) return;
            setAgentsBtn('launching');
            const r = await fetch('/agent/api/agents/' + CURRENT_JOB, {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({})
            });
            if (!r.ok) {
                const e = await r.json().catch(() => ({}));
                bannerAgentes(`<b>No se pudo lanzar la simulación.</b> ${esc(e.error || '')}`, 'error');
                setAgentsBtn('idle');
                return;
            }
            d.agentes.estado = 'corriendo';
            pintarBotonAgentes(d);
        };
    }

    function bannerAgentes(html, estado, scope) {
        const el = $('#agAgentsBanner');
        el.hidden = false;
        el.dataset.scope = scope || 'global';
        const icon = estado === 'error' ? 'circle-x' : estado === 'done' ? 'circle-check' : estado === 'warn' ? 'triangle-alert' : estado === 'info' ? 'info' : 'loader-circle';
        el.innerHTML = `<div class="ag-banner${estado === 'error' ? ' is-bad' : estado === 'done' ? ' is-good' : estado === 'warn' ? ' is-warn' : ''}">
            ${ic(icon, estado === 'running' ? 'ag-spin' : '')}<div>${html}</div></div>`;
        refreshIcons();
    }

    function arrancarPollAgentes(d) {
        if (AGENTS_POLL) return;
        AGENTS_POLL = setInterval(async () => {
            let s;
            try { s = await (await fetch('/agent/api/agents/' + CURRENT_JOB + '/status')).json(); } catch (e) { return; }
            if (s.status === 'running') {
                const m = Math.floor((s.elapsed || 0) / 60), seg = (s.elapsed || 0) % 60;
                bannerAgentes(`<b>${esc(s.phase || 'Simulando agentes…')}</b> · ${m}m ${seg}s. Puedes seguir usando el informe mientras tanto.
                    <span class="ag-banner-last">${esc((s.log || []).slice(-1)[0] || '')}</span>`, 'running');
                return;
            }
            clearInterval(AGENTS_POLL);
            AGENTS_POLL = null;
            if (s.status === 'error') {
                bannerAgentes(`<b>La simulación agéntica falló:</b> ${esc(s.error || 'error desconocido')}`, 'error');
                d.agentes.estado = 'error';
                pintarBotonAgentes(d);
                return;
            }
            if (s.status === 'done') {
                // el informe se recarga con las puntuaciones ya recalculadas
                const rr = await fetch('/agent/api/result/' + CURRENT_JOB);
                const nuevo = await rr.json();
                renderReport(nuevo, CURRENT_JOB);
                const det = (nuevo.agentes || {}).detalle;
                bannerAgentes(`<b>Simulación con agentes completada.</b> La puntuación ya la incluye y tienes el resumen en esta página; cada intento paso a paso está en <b>Evidencias</b>.${det ? ' ' + esc(det) : ''}`, det ? 'warn' : 'done', 'global');
            }
        }, 4000);
    }

    /* ───────────────────────────── arranque ───────────────────────────── */

    function route() {
        const p = new URLSearchParams(location.search);
        const job = p.get('job');
        if (job) { openJob(job); return; }
        if (ANALISIS_EN_CURSO) return;   // un "atrás" no saca de un análisis en curso
        switchTab(p.get('tab') || (APP && APP.dataset.initialTab) || 'nuevo', { keepUrl: true });
    }
    window.addEventListener('popstate', route);
    route();
    refreshIcons();
    // cuenta de informes en la pestaña sin esperar a abrirla
    if (!new URLSearchParams(location.search).get('tab')) loadHistory();
})();
