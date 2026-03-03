// ============================================================
//  ui-overview-movers.js
//  Top Winners & Losers tables + Position Distribution chart
//  Brandbook v2: Bio-Lime · Inter Tight · Libre Baskerville
// ============================================================

import { processUrlsForComparison } from './data.js';

// ── Helpers ─────────────────────────────────────────────────

/** True if the value is a usable numeric delta (not "New", "Lost", "Infinity", etc.) */
function isNumericDelta(v) {
  if (v === null || v === undefined) return false;
  if (typeof v === 'string') return false; // "New", "Lost", "Infinity", "N/A"
  return Number.isFinite(v);
}

/** Format a number for display (compact) */
function fmt(n, decimals = 0) {
  if (n === null || n === undefined || typeof n === 'string') return '—';
  return Number(n).toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  });
}

/** Format a delta % with sign and color class */
function deltaHTML(value, invert = false) {
  if (!isNumericDelta(value)) return '<span class="delta-tag neutral">—</span>';
  const v = Number(value);
  if (v === 0) return '<span class="delta-tag neutral">0%</span>';

  // For position, lower is better → invert colors
  const isPositive = invert ? v < 0 : v > 0;
  const cls = isPositive ? 'positive' : 'negative';
  const sign = v > 0 ? '+' : '';
  return `<span class="delta-tag ${cls}">${sign}${v.toFixed(1)}%</span>`;
}

/** Format a position delta (absolute, not %) — lower is better */
function posDeltaHTML(value) {
  if (!isNumericDelta(value)) return '<span class="delta-tag neutral">—</span>';
  const v = Number(value);
  if (v === 0) return '<span class="delta-tag neutral">0</span>';

  // Negative delta = position improved (went from 10 to 5 = -5)
  const isPositive = v < 0;
  const cls = isPositive ? 'positive' : 'negative';
  const sign = v > 0 ? '+' : '';
  return `<span class="delta-tag ${cls}">${sign}${v.toFixed(1)}</span>`;
}

/** Truncate a string to maxLen chars */
function truncate(str, maxLen = 45) {
  if (!str) return '—';
  return str.length > maxLen ? str.substring(0, maxLen) + '…' : str;
}


// ── Main Entry Point ────────────────────────────────────────

/**
 * Renders the Top Movers tables and Position Distribution chart.
 * Called from ui-core.js after data loads.
 *
 * @param {Array} keywordData  — window.currentData.keyword_comparison_data
 * @param {Array} urlsData     — processUrlsForComparison(data.pages, data.periods)
 * @param {boolean} hasComparison — data.periods?.has_comparison
 */
export function renderOverviewMovers(keywordData, urlsData, hasComparison) {
  const moversSection = document.getElementById('moversSection');
  const posDistSection = document.getElementById('positionDistSection');

  // Need comparison data to show movers
  if (!hasComparison) {
    if (moversSection) moversSection.style.display = 'none';
    if (posDistSection) posDistSection.style.display = 'none';
    return;
  }

  // ── Render Movers ──
  if (moversSection) {
    moversSection.style.display = 'block';
    initMoversPanel('keywordMoversPanel', 'keywordMoversTable', keywordData, 'keyword');
    initMoversPanel('urlMoversPanel', 'urlMoversTable', urlsData, 'url');
  }

  // ── Render Position Distribution ──
  if (posDistSection) {
    posDistSection.style.display = 'block';
    renderPositionDistribution(keywordData, hasComparison);
  }
}


// ── Movers Panel Logic ──────────────────────────────────────

function initMoversPanel(panelId, tableContainerId, data, type) {
  const panel = document.getElementById(panelId);
  if (!panel) return;

  // Prepare sorted data
  const winners = getTopMovers(data, type, 'winners', 10);
  const losers  = getTopMovers(data, type, 'losers', 10);

  // Render default (winners)
  renderMoversTable(tableContainerId, winners, type, 'winners');

  // Chip handlers
  const chips = panel.querySelectorAll('.movers-chip');
  chips.forEach(chip => {
    chip.addEventListener('click', () => {
      // Toggle active
      chips.forEach(c => c.classList.remove('active'));
      chip.classList.add('active');

      const selected = chip.getAttribute('data-type');
      const rows = selected === 'winners' ? winners : losers;
      renderMoversTable(tableContainerId, rows, type, selected);
    });
  });
}


