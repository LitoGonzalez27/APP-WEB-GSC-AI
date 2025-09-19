// performance-overview.js - Montaje del gráfico Recharts estilo GSC
// Nota: Se usa import dinámico ESM desde CDN para evitar build steps.

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = src;
    s.async = true;
    s.crossOrigin = 'anonymous';
    s.onload = () => resolve();
    s.onerror = () => reject(new Error('Script load error: ' + src));
    document.head.appendChild(s);
  });
}

async function ensureReact() {
  if (window.React && window.ReactDOM && window.ReactDOM.createRoot) return window.React;
  // Cargar UMD para evitar múltiples instancias de React
  await loadScript('https://unpkg.com/react@18/umd/react.production.min.js');
  await loadScript('https://unpkg.com/react-dom@18/umd/react-dom.production.min.js');
  return window.React;
}

async function ensureRecharts() {
  try {
    if (window.Recharts) return window.Recharts;
    await loadScript('https://unpkg.com/recharts@2.12.7/umd/Recharts.min.js');
    return window.Recharts;
  } catch (e) {
    console.warn('Recharts no disponible (CORS/CSP). Usando fallback Chart.js');
    return null;
  }
}

async function ensureLucide() {
  if (window.lucideReact) return window.lucideReact;
  try {
    const mod = await import('https://esm.sh/lucide-react@0.454.0?bundle');
    window.lucideReact = mod;
    return mod;
  } catch (_) {
    return {};
  }
}

function normalizeCtrValue(v) {
  if (v == null) return 0;
  if (v <= 1) return v * 100; // ratio -> %
  return v; // ya en %
}

function formatNumber(n) {
  return (n ?? 0).toLocaleString();
}

function getConfigParams() {
  const country = document.getElementById('countrySelect')?.value || '';
  const urlsRaw = document.getElementById('urlsInput')?.value || '';
  const matchType = (document.querySelector('input[name="match_type"]:checked')?.value) || (window.utils?.matchType) || 'contains';
  // Normalizar URLs: líneas no vacías
  const urls = urlsRaw
    .split('\n')
    .map(s => s.trim())
    .filter(s => s.length > 0);
  return { country, urls, matchType };
}

function buildFetchUrl(base, start, end, siteUrl) {
  const u = new URL(base, window.location.origin);
  u.searchParams.set('start', start);
  u.searchParams.set('end', end);
  if (siteUrl) u.searchParams.set('siteUrl', siteUrl);
  // Añadir filtros de configuration
  const cfg = getConfigParams();
  if (cfg.country) u.searchParams.set('country', cfg.country);
  if (cfg.matchType) u.searchParams.set('match_type', cfg.matchType);
  if (cfg.urls && cfg.urls.length) u.searchParams.set('urls', cfg.urls.join('\n'));
  return u.toString();
}

function getGlobalDateRange() {
  try {
    const sel = window.dateSelector;
    if (!sel) return null;
    const fmt = (d) => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
    const { currentPeriod } = sel;
    if (!currentPeriod?.startDate || !currentPeriod?.endDate) return null;
    return { start: fmt(currentPeriod.startDate), end: fmt(currentPeriod.endDate) };
  } catch (_) { return null; }
}

