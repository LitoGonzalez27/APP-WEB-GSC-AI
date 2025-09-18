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
  const Recharts = await ensureRecharts();
  if (!Recharts) {
    // Fallback inmediato a Chart.js
    return mountChartJSOverview(rootId, fetchUrl);
  }
  await ensureReact();
  const React = window.React;
  const ReactDOM = window.ReactDOM;
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


// ==============================
// Fallback Chart.js (sin React)
// ==============================
function formatNumberIntl(n){try{return (n??0).toLocaleString()}catch(_){return String(n??0)}}

async function mountChartJSOverview(rootId, fetchUrl){
  const container = document.getElementById(rootId);
  if(!container) return;

  // Ocultar bloque antiguo
  try{const d=document.getElementById('summaryDisclaimer'); if(d) d.style.display='none';}catch(_){}

  // UI básica
  container.innerHTML = `
    <div id=\"po-metrics\" style=\"display:flex;gap:18px;align-items:center;margin:2px 0 10px 0;flex-wrap:wrap;font-size:13px;color:#111827\">
      <div class=\"po-metric\" data-k=\"clicks\" style=\"display:flex;gap:6px;align-items:center\">
        <i class=\"fas fa-mouse-pointer\" style=\"color:#2563eb\"></i>
        <span style=\"font-weight:600\">Clicks</span>
        <span class=\"po-value\" aria-label=\"clicks value\">–</span>
        <span class=\"po-delta\" aria-label=\"clicks delta\" style=\"font-size:12px;color:#059669\"> </span>
      </div>
      <div class=\"po-metric\" data-k=\"impressions\" style=\"display:flex;gap:6px;align-items:center\">
        <i class=\"fas fa-eye\" style=\"color:#10b981\"></i>
        <span style=\"font-weight:600\">Impr.</span>
        <span class=\"po-value\" aria-label=\"impressions value\">–</span>
        <span class=\"po-delta\" aria-label=\"impressions delta\" style=\"font-size:12px;color:#059669\"> </span>
      </div>
      <div class=\"po-metric\" data-k=\"ctr\" style=\"display:flex;gap:6px;align-items:center\">
        <i class=\"fas fa-percentage\" style=\"color:#f59e0b\"></i>
        <span style=\"font-weight:600\">CTR</span>
        <span class=\"po-value\" aria-label=\"ctr value\">–</span>
        <span class=\"po-delta\" aria-label=\"ctr delta\" style=\"font-size:12px;color:#059669\"> </span>
      </div>
      <div class=\"po-metric\" data-k=\"position\" style=\"display:flex;gap:6px;align-items:center\">
        <i class=\"fas fa-location-arrow\" style=\"color:#ef4444\"></i>
        <span style=\"font-weight:600\">Pos.</span>
        <span class=\"po-value\" aria-label=\"position value\">–</span>
        <span class=\"po-delta\" aria-label=\"position delta\" style=\"font-size:12px;color:#059669\"> </span>
      </div>
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px" id="po-top-toggles">
      <button type="button" data-k="clicks" class="po-btn">Clicks</button>
      <button type="button" data-k="impressions" class="po-btn">Impressions</button>
      <button type="button" data-k="ctr" class="po-btn">CTR</button>
      <button type="button" data-k="position" class="po-btn">Avg. Position</button>
      <button type="button" id="po-invert" class="po-btn">Invert position</button>
      <style>
        .po-btn{padding:6px 10px;border-radius:6px;border:1px solid #d1d5db;background:#fff;color:#111827;cursor:pointer}
        .po-btn.active{background:#161616;color:#D8F9B8;border-color:#161616}
      </style>
    </div>
    <div style="width:100%;height:320px"><canvas id="po-canvas" aria-label="Performance Overview Chart" role="img"></canvas></div>
  `;

  const savedToggles = JSON.parse(localStorage.getItem('po_toggles')||'{}');
  const state = { 
    show: { clicks: savedToggles.clicks!==false, impressions: savedToggles.impressions||false, ctr: savedToggles.ctr||false, position: savedToggles.position||false },
    invert: localStorage.getItem('po_invert_pos')==='1'
  };

  const syncButtons = ()=>{
    container.querySelectorAll('#po-top-toggles .po-btn[data-k]').forEach(btn=>{
      const k = btn.getAttribute('data-k');
      btn.classList.toggle('active', !!state.show[k]);
    });
    container.querySelector('#po-invert')?.classList.toggle('active', !!state.invert);
  };

  syncButtons();

  const ctx = container.querySelector('#po-canvas');
  if(!ctx || !window.Chart){
    console.warn('Chart.js no está disponible');
    return;
  }

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
    if(!r || !r.start || !r.end || !s) return;
    const url = buildFetchUrl(fetchUrl, r.start, r.end, s);
    let rows=[];
    try{
      const resp = await fetch(url);
      rows = await resp.json();
    }catch(e){ console.warn('No se pudo cargar /api/gsc/performance', e); return; }

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
    const makeGrad = (hex)=>{
      const g = ctx2.createLinearGradient(0, ctx.height, 0, 0);
      g.addColorStop(0, 'rgba(255,255,255,0.0)');
      g.addColorStop(0.9, hex.replace('1)', '0.25)').replace('rgb(', 'rgba('));
      g.addColorStop(1, hex);
      return g;
    };
    // Colores base en rgba fuertes para líneas
    const colClicks = 'rgba(37,99,235,1)';
    const colImpr = 'rgba(16,185,129,1)';
    const colCtr = 'rgba(245,158,11,1)';
    const colPos = 'rgba(239,68,68,1)';

    container._chart = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {label:'Clicks', data:clicks, borderColor:colClicks, backgroundColor:makeGrad('rgba(37,99,235,1)'), fill:true, yAxisID:'y', hidden: !state.show.clicks, pointRadius:0, tension:0.25},
          {label:'Impressions', data:impressions, borderColor:colImpr, backgroundColor:makeGrad('rgba(16,185,129,1)'), fill:true, yAxisID:'y1', hidden: !state.show.impressions, pointRadius:0, tension:0.25},
          {label:'CTR (%)', data:ctr, borderColor:colCtr, backgroundColor:makeGrad('rgba(245,158,11,1)'), fill:true, yAxisID:'y2', hidden: !state.show.ctr, pointRadius:0, tension:0.25},
          {label:'Avg. Position', data:position, borderColor:colPos, backgroundColor:makeGrad('rgba(239,68,68,1)'), fill:true, yAxisID:'y3', hidden: !state.show.position, pointRadius:0, tension:0.25}
          // Periodo comparado (solo líneas punteadas, sin fill)
          , ...(rowsComp.length ? [
            {label:'Clicks (comp)', data:clicksComp, borderColor:colClicks, fill:false, yAxisID:'y', hidden: !state.show.clicks, pointRadius:0, tension:0.25, borderDash:[5,5], borderWidth:2, backgroundColor:'transparent'},
            {label:'Impressions (comp)', data:impressionsComp, borderColor:colImpr, fill:false, yAxisID:'y1', hidden: !state.show.impressions, pointRadius:0, tension:0.25, borderDash:[5,5], borderWidth:2, backgroundColor:'transparent'},
            {label:'CTR (comp) %', data:ctrComp, borderColor:colCtr, fill:false, yAxisID:'y2', hidden: !state.show.ctr, pointRadius:0, tension:0.25, borderDash:[5,5], borderWidth:2, backgroundColor:'transparent'},
            {label:'Position (comp)', data:positionComp, borderColor:colPos, fill:false, yAxisID:'y3', hidden: !state.show.position, pointRadius:0, tension:0.25, borderDash:[5,5], borderWidth:2, backgroundColor:'transparent'}
          ] : [])
        ]
      },
      options: {
        responsive:true,
        maintainAspectRatio:false,
        animation:false,
        plugins:{ legend:{ display:false }, tooltip:{ enabled:false, mode:'index', intersect:false, external: externalTooltip } },
        scales:{
          y:{ position:'left', ticks:{ callback:(v)=>formatNumberIntl(v) }},
          y1:{ position:'right', reverse: !!state.invert, grid:{ drawOnChartArea:false }, ticks:{ callback:(v)=>formatNumberIntl(v) }},
          // Ejes internos no visibles para escalado dinámico
          y2:{ display:false, suggestedMin: 0, suggestedMax: Math.max(10, Math.ceil(Math.max(...ctr) * 1.2)) },
          y3:{ display:false, suggestedMin: 0, suggestedMax: 20 },
          x:{ ticks:{ maxTicksLimit: 10 } }
        },
        hover: hoverStyle,
        elements: { point: { radius: 0, hoverRadius: 4, hitRadius: 6 } }
      }
    });

    // Actualizar indicadores minimalistas con deltas si hay comparación
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
    const setMetric = (k, val, delta)=>{
      const root = container.querySelector(`.po-metric[data-k="${k}"]`) || container.querySelector(`[data-k="${k}"]`);
      const vEl = container.querySelector(`.po-metric[data-k="${k}"] .po-value`);
      const dEl = container.querySelector(`.po-metric[data-k="${k}"] .po-delta`);
      if(vEl) vEl.textContent = k==='ctr' ? `${val.toFixed(2)}%` : (k==='position' ? val.toFixed(2) : formatNumberIntl(val));
      if(dEl){
        if(isFinite(delta)){
          const up = delta >= 0; dEl.style.color = up ? '#16a34a' : '#dc2626';
          dEl.textContent = (k==='position') ? `${(delta).toFixed(2)}` : `${(delta).toFixed(2)}%`;
        }else{
          dEl.textContent = '';
        }
      }
    };

    setMetric('clicks', tClicks, rowsComp.length? ((tClicks - tClicksC) / (tClicksC||1))*100 : NaN);
    setMetric('impressions', tImpr, rowsComp.length? ((tImpr - tImprC) / (tImprC||1))*100 : NaN);
    setMetric('ctr', tCtr, rowsComp.length? (tCtr - tCtrC) : NaN);
    setMetric('position', tPos, rowsComp.length? (tPos - tPosC) : NaN);
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

  container.querySelector('#po-invert')?.addEventListener('click', ()=>{
    state.invert = !state.invert;
    localStorage.setItem('po_invert_pos', state.invert ? '1' : '0');
    syncButtons();
    if(container._chart){
      container._chart.options.scales.y1.reverse = !!state.invert;
      container._chart.update('none');
    }
  });

  // Reaccionar a cambios del selector de fechas
  const applyBtn = document.getElementById('modalApplyBtn');
  if(applyBtn){ applyBtn.addEventListener('click', fetchAndRender); }
  // Reaccionar a cambios de propiedad
  const siteSelectEl = document.getElementById('siteUrlSelect');
  if(siteSelectEl){ siteSelectEl.addEventListener('change', fetchAndRender); }

  // Primera carga (con reintento breve hasta que haya fechas y siteUrl)
  let tries=0; const timer = setInterval(()=>{ tries++; fetchAndRender(); if(tries>10) clearInterval(timer); }, 800);
}


