// performance-overview.js - Chart.js v4 Overview (usando Chart global del CDN)

function numberFormatInteger(v) {
  return new Intl.NumberFormat().format(Math.round(Number(v) || 0));
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

  const canvas = container.querySelector('canvas') || document.getElementById('poChartCanvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');

  const state = {
    activeMetric: 'clicks',
    trend: { clicks: false, impressions: false, ctr: false, position: false },
    data: { current: [], prev: [] }
  };

  function getOrCreateTooltipEl() {
    let el = container.querySelector('.po-tooltip');
    if (!el) {
      el = document.createElement('div');
      el.className = 'po-tooltip';
      el.style.cssText = [
        'position:absolute', 'pointer-events:none', 'background:#0b1220', 'color:#fff',
        'border-radius:10px', 'padding:10px 12px', 'box-shadow:0 6px 24px rgba(0,0,0,0.25)',
        'z-index:30', 'opacity:0', 'transform:translate(-50%, -120%)', 'transition:opacity .12s ease'
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

  // Tooltip externo con doble columna (fecha actual vs fecha previa)
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
    const metric = dataRef.metric;

    const curDate = dataRef.labels[i] || '';
    const prevDate = dataRef.prevLabels?.[i] || '';
    const curVal = Number(dataRef.main[i] || 0);
    const prevVal = Number((dataRef.comp && dataRef.comp[i]) || 0);

    const lineColor = COLORS[metric];
    const compColor = COLORS.compare;

    const formatVal = (v) => buildTooltipLabel(metric, v);
    const delta = formatPctDelta(curVal, prevVal, metric);

    tooltipEl.innerHTML = `
      <div style="display:flex; gap:16px; align-items:flex-start;">
        <div style="min-width:120px;">
          <div style="opacity:.85; font-size:12px; margin-bottom:6px;">${curDate}</div>
          <div style="display:flex; align-items:center; gap:6px;">
            <span style="width:10px;height:10px;border-radius:50%;background:${lineColor};display:inline-block"></span>
            <span style="font-weight:600; text-transform:capitalize;">${metric}</span>
          </div>
          <div style="margin-top:4px; font-size:14px;">
            ${formatVal(curVal)}
            <span style="margin-left:8px; ${delta.startsWith('+') ? 'color:#10b981' : (delta.startsWith('-') ? 'color:#ef4444' : 'opacity:.75')}">${delta}</span>
          </div>
        </div>
        <div style="min-width:120px;">
          <div style="opacity:.7; font-size:12px; margin-bottom:6px;">${prevDate}</div>
          <div style="display:flex; align-items:center; gap:6px;">
            <span style="width:10px;height:10px;border-radius:50%;background:${compColor};display:inline-block"></span>
            <span style="opacity:.85;">Prev</span>
          </div>
          <div style="margin-top:4px; font-size:14px; opacity:.9;">${formatVal(prevVal)}</div>
        </div>
      </div>
    `;

    const { offsetLeft: positionX, offsetTop: positionY } = chart.canvas;
    tooltipEl.style.left = positionX + tooltip.caretX + 'px';
    tooltipEl.style.top = positionY + tooltip.caretY + 'px';
    tooltipEl.style.opacity = '1';
  }

  function render() {
    const rows = state.data.current;
    const prev = state.data.prev;
    const metric = state.activeMetric;

    const labels = rows.map(d => d.date);
    const main = buildSeries(rows, metric);
    const comp = buildSeries(prev, metric);
    const trend = state.trend[metric] ? linearRegression(main) : null;

    const leftAxisMetrics = ['clicks', 'impressions'];
    const useRightAxis = !leftAxisMetrics.includes(metric);

    const datasets = [
      {
        label: metric,
        data: main,
        borderColor: COLORS[metric],
        backgroundColor: makeGradient(ctx, canvas, COLORS[metric]),
        borderWidth: 2,
        fill: 'origin',
        pointRadius: 0,
        tension: 0.35,
        yAxisID: useRightAxis ? 'y1' : 'y'
      },
      {
        label: metric + ' (prev)',
        data: comp,
        borderColor: COLORS.compare,
        borderDash: [6, 6],
        borderWidth: 2,
        pointRadius: 0,
        fill: false,
        tension: 0.35,
        yAxisID: useRightAxis ? 'y1' : 'y'
      }
    ];

    if (trend) {
      datasets.push({
        label: metric + ' (trend)',
        data: trend,
        borderColor: COLORS[metric],
        borderDash: [3, 3],
        borderWidth: 2,
        pointRadius: 0,
        fill: false,
        tension: 0,
        yAxisID: useRightAxis ? 'y1' : 'y'
      });
    }

    // Guardar datos para tooltip externo alineado por índice
    container._poTooltipData = {
      labels,
      prevLabels: labels, // asumimos alineación 1:1 de periodos
      main,
      comp,
      metric
    };

    if (container._chart) container._chart.destroy();

    container._chart = new Chart(ctx, {
      type: 'line',
      data: { labels, datasets },
      options: {
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: { legend: { display: false }, tooltip: { enabled: false, external: externalTooltip } },
        scales: {
          x: { grid: { color: 'rgba(0,0,0,0.06)' } },
          y: {
            position: 'left',
            grid: { color: 'rgba(0,0,0,0.06)' },
            ticks: { callback: v => numberFormatInteger(Number(v)) }
          },
          y1: {
            position: 'right',
            grid: { drawOnChartArea: false },
            ticks: {
              callback: v => state.activeMetric === 'ctr' ? (Number(v).toFixed(2) + '%') : Number(v).toFixed(2)
            },
            reverse: state.activeMetric === 'position' ? true : false
          }
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

    const current = normalizePoints(payload.current || []);
    const prev = normalizePoints(payload.prev || []);

    // Mostrar contenedor si hay datos
    const section = document.getElementById('performanceOverview');
    if (section) section.style.display = (current.length > 0) ? 'block' : 'none';

    state.data.current = current;
    state.data.prev = prev;
    render();
  }

  // Event handlers
  container.querySelectorAll('.po-metric-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      state.activeMetric = btn.dataset.metric;
      // Apagar todas las tendencias al cambiar de métrica (recomendado)
      state.trend = { clicks: false, impressions: false, ctr: false, position: false };
      // Actualizar estilos de tabs y botones de tendencia
      container.querySelectorAll('.po-metric-tab').forEach(b => b.classList.toggle('active', b === btn));
      container.querySelectorAll('.po-trend-btn').forEach(b => b.classList.remove('active'));
      render();
    });
  });

  container.querySelectorAll('.po-trend-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const m = btn.dataset.trend;
      state.trend[m] = !state.trend[m];
      btn.classList.toggle('active', state.trend[m]);
      // Opcional: atenuar área cuando hay tendencia
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