async function mountPerformanceOverview(rootId = 'performanceOverviewRoot', fetchUrl = '/api/gsc/performance') {
  // Usar exclusivamente Chart.js (desactivar completamente flujo Recharts/React)
  return mountChartJSOverview(rootId, fetchUrl);
  // Código legacy Recharts/React queda debajo sin ejecutarse

  const { useMemo, useState, useEffect } = {};
  const {
    ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  } = {};

  function ToggleButton({ active, onClick, title, Icon }) {
    return React.createElement(
      'button',
      {
        type: 'button',
        className: 'btn btn-outline',
        'aria-pressed': !!active,
        onClick,
        style: {
          padding: '6px 10px', borderRadius: 6, border: `1px solid ${active ? '#161616' : '#d1d5db'}`,
          background: active ? '#161616' : 'transparent', color: active ? '#D8F9B8' : '#111827',
          display: 'inline-flex', alignItems: 'center', gap: 6, cursor: 'pointer'
        },
        title
      },
      Icon ? React.createElement(Icon, { size: 16 }) : null,
      React.createElement('span', null, title)
    );
  }

  // ✅ NUEVO: Componente para las tablas Top 10 Keywords y URLs
  function OverviewTables() {
    const [tablesData, setTablesData] = useState({ keywords: [], urls: [], hasComparison: false });

    // Obtener datos de window.currentData
    useEffect(() => {
      try {
        const cd = window.currentData || {};
        const hasComp = !!(cd.periods && cd.periods.has_comparison);
        
        // Keywords: de keyword_comparison_data o keywords
        let kwords = [];
        if (Array.isArray(cd.keywords)) kwords = cd.keywords.slice();
        else if (Array.isArray(cd.keyword_comparison_data)) kwords = cd.keyword_comparison_data.slice();
        
        // URLs: de pages
        const pagesList = Array.isArray(cd.pages) ? cd.pages.slice() : [];
        
        // Ordenar por clics descendente
        const sortByClicks = (a, b) => ((b.clicks_m1 ?? b.Clicks ?? 0) - (a.clicks_m1 ?? a.Clicks ?? 0));
        const topK = kwords.sort(sortByClicks).slice(0, 10);
        const topU = pagesList.sort(sortByClicks).slice(0, 10);

        setTablesData({ keywords: topK, urls: topU, hasComparison: hasComp });
      } catch (err) {
        console.warn('Error processing overview tables data:', err);
        setTablesData({ keywords: [], urls: [], hasComparison: false });
      }
    }, []);

    // Función para calcular delta
    const calcDelta = (current, previous, positiveIsGood = true) => {
      if (!tablesData.hasComparison || previous == null || previous === 0) return 'New';
      const val = ((current - previous) / previous) * 100;
      return val;
    };

    // Función para formatear delta
    const formatDelta = (delta, positiveIsGood = true) => {
      if (delta === 'New') return React.createElement('span', { style: { fontSize: 12, color: '#6b7280' } }, 'New');
      const good = positiveIsGood ? (delta >= 0) : (delta < 0);
      const color = good ? '#16a34a' : '#dc2626';
      const sign = delta > 0 ? '+' : '';
      return React.createElement('span', { style: { fontSize: 12, color } }, `${sign}${delta.toFixed(0)}%`);
    };

    // Renderizar tabla individual
    const renderTable = (items, isKeyword = true, title, icon) => {
      if (!items || items.length === 0) return null;
      
      const gridCols = tablesData.hasComparison ? '1fr 100px 70px 70px 70px 60px' : '1fr 120px 80px 80px 80px';
      
      return React.createElement(
        'div',
        { style: { background: '#fff', border: '1px solid #e5e7eb', borderRadius: 10, padding: 12 } },
        React.createElement(
          'div',
          { style: { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 } },
          React.createElement('i', { className: icon, style: { color: isKeyword ? '#2563eb' : '#10b981' } }),
          React.createElement('h4', { style: { margin: 0, fontWeight: 600, color: '#111827' } }, title)
        ),
        React.createElement(
          'div',
          { style: { fontSize: 13 } },
          // Header
          React.createElement(
            'div',
            { style: { display: 'grid', gridTemplateColumns: gridCols, gap: 8, padding: '6px 8px', borderBottom: '1px solid #f3f4f6', color: '#6b7280', fontSize: 12 } },
            React.createElement('div', null, isKeyword ? 'Query' : 'URL'),
            React.createElement('div', null, 'Clicks'),
            React.createElement('div', null, 'Impr.'),
            React.createElement('div', null, 'CTR'),
            React.createElement('div', null, 'Pos.'),
            tablesData.hasComparison ? React.createElement('div', null, 'Δ') : null
          ),
          // Rows
          items.map((item, index) => {
            const name = isKeyword ? (item.keyword || item.query || '') : (item.url || item.page || '');
            const c1 = item.clicks_m1 != null ? item.clicks_m1 : (item.Clicks != null ? item.Clicks : 0);
            const c2 = item.clicks_m2 != null ? item.clicks_m2 : 0;
            const i1 = item.impressions_m1 != null ? item.impressions_m1 : (item.Impressions != null ? item.Impressions : 0);
            const ctr1 = item.ctr_m1 != null ? item.ctr_m1 : (item.CTR != null ? (item.CTR * 100) : 0);
            const p1 = item.position_m1 != null ? item.position_m1 : (item.Position != null ? item.Position : null);
            
            const delta = calcDelta(c1, c2, true);
            
            return React.createElement(
              'div',
              { 
                key: index,
                style: { 
                  display: 'grid', 
                  gridTemplateColumns: gridCols, 
                  gap: 8, 
                  padding: '8px 8px', 
                  borderBottom: '1px solid #f9fafb', 
                  alignItems: 'center' 
                } 
              },
              React.createElement('div', { 
                style: { 
                  overflow: 'hidden', 
                  textOverflow: 'ellipsis', 
                  whiteSpace: 'nowrap', 
                  color: '#111827',
                  title: name
                } 
              }, name),
              React.createElement('div', { style: { fontWeight: 600, color: '#111827' } }, formatNumber(c1)),
              React.createElement('div', null, formatNumber(i1)),
              React.createElement('div', null, `${ctr1.toFixed(2)}%`),
              React.createElement('div', null, p1 != null ? p1.toFixed(2) : ''),
              tablesData.hasComparison ? React.createElement('div', null, formatDelta(delta, true)) : null
            );
          })
        )
      );
    };

    if (tablesData.keywords.length === 0 && tablesData.urls.length === 0) return null;

    return React.createElement(
      'div',
      { style: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, margin: '16px 0' } },
      renderTable(tablesData.keywords, true, 'Top 10 Keywords', 'fas fa-search'),
      renderTable(tablesData.urls, false, 'Top 10 URLs', 'fas fa-link')
    );
  }

  function Overview() {
    const siteUrlSelect = document.getElementById('siteUrlSelect');
    const [siteUrl, setSiteUrl] = useState(siteUrlSelect?.value || '');
    const [range, setRange] = useState(() => getGlobalDateRange());
    const [data, setData] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    // Totales del periodo
    const totals = useMemo(() => {
      if (!data || data.length === 0) return { clicks: 0, impressions: 0, ctr: 0, position: 0 };
      const clicks = data.reduce((a, b) => a + (b.clicks || 0), 0);
      const impressions = data.reduce((a, b) => a + (b.impressions || 0), 0);
      const ctr = impressions > 0 ? (clicks / impressions) * 100 : 0; // método por defecto: total
      const position = data.reduce((a, b) => a + (b.position || 0), 0) / data.length;
      return { clicks, impressions, ctr, position };
    }, [data]);
    const [show, setShow] = useState(() => {
      try {
        return JSON.parse(localStorage.getItem('po_toggles')) || { clicks: true, impressions: false, ctr: false, position: false };
      } catch (_) {
        return { clicks: true, impressions: false, ctr: false, position: false };
      }
    });
    // Eliminado invert position

    // Sincronizar con selector de fechas (cuando usuario pulsa Apply)
    useEffect(() => {
      const handler = () => setRange(getGlobalDateRange());
      const applyBtn = document.getElementById('modalApplyBtn');
      if (applyBtn) applyBtn.addEventListener('click', handler);
      return () => { if (applyBtn) applyBtn.removeEventListener('click', handler); };
    }, []);

    // Reaccionar a cambios de propiedad
    useEffect(() => {
      const select = document.getElementById('siteUrlSelect');
      if (!select) return;
      const onChange = () => setSiteUrl(select.value);
      select.addEventListener('change', onChange);
      return () => select.removeEventListener('change', onChange);
    }, []);

    useEffect(() => {
      if (!range || !range.start || !range.end) return;
      const url = buildFetchUrl(fetchUrl, range.start, range.end, siteUrl);
      setLoading(true); setError('');
      fetch(url)
        .then(async (r) => {
          if (!r.ok) {
            const e = await r.json().catch(() => ({}));
            throw new Error(e.error || r.statusText);
          }
          return r.json();
        })
        .then((rows) => {
          // ✅ MEJORA: Validar y limpiar datos antes de renderizar
          const normalized = (rows || []).map((p) => ({ 
            ...p, 
            ctr: normalizeCtrValue(p.ctr),
            // Validar que las métricas no sean negativas
            clicks: Math.max(0, p.clicks || 0),
            impressions: Math.max(0, p.impressions || 0),
            position: p.position > 0 ? p.position : null
          }));
          
          // ✅ MEJORA: Filtrar días sin datos reales si están al final del período
          const filteredData = normalized.filter((p, index, arr) => {
            // Mantener todos los días con datos
            if (p.clicks > 0 || p.impressions > 0) return true;
            
            // Para días sin datos, solo mantener si no están al final de la serie
            const isLastDay = index === arr.length - 1;
            if (isLastDay) {
              // Solo mantener el último día si es parte de una secuencia de días con datos
              const hasRecentData = arr.slice(Math.max(0, index - 2), index)
                .some(d => d.clicks > 0 || d.impressions > 0);
              return hasRecentData;
            }
            return true;
          });
          
          setData(filteredData);
        })
        .catch((e) => setError(e.message || 'Error cargando datos'))
        .finally(() => setLoading(false));
    }, [range?.start, range?.end, siteUrl]);

    // Sincronización inicial pasiva (por si el date selector y propiedades se cargan después)
    useEffect(() => {
      let attempts = 0;
      const t = setInterval(() => {
        attempts += 1;
        const r = getGlobalDateRange();
        if (r && (!range || r.start !== range.start || r.end !== range.end)) {
          setRange(r);
        }
        const sel = document.getElementById('siteUrlSelect');
        if (sel && sel.value && sel.value !== siteUrl) {
          setSiteUrl(sel.value);
        }
        if (attempts >= 15) clearInterval(t); // ~15s máximo de sincronización inicial
      }, 1000);
      return () => clearInterval(t);
    }, []);

    const yRightDomain = useMemo(() => {
      const ctrVals = data.map(d => d.ctr || 0);
      const posVals = data.map(d => d.position || 0);
      const maxCtr = Math.max(0, ...ctrVals);
      const maxPos = Math.max(0, ...posVals);
      return [0, Math.max(100, Math.ceil(Math.max(maxCtr, maxPos)))]
    }, [data]);

    const palette = { clicks: '#2563eb', impressions: '#10b981', ctr: '#f59e0b', position: '#ef4444' };

    return React.createElement(
      'div',
      { style: { display: 'flex', flexDirection: 'column', gap: 12 } },
      React.createElement(
        'div', { style: { display: 'flex', gap: 8, flexWrap: 'wrap' } },
        ToggleButton({ active: show.clicks, onClick: () => setShow((s)=>{const n={ ...s, clicks: !s.clicks }; localStorage.setItem('po_toggles', JSON.stringify(n)); return n; }), title: 'Clicks', Icon: (window.lucideReact?.MousePointerClick || window.lucideReact?.MousePointer || null) }),
        ToggleButton({ active: show.impressions, onClick: () => setShow((s)=>{const n={ ...s, impressions: !s.impressions }; localStorage.setItem('po_toggles', JSON.stringify(n)); return n; }), title: 'Impressions', Icon: (window.lucideReact?.Eye || null) }),
        ToggleButton({ active: show.ctr, onClick: () => setShow((s)=>{const n={ ...s, ctr: !s.ctr }; localStorage.setItem('po_toggles', JSON.stringify(n)); return n; }), title: 'CTR', Icon: (window.lucideReact?.Percent || null) }),
        ToggleButton({ active: show.position, onClick: () => setShow((s)=>{const n={ ...s, position: !s.position }; localStorage.setItem('po_toggles', JSON.stringify(n)); return n; }), title: 'Avg. Position', Icon: (window.lucideReact?.MapPin || null) })
      ),
      // Cabecera de totales
      React.createElement('div', { style: { display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: 16, color: '#111827', marginBottom: 30 } },
        React.createElement('div', null, `Clicks: ${formatNumber(totals.clicks)}`),
        React.createElement('div', null, `Impressions: ${formatNumber(totals.impressions)}`),
        React.createElement('div', null, `CTR: ${totals.ctr.toFixed(2)}%`),
        React.createElement('div', null, `Avg. Pos: ${totals.position.toFixed(2)}`)
      ),
      loading && React.createElement('div', { style: { fontSize: 13, color: '#6b7280' } }, 'Loading...'),
      error && React.createElement('div', { style: { color: '#b91c1c', fontSize: 13 } }, error),
      React.createElement(
        'div', { style: { width: '100%', height: 300 } },
        React.createElement(
          ResponsiveContainer, { width: '100%', height: '100%' },
          React.createElement(
            AreaChart, { data, margin: { top: 10, right: 24, left: 0, bottom: 0 } },
            React.createElement(CartesianGrid, { strokeDasharray: '3 3' }),
            React.createElement(XAxis, { dataKey: 'date' }),
            React.createElement(YAxis, { yAxisId: 'left', orientation: 'left', allowDecimals: false }),
            React.createElement(YAxis, { yAxisId: 'right', orientation: 'right', domain: yRightDomain }),
            React.createElement(Tooltip, {
              formatter: (value, name) => {
                if (name === 'ctr') return [`${(value ?? 0).toFixed(2)}%`, 'CTR'];
                if (name === 'position') return [(value ?? 0).toFixed(2), 'Avg. Position'];
                return [formatNumber(value ?? 0), name.charAt(0).toUpperCase() + name.slice(1)];
              },
            }),
            show.clicks ? React.createElement(Recharts.Area, { type: 'monotone', dataKey: 'clicks', yAxisId: 'left', stroke: palette.clicks, fill: palette.clicks, fillOpacity: 0.2, isAnimationActive: false }) : null,
            show.impressions ? React.createElement(Recharts.Area, { type: 'monotone', dataKey: 'impressions', yAxisId: 'left', stroke: palette.impressions, fill: palette.impressions, fillOpacity: 0.2, isAnimationActive: false }) : null,
            show.ctr ? React.createElement(Recharts.Area, { type: 'monotone', dataKey: 'ctr', yAxisId: 'right', stroke: palette.ctr, fill: palette.ctr, fillOpacity: 0.15, isAnimationActive: false }) : null,
            show.position ? React.createElement(Recharts.Area, { type: 'monotone', dataKey: 'position', yAxisId: 'right', stroke: palette.position, fill: palette.position, fillOpacity: 0.1, isAnimationActive: false }) : null,
          )
        )
      ),
      // ✅ NUEVO: Tablas Top 10 Keywords y URLs
      React.createElement(OverviewTables, null),
      React.createElement(
        'div', { style: { display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'center' } },
        ['clicks', 'impressions', 'ctr', 'position'].map((key) => (
          React.createElement('label', { key, style: { display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13 } },
            React.createElement('input', {
              type: 'checkbox', checked: !!show[key],
              onChange: () => setShow((s) => { const n={ ...s, [key]: !s[key] }; localStorage.setItem('po_toggles', JSON.stringify(n)); return n; }), 'aria-label': `Toggle ${key}`
            }),
            key.charAt(0).toUpperCase() + key.slice(1)
          )
        ))
      )
    );
  }

  const rootEl = document.getElementById(rootId);
  if (!rootEl) return;
  try {
    // Desactivado: flujo React/Recharts no se usa cuando forzamos Chart.js
    // Mantener oculto el disclaimer por consistencia visual
    try {
      const disclaimer = document.getElementById('summaryDisclaimer');
      if (disclaimer) disclaimer.style.display = 'none';
    } catch (_) {}

    // No render React. El montaje real lo hace mountChartJSOverview antes de entrar aquí
    // const root = window.ReactDOM.createRoot(rootEl);
    // root.render(window.React.createElement(Overview));
    if (window.sidebarOnContentReady) window.sidebarOnContentReady('performance');
  } catch (e) {
    console.error('Error montando PerformanceOverview:', e);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const hasRoot = document.getElementById('performanceOverviewRoot');
  if (hasRoot) mountPerformanceOverview();
});