/**
 * Sort and pick top movers.
 * Winners = highest delta_clicks_percent (positive)
 * Losers  = lowest delta_clicks_percent (negative)
 */
function getTopMovers(data, type, direction, count) {
  if (!data || !data.length) return [];

  // Filter to only numeric deltas
  const filtered = data.filter(d => {
    const delta = d.delta_clicks_percent;
    return isNumericDelta(delta);
  });

  // Sort
  const sorted = [...filtered].sort((a, b) => {
    if (direction === 'winners') {
      return Number(b.delta_clicks_percent) - Number(a.delta_clicks_percent);
    }
    return Number(a.delta_clicks_percent) - Number(b.delta_clicks_percent);
  });

  // Filter direction: winners = positive delta, losers = negative delta
  const dirFiltered = sorted.filter(d => {
    const v = Number(d.delta_clicks_percent);
    return direction === 'winners' ? v > 0 : v < 0;
  });

  return dirFiltered.slice(0, count);
}


/**
 * Renders a plain HTML table of movers.
 */
function renderMoversTable(containerId, rows, type, direction) {
  const container = document.getElementById(containerId);
  if (!container) return;

  if (!rows || rows.length === 0) {
    container.innerHTML = `
      <div class="movers-empty">
        <i class="fas fa-${direction === 'winners' ? 'trophy' : 'chart-line-down'}"></i>
        <span>No ${direction} found for this period</span>
      </div>`;
    return;
  }

  // Determine field names based on type
  const isKeyword = type === 'keyword';
  const nameField = isKeyword ? 'keyword' : 'url';
  const clicksField = isKeyword ? 'clicks_m1' : 'clicks_p1';
  const impressionsField = isKeyword ? 'impressions_m1' : 'impressions_p1';
  const posField = isKeyword ? 'position_m1' : 'position_p1';
  const deltaClicksField = 'delta_clicks_percent';
  const deltaImpField = 'delta_impressions_percent';
  const deltaPosField = 'delta_position_absolute';

  let html = `
    <table class="movers-table">
      <thead>
        <tr>
          <th class="col-name">${isKeyword ? 'Keyword' : 'URL'}</th>
          <th class="col-metric">Clicks</th>
          <th class="col-delta">Δ Clicks</th>
          <th class="col-metric">Impr.</th>
          <th class="col-delta">Δ Impr.</th>
          <th class="col-metric">Position</th>
          <th class="col-delta">Δ Pos</th>
        </tr>
      </thead>
      <tbody>`;

  rows.forEach((row, i) => {
    const name = isKeyword
      ? truncate(row[nameField], 35)
      : truncate(row[nameField], 50);
    const clicks = fmt(row[clicksField]);
    const impressions = fmt(row[impressionsField]);
    const position = row[posField] !== null ? fmt(row[posField], 1) : '—';
    const dClicks = deltaHTML(row[deltaClicksField]);
    const dImpr = deltaHTML(row[deltaImpField]);
    const dPos = posDeltaHTML(row[deltaPosField]);

    html += `
        <tr>
          <td class="col-name" title="${row[nameField] || ''}">${name}</td>
          <td class="col-metric">${clicks}</td>
          <td class="col-delta">${dClicks}</td>
          <td class="col-metric">${impressions}</td>
          <td class="col-delta">${dImpr}</td>
          <td class="col-metric">${position}</td>
          <td class="col-delta">${dPos}</td>
        </tr>`;
  });

  html += `
      </tbody>
    </table>`;

  container.innerHTML = html;
}


// ── Position Distribution Chart ─────────────────────────────

