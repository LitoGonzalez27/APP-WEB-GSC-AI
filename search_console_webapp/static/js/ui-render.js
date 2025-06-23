// ui-render.js - ACTUALIZADO para manejar períodos específicos en lugar de meses
import { elems } from './utils.js';

// Variable para almacenar la instancia de DataTable de URLs
let urlsDataTable = null;

// Funciones auxiliares para formateo (reutilizadas de la tabla de keywords)
function formatPercentageChange(value, isCTR = false) {
  if (value === "Infinity") return '+∞%';
  if (value === "-Infinity") return '-∞%';
  if (value === "New") return '<span class="positive-change">Nuevo</span>';
  if (value === "Lost") return '<span class="negative-change">Perdido</span>';
  if (typeof value === 'number' && isFinite(value)) {
    if (value === 0 && Object.is(value, -0)) return isCTR ? '-0.00%' : '-0.0%';
    if (value === 0) return isCTR ? '0.00%' : '0.0%';
    return isCTR ? `${value.toFixed(2)}%` : `${value.toFixed(1)}%`;
  }
  return 'N/A';
}

function formatPosition(value) {
  return (value == null || isNaN(value)) ? 'N/A' : value.toFixed(1);
}

function formatPositionDelta(delta, pos1, pos2) {
  if (delta === 'New')   return '<span class="positive-change">Nuevo</span>';
  if (delta === 'Lost')  return '<span class="negative-change">Perdido</span>';
  if (typeof delta === 'number' && isFinite(delta)) {
    if (delta > 0) return `+${delta.toFixed(1)}`;
    if (delta < 0) return delta.toFixed(1);
    return '0.0';
  }
  if (pos1 == null && pos2 == null) return 'N/A';
  return pos1 === pos2 ? '0.0' : 'N/A';
}

// ✅ NUEVA función para determinar el tipo de análisis para URLs
function getUrlAnalysisType(urlData) {
  if (!urlData || urlData.length === 0) return 'empty';
  
  // Verificar si hay múltiples períodos por URL
  const hasMultiplePeriods = urlData.some(urlItem => 
    urlItem.Metrics && urlItem.Metrics.length > 1
  );
  
  return hasMultiplePeriods ? 'comparison' : 'single';
}

// ✅ NUEVA función para actualizar headers de tabla de URLs
function updateUrlTableHeaders(analysisType) {
  const table = document.getElementById('resultsTable');
  if (!table) return;
  
  const headers = table.querySelectorAll('thead th');
  
  if (analysisType === 'single') {
    // Headers para período único
    if (headers[1]) headers[1].textContent = 'Clicks P1';
    if (headers[2]) headers[2].style.display = 'none'; // Ocultar P2
    if (headers[3]) headers[3].style.display = 'none'; // Ocultar Delta
    if (headers[4]) headers[4].textContent = 'Impressions P1';
    if (headers[5]) headers[5].style.display = 'none'; // Ocultar P2
    if (headers[6]) headers[6].style.display = 'none'; // Ocultar Delta
    if (headers[7]) headers[7].textContent = 'CTR P1 (%)';
    if (headers[8]) headers[8].style.display = 'none'; // Ocultar P2
    if (headers[9]) headers[9].style.display = 'none'; // Ocultar Delta
    if (headers[10]) headers[10].textContent = 'Pos P1';
    if (headers[11]) headers[11].style.display = 'none'; // Ocultar P2
    if (headers[12]) headers[12].style.display = 'none'; // Ocultar Delta
  } else {
    // Headers para comparación (mostrar todos)
    if (headers[1]) headers[1].textContent = 'Clicks P1';
    if (headers[2]) {
      headers[2].style.display = '';
      headers[2].textContent = 'Clicks P2';
    }
    if (headers[3]) {
      headers[3].style.display = '';
      headers[3].textContent = 'ΔClicks (%)';
    }
    if (headers[4]) headers[4].textContent = 'Impressions P1';
    if (headers[5]) {
      headers[5].style.display = '';
      headers[5].textContent = 'Impressions P2';
    }
    if (headers[6]) {
      headers[6].style.display = '';
      headers[6].textContent = 'ΔImp. (%)';
    }
    if (headers[7]) headers[7].textContent = 'CTR P1 (%)';
    if (headers[8]) {
      headers[8].style.display = '';
      headers[8].textContent = 'CTR P2 (%)';
    }
    if (headers[9]) {
      headers[9].style.display = '';
      headers[9].textContent = 'ΔCTR (%)';
    }
    if (headers[10]) headers[10].textContent = 'Pos P1';
    if (headers[11]) {
      headers[11].style.display = '';
      headers[11].textContent = 'Pos P2';
    }
    if (headers[12]) {
      headers[12].style.display = '';
      headers[12].textContent = 'ΔPos';
    }
  }
}