window.mountPerformanceOverview = mountPerformanceOverview;

// ✅ DEBUGGING: Funciones globales para probar desde la consola
window.debugPerformanceOverview = {
  checkCurrentData: () => {
    console.log('🔍 window.currentData:', window.currentData);
    return window.currentData;
  },
  testTableRender: () => {
    const container = document.getElementById('performanceOverviewRoot');
    if (!container) {
      console.error('❌ No se encontró performanceOverviewRoot');
      return;
    }
    
    const kwEl = container.querySelector('#po-topkeywords');
    const urlEl = container.querySelector('#po-topurls');
    
    console.log('🔍 Estado de elementos de tablas:', {
      hasContainer: !!container,
      hasKeywordsEl: !!kwEl,
      hasUrlsEl: !!urlEl,
      containerHTML: container.innerHTML.length > 100 ? 'HTML presente' : 'HTML vacío'
    });
    
    return { container, kwEl, urlEl };
  },
  testMetricsUpdate: () => {
    const container = document.getElementById('performanceOverviewRoot');
    if (!container) {
      console.error('❌ No se encontró performanceOverviewRoot');
      return;
    }
    
    const clicksEl = container.querySelector('.po-metric[data-k="clicks"]');
    const imprEl = container.querySelector('.po-metric[data-k="impressions"]');
    const ctrEl = container.querySelector('.po-metric[data-k="ctr"]');
    const posEl = container.querySelector('.po-metric[data-k="position"]');
    
    console.log('🔍 Estado de elementos de métricas:', {
      hasClicks: !!clicksEl,
      hasImpressions: !!imprEl,
      hasCtr: !!ctrEl,
      hasPosition: !!posEl
    });
    
    // Probar actualización manual con datos de prueba
    if (clicksEl) {
      const p1 = clicksEl.querySelector('.po-p1');
      if (p1) {
        p1.innerHTML = '<span class="po-date">Periodo actual</span> · <strong class="po-value-strong">12.345</strong>';
        console.log('✅ Métrica de prueba insertada en clicks');
      }
    }
    
    return { clicksEl, imprEl, ctrEl, posEl };
  },
  // ✅ NUEVA función para forzar actualización de métricas
  forceMetricsUpdate: async () => {
    console.log('🔄 Forzando actualización de métricas...');
    
    const container = document.getElementById('performanceOverviewRoot');
    if (!container || !container._chart) {
      console.error('❌ No se encontró container o chart');
      return;
    }
    
    // Intentar obtener datos del gráfico existente
    const chart = container._chart;
    if (!chart || !chart.data || !chart.data.datasets) {
      console.error('❌ No hay datos en el gráfico');
      return;
    }
    
    // Obtener datos del primer dataset (clicks)
    const clicksData = chart.data.datasets[0]?.data || [];
    const impressionsData = chart.data.datasets[1]?.data || [];
    const ctrData = chart.data.datasets[2]?.data || [];
    const positionData = chart.data.datasets[3]?.data || [];
    
    console.log('📊 Datos extraídos del gráfico:', {
      clicks: clicksData.length,
      impressions: impressionsData.length,
      ctr: ctrData.length,
      position: positionData.length
    });
    
    if (clicksData.length === 0) {
      console.error('❌ No hay datos de clicks en el gráfico');
      return;
    }
    
    // Calcular totales
    const sum = (arr) => arr.reduce((a, b) => a + (b || 0), 0);
    const avg = (arr) => arr.length ? (arr.reduce((a, b) => a + (b || 0), 0) / arr.length) : 0;
    
    const tClicks = sum(clicksData);
    const tImpr = sum(impressionsData);
    const tCtr = tImpr > 0 ? (tClicks / tImpr) * 100 : 0;
    const tPos = avg(positionData);
    
    console.log('📊 Totales calculados:', {
      clicks: tClicks,
      impressions: tImpr,
      ctr: tCtr.toFixed(2) + '%',
      position: tPos.toFixed(2)
    });
    
    // Formatear números
    const formatNumberIntl = (n) => {
      try { return (n ?? 0).toLocaleString('es-ES'); } catch(_) { return String(n ?? 0); }
    };
    
    // Actualizar cada métrica manualmente
    const updateMetric = (key, value) => {
      const metricEl = container.querySelector(`.po-metric[data-k="${key}"]`);
      if (!metricEl) {
        console.warn(`⚠️ No se encontró métrica ${key}`);
        return;
      }
      
      const p1 = metricEl.querySelector('.po-p1');
      if (p1) {
        let formattedValue;
        if (key === 'clicks' || key === 'impressions') {
          formattedValue = formatNumberIntl(value);
        } else if (key === 'ctr') {
          formattedValue = `${value.toFixed(2)}%`;
        } else if (key === 'position') {
          formattedValue = value.toFixed(2);
        }
        
        p1.innerHTML = `<span class="po-date">Periodo actual</span> · <strong class="po-value-strong">${formattedValue}</strong>`;
        console.log(`✅ Métrica ${key} actualizada: ${formattedValue}`);
      }
    };
    
    updateMetric('clicks', tClicks);
    updateMetric('impressions', tImpr);
    updateMetric('ctr', tCtr);
    updateMetric('position', tPos);
    
    return { tClicks, tImpr, tCtr, tPos };
  }
};

console.log('🚀 Performance Overview debugging functions available:');
console.log('📍 window.debugPerformanceOverview.checkCurrentData()');
console.log('📍 window.debugPerformanceOverview.testTableRender()');
console.log('📍 window.debugPerformanceOverview.testMetricsUpdate()');
console.log('📍 window.debugPerformanceOverview.forceMetricsUpdate() // ⭐ NUEVA!');


// ==============================
// Fallback Chart.js (sin React)
// ==============================
function formatNumberIntl(n){try{return (n??0).toLocaleString()}catch(_){return String(n??0)}}

