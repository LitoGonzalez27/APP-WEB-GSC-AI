/**
 * CLICANDSEO — Tarjeta de proyecto común (AI Overview, AI Mode, LLM Visibility)
 *
 * Las tres listas de proyectos pintaban tarjetas distintas (una por fila con
 * seis cifras, otra con metadatos y cuatro botones). Ahora comparten este
 * componente, inspirado en las tarjetas de AI Visibility Summary: logo,
 * nombre y dominio, UNA cifra principal con su variación, tres datos
 * pequeños, estado en texto y una acción principal; el resto de acciones va
 * en un menú «⋯».
 *
 * Uso (cada panel traduce sus proyectos a «items»):
 *
 *   ClicandseoProjectCards.render(container, items, handlers, {
 *       module: 'manual_ai' | 'ai_mode' | 'llm',   // para /api/project-cards/kpis
 *       metricLabel: 'Visibility · 30d',
 *   });
 *
 * item = {
 *   id, name, domain, subtitle,           // subtitle: p. ej. país o marca
 *   href,                                 // URL propia del dashboard (?project=id)
 *   status: 'active' | 'paused' | 'quota', statusNote,
 *   shared: bool,                         // solo lectura
 *   stats: [{ label, value }],            // 3 datos pequeños
 *   cta: { action, label, disabled, title, id } | null,  // p. ej. primer análisis
 *   menu: [{ action, label, danger }],
 * }
 * handlers = { open(id), <action>(id) ... }  — se llaman por delegación.
 *
 * La cifra principal llega después (fetchKpis) para no frenar la lista; los
 * números son los mismos que usa AI Visibility Summary.
 */