// ✅ FUNCIÓN CORREGIDA: processUrlsData en ui-render.js
function processUrlsData(pages) {
  const urlsData = [];
  
  pages.forEach(item => {
    const url = item.URL || 'N/A';
    const metrics = item.Metrics || [];
    
    if (metrics.length === 1) {
      // Período único
      const metric = metrics[0];
      urlsData.push({
        url: url,
        clicks_p1: 0,
        clicks_p2: metric.Clicks || 0,
        impressions_p1: 0,
        impressions_p2: metric.Impressions || 0,
        ctr_p1: 0,
        ctr_p2: (metric.CTR || 0) * 100,
        position_p1: null,
        position_p2: metric.Position || null,
        delta_clicks_percent: 'New',
        delta_impressions_percent: 'New',
        delta_ctr_percent: 'New',
        delta_position_absolute: 'New'
      });
    } else if (metrics.length >= 2) {
      // ✅ CORREGIDO: Ordenar por fecha para asegurar el orden correcto
      const sortedMetrics = metrics.sort((a, b) => {
        if (a.StartDate && b.StartDate) {
          return new Date(a.StartDate) - new Date(b.StartDate);
        }
        return 0;
      });
      
      // ✅ CORREGIDO: Asignación correcta según el orden temporal
      const currentMetric = sortedMetrics[sortedMetrics.length - 1]; // P1 = Más reciente (actual)
      const comparisonMetric = sortedMetrics[0]; // P2 = Más antiguo (comparación)
      
      // ✅ CORREGIDO: Calcular deltas como P1 sobre P2 (actual sobre comparación)
      const deltaClicks = calculatePercentageChange(currentMetric.Clicks, comparisonMetric.Clicks);
      const deltaImpressions = calculatePercentageChange(currentMetric.Impressions, comparisonMetric.Impressions);
      const deltaCTR = ((currentMetric.CTR || 0) * 100) - ((comparisonMetric.CTR || 0) * 100);
      const deltaPosition = (currentMetric.Position && comparisonMetric.Position)
        ? currentMetric.Position - comparisonMetric.Position
        : (currentMetric.Position ? 'New' : 'Lost');
      
      urlsData.push({
        url: url,
        // ✅ CORREGIDO: P1 = período actual (más reciente)
        clicks_p1: currentMetric.Clicks || 0,      
        impressions_p1: currentMetric.Impressions || 0,
        ctr_p1: (currentMetric.CTR || 0) * 100,
        position_p1: currentMetric.Position || null,
        
        // ✅ CORREGIDO: P2 = período de comparación (más antiguo)
        clicks_p2: comparisonMetric.Clicks || 0,      
        impressions_p2: comparisonMetric.Impressions || 0,
        ctr_p2: (comparisonMetric.CTR || 0) * 100,
        position_p2: comparisonMetric.Position || null,
        
        // ✅ CORREGIDO: Deltas calculados como (P1 - P2) / P2
        delta_clicks_percent: deltaClicks,
        delta_impressions_percent: deltaImpressions,
        delta_ctr_percent: deltaCTR,
        delta_position_absolute: deltaPosition
      });
    }
  });
  
  return urlsData;
}

// ✅ FUNCIÓN auxiliar para calcular cambio porcentual
function calculatePercentageChange(p1, p2) {
  if (p1 === null || p2 === null || typeof p1 === 'undefined' || typeof p2 === 'undefined') {
    return 'N/A';
  }
  if (p2 === 0) {
    if (p1 > 0) return "Infinity";
    if (p1 < 0) return "-Infinity";
    return 0;
  }
  return ((p1 / p2) - 1) * 100;
}

// Genera la tarjeta de categoría para palabras clave
function buildCatCard(title, stat = { current: 0, new: 0, lost: 0, stay: 0 }) {
  return `
    <div class="category-card">
      <div class="value">${stat.current}</div>
      <div class="subtitle">${title}</div>
      <div class="entry">New: <strong>+${stat.new}</strong></div>
      <div class="exit">Lost: <strong>-${stat.lost}</strong></div>
      <div class="maintain">Maintained: <strong>${stat.stay}</strong></div>
    </div>
  `;
}

