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
        return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
    }

    function fmtDateTime(iso) {
        if (!iso) return '';
        const d = new Date(iso);
        if (isNaN(d)) return String(iso).slice(0, 16).replace('T', ' ');
        return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }) + ' · '
            + d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
    }

    const TYPOLOGY = { ecommerce: 'E-commerce', saas: 'SaaS', corporativo: 'Corporate' };
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
        C1: 'Discoverability & access', C2: 'Identity & bot control', C3: 'Structured data',
        C4: 'Rendering & architecture', C5: 'Content for LLMs', C6: 'Capabilities & actions',
        C7: 'Agentic commerce'
    };
    const CAT_DESC = {
        C1: 'Can AI systems find you and get in? Measures robots.txt, sitemap, real firewall blocks and access without login.',
        C2: 'Do you control which bots get in and what they can do? Measures Content Signals, crawl management and agent identity verification.',
        C3: 'Is your data marked up so AI doesn\'t have to guess? Measures JSON-LD, your brand entity, product attributes and semantic HTML.',
        C4: 'Does your content exist without running JavaScript, and does it respond fast? That is what the ChatGPT, Claude or Perplexity crawlers see, since they don\'t run JS.',
        C5: 'Is your content written to be cited? Measures direct answers, self-contained sections, verifiable authorship and a Markdown version.',
        C6: 'Do you offer capabilities an agent can use, not just read? Measures MCP/A2A, APIs and operable forms.',
        C7: 'Can a shopping assistant sell your products? Measures a structured catalogue, price reliability and agentic checkout (ACP).'
    };
    const IMPORD = {
        'Crítico': 0, 'Alto': 1, 'Alto (apuesta de futuro)': 1, 'Alto (ventana de oportunidad)': 1,
        'Medio': 2, 'Medio (creciente)': 2, 'Bajo': 3, 'Bajo (hoy)': 3, 'Diagnóstico': 4,
        // claves en inglés (informes nuevos); las de arriba siguen para los informes guardados
        'Critical': 0, 'High': 1, 'High (future bet)': 1, 'High (window of opportunity)': 1,
        'Medium': 2, 'Medium (growing)': 2, 'Low': 3, 'Low (today)': 3, 'Diagnostic': 4
    };
    /* Los informes guardados antes de pasar la app a inglés traen impacto,
       esfuerzo y nombre de nivel en español. Se traducen al abrirlos (solo para
       mostrarlos; los códigos y claves no cambian) y así el resto del panel
       trabaja siempre con los valores en inglés. */
    const LEGACY_EN = {
        'Crítico': 'Critical', 'Alto': 'High', 'Alto (apuesta de futuro)': 'High (future bet)',
        'Alto (ventana de oportunidad)': 'High (window of opportunity)', 'Medio': 'Medium',
        'Medio (creciente)': 'Medium (growing)', 'Bajo': 'Low', 'Bajo (hoy)': 'Low (today)', 'Diagnóstico': 'Diagnostic',
        'Invisible para agentes': 'Invisible to agents', 'Legible, no operable': 'Readable, not operable',
        'Puerta cerrada a agentes': 'Closed to agents', 'No evaluable desde nuestra red': 'Not assessable from our network'
    };
    function localizeLegacy(d) {
        [d && d.client, ...((d && d.competitors) || [])].forEach(a => {
            if (!a) return;
            if (a.level && LEGACY_EN[a.level.name]) a.level.name = LEGACY_EN[a.level.name];
            (a.checks || []).forEach(c => {
                if (!c.advice) return;
                if (LEGACY_EN[c.advice.impacto]) c.advice.impacto = LEGACY_EN[c.advice.impacto];
                if (LEGACY_EN[c.advice.esfuerzo]) c.advice.esfuerzo = LEGACY_EN[c.advice.esfuerzo];
            });
        });
        return d;
    }
    /* metodología de cada check (matriz de fiabilidad y detalle check a check) */
    const METHODS = {
        '1.1': 'GET /robots.txt and syntax validation (parseable plain text, not HTML)',
        '1.2': 'Parsing of rules per AI user agent; blocking live-search bots is penalised',
        '1.3': 'Real requests with each bot\'s official UA, checked against what robots.txt declares',
        '1.4': 'GET of sitemap(s) and indexes, URL count and lastmod freshness (<90 days)',
        '1.5': 'Inspection of Link headers (RFC 8288) in the HTTP response',
        '1.6': 'Anonymous fetch of the sampled pages: is there useful content without a session?',
        '1.7': 'DNS TXT lookup of _aid/_agent (experimental standard)',
        '2.1': 'Parsing of Content Signals (search / ai-input / ai-train) in robots.txt',
        '2.2': 'CDN/WAF detection from headers + 402 responses observed for bots',
        '2.3': 'GET /.well-known/http-message-signatures-directory with JWKS validation',
        '2.4': '10 consecutive requests as GPTBot: pattern of response codes',
        '3.1': 'Extraction and parsing of every JSON-LD block on the sampled pages',
        '3.2': 'Validation of Organization/LocalBusiness fields on the homepage',
        '3.3': 'Validation of Product/Offer (price, priceCurrency, availability) on product pages',
        '3.4': 'Count of rich attributes (GTIN, brand, rating, dates…) in the markup',
        '3.5': 'DOM analysis: heading hierarchy, landmarks, button vs div-onclick',
        '3.6': 'Count of clickable div/span without semantics vs native and mitigated controls (role+tabindex)',
        '4.1': 'Comparison of visible text: raw HTML (curl) vs JS-rendered (Camoufox)',
        '4.2': 'Search for price and buy CTA in the HTML without running JS',
        '4.3': 'TTFB measured on every sampled page',
        '4.4': 'Direct GET without a session for each sampled deep URL',
        '4.5': 'Probe of /openapi.json, /swagger.json and /api-docs',
        '4.6': 'CLS via the PageSpeed Insights API (requires --psi and an API key)',
        '5.1': 'Deterministic analysis of the block after the H1: data density vs filler wording',
        '5.2': 'Section by section H2/H3: descriptive heading + 25-450 word body + hierarchy jumps',
        '5.3': 'Verifiable authorship and dates in the schema/HTML of the sampled articles',
        '5.5': 'GET /llms.txt and /llms-full.txt with content validation (anti soft-404)',
        '5.6': 'Real request with Accept: text/markdown and analysis of the returned Content-Type/body',
        '6.1': 'Probe of 12 agentic paths (MCP/A2A/OAuth/Skills) with content validation',
        '6.2': 'Per-form analysis: for=id binding verified against the real ids, autocomplete, real submit and CAPTCHA. No forms are submitted (ethics)',
        '6.3': 'ChatGPT, Gemini and Claude drive a real browser, several runs per agent to measure consistency. In e-commerce: product→cart→checkout with contact and shipping details filled in. Card fields are blocked in code: nothing is ever paid and no accounts are created. Form submission only happens once and only on the client\'s domain, with explicit authorisation',
        '7.1': 'E-commerce platform detection + Product schema on the sampled product pages',
        '7.2': 'Comparison of the JSON-LD price against the visible price on the same product page',
        '7.3': 'Detection of an ACP-compatible PSP (Stripe / Shopify)',
        '7.4': 'Informational probe of x402/UCP/MPP + HTTP 402 signals (not scored, not in Cloudflare either)'
    };
    const CHECK_LINKS = {
        '1.1': '/robots.txt', '1.2': '/robots.txt', '2.1': '/robots.txt',
        '1.4': '/sitemap.xml', '5.5': '/llms.txt', '2.3': '/.well-known/http-message-signatures-directory'
    };
    const STAGES = [
        { name: 'Can they read you?', desc: 'Access and crawling', cats: ['C1', 'C2'] },
        { name: 'Do they understand you?', desc: 'Data and content', cats: ['C3', 'C4', 'C5'] },
        { name: 'Can they use you?', desc: 'Actions and purchase', cats: ['C6', 'C7'] }
    ];
    const TIERS = [
        { ord: 0, title: 'Critical', hint: 'It is holding agents back today. Fix this first.' },
        { ord: 1, title: 'Important', hint: 'High impact on your visibility and on your ability to be used.' },
        { ord: 2, title: 'Recommended improvements', hint: 'They add points and polish the agent experience.' },
        { ord: 3, title: 'Minor', hint: 'Low urgency: for when everything else is done.' }
    ];
    const SCALE = [
        { from: 0, to: 25, name: 'Invisible to agents' },
        { from: 26, to: 50, name: 'Readable, not operable' },
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
            el.textContent = cats === 7 ? 'Full audit' : `${cats} of 7 categories`;
            return;
        }
        el.textContent = on === all.length ? 'Full audit' : `${on} of ${all.length} factors`;
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
        if (!groups.length) $('#agFacList').innerHTML = '<p class="ag-help">The list of factors couldn\'t be loaded. You can still run the analysis: the selected categories will be checked.</p>';
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
        if (!$('#agU0').value.trim()) { err.textContent = 'Enter your website URL to get started.'; $('#agU0').setAttribute('aria-invalid', 'true'); $('#agU0').focus(); return; }
        // factores concretos seleccionados; si el catálogo no cargó, se cae a categorías
        const checks = $$('.ag-fac-item input[data-cat]:checked').map(i => i.value);
        const cats = checks.length
            ? [...new Set($$('.ag-fac-item input[data-cat]:checked').map(i => i.dataset.cat))]
            : $$('#agCats input:checked').map(i => i.value);
        if (!cats.length) { err.textContent = 'Select at least one factor or category to analyse.'; return; }
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

    /* El backend responde "URL not allowed (x): <motivo>" (antes "URL no permitida").
       Se traduce a qué falló y qué hacer, y se marca el campo afectado. */
    function showFormError(raw) {
        const err = $('#agErr');
        ['#agU0', '#agU1', '#agU2'].forEach(q => { $(q).removeAttribute('aria-invalid'); });
        const m = String(raw || '').match(/URL (?:not allowed|no permitida) \(([^)]*)\):\s*(.*)$/);
        if (m) {
            const field = ['#agU0', '#agU1', '#agU2'].map(q => $(q)).find(i => i.value.trim() === m[1]);
            if (field) { field.setAttribute('aria-invalid', 'true'); field.focus(); }
            const why = /no resuelve|resolve/i.test(m[2])
                ? 'We couldn\'t find that domain. Check it is spelled correctly, for example https://yourbrand.com.'
                : /privad|interna|private|internal|local/i.test(m[2])
                    ? 'That is an internal or private address: only public websites can be analysed.'
                    : m[2];
            err.textContent = `“${m[1]}”: ${why}`;
            return;
        }
        if (/en curso|already running/i.test(raw)) { err.textContent = 'An analysis is already running. Wait for it to finish or cancel it from its screen.'; return; }
        err.textContent = 'We couldn\'t start the analysis: ' + raw;
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
            b.innerHTML = `${ic('x')} Really cancel?`;
            refreshIcons();
            setTimeout(() => {
                if (b.dataset.confirm === '1') {
                    b.dataset.confirm = '0';
                    b.classList.remove('btn-danger-confirm');
                    b.innerHTML = `${ic('x')} Cancel analysis`;
                    refreshIcons();
                }
            }, 4000);
            return;
        }
        b.dataset.confirm = '0';
        b.classList.remove('btn-danger-confirm');
        b.innerHTML = `${ic('x')} Cancel analysis`;
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
       (engine.py: "robots.txt…", "sitemap…", "rendering the homepage…"). Cada paso
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
        { re: /(^|:\s*)(home|homepage)…/i, ids: ['1.5', '1.8', '3.2', '3.5'] },
        { re: /bot access matrix|matriz de acceso/i, ids: ['1.3', '2.2'] },
        { re: /agentic surface|superficie agéntica/i, ids: ['2.3', '4.5', '5.5', '6.1', '7.4'] },
        { re: /sampling pages|muestreo/i, ids: ['1.6', '3.1', '3.4', '4.3', '4.4', '4.9', '5.1', '5.2', '5.3', '5.8', '6.2'] },
        { re: /product pages by content|fichas de producto/i, ids: ['3.3', '4.2', '7.1', '7.2', '7.3', '7.5', '7.6'] },
        { re: /rendering the homepage|render de la home/i, ids: ['3.6', '4.1'] },
        { re: /click targets on other|zonas de clic en otras/i, ids: ['4.7'] },
        { re: /login area|área de acceso/i, ids: ['6.4'] },
        { re: /error states|estados de error/i, ids: ['4.8'] },
        { re: /markdown|dns-aid/i, ids: ['1.7', '5.6'] },
        { re: /wikidata|trust pages|páginas de confianza/i, ids: ['3.7', '5.7'] },
        { re: /LLM view|vista LLM|jina/i, ids: ['4.6'] },
        { re: /agentic tests|pruebas agénticas/i, ids: [] },
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
        if (f.id === '6.3') return 'completed separately';
        if (LIVE_SEL && (LIVE_SEL.ids.size ? !LIVE_SEL.ids.has(f.id) : !LIVE_SEL.cats.has(catOfId(f.id)))) return 'not selected';
        if (ECOM_ONLY.includes(f.id) && LIVE.typ && LIVE.typ !== 'ecommerce' && !LIVE.fichas) return 'not applicable: not e-commerce';
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
        const typLine = seg.find(l => /(site type|tipología):\s*\S/i.test(l));
        if (typLine) LIVE.typ = typLine.replace(/^.*(site type|tipología):\s*/i, '').trim().toLowerCase();
        LIVE.fichas = seg.some(l => /product pages by content|fichas de producto/i.test(l));
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
            b.setAttribute('aria-label', `${CATS[CAT_KEYS[j]]}: ${{ done: 'data collected', current: 'collecting data', partial: 'partly collected', pending: 'pending', skip: 'not analysed' }[st]}`);
        });
        const facs = (CATALOG && CATALOG[k]) || [];
        const juego = enJuego();
        const total = juego.length;
        const hechos = juego.filter(f => LIVE.done.has(f.id)).length;
        // último paso: la evaluación de todos los factores, cuando ya están todos los datos
        const ultimo = LIVE.last === LIVE_STEPS.length - 1;
        const evalSt = LIVE.finished ? 'done' : ultimo ? 'next' : 'pending';
        const evalTxt = { done: `${plural(total, 'factor', 'factors')} evaluated`, next: `Next: evaluating the ${plural(total, 'factor', 'factors')}`, pending: `Final step: evaluating the ${plural(total, 'factor', 'factors')}` }[evalSt];
        $('#agLearnStatus').innerHTML = CATALOG
            ? `<div class="ag-learn-progress"><span>${LIVE.host ? `Collecting data from <b>${esc(LIVE.host)}</b>` : 'Preparing data collection'}</span><span><b>${hechos}</b> of ${plural(total, 'factor', 'factors')} with data</span></div>
               <div class="ag-bar ag-bar-sm"><i style="width:${total ? Math.round(hechos / total * 100) : 0}%"></i></div>
               ${LIVE.step ? `<p class="ag-learn-now">${ic('loader-circle', 'ag-spin')} Now: ${esc(LIVE.step)}</p>` : ''}
               <p class="ag-learn-final is-${evalSt}">${ic(evalSt === 'done' ? 'check' : 'list-checks')} ${esc(evalTxt)}</p>`
            : '';
        const fstate = f => skipOf(f) ? 'skip' : LIVE.done.has(f.id) ? 'done' : LIVE.current.includes(f.id) ? 'current' : 'pending';
        const ficon = { done: ic('database'), current: ic('loader-circle', 'ag-spin'), pending: ic('circle-dashed'), skip: ic('minus') };
        $('#agLearnBody').innerHTML = `
            <div>
                <h3>${esc(CATS[k])}</h3>
                <p class="ag-learn-meta">Category ${i + 1} of 7 · ${k}</p>
                <p>${esc(CAT_DESC[k])}</p>
            </div>
            <ul class="ag-learn-checks">${facs.map(f => {
                const st = fstate(f);
                const nota = st === 'skip' ? `<span class="ag-learn-skip">${esc(skipOf(f))}</span>` : '';
                const sr = { done: ' (data collected)', current: ' (collecting data)', pending: ' (pending)', skip: '' }[st];
                return `<li class="is-${st}"><span class="ag-learn-ic">${ficon[st]}</span><span class="ag-learn-name">${esc(f.nombre)}</span>${nota}${sr ? `<span class="ag-sr">${sr}</span>` : ''}</li>`;
            }).join('') || '<li>Loading factors…</li>'}</ul>`;
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
            t.querySelector('span').textContent = LOG_OPEN ? 'Show latest only' : 'View full log';
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
        $('#agRunHost').textContent = first.replace(/^https?:\/\//, '').replace(/^www\./, '').replace(/\/$/, '') || 'your site';
        $('#agPhase').textContent = 'Preparing analysis…';
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
                : d.state === 'running' ? `${ic('loader-circle', 'ag-spin')} analysing`
                    : d.state === 'error' ? `${ic('circle-x')} error` : `${ic('clock')} queued`;
            return `<li class="is-${esc(d.state)}">
                <span class="ag-run-host"><span class="ag-dot" style="background:${SERIES[i % 3]}"></span>${esc(d.host)}
                <span class="ag-run-role">${i === 0 ? 'your site' : 'competitor'}</span></span>
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
                $('#agPhase').textContent = 'Analysis running (waiting for the server)…';
                setTimeout(() => poll(id, intentos + 1), 10000); return;
            }
            if (r.status === 404) {
                // el job ya no está en memoria: quizá terminó y está guardado
                ANALISIS_EN_CURSO = null; stopLearn();
                openSaved(id, 'Analysis not found (server restarted?)');
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
            if (s.status === 'cancelled') { ANALISIS_EN_CURSO = null; stopLearn(); showMissing('Analysis cancelled', 'It was cancelled because nobody was watching it or because you cancelled it. You can run it again.'); return; }
            if (s.status === 'error') { ANALISIS_EN_CURSO = null; stopLearn(); showMissing('We couldn\'t complete the analysis', s.error || 'Analysis error'); return; }
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
        showMissing(notFoundTitle || 'We couldn\'t find this report',
            'It may have been cancelled, the server may have restarted before it finished, or it was deleted from the history.');
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
                if (s.status === 'cancelled') { showMissing('Analysis cancelled', 'It was cancelled because nobody was watching it or because you cancelled it. You can run it again.'); return; }
                if (s.status === 'error') { showMissing('We couldn\'t complete the analysis', s.error || 'Analysis error'); return; }
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
            if (IS_ADMIN) $('#agHistScope').textContent = 'As an administrator you see the reports of every user with access.';
            if (j.persistencia === false) {
                body.innerHTML = emptyState('database', 'History is not available',
                    'The reports database is not responding right now. Analyses still work, but they can\'t be listed.');
                refreshIcons(); return;
            }
            if (!items.length) {
                body.innerHTML = emptyState('folder-open', 'No reports yet',
                    'When you run your first analysis it will appear here, ready to reopen or download.',
                    `<button type="button" class="btn-primary" data-ag-goto="nuevo">${ic('plus')} New analysis</button>`);
                refreshIcons(); return;
            }
            body.innerHTML = `<div class="ag-card ag-table-wrap"><table class="ag-table ag-stack">
                <thead><tr><th>Domain</th><th>Date</th><th>Site type</th><th>Agents</th><th class="ag-num">Score</th><th><span class="ag-sr">Actions</span></th></tr></thead>
                <tbody>${items.map(histRow).join('')}</tbody></table></div>`;
            refreshIcons();
        } catch (e) {
            body.innerHTML = emptyState('circle-alert', 'The history couldn\'t be loaded', 'Try again in a few seconds.');
            refreshIcons();
        }
    }

    function histRow(it) {
        const s = typeof it.score === 'number' ? Math.round(it.score * 10) / 10 : null;
        const agentes = { completado: 'Simulated', pendiente: 'Not started', corriendo: 'Running', error: 'Failed', desactivadas: 'Not requested' }[it.agentes] || 'Not requested';
        const fiable = it.fiable === false
            ? `<span class="ag-hist-comp is-warn-text" data-tip="Limited read||The site blocked part of the access: some factors couldn\'t be verified.">${ic('triangle-alert')} limited read</span>` : '';
        return `<tr class="ag-hist-row">
            <td class="c-main"><span class="ag-hist-host">${esc(it.host)}</span>
                ${it.competidores ? `<span class="ag-hist-comp">vs ${esc(it.competidores)}</span>` : ''}${fiable}</td>
            <td class="c-meta" data-label="Date" style="white-space:nowrap">${esc(fmtDateTime(it.fecha))}</td>
            <td class="c-meta" data-label="Site type">${esc(typ(it.tipologia))}</td>
            <td class="c-meta" data-label="Agents">${esc(agentes)}</td>
            <td class="ag-num c-score"><span class="ag-hist-score">${s !== null ? `<span class="ag-bar ag-bar-sm"><i class="is-${scoreTone(s)}" style="width:${Math.max(0, Math.min(100, s))}%"></i></span><b class="is-${scoreTone(s)}-text">${s}</b>` : '—'}</span></td>
            <td class="c-actions"><div class="ag-hist-actions">
                <button type="button" class="btn-secondary ag-btn-sm" data-open="${esc(it.id)}">Open</button>
                <button type="button" class="btn-ghost ag-btn-sm" data-del="${esc(it.id)}" aria-label="Delete report for ${esc(it.host)}">${ic('trash-2')}</button>
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
            d.innerHTML = 'Delete?';
            setTimeout(() => {
                if (d.dataset.confirm === '1') {
                    d.dataset.confirm = '0'; d.classList.remove('btn-danger-confirm');
                    d.innerHTML = ic('trash-2'); refreshIcons();
                }
            }, 3500);
            return;
        }
        d.disabled = true;
        d.textContent = 'Deleting…';
        try {
            const r = await fetch('/agent/api/historial/' + encodeURIComponent(d.dataset.del), { method: 'DELETE' });
            const j = await r.json();
            if (!j.borrado) throw new Error('not deleted');
        } catch (err) {
            d.textContent = 'Failed';
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
                list.innerHTML = '<p class="ag-help">You haven\'t given access to any email yet. Administrators have access by default.</p>';
                return;
            }
            list.innerHTML = `<div class="ag-table-wrap"><table class="ag-table"><thead><tr><th>Email</th><th>Added</th><th></th></tr></thead><tbody>` +
                emails.map(e => `<tr class="ag-hist-row">
                    <td><b>${esc(e.email)}</b></td>
                    <td class="ag-muted">${esc(e.added_at || '')}${e.added_by ? ` · by ${esc(e.added_by)}` : ''}</td>
                    <td><div class="ag-hist-actions">
                        <button type="button" class="btn-secondary ag-btn-sm" data-resend="${esc(e.email)}">Resend invitation</button>
                        <button type="button" class="btn-ghost ag-btn-sm" data-revoke="${esc(e.email)}">Remove access</button>
                    </div></td></tr>`).join('') + '</tbody></table></div>';
        } catch (e) {
            list.innerHTML = '<p class="ag-help">The list couldn\'t be loaded.</p>';
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
            if (!email) { $('#agAccErr').textContent = 'Enter an email.'; return; }
            $('#agAccAdd').disabled = true;
            try {
                const r = await fetch('/agent/api/access/add', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email })
                });
                const j = await r.json();
                if (!r.ok) throw new Error(j.error || 'error');
                $('#agAccEmail').value = '';
                if (j.email_sent) accMsg('Access granted. We have sent the invitation to ' + j.email + '.', true);
                else accMsg('Access granted, but the invitation couldn\'t be sent. Try “Resend invitation” in the list.');
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
                rs.textContent = 'Sending…'; rs.disabled = true;
                try {
                    const j = await (await fetch('/agent/api/access/resend', {
                        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email })
                    })).json();
                    accMsg(j.email_sent ? 'Invitation resent to ' + email + '.' : 'The email couldn\'t be sent (check the environment\'s SMTP settings).', j.email_sent);
                } catch (_) { accMsg('Error while resending.'); }
                finally { rs.textContent = old; rs.disabled = false; }
                return;
            }
            const b = e.target.closest('[data-revoke]');
            if (!b) return;
            if (b.dataset.confirm !== '1') {
                b.dataset.confirm = '1';
                b.textContent = 'Confirm?';
                b.classList.add('btn-danger-confirm');
                setTimeout(() => {
                    if (b.dataset.confirm === '1') { b.dataset.confirm = '0'; b.textContent = 'Remove access'; b.classList.remove('btn-danger-confirm'); }
                }, 3500);
                return;
            }
            b.textContent = 'Removing…'; b.disabled = true;
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
        ok: ['check', 'pass'], part: ['contrast', 'partial'], bad: ['x', 'fail'], na: ['minus', 'not applicable']
    };
    const markOf = k => `<span class="ag-mark is-${k}" role="img" aria-label="${MARKS[k][1]}">${ic(MARKS[k][0])}</span>`;
    const mark = s => markOf(s == null ? 'na' : s >= 1 ? 'ok' : s > 0 ? 'part' : 'bad');

    const MARK_LEGEND = `<div class="ag-legend">
        <span>${mark(1)} pass</span><span>${mark(0.5)} partial</span>
        <span>${mark(0)} fail</span><span>${mark(null)} not applicable / not measured</span></div>`;

    const stateOf = p => p >= 75 ? ['Strong', 'is-good'] : p >= 50 ? ['Needs work', 'is-warn'] : p >= 25 ? ['Weak', 'is-bad'] : ['Critical', 'is-bad'];

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
        return `<svg class="ag-gauge" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="Score ${score} out of 100">
            <path d="${arc}" fill="none" stroke="${C.grid}" stroke-width="16" stroke-linecap="round"/>
            <path d="${arc}" fill="none" stroke="${col}" stroke-width="16" stroke-linecap="round"
                stroke-dasharray="${(frac * L).toFixed(1)} ${L.toFixed(1)}" style="transition:stroke-dasharray .9s cubic-bezier(0.2,0.8,0.2,1)"/>
            ${ticks}
            <text x="${cx}" y="${cy - 24}" text-anchor="middle" fill="${C.text}" font-family="Inter Tight, sans-serif" font-size="48" font-weight="800" letter-spacing="-2">${score}</text>
            <text x="${cx}" y="${cy}" text-anchor="middle" fill="${C.text3}" font-family="Inter Tight, sans-serif" font-size="12" font-weight="600">${parcial ? 'partial score' : 'out of 100'}</text>
        </svg>`;
    }

    function scaleHTML(score) {
        const b = bandOf(score);
        const pos = Math.max(0, Math.min(100, score));
        return `<div class="ag-scale" data-tip="Agent readiness scale||0-25 invisible to agents · 26-50 readable but not operable · 51-75 agent-aware · 76-100 agent-ready.">
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
            <div class="ag-balance-bar" role="img" aria-label="${n.ok} pass, ${n.part} partial, ${n.bad} fail, ${n.na} not applicable">${seg('ok')}${seg('part')}${seg('bad')}${seg('na')}</div>
            <div class="ag-balance-legend">
                <span><span class="ag-sw is-ok"></span><b>${n.ok}</b> pass</span>
                <span><span class="ag-sw is-part"></span><b>${n.part}</b> partial</span>
                <span><span class="ag-sw is-bad"></span><b>${n.bad}</b> fail</span>
                <span><span class="ag-sw is-na"></span><b>${n.na}</b> not applicable</span>
            </div></div>`;
    }

    function catRows(a, color) {
        return Object.keys(CATS).filter(c => a.category_scores && a.category_scores[c] != null).map(c => {
            const p = pct(a.category_scores[c]);
            const [st, cls] = stateOf(p);
            return `<div class="ag-catrow" data-tip="${esc(c + ' · ' + CATS[c] + '||' + CAT_DESC[c] + ' The % is the checks passed, weighted by importance.')}">
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
                ${weak ? `<p class="ag-link-flag">${ic('link-2-off')} Weakest link: start here</p>` : ''}
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
        const qwAll = (c.checks || []).filter(x => x.advice && x.advice.esfuerzo === 'Low' && (IMPORD[x.advice.impacto] ?? 3) <= 2 && x.score < 1)
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
                    ${deg.degradados ? ` <b>${plural(deg.degradados, 'factor is', 'factors are')}</b> marked “not verifiable” because they couldn't be checked: they do not count as failures.` : ''}
                    ${c.cobertura_score != null ? ` This score covers <b>${pct(c.cobertura_score)}%</b> of the model.` : ''}
                    You can try again later: if the site was only rate limiting, the next analysis will be complete.
                    <br><br>Even if our network is blocked, you can complete the audit yourself: copy this prompt, paste it into ChatGPT or Claude and get the missing factors, with the guarantee that nothing is made up.`,
                actions: `<button type="button" class="btn-primary ag-btn-sm js-superprompt">${ic('clipboard-copy')} <span>Copy prompt to complete with AI</span></button>`
            });
        } else if (c.score_fiable === false && deg) {
            aviso = alertHTML({
                tone: 'warn',
                icon: 'shield-alert',
                title: 'Limited read',
                body: `${esc(deg.motivo)}. <b>${plural(deg.degradados, 'factor is', 'factors are')}</b> marked “not verifiable” because they couldn't be checked: they do not count as failures. You can run the analysis again later or from another network.`
            });
        }
        const pens = (c.penalties || []).map(p =>
            `<div class="ag-penalty">${ic('circle-minus')}<span>Penalty applied: <b>${esc(p[0])}</b> (${p[1]} points)</span></div>`).join('');
        const via = (c.via_lectura && c.via_lectura !== 'http')
            ? `<p class="ag-score-note">Content read via <b>${esc(c.via_lectura.replace('ua:', ''))}</b>${c.via_lectura.startsWith('ua:') ? ': normal access was blocked; each AI bot\'s real access is measured separately' : ''}.</p>` : '';
        const cobertura = parcial && c.cobertura_score != null
            ? `<p class="ag-score-note">Covers <b>${pct(c.cobertura_score)}%</b> of the model: only what could be verified.</p>` : '';

        return `<div class="ag-pane">${aviso}
            <div class="ag-grid-score">
                <div class="ag-card ag-score-card">
                    <h2 class="ag-card-title ag-score-title">${parcial ? 'Partial score' : 'Overall score'}</h2>
                    ${gaugeSVG(c.score, parcial)}
                    ${via}${cobertura}
                    <div class="ag-level ${parcial ? '' : 'is-' + scoreTone(c.score)}">${esc(c.level.name)}</div>
                    ${aviso && parcial ? '' : `<p class="ag-level-msg">${esc(c.level.msg)}</p>`}
                    ${scaleHTML(c.score)}
                    ${balanceHTML(c)}
                    ${pens}
                </div>
                <div class="ag-card">
                    <div class="ag-card-head"><h2 class="ag-card-title">Breakdown by category</h2>
                        <span class="ag-muted">${plural((c.checks || []).length, 'check', 'checks')}</span></div>
                    <div class="ag-catrows" style="margin-top:var(--cs-space-sm)">${catRows(c, null)}</div>
                </div>
            </div>
            ${agentsSummaryHTML(d)}
            <div class="ag-card ag-section">
                <h2 class="ag-card-title">The agent's journey through your site</h2>
                <p class="ag-card-sub">An agent first has to be able to <b>read you</b>, then <b>understand you</b> without getting it wrong, and only then can it <b>use you</b> (buy, book, get in touch). The chain breaks at the weakest link.</p>
                ${journeyHTML(c)}
            </div>
            <div class="ag-card ag-section">
                <h2 class="ag-card-title">Where to start</h2>
                <p class="ag-card-sub">The fixes with the biggest payoff for the least effort, from most to least urgent.</p>
                ${qw.length ? `<ol class="ag-steps">${qw.map((x, i) => `
                    <li class="ag-step t${Math.min(IMPORD[x.advice.impacto] ?? 3, 3)}"><span class="ag-qn" aria-hidden="true">${i + 1}</span>
                    <div><div class="ag-step-title">${esc(x.advice.titulo)}</div><div class="ag-step-body">${esc(x.advice.como)}</div>
                    <div class="ag-step-meta">Impact <b>${esc(String(x.advice.impacto).toLowerCase())}</b> · effort <b>${esc(String(x.advice.esfuerzo).toLowerCase())}</b></div></div></li>`).join('')}</ol>`
                : '<p class="ag-help">No quick fixes left: what remains needs more work and is in the action plan.</p>'}
                <div class="ag-cta-row"><button type="button" class="btn-secondary" data-rep-tab="2">${qwAll.length > qw.length ? `See the next ${qwAll.length - qw.length} and the full plan` : 'See the full action plan'} ${ic('arrow-right')}</button></div>
            </div></div>`;
    }

    /* ───── Comparativa ───── */
    function radarSVG(audits, size) {
        size = size || 360;
        const cats = Object.keys(CATS).filter(c => audits.some(a => a.category_scores && a.category_scores[c] != null));
        if (cats.length < 3) return '';
        const cx = size / 2, cy = size / 2, rad = size / 2 - 44, n = cats.length;
        const pt = (i, r) => { const a = -Math.PI / 2 + 2 * Math.PI * i / n; return [cx + r * Math.cos(a), cy + r * Math.sin(a)]; };
        let out = `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" role="img" aria-label="Category radar">`;
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
            out += `<polygon points="${pts}" fill="${col}" fill-opacity="${idx === 0 ? 0.14 : 0.06}" stroke="${col}" stroke-width="${idx === 0 ? 2.5 : 1.75}" stroke-linejoin="round" data-tip="${esc(a.host + '||The bigger and more even the polygon, the better prepared across all categories. ' + resume)}"/>`;
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
            return `<div class="ag-pane">${emptyState('swords', 'No competitors in this analysis',
                'Add one or two competitors when you run the analysis to compare them with the same yardstick.',
                `<button type="button" class="btn-primary" data-ag-goto="nuevo">${ic('plus')} New analysis</button>`)}</div>`;
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
            title: 'Different site types: the scores are not comparable',
            body: `You are comparing ${tipos.map(t => `<b>${esc(typ(t))}</b>`).join(' and ')}. Each site type is scored with different weights (the product-page category only counts in e-commerce) and the task an agent has to complete is not equally hard: when validating with real agents, SaaS sites completed between 25% and 100% of the journey and stores between 0% and 55%. That is why <b>no winner is highlighted</b>. Compare each domain with others of the same site type, or stick to the category breakdown, which is comparable.`
        }) : '';

        const ranking = audits.map((a, i) => {
            const win = !a.level.cobertura_parcial && best !== null && a.score === best;
            return `<tr class="ag-hist-row${win ? ' win' : ''}">
                <td class="c-main"><span class="ag-entity"><span class="ag-dot" style="background:${SERIES[i % 3]}"></span>${esc(a.host)}</span></td>
                <td class="c-meta ag-muted" data-label="Role">${i === 0 ? 'Your site' : 'Competitor ' + i}</td>
                <td class="c-meta" data-label="Site type">${esc(typ(a.typology))}</td>
                <td class="c-meta" data-label="Level">${esc(a.level.name)}${win ? ` <span class="ag-best" role="img" aria-label="top score" data-tip="Top score||Among domains of the same site type with a complete score.">${ic('trophy')}</span>` : ''}</td>
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
                return `<td class="ag-num"><span class="ag-cell"><span class="ag-bar ag-bar-sm"><i style="width:${p}%;background:${SERIES[i % 3]}"></i></span><b class="v is-${toneOf(p)}-text">${p}</b>${best ? `<span class="ag-best" role="img" aria-label="best in row">${ic('trophy')}</span>` : '<span class="ag-best"></span>'}</span></td>`;
            }).join('')}</tr>`;
        }).join('');

        const gaps = gapsOf(d.client, audits.slice(1));
        const gapsHTML = gaps.length
            ? `<ul class="ag-list">${gaps.map(g => `<li><span class="ag-list-ic">${ic('trending-down')}</span><div>
                <div class="ag-list-title">${g.c} · ${esc(CATS[g.c])}</div>
                <div class="ag-list-body">${esc(g.host)} is ahead of you by <b>${g.diff} points</b> (${g.v}% vs your ${g.mine}%).</div></div></li>`).join('')}</ul>`
            : '<p class="ag-help">No relevant gaps: no category where you are 15 points or more behind.</p>';

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
                    ? ` <a href="https://${esc(a.host)}${CHECK_LINKS[c.id]}" target="_blank" rel="noopener">open ${CHECK_LINKS[c.id]} ${ic('external-link')}</a>` : '';
                return `<div class="ag-ev-item"><div class="ag-ev-head"><span class="ag-dot" style="background:${SERIES[i % 3]}"></span>${esc(a.host)}${link}</div>
                    <div class="ag-evidence-box">${esc(m ? m.evidence : 'not analysed on this domain')}</div></div>`;
            }).join('');
            return `<tr class="ag-row-click" data-r="${ri}"><td><button type="button" class="ag-row-toggle" aria-expanded="false" aria-controls="agChk-${ri}">${ic('chevron-right', 'ag-caret')}<span>${esc(nameOf(c))}</span></button></td>${cells}</tr>
                <tr class="ag-row-detail" id="agChk-${ri}" hidden><td colspan="${audits.length + 1}">
                    <p class="ag-help" style="margin:0 0 var(--cs-space-sm)"><b>How it is measured:</b> ${esc(METHODS[c.id] || '')}</p>${detail}</td></tr>`;
        }).join('');

        const head = audits.map((a, i) => `<th class="ag-num"><span class="ag-entity" style="justify-content:flex-end"><span class="ag-dot" style="background:${SERIES[i % 3]}"></span>${esc(a.host)}</span></th>`).join('');
        const headC = audits.map((a, i) => `<th class="ag-center"><span class="ag-entity"><span class="ag-dot" style="background:${SERIES[i % 3]}"></span>${esc(a.host)}</span></th>`).join('');

        return `<div class="ag-pane">${avisoMixto}
            <div class="ag-card">
                <h2 class="ag-card-title">Score by domain</h2>
                <div class="ag-table-wrap"><table class="ag-table ag-stack"><thead><tr><th>Domain</th><th><span class="ag-sr">Role</span></th><th>Site type</th><th>Level</th><th class="ag-num">Score</th></tr></thead>
                <tbody>${ranking}</tbody></table></div>
            </div>
            <div class="ag-grid-2">
                <div class="ag-card">
                    <h2 class="ag-card-title">Profile by category</h2>
                    <div class="ag-chart-scroll" style="display:flex;justify-content:center">${radarSVG(audits)}</div>
                    <div class="ag-legend" style="justify-content:center">${audits.map((a, i) => `<span><span class="ag-dot" style="background:${SERIES[i % 3]}"></span>${esc(a.host)}</span>`).join('')}</div>
                </div>
                <div class="ag-card">
                    <h2 class="ag-card-title">Where they're ahead of you</h2>
                    <p class="ag-card-sub">Categories where a competitor beats you by 15 points or more.</p>
                    ${gapsHTML}
                </div>
            </div>
            <div class="ag-card ag-section">
                <h2 class="ag-card-title">Category by category</h2>
                <p class="ag-card-sub">Same checks and same weights for everyone. Figure in green (75 or more), orange (50-74) or red (under 50); the trophy marks the best in each row.</p>
                <div class="ag-table-wrap"><table class="ag-table ag-matrix"><thead><tr><th>Category</th>${head}</tr></thead><tbody>${matrix}</tbody></table></div>
            </div>
            <div class="ag-card ag-section">
                <div class="ag-card-head"><h2 class="ag-card-title">Check-by-check detail</h2>
                    <div class="ag-switcher ag-filter" role="group" aria-label="Filter checks">
                        <button type="button" class="btn-secondary ag-btn-sm${CMP_ALL ? '' : ' is-active'}" data-cmp="diff" aria-pressed="${!CMP_ALL}">Differences only (${nDiff})</button>
                        <button type="button" class="btn-secondary ag-btn-sm${CMP_ALL ? ' is-active' : ''}" data-cmp="all" aria-pressed="${CMP_ALL}">All (${d.client.checks.length})</button>
                    </div></div>
                <p class="ag-card-sub">Open a check to see each domain's evidence and the link to the resource.</p>
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
        const effOf = e => (e === 'Low' ? 0 : e === 'Medium' ? 1 : 2);
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
                        aria-label="${esc(c.advice.titulo + '. Impact ' + c.advice.impacto + ', effort ' + c.advice.esfuerzo)}"
                        data-tip="${esc(c.advice.titulo + '||Impact ' + c.advice.impacto + ' · effort ' + c.advice.esfuerzo + ' · fixing it recovers about ' + rec(c).toFixed(1) + ' points. How: ' + c.advice.como)}"/>
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
            + label(padL + 16, padT + 24, 'DO IT NOW', C.text)
            + label(padL + cw * 2 + 16, padT + 24, 'PLAN IT', C.text2)
            + label(padL + 16, padT + ch * 2 + 24, 'WHEN YOU CAN', C.text3)
            + label(padL + cw * 2 + 16, padT + ch * 2 + 24, 'LAST', C.text3);
        const xLabels = ['LOW', 'MEDIUM', 'HIGH'].map((t, i) =>
            `<text x="${padL + (i + 0.5) * cw}" y="${H - padB + 26}" text-anchor="middle" fill="${C.text3}" font-family="Inter Tight, sans-serif" font-size="11" font-weight="600">${t}</text>`).join('');
        const yLabels = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].map((t, i) =>
            `<text x="${padL - 14}" y="${padT + (3 - i + 0.5) * ch}" text-anchor="end" dy="4" fill="${C.text3}" font-family="Inter Tight, sans-serif" font-size="10" font-weight="600">${t}</text>`).join('');
        const grid = [1, 2].map(i => `<line x1="${padL + i * cw}" y1="${padT}" x2="${padL + i * cw}" y2="${H - padB}" stroke="${C.border}" stroke-dasharray="3 4"/>`).join('')
            + [1, 2, 3].map(i => `<line x1="${padL}" y1="${padT + i * ch}" x2="${W - padR}" y2="${padT + i * ch}" stroke="${C.border}" stroke-dasharray="3 4"/>`).join('');
        const legend = TIERS.filter(t => items.some(c => tierOf(c) === t.ord)).map(t =>
            `<span><span class="ag-dot" style="background:${TIER_FILL[t.ord]}"></span>${t.title}</span>`).join('');
        return `<div class="ag-card">
            <h2 class="ag-card-title">Priority map</h2>
            <p class="ag-card-sub">Each bubble is an issue. The higher up, the more business impact; the further right, the more effort; the bigger, the more points you recover. <b>Start with the “Do it now” zone.</b> Hover over or focus a bubble to see the detail; the full list is below.</p>
            <div class="ag-chart-full"><svg viewBox="0 0 ${W} ${H}" role="group" aria-label="Priority map: ${plural(items.length, 'issue', 'issues')} by impact and effort">
                ${zones}${grid}
                <line x1="${padL}" y1="${H - padB}" x2="${W - padR}" y2="${H - padB}" stroke="${C.border}"/>
                <line x1="${padL}" y1="${padT}" x2="${padL}" y2="${H - padB}" stroke="${C.border}"/>
                <text x="${padL + plotW / 2}" y="${H - 14}" text-anchor="middle" fill="${C.text2}" font-family="Inter Tight, sans-serif" font-size="11" font-weight="600" letter-spacing="1">EFFORT TO FIX →</text>
                <text transform="rotate(-90 26 ${padT + plotH / 2})" x="26" y="${padT + plotH / 2}" text-anchor="middle" fill="${C.text2}" font-family="Inter Tight, sans-serif" font-size="11" font-weight="600" letter-spacing="1">BUSINESS IMPACT →</text>
                ${xLabels}${yLabels}${bubbles}
            </svg></div>
            <div class="ag-legend">${legend}</div></div>`;
    }

    // El bloque ya dice la prioridad: el título de cada acción lleva su color
    // (rojo en Crítico e Importante, naranja en Mejoras) y sobra repetir
    // impacto y esfuerzo en cada una. Solo se marca lo que se arregla rápido.
    function findingHTML(c, ord) {
        const a = c.advice;
        const qw = a.esfuerzo === 'Low' && (IMPORD[a.impacto] ?? 3) <= 2;
        return `<article class="ag-finding">
            <div class="ag-finding-top"><h3 class="ag-finding-title t${ord}">${esc(a.titulo)}</h3>
                ${qw ? `<span class="ag-qw">${ic('zap')} Quick fix</span>` : ''}</div>
            <div class="ag-finding-cols">
                <div><div class="ag-subhead">Why it matters to you</div><p>${esc(a.por_que)}</p></div>
                <div class="is-fix"><div class="ag-subhead">How to fix it</div><p>${esc(a.como)}</p></div>
            </div>
            <details class="ag-details"><summary>${ic('chevron-right', 'ag-caret')} Technical evidence · ${esc(nameOf(c))} (check ${esc(c.id)})</summary>
                <div class="ag-evidence-box">${esc(c.evidence)}</div></details>
        </article>`;
    }

    function paneHallazgos(d) {
        const items = d.client.checks.filter(c => c.score != null && c.score < 1 && c.advice)
            .sort((a, b) => (IMPORD[a.advice.impacto] ?? 3) - (IMPORD[b.advice.impacto] ?? 3) || a.score - b.score
                || (a.advice.esfuerzo === 'Low' ? -1 : 1) - (b.advice.esfuerzo === 'Low' ? -1 : 1));
        if (!items.length) {
            return `<div class="ag-pane">${emptyState('circle-check', 'All scorable checks pass', 'There is nothing left to fix in this analysis.')}</div>`;
        }
        const groups = TIERS.map((t, gi) => {
            const inTier = items.filter(c => Math.min(IMPORD[c.advice.impacto] ?? 3, 3) === t.ord);
            if (!inTier.length) return '';
            return `<details class="ag-tier t${t.ord}"${gi < 2 ? ' open' : ''}>
                <summary><span class="ag-tier-mark t${t.ord}"></span>
                    <span class="ag-tier-name">${t.title}</span>
                    <span class="ag-tier-count">${plural(inTier.length, 'item', 'items')}</span>
                    <span class="ag-tier-hint">${t.hint}</span>
                    ${ic('chevron-right', 'ag-caret')}</summary>
                <div class="ag-tier-body">${inTier.map(c => findingHTML(c, t.ord)).join('')}</div>
            </details>`;
        }).join('');
        return `<div class="ag-pane">${bubbleChart(d.client)}
            <div class="ag-section"><p class="ag-help">Grouped by priority. Each item explains what is failing, why it matters to the business and how to fix it; that last part can go straight to the technical team.</p></div>
            ${groups}</div>`;
    }

    /* ───── Evidencias ───── */
    // los códigos de desenlace se guardan en español (son datos); aquí solo se rotulan
    const OUTCOME_EN = {
        conseguido: 'achieved', conseguido_con_friccion: 'achieved with friction', no_conseguido: 'not achieved',
        inconsistente: 'inconsistent', no_verificable: 'not verifiable', no_disponible: 'not available', error: 'error'
    };
    const outcomeLabel = o => OUTCOME_EN[o] || String(o || '?').replace(/_/g, ' ');
    function outcomeOf(r) {
        const o = r.outcome || '?';
        const label = outcomeLabel(o);
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
                cons = `<div class="ag-runs"><span>Consistency</span>${(r.runs || []).map((x, i) => {
                    const okr = String(x.outcome || '').startsWith('conseguido');
                    return `<span class="ag-run ${okr ? 'is-ok' : 'is-bad'}" title="Attempt ${i + 1}: ${esc(outcomeLabel(x.outcome))}">${ic(okr ? 'check' : 'x')}</span>`;
                }).join('')}<b>${r.exitos}/${r.intentos} attempts</b></div>`;
            }
            const p = r.progreso || {};
            let ruta = '';
            if (p.total) {
                const hechos = new Set((p.hitos || []).map(h => h.nombre));
                const todos = (at.hitos_tarea || []).length ? at.hitos_tarea
                    : [...(p.hitos || []).map(h => h.nombre), ...(p.pendientes || [])];
                ruta = `<p class="ag-help" style="margin-top:var(--cs-space-md)">Task journey: <b>${p.alcanzados}/${p.total}</b> steps</p>
                    <ol class="ag-path">${todos.map(n => {
                        const done = hechos.has(n), stuck = !done && n === (p.pendientes || [])[0];
                        return `<li class="${done ? 'is-done' : stuck ? 'is-stuck' : ''}"><span class="ag-path-dot"></span>${esc(n)}${stuck ? '<span class="ag-path-note">got stuck here</span>' : ''}<span class="ag-sr">${done ? ' (completed)' : ' (not reached)'}</span></li>`;
                    }).join('')}</ol>`;
            }
            return `<div class="ag-agent">
                <div class="ag-agent-top"><span class="ag-agent-name">${esc(AGENT_NAMES[name] || name)}</span>
                    <span class="ag-outcome ${cls}">${txt}</span>
                    ${r.steps ? `<span class="ag-muted">· ${plural(r.steps, 'step', 'steps')}</span>` : ''}</div>
                ${r.detail ? `<p class="ag-agent-detail">${esc(r.detail)}</p>` : ''}
                ${cons}${ruta}
                ${r.action_log && r.action_log.length ? `<details class="ag-details"><summary>${ic('chevron-right', 'ag-caret')} Agent action log</summary>
                    <div class="ag-evidence-box">${r.action_log.map(esc).join('\n')}</div></details>` : ''}
            </div>`;
        }).join('');
        return `<div class="ag-card">
            <h2 class="ag-card-title">Test with real agents</h2>
            <p class="ag-card-sub">Task for site type <b>${esc(typ(at.typology))}</b>${at.allow_submit ? ' · form submission authorised on this domain' : ' · no submissions (reach and fill in only)'}. Each agent controls a real browser and tries to complete it; purchases are never paid and no accounts are created.</p>
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
                <td class="ag-muted">${p.total ? `${p.alcanzados}/${p.total} steps${atasco ? ` · got stuck at “${esc(atasco)}”` : ''}` : ''}</td></tr>`;
        }).join('')).join('');
        return `<div class="ag-card ag-section">
            <div class="ag-card-head"><h2 class="ag-card-title">What happened when the agents tried</h2>
                <button type="button" class="ag-link-btn" data-rep-tab="3">See each attempt ${ic('arrow-right')}</button></div>
            <p class="ag-card-sub">ChatGPT, Claude and Gemini drove a real browser and tried to complete a task${varias ? '' : ` on <b>${esc(conAgentes[0].a.host)}</b>`}. Nothing is ever paid and no accounts are created.</p>
            <div class="ag-table-wrap"><table class="ag-table ag-stack"><thead><tr>${varias ? '<th>Site</th>' : ''}<th>Agent</th><th>Result</th><th>Journey</th></tr></thead>
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
    // plantillas del muestreo: el código (discovery.py) se guarda en español
    const BUCKET_EN = { producto: 'product', categoria: 'category', servicio: 'service', blog: 'blog', otras: 'other', legal: 'legal', home: 'home' };
    const SIGNAL_NAMES = {
        schema_offer: 'schema Offer', schema_product: 'schema Product', schema_software: 'schema SoftwareApplication',
        add_to_cart: 'add-to-cart button', cart_url: 'cart URL', checkout_url: 'checkout URL',
        login_url: 'login URL', pricing_url: 'pricing page', signup_url: 'sign-up page',
        free_trial: 'free trial', no_card: '“no card required”', saas_words: 'SaaS vocabulary'
    };
    function typologyHTML(a) {
        const ev = a.typology_evidence || {};
        const tipos = Object.entries(ev).filter(([, v]) => v && typeof v === 'object');
        if (!tipos.length) return '<p class="ag-help">No signals recorded.</p>';
        const sig = arr => (arr || []).map(x => SIGNAL_NAMES[x] || String(x).replace(/_/g, ' ')).join(', ');
        return `<ul class="ag-typo">${tipos.map(([t, v]) => `
            <li class="${t === a.typology ? 'is-picked' : ''}"><b>${esc(typ(t))}</b> · ${esc(v.puntos ?? 0)} ${(v.puntos === 1) ? 'point' : 'points'}
                ${(v.fuertes || []).length ? `<span class="ag-typo-sig">Strong: ${esc(sig(v.fuertes))}</span>` : ''}
                ${(v.debiles || []).length ? `<span class="ag-typo-sig">Weak: ${esc(sig(v.debiles))}</span>` : ''}
                ${!(v.fuertes || []).length && !(v.debiles || []).length ? '<span class="ag-typo-sig">No signals</span>' : ''}</li>`).join('')}</ul>`;
    }

    function paneEvidencias(d) {
        const audits = [d.client, ...(d.competitors || []).filter(a => !a.error)];
        const a = audits[EV_SEL] || audits[0];
        const bots = Object.entries(a.bot_matrix || {}).map(([b, c]) => {
            const cls = c === 200 ? 'is-ok' : (c === 0 || c === 403 || c === 429) ? 'is-bad' : 'is-part';
            const k = cls.replace('is-', '');
            return `<tr><td>${esc(b === '_human' ? 'Human browser' : b)}</td><td class="ag-num"><span class="ag-mark is-${k}">${ic(MARKS[k][0])} ${c === 0 ? 'no response' : c === 200 ? '200 · gets in' : c}</span></td></tr>`;
        }).join('');
        const pages = (a.pages_sampled || []).map(p =>
            `<tr><td>${esc(BUCKET_EN[p.bucket] || p.bucket)}</td><td style="word-break:break-all">${esc(p.url)}</td><td class="ag-num">${esc(p.status)}</td><td>${esc(p.via)}</td></tr>`).join('');
        const wk = Object.keys(a.wellknown || {}).length
            ? `<ul class="ag-list">${Object.keys(a.wellknown).map(p => `<li><span class="ag-list-ic">${ic('plug')}</span><div class="ag-mono" style="align-self:center">${esc(p)}</div></li>`).join('')}</ul>`
            : '<p class="ag-help">No agentic surface exposed.</p>';
        const fallos = (a.checks || []).filter(c => c.score != null && c.score < 1);
        const lista = EV_ALL ? (a.checks || []) : fallos;
        const checks = lista.map(c =>
            `<tr><td style="min-width:200px"><b>${esc(nameOf(c))}</b><span class="ag-hist-comp">check ${c.id}${c.manual ? ' · needs human review' : ''}</span></td>
            <td class="ag-center">${mark(c.score)}</td><td class="ag-evidence">${esc(c.evidence)}</td></tr>`).join('')
            || '<tr><td colspan="3" class="ag-muted">No check fails on this domain.</td></tr>';
        const ag = d.agentes || {};
        const sinAgentes = !(a.agent_tests && a.agent_tests.agents) && ag.solicitados && (ag.estado === 'completado' || ag.estado === 'error')
            ? alertHTML({ tone: 'warn', icon: 'bot-off', title: 'No agentic evidence on this domain',
                body: 'The agent simulation couldn\'t be completed here, so check 6.3 for ' + esc(a.host) + ' is still unverified. It does not count as a failure.' })
            : '';
        return `<div class="ag-pane">${domainSwitcher(audits, EV_SEL, 'data-ev')}
            ${agentPanelHTML(a)}${sinAgentes}
            <div class="ag-grid-2">
                <div class="ag-card">
                    <h2 class="ag-card-title">Real AI bot access</h2>
                    <p class="ag-card-sub">Real requests with each bot's official user agent.</p>
                    <div class="ag-table-wrap"><table class="ag-table"><thead><tr><th>User agent</th><th class="ag-num">Response</th></tr></thead><tbody>${bots}</tbody></table></div>
                </div>
                <div class="ag-card">
                    <h2 class="ag-card-title">Agentic surface found</h2>
                    ${wk}
                    <h2 class="ag-card-title" style="margin-top:var(--cs-space-lg)">Detected site type</h2>
                    <p class="ag-help" style="margin-top:0">Classified as <b>${esc(typ(a.typology))}</b> based on these signals:</p>
                    ${typologyHTML(a)}
                    <p class="ag-help">JS render: ${a.render_ok ? 'run' : 'not run'} · LLM view (Jina): ${a.jina_ok ? 'yes' : 'no'}</p>
                </div>
            </div>
            <div class="ag-card ag-section">
                <h2 class="ag-card-title">Sampled pages</h2>
                <div class="ag-table-wrap"><table class="ag-table"><thead><tr><th>Template</th><th>URL</th><th class="ag-num">HTTP</th><th>Via</th></tr></thead><tbody>${pages}</tbody></table></div>
            </div>
            <div class="ag-card ag-section">
                <div class="ag-card-head"><h2 class="ag-card-title">Checks and their evidence</h2>
                    <div class="ag-switcher ag-filter" role="group" aria-label="Filter checks">
                        <button type="button" class="btn-secondary ag-btn-sm${EV_ALL ? '' : ' is-active'}" data-evf="fail" aria-pressed="${!EV_ALL}">Failures and partials (${fallos.length})</button>
                        <button type="button" class="btn-secondary ag-btn-sm${EV_ALL ? ' is-active' : ''}" data-evf="all" aria-pressed="${EV_ALL}">All (${(a.checks || []).length})</button>
                    </div></div>
                <div class="ag-table-wrap"><table class="ag-table"><thead><tr><th>Check</th><th class="ag-center">Result</th><th>Evidence</th></tr></thead><tbody>${checks}</tbody></table></div>
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
            if ((m.evidence || '').startsWith('N/A')) return lbl('na', 'not applicable');
            if (m.score == null && m.manual) return lbl('part', 'human judgement');
            if (m.score == null) return lbl('na', 'informational');
            if (m.manual) return lbl('part', 'heuristic');
            return lbl('ok', 'measured');
        };
        const matrixRows = d.client.checks.map(c =>
            `<tr><td><b>${esc(nameOf(c))}</b><span class="ag-hist-comp">check ${c.id}</span></td>
            <td class="ag-muted" style="font-size:var(--cs-text-xs);min-width:260px">${esc(METHODS[c.id] || '')}</td>
            ${audits.map(au => `<td style="white-space:nowrap;font-size:var(--cs-text-xs)">${statusFor(au, c.id)}</td>`).join('')}</tr>`).join('');

        let body;
        if (!a.trail) {
            body = alertHTML({ icon: 'history', title: 'No process log', body: 'This analysis was generated with an earlier version of the engine. Run the analysis again to get the reliability panel.' });
        } else {
            const n = { ok: 0, warn: 0, fail: 0, skipped: 0 };
            a.trail.forEach(t => { n[t.status] = (n[t.status] || 0) + 1; });
            const manual = (a.checks || []).filter(x => x.manual);
            const informational = (a.checks || []).filter(x => x.score == null && !x.manual);
            let v;
            if (n.fail > 0) v = { tone: 'bad', icon: 'circle-x', title: 'Incomplete analysis', msg: `${plural(n.fail, 'process', 'processes')} failed and some checks have no evidence. Don't hand it over without reviewing or rerunning it.` };
            else if (n.warn > 0 || n.skipped > 0) v = { tone: 'warn', icon: 'triangle-alert', title: 'Reliable with warnings', msg: `All processes ran, but ${n.warn} with degraded evidence and ${n.skipped} disabled. Review the warnings before handing it over.` };
            else v = { tone: 'good', icon: 'circle-check', title: 'Complete and reliable analysis', msg: 'Every process ran with direct evidence. What the report says is backed up.' };
            const IC = { ok: 'ok', warn: 'part', fail: 'bad', skipped: 'na' };
            const steps = a.trail.map(t => {
                return `<tr><td class="ag-center">${markOf(IC[t.status] || 'na')}</td>
                    <td style="font-weight:600;white-space:nowrap">${esc(t.step)}</td><td class="ag-muted">${esc(t.detail)}</td></tr>`;
            }).join('');
            const cov = a.coverage || {};
            const buckets = Object.entries(cov.buckets || {}).map(([b, total]) => {
                const sampled = (a.pages_sampled || []).filter(p => p.bucket === b).length;
                return `<tr><td>${esc(BUCKET_EN[b] || b)}</td><td class="ag-num">${total}</td><td class="ag-num">${sampled}</td></tr>`;
            }).join('');
            body = alertHTML({ tone: v.tone, icon: v.icon, title: v.title, body: `${v.msg} ${plural(manual.length, 'check', 'checks')} flagged for human judgement.` }) + `
                <div class="ag-card">
                    <h2 class="ag-card-title">Processes run <span class="ag-muted">${a.trail.length}</span></h2>
                    <div class="ag-table-wrap"><table class="ag-table"><thead><tr><th></th><th>Process</th><th>Result / evidence</th></tr></thead><tbody>${steps}</tbody></table></div>
                    <div class="ag-legend"><span>${markOf('ok')} run with evidence</span><span>${markOf('part')} degraded evidence</span><span>${markOf('bad')} the process failed</span><span>${markOf('na')} disabled</span><span>A 404 from the site is a finding, not an analysis failure.</span></div>
                </div>
                <div class="ag-grid-2">
                    <div class="ag-card">
                        <h2 class="ag-card-title">Sampling coverage</h2>
                        <p class="ag-help" style="margin-top:0"><b>${cov.sampled_ok ?? '?'}/${cov.sampled ?? '?'}</b> pages accessible out of ${cov.sitemap_urls ?? '?'} sitemap URLs (cap 800) · ${cov.fallbacks ?? 0} via fallback</p>
                        ${buckets ? `<div class="ag-table-wrap"><table class="ag-table"><thead><tr><th>Template</th><th class="ag-num">Found</th><th class="ag-num">Sampled</th></tr></thead><tbody>${buckets}</tbody></table></div>` : ''}
                        <p class="ag-help">Representative, not exhaustive, sampling: up to 2 pages per template.</p>
                    </div>
                    <div class="ag-card">
                        <h2 class="ag-card-title">Need human judgement <span class="ag-muted">${manual.length}</span></h2>
                        <ul class="ag-learn-checks">${manual.map(x => `<li><span>${x.id}</span>${esc(nameOf(x))}</li>`).join('') || '<li>None</li>'}</ul>
                        <h2 class="ag-card-title" style="margin-top:var(--cs-space-lg)">Informational, not scored <span class="ag-muted">${informational.length}</span></h2>
                        <ul class="ag-learn-checks">${informational.map(x => `<li><span>${x.id}</span>${esc(nameOf(x))}</li>`).join('') || '<li>None</li>'}</ul>
                    </div>
                </div>`;
        }
        return `<div class="ag-pane">
            <p class="ag-help ag-pane-intro">Check here that the analysis was complete before sharing the report: which processes ran, with what evidence and what couldn't be verified.</p>
            ${domainSwitcher(audits, FB_SEL, 'data-fb')}
            ${body}
            <details class="ag-card ag-section ag-fold">
                <summary><h2 class="ag-card-title">Factor matrix</h2><span class="ag-muted">What we check, how, and whether it could be measured on each domain</span>${ic('chevron-down', 'ag-fold-caret')}</summary>
                <div class="ag-table-wrap"><table class="ag-table"><thead><tr><th>Factor</th><th>Methodology</th>${audits.map((au, i) => `<th><span class="ag-entity"><span class="ag-dot" style="background:${SERIES[i % 3]}"></span>${esc(au.host)}</span></th>`).join('')}</tr></thead>
                <tbody>${matrixRows}</tbody></table></div>
                <div class="ag-legend"><span>Measured: direct evidence</span><span>Heuristic: partial evidence</span><span>Human judgement: the analyst decides</span><span>Informational: checked but not scored</span></div>
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
                <h2 class="ag-card-title">Weights applied <span class="ag-muted">${esc(typ(c.typology))}</span></h2>
                <div class="ag-table-wrap"><table class="ag-table"><tbody>${w}</tbody></table></div>
                <p class="ag-help">Each check scores 0, 0.5 or 1 and is weighted within its category. Critical checks weigh more. Categories that don't apply redistribute their weight.</p>
            </div>
            <div class="ag-card">
                <h2 class="ag-card-title">Scale</h2>
                <ul class="ag-list">${[
                    ['0–25', 'Invisible to agents', 'They neither read you nor use you.'],
                    ['26–50', 'Readable, not operable', 'They read you, don\'t understand you well, and don\'t use you.'],
                    ['51–75', 'Agent-aware', 'Well positioned; executable capabilities are missing.'],
                    ['76–100', 'Agent-ready', 'A real competitive advantage.']
                ].map((s, i) => `<li><span class="ag-list-ic" style="width:56px;font-size:var(--cs-text-xs);font-weight:700;${i === b ? `background:${C.text};color:#FFFFFF` : ''}">${s[0]}</span>
                    <div><div class="ag-list-title">${s[1]}${i === b ? ' <span class="ag-muted">· this report</span>' : ''}</div><div class="ag-list-body">${s[2]}</div></div></li>`).join('')}</ul>
            </div></div>
            <div class="ag-card ag-section">
                <h2 class="ag-card-title">Checks that need human review</h2>
                <ul class="ag-learn-checks">${manual || '<li>None</li>'}</ul>
                <p class="ag-help">Methodology v${esc(String(d.framework_version || '').split(' ')[0] || '2.0')} · based on open standards (RFC 9421, MCP, ACP, Schema.org) and Cloudflare's Agent Readiness score. The field changes quarter by quarter: re-audit every 90 days.</p>
            </div></div>`;
    }

    /* ───────────────────────────── informe ───────────────────────────── */

    let CURRENT_JOB = null, ACTIVE_TAB = 0;
    const TABS = [
        ['Summary', 'layout-dashboard', paneResumen],
        ['Comparison', 'swords', paneComparativa],
        ['Action plan', 'list-checks', paneHallazgos],
        ['Evidence', 'microscope', paneEvidencias],
        ['Reliability', 'shield-check', paneFiabilidad],
        ['Methodology', 'book-open', paneMetodologia]
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
        localizeLegacy(d);
        const c = d.client;
        const comps = (d.competitors || []).filter(a => !a.error).map(a => a.host);
        $('#agRepTitle').innerHTML = `Is <span class="ag-hl">${esc(c.host)}</span> ready for AI?`;
        $('#agRepSub').textContent = [fmtDate(d.generated), typ(c.typology),
            comps.length ? 'vs ' + comps.join(' and ') : 'no competitors'].filter(Boolean).join(' · ');
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
                bannerAgentes(`<b>Analysis completed in ${m}:${sg}.</b> Here is what we found; the report is saved in Reports.`, 'done', 'resumen');
                JUST_FINISHED = null;
            } else if (ag.detalle && (ag.estado === 'completado' || ag.estado === 'error')) {
                bannerAgentes(`<b>Agent simulation:</b> ${esc(ag.detalle)}`, ag.estado === 'error' ? 'error' : 'warn', 'resumen');
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
        label.textContent = 'Generating…';
        try {
            const r = await fetch('/agent/api/prompt/' + CURRENT_JOB);
            const j = await r.json();
            if (!r.ok || !j.prompt) throw new Error(j.error || 'error');
            await navigator.clipboard.writeText(j.prompt);
            label.textContent = 'Copied: paste it into ChatGPT or Claude';
            setTimeout(() => { label.textContent = orig; b.disabled = false; }, 4000);
        } catch (e) {
            label.textContent = 'Couldn\'t copy';
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
        label.textContent = kind === 'pdf' ? 'Generating PDF…' : 'Preparing JSON…';
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
            alert('Download failed: ' + e.message);
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
            idle: ['bot', 'Simulate agents', false],
            launching: ['loader-circle', 'Starting…', true],
            running: ['loader-circle', 'Simulating agents…', true],
            done: ['circle-check', 'Agents simulated', true],
            error: ['rotate-ccw', 'Retry simulation', false]
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
                bannerAgentes(`<b>The simulation couldn't be started.</b> ${esc(e.error || '')}`, 'error');
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
                bannerAgentes(`<b>${esc(s.phase || 'Simulating agents…')}</b> · ${m}m ${seg}s. You can keep using the report in the meantime.
                    <span class="ag-banner-last">${esc((s.log || []).slice(-1)[0] || '')}</span>`, 'running');
                return;
            }
            clearInterval(AGENTS_POLL);
            AGENTS_POLL = null;
            if (s.status === 'error') {
                bannerAgentes(`<b>The agent simulation failed:</b> ${esc(s.error || 'unknown error')}`, 'error');
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
                bannerAgentes(`<b>Agent simulation complete.</b> The score already includes it and the summary is on this page; each attempt step by step is under <b>Evidence</b>.${det ? ' ' + esc(det) : ''}`, det ? 'warn' : 'done', 'global');
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