function renderPositionDistribution(keywordData, hasComparison) {
  const canvas = document.getElementById('positionDistChart');
  if (!canvas) return;

  // Destroy previous chart instance if any
  if (canvas._chartInstance) {
    canvas._chartInstance.destroy();
    canvas._chartInstance = null;
  }

  const buckets = [
    { label: 'Top 3',  min: 1,  max: 3  },
    { label: '4–10',   min: 4,  max: 10 },
    { label: '11–20',  min: 11, max: 20 },
    { label: '20+',    min: 21, max: Infinity }
  ];

  // Count keywords per bucket for current period (position_m1) and comparison (position_m2)
  const countsP1 = buckets.map(() => 0);
  const countsP2 = buckets.map(() => 0);
  let totalP1 = 0;
  let totalP2 = 0;

  (keywordData || []).forEach(kw => {
    const pos1 = kw.position_m1;
    const pos2 = kw.position_m2;

    if (pos1 !== null && pos1 !== undefined && Number.isFinite(pos1)) {
      totalP1++;
      for (let i = 0; i < buckets.length; i++) {
        if (pos1 >= buckets[i].min && pos1 <= buckets[i].max) {
          countsP1[i]++;
          break;
        }
      }
    }

    if (hasComparison && pos2 !== null && pos2 !== undefined && Number.isFinite(pos2)) {
      totalP2++;
      for (let i = 0; i < buckets.length; i++) {
        if (pos2 >= buckets[i].min && pos2 <= buckets[i].max) {
          countsP2[i]++;
          break;
        }
      }
    }
  });

  // Append "Total" bucket
  countsP1.push(totalP1);
  countsP2.push(totalP2);

  const labels = [...buckets.map(b => b.label), 'Total'];

  // Detect dark mode
  const isDark = document.body.classList.contains('dark-mode');
  const textColor = isDark ? '#CBD5E1' : '#64748B';
  const gridColor = isDark ? 'rgba(51,65,85,0.4)' : 'rgba(226,232,240,0.8)';

  // Brandbook colors — "Total" bar gets a distinct accent color
  const bgP1 = countsP1.map((_, i) =>
    i === countsP1.length - 1 ? 'rgba(217, 249, 184, 0.55)' : 'rgba(59, 130, 246, 0.75)'
  );
  const borderP1 = countsP1.map((_, i) =>
    i === countsP1.length - 1 ? '#9AE6A1' : '#3B82F6'
  );

  const datasets = [
    {
      label: 'Current Period',
      data: countsP1,
      backgroundColor: bgP1,
      borderColor: borderP1,
      borderWidth: 1,
      borderRadius: 6,
      barPercentage: hasComparison ? 0.45 : 0.6,
      categoryPercentage: 0.7
    }
  ];

  if (hasComparison) {
    const bgP2 = countsP2.map((_, i) =>
      i === countsP2.length - 1 ? 'rgba(148, 163, 184, 0.25)' : 'rgba(148, 163, 184, 0.45)'
    );
    const borderP2 = countsP2.map((_, i) =>
      i === countsP2.length - 1 ? '#B0BEC5' : '#94A3B8'
    );
    datasets.push({
      label: 'Previous Period',
      data: countsP2,
      backgroundColor: bgP2,
      borderColor: borderP2,
      borderWidth: 1,
      borderRadius: 6,
      barPercentage: 0.45,
      categoryPercentage: 0.7
    });
  }

  // Wait for Chart.js to be available
  if (typeof Chart === 'undefined') {
    console.warn('Chart.js not loaded yet for position distribution');
    return;
  }

  const ctx = canvas.getContext('2d');
  const chart = new Chart(ctx, {
    type: 'bar',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: hasComparison,
          position: 'top',
          align: 'end',
          labels: {
            color: textColor,
            font: { family: "'Inter Tight', sans-serif", size: 12, weight: 500 },
            usePointStyle: true,
            pointStyle: 'rectRounded',
            padding: 16
          }
        },
        tooltip: {
          backgroundColor: isDark ? '#1E293B' : '#0F172A',
          titleFont: { family: "'Inter Tight', sans-serif", size: 13, weight: 600 },
          bodyFont: { family: "'Inter Tight', sans-serif", size: 12 },
          padding: 12,
          cornerRadius: 10,
          displayColors: true,
          callbacks: {
            label: function(context) {
              return ` ${context.dataset.label}: ${context.parsed.y} keywords`;
            }
          }
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            color: (ctx) => ctx.index === labels.length - 1 ? (isDark ? '#D9F9B8' : '#0F172A') : textColor,
            font: (ctx) => ({
              family: "'Inter Tight', sans-serif",
              size: 13,
              weight: ctx.index === labels.length - 1 ? 700 : 600
            })
          }
        },
        y: {
          beginAtZero: true,
          grid: { color: gridColor },
          ticks: {
            color: textColor,
            font: { family: "'Inter Tight', sans-serif", size: 12 },
            stepSize: Math.max(1, Math.ceil(Math.max(...countsP1, ...countsP2) / 6))
          }
        }
      },
      animation: {
        duration: 700,
        easing: 'easeOutQuart'
      }
    }
  });

  // Store reference for cleanup
  canvas._chartInstance = chart;
}
