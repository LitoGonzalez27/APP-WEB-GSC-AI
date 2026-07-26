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
 * MutationObserver con debounce repite la pasada sobre los nodos que el JS del
 * panel inyecta (tablas, modales, listas).
 *
 * Font Awesome sigue cargado como red de seguridad: los iconos SIN mapeo (p.ej.
 * las marcas fab fa-google, que Lucide no tiene) se quedan como están.
 *
 * OPT-OUT: un icono cuyo estado muta otro script vía `className` NO puede
 * convertirse (en SVG `className` es de solo lectura y `querySelector('i')`
 * dejaría de encontrarlo). Márcalo con `data-no-lucide` en el propio <i> y se
 * quedará en Font Awesome.
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

    /**
     * Iconos con estado del navbar, que es markup COMPARTIDO por toda la app y
     * no lleva `data-no-lucide`: navbar.js:220 alterna fa-sun/fa-moon vía
     * className. El resto de casos deben usar el atributo, no esta lista.
     */
    const STATEFUL_IDS = new Set(['themeIcon', 'mobileThemeIcon', 'dropdownThemeIcon']);

    const FA_SELECTOR = 'i[class*="fa-"]:not([data-lucide])';
    /**
     * Subárboles que el observer ignora por completo. Es el mismo atributo del
     * opt-out, puesto en un contenedor en vez de en un icono: todo lo de dentro
     * queda fuera del conversor.
     *
     * Lo usan los tooltips flotantes, que reescriben su innerHTML en cada frame
     * del hover y nunca contienen iconos de Font Awesome; sin esto, mover el
     * ratón sobre una gráfica lanzaba un escaneo cada 120 ms para no convertir
     * nada.
     */
    const IGNORED_SELECTOR = '[data-no-lucide]';

    /** Convierte un <i> de Font Awesome en un placeholder Lucide. true si tocó algo. */
    function convertNode(el) {
        // closest y no hasAttribute: el opt-out vale tanto en el propio icono
        // como en cualquier contenedor que lo envuelva.
        if (el.closest(IGNORED_SELECTOR)) return false;
        if (el.id && STATEFUL_IDS.has(el.id)) return false;
        const classes = Array.from(el.classList);
        // Solo la familia solid/regular; las marcas (fab) no tienen outline en Lucide
        if (classes.includes('fab')) return false;
        const faName = classes.find(c => c.startsWith('fa-') && c !== 'fa-spin' && c !== 'fa-fw');
        if (!faName) return false;
        const lucideName = MAP[faName.slice(3)];
        if (!lucideName) return false;   // sin mapeo: se queda en Font Awesome
        const spin = classes.includes('fa-spin') || faName === 'fa-spinner' || faName === 'fa-circle-notch';
        // Conservar las clases ajenas a FA (p.ej. chip-add-icon) para que su CSS siga aplicando
        const keep = classes.filter(c => !/^fa[srb]?$/.test(c) && !c.startsWith('fa-'));

        // ENVOLVER, NO REEMPLAZAR: el <i> se queda y el SVG va dentro.
        //
        // Sustituir el <i> por el <svg> rompía en silencio TODA regla CSS del
        // tipo `.x i { color: ... }`, porque el selector deja de casar. Las
        // hojas de LLM Monitoring se parchearon con selectores gemelos
        // `.x svg.lucide`, pero quedaban 97 reglas más en las hojas compartidas
        // (manual-ai, navbar, paywall...) y por eso los iconos de las tarjetas
        // de AI Overview salían oscuros sobre fondo oscuro.
        //
        // Manteniendo el <i>, esas reglas siguen aplicando y el SVG hereda el
        // color por `currentColor` y el tamaño por `width:1em` (ver la regla
        // `svg.lucide` de brand-dashboard-overrides.css). Los gemelos ya
        // escritos siguen valiendo porque son selectores de descendiente.
        // `lucide-icon` marca al envoltorio: le devuelve el comportamiento de
        // caja que antes tenía el propio <svg> como flex item (ver overrides).
        keep.push('lucide-icon');
        el.className = keep.join(' ');
        el.textContent = '';
        const placeholder = document.createElement('span');
        placeholder.setAttribute('data-lucide', lucideName);
        // La animación vive en `svg.lucide-spin`, así que la clase debe viajar
        // al SVG: lucide copia los atributos del placeholder al svg que crea.
        if (spin) placeholder.setAttribute('class', 'lucide-spin');
        el.appendChild(placeholder);
        return true;
    }

    /**
     * Convierte dentro de `root` (incluido el propio nodo) y pinta los SVG.
     * Acotar el escaneo importa: `createIcons()` sin `root` recorre el documento
     * entero dos veces, y el observer se dispara con cada re-render de tabla.
     */
    function convert(root) {
        if (!root || root.nodeType !== Node.ELEMENT_NODE) return 0;
        let converted = 0;
        if (root.matches(FA_SELECTOR) && convertNode(root)) converted++;
        root.querySelectorAll(FA_SELECTOR).forEach(el => { if (convertNode(el)) converted++; });
        if (converted === 0) return 0;
        // Los placeholders son descendientes de root, así que root vale de scope
        // incluso cuando el propio root era el <i>.
        lucide.createIcons({ root: root });
        return converted;
    }

    /** Nodos añadidos pendientes de procesar, acumulados entre frames. */
    let pendingRoots = new Set();
    let pendingTimer = null;

    function flush() {
        pendingTimer = null;
        const roots = pendingRoots;
        pendingRoots = new Set();
        roots.forEach(root => {
            // El nodo puede haberse desmontado entre la mutación y el flush
            if (root.isConnected) convert(root);
        });
    }

    function init() {
        convert(document.body);
        // El JS de los paneles inyecta HTML constantemente (tablas Grid.js,
        // modales, listas): el observer reconvierte SOLO el subárbol añadido.
        const observer = new MutationObserver(muts => {
            for (const m of muts) {
                if (!m.addedNodes.length) continue;
                if (m.target.nodeType === Node.ELEMENT_NODE && m.target.closest(IGNORED_SELECTOR)) continue;
                for (const node of m.addedNodes) {
                    if (node.nodeType === Node.ELEMENT_NODE) pendingRoots.add(node);
                }
            }
            if (pendingRoots.size && !pendingTimer) pendingTimer = setTimeout(flush, 120);
        });
        observer.observe(document.body, { childList: true, subtree: true });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
