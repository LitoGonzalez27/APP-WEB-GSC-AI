// static/js/ui-ai-overview-display.js - Visualización de resultados AI Overview

import { escapeHtml, formatNumber, showToast } from './ui-ai-overview-utils.js';
import { showAIDetailsModalImproved } from './ui-ai-overview-modals.js';
import { openSerpModal } from './ui-serp-modal.js'; // IMPORTANTE: Importar la función del modal SERP

export function displayAIOverviewResults(data) {
  const resultsContainer = document.getElementById('aiOverviewResultsContainer');
  if (!resultsContainer) {
    console.error('Container aiOverviewResultsContainer not found');
    return;
  }

  // Limpiar resultados anteriores antes de mostrar los nuevos
  resultsContainer.innerHTML = '';

  // Mostrar sección AI Overview
  const aiSection = document.getElementById('aiOverviewSection');
  if (aiSection) aiSection.style.display = 'block';

  // Mostrar resumen
  displaySummary(data.summary, resultsContainer);
  
  // Mostrar resultados detallados
  displayDetailedResults(data.keywordResults, resultsContainer);
  
  // ✅ NUEVO: Mostrar gráfico de tipología
  displayTypologyChart(resultsContainer);
  
  showToast('AI Overview analysis complete', 'success');
}

// ====================================
// 📊 GRÁFICO DE TIPOLOGÍA DE CONSULTAS
// ====================================

/**
 * Muestra el gráfico de barras de tipología de consultas
 */
export function displayTypologyChart(container) {
  if (!container) {
    console.error('Container no encontrado para gráfico de tipología');
    return;
  }

  // Crear contenedor del gráfico
  const chartHTML = `
    <div class="ai-typology-section" style="margin-top: 2em;">
      <div class="ai-section-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5em;">
        <h3 style="color: var(--primary-color); margin: 0;">
          <i class="fas fa-chart-bar"></i> Tipología de Consultas AI Overview
        </h3>
        <button id="refreshTypologyBtn" class="btn-secondary" style="padding: 0.5em 1em; font-size: 0.9em;">
          <i class="fas fa-sync-alt"></i> Actualizar
        </button>
      </div>
      
      <div id="typologyChartContainer" style="background: var(--card-background); border-radius: 8px; padding: 1.5em; border: 1px solid var(--border-color);">
        <div class="loading-placeholder" style="text-align: center; padding: 2em; color: var(--text-secondary);">
          <i class="fas fa-spinner fa-spin"></i> Cargando datos de tipología...
        </div>
      </div>
      
      <div class="typology-insights" id="typologyInsights" style="margin-top: 1em; display: none;">
        <div style="background: rgba(52, 152, 219, 0.1); border-left: 4px solid #3498db; padding: 1em; border-radius: 4px;">
          <h4 style="margin: 0 0 0.5em 0; color: #3498db;">💡 Insights de Tipología</h4>
          <div id="typologyInsightsContent"></div>
        </div>
      </div>
    </div>
  `;

  container.insertAdjacentHTML('beforeend', chartHTML);

  // Cargar datos y crear gráfico
  loadTypologyData();

  // Event listener para el botón de refresh
  const refreshBtn = document.getElementById('refreshTypologyBtn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => {
      refreshBtn.disabled = true;
      refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Actualizando...';
      
      loadTypologyData().finally(() => {
        refreshBtn.disabled = false;
        refreshBtn.innerHTML = '<i class="fas fa-sync-alt"></i> Actualizar';
      });
    });
  }
}

/**
 * Carga los datos de tipología desde el servidor
 */
async function loadTypologyData() {
  try {
    const response = await fetch('/api/ai-overview-typology');
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    const data = await response.json();
    
    if (data.success) {
      createTypologyChart(data.typology_data, data.summary);
      showTypologyInsights(data.typology_data, data.summary);
    } else {
      throw new Error(data.error || 'Error desconocido');
    }
    
  } catch (error) {
    console.error('Error cargando datos de tipología:', error);
    showTypologyError(error.message);
  }
}

