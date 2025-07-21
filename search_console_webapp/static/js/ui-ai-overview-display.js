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
  displayTypologyChart(resultsContainer, data);
  
  showToast('AI Overview analysis complete', 'success');
}

// ====================================
// 📊 GRÁFICO DE TIPOLOGÍA DE CONSULTAS
// ====================================

/**
 * Muestra el gráfico de barras de tipología basado en el análisis actual
 */
export function displayTypologyChart(container, analysisData) {
  if (!container) {
    console.error('Container no encontrado para gráfico de tipología');
    return;
  }

  // Verificar que tenemos datos del análisis actual
  if (!analysisData || !analysisData.keywordResults || analysisData.keywordResults.length === 0) {
    console.log('No hay datos del análisis actual para tipología');
    return;
  }

  console.log('📊 Generando tipología dinámica con', analysisData.keywordResults.length, 'keywords');

  // Crear contenedor del gráfico
  const chartHTML = `
    <div class="ai-typology-section">
      <div class="ai-typology-header">
        <h3 class="ai-typology-title">
          <i class="fas fa-chart-bar"></i>
          Tipología de Consultas AI Overview
        </h3>
        <div class="ai-typology-subtitle">
          Basado en el análisis actual
        </div>
      </div>
      
      <div id="typologyChartContainer" class="ai-typology-container">
        <div class="typology-loading">
          <i class="fas fa-calculator"></i>
          <p>Procesando keywords del análisis actual...</p>
        </div>
      </div>
      
      <div class="typology-insights" id="typologyInsights" style="display: none;">
        <div class="typology-insights-container">
          <h4 class="typology-insights-title">
            <i class="fas fa-lightbulb"></i>
            Insights de Tipología
          </h4>
          <div class="typology-insights-grid" id="typologyInsightsContent"></div>
        </div>
      </div>
    </div>
  `;

  container.insertAdjacentHTML('beforeend', chartHTML);

  // Procesar datos dinámicamente
  processCurrentAnalysisData(analysisData.keywordResults);
}

/**
 * Procesa los datos del análisis actual y genera el gráfico
 */
function processCurrentAnalysisData(keywordResults) {
  console.log('🔍 Procesando', keywordResults.length, 'keywords para tipología');

  // Definir categorías según los nuevos criterios
  const categories = {
    '1_palabra': { label: '1 palabra', min: 1, max: 1, total: 0, conAI: 0 },
    '2_3_palabras': { label: '2-3 palabras', min: 2, max: 3, total: 0, conAI: 0 },
    '4_8_palabras': { label: '4-8 palabras', min: 4, max: 8, total: 0, conAI: 0 },
    '9_12_palabras': { label: '9-12 palabras', min: 9, max: 12, total: 0, conAI: 0 }
  };

  // Procesar cada keyword del análisis actual
  keywordResults.forEach(result => {
    const keyword = result.keyword || '';
    const wordCount = keyword.trim().split(/\s+/).length;
    const hasAI = result.ai_analysis?.has_ai_overview || false;

    console.log(`📝 Keyword: "${keyword}" - ${wordCount} palabras - AI: ${hasAI}`);

    // Clasificar en la categoría correcta
    for (const [key, category] of Object.entries(categories)) {
      if (wordCount >= category.min && wordCount <= category.max) {
        category.total++;
        if (hasAI) {
          category.conAI++;
        }
        break;
      }
    }
  });

  // Preparar datos para el gráfico
  const typologyData = {
    categories: [],
    total_queries: [],
    queries_with_ai: [],
    ai_percentage: []
  };

  // Calcular total de AIO para porcentajes relativos
  const totalWithAI = Object.values(categories).reduce((sum, cat) => sum + cat.conAI, 0);

  console.log('📊 Resumen por categorías:');
  Object.values(categories).forEach(category => {
    if (category.total > 0) { // Solo mostrar categorías con datos
      const percentageOfCategory = category.total > 0 ? (category.conAI / category.total * 100) : 0;
      const percentageOfTotal = totalWithAI > 0 ? (category.conAI / totalWithAI * 100) : 0;
      
      console.log(`   - ${category.label}: ${category.conAI}/${category.total} (${percentageOfCategory.toFixed(1)}% de la categoría, ${percentageOfTotal.toFixed(1)}% del total AIO)`);
      
      typologyData.categories.push(category.label);
      typologyData.total_queries.push(category.total);
      typologyData.queries_with_ai.push(category.conAI);
      typologyData.ai_percentage.push(percentageOfTotal); // Porcentaje relativo al total de AIO
    }
  });

  const summary = {
    total_queries_analyzed: keywordResults.length,
    total_with_ai_overview: totalWithAI,
    categories_with_data: typologyData.categories.length
  };

  // Crear el gráfico
  createTypologyChart(typologyData, summary);
  showTypologyInsights(typologyData, summary);
}

/**
 * Carga los datos de tipología desde el servidor
 */