// ✅ ACTUALIZADA: Función para crear mini-gráficos que maneja períodos específicos
function createMiniChart(canvasId, data, color, labels, type = 'line') {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return null;
  
  const ctx = canvas.getContext('2d');
  
  if (canvas.chart) {
    canvas.chart.destroy();
  }

  const gradient = ctx.createLinearGradient(0, 0, 0, 60);
  gradient.addColorStop(0, `${color}40`);
  gradient.addColorStop(1, `${color}08`);
  
  const chartConfig = {
    type: 'line',
    data: {
      labels: labels || ['P1', 'P2'], // Etiquetas por defecto para períodos
      datasets: [{
        data: data,
        borderColor: color,
        backgroundColor: gradient,
        borderWidth: 2.5,
        fill: true,
        tension: 0.4,
        pointRadius: 3,
        pointHoverRadius: 6,
        pointBackgroundColor: color,
        pointBorderColor: '#ffffff',
        pointBorderWidth: 2,
        pointHoverBackgroundColor: color,
        pointHoverBorderColor: '#ffffff',
        pointHoverBorderWidth: 3,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        intersect: false,
        mode: 'index',
      },
      plugins: {
        legend: { display: false },
        tooltip: { 
          enabled: true,
          mode: 'index',
          intersect: false,
          bodyFont: { size: 12 },
          titleFont: { size: 12 },
          backgroundColor: 'rgba(0, 0, 0, 0.8)',
          titleColor: '#fff',
          bodyColor: '#fff',
          borderColor: color,
          borderWidth: 1,
          cornerRadius: 6,
          displayColors: false,
          callbacks: {
            title: function(context) {
              return labels ? labels[context[0].dataIndex] : `Período ${context[0].dataIndex + 1}`;
            },
            label: function(context) {
              const value = context.parsed.y;
              if (canvasId.includes('ctr')) return `${value.toFixed(2)}%`;
              if (canvasId.includes('position')) return value.toFixed(1);
              return Number.isInteger(value) ? value.toLocaleString() : value;
            }
          }
        }
      },
      scales: {
        x: { 
          display: false,
          grid: { display: false }
        },
        y: { 
          display: false,
          grid: { display: false },
          beginAtZero: true
        }
      },
      animation: {
        duration: 1000,
        easing: 'easeInOutQuart'
      },
      hover: {
        animationDuration: 200
      }
    }
  };
  
  canvas.chart = new Chart(ctx, chartConfig);
  return canvas.chart;
}

// ✅ ACTUALIZADA: Renderiza el bloque de resumen con períodos específicos
export function renderSummary(periodSummary) {
  ['#summaryClicks', '#summaryImpressions', '#summaryCTR', '#summaryPosition'].forEach(sel => {
    const el = document.querySelector(`${sel} .summary-content`);
    if (el) el.innerHTML = '';
  });

  const periods = Object.keys(periodSummary).sort((a, b) => {
    // Ordenar por fecha de inicio si está disponible
    const periodA = periodSummary[a];
    const periodB = periodSummary[b];
    
    if (periodA.StartDate && periodB.StartDate) {
      return new Date(periodA.StartDate) - new Date(periodB.StartDate);
    }
    
    return a.localeCompare(b);
  });
  
  window.currentPeriodSummary = periodSummary;

  if (periods.length === 0) {
    console.warn('No hay períodos para mostrar en el resumen');
    return;
  }

  // ✅ NUEVO: Usar datos del último período (más reciente) como base
  const lastPeriod = periodSummary[periods[periods.length - 1]];
  const p1Clicks = lastPeriod.Clicks || 0;
  const p1Impressions = lastPeriod.Impressions || 0;
  const p1CTR = (lastPeriod.CTR || 0) * 100;
  const p1Position = lastPeriod.Position || 0;

  // Preparar datos para mini-gráficos
  const clicksData = periods.map(p => periodSummary[p].Clicks || 0);
  const impressionsData = periods.map(p => periodSummary[p].Impressions || 0);
  const ctrData = periods.map(p => parseFloat(((periodSummary[p].CTR || 0) * 100).toFixed(2)));
  const positionData = periods.map(p => parseFloat((periodSummary[p].Position || 0).toFixed(1)));

  // Generar etiquetas más legibles para los gráficos
  const chartLabels = periods.map((periodKey, index) => {
    const period = periodSummary[periodKey];
    if (period.StartDate && period.EndDate) {
      const start = new Date(period.StartDate);
      const end = new Date(period.EndDate);
      
      // Si es el mismo día
      if (period.StartDate === period.EndDate) {
        return start.toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit' });
      }
      
      // Si es un rango
      return `${start.toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit' })} - ${end.toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit' })}`;
    }
    
    return `P${index + 1}`;
  });

  const colors = {
    clicks: '#3B82F6',      // Azul
    impressions: '#8B45FF',  // Lila/Morado
    ctr: '#F59E0B',         // Naranja
    position: '#EF4444'     // Rojo
  };

  // ✅ ACTUALIZADA: Función para crear cards con información de períodos
  const createSummaryCard = (id, title, icon, total, chartData, chartLabels, color, isPercentage = false, isPosition = false) => {
    const formatValue = (val) => {
      if (isPercentage) return `${val.toFixed(2)}%`;
      if (isPosition) return val.toFixed(1);
      return val.toLocaleString();
    };

    // Función para formatear el delta
    const formatDelta = (deltaValue, isDeltaPercentage = false, isDeltaPosition = false, isDeltaCTR = false) => {
      if (deltaValue === 'N/A' || deltaValue === null || deltaValue === undefined) return 'N/A';
      if (deltaValue === 'Infinity' || deltaValue === '-Infinity') return deltaValue === 'Infinity' ? '+∞%' : '-∞%';
      
      if (isDeltaPosition) {
        // Para posición, el delta es absoluto (no porcentual)
        const sign = deltaValue > 0 ? '+' : '';
        return `${sign}${deltaValue.toFixed(1)}`;
      } else if (isDeltaCTR) {
        // Para CTR, el delta es en puntos porcentuales
        const sign = deltaValue > 0 ? '+' : '';
        return `${sign}${deltaValue.toFixed(2)}%`;
      } else {
        // Para clicks e impressions, el delta es porcentual
        const sign = deltaValue > 0 ? '+' : '';
        return `${sign}${deltaValue.toFixed(1)}%`;
      }
    };

    // ✅ NUEVO: Crear valores de períodos con formato de fechas (P1 primero)
    let periodValues = '';
    let deltaValues = [];
    
    // Invertir el orden para mostrar P1 (más reciente) primero
    const reversedPeriods = [...periods].reverse();
    reversedPeriods.forEach((periodKey, index) => {
      const period = periodSummary[periodKey];
      let value;
      if (id === 'clicks') value = period.Clicks || 0;
      else if (id === 'impressions') value = period.Impressions || 0;
      else if (id === 'ctr') value = (period.CTR || 0) * 100;
      else if (id === 'position') value = period.Position || 0;
      
      deltaValues.push(value);
      
      // Crear etiqueta con formato de fecha
      let dateLabel = '';
      if (period.StartDate && period.EndDate) {
        const start = new Date(period.StartDate);
        const end = new Date(period.EndDate);
        dateLabel = `${start.toLocaleDateString('es-ES', { day: 'numeric', month: 'numeric', year: 'numeric' })} - ${end.toLocaleDateString('es-ES', { day: 'numeric', month: 'numeric', year: 'numeric' })}`;
      } else {
        // Ajustar numeración para mostrar P1, P2 correctamente
        const originalIndex = periods.length - index;
        dateLabel = `P${originalIndex}`;
      }
      
      periodValues += `<div class="period-value-line">
        <span class="period-date">${dateLabel}</span>
        <span class="period-metric">${formatValue(value)}</span>
      </div>`;
    });

    // ✅ NUEVO: Calcular y mostrar delta solo cuando hay múltiples períodos
    let deltaHTML = '';
    if (periods.length >= 2 && deltaValues.length >= 2) {
      const p1Value = deltaValues[0]; // Período más reciente (P1)
      const p2Value = deltaValues[deltaValues.length - 1]; // Período más antiguo (P2)
      
      let deltaValue;
      if (isPosition) {
        // Para posición, calcular diferencia absoluta (P1 - P2)
        deltaValue = p1Value - p2Value;
      } else if (id === 'ctr') {
        // Para CTR, calcular diferencia absoluta en puntos porcentuales (P1 - P2)
        deltaValue = p1Value - p2Value;
        

      } else {
        // Para clicks e impressions, calcular cambio porcentual ((P1 - P2) / P2) * 100
        deltaValue = calculatePercentageChange(p1Value, p2Value);
      }
      
      // Determinar clase CSS según si es positivo o negativo
      let deltaClass = 'delta-neutral';
      if (deltaValue !== 'N/A' && deltaValue !== 'Infinity' && deltaValue !== '-Infinity') {
        if (isPosition) {
          // Para posición, negativo es mejor (menor posición es mejor)
          deltaClass = deltaValue < 0 ? 'delta-positive' : (deltaValue > 0 ? 'delta-negative' : 'delta-neutral');
        } else {
          // Para clicks, impressions, CTR, positivo es mejor
          deltaClass = deltaValue > 0 ? 'delta-positive' : (deltaValue < 0 ? 'delta-negative' : 'delta-neutral');
        }
      }
      
      deltaHTML = `
        <div class="period-delta-line ${deltaClass}">
          <span class="delta-label">Δ P1 vs P2</span>
          <span class="delta-value">${formatDelta(deltaValue, !isPosition && id !== 'ctr', isPosition, id === 'ctr')}</span>
        </div>
      `;
    }

    return `
      <div class="summary-card-enhanced modern-card">
        <div class="card-header-modern">
          <div class="card-icon-modern" style="background: linear-gradient(135deg, ${color}20, ${color}40); color: ${color};">
            <i class="${icon}"></i>
          </div>
          <h3 class="card-title-modern">${title}</h3>
        </div>
        
        <div class="period-values-modern">
          ${periodValues}
          ${deltaHTML}
        </div>
        
        ${periods.length > 1 ? `
        <div class="mini-chart-container-modern">
          <canvas id="mini-chart-${id}" width="120" height="80"></canvas>
        </div>
        ` : ''}
      </div>
    `;
  };

  // Limpiar y actualizar HTML de cada card completamente
  document.querySelector('#summaryClicks').innerHTML = 
    createSummaryCard('clicks', 'Total Clicks', 'fas fa-mouse-pointer', null, clicksData, chartLabels, colors.clicks);
  
  document.querySelector('#summaryImpressions').innerHTML = 
    createSummaryCard('impressions', 'Total Impressions', 'fas fa-eye', null, impressionsData, chartLabels, colors.impressions);
  
  document.querySelector('#summaryCTR').innerHTML = 
    createSummaryCard('ctr', 'Average CTR', 'fas fa-percentage', null, ctrData, chartLabels, colors.ctr, true);
  
  document.querySelector('#summaryPosition').innerHTML = 
    createSummaryCard('position', 'Average Position', 'fas fa-location-arrow', null, positionData, chartLabels, colors.position, false, true);

  // ✅ ACTUALIZADO: Solo crear mini-gráficos si hay múltiples períodos
  if (periods.length > 1) {
    setTimeout(() => {
      createMiniChart('mini-chart-clicks', clicksData, colors.clicks, chartLabels);
      createMiniChart('mini-chart-impressions', impressionsData, colors.impressions, chartLabels);
      createMiniChart('mini-chart-ctr', ctrData, colors.ctr, chartLabels);
      createMiniChart('mini-chart-position', positionData, colors.position, chartLabels);
    }, 100);
  }

  if (elems.summaryBlock) elems.summaryBlock.style.display = 'grid';
  if (elems.performanceTitle) elems.performanceTitle.style.display = 'block';
  if (elems.chartsBlock) elems.chartsBlock.style.display = 'none'; 
  if (elems.performanceSection) elems.performanceSection.style.display = 'block';
}

// ✅ FUNCIÓN CORREGIDA para ui-render.js (reemplazar solo la función renderKeywords)

export function renderKeywords(keywordStats = {}) {
  const ov = keywordStats.overall || {};
  
  if (elems.keywordOverviewDiv) {
    // ✅ Adaptar mensajes según si hay comparación o no
    const hasComparison = (ov.improved > 0 || ov.worsened > 0 || ov.lost > 0);
    
    elems.keywordOverviewDiv.innerHTML = `
      <div class="overview-card total-kws">
        <div class="card-icon"><i class="fas fa-search"></i></div>
        <div class="label">Total KWs</div>
        <div class="value">${(ov.total ?? 0).toLocaleString()}</div>
      </div>
      <div class="overview-card improved">
        <div class="card-icon"><i class="fas fa-arrow-trend-up"></i></div>
        <div class="label">${hasComparison ? 'Improve positions' : 'Top 1-3'}</div>
        <div class="value">${hasComparison ? '+' + (ov.improved ?? 0).toLocaleString() : (keywordStats.top3?.current ?? 0).toLocaleString()}</div>
      </div>
      <div class="overview-card declined">
        <div class="card-icon"><i class="fas fa-arrow-trend-down"></i></div>
        <div class="label">${hasComparison ? 'Decline positions' : 'Pos 4-10'}</div>
        <div class="value">${hasComparison ? '-' + (ov.worsened ?? 0).toLocaleString() : (keywordStats.top10?.current ?? 0).toLocaleString()}</div>
      </div>
      <div class="overview-card same-pos">
        <div class="card-icon"><i class="fas fa-equals"></i></div>
        <div class="label">Same pos.</div>
        <div class="value">${hasComparison ? (ov.same ?? 0).toLocaleString() : (keywordStats.top20?.current ?? 0).toLocaleString()}</div>
      </div>
      <div class="overview-card added">
        <div class="card-icon"><i class="fas fa-plus-circle"></i></div>
        <div class="label">${hasComparison ? 'New' : 'Pos 20+'}</div>
        <div class="value">${hasComparison ? '+' + (ov.new ?? 0).toLocaleString() : (keywordStats.top20plus?.current ?? 0).toLocaleString()}</div>
      </div>
      <div class="overview-card removed">
        <div class="card-icon"><i class="fas fa-minus-circle"></i></div>
        <div class="label">${hasComparison ? 'Lost' : 'Current period'}</div>
        <div class="value">${hasComparison ? '-' + (ov.lost ?? 0).toLocaleString() : '📊'}</div>
      </div>
    `;
    elems.keywordOverviewDiv.style.display = 'flex';
  }

  if (elems.keywordCategoryDiv) {
    const buckets = keywordStats;
    
    const buildModernCatCard = (title, stat = { current: 0, new: 0, lost: 0, stay: 0 }) => {
      const hasComparison = (stat.new > 0 || stat.lost > 0);
      
      return `
        <div class="category-card">
          <div class="card-icon"><i class="fas fa-layer-group"></i></div>
          <div class="value">${(stat.current ?? 0).toLocaleString()}</div>
          <div class="subtitle">${title}</div>
          ${hasComparison ? `
            <div class="entry">New: <strong>+${(stat.new ?? 0).toLocaleString()}</strong></div>
            <div class="exit">Lost: <strong>-${(stat.lost ?? 0).toLocaleString()}</strong></div>
            <div class="maintain">Maintained: <strong>${(stat.stay ?? 0).toLocaleString()}</strong></div>
          ` : `
            <div class="entry">Keywords in these positions</div>
            <div class="maintain">Total of the selected period</div>
          `}
        </div>
      `;
    };
    
    elems.keywordCategoryDiv.innerHTML = [
      buildModernCatCard('Positions 1 – 3', buckets.top3),
      buildModernCatCard('Positions 4 – 10', buckets.top10),
      buildModernCatCard('Positions 11 – 20', buckets.top20),
      buildModernCatCard('Positions 20 or more', buckets.top20plus)
    ].join('');
    elems.keywordCategoryDiv.style.display = 'grid';
  }

  if (elems.keywordsSection) elems.keywordsSection.style.display = 'block';
  if (elems.keywordsTitle) elems.keywordsTitle.style.display = 'block';
}

// ✅ ACTUALIZADA: renderInsights para trabajar con períodos específicos
export function renderInsights(periodData) {
  console.log('📊 Datos recibidos en renderInsights:', periodData);
  
  const insightsContainer = document.getElementById('summaryDisclaimer');
  if (!insightsContainer) {
    console.warn('Container de insights no encontrado');
    return;
  }

  if (!periodData || typeof periodData !== 'object') {
    console.warn('No hay datos de períodos para mostrar insights');
    insightsContainer.innerHTML = '<p>No hay datos disponibles para mostrar insights.</p>';
    return;
  }

  const periods = Object.keys(periodData).sort((a, b) => {
    const periodA = periodData[a];
    const periodB = periodData[b];
    
    if (periodA.StartDate && periodB.StartDate) {
      return new Date(periodA.StartDate) - new Date(periodB.StartDate);
    }
    
    return a.localeCompare(b);
  });

  console.log('📅 Períodos encontrados:', periods);

  if (periods.length === 0) {
    insightsContainer.innerHTML = '<p>No hay datos de períodos disponibles.</p>';
    return;
  }

  // ✅ NUEVO: Usar datos del último período (más reciente) como base
  const lastPeriod = periodData[periods[periods.length - 1]];
  const p1Clicks = lastPeriod.Clicks || 0;
  const p1Impressions = lastPeriod.Impressions || 0;
  const p1CTR = (lastPeriod.CTR || 0) * 100;
  const p1Position = lastPeriod.Position || 0;

  // ✅ NUEVO: Calcular comparaciones entre períodos si hay múltiples
  let changeData = null;
  if (periods.length >= 2) {
    const firstPeriod = periodData[periods[0]];
    const lastPeriod = periodData[periods[periods.length - 1]];
    
    changeData = {
      clicks: calculatePercentageChangeInsights(firstPeriod.Clicks, lastPeriod.Clicks),
      impressions: calculatePercentageChangeInsights(firstPeriod.Impressions, lastPeriod.Impressions),
      ctr: calculatePercentageChangeInsights(firstPeriod.CTR * 100, lastPeriod.CTR * 100),
      position: calculatePercentageChangeInsights(firstPeriod.Position, lastPeriod.Position, true)
    };
  }

  console.log('📈 Datos calculados:', {
    p1Clicks,
    p1Impressions,  
    p1CTR,
    p1Position,
    changeData,
    periodsCount: periods.length
  });

  // ✅ ACTUALIZADO: Generar insights con información de períodos
  const insights = [
    {
      type: 'clicks',
      icon: 'fas fa-mouse-pointer',
      label: 'Clicks',
      value: p1Clicks.toLocaleString(),
      change: changeData ? formatChange(changeData.clicks) : getNoChangeHTML(periods.length),
      description: periods.length > 1 ? 'vs first period' : `Total del período`
    },
    {
      type: 'impressions',
      icon: 'fas fa-eye',
      label: 'Impressions',
      value: p1Impressions.toLocaleString(),
      change: changeData ? formatChange(changeData.impressions) : getNoChangeHTML(periods.length),
      description: periods.length > 1 ? 'vs first period' : `Total del período`
    },
    {
      type: 'ctr',
      icon: 'fas fa-percentage',
      label: 'Average CTR',
      value: `${p1CTR.toFixed(2)}%`,
      change: changeData ? formatChange(changeData.ctr) : getNoChangeHTML(periods.length),
      description: periods.length > 1 ? 'vs first period' : `Promedio del período`
    },
    {
      type: 'position',
      icon: 'fas fa-location-arrow',
      label: 'Average Position',
      value: p1Position.toFixed(1),
      change: changeData ? formatChange(changeData.position) : getNoChangeHTML(periods.length),
      description: periods.length > 1 ? 'vs first period' : `Promedio del período`
    }
  ];

  insightsContainer.innerHTML = insights.map(insight => `
    <div class="insight-item ${insight.type}">
      <div class="insight-icon">
        <i class="${insight.icon}"></i>
      </div>
      
      <h3 class="insight-label">${insight.label}</h3>
      
      <div class="insight-value">${insight.value}</div>
      
      ${insight.change}
      
      <p class="insight-description">${insight.description}</p>
    </div>
  `).join('');

  const insightsSection = document.getElementById('insightsSection');
  const insightsTitle = document.getElementById('insightsTitle');
  
  if (insightsSection) {
    insightsSection.style.display = 'block';
  }
  
  if (insightsTitle) {
    insightsTitle.style.display = 'block';
  }

  console.log('✅ Insights renderizados correctamente');
}

// ✅ ACTUALIZADA: Función auxiliar para mostrar estado cuando no hay comparación
function getNoChangeHTML(periodsCount) {
  if (periodsCount === 1) {
    return '<div class="insight-change neutral"><span>Período único</span></div>';
  }
  return '<div class="insight-change neutral"><span>Análisis consolidado</span></div>';
}

// ✅ SIN CAMBIOS: Funciones auxiliares para cálculos permanecen igual
function calculatePercentageChangeInsights(oldValue, newValue, lowerIsBetter = false) {
  if (oldValue === null || newValue === null || typeof oldValue === 'undefined' || typeof newValue === 'undefined') {
    return null;
  }
  if (oldValue === 0) {
    if (newValue > 0) return { value: Infinity, isPositive: true, isNegative: false };
    if (newValue < 0) return { value: -Infinity, isPositive: false, isNegative: true };
    return { value: 0, isPositive: false, isNegative: false };
  }
  
  const change = ((newValue - oldValue) / oldValue) * 100;
  return {
    value: change,
    isPositive: lowerIsBetter ? change < 0 : change > 0,
    isNegative: lowerIsBetter ? change > 0 : change < 0
  };
}

function formatChange(changeObj) {
  if (!changeObj || changeObj.value === null) {
    return getNoChangeHTML(1);
  }
  if (changeObj.value === Infinity) {
    return '<div class="insight-change positive"><i class="fas fa-infinity change-icon"></i> <span>+∞%</span></div>';
  }
  if (changeObj.value === -Infinity) {
    return '<div class="insight-change negative"><i class="fas fa-infinity change-icon"></i> <span>-∞%</span></div>';
  }

  let changeClass = 'neutral';
  let icon = '';
  
  if (changeObj.isPositive) {
    changeClass = 'positive';
    icon = '<i class="fas fa-arrow-up change-icon"></i>';
  } else if (changeObj.isNegative) {
    changeClass = 'negative';
    icon = '<i class="fas fa-arrow-down change-icon"></i>';
  }

  const formattedChange = Math.abs(changeObj.value).toFixed(1);
  
  return `<div class="insight-change ${changeClass}">
    ${icon}
    <span>${formattedChange}%</span>
  </div>`;
}

// ✅ COMPLETAMENTE NUEVA: renderTable para manejar comparación de URLs
export function renderTable(pages) {
  if (elems.tableBody) elems.tableBody.innerHTML = '';
  
  // Destruir DataTable anterior si existe
  if (urlsDataTable) {
    urlsDataTable.destroy();
    urlsDataTable = null;
  }
  
  if (!pages.length) {
    if (elems.tableBody) elems.tableBody.innerHTML = '<tr><td colspan="13">No hay datos para la tabla.</td></tr>';
    if (elems.resultsSection) elems.resultsSection.style.display = 'block';
    if (elems.resultsTitle) elems.resultsTitle.style.display = 'block';
    return;
  }

  // ✅ Procesar datos de URLs
  const urlsData = processUrlsData(pages);
  const analysisType = getUrlAnalysisType(pages);
  
  console.log(`📊 Tipo de análisis URLs: ${analysisType}, URLs: ${urlsData.length}`);
  
  // ✅ Actualizar headers según el tipo
  updateUrlTableHeaders(analysisType);

  // ✅ Renderizar filas
  urlsData.forEach(row => {
    const deltaClicksClass =
      (row.delta_clicks_percent === 'Infinity' || (typeof row.delta_clicks_percent === 'number' && row.delta_clicks_percent > 0))
        ? 'positive-change'
        : (typeof row.delta_clicks_percent === 'number' && row.delta_clicks_percent < 0)
          ? 'negative-change'
          : '';
    const deltaImprClass   =
      (row.delta_impressions_percent === 'Infinity' || (typeof row.delta_impressions_percent === 'number' && row.delta_impressions_percent > 0))
        ? 'positive-change'
        : (typeof row.delta_impressions_percent === 'number' && row.delta_impressions_percent < 0)
          ? 'negative-change'
          : '';
    const deltaCtrClass    =
      (row.delta_ctr_percent === 'Infinity' || (typeof row.delta_ctr_percent === 'number' && row.delta_ctr_percent > 0))
        ? 'positive-change'
        : (typeof row.delta_ctr_percent === 'number' && row.delta_ctr_percent < 0)
          ? 'negative-change'
          : '';
    const deltaPosClass    =
      (row.delta_position_absolute === 'New' || (typeof row.delta_position_absolute === 'number' && row.delta_position_absolute < 0)) // Pos delta: negative is good (lower position)
        ? 'positive-change'
        : (row.delta_position_absolute === 'Lost' || (typeof row.delta_position_absolute === 'number' && row.delta_position_absolute > 0))
          ? 'negative-change'
          : '';

    const tr = document.createElement('tr');
    
    // ✅ Ajustar visibilidad de columnas según el tipo
    const p2ColumnsStyle = analysisType === 'single' ? 'style="display: none;"' : '';
    const deltaColumnsStyle = analysisType === 'single' ? 'style="display: none;"' : '';

    tr.innerHTML = `
      <td class="dt-body-left url-cell" title="${row.url}">${row.url}</td>
      <td>${analysisType === 'single' ? (row.clicks_p2 ?? 0).toLocaleString('es-ES') : (row.clicks_p1 ?? 0).toLocaleString('es-ES')}</td>
      <td ${p2ColumnsStyle}>${(row.clicks_p2 ?? 0).toLocaleString('es-ES')}</td>
      <td class="${deltaClicksClass}" ${deltaColumnsStyle}>${formatPercentageChange(row.delta_clicks_percent)}</td>
      <td>${analysisType === 'single' ? (row.impressions_p2 ?? 0).toLocaleString('es-ES') : (row.impressions_p1 ?? 0).toLocaleString('es-ES')}</td>
      <td ${p2ColumnsStyle}>${(row.impressions_p2 ?? 0).toLocaleString('es-ES')}</td>
      <td class="${deltaImprClass}" ${deltaColumnsStyle}>${formatPercentageChange(row.delta_impressions_percent)}</td>
      <td>${analysisType === 'single' ? (typeof row.ctr_p2 === 'number' ? row.ctr_p2.toFixed(2) + '%' : 'N/A') : (typeof row.ctr_p1 === 'number' ? row.ctr_p1.toFixed(2) + '%' : 'N/A')}</td>
      <td ${p2ColumnsStyle}>${typeof row.ctr_p2 === 'number' ? row.ctr_p2.toFixed(2) + '%' : 'N/A'}</td>
      <td class="${deltaCtrClass}" ${deltaColumnsStyle}>${formatPercentageChange(row.delta_ctr_percent, true)}</td>
      <td>${analysisType === 'single' ? formatPosition(row.position_p2) : formatPosition(row.position_p1)}</td>
      <td ${p2ColumnsStyle}>${formatPosition(row.position_p2)}</td>
      <td class="${deltaPosClass}" ${deltaColumnsStyle}>${formatPositionDelta(row.delta_position_absolute, row.position_p1, row.position_p2)}</td>
    `;
    
    if (elems.tableBody) elems.tableBody.appendChild(tr);
  });

  // === ORDENAMIENTO PERSONALIZADO PARA DATATABLES ===
  function parseSortableValue(val) {
    if (val === 'Infinity' || val === '+∞%' || val === '+∞') return Infinity;
    if (val === '-Infinity' || val === '-∞%' || val === '-∞') return -Infinity;
    if (val === 'New' || val === 'Nuevo') return 0.00001; // Valor bajo pero positivo
    if (val === 'Lost' || val === 'Perdido') return -0.00001; // Valor bajo pero negativo
    if (typeof val === 'string') {
      // ✅ CORREGIDO: Manejar separadores de miles (puntos) y porcentajes
      let num = val.replace(/[%]/g, ''); // Quitar %
      
      // ✅ Si el string contiene puntos, asumir que son separadores de miles
      // Ejemplo: "14.789" -> 14789, "1.234.567" -> 1234567
      if (num.includes('.') && !num.includes(',')) {
        // Solo puntos - interpretar como separadores de miles
        num = num.replace(/\./g, '');
      } else if (num.includes(',') && !num.includes('.')) {
        // Solo comas - interpretar como separadores de miles
        num = num.replace(/,/g, '');
      } else if (num.includes('.') && num.includes(',')) {
        // Ambos - el último carácter determina el separador decimal
        const lastDot = num.lastIndexOf('.');
        const lastComma = num.lastIndexOf(',');
        
        if (lastDot > lastComma) {
          // Punto es decimal, comas son separadores de miles: "1,234.56"
          num = num.replace(/,/g, '');
        } else {
          // Coma es decimal, puntos son separadores de miles: "1.234,56"
          num = num.replace(/\./g, '').replace(',', '.');
        }
      }
      
      let parsed = parseFloat(num);
      if (!isNaN(parsed)) return parsed;
    }
    if (typeof val === 'number') return val;
    return 0;
  }

  // ✅ NUEVO: Función específica para números con separadores de miles
  function parseThousandsSeparatedNumber(val) {
    if (typeof val === 'number') return val;
    if (typeof val !== 'string') return 0;
    
    // Limpiar el string
    let cleaned = val.toString().trim();
    
    // Si contiene solo dígitos y puntos (sin comas), tratar puntos como separadores de miles
    if (/^\d{1,3}(\.\d{3})*$/.test(cleaned)) {
      return parseInt(cleaned.replace(/\./g, ''), 10);
    }
    
    // Si contiene solo dígitos y comas (sin puntos), tratar comas como separadores de miles
    if (/^\d{1,3}(,\d{3})*$/.test(cleaned)) {
      return parseInt(cleaned.replace(/,/g, ''), 10);
    }
    
    // Usar la función general para otros casos
    return parseSortableValue(val);
  }

  if (window.DataTable && window.DataTable.ext && window.DataTable.ext.type) {
    // Para columnas de porcentaje
    DataTable.ext.type.order['percent-custom-pre'] = parseSortableValue;
    // Para columnas de posición
    DataTable.ext.type.order['position-custom-pre'] = parseSortableValue;
    // Para columnas de delta
    DataTable.ext.type.order['delta-custom-pre'] = parseSortableValue;
    // ✅ NUEVO: Para columnas de números con separadores de miles
    DataTable.ext.type.order['thousands-separated-pre'] = parseThousandsSeparatedNumber;
  }

  // ✅ Configuración de DataTable adaptada
  const columnDefs = [
    { targets: '_all', className: 'dt-body-right' },
    { targets: [0], className: 'dt-body-left' },
    // Orden personalizado para cada columna relevante
    { targets: [1,2], type: 'thousands-separated' }, // ✅ CORREGIDO: Clicks P1 y P2 con separadores de miles
    { targets: [3], type: 'delta-custom' }, // ΔClicks (%)
    { targets: [4,5], type: 'thousands-separated' }, // ✅ CORREGIDO: Impressions P1 y P2 con separadores de miles
    { targets: [6], type: 'delta-custom' }, // ΔImp. (%)
    { targets: [7,8], type: 'percent-custom' }, // CTR P1 y P2
    { targets: [9], type: 'delta-custom' }, // ΔCTR (%)
    { targets: [10,11], type: 'position-custom' }, // Pos P1 y P2
    { targets: [12], type: 'delta-custom' } // ΔPos
  ];

  // ✅ Ocultar columnas para período único
  if (analysisType === 'single') {
    columnDefs.push(
      { targets: [2, 3, 5, 6, 8, 9, 11, 12], visible: false }  // Ocultar P2 y Delta
    );
  }

  urlsDataTable = new DataTable('#resultsTable', {
    pageLength: 10,
    lengthMenu: [10, 25, 50, 100, -1],
    language: { url: 'https://cdn.datatables.net/plug-ins/1.13.6/i18n/en-GB.json' },
    scrollX: true,
    responsive: false,
    columnDefs: columnDefs,
    order: analysisType === 'single' ? [[1, 'desc']] : [[2, 'desc']], // Ordenar por clicks actuales
    drawCallback: () => {
      if (window.jQuery && window.jQuery.fn.tooltip) window.jQuery('[data-toggle="tooltip"]').tooltip();
    }
  });

  if (elems.resultsSection) elems.resultsSection.style.display = 'block';
  if (elems.resultsTitle) {
    elems.resultsTitle.style.display = 'block';
    
    // ✅ Actualizar título según el tipo
    if (analysisType === 'single') {
      elems.resultsTitle.textContent = 'Results by URL';
    } else {
      elems.resultsTitle.textContent = 'URL Comparison Between Periods';
    }
  }
}

// ✅ SIN CAMBIOS: renderTableError permanece igual
export function renderTableError() {
  if (elems.tableBody) elems.tableBody.innerHTML = '<tr><td colspan="13">Error al procesar la solicitud.</td></tr>';
  if (elems.resultsSection) elems.resultsSection.style.display = 'block';
  if (elems.resultsTitle) elems.resultsTitle.style.display = 'block';
}