/**
 * Crea el gráfico de barras de tipología
 */
function createTypologyChart(typologyData, summary) {
  const container = document.getElementById('typologyChartContainer');
  if (!container) return;

  // Si no hay datos, mostrar mensaje
  if (!typologyData.categories || typologyData.categories.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; padding: 2em; color: var(--text-secondary);">
        <i class="fas fa-info-circle" style="font-size: 2em; margin-bottom: 0.5em; opacity: 0.5;"></i>
        <p>No hay datos de tipología disponibles</p>
        <p style="font-size: 0.9em; opacity: 0.7;">Ejecuta algunos análisis de AI Overview para ver estadísticas</p>
      </div>
    `;
    return;
  }

  // Crear gráfico HTML (usando CSS para las barras)
  let chartHTML = `
    <div class="typology-chart">
      <div class="chart-header" style="margin-bottom: 1.5em;">
        <h4 style="margin: 0; color: var(--text-color);">Distribución por Número de Términos</h4>
        <p style="margin: 0.5em 0 0 0; font-size: 0.9em; color: var(--text-secondary);">
          Total: ${summary.total_queries_analyzed} consultas analizadas
        </p>
      </div>
      
      <div class="chart-bars" style="space-y: 1em;">
  `;

  // Calcular el valor máximo para escalar las barras
  const maxValue = Math.max(...typologyData.total_queries);

  typologyData.categories.forEach((category, index) => {
    const total = typologyData.total_queries[index];
    const withAI = typologyData.queries_with_ai[index];
    const percentage = typologyData.ai_percentage[index];
    
    const barWidth = (total / maxValue) * 100;
    const aiBarWidth = (withAI / maxValue) * 100;
    
    chartHTML += `
      <div class="chart-bar-group" style="margin-bottom: 1.5em;">
        <div class="bar-label" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5em;">
          <span style="font-weight: 500; color: var(--text-color);">${category}</span>
          <span style="font-size: 0.9em; color: var(--text-secondary);">
            ${withAI}/${total} (${percentage.toFixed(1)}%)
          </span>
        </div>
        
        <div class="bar-container" style="position: relative; height: 24px; background: var(--border-color); border-radius: 12px; overflow: hidden;">
          <div class="bar-total" style="
            width: ${barWidth}%; 
            height: 100%; 
            background: linear-gradient(90deg, #e74c3c, #c0392b); 
            border-radius: 12px;
            position: relative;
          "></div>
          <div class="bar-ai" style="
            width: ${aiBarWidth}%; 
            height: 100%; 
            background: linear-gradient(90deg, #3498db, #2980b9); 
            border-radius: 12px;
            position: absolute;
            top: 0;
            left: 0;
          "></div>
        </div>
        
        <div class="bar-stats" style="display: flex; justify-content: space-between; margin-top: 0.3em; font-size: 0.8em; color: var(--text-secondary);">
          <span>Total: ${total}</span>
          <span>Con AI: ${withAI}</span>
        </div>
      </div>
    `;
  });

  chartHTML += `
      </div>
      
      <div class="chart-legend" style="margin-top: 1.5em; padding-top: 1em; border-top: 1px solid var(--border-color);">
        <div style="display: flex; gap: 2em; justify-content: center; font-size: 0.9em;">
          <div style="display: flex; align-items: center; gap: 0.5em;">
            <div style="width: 16px; height: 16px; background: linear-gradient(90deg, #e74c3c, #c0392b); border-radius: 8px;"></div>
            <span>Total de consultas</span>
          </div>
          <div style="display: flex; align-items: center; gap: 0.5em;">
            <div style="width: 16px; height: 16px; background: linear-gradient(90deg, #3498db, #2980b9); border-radius: 8px;"></div>
            <span>Con AI Overview</span>
          </div>
        </div>
      </div>
    </div>
  `;

  container.innerHTML = chartHTML;
}

/**
 * Muestra insights de tipología
 */
function showTypologyInsights(typologyData, summary) {
  const insightsContainer = document.getElementById('typologyInsights');
  const insightsContent = document.getElementById('typologyInsightsContent');
  
  if (!insightsContainer || !insightsContent) return;

  // Calcular insights
  const insights = calculateTypologyInsights(typologyData, summary);
  
  let insightsHTML = '<div style="display: grid; gap: 0.5em;">';
  
  insights.forEach(insight => {
    insightsHTML += `
      <div style="display: flex; align-items: center; gap: 0.5em;">
        <i class="${insight.icon}" style="color: ${insight.color}; width: 16px;"></i>
        <span>${insight.text}</span>
      </div>
    `;
  });
  
  insightsHTML += '</div>';
  
  insightsContent.innerHTML = insightsHTML;
  insightsContainer.style.display = 'block';
}

/**
 * Calcula insights automáticos de los datos de tipología
 */
function calculateTypologyInsights(data, summary) {
  const insights = [];
  
  if (!data.categories || data.categories.length === 0) {
    return [{ 
      icon: 'fas fa-info-circle', 
      color: '#3498db', 
      text: 'Sin datos suficientes para generar insights' 
    }];
  }

  // Encontrar la categoría con mayor porcentaje de AI Overview
  let maxAIPercentage = 0;
  let maxAICategory = '';
  data.ai_percentage.forEach((percentage, index) => {
    if (percentage > maxAIPercentage) {
      maxAIPercentage = percentage;
      maxAICategory = data.categories[index];
    }
  });

  if (maxAIPercentage > 0) {
    insights.push({
      icon: 'fas fa-trophy',
      color: '#f39c12',
      text: `${maxAICategory} tienen la mayor probabilidad de AI Overview (${maxAIPercentage.toFixed(1)}%)`
    });
  }

  // Encontrar la categoría con más volumen
  let maxVolume = 0;
  let maxVolumeCategory = '';
  data.total_queries.forEach((total, index) => {
    if (total > maxVolume) {
      maxVolume = total;
      maxVolumeCategory = data.categories[index];
    }
  });

  if (maxVolume > 0) {
    insights.push({
      icon: 'fas fa-chart-line',
      color: '#27ae60',
      text: `${maxVolumeCategory} representan el mayor volumen (${maxVolume} consultas)`
    });
  }

  // Calcular promedio de AI Overview
  const totalQueries = data.total_queries.reduce((sum, val) => sum + val, 0);
  const totalWithAI = data.queries_with_ai.reduce((sum, val) => sum + val, 0);
  const averageAIRate = totalQueries > 0 ? (totalWithAI / totalQueries * 100) : 0;

  insights.push({
    icon: 'fas fa-percentage',
    color: '#8e44ad',
    text: `Promedio general de AI Overview: ${averageAIRate.toFixed(1)}%`
  });

  // Insight sobre consultas largas vs cortas
  if (data.categories.length >= 2) {
    const shortQueries = data.ai_percentage[0] || 0; // 1 término
    const longQueries = data.ai_percentage[data.ai_percentage.length - 1] || 0; // Última categoría
    
    if (shortQueries > longQueries) {
      insights.push({
        icon: 'fas fa-arrow-up',
        color: '#e74c3c',
        text: 'Las consultas cortas tienden a generar más AI Overview'
      });
    } else if (longQueries > shortQueries) {
      insights.push({
        icon: 'fas fa-arrow-down',
        color: '#3498db',
        text: 'Las consultas largas tienden a generar más AI Overview'
      });
    }
  }

  return insights;
}

/**
 * Muestra error en el gráfico de tipología
 */
function showTypologyError(errorMessage) {
  const container = document.getElementById('typologyChartContainer');
  if (!container) return;

  container.innerHTML = `
    <div style="text-align: center; padding: 2em; color: var(--error-color);">
      <i class="fas fa-exclamation-triangle" style="font-size: 2em; margin-bottom: 0.5em;"></i>
      <p>Error cargando datos de tipología</p>
      <p style="font-size: 0.9em; opacity: 0.7;">${errorMessage}</p>
      <button onclick="loadTypologyData()" class="btn-primary" style="margin-top: 1em;">
        <i class="fas fa-retry"></i> Reintentar
      </button>
    </div>
  `;
}

function displaySummary(summary, container) {
  // Calcular % de visibilidad en AIO
  const keywordsWithAIO = summary.keywords_with_ai_overview || 0;
  const mentionsInAIO = summary.keywords_as_ai_source || 0;
  const totalKeywords = summary.total_keywords_analyzed || 0;
  const visibilityPercentage = keywordsWithAIO > 0 ? ((mentionsInAIO / keywordsWithAIO) * 100).toFixed(1) : '0.0';
  
  // Calcular peso AIO en SERPs
  const pesoAIOPercentage = totalKeywords > 0 ? ((keywordsWithAIO / totalKeywords) * 100).toFixed(1) : '0.0';
  
  const summaryHTML = `
    <div class="ai-overview-summary" style="
      /* Eliminamos el background linear-gradient y el border directos
         para que el estilo de la sección principal glass-effect sea dominante */
      padding: 1.5em;
      margin-bottom: 2em;
      border-radius: 12px; /* Mantenemos el border-radius para las métricas internas */
    ">
      <h3 style="text-align: center; color: var(--heading); margin-bottom: 1em;">
        <i class="fas fa-chart-line"></i> AI Overview Analysis Summary
      </h3>
      <div style="
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 1em;
        margin-bottom: 1em;
      ">
        <div class="summary-metric" style="
          text-align: center; 
          padding: 1em; 
          background: var(--card-bg); /* Usar variable CSS para el fondo de la tarjeta */
          border-radius: 8px;
          border: 1px solid var(--border-color); /* Añadir borde */
          transition: transform 0.2s ease, box-shadow 0.2s ease;
        ">
          <div style="font-size: 2em; font-weight: bold; color: var(--cta-bg);">
            ${formatNumber(totalKeywords)}
          </div>
          <div style="color: var(--text-color); font-size: 0.9em; opacity: 0.7;">Keywords Analyzed</div>
        </div>
        <div class="summary-metric" style="
          text-align: center; 
          padding: 1em; 
          background: var(--card-bg); 
          border-radius: 8px;
          border: 1px solid var(--border-color);
          transition: transform 0.2s ease, box-shadow 0.2s ease;
        ">
          <div style="font-size: 2em; font-weight: bold; color: var(--error-color);">
            ${formatNumber(keywordsWithAIO)}
          </div>
          <div style="color: var(--text-color); font-size: 0.9em; opacity: 0.7;">With AI Overview</div>
        </div>
        <div class="summary-metric" style="
          text-align: center; 
          padding: 1em; 
          background: var(--card-bg); 
          border-radius: 8px;
          border: 1px solid var(--border-color);
          transition: transform 0.2s ease, box-shadow 0.2s ease;
        ">
          <div style="font-size: 2em; font-weight: bold; color: ${parseFloat(pesoAIOPercentage) >= 75 ? 'var(--error-color)' : parseFloat(pesoAIOPercentage) >= 50 ? 'var(--warning-color)' : parseFloat(pesoAIOPercentage) >= 25 ? 'var(--info-color)' : 'var(--success-color)'};">
            ${pesoAIOPercentage}%
          </div>
          <div style="color: var(--text-color); font-size: 0.9em; opacity: 0.7;">AIO Weight in SERPs</div>
        </div>
        <div class="summary-metric" style="
          text-align: center; 
          padding: 1em; 
          background: var(--card-bg); 
          border-radius: 8px;
          border: 1px solid var(--border-color);
          transition: transform 0.2s ease, box-shadow 0.2s ease;
        ">
          <div style="font-size: 2em; font-weight: bold; color: var(--warning-color);">
            ${formatNumber(mentionsInAIO)}
          </div>
          <div style="color: var(--text-color); font-size: 0.9em; opacity: 0.7;">Mentions of Your Brand</div>
        </div>
        <div class="summary-metric" style="
          text-align: center; 
          padding: 1em; 
          background: var(--card-bg); 
          border-radius: 8px;
          border: 1px solid var(--border-color);
          transition: transform 0.2s ease, box-shadow 0.2s ease;
        ">
          <div style="font-size: 2em; font-weight: bold; color: ${parseFloat(visibilityPercentage) >= 50 ? 'var(--success-color)' : parseFloat(visibilityPercentage) >= 25 ? 'var(--warning-color)' : 'var(--error-color)'};">
            ${visibilityPercentage}%
          </div>
          <div style="color: var(--text-color); font-size: 0.9em; opacity: 0.7;">% Visibility in AIO</div>
        </div>
      </div>
    </div>
  `;
  
  container.innerHTML = summaryHTML; 
}

function displayDetailedResults(results, container) {
  // Eliminar tabla previa si existe
  const oldTable = document.getElementById('aiOverviewTable');
  if (oldTable) oldTable.parentNode.removeChild(oldTable);

  if (!results || results.length === 0) {
    container.insertAdjacentHTML('beforeend', `
      <div style="text-align: center; padding: 2em; color: var(--text-color); opacity: 0.7;">
        <i class="fas fa-info-circle" style="font-size: 2em; margin-bottom: 0.5em;"></i>
        <p>No se encontraron resultados detallados para mostrar.</p>
      </div>
    `);
    return;
  }

  // Estructura de tabla igual a Keywords
  const tableHTML = `
    <div class="ai-results-table-container" style="margin-top: 2em;">
      <h3 style="text-align: center; margin-bottom: 1em; color: var(--heading);">
        <i class="fas fa-table"></i> Detailed Results by Keyword
      </h3>
      <div class="table-responsive-container">
        <table id="aiOverviewTable" class="dataTable display" style="width:100%">
          <thead>
            <tr>
              <th style="width: 60px;">View SERP</th>
              <th>Keyword</th>
              <th>With AIO</th>
              <th>Organic Position</th>
              <th>Your Domain in AIO</th>
              <th>AIO Position</th>
            </tr>
          </thead>
          <tbody>
            ${results.map((result, index) => createResultRowAIO(result)).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
  container.insertAdjacentHTML('beforeend', tableHTML);

  // Inicializar DataTable con las mismas opciones que Keywords
  if (window.DataTable) {
    new DataTable('#aiOverviewTable', {
      pageLength: 10,
      lengthMenu: [10, 25, 50, 100, -1],
      language: { url: 'https://cdn.datatables.net/plug-ins/1.13.6/i18n/en-GB.json' },
      scrollX: true,
      responsive: false,
      autoWidth: false,
      sScrollX: "100%",
      sScrollXInner: "1300px",
      columnDefs: [
        { targets: 0, orderable: false, className: 'dt-body-center', width: '60px' },
        { targets: 1, className: 'dt-body-left kw-cell', width: '250px' },
        { targets: 2, className: 'dt-body-center', width: '120px' },
        { targets: 3, className: 'dt-body-center', width: '150px' },
        { targets: 4, className: 'dt-body-center', width: '180px' },
        { targets: 5, className: 'dt-body-center', width: '130px' }
      ],
      order: [[2, 'desc']],
      drawCallback: () => {
        if (window.jQuery && window.jQuery.fn.tooltip) window.jQuery('[data-toggle="tooltip"]').tooltip();
      },
      initComplete: () => {
        // Forzar ancho del contenedor scroll interno
        const scrollHeadInner = document.querySelector('#aiOverviewTable_wrapper .dataTables_scrollHeadInner');
        if (scrollHeadInner) {
          scrollHeadInner.style.width = '1300px';
          scrollHeadInner.style.boxSizing = 'content-box';
          
          // También forzar el ancho de la tabla dentro del contenedor
          const innerTable = scrollHeadInner.querySelector('table');
          if (innerTable) {
            innerTable.style.width = '1300px';
            innerTable.style.marginLeft = '0px';
          }
        }
        
        // Forzar anchos después de la inicialización
        const table = document.getElementById('aiOverviewTable');
        if (table) {
          const headers = table.querySelectorAll('thead th');
          const widths = ['60px', '250px', '120px', '150px', '180px', '130px'];
          headers.forEach((header, index) => {
            if (widths[index]) {
              header.style.width = widths[index];
              header.style.minWidth = widths[index];
              header.style.maxWidth = widths[index];
            }
          });
          
          // También forzar en las celdas del cuerpo
          const rows = table.querySelectorAll('tbody tr');
          rows.forEach(row => {
            const cells = row.querySelectorAll('td');
            cells.forEach((cell, index) => {
              if (widths[index]) {
                cell.style.width = widths[index];
                cell.style.minWidth = widths[index];
                cell.style.maxWidth = widths[index];
              }
            });
          });
        }
      }
    });
    // Aplicar mejoras visuales
    if (window.tableEnhancements && window.tableEnhancements.enhance) {
      window.tableEnhancements.enhance('aiOverviewTable');
    }
  }

  // Listeners para iconos SERP
  setupTableEventListenersAIO();
}

// Nueva función para crear filas con la misma estructura visual que Keywords
function createResultRowAIO(result) {
  const aiAnalysis = result.ai_analysis || {};
  const isDomainInAI = aiAnalysis.domain_is_ai_source || false;
  const hasAIOverview = aiAnalysis.has_ai_overview || false;
  const organicPosition = (result.site_position !== null && result.site_position !== undefined)
    ? result.site_position
    : 'Not found';
  const aiPosition = (aiAnalysis.domain_ai_source_position !== null && aiAnalysis.domain_ai_source_position !== undefined)
    ? aiAnalysis.domain_ai_source_position
    : 'No';

  return `
    <tr>
      <td class="dt-body-center">
        <i class="fas fa-search serp-icon"
           data-keyword="${escapeHtml(result.keyword)}"
           data-url="${escapeHtml(result.url || '')}"
           title="Ver SERP para ${escapeHtml(result.keyword)}"
           style="cursor:pointer;"></i>
      </td>
      <td class="dt-body-left kw-cell">${escapeHtml(result.keyword || 'N/A')}</td>
      <td>${hasAIOverview ? '<span class="negative-change">Yes</span>' : '<span class="positive-change">No</span>'}</td>
      <td>${typeof organicPosition === 'number' ? (organicPosition === 0 ? '#0 (Featured)' : `#${organicPosition}`) : `${organicPosition}`}</td>
      <td>${isDomainInAI ? '<span class="positive-change">Yes</span>' : '<span class="negative-change">No</span>'}</td>
      <td>${(typeof aiPosition === 'number' && aiPosition > 0) ? `#${aiPosition}` : 'No'}</td>
    </tr>
  `;
}

// Listeners para la nueva tabla (iconos SERP)
function setupTableEventListenersAIO() {
  document.querySelectorAll('#aiOverviewTable .serp-icon').forEach(icon => {
    icon.addEventListener('click', () => openSerpModal(icon.dataset.keyword, icon.dataset.url));
    icon.addEventListener('mouseenter', () => icon.classList.add('hover'));
    icon.addEventListener('mouseleave', () => icon.classList.remove('hover'));
  });
}