async function loadTypologyData() {
  // Esta función ya no se usa, pero la mantengo por compatibilidad
  console.log('⚠️ loadTypologyData llamada pero se usa procesamiento dinámico');
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
      <div class="typology-empty">
        <i class="fas fa-info-circle"></i>
        <p>No se encontraron keywords con AI Overview en este análisis</p>
      </div>
    `;
    return;
  }

  // Encontrar el valor máximo para escalar las barras (usamos queries_with_ai para escalar)
  const maxValue = Math.max(...typologyData.queries_with_ai);
  const totalAIO = typologyData.queries_with_ai.reduce((sum, val) => sum + val, 0);
  
  // Crear gráfico HTML
  let chartHTML = `
    <div class="typology-chart">
      <div class="typology-chart-header">
        <h4 class="typology-chart-title">AI Overview por Tipología de Consulta</h4>
        <p class="typology-chart-subtitle">
          ${summary.total_queries_analyzed} keywords analizadas • ${totalAIO} con AI Overview
        </p>
      </div>
      
      <div class="typology-chart-bars">
  `;

  typologyData.categories.forEach((category, index) => {
    const totalQueries = typologyData.total_queries[index];
    const withAI = typologyData.queries_with_ai[index];
    const percentageOfTotal = typologyData.ai_percentage[index];
    const percentageOfCategory = totalQueries > 0 ? (withAI / totalQueries * 100) : 0;
    
    // Escalar la barra basada en la cantidad de AIO (no en total de queries)
    const barWidth = maxValue > 0 ? (withAI / maxValue) * 100 : 0;
    
    chartHTML += `
      <div class="typology-bar-group">
        <div class="typology-bar-header">
          <div class="typology-bar-label">
            <div class="typology-bar-category">${category}</div>
            <div class="typology-bar-details">
              ${totalQueries} keywords total • ${withAI} con AIO
            </div>
          </div>
          <div class="typology-bar-stats">
            <div class="typology-bar-value">${withAI}</div>
            <div class="typology-bar-percentage">
              ${percentageOfTotal.toFixed(1)}% del total AIO
            </div>
          </div>
        </div>
        
        <div class="typology-bar-container">
          <div class="typology-bar-fill" style="width: ${barWidth}%;">
            ${withAI > 0 ? `<span class="typology-bar-fill-text">${withAI}</span>` : ''}
          </div>
        </div>
        
        <div class="typology-bar-footer">
          <span>${percentageOfCategory.toFixed(1)}% de keywords de esta categoría tienen AIO</span>
          <span>Peso: ${percentageOfTotal.toFixed(1)}% del total de AIO detectado</span>
        </div>
      </div>
    `;
  });

  chartHTML += `
      </div>
      
      <div class="typology-chart-summary">
        <div class="typology-summary-grid">
          <div class="typology-summary-card with-ai">
            <div class="typology-summary-number">${totalAIO}</div>
            <div class="typology-summary-label">Keywords con AI Overview</div>
          </div>
          <div class="typology-summary-card without-ai">
            <div class="typology-summary-number">${summary.total_queries_analyzed - totalAIO}</div>
            <div class="typology-summary-label">Keywords sin AI Overview</div>
          </div>
        </div>
      </div>
      
      <div class="typology-chart-legend">
        <div class="typology-legend-content">
          <div class="typology-legend-item">
            <div class="typology-legend-color"></div>
            <span>Keywords con AI Overview</span>
          </div>
          <span class="typology-legend-separator">•</span>
          <span>Las barras muestran cantidad absoluta y peso relativo</span>
        </div>
      </div>
    </div>
  `;

  container.innerHTML = chartHTML;
  
  // Animar las barras después de que se rendericen
  setTimeout(() => {
    const bars = container.querySelectorAll('.typology-bar-fill');
    bars.forEach(bar => {
      bar.style.transform = 'scaleX(1)';
    });
  }, 100);
}

/**
 * Muestra insights de tipología basados en el análisis actual
 */
function showTypologyInsights(typologyData, summary) {
  const insightsContainer = document.getElementById('typologyInsights');
  const insightsContent = document.getElementById('typologyInsightsContent');
  
  if (!insightsContainer || !insightsContent) return;

  // Calcular insights del análisis actual
  const insights = calculateCurrentAnalysisInsights(typologyData, summary);
  
  let insightsHTML = '';
  
  insights.forEach(insight => {
    insightsHTML += `
      <div class="typology-insight-item">
        <i class="${insight.icon} typology-insight-icon" style="color: ${insight.color};"></i>
        <span class="typology-insight-text">${insight.text}</span>
      </div>
    `;
  });
  
  insightsContent.innerHTML = insightsHTML;
  insightsContainer.style.display = 'block';
}

/**
 * Calcula insights específicos del análisis actual
 */
function calculateCurrentAnalysisInsights(data, summary) {
  const insights = [];
  
  if (!data.categories || data.categories.length === 0) {
    return [{
      icon: 'fas fa-info-circle',
      color: '#3498db',
      text: 'No se detectó AI Overview en ninguna keyword de este análisis'
    }];
  }

  const totalWithAI = data.queries_with_ai.reduce((sum, val) => sum + val, 0);
  const totalAnalyzed = summary.total_queries_analyzed;
  const aiRate = (totalWithAI / totalAnalyzed * 100);

  // Insight general sobre la tasa de AI Overview
  if (aiRate >= 70) {
    insights.push({
      icon: 'fas fa-exclamation-triangle',
      color: '#e74c3c',
      text: `¡Alto riesgo! ${aiRate.toFixed(1)}% de tus keywords principales ya tienen AI Overview`
    });
  } else if (aiRate >= 40) {
    insights.push({
      icon: 'fas fa-exclamation-circle',
      color: '#f39c12',
      text: `Riesgo moderado: ${aiRate.toFixed(1)}% de tus keywords tienen AI Overview`
    });
  } else if (aiRate >= 15) {
    insights.push({
      icon: 'fas fa-chart-line',
      color: '#3498db',
      text: `${aiRate.toFixed(1)}% de tus keywords tienen AI Overview - situación manejable`
    });
  } else {
    insights.push({
      icon: 'fas fa-check-circle',
      color: '#27ae60',
      text: `Bajo impacto: solo ${aiRate.toFixed(1)}% de tus keywords tienen AI Overview`
    });
  }

  // Encontrar la categoría con mayor cantidad de AIO
  let maxAICategory = '';
  let maxAICount = 0;
  let maxAIPercentage = 0;

  data.categories.forEach((category, index) => {
    const aiCount = data.queries_with_ai[index];
    const aiPercentage = data.ai_percentage[index];
    
    if (aiCount > maxAICount) {
      maxAICount = aiCount;
      maxAICategory = category;
      maxAIPercentage = aiPercentage;
    }
  });

  if (maxAICount > 0) {
    insights.push({
      icon: 'fas fa-target',
      color: '#9b59b6',
      text: `Las keywords de "${maxAICategory}" son las más afectadas (${maxAICount} keywords, ${maxAIPercentage.toFixed(1)}% del total AIO)`
    });
  }

  // Comparar keywords cortas vs largas
  const shortCategories = ['1 palabra', '2-3 palabras'];
  const longCategories = ['4-8 palabras', '9-12 palabras'];
  
  let shortAI = 0, shortTotal = 0;
  let longAI = 0, longTotal = 0;

  data.categories.forEach((category, index) => {
    const aiCount = data.queries_with_ai[index];
    const totalCount = data.total_queries[index];
    
    if (shortCategories.includes(category)) {
      shortAI += aiCount;
      shortTotal += totalCount;
    } else if (longCategories.includes(category)) {
      longAI += aiCount;
      longTotal += totalCount;
    }
  });

  if (shortTotal > 0 && longTotal > 0) {
    const shortRate = (shortAI / shortTotal * 100);
    const longRate = (longAI / longTotal * 100);
    
    if (Math.abs(shortRate - longRate) > 15) {
      if (shortRate > longRate) {
        insights.push({
          icon: 'fas fa-compress-alt',
          color: '#e67e22',
          text: `Las keywords cortas tienen mayor riesgo de AI Overview (${shortRate.toFixed(1)}% vs ${longRate.toFixed(1)}%)`
        });
      } else {
        insights.push({
          icon: 'fas fa-expand-alt',
          color: '#16a085',
          text: `Las keywords largas son más vulnerables a AI Overview (${longRate.toFixed(1)}% vs ${shortRate.toFixed(1)}%)`
        });
      }
    }
  }

  // Recomendación estratégica
  if (totalWithAI > 0) {
    if (aiRate >= 50) {
      insights.push({
        icon: 'fas fa-lightbulb',
        color: '#f1c40f',
        text: 'Recomendación: Considera estrategias de long-tail y contenido muy específico para evitar AI Overview'
      });
    } else if (aiRate >= 25) {
      insights.push({
        icon: 'fas fa-shield-alt',
        color: '#3498db',
        text: 'Recomendación: Optimiza para aparecer como fuente en AI Overview y mejora featured snippets'
      });
    } else {
      insights.push({
        icon: 'fas fa-eye',
        color: '#27ae60',
        text: 'Recomendación: Mantén el seguimiento, tu posición actual es favorable'
      });
    }
  }

  return insights;
}

/**
 * Muestra un mensaje de error en el contenedor de tipología
 */
function showTypologyError(errorMessage) {
  const container = document.getElementById('typologyChartContainer');
  if (!container) return;

  container.innerHTML = `
    <div class="typology-empty">
      <i class="fas fa-exclamation-triangle"></i>
      <p>Error cargando tipología: ${errorMessage}</p>
      <p style="font-size: 0.9em; opacity: 0.7;">Inténtalo de nuevo más tarde</p>
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
