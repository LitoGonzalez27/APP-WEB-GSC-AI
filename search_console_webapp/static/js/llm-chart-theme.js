/**
 * CLICANDSEO — Tema único de Chart.js para los paneles de datos
 *
 * Antes de esto no había ningún Chart.defaults en el proyecto: cada gráfica
 * repetía su propia tipografía, colores de eje, grid y tooltip (~500 líneas de
 * config duplicada y divergente — por ejemplo dos tooltips con fondos distintos
 * para el mismo rol). Aquí se fija una sola vez y las gráficas solo declaran
 * sus datos y sus formatters.
 *
 * Compartido por LLM Monitoring, Manual AI, AI Mode y AI Visibility Summary.
 * Debe cargarse DESPUÉS de chart.js y ANTES de cualquier new Chart().
 *
 * Los colores se leen de los tokens --cs-* de brand-dashboard-tokens.css para
 * que exista una sola fuente de verdad; los literales son solo el fallback si
 * el CSS no hubiera cargado.
 */
(function () {
    'use strict';

    if (typeof Chart === 'undefined') {
        console.warn('[CSChartTheme] Chart.js no está cargado; el tema no se aplica.');
        return;
    }

    const css = getComputedStyle(document.documentElement);
    const token = (name, fallback) => (css.getPropertyValue(name) || '').trim() || fallback;

    const ink = {
        primary: token('--cs-text-primary', '#0F172A'),
        secondary: token('--cs-text-secondary', '#64748B'),
        tertiary: token('--cs-text-tertiary', '#94A3B8'),
        inverse: token('--cs-text-inverse', '#F8FAFC')
    };

    const surface = {
        paper: token('--cs-bg-paper', '#FFFFFF'),
        subtle: token('--cs-bg-subtle', '#F1F5F9')
    };

    const chrome = {
        grid: token('--cs-chart-grid', '#EEF2F7'),
        axis: token('--cs-chart-axis', '#94A3B8'),
        tooltipBg: token('--cs-chart-tooltip-bg', '#0F172A')
    };

    /**
     * Paleta categórica de series. El ORDEN es el mecanismo de accesibilidad:
     * estos 4 tonos pasan los checks de separación bajo protanopia y
     * deuteranopia (peor par ΔE 9.2) y de visión normal (16.3). No reordenar ni
     * añadir un 5º sin re-validar — la paleta anterior fallaba: Gemini y Claude
     * eran literalmente el mismo color para quien tiene daltonismo (ΔE 0.9).
     */
    const series = [
        token('--cs-series-1', '#2a78d6'),
        token('--cs-series-2', '#1baf7a'),
        token('--cs-series-3', '#eb6834'),
        token('--cs-series-4', '#4a3aa7')
    ];

    const seriesMuted = token('--cs-series-muted', '#CBD5E1');

    const status = {
        success: token('--cs-success', '#3CB371'),
        successText: token('--cs-success-text', '#287A4C'),
        error: token('--cs-error', '#E05252'),
        errorText: token('--cs-error-text', '#D13B3B'),
        neutral: ink.tertiary
    };

    /**
     * Sentimiento: color + etiqueta legible. Es un rol de ESTADO, no una serie
     * categórica, así que reutiliza los colores de status (validados para
     * contraste) en lugar de un verde/rojo propio.
     */
    const sentiment = {
        positive: { color: status.success, label: 'Positive' },
        neutral: { color: status.neutral, label: 'Neutral' },
        negative: { color: status.error, label: 'Negative' }
    };

    /** Meta de sentimiento con recurso para etiquetas desconocidas. */
    function sentimentMeta(label) {
        return sentiment[label] || { color: status.neutral, label: label };
    }

    /**
     * Color por ENTIDAD, no por posición: si un filtro deja fuera a un LLM, los
     * que sobreviven conservan su color. Reasignar por índice haría que quien
     * aprendió "Gemini es azul" leyera mal el gráfico siguiente.
     *
     * El reparto de slots sigue la identidad de cada LLM (ChatGPT verde, Gemini
     * azul, Claude coral) para que el color ayude a reconocerlos. Verificado que
     * el orden en que se pintan — ChatGPT, Claude, Gemini, Perplexity — pasa los
     * checks de daltonismo y all-pairs; cambiarlo obliga a re-validar.
     */
    const ENTITY_SLOT = {
        openai: 1,      // ChatGPT  → aqua
        anthropic: 2,   // Claude   → naranja
        google: 0,      // Gemini   → azul
        perplexity: 3   // Perplexity → violeta
    };

    function seriesColorFor(entityKey, fallbackIndex) {
        const slot = ENTITY_SLOT[entityKey];
        if (slot !== undefined) return series[slot];
        if (typeof fallbackIndex === 'number') return series[fallbackIndex % series.length];
        return seriesMuted;
    }

    const fontSans = token('--cs-font-sans', "'Inter Tight', sans-serif")
        .replace(/^['"]|['"]$/g, '');

    // ── Publicar el tema ANTES de tocar los defaults ─────────────────────────
    // Los colores son lo que las gráficas necesitan para pintar; los defaults
    // son cosmética. Si una clave de Chart.defaults cambia de forma entre
    // versiones, la excepción no debe dejar a CSChartTheme sin definir y tumbar
    // las 7 gráficas — que es exactamente lo que pasó al asumir que
    // Chart.defaults.scales.category tenía un objeto grid (no lo tiene).
    window.CSChartTheme = {
        series,
        seriesMuted,
        status,
        ink,
        surface,
        sentiment,
        sentimentMeta,
        seriesColorFor,
        /**
         * Normaliza los datasets de una gráfica de líneas "marca vs competidores".
         * El dataset 0 es SIEMPRE la marca propia.
         *
         * Existe porque dos competidores con el mismo valor exacto dejaban una
         * línea invisible bajo la otra. Hacen falta las tres cosas a la vez:
         *
         * - `borderDash`: los competidores van punteados, con patrón distinto
         *   entre sí, y sus huecos dejan ver lo que tienen debajo.
         * - `order`: Chart.js pinta el dataset 0 EN ÚLTIMO lugar, es decir
         *   ENCIMA de todos. Sin bajar el `order` de los competidores, la línea
         *   sólida de la marca los tapaba igualmente.
         * - `borderWidth`: normalizado aquí y no en el backend, que servía
         *   competidores a 1.5px. Un punteado más estrecho que la línea sólida
         *   de debajo apenas asoma cuando coinciden en valor.
         */
        lineSeries(datasets) {
            const DASHES = [[6, 4], [2, 3], [10, 4, 2, 4]];
            return (datasets || []).map((ds, idx) => {
                const isBrand = idx === 0;
                return Object.assign({}, ds, {
                    borderDash: isBrand ? [] : DASHES[(idx - 1) % DASHES.length],
                    order: isBrand ? 2 : 1,
                    borderWidth: isBrand ? 3 : 2.5,
                    pointBackgroundColor: ds.borderColor,
                    pointBorderColor: '#FFFFFF',
                    pointHoverBackgroundColor: ds.borderColor,
                    pointHoverBorderColor: '#FFFFFF',
                    pointStyle: 'circle',
                    pointBorderWidth: 2
                });
            });
        },

        /**
         * Eje y en porcentaje 0-100.
         *
         * `ticks` se fusiona en vez de reemplazarse: con Object.assign plano,
         * un `ticks: { stepSize: 25 }` del llamante borraba el formateador de
         * `%` sin avisar y obligaba a repetirlo en cada sitio.
         *
         * Para un eje que no deba tener tope fijo, pasar `max: null` junto a
         * `suggestedMax`.
         */
        percentAxis(overrides) {
            const { ticks, ...rest } = overrides || {};
            const axis = {
                beginAtZero: true,
                max: 100,
                ticks: Object.assign({ callback: (v) => `${v}%` }, ticks)
            };
            Object.assign(axis, rest);
            if (axis.max === null) delete axis.max;
            return axis;
        }
    };

    // ── Defaults globales ────────────────────────────────────────────────────
    // En try/catch a propósito: los defaults son cosmética y su forma cambia
    // entre versiones de Chart.js. Si uno falla, preferimos gráficas con el
    // estilo por defecto de la librería antes que ninguna gráfica.
    try {
    Chart.defaults.font.family = fontSans;
    Chart.defaults.font.size = 12;
    Chart.defaults.font.weight = 500;
    Chart.defaults.color = ink.secondary;
    Chart.defaults.borderColor = chrome.grid;
    Chart.defaults.maintainAspectRatio = false;
    Chart.defaults.animation.duration = 200;

    // Leyenda: siempre presente cuando hay 2+ series, con punto en vez de caja
    // para que no compita con las marcas del propio gráfico.
    Chart.defaults.plugins.legend.labels.usePointStyle = true;
    Chart.defaults.plugins.legend.labels.pointStyle = 'circle';
    Chart.defaults.plugins.legend.labels.boxWidth = 8;
    Chart.defaults.plugins.legend.labels.boxHeight = 8;
    Chart.defaults.plugins.legend.labels.padding = 18;
    Chart.defaults.plugins.legend.labels.color = ink.secondary;

    // Un solo tooltip para todo el producto.
    Chart.defaults.plugins.tooltip.backgroundColor = chrome.tooltipBg;
    Chart.defaults.plugins.tooltip.titleColor = ink.inverse;
    Chart.defaults.plugins.tooltip.bodyColor = ink.inverse;
    Chart.defaults.plugins.tooltip.borderWidth = 0;
    Chart.defaults.plugins.tooltip.padding = 12;
    Chart.defaults.plugins.tooltip.cornerRadius = 8;
    Chart.defaults.plugins.tooltip.boxPadding = 6;
    Chart.defaults.plugins.tooltip.titleFont = { size: 13, weight: '600' };
    Chart.defaults.plugins.tooltip.bodyFont = { size: 12, weight: '400' };
    Chart.defaults.plugins.tooltip.usePointStyle = true;

    // Marcas finas. Las barras se redondean solo en el extremo del dato y
    // quedan a escuadra en la línea base, que es donde se apoya la lectura.
    Chart.defaults.elements.bar.borderRadius = 4;
    Chart.defaults.elements.bar.borderSkipped = 'bottom';
    Chart.defaults.elements.bar.borderWidth = 0;

    Chart.defaults.elements.line.borderWidth = 2;
    Chart.defaults.elements.line.tension = 0.3;
    Chart.defaults.elements.line.fill = false;

    // Puntos invisibles en reposo pero con área de acierto amplia: no hay que
    // clavar el cursor en un punto de 8px para leer el valor.
    Chart.defaults.elements.point.radius = 0;
    Chart.defaults.elements.point.hoverRadius = 5;
    Chart.defaults.elements.point.hitRadius = 12;
    Chart.defaults.elements.point.borderWidth = 2;
    Chart.defaults.elements.point.hoverBorderWidth = 2;

    // 2px de superficie entre segmentos, en vez de un borde de separación.
    Chart.defaults.elements.arc.borderWidth = 2;
    Chart.defaults.elements.arc.borderColor = surface.paper;

    if (Chart.defaults.datasets.bar) {
        Chart.defaults.datasets.bar.maxBarThickness = 28;
    }
    if (Chart.defaults.datasets.doughnut) {
        Chart.defaults.datasets.doughnut.cutout = '68%';
    }

    // Ejes: rejilla de un solo pelo, sin bordes de eje ni marcas de tick.
    Chart.defaults.scale.grid.color = chrome.grid;
    Chart.defaults.scale.grid.lineWidth = 1;
    Chart.defaults.scale.grid.drawTicks = false;
    Chart.defaults.scale.border.display = false;
    Chart.defaults.scale.ticks.padding = 8;
    Chart.defaults.scale.ticks.color = chrome.axis;
    Chart.defaults.scale.ticks.font = { size: 11, weight: '500' };

    // El grid del eje de categorías se desactiva por gráfica (scales.x.grid),
    // no aquí: Chart.defaults.scales.category solo trae `ticks`, sin objeto
    // `grid` que poder configurar.
    } catch (err) {
        console.warn('[CSChartTheme] No se pudieron aplicar todos los defaults de Chart.js:', err);
    }
})();
