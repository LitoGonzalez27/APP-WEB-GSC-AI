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
  if (window.Recharts) return window.Recharts;
  await loadScript('https://unpkg.com/recharts@2.12.7/umd/Recharts.min.js');
  return window.Recharts;
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

function buildFetchUrl(base, start, end, siteUrl) {
  const u = new URL(base, window.location.origin);
  u.searchParams.set('start', start);
  u.searchParams.set('end', end);
  if (siteUrl) u.searchParams.set('siteUrl', siteUrl);
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
  await ensureReact();
  const React = window.React;
  const ReactDOM = window.ReactDOM;
  const Recharts = await ensureRecharts();
  const Lucide = await ensureLucide();

  const { useMemo, useState, useEffect } = React;
  const {
    ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  } = Recharts;

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
    const [invertPosition, setInvertPosition] = useState(() => localStorage.getItem('po_invert_pos') === '1');

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
          const normalized = (rows || []).map((p) => ({ ...p, ctr: normalizeCtrValue(p.ctr) }));
          setData(normalized);
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
        ToggleButton({ active: show.position, onClick: () => setShow((s)=>{const n={ ...s, position: !s.position }; localStorage.setItem('po_toggles', JSON.stringify(n)); return n; }), title: 'Avg. Position', Icon: (window.lucideReact?.MapPin || null) }),
        ToggleButton({ active: invertPosition, onClick: ()=>{ const v=!invertPosition; setInvertPosition(v); localStorage.setItem('po_invert_pos', v?'1':'0'); }, title: 'Invert position', Icon: (window.lucideReact?.ArrowUpDown || null) }),
      ),
      // Cabecera de totales
      React.createElement('div', { style: { display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: 13, color: '#111827' } },
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
            React.createElement(YAxis, { yAxisId: 'right', orientation: 'right', domain: yRightDomain, reversed: invertPosition }),
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
    // Ocultar contenido previo del bloque Performance Overview (disclaimer/placeholder)
    try {
      const disclaimer = document.getElementById('summaryDisclaimer');
      if (disclaimer) disclaimer.style.display = 'none';
    } catch (_) {}

    const root = window.ReactDOM.createRoot(rootEl);
    root.render(window.React.createElement(Overview));
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