async function mountChartJSOverview(rootId, fetchUrl){
  const container = document.getElementById(rootId);
  if(!container) return;

  // Ocultar por CSS el summaryDisclaimer de forma global y usar performanceOverviewRoot como ancla
  try{
    let hideStyle = document.getElementById('po-hide-disclaimer');
    if(!hideStyle){
      hideStyle = document.createElement('style');
      hideStyle.id = 'po-hide-disclaimer';
      hideStyle.textContent = '#summaryDisclaimer{display:none !important;}';
      document.head.appendChild(hideStyle);
    }
  }catch(_){ }
  
  // Padding del contenedor raíz
  container.style.padding = '30px';

  // UI básica
  container.innerHTML = `
    <div id="po-metrics" style="display:flex;gap:22px;align-items:flex-start;justify-content:space-evenly;margin:2px 0 40px 0;flex-wrap:wrap;font-size:16px;color:#111827">
      <div class="po-metric" data-k="clicks" style="display:flex;gap:10px;align-items:flex-start">
        <i class="fas fa-mouse-pointer" style="color:#2563eb;font-size:18px;margin-top:2px"></i>
        <div>
          <div style="font-weight:600">Clicks</div>
          <div class="po-lines" style="display:flex;flex-direction:column;gap:2px;font-size:13px;color:#374151">
            <div class="po-p1"></div>
            <div class="po-p2"></div>
            <div class="po-delta" style="font-size:13px"></div>
          </div>
        </div>
      </div>
      <div class="po-metric" data-k="impressions" style="display:flex;gap:10px;align-items:flex-start">
        <i class="fas fa-eye" style="color:#10b981;font-size:18px;margin-top:2px"></i>
        <div>
          <div style="font-weight:600">Impr.</div>
          <div class="po-lines" style="display:flex;flex-direction:column;gap:2px;font-size:13px;color:#374151">
            <div class="po-p1"></div>
            <div class="po-p2"></div>
            <div class="po-delta" style="font-size:13px"></div>
          </div>
        </div>
      </div>
      <div class="po-metric" data-k="ctr" style="display:flex;gap:10px;align-items:flex-start">
        <i class="fas fa-percentage" style="color:#f59e0b;font-size:18px;margin-top:2px"></i>
        <div>
          <div style="font-weight:600">CTR</div>
          <div class="po-lines" style="display:flex;flex-direction:column;gap:2px;font-size:13px;color:#374151">
            <div class="po-p1"></div>
            <div class="po-p2"></div>
            <div class="po-delta" style="font-size:13px"></div>
          </div>
        </div>
      </div>
      <div class="po-metric" data-k="position" style="display:flex;gap:10px;align-items:flex-start">
        <i class="fas fa-location-arrow" style="color:#ef4444;font-size:18px;margin-top:2px"></i>
        <div>
          <div style="font-weight:600">Pos.</div>
          <div class="po-lines" style="display:flex;flex-direction:column;gap:2px;font-size:13px;color:#374151">
            <div class="po-p1"></div>
            <div class="po-p2"></div>
            <div class="po-delta" style="font-size:13px"></div>
          </div>
        </div>
      </div>
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;align-items:center;justify-content:space-between" id="po-top-toggles">
      <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
        <button type="button" data-k="clicks" class="po-btn">Clicks</button>
        <button type="button" data-k="impressions" class="po-btn">Impressions</button>
        <button type="button" data-k="ctr" class="po-btn">CTR</button>
        <button type="button" data-k="position" class="po-btn">Avg. Position</button>
      </div>
      <div id="po-trend-controls" style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;position:relative">
        <button type="button" data-trend="clicks" class="po-btn po-trend-btn">Trend clicks</button>
        <button type="button" data-trend="impressions" class="po-btn po-trend-btn">Trend impressions</button>
        <button type="button" data-trend="ctr" class="po-btn po-trend-btn">Trend CTR</button>
        <button type="button" data-trend="position" class="po-btn po-trend-btn">Trend position</button>
        <span id="po-trend-info" class="urls-info-icon" aria-label="Trend info">ℹ️</span>
        <div id="po-trend-tooltip" class="urls-info-tooltip" style="top:auto;bottom:120%;right:0;min-width:260px">
          <strong>Trend lines behavior</strong>
          <p>When comparison is active, trend lines are computed over the current period only. They do not use the comparison period or combined totals.</p>
        </div>
      </div>
      <style>
        .po-btn{padding:6px 10px;border-radius:6px;border:1px solid #d1d5db;background:#fff;color:#111827;cursor:pointer}
        .po-btn.active{background:#161616;color:#D8F9B8;border-color:#161616}
        .po-trend-btn{border-style:dashed}
        /* Tipografías para P1/P2 y valores */
        #po-metrics .po-lines .po-date{font-size:12px;color:#6b7280}
        #po-metrics .po-lines .po-value-strong{font-size:15px;color:#111827}
        #po-metrics .po-lines .po-value-small{font-size:12px;color:#374151;opacity:0.85}
      </style>
    </div>
    <div style="width:100%;height:320px"><canvas id="po-canvas" aria-label="Performance Overview Chart" role="img"></canvas></div>
    <div id="po-toplists" style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px">
      <div class="po-card" style="background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:12px">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
          <i class="fas fa-search" style="color:#2563eb"></i>
          <h4 style="margin:0;font-weight:600;color:#111827">Queries</h4>
        </div>
        <div class="po-table" id="po-topkeywords"></div>
      </div>
      <div class="po-card" style="background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:12px">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
          <i class="fas fa-link" style="color:#10b981"></i>
          <h4 style="margin:0;font-weight:600;color:#111827">Pages</h4>
        </div>
        <div class="po-table" id="po-topurls"></div>
      </div>
    </div>
  `;

  const savedToggles = JSON.parse(localStorage.getItem('po_toggles')||'{}');
  const state = { 
    // Forzar Clicks e Impressions activos por defecto al entrar
    show: { clicks: true, impressions: true, ctr: !!savedToggles.ctr, position: !!savedToggles.position }
  };

  const syncButtons = ()=>{
    container.querySelectorAll('#po-top-toggles .po-btn[data-k]').forEach(btn=>{
      const k = btn.getAttribute('data-k');
      btn.classList.toggle('active', !!state.show[k]);
    });
  };

  syncButtons();

  // Asegurar que Chart.js esté disponible (carga perezosa si hace falta)
  const ensureChartJS = async ()=>{
    if (window.Chart) return window.Chart;
    try{
      await loadScript('https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js');
      return window.Chart;
    }catch(e){
      console.warn('No fue posible cargar Chart.js dinámicamente:', e);
      return null;
    }
  };

  const ctx = container.querySelector('#po-canvas');
  if(!ctx){
    console.warn('No se encontró el canvas #po-canvas');
    return;
  }
  if(!window.Chart){
    await ensureChartJS();
  }
  if(!window.Chart){
    console.warn('Chart.js no está disponible');
    return;
  }

  // Inicializar tooltip de info (consistente con configuration)
  try{
    const infoIcon = container.querySelector('#po-trend-info');
    const tooltip = container.querySelector('#po-trend-tooltip');
    if(infoIcon && tooltip){
      const open = ()=> tooltip.classList.add('active');
      const close = ()=> tooltip.classList.remove('active');
      infoIcon.addEventListener('mouseenter', open);
      infoIcon.addEventListener('mouseleave', ()=> setTimeout(()=>{ if(!tooltip.matches(':hover')) close(); }, 100));
      tooltip.addEventListener('mouseenter', open);
      tooltip.addEventListener('mouseleave', close);
      infoIcon.addEventListener('click', (e)=>{ e.preventDefault(); e.stopPropagation(); tooltip.classList.toggle('active'); });
      document.addEventListener('click', (e)=>{ if(!container.querySelector('#po-top-toggles').contains(e.target)) close(); });
      document.addEventListener('keydown', (e)=>{ if(e.key==='Escape') close(); });
    }
  }catch(_){ }

  const siteSelect = document.getElementById('siteUrlSelect');
  const range = getGlobalDateRange();
  const siteUrl = siteSelect?.value || '';
  if(!range || !siteUrl){ /* esperar cambios */ }

  const fmt = (d)=>{
    const y=d.getFullYear(); const m=String(d.getMonth()+1).padStart(2,'0'); const da=String(d.getDate()).padStart(2,'0');
    return `${y}-${m}-${da}`;
  };

  const fetchAndRender = async ()=>{
    const r = getGlobalDateRange();
    const s = document.getElementById('siteUrlSelect')?.value || siteUrl;
    if(!r || !r.start || !r.end || !s) {
      console.log('⚠️ Faltan datos para cargar gráfico:', {range: r, siteUrl: s});
      return;
    }
    const url = buildFetchUrl(fetchUrl, r.start, r.end, s);
    console.log('📊 Cargando datos de:', url);
    let rows=[];
    try{
      const resp = await fetch(url);
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
      }
      rows = await resp.json();
      console.log('📊 Datos recibidos:', rows.length, 'días');
    }catch(e){ 
      console.error('❌ Error cargando /api/gsc/performance:', e); 
      return; 
    }

    // ¿Hay comparación activa?
    let rowsComp = [];
    try{
      const ds = window.dateSelector;
      if(ds && ds.comparisonMode && ds.comparisonMode !== 'none' && ds.comparisonPeriod?.startDate && ds.comparisonPeriod?.endDate){
        const cs = fmt(ds.comparisonPeriod.startDate);
        const ce = fmt(ds.comparisonPeriod.endDate);
        const compUrl = buildFetchUrl(fetchUrl, cs, ce, s);
        const resp2 = await fetch(compUrl);
        rowsComp = await resp2.json();
      }
    }catch(_){ rowsComp = []; }

    const labels = rows.map(d=>d.date);
    const clicks = rows.map(d=>d.clicks||0);
    const impressions = rows.map(d=>d.impressions||0);
    const ctr = rows.map(d=> (d.ctr||0) <=1 ? (d.ctr||0)*100 : (d.ctr||0));
    const position = rows.map(d=>d.position||0);

    const clicksComp = rowsComp.map(d=>d.clicks||0);
    const impressionsComp = rowsComp.map(d=>d.impressions||0);
    const ctrComp = rowsComp.map(d=> ((d.ctr||0) <=1 ? (d.ctr||0)*100 : (d.ctr||0)));
    const positionComp = rowsComp.map(d=>d.position||0);

    // 1) Actualizar métricas inmediatamente aunque el gráfico aún no exista
    try{
      const sum = (arr)=>arr.reduce((a,b)=>a+(b||0),0);
      const avg = (arr)=> arr.length ? (arr.reduce((a,b)=>a+(b||0),0)/arr.length) : 0;

      // Preferir datos de summary del backend (agregado por día, sin límite de filas)
      let tClicks, tImpr, tCtr, tPos, tClicksC, tImprC, tCtrC, tPosC;
      const cd = window.currentData || {};
      if (Array.isArray(cd.summary) && cd.summary.length > 0) {
        const metrics = (cd.summary||[]).flatMap(s => Array.isArray(s.Metrics) ? s.Metrics : []);
        const findBySuffix = (suffix)=> metrics.find(m => (m.Period||'').includes(suffix)) || null;
        // Buscar explícitamente etiquetas añadidas por el backend
        const mCur = findBySuffix('(Current)');
        const mCmp = findBySuffix('(Comparison)');
        if (mCur) {
          tClicks = mCur.Clicks||0; tImpr = mCur.Impressions||0; tCtr = (mCur.CTR||0)*100; tPos = mCur.Position ?? 0;
        }
        if (mCmp) {
          tClicksC = mCmp.Clicks||0; tImprC = mCmp.Impressions||0; tCtrC = (mCmp.CTR||0)*100; tPosC = mCmp.Position ?? 0;
        }
      }

      // Fallback a series del gráfico si no hay summary
      if (typeof tClicks === 'undefined') {
        tClicks = sum(clicks);
        tImpr = sum(impressions);
        tCtr = tImpr>0 ? (tClicks/tImpr)*100 : 0;
        tPos = avg(position);
      }
      if (typeof tClicksC === 'undefined') {
        tClicksC = sum(clicksComp);
        tImprC = sum(impressionsComp);
        tCtrC = tImprC>0 ? (tClicksC/tImprC)*100 : 0;
        tPosC = avg(positionComp);
      }

      const formatNumberIntl = (n) => { try { return (n ?? 0).toLocaleString('es-ES'); } catch(_) { return String(n ?? 0); } };
      const updateQuick = (key, value, compValue, isPercent=false, isPosition=false)=>{
        const root = container.querySelector(`.po-metric[data-k="${key}"]`);
        if(!root) return;
        const p1 = root.querySelector('.po-p1');
        const p2 = root.querySelector('.po-p2');
        const dEl = root.querySelector('.po-delta');
        const formatVal = (v)=> isPercent ? `${(v||0).toFixed(2)}%` : (isPosition ? (v||0).toFixed(2) : formatNumberIntl(v||0));
        const ds = window.dateSelector;
        const fmtDate=(d)=>`${String(d.getDate()).padStart(2,'0')}/${String(d.getMonth()+1).padStart(2,'0')}/${d.getFullYear()}`;
        const cur = ds?.currentPeriod; const comp = ds?.comparisonPeriod;
        const p1Label = (cur?.startDate && cur?.endDate) ? `${fmtDate(cur.startDate)} - ${fmtDate(cur.endDate)}` : 'Periodo actual';
        const p2Label = (comp?.startDate && comp?.endDate) ? `${fmtDate(comp.startDate)} - ${fmtDate(comp.endDate)}` : 'Periodo anterior';
        if(p1) p1.innerHTML = `<span class="po-date">${p1Label}</span> · <strong class="po-value-strong">${formatVal(value)}</strong>`;
        if(p2) p2.innerHTML = rowsComp.length ? `<span class="po-date">${p2Label}</span> · <span class="po-value-small">${formatVal(compValue)}</span>` : '';
        if(dEl){
          if(rowsComp.length){
            let delta;
            if(isPosition){ delta = (value - compValue); }
            else if(isPercent){ delta = ((value - (compValue||1)) / (compValue||1)) * 100; }
            else { delta = (value - compValue); }
            const good = isPosition ? (delta < 0) : (delta >= 0);
            dEl.style.color = good ? '#16a34a' : '#dc2626';
            dEl.textContent = isPosition ? `${delta.toFixed(2)}` : (isPercent ? `${delta.toFixed(2)}%` : `${delta.toFixed(0)}%`);
          } else {
            dEl.textContent = '';
          }
        }
      };
      updateQuick('clicks', tClicks, tClicksC, true, false);
      updateQuick('impressions', tImpr, tImprC, true, false);
      updateQuick('ctr', tCtr, tCtrC, false, false);
      updateQuick('position', tPos, tPosC, false, true);
      console.log('✅ Métricas Overview actualizadas (modo rápido)');
    }catch(e){ console.warn('⚠️ No se pudieron actualizar métricas en modo rápido:', e); }

    if(container._chart){ container._chart.destroy(); }

    // Crear tooltip externo
    let tt = container.querySelector('#po-tooltip');
    if(!tt){
      tt = document.createElement('div');
      tt.id = 'po-tooltip';
      tt.style.cssText = 'position:absolute;pointer-events:none;background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:8px 10px;box-shadow:0 8px 30px rgba(0,0,0,0.08);font-size:13px;color:#111827;z-index:5;display:none;min-width:220px;';
      container.style.position = 'relative';
      container.appendChild(tt);
    }

    const externalTooltip = (context)=>{
      const {chart, tooltip} = context;
      if(!tooltip || tooltip.opacity === 0){ tt.style.display='none'; return; }

      const i = tooltip.dataPoints?.[0]?.dataIndex ?? 0;
      const dateCur = labels[i] || '';
      const dateComp = rowsComp[i]?.date || '';

      const fmtDate = (iso)=>{
        try{ const d = new Date(iso+'T00:00:00'); return d.toLocaleDateString(undefined,{month:'short', day:'2-digit', year:'numeric'});}catch(_){return iso}
      };

      const rowsHTML = [];
      const pushRow = (name, color, curVal, compVal, isPercentDelta, isPosition=false)=>{
        // Delta
        let deltaHtml = '';
        if(rowsComp.length){
          if(isPosition){
            const d = (curVal - compVal);
            const sign = d >= 0 ? '+' : '';
            const col = d >= 0 ? '#16a34a' : '#dc2626';
            deltaHtml = `<span style="color:${col};margin-left:6px">${sign}${d.toFixed(2)}</span>`;
          }else if(isPercentDelta){
            const base = compVal || 1;
            const d = ((curVal - base) / base) * 100;
            const sign = d >= 0 ? '+' : '';
            const col = d >= 0 ? '#16a34a' : '#dc2626';
            deltaHtml = `<span style="color:${col};margin-left:6px">${sign}${d.toFixed(0)}%</span>`;
          }else{
            const d = (curVal - compVal);
            const sign = d >= 0 ? '+' : '';
            const col = d >= 0 ? '#16a34a' : '#dc2626';
            deltaHtml = `<span style="color:${col};margin-left:6px">${sign}${d.toFixed(2)}</span>`;
          }
        }
        const curFmt = isPosition ? curVal.toFixed(2) : (name.includes('CTR') ? `${curVal.toFixed(2)}%` : formatNumberIntl(curVal));
        const compFmt = rowsComp.length ? (isPosition ? compVal.toFixed(2) : (name.includes('CTR') ? `${compVal.toFixed(2)}%` : formatNumberIntl(compVal))) : '';
        rowsHTML.push(`
          <div style="display:flex;justify-content:space-between;align-items:center;margin:2px 0">
            <div style="display:flex;align-items:center;gap:8px">
              <span style="width:8px;height:8px;background:${color};border-radius:50%;display:inline-block"></span>
              <span>${name}</span>
            </div>
            <div style="display:flex;align-items:center;gap:8px">
              <strong>${curFmt}</strong>${deltaHtml}
              ${rowsComp.length ? `<span style="opacity:0.7;min-width:64px;text-align:right">${compFmt}</span>` : ''}
            </div>
          </div>`);
      };

      if(state.show.clicks) pushRow('Clicks','#2563eb', clicks[i]||0, clicksComp[i]||0, true);
      if(state.show.impressions) pushRow('Impressions','#10b981', impressions[i]||0, impressionsComp[i]||0, true);
      if(state.show.ctr) pushRow('CTR','#f59e0b', ctr[i]||0, ctrComp[i]||0, false);
      if(state.show.position) pushRow('Avg. Position','#ef4444', position[i]||0, positionComp[i]||0, false, true);

      tt.innerHTML = `
        <div style="display:flex;justify-content:space-between;gap:10px;margin-bottom:6px">
          <div><div style="font-weight:600;">${fmtDate(dateCur)}</div></div>
          ${rowsComp.length ? `<div style="opacity:0.8;text-align:right"><div style="font-weight:600;">${fmtDate(dateComp)}</div></div>` : ''}
        </div>
        ${rowsHTML.join('')}
      `;
      const {offsetLeft: positionX, offsetTop: positionY} = chart.canvas;
      tt.style.left = positionX + tooltip.caretX + 12 + 'px';
      tt.style.top = positionY + tooltip.caretY - tt.offsetHeight - 12 + 'px';
      tt.style.display = 'block';
    };

    // Puntos interactivos en hover
  const hoverStyle = { mode: 'index', intersect: false, onHover: (e, active) => { /* noop */ } };

    // Definir gradientes verticales (blanco -> color)
    const ctx2 = ctx.getContext('2d');
    const makeGrad = (hex, dim=1)=>{
      const clamp = (v)=> Math.max(0, Math.min(1, v));
      const withAlpha = (a)=> hex.replace(/1\)$/,'') + clamp(a) + ')';
      const g = ctx2.createLinearGradient(0, ctx.height, 0, 0);
      // Estilo GSC con factor dim para atenuar el relleno cuando se activa la tendencia
      const aLight = 0.08 * dim;
      const aMedium = 0.22 * dim;
      const aStrong = 0.40 * dim;
      g.addColorStop(0.00, withAlpha(aLight));
      g.addColorStop(0.35, withAlpha(aLight));
      g.addColorStop(0.70, withAlpha(aMedium));
      g.addColorStop(1.00, withAlpha(aStrong));
      return g;
    };
    // Normaliza un color a 'rgba(r,g,b,1)'
    const ensureRgba1 = (c)=>{
      if (typeof c !== 'string') return 'rgba(0,0,0,1)';
      if (c.startsWith('rgba(')) {
        return c.replace(/rgba\((\s*\d+\s*,\s*\d+\s*,\s*\d+\s*),\s*[^)]+\)/, 'rgba($1,1)');
      }
      if (c.startsWith('rgb(')) {
        return c.replace(/rgb\(([^)]+)\)/, 'rgba($1,1)');
      }
      return 'rgba(0,0,0,1)';
    };
    // Exponer helpers a nivel del contenedor para usarlos en handlers externos
    container._makeGrad = makeGrad;
    container._ensureRgba1 = ensureRgba1;
    container._baseIndexMap = { clicks:0, impressions:1, ctr:2, position:3 };
    // Colores base en rgba fuertes para líneas
    const colClicks = 'rgba(37,99,235,1)';
    const colImpr = 'rgba(16,185,129,1)';
    const colCtr = 'rgba(245,158,11,1)';
    const colPos = 'rgba(239,68,68,1)';

    // Calcular series de tendencia lineal (mínimos cuadrados) por métrica
    const linReg = (ys)=>{
      const n = ys.length; if(!n) return [];
      const xs = ys.map((_,i)=>i);
      const sumX = xs.reduce((a,b)=>a+b,0);
      const sumY = ys.reduce((a,b)=>a+(b||0),0);
      const sumXX = xs.reduce((a,b)=>a+b*b,0);
      const sumXY = xs.reduce((a,xi,i)=>a+xi*(ys[i]||0),0);
      const denom = (n*sumXX - sumX*sumX) || 1;
      const a = (n*sumXY - sumX*sumY) / denom; // slope
      const b = (sumY - a*sumX) / n; // intercept
      return xs.map(x=> a*x + b);
    };

    const trendClicks = linReg(clicks);
    const trendImpr = linReg(impressions);
    const trendCtr = linReg(ctr);
    const trendPos = linReg(position);

    try {
    // 2) Preparar mapa de índices de tendencia ANTES de crear el gráfico
    const trendStartIndex = 4 + (rowsComp.length ? 4 : 0);
    container._trendIndexMap = {
      clicks: trendStartIndex,
      impressions: trendStartIndex + 1,
      ctr: trendStartIndex + 2,
      position: trendStartIndex + 3,
    };

    // Asegurar Chart.js cargado en cada render
    if(!window.Chart){
      try{ await ensureChartJS(); }catch(_){ /* noop */ }
    }

    container._chart = new Chart(ctx, {
        type: 'line',
        data: {
          labels,
          datasets: [
          {label:'Clicks', data:clicks, borderColor:colClicks, backgroundColor:makeGrad('rgba(37,99,235,1)', 1), fill:true, yAxisID:'y', hidden: !state.show.clicks, pointRadius:0, tension:0.25},
          {label:'Impressions', data:impressions, borderColor:colImpr, backgroundColor:makeGrad('rgba(16,185,129,1)', 1), fill:true, yAxisID:'y1', hidden: !state.show.impressions, pointRadius:0, tension:0.25},
          {label:'CTR (%)', data:ctr, borderColor:colCtr, backgroundColor:makeGrad('rgba(245,158,11,1)', 1), fill:true, yAxisID:'y2', hidden: !state.show.ctr, pointRadius:0, tension:0.25},
          {label:'Avg. Position', data:position, borderColor:colPos, backgroundColor:makeGrad('rgba(239,68,68,1)', 1), fill:true, yAxisID:'y3', hidden: !state.show.position, pointRadius:0, tension:0.2, borderWidth:1.5}
          // Periodo comparado (solo líneas punteadas, sin fill)
          , ...(rowsComp.length ? [
            {label:'Clicks (comp)', data:clicksComp, borderColor:colClicks, fill:false, yAxisID:'y', hidden: !state.show.clicks, pointRadius:0, tension:0.25, borderDash:[5,5], borderWidth:2, backgroundColor:'transparent'},
            {label:'Impressions (comp)', data:impressionsComp, borderColor:colImpr, fill:false, yAxisID:'y1', hidden: !state.show.impressions, pointRadius:0, tension:0.25, borderDash:[5,5], borderWidth:2, backgroundColor:'transparent'},
            {label:'CTR (comp) %', data:ctrComp, borderColor:colCtr, fill:false, yAxisID:'y2', hidden: !state.show.ctr, pointRadius:0, tension:0.25, borderDash:[5,5], borderWidth:2, backgroundColor:'transparent'},
            {label:'Position (comp)', data:positionComp, borderColor:colPos, fill:false, yAxisID:'y3', hidden: !state.show.position, pointRadius:0, tension:0.25, borderDash:[5,5], borderWidth:2, backgroundColor:'transparent'}
          ] : []),
          // Tendencias (inicialmente ocultas, se activan con botones)
          {label:'Trend Clicks', data: trendClicks, borderColor: colClicks, yAxisID:'y', pointRadius:0, tension:0, borderDash:[2,2], hidden:true, order: 999, backgroundColor:'transparent'},
          {label:'Trend Impressions', data: trendImpr, borderColor: colImpr, yAxisID:'y1', pointRadius:0, tension:0, borderDash:[2,2], hidden:true, order: 999, backgroundColor:'transparent'},
          {label:'Trend CTR', data: trendCtr, borderColor: colCtr, yAxisID:'y2', pointRadius:0, tension:0, borderDash:[2,2], hidden:true, order: 999, backgroundColor:'transparent'},
          {label:'Trend Position', data: trendPos, borderColor: colPos, yAxisID:'y3', pointRadius:0, tension:0, borderDash:[2,2], hidden:true, order: 999, backgroundColor:'transparent'}
          ]
        },
        options: {
          responsive:true,
          maintainAspectRatio:false,
          animation:false,
          plugins:{ legend:{ display:false }, tooltip:{ enabled:false, mode:'index', intersect:false, external: externalTooltip } },
          scales:{
            y:{ position:'left', ticks:{ callback:(v)=>formatNumberIntl(v) }},
            y1:{ position:'right', grid:{ drawOnChartArea:false }, ticks:{ callback:(v)=>formatNumberIntl(v) }},
            // Ejes internos no visibles para escalado dinámico
            y2:{ display:false, suggestedMin: 0, suggestedMax: Math.max(10, Math.ceil(Math.max(...ctr) * 1.2)) },
            y3:{ display:false, suggestedMin: 0, suggestedMax: Math.max(10, Math.ceil(Math.max(...position) * 1.2)) },
            x:{ ticks:{ maxTicksLimit: 10 } }
          },
          hover: hoverStyle,
          elements: { point: { radius: 0, hoverRadius: 4, hitRadius: 6 } }
        }
      });
    } catch(chartErr) {
      console.error('❌ Error creando gráfico Chart.js:', chartErr);
      container._chart = null; // Continuar para actualizar métricas y tablas
    }

    // ✅ MEJORADO: Top 10 tablas (Keywords y URLs) desde window.currentData
    try{
      const cd = window.currentData || {};
      console.log('🔍 DEBUG: Estructura de currentData:', cd);
      
      const hasComp = !!(cd.periods && cd.periods.has_comparison);
      
      // ✅ Mejorado: Obtener keywords con más opciones de acceso
      let kwords = [];
      if (Array.isArray(cd.keyword_comparison_data)) {
        kwords = cd.keyword_comparison_data.slice();
        console.log('📋 Keywords desde keyword_comparison_data:', kwords.length);
      } else if (Array.isArray(cd.keywords)) {
        kwords = cd.keywords.slice();
        console.log('📋 Keywords desde keywords:', kwords.length);
      } else if (Array.isArray(cd.keywordStats)) {
        kwords = cd.keywordStats.slice();
        console.log('📋 Keywords desde keywordStats:', kwords.length);
      }
      
      // ✅ Mejorado: Obtener páginas con más opciones de acceso
      let pagesList = [];
      if (Array.isArray(cd.pages)) {
        pagesList = cd.pages.slice();
        console.log('📋 URLs desde pages:', pagesList.length);
      }
      
      // Si no hay datos, salir sin error
      if (kwords.length === 0 && pagesList.length === 0) {
        console.log('⚠️ No hay datos para tablas Top 10, esperando...');
        return;
      }
      
      // ✅ DEBUG: Mostrar estructura de datos antes de procesar
      if (kwords.length > 0) {
        console.log('🔍 DEBUG: Primer elemento de keywords:', kwords[0]);
        console.log('🔍 DEBUG: Propiedades disponibles keywords:', Object.keys(kwords[0]));
      }
      if (pagesList.length > 0) {
        console.log('🔍 DEBUG: Primer elemento de pages:', pagesList[0]);
        console.log('🔍 DEBUG: Propiedades disponibles pages:', Object.keys(pagesList[0]));
      }
      
      // ✅ Mejorado: Función de ordenamiento más robusta
      const sortByClicks = (a, b) => {
        // Intentar múltiples propiedades para obtener clics
        const aClicks = a.clicks_m1 ?? a.clicks_p1 ?? a.Clicks ?? a.clicks ?? 
                       (a.Metrics && a.Metrics[0] && a.Metrics[0].Clicks) ?? 0;
        const bClicks = b.clicks_m1 ?? b.clicks_p1 ?? b.Clicks ?? b.clicks ?? 
                       (b.Metrics && b.Metrics[0] && b.Metrics[0].Clicks) ?? 0;
        return bClicks - aClicks;
      };
      
      const topK = kwords.sort(sortByClicks).slice(0, 10);
      const topU = pagesList.sort(sortByClicks).slice(0, 10);
      
      console.log('🔝 Top 10 Keywords:', topK.length, topK.slice(0,2));
      console.log('🔝 Top 10 URLs:', topU.length, topU.slice(0,2));
      
      const fmtNum = (n) => {
        try { 
          return (n ?? 0).toLocaleString('es-ES'); 
        } catch(_) { 
          return String(n ?? 0);
        } 
      };
      const fmtCtr = (n) => `${(n ?? 0).toFixed(2)}%`;
      const fmtPos = (n) => (n == null ? '' : (n).toFixed(2));
      
      const deltaChip = (cur, prev, positiveIsGood = true) => {
        if (!hasComp) return '';
        if (prev == null || prev === 0) return `<span style="font-size:12px;color:#6b7280">New</span>`;
        const val = ((cur - prev) / prev) * 100;
        const good = positiveIsGood ? (val >= 0) : (val < 0);
        const col = good ? '#16a34a' : '#dc2626';
        const sign = val > 0 ? '+' : '';
        return `<span style="font-size:12px;color:${col}">${sign}${val.toFixed(0)}%</span>`;
      };
      
      // ✅ SIMPLIFICADO: Solo clicks e impressions con deltas como en el ejemplo
      const buildTable = (rows, isKeyword = true) => {
        if (!rows || rows.length === 0) {
          return `<div style="padding:16px;text-align:center;color:#6b7280;font-style:italic">No hay datos disponibles</div>`;
        }
        
        // Simplificado: solo name, clicks, impressions
        const cols = '1fr 120px 120px';
        const head = `<div style="display:grid;grid-template-columns:${cols};gap:12px;padding:8px 12px;border-bottom:1px solid #f3f4f6;color:#6b7280;font-size:12px;font-weight:500">
          <div>${isKeyword ? 'Query' : 'Page'}</div>
          <div style="text-align:center">Clicks</div>
          <div style="text-align:center">Impressions</div>
        </div>`;
        
        const body = rows.map((r, index) => {
          const name = isKeyword ? 
            (r.keyword || r.query || r.Query || '') : 
            (r.url || r.page || r.URL || r.Page || '');
            
          // ✅ MEJORADO: Acceso más robusto a métricas incluyendo estructura Metrics[]
          const getMetric = (item, metricName) => {
            // Intentar propiedades directas primero
            const direct = item[`${metricName}_m1`] ?? item[`${metricName}_p1`] ?? 
                          item[metricName.charAt(0).toUpperCase() + metricName.slice(1)] ?? 
                          item[metricName];
            if (direct !== undefined) return direct;
            
            // Intentar estructura anidada Metrics[]
            if (item.Metrics && Array.isArray(item.Metrics) && item.Metrics[0]) {
              return item.Metrics[0][metricName.charAt(0).toUpperCase() + metricName.slice(1)] ?? 0;
            }
            
            return 0;
          };
          
          const c1 = getMetric(r, 'clicks');
          const c2 = r.clicks_m2 ?? r.clicks_p2 ?? (r.Metrics && r.Metrics[1] && r.Metrics[1].Clicks) ?? 0;
          const i1 = getMetric(r, 'impressions');
          const i2 = r.impressions_m2 ?? r.impressions_p2 ?? (r.Metrics && r.Metrics[1] && r.Metrics[1].Impressions) ?? 0;
          
          // Log para debugging del primer elemento
          if (index === 0) {
            console.log(`🔍 DEBUG buildTable ${isKeyword ? 'keyword' : 'page'}:`, {
              name,
              clicks: c1,
              impressions: i1,
              originalData: r
            });
          }
          
          // Calcular deltas para clicks e impressions
          const clicksDelta = hasComp && c2 > 0 ? deltaChip(c1, c2, true) : '';
          const imprDelta = hasComp && i2 > 0 ? deltaChip(i1, i2, true) : '';
          
          return `<div style="display:grid;grid-template-columns:${cols};gap:12px;padding:10px 12px;border-bottom:1px solid #f9fafb;align-items:center">
            <div style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#111827;font-size:13px" title="${name}">${name}</div>
            <div style="text-align:center">
              <div style="font-weight:600;color:#111827;font-size:14px">${fmtNum(c1)}</div>
              ${clicksDelta ? `<div style="margin-top:2px">${clicksDelta}</div>` : ''}
            </div>
            <div style="text-align:center">
              <div style="color:#111827;font-size:14px">${fmtNum(i1)}</div>
              ${imprDelta ? `<div style="margin-top:2px">${imprDelta}</div>` : ''}
            </div>
          </div>`;
        }).join('');
        
        return head + body;
      };
      
      const kwEl = container.querySelector('#po-topkeywords');
      const urlEl = container.querySelector('#po-topurls');
      
      if (kwEl && topK.length > 0) {
        kwEl.innerHTML = buildTable(topK, true);
        console.log('✅ Tabla Queries renderizada con', topK.length, 'elementos');
      } else if (kwEl) {
        kwEl.innerHTML = '<div style="padding:16px;text-align:center;color:#6b7280">No hay datos de queries disponibles</div>';
      }
      
      if (urlEl && topU.length > 0) {
        urlEl.innerHTML = buildTable(topU, false);
        console.log('✅ Tabla Pages renderizada con', topU.length, 'elementos');
      } else if (urlEl) {
        urlEl.innerHTML = '<div style="padding:16px;text-align:center;color:#6b7280">No hay datos de páginas disponibles</div>';
      }
      
    } catch(err) { 
      console.error('❌ Error rendering Top lists:', err);
      console.log('🔍 currentData structure:', window.currentData);
    }

    // Mapa de índices de tendencias ya calculado arriba

    // Actualizar indicadores minimalistas con P1, P2 y delta si hay comparación
    const sum = (arr)=>arr.reduce((a,b)=>a+(b||0),0);
    const avg = (arr)=> arr.length ? (arr.reduce((a,b)=>a+(b||0),0)/arr.length) : 0;
    const tClicks = sum(clicks);
    const tImpr = sum(impressions);
    const tCtr = tImpr>0 ? (tClicks/tImpr)*100 : 0;
    const tPos = avg(position);
    const tClicksC = sum(clicksComp);
    const tImprC = sum(impressionsComp);
    const tCtrC = tImprC>0 ? (tClicksC/tImprC)*100 : 0;
    const tPosC = avg(positionComp);
    const updateMetricBlock = (key, labelFormatter, isPercentDelta=false, isPosition=false)=>{
      const root = container.querySelector(`.po-metric[data-k="${key}"]`);
      if(!root) {
        console.warn(`⚠️ No se encontró elemento .po-metric[data-k="${key}"]`);
        return;
      }
      const p1 = root.querySelector('.po-p1');
      const p2 = root.querySelector('.po-p2');
      const dEl = root.querySelector('.po-delta');
      
      console.log(`🔍 Actualizando métrica ${key}:`, {
        found: !!root,
        hasP1: !!p1,
        hasP2: !!p2,
        hasDelta: !!dEl
      });
      let v1, v2;
      if(key==='clicks'){ v1=tClicks; v2=tClicksC; }
      else if(key==='impressions'){ v1=tImpr; v2=tImprC; }
      else if(key==='ctr'){ v1=tCtr; v2=tCtrC; }
      else { v1=tPos; v2=tPosC; }

      const formatVal = (v)=>{
        if(key==='ctr') return `${(v||0).toFixed(2)}%`;
        if(key==='position') return (v||0).toFixed(2);
        return formatNumberIntl(v||0);
      };
      const formatDateRange = ()=>{
        try{
          const ds = window.dateSelector;
          const fmt=(d)=>`${String(d.getDate()).padStart(2,'0')}/${String(d.getMonth()+1).padStart(2,'0')}/${d.getFullYear()}`;
          const cur = ds?.currentPeriod; const comp = ds?.comparisonPeriod;
          const p1Label = (cur?.startDate && cur?.endDate) ? `${fmt(cur.startDate)} - ${fmt(cur.endDate)}` : 'Periodo actual';
          const p2Label = (comp?.startDate && comp?.endDate) ? `${fmt(comp.startDate)} - ${fmt(comp.endDate)}` : 'Periodo anterior';
          return { p1Label, p2Label };
        }catch(_){ return { p1Label:'Periodo actual', p2Label:'Periodo anterior' }; }
      };
      const { p1Label, p2Label } = formatDateRange();

      if(p1) p1.innerHTML = `<span class="po-date">${p1Label}</span> · <strong class="po-value-strong">${formatVal(v1)}</strong>`;
      if(p2) p2.innerHTML = rowsComp.length ? `<span class="po-date">${p2Label}</span> · <span class="po-value-small">${formatVal(v2)}</span>` : '';

      if(dEl){
        if(rowsComp.length){
          let delta;
          if(isPosition){ delta = (v1 - v2); }
          else if(isPercentDelta){ delta = ((v1 - (v2||1)) / (v2||1)) * 100; }
          else { delta = (v1 - v2); }
          const good = isPosition ? (delta < 0) : (delta >= 0);
          dEl.style.color = good ? '#16a34a' : '#dc2626';
          dEl.textContent = isPosition ? `${delta.toFixed(2)}` : (key==='ctr' ? `${delta.toFixed(2)}%` : `${delta.toFixed(0)}%`);
        } else {
          dEl.textContent = '';
        }
      }
    };

    // ✅ MEJORADO: Logging para debuggear las métricas
    console.log('📊 Actualizando métricas de Overview:', {
      clicks: tClicks,
      impressions: tImpr,
      ctr: tCtr.toFixed(2) + '%',
      position: tPos.toFixed(2),
      hasComparison: rowsComp.length > 0
    });
    
    updateMetricBlock('clicks', formatNumberIntl, true, false);
    updateMetricBlock('impressions', formatNumberIntl, true, false);
    updateMetricBlock('ctr', (v)=>`${v.toFixed(2)}%`, false, false);
    updateMetricBlock('position', (v)=>v.toFixed(2), false, true);
    
    console.log('✅ Métricas de Overview actualizadas');
  };

  // Eventos de toggles
  container.querySelectorAll('#po-top-toggles .po-btn[data-k]').forEach(btn=>{
    btn.addEventListener('click', ()=>{
      const k = btn.getAttribute('data-k');
      state.show[k] = !state.show[k];
      localStorage.setItem('po_toggles', JSON.stringify(state.show));
      syncButtons();
      if(container._chart){
        const mapIndex = { clicks:0, impressions:1, ctr:2, position:3 };
        const idx = mapIndex[k];
        container._chart.data.datasets[idx].hidden = !state.show[k];
        // También ocultar/mostrar comparativas si existen (mismo orden +4)
        if(container._chart.data.datasets[idx+4]){
          container._chart.data.datasets[idx+4].hidden = !state.show[k];
        }
        container._chart.update('none');
      }
    });
  });

  // Botones de tendencia: alternan visibilidad de datasets finales
  container.querySelectorAll('#po-top-toggles .po-trend-btn').forEach(btn=>{
    btn.addEventListener('click', ()=>{
      const which = btn.getAttribute('data-trend');
      if(!container._chart) return;
      const mapIndex = container._trendIndexMap || {};
      const idx = mapIndex[which];
      if(typeof idx !== 'number'){
        console.warn('⚠️ Trend index no disponible para', which, mapIndex);
        return;
      }
      const ds = container._chart.data.datasets[idx];
      if(!ds){
        console.warn('⚠️ Dataset de tendencia no encontrado en índice', idx);
        return;
      }
      ds.hidden = !ds.hidden;
      btn.classList.toggle('active', !ds.hidden);
      // Atenuar relleno y línea de la métrica correspondiente cuando la tendencia esté visible
      const baseIndex = (container._baseIndexMap||{})[which];
      if(typeof baseIndex === 'number'){
        const baseDs = container._chart.data.datasets[baseIndex];
        const factor = ds.hidden ? 1 : 0.5; // 0.5 con tendencia
        const color = baseDs.borderColor;
        const gradFn = container._makeGrad;
        const toRgba1 = container._ensureRgba1 || ((x)=>x);
        if (typeof gradFn === 'function') {
          const rgba = toRgba1(color);
          baseDs.backgroundColor = (ctx)=> gradFn(rgba, factor);
        }
        // También atenuar la opacidad de la línea
        const baseRgba = toRgba1(color);
        baseDs.borderColor = baseRgba.replace(/rgba\(([^)]+),\s*([01](?:\.\d+)?)\)/, 'rgba($1,'+factor+')');
        baseDs.borderWidth = ds.hidden ? baseDs.borderWidth : (baseDs.borderWidth || 2);
      }
      console.log('🔀 Trend toggle', { which, index: idx, nowHidden: ds.hidden });
      container._chart.update('none');
    });
  });

  // invert position eliminado

  // ✅ NUEVO: Función para actualizar solo las tablas Top 10
  const updateTopTables = () => {
    try {
      const cd = window.currentData || {};
      console.log('🔄 Actualizando tablas Top 10 con currentData:', !!cd);
      
      const hasComp = !!(cd.periods && cd.periods.has_comparison);
      
      // Obtener keywords con más opciones de acceso
      let kwords = [];
      if (Array.isArray(cd.keyword_comparison_data)) {
        kwords = cd.keyword_comparison_data.slice();
      } else if (Array.isArray(cd.keywords)) {
        kwords = cd.keywords.slice();
      } else if (Array.isArray(cd.keywordStats)) {
        kwords = cd.keywordStats.slice();
      }
      
      // Obtener páginas
      let pagesList = [];
      if (Array.isArray(cd.pages)) {
        pagesList = cd.pages.slice();
      }
      
      if (kwords.length === 0 && pagesList.length === 0) {
        console.log('⚠️ No hay datos para tablas Top 10 en updateTopTables');
        return;
      }
      
      // ✅ DEBUG: Mostrar estructura de datos en updateTopTables
      if (kwords.length > 0) {
        console.log('🔍 DEBUG updateTopTables: Primer elemento de keywords:', kwords[0]);
      }
      if (pagesList.length > 0) {
        console.log('🔍 DEBUG updateTopTables: Primer elemento de pages:', pagesList[0]);
      }
      
      // Función de ordenamiento más robusta
      const sortByClicks = (a, b) => {
        const aClicks = a.clicks_m1 ?? a.clicks_p1 ?? a.Clicks ?? a.clicks ?? 
                       (a.Metrics && a.Metrics[0] && a.Metrics[0].Clicks) ?? 0;
        const bClicks = b.clicks_m1 ?? b.clicks_p1 ?? b.Clicks ?? b.clicks ?? 
                       (b.Metrics && b.Metrics[0] && b.Metrics[0].Clicks) ?? 0;
        return bClicks - aClicks;
      };
      
      const topK = kwords.sort(sortByClicks).slice(0, 10);
      const topU = pagesList.sort(sortByClicks).slice(0, 10);
      
      const fmtNum = (n) => {
        try { return (n ?? 0).toLocaleString('es-ES'); } catch(_) { return String(n ?? 0); } 
      };
      const fmtCtr = (n) => `${(n ?? 0).toFixed(2)}%`;
      const fmtPos = (n) => (n == null ? '' : (n).toFixed(2));
      
      const deltaChip = (cur, prev, positiveIsGood = true) => {
        if (!hasComp) return '';
        if (prev == null || prev === 0) return `<span style="font-size:12px;color:#6b7280">New</span>`;
        const val = ((cur - prev) / prev) * 100;
        const good = positiveIsGood ? (val >= 0) : (val < 0);
        const col = good ? '#16a34a' : '#dc2626';
        const sign = val > 0 ? '+' : '';
        return `<span style="font-size:12px;color:${col}">${sign}${val.toFixed(0)}%</span>`;
      };
      
      // ✅ SIMPLIFICADO: Solo clicks e impressions con deltas como en el ejemplo
      const buildTable = (rows, isKeyword = true) => {
        if (!rows || rows.length === 0) {
          return `<div style="padding:16px;text-align:center;color:#6b7280;font-style:italic">No hay datos disponibles</div>`;
        }
        
        // Simplificado: solo name, clicks, impressions
        const cols = '1fr 120px 120px';
        const head = `<div style="display:grid;grid-template-columns:${cols};gap:12px;padding:8px 12px;border-bottom:1px solid #f3f4f6;color:#6b7280;font-size:12px;font-weight:500">
          <div>${isKeyword ? 'Query' : 'Page'}</div>
          <div style="text-align:center">Clicks</div>
          <div style="text-align:center">Impressions</div>
        </div>`;
        
        const body = rows.map((r, index) => {
          const name = isKeyword ? 
            (r.keyword || r.query || r.Query || '') : 
            (r.url || r.page || r.URL || r.Page || '');
            
          // ✅ MEJORADO: Acceso más robusto a métricas incluyendo estructura Metrics[]
          const getMetric = (item, metricName) => {
            // Intentar propiedades directas primero
            const direct = item[`${metricName}_m1`] ?? item[`${metricName}_p1`] ?? 
                          item[metricName.charAt(0).toUpperCase() + metricName.slice(1)] ?? 
                          item[metricName];
            if (direct !== undefined) return direct;
            
            // Intentar estructura anidada Metrics[]
            if (item.Metrics && Array.isArray(item.Metrics) && item.Metrics[0]) {
              return item.Metrics[0][metricName.charAt(0).toUpperCase() + metricName.slice(1)] ?? 0;
            }
            
            return 0;
          };
          
          const c1 = getMetric(r, 'clicks');
          const c2 = r.clicks_m2 ?? r.clicks_p2 ?? (r.Metrics && r.Metrics[1] && r.Metrics[1].Clicks) ?? 0;
          const i1 = getMetric(r, 'impressions');
          const i2 = r.impressions_m2 ?? r.impressions_p2 ?? (r.Metrics && r.Metrics[1] && r.Metrics[1].Impressions) ?? 0;
          
          // Log para debugging del primer elemento
          if (index === 0) {
            console.log(`🔍 DEBUG buildTable ${isKeyword ? 'keyword' : 'page'}:`, {
              name,
              clicks: c1,
              impressions: i1,
              originalData: r
            });
          }
          
          // Calcular deltas para clicks e impressions
          const clicksDelta = hasComp && c2 > 0 ? deltaChip(c1, c2, true) : '';
          const imprDelta = hasComp && i2 > 0 ? deltaChip(i1, i2, true) : '';
          
          return `<div style="display:grid;grid-template-columns:${cols};gap:12px;padding:10px 12px;border-bottom:1px solid #f9fafb;align-items:center">
            <div style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#111827;font-size:13px" title="${name}">${name}</div>
            <div style="text-align:center">
              <div style="font-weight:600;color:#111827;font-size:14px">${fmtNum(c1)}</div>
              ${clicksDelta ? `<div style="margin-top:2px">${clicksDelta}</div>` : ''}
            </div>
            <div style="text-align:center">
              <div style="color:#111827;font-size:14px">${fmtNum(i1)}</div>
              ${imprDelta ? `<div style="margin-top:2px">${imprDelta}</div>` : ''}
            </div>
          </div>`;
        }).join('');
        
        return head + body;
      };
      
      const kwEl = container.querySelector('#po-topkeywords');
      const urlEl = container.querySelector('#po-topurls');
      
      if (kwEl && topK.length > 0) {
        kwEl.innerHTML = buildTable(topK, true);
        console.log('✅ Tabla Queries actualizada en updateTopTables con', topK.length, 'elementos');
      } else if (kwEl) {
        kwEl.innerHTML = '<div style="padding:16px;text-align:center;color:#6b7280">No hay datos de queries disponibles</div>';
      }
      
      if (urlEl && topU.length > 0) {
        urlEl.innerHTML = buildTable(topU, false);
        console.log('✅ Tabla Pages actualizada en updateTopTables con', topU.length, 'elementos');
      } else if (urlEl) {
        urlEl.innerHTML = '<div style="padding:16px;text-align:center;color:#6b7280">No hay datos de páginas disponibles</div>';
      }
      
    } catch(err) { 
      console.error('❌ Error en updateTopTables:', err);
    }
  };
  
  // ✅ NUEVO: Escuchar cambios en window.currentData
  let currentDataWatcher;
  const watchCurrentData = () => {
    if (currentDataWatcher) clearInterval(currentDataWatcher);
    
    let lastDataHash = '';
    currentDataWatcher = setInterval(() => {
      const cd = window.currentData;
      if (cd) {
        // Crear un hash simple de los datos para detectar cambios
        const dataString = JSON.stringify({
          keywordCount: cd.keyword_comparison_data?.length || cd.keywords?.length || 0,
          pagesCount: cd.pages?.length || 0,
          hasComparison: !!(cd.periods && cd.periods.has_comparison)
        });
        
        if (dataString !== lastDataHash && dataString !== '{"keywordCount":0,"pagesCount":0,"hasComparison":false}') {
          lastDataHash = dataString;
          console.log('🔄 Detectado cambio en currentData, actualizando tablas');
          updateTopTables();
        }
      }
    }, 1000);
    
    // Limpiar después de 30 segundos
    setTimeout(() => {
      if (currentDataWatcher) {
        clearInterval(currentDataWatcher);
        currentDataWatcher = null;
      }
    }, 30000);
  };
  
  // Iniciar el watcher
  watchCurrentData();

  // Reaccionar a cambios del selector de fechas
  const applyBtn = document.getElementById('modalApplyBtn');
  if(applyBtn){ 
    applyBtn.addEventListener('click', () => {
      fetchAndRender();
      // Reiniciar watcher después de nueva consulta
      setTimeout(watchCurrentData, 2000);
    }); 
  }
  // Reaccionar a cambios de propiedad
  const siteSelectEl = document.getElementById('siteUrlSelect');
  if(siteSelectEl){ 
    siteSelectEl.addEventListener('change', () => {
      fetchAndRender();
      // Reiniciar watcher después de nueva consulta
      setTimeout(watchCurrentData, 2000);
    }); 
  }

  // ✅ MEJORADO: Función para verificar estado del container
  const checkContainerState = () => {
    const metricsEl = container.querySelector('#po-metrics');
    const clicksEl = container.querySelector('.po-metric[data-k="clicks"]');
    console.log('🔍 Estado del container:', {
      hasMetrics: !!metricsEl,
      hasClicksMetric: !!clicksEl,
      containerId: container.id,
      containerChildren: container.children.length
    });
  };
  
  // Primera carga (con reintento breve hasta que haya fechas y siteUrl)
  let tries=0; 
  const timer = setInterval(()=>{ 
    tries++; 
    console.log(`🔄 Intento ${tries}/10 de cargar gráfico Chart.js`);
    checkContainerState();
    fetchAndRender(); 
    if(tries>10) {
      clearInterval(timer);
      console.log('⚠️ Máximo de intentos alcanzado para Chart.js');
    }
  }, 800);
}


