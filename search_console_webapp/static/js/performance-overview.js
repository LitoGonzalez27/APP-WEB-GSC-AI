// performance-overview.js - Chart.js v4 Overview (usando Chart global del CDN)

function numberFormatInteger(v) {
  return new Intl.NumberFormat().format(Math.round(Number(v) || 0));
}

function formatShortNumber(v) {
  const n = Number(v) || 0;
  const abs = Math.abs(n);
  if (abs >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M';
  if (abs >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, '') + 'k';
  return String(Math.round(n));
}

function toPercentage(v) {
  const num = Number(v) || 0;
  return num <= 1 ? num * 100 : num;
}

const COLORS = {
  clicks: '#2563eb',
  impressions: '#16a34a',
  ctr: '#f59e0b',
  position: '#ef4444',
  compare: '#64748b'
};

function linearRegression(values) {
  const xs = values.map((_, i) => i);
  const n = values.length || 1;
  const sumX = xs.reduce((s, v) => s + v, 0);
  const sumY = values.reduce((s, v) => s + (Number(v) || 0), 0);
  const sumXY = xs.reduce((s, x, i) => s + x * (Number(values[i]) || 0), 0);
  const sumX2 = xs.reduce((s, x) => s + x * x, 0);
  const denom = n * sumX2 - sumX * sumX || 1;
  const a = (n * sumXY - sumX * sumY) / denom;
  const b = (sumY - a * sumX) / n;
  return xs.map(x => a * x + b);
}

function makeGradient(ctx, canvas, color) {
  const g = ctx.createLinearGradient(0, 0, 0, canvas.height);
  g.addColorStop(0, color + '33');
  g.addColorStop(1, color + '00');
  return g;
}

function ensureRgba1(color) {
  if (typeof color !== 'string') return 'rgba(0,0,0,1)';
  if (color.startsWith('rgba(')) return color.replace(/rgba\((\s*\d+\s*,\s*\d+\s*,\s*\d+\s*),\s*[^)]+\)/, 'rgba($1,1)');
  if (color.startsWith('rgb(')) return color.replace(/rgb\(([^)]+)\)/, 'rgba($1,1)');
  // Hex (#RGB, #RRGGBB)
  if (color.startsWith('#')) {
    let hex = color.slice(1);
    if (hex.length === 3) hex = hex.split('').map(c => c + c).join('');
    const int = parseInt(hex, 16);
    const r = (int >> 16) & 255;
    const g = (int >> 8) & 255;
    const b = int & 255;
    return `rgba(${r},${g},${b},1)`;
  }
  // Fallback
  return 'rgba(0,0,0,1)';
}

function makeGradDim(ctx, canvas, rgba1, dim) {
  const clamp = (v) => Math.max(0, Math.min(1, v));
  const withAlpha = (a) => rgba1.replace(/rgba\(([^)]+),\s*([01](?:\.\d+)?)\)/, 'rgba($1,' + clamp(a) + ')');
  const g = ctx.createLinearGradient(0, canvas.height, 0, 0);
  // Suavizar el degradado ~25% para un look más elegante
  const aLight = 0.06 * dim;
  const aMedium = 0.16 * dim;
  const aStrong = 0.30 * dim;
  g.addColorStop(0.00, withAlpha(aLight));
  g.addColorStop(0.35, withAlpha(aLight));
  g.addColorStop(0.70, withAlpha(aMedium));
  g.addColorStop(1.00, withAlpha(aStrong));
  return g;
}

function buildSeries(rows, metric) {
  if (!Array.isArray(rows)) return [];
  switch (metric) {
    case 'ctr': return rows.map(d => toPercentage(d.ctr));
    case 'position': return rows.map(d => d.position);
    case 'impressions': return rows.map(d => d.impressions);
    case 'clicks':
    default: return rows.map(d => d.clicks);
  }
}