(function () {
    'use strict';

    const esc = (v) => (window.ClicandseoHtml ? window.ClicandseoHtml.escapeHtml(v) : String(v ?? ''));

    function cleanDomain(domain) {
        return String(domain || '').toLowerCase()
            .replace(/^https?:\/\//, '').replace(/^www\./, '').split(/[/?#]/)[0].trim();
    }
    // Mismo servicio que AI Visibility Summary (logo.dev) y favicon de Google
    // como respaldo; si ninguno carga, queda la inicial.
    function logoUrl(domain) {
        const clean = cleanDomain(domain);
        return clean ? `https://img.logo.dev/${encodeURIComponent(clean)}?token=pk_a4PP_KI7Qj-y6MnQSvu-3A&size=64&format=png` : '';
    }
    function logoFallbackUrl(domain) {
        const clean = cleanDomain(domain);
        return clean ? `https://www.google.com/s2/favicons?domain=${encodeURIComponent(clean)}&sz=64` : '';
    }

    const STATUS = {
        active: { label: 'Active', cls: 'is-active' },
        paused: { label: 'Paused', cls: 'is-paused' },
        quota: { label: 'Paused · quota', cls: 'is-quota' },
    };

    function cardHtml(item, opts) {
        const st = STATUS[item.status] || STATUS.active;
        const initial = esc((item.name || '?').trim().charAt(0).toUpperCase());
        const logo = logoUrl(item.domain);
        const menu = (item.menu || []).filter(Boolean);
        const menuId = `pcMenu-${opts.module}-${item.id}`;
        return `
        <article class="pc-card${item.status !== 'active' ? ' is-dimmed' : ''}" data-pc-id="${esc(item.id)}">
            <header class="pc-head">
                <span class="pc-logo" aria-hidden="true">
                    ${logo ? `<img src="${esc(logo)}" alt="" loading="lazy" data-fallback="${esc(logoFallbackUrl(item.domain))}"
                         onerror="if(this.dataset.fallback){this.src=this.dataset.fallback;this.dataset.fallback='';}else{this.remove();}">` : ''}
                    <span class="pc-logo-fallback">${initial}</span>
                </span>
                <div class="pc-id">
                    <h3 class="pc-name">
                        <a href="${esc(item.href || '#')}" class="pc-open-link" data-pc-action="open">${esc(item.name)}</a>
                    </h3>
                    <p class="pc-sub">${[item.domain, item.subtitle].filter(Boolean).map(esc).join('<span class="pc-sep">·</span>')}</p>
                </div>
                ${menu.length ? `
                <div class="pc-menu">
                    <button type="button" class="pc-menu-btn" aria-haspopup="menu" aria-expanded="false"
                            aria-controls="${menuId}" aria-label="More actions for ${esc(item.name)}">
                        <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true"><circle cx="5" cy="12" r="1.8"/><circle cx="12" cy="12" r="1.8"/><circle cx="19" cy="12" r="1.8"/></svg>
                    </button>
                    <div class="pc-menu-list" id="${menuId}" role="menu" hidden>
                        ${menu.map(m => `<button type="button" role="menuitem" class="pc-menu-item${m.danger ? ' is-danger' : ''}" data-pc-action="${esc(m.action)}">${esc(m.label)}</button>`).join('')}
                    </div>
                </div>` : ''}
            </header>

            <div class="pc-metric" data-pc-metric>
                <span class="pc-value">–</span>
                <span class="pc-delta"></span>
                <span class="pc-metric-label">${esc(opts.metricLabel || '')}</span>
            </div>

            <dl class="pc-stats">
                ${(item.stats || []).map(s => `<div><dt>${esc(s.label)}</dt><dd>${esc(s.value)}</dd></div>`).join('')}
            </dl>

            ${item.cta ? `
            <button type="button" class="pc-cta" data-pc-action="${esc(item.cta.action)}"${item.cta.id ? ` id="${esc(item.cta.id)}"` : ''}${item.cta.disabled ? ' disabled' : ''}${item.cta.title ? ` title="${esc(item.cta.title)}"` : ''}>${esc(item.cta.label)}</button>` : ''}

            <footer class="pc-foot">
                <span class="pc-status ${st.cls}"><span class="pc-dot" aria-hidden="true"></span>${esc(st.label)}${item.statusNote ? ` <span class="pc-status-note">${esc(item.statusNote)}</span>` : ''}</span>
                ${item.shared ? '<span class="pc-shared">Shared · view only</span>' : ''}
                <a href="${esc(item.href || '#')}" class="pc-open" data-pc-action="open">Open dashboard <span aria-hidden="true">→</span></a>
            </footer>
        </article>`;
    }

    function closeMenus(except) {
        document.querySelectorAll('.pc-menu-list:not([hidden])').forEach(list => {
            if (list === except) return;
            list.hidden = true;
            const btn = list.parentElement.querySelector('.pc-menu-btn');
            if (btn) btn.setAttribute('aria-expanded', 'false');
        });
    }

    let globalListeners = false;
    function bindGlobal() {
        if (globalListeners) return;
        globalListeners = true;
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.pc-menu')) closeMenus();
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeMenus();
        });
    }

    function bind(container) {
        if (container.__pcBound) return;
        container.__pcBound = true;
        container.addEventListener('click', (e) => {
            const toggle = e.target.closest('.pc-menu-btn');
            if (toggle) {
                e.preventDefault();
                const list = toggle.parentElement.querySelector('.pc-menu-list');
                const open = list.hidden;
                closeMenus(list);
                list.hidden = !open;
                toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
                if (open) list.querySelector('.pc-menu-item')?.focus();
                return;
            }
            const actionEl = e.target.closest('[data-pc-action]');
            const card = e.target.closest('.pc-card');
            if (!card) return;
            const id = card.dataset.pcId;
            const handlers = container.__pcHandlers || {};
            if (actionEl) {
                // cmd/ctrl/shift-clic o clic central en un enlace: que el
                // navegador lo abra en otra pestaña con su URL propia
                if (actionEl.tagName === 'A' && (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1)) return;
                e.preventDefault();
                closeMenus();
                const fn = handlers[actionEl.dataset.pcAction];
                if (typeof fn === 'function' && !actionEl.disabled) fn(id);
                return;
            }
            // clic en la tarjeta (fuera de botones/enlaces) = abrir
            if (!e.target.closest('a, button, input, select, textarea') && typeof handlers.open === 'function') {
                handlers.open(id);
            }
        });
        // flechas dentro del menú
        container.addEventListener('keydown', (e) => {
            const item = e.target.closest('.pc-menu-item');
            if (!item || !['ArrowDown', 'ArrowUp'].includes(e.key)) return;
            e.preventDefault();
            const items = [...item.parentElement.querySelectorAll('.pc-menu-item')];
            const i = items.indexOf(item) + (e.key === 'ArrowDown' ? 1 : -1);
            items[(i + items.length) % items.length].focus();
        });
    }

    function patchKpis(container, kpis, opts) {
        container.querySelectorAll('.pc-card').forEach(card => {
            const slot = card.querySelector('[data-pc-metric]');
            const k = kpis[card.dataset.pcId];
            if (!slot) return;
            const valueEl = slot.querySelector('.pc-value');
            const deltaEl = slot.querySelector('.pc-delta');
            if (!k || !k.available || k.value == null) {
                valueEl.textContent = '–';
                valueEl.classList.add('is-empty');
                deltaEl.textContent = k && k.reason === 'no_data' ? 'No data yet' : '';
                deltaEl.className = 'pc-delta is-flat';
                return;
            }
            valueEl.classList.remove('is-empty');
            valueEl.textContent = `${Number(k.value).toFixed(1)}%`;
            const d = k.delta;
            if (d == null || Math.abs(d) < 0.05) {
                deltaEl.textContent = '= 0.0';
                deltaEl.className = 'pc-delta is-flat';
                deltaEl.title = `No change vs previous ${opts.periodDays || 30} days`;
            } else {
                const up = d > 0;
                deltaEl.textContent = `${up ? '↑ +' : '↓ '}${d.toFixed(1)}`;
                deltaEl.className = `pc-delta ${up ? 'is-up' : 'is-down'}`;
                deltaEl.title = `${up ? '+' : ''}${d.toFixed(1)} pts vs previous ${opts.periodDays || 30} days`;
            }
        });
    }

    async function fetchKpis(container, ids, opts) {
        if (!opts.module || !ids.length) return;
        try {
            const r = await fetch(`/api/project-cards/kpis?module=${encodeURIComponent(opts.module)}&ids=${ids.join(',')}`,
                { credentials: 'same-origin' });
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            const data = await r.json();
            patchKpis(container, data.kpis || {}, { ...opts, periodDays: data.period_days });
        } catch (err) {
            console.warn('[ProjectCards] KPIs unavailable:', err.message);
            patchKpis(container, {}, opts);
        }
    }

    function render(container, items, handlers, opts) {
        if (!container) return;
        bindGlobal();
        container.classList.add('pc-grid');
        // los paneles lo muestran con display:block en línea (showElement),
        // que anulaba la rejilla: por eso AI Overview salía de uno en uno
        container.style.display = 'grid';
        container.__pcHandlers = handlers || {};
        container.innerHTML = items.map(item => cardHtml(item, opts || {})).join('');
        bind(container);
        fetchKpis(container, items.map(i => i.id), opts || {});
    }

    function formatDate(value) {
        if (!value) return 'Never';
        const d = new Date(value);
        if (Number.isNaN(d.getTime())) return 'Never';
        return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
    }

    window.ClicandseoProjectCards = { render, patchKpis, formatDate, logoUrl };
})();
