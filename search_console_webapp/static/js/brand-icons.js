/**
 * CLICANDSEO — Iconografía Lucide para los paneles de datos
 *
 * El brandbook exige iconos Lucide outline con trazo de 2px (Brandbook.md:234)
 * y prohíbe los rellenos; el código usaba Font Awesome solid en ~125 sitios
 * entre plantillas y HTML generado por JS.
 *
 * En lugar de editar los 125 usos (inabarcable de verificar sin regresiones),
 * este script convierte EN RUNTIME cada <i class="fas fa-x"> a su equivalente
 * Lucide y deja que lucide.createIcons() lo sustituya por el SVG. Un
 * MutationObserver con debounce repite la pasada cuando el JS del panel inyecta
 * HTML nuevo (tablas, modales, listas).
 *
 * Font Awesome sigue cargado como red de seguridad: los iconos SIN mapeo (p.ej.
 * las marcas fab fa-google, que Lucide no tiene) se quedan como están.
 *
 * Compartido por LLM Monitoring, Manual AI, AI Mode y AI Visibility Summary.
 * Debe cargarse DESPUÉS del UMD de lucide.
 */
(function () {
    'use strict';

    if (typeof lucide === 'undefined') {
        console.warn('[BrandIcons] lucide no está cargado; los iconos siguen en Font Awesome.');
        return;
    }

    /** fa-name -> nombre lucide. Solo outline; lo no mapeado permanece en FA. */
    const MAP = {
        'arrow-left': 'arrow-left', 'arrow-right': 'arrow-right', 'arrow-up': 'arrow-up',
        'arrow-down': 'arrow-down', 'align-left': 'align-left', 'award': 'award',
        'ban': 'ban', 'bolt': 'zap', 'brain': 'brain', 'briefcase': 'briefcase',
        'building': 'building-2', 'calculator': 'calculator', 'calendar': 'calendar',
        'chart-bar': 'chart-column', 'chart-line': 'chart-line', 'chart-pie': 'chart-pie',
        'check': 'check', 'check-circle': 'circle-check', 'check-double': 'check-check',
        'chevron-down': 'chevron-down', 'chevron-left': 'chevron-left',
        'chevron-right': 'chevron-right', 'chevron-up': 'chevron-up',
        'clock': 'clock', 'cog': 'settings', 'cogs': 'settings-2', 'columns': 'columns-2',
        'comment-dots': 'message-circle-more', 'comments': 'messages-square',
        'crown': 'crown', 'database': 'database', 'download': 'download',
        'edit': 'square-pen', 'equals': 'equal', 'eraser': 'eraser',
        'exclamation-triangle': 'triangle-alert', 'expand-alt': 'maximize-2',
        'external-link-alt': 'external-link', 'eye': 'eye', 'file-alt': 'file-text',
        'file-excel': 'sheet', 'file-pdf': 'file-text', 'filter': 'filter',
        'folder': 'folder', 'folder-open': 'folder-open', 'globe': 'globe',
        'graduation-cap': 'graduation-cap', 'heart': 'heart', 'home': 'house',
        'hourglass-half': 'hourglass', 'inbox': 'inbox', 'industry': 'factory',
        'info-circle': 'info', 'key': 'key-round', 'layer-group': 'layers',
        'lightbulb': 'lightbulb', 'link': 'link', 'list': 'list', 'list-ul': 'list',
        'magic': 'wand-sparkles', 'medal': 'medal', 'microchip': 'cpu',
        'minus': 'minus', 'paper-plane': 'send', 'pause': 'pause', 'pen': 'pen',
        'play': 'play', 'plus': 'plus', 'plus-circle': 'circle-plus',
        'quote-left': 'quote', 'redo': 'redo-2', 'robot': 'bot', 'rocket': 'rocket',
        'save': 'save', 'search': 'search', 'search-plus': 'zoom-in',
        'shield-alt': 'shield', 'sign-out-alt': 'log-out', 'sitemap': 'network',
        'smile': 'smile', 'star': 'star', 'sync-alt': 'refresh-cw',
        'tachometer-alt': 'gauge', 'tag': 'tag', 'tags': 'tags', 'times': 'x',
        'times-circle': 'circle-x', 'trash': 'trash-2', 'trash-alt': 'trash-2',
        'trophy': 'trophy', 'user-circle': 'circle-user', 'user-minus': 'user-minus',
        'user-shield': 'shield-user', 'users': 'users',
        // Iconos que solo usan Manual AI / AI Mode / AI Summary
        'balance-scale': 'scale', 'calendar-alt': 'calendar-days',
        'circle-info': 'info', 'clock-rotate-left': 'history',
        'comment-alt': 'message-square', 'flag': 'flag', 'history': 'history',
        'lock': 'lock', 'moon': 'moon', 'newspaper': 'newspaper',
        'percentage': 'percent', 'project-diagram': 'git-fork',
        'share-alt': 'share-2', 'sign-in-alt': 'log-in',
        'sliders-h': 'sliders-horizontal', 'sort-numeric-down': 'arrow-down-0-1',
        'sticky-note': 'sticky-note', 'table': 'table', 'unlink': 'unlink',
        'user-plus': 'user-plus', 'video': 'video', 'x': 'x',
        // Spinners: el giro lo pone la clase .lucide-spin (animación CSS propia)
        'spinner': 'loader-circle', 'circle-notch': 'loader-circle'
    };

    function convert(root) {
        const nodes = (root || document).querySelectorAll('i[class*="fa-"]:not([data-lucide])');
        let converted = 0;
        nodes.forEach(el => {
            const classes = Array.from(el.classList);
            // Solo la familia solid/regular; las marcas (fab) no tienen outline en Lucide
            if (classes.includes('fab')) return;
            const faName = classes.find(c => c.startsWith('fa-') && c !== 'fa-spin' && c !== 'fa-fw');
            if (!faName) return;
            const lucideName = MAP[faName.slice(3)];
            if (!lucideName) return;   // sin mapeo: se queda en Font Awesome
            const spin = classes.includes('fa-spin') || faName === 'fa-spinner' || faName === 'fa-circle-notch';
            // Conservar las clases ajenas a FA (p.ej. chip-add-icon) para que su CSS siga aplicando
            const keep = classes.filter(c => !/^fa[srb]?$/.test(c) && !c.startsWith('fa-'));
            if (spin) keep.push('lucide-spin');
            el.setAttribute('data-lucide', lucideName);
            el.className = keep.join(' ');
            converted++;
        });
        if (converted > 0 || (root || document).querySelector('i[data-lucide]')) {
            lucide.createIcons();
        }
        return converted;
    }

    let pending = null;
    function scheduleConvert() {
        if (pending) return;
        pending = setTimeout(() => { pending = null; convert(); }, 120);
    }

    function init() {
        convert();
        // El JS de los paneles inyecta HTML constantemente (tablas Grid.js,
        // modales, listas): el observer repite la conversión con debounce.
        const observer = new MutationObserver(muts => {
            for (const m of muts) {
                if (m.addedNodes && m.addedNodes.length) { scheduleConvert(); return; }
            }
        });
        observer.observe(document.body, { childList: true, subtree: true });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