function normalizePoints(arr) {
  return (arr || []).map(d => ({
    date: d.date,
    clicks: Number(d.clicks) || 0,
    impressions: Number(d.impressions) || 0,
    ctr: (Number(d.ctr) || 0) <= 1 ? (Number(d.ctr) || 0) : (Number(d.ctr) || 0) / 100,
    position: typeof d.position === 'number' ? d.position : Number(d.position) || 0
  }));
}

function buildTooltipLabel(metric, value) {
  if (metric === 'ctr') return `${Number(value).toFixed(2)}%`;
  if (metric === 'position') return Number(value).toFixed(2);
  return numberFormatInteger(value);
}

export async function mountChartJSOverview(rootId, fetchUrlOrData) {
  const container = document.getElementById(rootId) || document.getElementById('performanceOverview');
  if (!container) return;

  // Inyectar estilos de botones si no existen
  try {
    let style = document.getElementById('po-style-core');
    if (!style) {
      style = document.createElement('style');
      style.id = 'po-style-core';
      style.textContent = `
        .po-btn{padding:6px 10px;border-radius:6px;border:1px solid #d1d5db;background:#fff;color:#111827;cursor:pointer}
        .po-btn.active{background:#161616;color:#D8F9B8;border-color:#161616}
        .po-trend-btn{border-style:dashed}
        #po-metrics .po-lines .po-date{font-size:12px;color:#6b7280}
        #po-metrics .po-lines .po-value-strong{font-size:15px;color:#111827}
        #po-metrics .po-lines .po-value-small{font-size:12px;color:#374151;opacity:0.85}
      `;
      document.head.appendChild(style);
    }
  } catch(_) {}

  // Reconstruir UI al estilo referencia (KPIs + toggles + canvas)
  container.innerHTML = `
    <div id="po-metrics" style="display:flex;gap:22px;align-items:flex-start;justify-content:space-evenly;margin:2px 0 20px 0;flex-wrap:wrap;font-size:16px;color:#111827">
      <div class="po-metric" data-k="clicks" style="display:flex;gap:10px;align-items:flex-start"><i class="fas fa-mouse-pointer" style="color:#2563eb;font-size:18px;margin-top:2px"></i><div><div style="font-weight:600">Clicks</div><div class="po-lines" style="display:flex;flex-direction:column;gap:2px;font-size:13px;color:#374151"><div class="po-p1"></div><div class="po-p2"></div><div class="po-delta" style="font-size:13px"></div></div></div></div>
      <div class="po-metric" data-k="impressions" style="display:flex;gap:10px;align-items:flex-start"><i class="fas fa-eye" style="color:#10b981;font-size:18px;margin-top:2px"></i><div><div style="font-weight:600">Impr.</div><div class="po-lines" style="display:flex;flex-direction:column;gap:2px;font-size:13px;color:#374151"><div class="po-p1"></div><div class="po-p2"></div><div class="po-delta" style="font-size:13px"></div></div></div></div>
      <div class="po-metric" data-k="ctr" style="display:flex;gap:10px;align-items:flex-start"><i class="fas fa-percentage" style="color:#f59e0b;font-size:18px;margin-top:2px"></i><div><div style="font-weight:600">CTR</div><div class="po-lines" style="display:flex;flex-direction:column;gap:2px;font-size:13px;color:#374151"><div class="po-p1"></div><div class="po-p2"></div><div class="po-delta" style="font-size:13px"></div></div></div></div>
      <div class="po-metric" data-k="position" style="display:flex;gap:10px;align-items:flex-start"><i class="fas fa-location-arrow" style="color:#ef4444;font-size:18px;margin-top:2px"></i><div><div style="font-weight:600">Pos.</div><div class="po-lines" style="display:flex;flex-direction:column;gap:2px;font-size:13px;color:#374151"><div class="po-p1"></div><div class="po-p2"></div><div class="po-delta" style="font-size:13px"></div></div></div></div>
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;align-items:center;justify-content:space-between" id="po-top-toggles">
      <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
        <button type="button" data-k="clicks" class="po-btn">Clicks</button>
        <button type="button" data-k="impressions" class="po-btn">Impressions</button>
        <button type="button" data-k="ctr" class="po-btn">CTR</button>
        <button type="button" data-k="position" class="po-btn">Avg. Position</button>
      </div>
      <div id="po-trend-controls" style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
        <button type="button" data-trend="clicks" class="po-btn po-trend-btn">Trend clicks</button>
        <button type="button" data-trend="impressions" class="po-btn po-trend-btn">Trend impressions</button>
        <button type="button" data-trend="ctr" class="po-btn po-trend-btn">Trend CTR</button>
        <button type="button" data-trend="position" class="po-btn po-trend-btn">Trend position</button>
      </div>
    </div>
    <div style="width:100%;height:320px"><canvas id="po-canvas" aria-label="Performance Overview Chart" role="img"></canvas></div>
  `;

  const canvas = container.querySelector('#po-canvas');
  const ctx = canvas.getContext('2d');

  // Estado de toggles (Clicks e Impressions ON por defecto como referencia)
  const saved = (()=>{ try { return JSON.parse(localStorage.getItem('po_toggles'))||{}; } catch(_) { return {}; }})();
  const state = {
    show: { clicks: saved.clicks ?? true, impressions: saved.impressions ?? true, ctr: !!saved.ctr, position: !!saved.position },
    trend: { clicks: false, impressions: false, ctr: false, position: false },
    data: { current: [], prev: [] }
  };

  function getOrCreateTooltipEl() {
    let el = container.querySelector('.po-tooltip');
    if (!el) {
      el = document.createElement('div');
      el.className = 'po-tooltip';
      el.style.cssText = [
        'position:absolute', 'pointer-events:none', 'background:#fff', 'color:#111827',
        'border-radius:10px', 'padding:10px 12px', 'box-shadow:0 8px 30px rgba(0,0,0,0.08)', 'border:1px solid #e5e7eb',
        'z-index:30', 'display:none', 'min-width:260px'
      ].join(';');
      container.style.position = container.style.position || 'relative';
      container.appendChild(el);
    }
    return el;
  }

  function formatPctDelta(cur, prev, metric) {
    if (metric === 'position') {
      if (prev === 0 && cur !== 0) return `${(cur - prev).toFixed(2)}`;
      return `${(cur - prev).toFixed(2)}`;
    }
    if (!isFinite(prev) || prev === 0) return cur > 0 ? '+∞%' : '0%';
    const pct = ((cur - prev) / prev) * 100;
    const sign = pct > 0 ? '+' : '';
    return `${sign}${pct.toFixed(0)}%`;
  }

  // Tooltip externo con doble columna (fecha actual vs fecha previa) y múltiples métricas
  function externalTooltip(context) {
    const { chart, tooltip } = context;
    const tooltipEl = getOrCreateTooltipEl();

    if (!tooltip || tooltip.opacity === 0) {
      tooltipEl.style.opacity = '0';
      return;
    }

    const dataRef = container._poTooltipData;
    if (!dataRef) { tooltipEl.style.opacity = '0'; return; }

    const i = tooltip.dataPoints?.[0]?.dataIndex ?? 0;
    const curDate = dataRef.labels[i] || '';
    const prevDate = dataRef.prevDateByLabel?.[curDate] || '';

    const fmtDate = (iso) => {
      try {
        const d = new Date(iso + 'T00:00:00');
        const wd = d.toLocaleDateString(undefined, { weekday: 'short' });
        const yr = d.getFullYear();
        const mon = d.toLocaleDateString(undefined, { month: 'short' });
        const day = String(d.getDate()).padStart(2, '0');
        return { top: `${wd} · ${yr}`, big: `${mon} ${day}` };
      } catch(_) { return { top: '', big: iso }; }
    };

    const rows = [];
    const pushRow = (name, color, curVal, prevVal, metricKey) => {
      const delta = formatPctDelta(curVal, prevVal, metricKey);
      const curFmt = metricKey==='ctr' ? `${Number(curVal).toFixed(2)}%` : (metricKey==='position' ? Number(curVal).toFixed(2) : formatShortNumber(curVal));
      const prevFmt = prevVal==null?'' : (metricKey==='ctr' ? `${Number(prevVal).toFixed(2)}%` : (metricKey==='position' ? Number(prevVal).toFixed(2) : formatShortNumber(prevVal)));
      rows.push(`
        <div style="display:flex;justify-content:space-between;align-items:center;margin:6px 0">
          <div style="display:flex;align-items:center;gap:8px">
            <span style="width:10px;height:10px;background:${color};border-radius:50%;display:inline-block"></span>
            <span style="font-weight:500">${name}</span>
          </div>
          <div style="display:flex;align-items:center;gap:10px">
            <div><strong style="font-size:14px">${curFmt}</strong> ${prevVal!=null ? `<span style=\"color:${delta.startsWith('+')?'#16a34a':(delta.startsWith('-')?'#dc2626':'#6b7280')}\">${delta}</span>` : ''}</div>
            ${prevFmt ? `<div style="min-width:64px;text-align:right;opacity:.8">${prevFmt}</div>` : ''}
          </div>
        </div>`);
    };

    if (dataRef.show.clicks) pushRow('Clicks', COLORS.clicks, dataRef.clicks[i]||0, dataRef.clicksPrevByLabel[curDate]??0, 'clicks');
    if (dataRef.show.impressions) pushRow('Impressions', COLORS.impressions, dataRef.impressions[i]||0, dataRef.impressionsPrevByLabel[curDate]??0, 'impressions');
    if (dataRef.show.ctr) pushRow('CTR', COLORS.ctr, dataRef.ctr[i]||0, dataRef.ctrPrevByLabel[curDate]??0, 'ctr');
    if (dataRef.show.position) pushRow('Avg. Position', COLORS.position, dataRef.position[i]||0, dataRef.positionPrevByLabel[curDate]??0, 'position');

    const h1 = fmtDate(curDate);
    const h2 = prevDate ? fmtDate(prevDate) : null;
    const accent = '#6366f1';
    const accent2 = '#a78bfa';
    tooltipEl.innerHTML = `
      <div style="display:flex;justify-content:space-between;gap:24px;margin-bottom:8px;align-items:flex-end">
        <div style="min-width:120px">
          <div style="font-size:12px;color:#6b7280;margin-bottom:2px">${h1.top}</div>
          <div style="font-size:18px;font-weight:700;border-bottom:2px solid ${accent};line-height:1.2">${h1.big}</div>
        </div>
        ${h2 ? `<div style=\"min-width:120px;text-align:right\"><div style=\"font-size:12px;color:#6b7280;margin-bottom:2px\">${h2.top}</div><div style=\"font-size:18px;font-weight:700;border-bottom:2px dotted ${accent2};line-height:1.2\">${h2.big}</div></div>` : ''}
      </div>
      ${rows.join('')}
    `;

    const { offsetLeft: positionX, offsetTop: positionY } = chart.canvas;
    tooltipEl.style.left = positionX + tooltip.caretX + 12 + 'px';
    tooltipEl.style.top = positionY + tooltip.caretY - tooltipEl.offsetHeight - 12 + 'px';
    tooltipEl.style.display = 'block';
  }

  function render() {
    const rows = state.data.current;
    const prev = state.data.prev || [];
    const labels = rows.map(d => d.date);

    // Mapear prev por fecha para alineación exacta
    const prevByDate = Object.create(null);
    prev.forEach(d => { prevByDate[d.date] = d; });

    const clicks = rows.map(d => d.clicks);
    const impressions = rows.map(d => d.impressions);
    const ctr = rows.map(d => toPercentage(d.ctr));
    const position = rows.map(d => d.position);

    const indexAligned = prev.length && prev.length === labels.length && prev.every((p, idx)=> p.date === labels[idx]);
    const clicksPrev = indexAligned ? prev.map(d=>d.clicks) : labels.map(l => (prevByDate[l]?.clicks) ?? 0);
    const impressionsPrev = indexAligned ? prev.map(d=>d.impressions) : labels.map(l => (prevByDate[l]?.impressions) ?? 0);
    const ctrPrev = indexAligned ? prev.map(d=>toPercentage(d.ctr||0)) : labels.map(l => toPercentage((prevByDate[l]?.ctr) ?? 0));
    const positionPrev = indexAligned ? prev.map(d=>d.position) : labels.map(l => (prevByDate[l]?.position) ?? 0);

    const trendClicks = state.trend.clicks ? linearRegression(clicks) : clicks.map(()=>null);
    const trendImpr = state.trend.impressions ? linearRegression(impressions) : impressions.map(()=>null);
    const trendCtr = state.trend.ctr ? linearRegression(ctr) : ctr.map(()=>null);
    const trendPos = state.trend.position ? linearRegression(position) : position.map(()=>null);

    // Dim de relleno cuando hay tendencia activa
    const dimClicks = state.trend.clicks ? 0.5 : 1;
    const dimImpr = state.trend.impressions ? 0.5 : 1;
    const dimCtr = state.trend.ctr ? 0.5 : 1;
    const dimPos = state.trend.position ? 0.5 : 1;

    const datasets = [
      { label:'Clicks', data:clicks, borderColor:ensureRgba1(COLORS.clicks), backgroundColor: (c)=> makeGradDim(ctx, canvas, ensureRgba1(COLORS.clicks), dimClicks), fill:'origin', pointRadius:0, tension:0.25, yAxisID:'y', hidden: !state.show.clicks, borderWidth: 2 },
      { label:'Impressions', data:impressions, borderColor:ensureRgba1(COLORS.impressions), backgroundColor: (c)=> makeGradDim(ctx, canvas, ensureRgba1(COLORS.impressions), dimImpr), fill:'origin', pointRadius:0, tension:0.25, yAxisID:'y1', hidden: !state.show.impressions, borderWidth: 2 },
      { label:'CTR (%)', data:ctr, borderColor:ensureRgba1(COLORS.ctr), backgroundColor: (c)=> makeGradDim(ctx, canvas, ensureRgba1(COLORS.ctr), dimCtr), fill:'origin', pointRadius:0, tension:0.25, yAxisID:'y2', hidden: !state.show.ctr, borderWidth: 2 },
      { label:'Avg. Position', data:position, borderColor:ensureRgba1(COLORS.position), backgroundColor: (c)=> makeGradDim(ctx, canvas, ensureRgba1(COLORS.position), dimPos), fill:'origin', pointRadius:0, tension:0.2, yAxisID:'y3', hidden: !state.show.position, borderWidth: 2 },
      // comparativas (solo si hay prev) – asegurar que al menos una serie visible
      ...(prev.length ? [
        { label:'Clicks (prev)', data:clicksPrev, borderColor:ensureRgba1(COLORS.clicks), borderDash:[6,6], borderWidth:1.5, pointRadius:0, tension:0.25, yAxisID:'y', fill:false, backgroundColor:'transparent', hidden: !state.show.clicks },
        { label:'Impressions (prev)', data:impressionsPrev, borderColor:ensureRgba1(COLORS.impressions), borderDash:[6,6], borderWidth:1.5, pointRadius:0, tension:0.25, yAxisID:'y1', fill:false, backgroundColor:'transparent', hidden: !state.show.impressions },
        { label:'CTR (prev) %', data:ctrPrev, borderColor:ensureRgba1(COLORS.ctr), borderDash:[6,6], borderWidth:1.5, pointRadius:0, tension:0.25, yAxisID:'y2', fill:false, backgroundColor:'transparent', hidden: !state.show.ctr },
        { label:'Position (prev)', data:positionPrev, borderColor:ensureRgba1(COLORS.position), borderDash:[6,6], borderWidth:1.5, pointRadius:0, tension:0.25, yAxisID:'y3', fill:false, backgroundColor:'transparent', hidden: !state.show.position }
      ] : []),
      // tendencias
      { label:'Trend Clicks', data: trendClicks, borderColor:ensureRgba1(COLORS.clicks), borderDash:[2,2], pointRadius:0, tension:0, yAxisID:'y', fill:false, backgroundColor:'transparent', hidden: !state.trend.clicks, borderWidth: 1.25 },
      { label:'Trend Impressions', data: trendImpr, borderColor:ensureRgba1(COLORS.impressions), borderDash:[2,2], pointRadius:0, tension:0, yAxisID:'y1', fill:false, backgroundColor:'transparent', hidden: !state.trend.impressions, borderWidth: 1.25 },
      { label:'Trend CTR', data: trendCtr, borderColor:ensureRgba1(COLORS.ctr), borderDash:[2,2], pointRadius:0, tension:0, yAxisID:'y2', fill:false, backgroundColor:'transparent', hidden: !state.trend.ctr, borderWidth: 1.25 },
      { label:'Trend Position', data: trendPos, borderColor:ensureRgba1(COLORS.position), borderDash:[2,2], pointRadius:0, tension:0, yAxisID:'y3', fill:false, backgroundColor:'transparent', hidden: !state.trend.position, borderWidth: 1.25 }
    ];

    // Guardar datos para tooltip externo
    const prevDateByLabel = {};
    prev.forEach(d => prevDateByLabel[d.date] = d.date);
    container._poTooltipData = {
      labels,
      prevDateByLabel,
      clicks, impressions, ctr, position,
      clicksPrevByLabel: Object.fromEntries(labels.map(l=>[l, clicksPrev[labels.indexOf(l)] ])),
      impressionsPrevByLabel: Object.fromEntries(labels.map(l=>[l, impressionsPrev[labels.indexOf(l)] ])),
      ctrPrevByLabel: Object.fromEntries(labels.map(l=>[l, ctrPrev[labels.indexOf(l)] ])),
      positionPrevByLabel: Object.fromEntries(labels.map(l=>[l, positionPrev[labels.indexOf(l)] ])),
      show: state.show
    };

    // Mapas de índices para toggles avanzados
    container._baseIndexMap = { clicks:0, impressions:1, ctr:2, position:3 };
    const compCount = prev.length ? 4 : 0;
    const trendStartIndex = 4 + compCount;
    container._trendIndexMap = { clicks: trendStartIndex, impressions: trendStartIndex+1, ctr: trendStartIndex+2, position: trendStartIndex+3 };

    if (container._chart) container._chart.destroy();

    container._chart = new Chart(ctx, {
      type: 'line',
      data: { labels, datasets },
      options: {
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: { legend: { display: false }, tooltip: { enabled: false, external: externalTooltip } },
         scales: {
          x: { grid: { color: 'rgba(0,0,0,0.06)' }, ticks: { maxTicksLimit: 10 } },
          y: { position: 'left', ticks: { callback: v => numberFormatInteger(Number(v)) } },
          y1: { position: 'right', grid: { drawOnChartArea: false }, ticks: { callback: v => numberFormatInteger(Number(v)) } },
          y2: { display: false, suggestedMin: 0, suggestedMax: Math.max(10, Math.ceil(Math.max(...ctr, ...ctrPrev) * 1.2)) },
          y3: { display: false, suggestedMin: 0, suggestedMax: Math.max(10, Math.ceil(Math.max(...position, ...positionPrev) * 1.2)) }
        }
      }
    });
  }

  async function fetchAndRender() {
    let payload;
    if (typeof fetchUrlOrData === 'string') {
      try {
        const res = await fetch(fetchUrlOrData, { credentials: 'include' });
        payload = await res.json();
      } catch (e) {
        console.warn('⚠️ Error obteniendo series diarias, usando fallback:', e);
        payload = buildDailySeriesFromCurrentData();
      }
    } else {
      payload = fetchUrlOrData; // datos ya construidos desde front
    }

    // Preferir daily_series de currentData si es más completa que el payload
    const ds = (window.currentData && window.currentData.daily_series) ? window.currentData.daily_series : {};
    let rawCurrent = payload && Array.isArray(payload.current) ? payload.current : null;
    let rawPrev = payload && Array.isArray(payload.prev) ? payload.prev : null;
    if ((!rawCurrent || (rawCurrent.length < 2)) && Array.isArray(ds.current) && ds.current.length > (rawCurrent ? rawCurrent.length : 0)) {
      rawCurrent = ds.current;
    }
    if ((!rawPrev || (rawPrev.length < 2)) && Array.isArray(ds.prev) && ds.prev.length > (rawPrev ? rawPrev.length : 0)) {
      rawPrev = ds.prev;
    }
    const current = normalizePoints(rawCurrent || []);
    const prev = normalizePoints(rawPrev || []);

    // Mostrar contenedor si hay datos
    const section = document.getElementById('performanceOverview');
    if (section) section.style.display = (current.length > 0) ? 'block' : 'none';

    state.data.current = current;
    state.data.prev = prev;
    render();

    // Actualizar KPIs superiores (P1/P2 y delta)
    try {
      const sum = arr => arr.reduce((a,b)=>a+(b||0),0);
      const avg = arr => arr.length ? (arr.reduce((a,b)=>a+(b||0),0)/arr.length) : 0;
      const clicks = current.map(d=>d.clicks); const impr = current.map(d=>d.impressions);
      const ctr = impr.reduce((a,_,i)=>a+((current[i].ctr||0)*(current[i].impressions||0)),0) / (sum(impr)||1);
      const pos = impr.reduce((a,_,i)=>a+((current[i].position||0)*(current[i].impressions||0)),0) / (sum(impr)||1);
      const clicksC = sum(prev.map(d=>d.clicks)); const imprC = sum(prev.map(d=>d.impressions));
      const ctrC = imprC>0 ? (prev.reduce((a,_,i)=>a+((prev[i].ctr||0)*(prev[i].impressions||0)),0)/imprC) : 0;
      const posC = imprC>0 ? (prev.reduce((a,_,i)=>a+((prev[i].position||0)*(prev[i].impressions||0)),0)/imprC) : 0;

      const p1Label = (()=>{ try { const ds = window.dateSelector; const s = ds?.currentPeriod?.startDate; const e = ds?.currentPeriod?.endDate; if (s&&e) return `${String(s.getDate()).padStart(2,'0')}/${String(s.getMonth()+1).padStart(2,'0')}/${s.getFullYear()} - ${String(e.getDate()).padStart(2,'0')}/${String(e.getMonth()+1).padStart(2,'0')}/${e.getFullYear()}`; } catch(_){} return 'Periodo actual'; })();
      const p2Label = (()=>{ try { const ds = window.dateSelector; const s = ds?.comparisonPeriod?.startDate; const e = ds?.comparisonPeriod?.endDate; if (s&&e) return `${String(s.getDate()).padStart(2,'0')}/${String(s.getMonth()+1).padStart(2,'0')}/${s.getFullYear()} - ${String(e.getDate()).padStart(2,'0')}/${String(e.getMonth()+1).padStart(2,'0')}/${e.getFullYear()}`; } catch(_){} return 'Periodo anterior'; })();

      const setMetric = (k, val, comp, isPercent=false, isPos=false)=>{
        const root = container.querySelector(`.po-metric[data-k="${k}"]`);
        if (!root) return;
        const p1 = root.querySelector('.po-p1');
        const p2 = root.querySelector('.po-p2');
        const dEl = root.querySelector('.po-delta');
        const fmt = v => isPercent ? `${(v||0).toFixed(2)}%` : (isPos ? (v||0).toFixed(2) : numberFormatInteger(v||0));
        if (p1) p1.innerHTML = `<span class="po-date">${p1Label}</span> · <strong class="po-value-strong">${fmt(val)}</strong>`;
        if (p2) p2.innerHTML = prev.length ? `<span class="po-date">${p2Label}</span> · <span class="po-value-small">${fmt(comp)}</span>` : '';
        if (dEl) {
          if (prev.length) {
            let delta;
            if (isPos) delta = (val - comp);
            else if (isPercent || k==='clicks' || k==='impressions') delta = ((val - (comp||1))/(comp||1))*100; else delta = (val - comp);
            const good = isPos ? (delta < 0) : (delta >= 0);
            dEl.style.color = good ? '#16a34a' : '#dc2626';
            dEl.textContent = isPos ? `${delta.toFixed(2)}` : `${delta.toFixed(2)}%`;
          } else {
            dEl.textContent = '';
          }
        }
      };

      setMetric('clicks', sum(clicks), clicksC, false, false);
      setMetric('impressions', sum(impr), imprC, false, false);
      setMetric('ctr', ctr*100, ctrC*100, true, false);
      setMetric('position', pos, posC, false, true);
    } catch(e) { /* noop */ }
  }

  // Event handlers
  const syncButtons = () => {
    container.querySelectorAll('#po-top-toggles .po-btn[data-k]').forEach(btn => {
      const k = btn.getAttribute('data-k');
      btn.classList.toggle('active', !!state.show[k]);
    });
  };
  syncButtons();

  container.querySelectorAll('#po-top-toggles .po-btn[data-k]').forEach(btn => {
    btn.addEventListener('click', () => {
      const k = btn.getAttribute('data-k');
      state.show[k] = !state.show[k];
      try { localStorage.setItem('po_toggles', JSON.stringify(state.show)); } catch(_) {}
      syncButtons();
      render();
    });
  });

  container.querySelectorAll('#po-top-toggles .po-trend-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const m = btn.getAttribute('data-trend');
      state.trend[m] = !state.trend[m];
      btn.classList.toggle('active', state.trend[m]);
      render();
    });
  });

  await fetchAndRender();
}

// Builder: compone los puntos diarios desde window.currentData.summary/pages si backend no entrega series
export function buildDailySeriesFromCurrentData() {
  const data = window.currentData || {};
  const periods = data.periods || {};
  const hasComparison = periods.has_comparison && periods.comparison;

  // Buscar origen de series: si backend ya adjunta series, respétalas
  if (data.daily_series && (data.daily_series.current || data.daily_series.prev)) {
    return { current: data.daily_series.current || [], prev: data.daily_series.prev || [] };
  }

  // Fallback: construir 1-2 puntos a partir de summary agregado (P1/P2)
  const periodSummary = window.currentPeriodSummary || null;
  if (!periodSummary || typeof periodSummary !== 'object') {
    return { current: [], prev: [] };
  }

  const keys = Object.keys(periodSummary).sort((a, b) => {
    const A = periodSummary[a];
    const B = periodSummary[b];
    if (A.StartDate && B.StartDate) return new Date(A.StartDate) - new Date(B.StartDate);
    return a.localeCompare(b);
  });

  if (keys.length === 0) return { current: [], prev: [] };

  const p1Key = keys[keys.length - 1];
  const p1 = periodSummary[p1Key] || {};
  const currentPoint = [{
    date: p1.EndDate || p1Key,
    clicks: Number(p1.Clicks) || 0,
    impressions: Number(p1.Impressions) || 0,
    ctr: Number(p1.CTR) || 0,
    position: typeof p1.Position === 'number' ? p1.Position : Number(p1.Position) || 0
  }];

  let prevPoints = [];
  if (hasComparison && keys.length >= 2) {
    const p2Key = keys[0];
    const p2 = periodSummary[p2Key] || {};
    prevPoints = [{
      date: p2.EndDate || p2Key,
      clicks: Number(p2.Clicks) || 0,
      impressions: Number(p2.Impressions) || 0,
      ctr: Number(p2.CTR) || 0,
      position: typeof p2.Position === 'number' ? p2.Position : Number(p2.Position) || 0
    }];
  }

  return { current: currentPoint, prev: prevPoints };
}

// Inicialización conveniente
export function initPerformanceOverview() {
  const series = buildDailySeriesFromCurrentData();
  mountChartJSOverview('performanceOverview', series);
}


