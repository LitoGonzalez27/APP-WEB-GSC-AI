// static/js/ui-ai-overview-display.js - Visualización de resultados AI Overview

import { escapeHtml, formatNumber, showToast } from './ui-ai-overview-utils.js';
import { showAIDetailsModalImproved } from './ui-ai-overview-modals.js';
import { openSerpModal } from './ui-serp-modal.js'; // IMPORTANTE: Importar la función del modal SERP
import { createAIOverviewGridTable } from './ui-ai-overview-gridjs.js'; // Grid.js table
import { createDetailedResultsGridTable } from './ui-detailed-results-gridjs.js'; // Detailed Grid.js table

// ====================================
// 🏷️ KEYWORD DIAGNOSTIC CLASSIFICATION
// ====================================

const CTR_BENCHMARKS = {
  1: 0.280, 2: 0.155, 3: 0.110, 4: 0.080, 5: 0.060,
  6: 0.045, 7: 0.035, 8: 0.028, 9: 0.024, 10: 0.020
};

// SERP features that absorb organic CTR (estimated % reduction on organic CTR)
// Based on industry studies: each feature pushes organic results down and captures clicks
const SERP_FEATURE_CTR_IMPACT = {
  featured_snippet:   { label: 'Featured Snippet',   icon: 'fa-star',          impact: 0.12, color: '#ffc107' },
  people_also_ask:    { label: 'People Also Ask',    icon: 'fa-question-circle', impact: 0.05, color: '#17a2b8' },
  knowledge_graph:    { label: 'Knowledge Graph',    icon: 'fa-info-circle',   impact: 0.08, color: '#6f42c1' },
  video_results:      { label: 'Video Results',      icon: 'fa-video',         impact: 0.06, color: '#e83e8c' },
  images_results:     { label: 'Image Results',      icon: 'fa-images',        impact: 0.03, color: '#20c997' },
  shopping_results:   { label: 'Shopping Results',   icon: 'fa-shopping-cart', impact: 0.08, color: '#fd7e14' },
  local_results:      { label: 'Local Pack',         icon: 'fa-map-marker-alt', impact: 0.07, color: '#28a745' },
  news_results:       { label: 'News Results',       icon: 'fa-newspaper',     impact: 0.04, color: '#6c757d' },
  ads:                { label: 'Paid Ads',           icon: 'fa-ad',            impact: 0.10, color: '#dc3545' },
  related_questions:  { label: 'Related Questions',  icon: 'fa-comments',      impact: 0.04, color: '#007bff' }
};

/**
 * Parses the serp_features string array from backend into structured data.
 * Backend sends: ["featured_snippet: presente", "people_also_ask: 4 elementos", ...]
 * @param {Array<string>} serpFeatures - Array of feature strings
 * @returns {Array<{key: string, label: string, icon: string, impact: number, color: string}>}
 */
function parseSerpFeatures(serpFeatures) {
  if (!serpFeatures || !Array.isArray(serpFeatures)) return [];
  const detected = [];
  for (const featureStr of serpFeatures) {
    const key = featureStr.split(':')[0].trim();
    const meta = SERP_FEATURE_CTR_IMPACT[key];
    if (meta) {
      detected.push({ key, ...meta });
    }
  }
  return detected;
}

const DIAGNOSTIC_CATEGORIES = {
  max_impact: {
    id: 'max_impact',
    label: 'Maximum Impact',
    icon: 'fa-bolt',
    description: 'Top 3 organic position with AI Overview above — your domain is NOT cited. Highest risk of click loss.',
    color: '#dc3545',
    dark: true
  },
  paradox: {
    id: 'paradox',
    label: 'Position Paradox',
    icon: 'fa-arrows-alt-v',
    description: 'Position improved but clicks dropped. AI Overview is likely absorbing the clicks you should be gaining.',
    color: '#fd7e14',
    dark: true
  },
  impacted: {
    id: 'impacted',
    label: 'Impacted by AIO',
    icon: 'fa-exclamation-triangle',
    description: 'Clicks dropped while position stayed stable. AI Overview is the most probable cause.',
    color: '#ffc107',
    dark: false
  },
  missed: {
    id: 'missed',
    label: 'Missed Opportunity',
    icon: 'fa-bullseye',
    description: 'A competitor appears as source in AI Overview but your domain does not. You could gain visibility here.',
    color: '#6f42c1',
    dark: true
  },
  visibility: {
    id: 'visibility',
    label: 'Visibility w/o Click',
    icon: 'fa-eye',
    description: 'Your domain IS cited in AI Overview but clicks still dropped. Brand visibility maintained, traffic absorbed.',
    color: '#17a2b8',
    dark: false
  },
  protected: {
    id: 'protected',
    label: 'Protected',
    icon: 'fa-shield-alt',
    description: 'Cited in AI Overview and clicks stable or growing. Best-case scenario — AIO works in your favor.',
    color: '#28a745',
    dark: false
  },
  no_impact: {
    id: 'no_impact',
    label: 'No AI Impact',
    icon: 'fa-check-circle',
    description: 'No AI Overview detected. Organic performance is not affected by AIO for these keywords.',
    color: '#6c757d',
    dark: false
  }
};

/**
 * Classifies all keywords into diagnostic categories.
 * Priority order ensures mutual exclusivity (first match wins).
 * @param {Array} keywordResults - All keyword results
 * @param {Array} competitorDomains - List of competitor domain strings
 * @returns {{ categories: Object, enrichedResults: Array }}
 */
function classifyKeywords(keywordResults, competitorDomains = []) {
  const categories = {};
  Object.keys(DIAGNOSTIC_CATEGORIES).forEach(id => {
    categories[id] = { count: 0, percentage: 0, keywords: [] };
  });

  const enrichedResults = keywordResults.map(result => {
    const ai = result.ai_analysis || {};
    const hasAIO = ai.has_ai_overview || false;
    const isDomainSource = ai.domain_is_ai_source || false;

    // m1 = previous period, m2 = current period
    const clicksM1 = result.clicks_m1 || 0;
    const clicksM2 = result.clicks_m2 || 0;
    const deltaClicks = result.delta_clicks_absolute != null
      ? result.delta_clicks_absolute
      : (clicksM2 - clicksM1);

    const posM1 = result.position_m1;
    const posM2 = result.position_m2;
    const posDelta = (typeof posM1 === 'number' && typeof posM2 === 'number')
      ? posM2 - posM1
      : null;

    const anyCompetitorIsSource = _checkCompetitorIsSource(result, competitorDomains);

    let category = 'no_impact';

    if (hasAIO) {
      // Priority 1: Maximum Impact — top 3 organic + AIO + not cited
      if (typeof posM2 === 'number' && posM2 > 0 && posM2 <= 3 && !isDomainSource) {
        category = 'max_impact';
      }
      // Priority 2: Paradox — position improved but clicks dropped
      else if (deltaClicks < 0 && posDelta !== null && posDelta < 0) {
        category = 'paradox';
      }
      // Priority 3: Impacted — clicks dropped, position stable
      else if (deltaClicks < 0 && (posDelta === null || Math.abs(posDelta) < 3)) {
        category = 'impacted';
      }
      // Priority 4: Missed Opportunity — competitor is source, you are not
      else if (!isDomainSource && anyCompetitorIsSource) {
        category = 'missed';
      }
      // Priority 5: Visibility Without Click — cited but clicks dropped
      else if (deltaClicks < 0 && isDomainSource) {
        category = 'visibility';
      }
      // Priority 6: Protected — cited and clicks stable/growing
      else if (deltaClicks >= 0 && isDomainSource) {
        category = 'protected';
      }
      // Fallback for AIO keywords that don't match specific patterns
      else {
        category = 'impacted';
      }
    }

    result._diagnostic = {
      category: category,
      label: DIAGNOSTIC_CATEGORIES[category].label
    };

    categories[category].keywords.push(result);
    categories[category].count++;

    return result;
  });

  const total = enrichedResults.length;
  Object.keys(categories).forEach(id => {
    categories[id].percentage = total > 0
      ? ((categories[id].count / total) * 100).toFixed(1)
      : '0.0';
  });

  return { categories, enrichedResults };
}

/**
 * Returns expected CTR for a given organic position (industry benchmark).
 * @param {number} position - Organic position (1-based)
 * @returns {number|null} Expected CTR as decimal (0.280 = 28%)
 */
function getExpectedCTR(position) {
  if (position === null || position === undefined || position <= 0) return null;
  const rounded = Math.min(Math.round(position), 10);
  return CTR_BENCHMARKS[rounded] || null;
}

/**
 * Enriches a keyword result with CTR benchmark analysis.
 * Mutates result by adding _ctr_analysis field.
 * @param {Object} result - Single keyword result
 * @returns {Object} The same result with _ctr_analysis added
 */
function enrichWithCTRAnalysis(result) {
  const position = result.position_m2; // Current period position from GSC
  const impressions = result.impressions_m2 || result.impressions_m1 || 0;

  // CTR from GSC: could be a percentage (5.2) or decimal (0.052)
  let actualCTR = result.ctr_m2 != null ? result.ctr_m2 : null;
  if (actualCTR !== null && actualCTR > 1) {
    actualCTR = actualCTR / 100; // Normalize percentage to decimal
  }

  const expectedCTR = getExpectedCTR(position);

  // Parse SERP features for this keyword
  const serpFeatures = parseSerpFeatures(result.serp_features);
  const hasAIO = result.ai_analysis?.has_ai_overview || false;

  // Calculate adjusted expected CTR considering all SERP features
  let adjustedExpectedCTR = expectedCTR;
  let totalSerpImpact = 0;
  if (expectedCTR !== null && serpFeatures.length > 0) {
    // Sum individual feature impacts (capped at 40% total reduction)
    totalSerpImpact = serpFeatures.reduce((sum, f) => sum + f.impact, 0);
    totalSerpImpact = Math.min(totalSerpImpact, 0.40);
    // Apply reduction: if baseline is 15.5% and SERP features absorb 20%, new expected = 15.5% * (1 - 0.20)
    adjustedExpectedCTR = expectedCTR * (1 - totalSerpImpact);
  }

  if (expectedCTR === null || actualCTR === null || impressions === 0) {
    result._ctr_analysis = {
      expected_ctr: expectedCTR,
      adjusted_expected_ctr: adjustedExpectedCTR,
      actual_ctr: actualCTR,
      ctr_gap: null,
      ctr_gap_adjusted: null,
      clicks_absorbed: null,
      clicks_absorbed_by_serp_features: null,
      serp_features: serpFeatures,
      serp_features_impact: totalSerpImpact
    };
    return result;
  }

  // Full gap (vs clean SERP benchmark)
  const ctrGap = expectedCTR - actualCTR;
  const clicksAbsorbed = Math.round(ctrGap * impressions);

  // Adjusted gap (remaining gap AFTER accounting for SERP features)
  const ctrGapAdjusted = adjustedExpectedCTR - actualCTR;
  // Clicks absorbed by non-AIO SERP features = difference between full and adjusted
  const clicksAbsorbedBySerpFeatures = Math.max(0, Math.round((expectedCTR - adjustedExpectedCTR) * impressions));

  result._ctr_analysis = {
    expected_ctr: expectedCTR,
    adjusted_expected_ctr: adjustedExpectedCTR,
    actual_ctr: actualCTR,
    ctr_gap: ctrGap,
    ctr_gap_adjusted: ctrGapAdjusted,
    clicks_absorbed: Math.max(0, clicksAbsorbed),
    clicks_absorbed_by_serp_features: clicksAbsorbedBySerpFeatures,
    serp_features: serpFeatures,
    serp_features_impact: totalSerpImpact
  };

  return result;
}

/**
 * Checks if any competitor domain appears as a source in the AI Overview references.
 */
function _checkCompetitorIsSource(result, competitorDomains) {
  if (!competitorDomains || competitorDomains.length === 0) return false;
  const references = result.ai_analysis?.debug_info?.references_found || [];
  if (references.length === 0) return false;

  for (const domain of competitorDomains) {
    const norm = domain.toLowerCase().replace('www.', '');
    for (const ref of references) {
      const link = (ref.link || '').toLowerCase();
      const source = (ref.source || '').toLowerCase();
      if (link.includes(norm) || source.includes(norm)) return true;
    }
  }
  return false;
}

/**
 * Extracts competitor domain list from analysis data.
 */
function _getCompetitorDomains(data) {
  const competitorAnalysis = data.summary?.competitor_analysis || [];
  return competitorAnalysis.slice(1).map(comp => comp.domain);
}

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

  // Obtener el keyword count del selector
  const keywordCountSelect = document.getElementById('keywordCountSelect');
  const selectedKeywordCount = keywordCountSelect ? parseInt(keywordCountSelect.value) : null;

  // 1️⃣ Mostrar resumen
  displaySummary(data.summary, resultsContainer, selectedKeywordCount);

  // 🆕 1.5️⃣ Enrich all keyword data with diagnostic classification + CTR analysis
  const competitorDomains = _getCompetitorDomains(data);
  const { categories, enrichedResults } = classifyKeywords(data.keywordResults, competitorDomains);
  enrichedResults.forEach(r => enrichWithCTRAnalysis(r));
  data.keywordResults = enrichedResults;

  // 🆕 Store globally so the SERP modal can access AI analysis data per keyword
  window._aioKeywordResults = enrichedResults;
  window._aioCompetitorDomains = competitorDomains;
  window._aioMostCitedUrls = data.summary?.most_cited_urls || [];
  window._aioManualCompetitors = data.summary?.manual_competitor_domains || [];

  console.log('🏷️ Diagnostic classification complete:', Object.entries(categories)
    .filter(([_, v]) => v.count > 0)
    .map(([k, v]) => `${k}: ${v.count}`)
    .join(', ')
  );

  // 🆕 1.6️⃣ CTR benchmark analysis summary — removed per design decision
  // displayCTRAnalysisSummary(enrichedResults, resultsContainer);

  // 2️⃣ Mostrar análisis de competidores si hay datos
  if (data.summary && data.summary.competitor_analysis) {
    displayCompetitorResults(data.summary.competitor_analysis, resultsContainer, {
      mostCitedUrls: data.summary.most_cited_urls || [],
      manualDomains: data.summary.manual_competitor_domains || []
    });
  }

  // 🆕 3️⃣ Mostrar análisis de Topic Clusters si hay datos
  if (data.clusters_analysis && window.TopicClustersVisualization) {
    console.log('🔗 Mostrando Topic Clusters:', data.clusters_analysis);
    console.log('🔍 Estructura completa de clusters_analysis:', JSON.stringify(data.clusters_analysis, null, 2));
    window.TopicClustersVisualization.displayTopicClustersResults(data.clusters_analysis, resultsContainer);
  } else {
    console.log('🔍 Debug clusters:', {
      hasClustersData: !!data.clusters_analysis,
      hasVisualization: !!window.TopicClustersVisualization,
      clustersData: data.clusters_analysis,
      fullData: data
    });
  }

  // 4️⃣ Mostrar tabla Grid.js de keywords con AI Overview (debajo de competidores y clusters)
  displayAIOverviewGridTable(data, resultsContainer, competitorDomains);

  // 5️⃣ Mostrar tablas de tipología y posiciones (MOVIDO ABAJO)
  displayTypologyChart(resultsContainer, data);

  // 6️⃣ Diagnostic cards — just above the detailed results table, filtering IT
  displayDiagnosticSection(categories, resultsContainer, data, competitorDomains);

  // 7️⃣ Mostrar tabla detallada de keywords usando Grid.js
  displayDetailedResultsWithDiagnosticFilter(data.keywordResults, resultsContainer);

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

  // Crear contenedor del gráfico con layout de 2 columnas
  const chartHTML = `
    <div class="ai-typology-section">
      <div class="ai-typology-header">
        <h3 class="ai-typology-title">Keyword Length & Position</h3>
      </div>
      
      <div class="ai-typology-main-container">
        <!-- COLUMNA IZQUIERDA: Tabla de Longitud de Keywords -->
        <div class="ai-typology-left">
          <div id="keywordLengthTableContainer" class="ai-typology-container">
            <div class="typology-loading">
              <i class="fas fa-calculator"></i>
              <p>Processing keyword analysis...</p>
            </div>
          </div>
        </div>
        
        <!-- COLUMNA DERECHA: Tabla de Posiciones AIO -->
        <div class="ai-typology-right">
          <div id="aioPositionTableContainer" class="aio-position-table-container">
            <div class="typology-loading">
              <i class="fas fa-list-ol"></i>
              <p>Analyzing AI Overview positions...</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;

  container.insertAdjacentHTML('beforeend', chartHTML);

  // Procesar datos dinámicamente para ambas visualizaciones
  processCurrentAnalysisData(analysisData.keywordResults);
}

/**
 * Procesa los datos del análisis actual y genera las tablas
 */
function processCurrentAnalysisData(keywordResults) {
  console.log('🔍 Processing', keywordResults.length, 'keywords for analysis');

  // Definir categorías actualizadas según los nuevos criterios
  const categories = {
    'short_tail': { label: 'Short Tail', description: '1 word', min: 1, max: 1, total: 0, withAI: 0 },
    'middle_tail': { label: 'Middle Tail', description: '2-3 words', min: 2, max: 3, total: 0, withAI: 0 },
    'long_tail': { label: 'Long Tail', description: '4-8 words', min: 4, max: 8, total: 0, withAI: 0 },
    'super_long_tail': { label: 'Super Long Tail', description: '9+ words', min: 9, max: Infinity, total: 0, withAI: 0 }
  };

  // Procesar cada keyword del análisis actual
  keywordResults.forEach(result => {
    const keyword = result.keyword || '';
    const wordCount = keyword.trim().split(/\s+/).length;
    const hasAI = result.ai_analysis?.has_ai_overview || false;

    console.log(`📝 Keyword: "${keyword}" - ${wordCount} words - AI: ${hasAI}`);

    // Clasificar en la categoría correcta
    for (const [key, category] of Object.entries(categories)) {
      if (wordCount >= category.min && wordCount <= category.max) {
        category.total++;
        if (hasAI) {
          category.withAI++;
        }
        break;
      }
    }
  });

  // Crear la tabla de longitud de keywords
  createKeywordLengthTable(categories, keywordResults.length);
  
  // Crear la tabla de posiciones AIO
  createAIOPositionTable(keywordResults);
}

/**
 * Crea la tabla de longitud de keywords
 */
function createKeywordLengthTable(categories, totalKeywords) {
  const container = document.getElementById('keywordLengthTableContainer');
  if (!container) {
    console.error('Container de tabla de longitud de keywords no encontrado');
    return;
  }

  // Calcular total de keywords con AI Overview
  const totalWithAI = Object.values(categories).reduce((sum, cat) => sum + cat.withAI, 0);

  console.log('📊 Creating keyword length table with data:', categories);

  // Crear tabla HTML
  let tableHTML = `
    <div class="aio-position-table-header">
      <h4 class="aio-position-table-title">Keyword Length Analysis</h4>
      <p class="aio-position-table-subtitle">
        ${totalWithAI} keywords with AI Overview from ${totalKeywords} analyzed
      </p>
    </div>
    
    <table class="aio-position-table">
      <thead>
        <tr>
          <th>Keyword Length</th>
          <th style="text-align: center;">Keywords with AIO</th>
          <th style="text-align: right;">Weight</th>
        </tr>
      </thead>
      <tbody>
  `;

  // Procesar cada categoría
  Object.values(categories).forEach(category => {
    // Porcentaje basado en keywords CON AIO (no total de keywords)
    const percentage = totalWithAI > 0 ? (category.withAI / totalWithAI * 100) : 0;
    
    tableHTML += `
      <tr>
        <td class="aio-position-range">
          ${category.label} (${category.description})
        </td>
        <td class="aio-position-count">${category.withAI}</td>
        <td class="aio-position-percentage">${percentage.toFixed(1)}%</td>
      </tr>
    `;
  });

  tableHTML += `
      </tbody>
    </table>

    <div class="aio-typology-summary">
      <div class="aio-typology-summary-grid">
        <div class="aio-typology-stat aio-typology-stat--accent">
          <div class="aio-typology-stat-value">${totalWithAI}</div>
          <div class="aio-typology-stat-label">With AI Overview</div>
        </div>
        <div class="aio-typology-stat aio-typology-stat--muted">
          <div class="aio-typology-stat-value">${totalKeywords - totalWithAI}</div>
          <div class="aio-typology-stat-label">Without AI Overview</div>
        </div>
      </div>
    </div>
  `;

  container.innerHTML = tableHTML;

  console.log('✅ Keyword length table created');
}

/**
 * Procesa las posiciones AIO y crea datos para la tabla
 */
function processAIOPositionData(keywordResults) {
  console.log('🎯 Processing AIO positions for', keywordResults.length, 'keywords');

  // Definir rangos de posición
  const positionRanges = {
    '1-3': { label: '1 - 3', min: 1, max: 3, count: 0 },
    '4-6': { label: '4 - 6', min: 4, max: 6, count: 0 },
    '7-9': { label: '7 - 9', min: 7, max: 9, count: 0 },
    '10+': { label: '10 or more', min: 10, max: Infinity, count: 0 }
  };

  let totalWithAIOPosition = 0;

  // Procesar cada keyword del análisis actual
  keywordResults.forEach(result => {
    const keyword = result.keyword || '';
    const hasAI = result.ai_analysis?.has_ai_overview || false;
    const aioPosition = result.ai_analysis?.domain_ai_source_position;

    console.log(`🔍 Keyword: "${keyword}" - AI: ${hasAI} - AIO Position: ${aioPosition}`);

    // Solo procesar si tiene AI Overview y posición
    if (hasAI && aioPosition && aioPosition > 0) {
      totalWithAIOPosition++;
      
      // Clasificar en el rango correcto
      for (const [key, range] of Object.entries(positionRanges)) {
        if (aioPosition >= range.min && aioPosition <= range.max) {
          range.count++;
          console.log(`   ✅ Classified in range ${range.label} (position ${aioPosition})`);
          break;
        }
      }
    }
  });

  // Preparar datos para la tabla
  const positionData = [];
  
  Object.values(positionRanges).forEach(range => {
    const percentage = totalWithAIOPosition > 0 ? (range.count / totalWithAIOPosition * 100) : 0;
    
    if (range.count > 0 || totalWithAIOPosition === 0) { // Mostrar todos los rangos, incluso con 0
      positionData.push({
        range: range.label,
        count: range.count,
        percentage: percentage
      });
    }
  });

  console.log('📊 AIO positions summary:', positionData);

  return {
    positionData,
    totalWithAIOPosition,
    totalWithAI: keywordResults.filter(r => r.ai_analysis?.has_ai_overview).length
  };
}

/**
 * Crea la tabla de posiciones AIO
 */
function createAIOPositionTable(keywordResults) {
  const container = document.getElementById('aioPositionTableContainer');
  if (!container) {
    console.error('AIO position table container not found');
    return;
  }

  // Procesar datos de posiciones
  const { positionData, totalWithAIOPosition, totalWithAI } = processAIOPositionData(keywordResults);

  // Si no hay datos de posiciones, mostrar mensaje
  if (totalWithAIOPosition === 0) {
    container.innerHTML = `
      <div class="typology-empty">
        <i class="fas fa-info-circle"></i>
        <p>Your domain doesn't appear as a source in any AI Overview</p>
        <p style="font-size: 0.85rem; opacity: 0.7; margin-top: 0.5rem;">
          ${totalWithAI} keywords have AI Overview, but your site is not mentioned
        </p>
      </div>
    `;
    return;
  }

  // Crear tabla HTML
  let tableHTML = `
    <div class="aio-position-table-header">
      <h4 class="aio-position-table-title">AI Overview Positions</h4>
      <p class="aio-position-table-subtitle">
        ${totalWithAIOPosition} mentions of your domain in ${totalWithAI} detected AI Overview
      </p>
    </div>
    
    <table class="aio-position-table">
      <thead>
        <tr>
          <th>Position</th>
          <th style="text-align: center;">Keywords</th>
          <th style="text-align: right;">Weight</th>
        </tr>
      </thead>
      <tbody>
  `;

  positionData.forEach(item => {
    tableHTML += `
      <tr>
        <td class="aio-position-range">${item.range}</td>
        <td class="aio-position-count">${item.count}</td>
        <td class="aio-position-percentage">${item.percentage.toFixed(1)}%</td>
      </tr>
    `;
  });

  tableHTML += `
      </tbody>
    </table>

    <div class="aio-typology-summary">
      <div class="aio-typology-summary-grid">
        <div class="aio-typology-stat aio-typology-stat--accent">
          <div class="aio-typology-stat-value">${totalWithAIOPosition}</div>
          <div class="aio-typology-stat-label">Total mentions</div>
        </div>
        <div class="aio-typology-stat aio-typology-stat--muted">
          <div class="aio-typology-stat-value">${totalWithAI - totalWithAIOPosition}</div>
          <div class="aio-typology-stat-label">Without mention</div>
        </div>
      </div>
    </div>
  `;

  container.innerHTML = tableHTML;

  console.log('✅ AIO position table created');
}

/**
 * Muestra la tabla Grid.js con keywords de AI Overview
 * @param {Object} data - Datos completos del análisis
 * @param {HTMLElement} container - Contenedor donde mostrar la tabla
 */
function displayAIOverviewGridTable(data, container, competitorDomainsPassed) {
  console.log('🏗️ Displaying AI Overview Grid.js table');

  if (!data || !data.keywordResults) {
    console.warn('⚠️ No keyword results available for Grid.js table');
    return;
  }

  // Use passed competitor domains or extract from summary
  const competitorDomains = competitorDomainsPassed || _getCompetitorDomains(data);

  console.log('📊 Grid.js table data:', {
    totalKeywords: data.keywordResults.length,
    competitorDomains: competitorDomains
  });

  // Crear contenedor para la tabla Grid.js
  const gridContainer = document.createElement('div');
  gridContainer.id = 'aiOverviewGridSection';
  gridContainer.className = 'ai-overview-grid-section';

  // Inner wrapper for the actual Grid.js table
  const gridTableWrapper = document.createElement('div');
  gridTableWrapper.id = 'aiOverviewGridTableWrapper';
  gridContainer.appendChild(gridTableWrapper);

  // Añadir al contenedor principal
  container.appendChild(gridContainer);

  // Crear la tabla Grid.js
  try {
    const grid = createAIOverviewGridTable(
      data.keywordResults,
      competitorDomains,
      gridTableWrapper
    );

    if (grid) {
      console.log('✅ Grid.js table created successfully');
    } else {
      console.warn('⚠️ Grid.js table creation failed');
    }
  } catch (error) {
    console.error('❌ Error creating Grid.js table:', error);
  }
}

// ====================================
// 🏷️ DIAGNOSTIC CARDS UI
// ====================================

/**
 * Displays the keyword diagnostic classification cards.
 * Each card is clickable and filters the "Detailed Results by Keyword" table below.
 */
function displayDiagnosticSection(categories, container, data, competitorDomains) {
  const totalKeywords = data.keywordResults?.length || 0;
  if (totalKeywords === 0) return;

  const sectionHTML = `
    <div class="diagnostic-section aio-diagnostic-section" id="diagnosticSection">
      <h3 class="aio-diagnostic-title">
        Keyword Diagnostic
        <span class="diagnostic-tooltip-trigger" data-tooltip="Each keyword is classified into one diagnostic category based on how AI Overview affects its organic performance. Categories are mutually exclusive — each keyword belongs to exactly one. Click a card to filter the table below and see only keywords in that category." style="font-size: 0.55em; vertical-align: middle; margin-left: 6px; cursor: help; opacity: 0.4;">
          <i class="fas fa-question-circle"></i>
        </span>
      </h3>
      <p class="aio-diagnostic-subtitle">
        <span class="aio-diagnostic-accent">Click a category</span> to filter the table below
      </p>
      <div class="diagnostic-cards-grid aio-diagnostic-grid">
        ${(() => {
          // Collect visible cards, then assign dark/light by position:
          // first 3 rendered = dark, rest = light
          const visibleCards = Object.entries(DIAGNOSTIC_CATEGORIES)
            .filter(([id]) => {
              const catData = categories[id] || { count: 0, percentage: '0.0' };
              return catData.count > 0 || id === 'no_impact';
            });
          return visibleCards.map(([id, cat], idx) => {
            const catData = categories[id] || { count: 0, percentage: '0.0' };
            return _createDiagnosticCard(id, cat, catData, false);
          }).join('');
        })()}
      </div>
      <div class="aio-diagnostic-hint">
        <i class="fas fa-hand-pointer"></i>
        Click any card to filter the detailed results table
      </div>
    </div>
  `;

  container.insertAdjacentHTML('beforeend', sectionHTML);

  // Attach click handlers to cards
  container.querySelectorAll('.diagnostic-card').forEach(card => {
    card.addEventListener('click', () => {
      const categoryId = card.dataset.category;
      _filterDetailedTableByCategory(categoryId);
    });
  });

  // Initialize tooltips on diagnostic cards
  _initDiagnosticTooltips();
}

function _createDiagnosticCard(id, cat, catData, forceDark) {
  const isDark = forceDark !== undefined ? forceDark : cat.dark;
  const darkClass = isDark ? ' aio-diagnostic-card--dark' : '';

  return `
    <div class="diagnostic-card aio-diagnostic-card${darkClass}" data-category="${id}">
      <div class="diagnostic-card-tooltip-icon" data-tooltip="${escapeHtml(cat.description)}">
        <i class="fas fa-info-circle"></i>
      </div>
      <div class="aio-diagnostic-count">
        ${catData.count}
      </div>
      <div class="aio-diagnostic-label">
        ${escapeHtml(cat.label)}
      </div>
      <div class="aio-diagnostic-badge">
        ${catData.percentage}%
      </div>
    </div>
  `;
}

/**
 * Wraps createDetailedResultsGridTable with a filterable container
 * that the diagnostic cards can control.
 */
function displayDetailedResultsWithDiagnosticFilter(keywordResults, container) {
  // Store state for diagnostic card filtering (used by the Detailed Results table)
  window._detailedResultsFilterState = {
    originalResults: keywordResults,
    activeFilter: null
  };

  // Global clear filter handler
  window._aiOverviewClearFilter = () => _filterDetailedTableByCategory(null);

  // Create wrapping section with an ID so we can target it
  const filterSection = document.createElement('div');
  filterSection.id = 'detailedResultsFilterSection';
  container.appendChild(filterSection);

  // Render the Grid.js detailed results table inside
  createDetailedResultsGridTable(keywordResults, filterSection);
}

/**
 * Filters the "Detailed Results by Keyword" table by diagnostic category.
 * If categoryId matches the active filter, clears the filter (toggle).
 */
function _filterDetailedTableByCategory(categoryId) {
  const state = window._detailedResultsFilterState;
  if (!state) return;

  const filterSection = document.getElementById('detailedResultsFilterSection');
  if (!filterSection) return;

  // Remove existing filter banner
  const existingBanner = document.getElementById('detailedFilterBanner');
  if (existingBanner) existingBanner.remove();

  let filteredResults;

  if (categoryId && categoryId !== state.activeFilter) {
    // Apply filter
    filteredResults = state.originalResults.filter(r => r._diagnostic?.category === categoryId);
    state.activeFilter = categoryId;

    const categoryInfo = DIAGNOSTIC_CATEGORIES[categoryId];
    const banner = document.createElement('div');
    banner.id = 'detailedFilterBanner';
    banner.className = 'filter-active-banner';
    banner.innerHTML = `
      <div style="
        display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.5em;
        padding: 0.7em 1.2em;
        background: linear-gradient(135deg, ${categoryInfo.color}15, ${categoryInfo.color}08);
        border: 1px solid ${categoryInfo.color}40;
        border-radius: 8px;
        margin-bottom: 1em;
      ">
        <span style="color: var(--text-color); font-size: 0.9em;">
          <i class="fas fa-filter" style="color: ${categoryInfo.color}; margin-right: 6px;"></i>
          Filtered by: <strong style="color: ${categoryInfo.color};">${escapeHtml(categoryInfo.label)}</strong>
          — ${filteredResults.length} keyword${filteredResults.length !== 1 ? 's' : ''}
        </span>
        <button onclick="window._aiOverviewClearFilter()" style="
          background: none; border: 1px solid var(--border-color);
          padding: 4px 12px; border-radius: 6px; cursor: pointer;
          color: var(--text-color); font-size: 0.82em; transition: all 0.2s ease;
        ">
          <i class="fas fa-times" style="margin-right: 4px;"></i> Clear filter
        </button>
      </div>
    `;
    filterSection.insertBefore(banner, filterSection.firstChild);
  } else {
    // Clear filter
    filteredResults = state.originalResults;
    state.activeFilter = null;
  }

  // Update card active states (CSS handles outline + transform via .active class)
  document.querySelectorAll('.diagnostic-card').forEach(card => {
    const isActive = card.dataset.category === state.activeFilter;
    card.classList.toggle('active', isActive);
  });

  // Re-render the detailed results Grid.js table
  // First remove existing grid section inside filterSection
  const existingGrid = filterSection.querySelector('.ai-overview-grid-section');
  if (existingGrid) existingGrid.remove();

  createDetailedResultsGridTable(filteredResults, filterSection);
}

/**
 * Initializes custom tooltips for diagnostic cards and other elements.
 * Uses a floating tooltip div instead of native title attribute for better UX.
 */
function _initDiagnosticTooltips() {
  // Create tooltip element if it doesn't exist
  let tooltipEl = document.getElementById('diagnosticTooltip');
  if (!tooltipEl) {
    tooltipEl = document.createElement('div');
    tooltipEl.id = 'diagnosticTooltip';
    tooltipEl.className = 'diagnostic-custom-tooltip';
    tooltipEl.style.cssText = `
      position: fixed;
      z-index: 10000;
      max-width: 280px;
      padding: 10px 14px;
      background: #1a1a1a;
      color: #f0f0f0;
      border-radius: 8px;
      font-size: 0.82em;
      line-height: 1.5;
      box-shadow: 0 4px 20px rgba(0,0,0,0.3);
      pointer-events: none;
      opacity: 0;
      transition: opacity 0.2s ease;
      border: 1px solid #333;
    `;
    document.body.appendChild(tooltipEl);
  }

  // Attach listeners ONLY to tooltip icon elements (not entire cards)
  document.querySelectorAll('.diagnostic-card-tooltip-icon[data-tooltip], .diagnostic-tooltip-trigger[data-tooltip]').forEach(el => {
    el.addEventListener('mouseenter', (e) => {
      const text = el.getAttribute('data-tooltip');
      if (!text) return;
      tooltipEl.textContent = text;
      tooltipEl.style.opacity = '1';
      _positionTooltip(e, tooltipEl);
    });

    el.addEventListener('mousemove', (e) => {
      _positionTooltip(e, tooltipEl);
    });

    el.addEventListener('mouseleave', () => {
      tooltipEl.style.opacity = '0';
    });
  });
}

function _positionTooltip(e, tooltipEl) {
  const pad = 12;
  let x = e.clientX + pad;
  let y = e.clientY + pad;

  // Prevent going off-screen right
  const tooltipWidth = tooltipEl.offsetWidth || 280;
  if (x + tooltipWidth > window.innerWidth - pad) {
    x = e.clientX - tooltipWidth - pad;
  }
  // Prevent going off-screen bottom
  const tooltipHeight = tooltipEl.offsetHeight || 60;
  if (y + tooltipHeight > window.innerHeight - pad) {
    y = e.clientY - tooltipHeight - pad;
  }

  tooltipEl.style.left = x + 'px';
  tooltipEl.style.top = y + 'px';
}

// ====================================
// 📊 CTR BENCHMARK ANALYSIS SUMMARY
// ====================================

/**
 * Displays a summary of CTR benchmark analysis comparing expected vs actual CTR.
 */
function displayCTRAnalysisSummary(enrichedResults, container) {
  // Only analyze keywords WITH AI Overview that have valid CTR data
  const aioKeywords = enrichedResults.filter(r =>
    r.ai_analysis?.has_ai_overview && r._ctr_analysis?.ctr_gap !== null
  );

  if (aioKeywords.length === 0) return;

  const totalClicksAbsorbed = aioKeywords.reduce((sum, r) => {
    return sum + (r._ctr_analysis.clicks_absorbed || 0);
  }, 0);

  const avgCTRGap = aioKeywords.reduce((sum, r) => {
    return sum + (r._ctr_analysis.ctr_gap || 0);
  }, 0) / aioKeywords.length;

  const underperformingCount = aioKeywords.filter(r =>
    r._ctr_analysis.actual_ctr < r._ctr_analysis.expected_ctr
  ).length;

  // SERP features breakdown: aggregate clicks absorbed by non-AIO features
  const totalClicksBySerpFeatures = aioKeywords.reduce((sum, r) => {
    return sum + (r._ctr_analysis.clicks_absorbed_by_serp_features || 0);
  }, 0);

  // Count frequency of each SERP feature across all keywords
  const featureFrequency = {};
  enrichedResults.forEach(r => {
    const features = r._ctr_analysis?.serp_features || [];
    features.forEach(f => {
      if (!featureFrequency[f.key]) {
        featureFrequency[f.key] = { ...f, count: 0 };
      }
      featureFrequency[f.key].count++;
    });
  });
  const sortedFeatures = Object.values(featureFrequency).sort((a, b) => b.count - a.count);

  // Build SERP features pills HTML
  let serpFeaturesPillsHTML = '';
  if (sortedFeatures.length > 0) {
    const pills = sortedFeatures.map(f => `
      <span class="aio-serp-pill">
        <i class="fas ${f.icon}"></i>
        ${escapeHtml(f.label)} <strong>${f.count}</strong>
      </span>
    `).join('');

    serpFeaturesPillsHTML = `
      <div class="aio-serp-features-bar">
        <div class="aio-serp-features-label">
          SERP Features Detected
          <span class="ctr-metric-tooltip-trigger aio-ctr-tooltip-trigger" data-tooltip="Other SERP features (Featured Snippets, People Also Ask, Video Carousels, etc.) also push organic results down and absorb clicks. We estimate ~${formatNumber(totalClicksBySerpFeatures)} additional clicks are being captured by these features beyond AI Overview.">
            <i class="fas fa-question-circle"></i>
          </span>
        </div>
        <div class="aio-serp-features-pills">
          ${pills}
        </div>
        ${totalClicksBySerpFeatures > 0 ? `
          <p class="aio-ctr-footnote" style="margin-top: 1.25em;">
            Est. <strong>${formatNumber(totalClicksBySerpFeatures)}</strong> additional clicks absorbed by non-AIO SERP features
          </p>
        ` : ''}
      </div>
    `;
  }

  const sectionHTML = `
    <div class="aio-ctr-section">
      <h3 class="aio-ctr-title">
        CTR Benchmark Analysis
        <span class="ctr-tooltip-trigger" data-tooltip="Compares your actual Click-Through Rate against industry benchmarks for each organic position. The gap estimates how many clicks AI Overview and other SERP features may be absorbing." style="font-size: 0.55em; vertical-align: middle; margin-left: 6px; cursor: help; opacity: 0.5;">
          <i class="fas fa-question-circle"></i>
        </span>
      </h3>
      <p class="aio-ctr-subtitle">
        Keywords with AI Overview: expected vs actual CTR based on organic position
      </p>
      <div class="aio-ctr-metrics-grid">
        <div class="aio-ctr-metric">
          <span class="ctr-metric-tooltip-trigger aio-ctr-tooltip-trigger" data-tooltip="Total estimated clicks lost: the full difference between expected CTR (based on organic position) and actual CTR. Includes impact from AI Overview AND other SERP features (Featured Snippets, PAA, Videos, etc.).">
            <i class="fas fa-question-circle"></i>
          </span>
          <div class="aio-ctr-metric-value">
            ${formatNumber(totalClicksAbsorbed)}
          </div>
          <div class="aio-ctr-metric-label">Est. Clicks Absorbed</div>
        </div>
        <div class="aio-ctr-metric">
          <span class="ctr-metric-tooltip-trigger aio-ctr-tooltip-trigger" data-tooltip="Average difference between the expected CTR for your organic position and your actual CTR across all keywords with AI Overview. A positive gap means you are getting fewer clicks than expected.">
            <i class="fas fa-question-circle"></i>
          </span>
          <div class="aio-ctr-metric-value">
            ${(avgCTRGap * 100).toFixed(1)}%
          </div>
          <div class="aio-ctr-metric-label">Avg CTR Gap</div>
        </div>
        <div class="aio-ctr-metric">
          <span class="ctr-metric-tooltip-trigger aio-ctr-tooltip-trigger" data-tooltip="Number of keywords where your actual CTR is lower than the industry benchmark for your organic position. These keywords are likely being impacted by AI Overview and/or other SERP features.">
            <i class="fas fa-question-circle"></i>
          </span>
          <div class="aio-ctr-metric-value">
            ${underperformingCount}<span class="aio-ctr-metric-sub">/${aioKeywords.length}</span>
          </div>
          <div class="aio-ctr-metric-label">Underperforming</div>
        </div>
      </div>
      <p class="aio-ctr-footnote">
        Based on organic position CTR benchmarks, we estimate these clicks are being absorbed by AI Overview
        and other SERP features displayed above organic results.
      </p>
      ${serpFeaturesPillsHTML}
    </div>
  `;

  container.insertAdjacentHTML('beforeend', sectionHTML);

  // Initialize tooltips for CTR section
  _initCTRTooltips();
}

/**
 * Initialize tooltips for the CTR analysis section.
 * Reuses the same floating tooltip element.
 */
function _initCTRTooltips() {
  let tooltipEl = document.getElementById('diagnosticTooltip');
  if (!tooltipEl) {
    tooltipEl = document.createElement('div');
    tooltipEl.id = 'diagnosticTooltip';
    tooltipEl.className = 'diagnostic-custom-tooltip';
    tooltipEl.style.cssText = `
      position: fixed; z-index: 10000; max-width: 280px;
      padding: 10px 14px; background: #1a1a1a; color: #f0f0f0;
      border-radius: 8px; font-size: 0.82em; line-height: 1.5;
      box-shadow: 0 4px 20px rgba(0,0,0,0.3); pointer-events: none;
      opacity: 0; transition: opacity 0.2s ease; border: 1px solid #333;
    `;
    document.body.appendChild(tooltipEl);
  }

  // Attach ONLY to tooltip trigger icons (not entire metric containers)
  document.querySelectorAll('.ctr-metric-tooltip-trigger[data-tooltip], .ctr-tooltip-trigger[data-tooltip]').forEach(el => {
    if (el._tooltipBound) return; // prevent duplicate binds
    el._tooltipBound = true;

    el.addEventListener('mouseenter', (e) => {
      const text = el.getAttribute('data-tooltip');
      if (!text) return;
      tooltipEl.textContent = text;
      tooltipEl.style.opacity = '1';
      _positionTooltip(e, tooltipEl);
    });

    el.addEventListener('mousemove', (e) => {
      _positionTooltip(e, tooltipEl);
    });

    el.addEventListener('mouseleave', () => {
      tooltipEl.style.opacity = '0';
    });
  });
}

function displaySummary(summary, container, keywordCount = null) {
  // Calcular % de visibilidad en AIO
  const keywordsWithAIO = summary.keywords_with_ai_overview || 0;
  const mentionsInAIO = summary.keywords_as_ai_source || 0;
  const totalKeywords = summary.total_keywords_analyzed || 0;
  const visibilityPercentage = keywordsWithAIO > 0 ? ((mentionsInAIO / keywordsWithAIO) * 100).toFixed(1) : '0.0';

  // Calcular peso AIO en SERPs
  const pesoAIOPercentage = totalKeywords > 0 ? ((keywordsWithAIO / totalKeywords) * 100).toFixed(1) : '0.0';

  // 🆕 NUEVO: Obtener posición promedio en AIO
  const averageAIOPosition = summary.average_ai_position;

  // Determinar el número de keywords dinámicamente
  const keywordCountText = keywordCount || totalKeywords || 50;

  const summaryHTML = `
    <div class="ai-overview-summary">
      <h3 class="aio-section-title">
        <span class="aio-title-accent">AI Overview</span> Analysis
      </h3>
      <p class="aio-section-subtitle">
        based on the ${keywordCountText} most clicked keywords
      </p>
      <div class="aio-summary-grid">
        <div class="aio-summary-card aio-summary-card--dark">
          <div class="aio-card-icon aio-card-icon--robot">
            <i class="fas fa-robot"></i>
          </div>
          <div class="aio-card-value">${formatNumber(keywordsWithAIO)}</div>
          <div class="aio-card-label">With AI Overview</div>
        </div>
        <div class="aio-summary-card">
          <div class="aio-card-icon aio-card-icon--chart">
            <i class="fas fa-chart-pie"></i>
          </div>
          <div class="aio-card-value">${pesoAIOPercentage}%</div>
          <div class="aio-card-label">AIO Weight in SERPs</div>
        </div>
        <div class="aio-summary-card aio-summary-card--dark">
          <div class="aio-card-icon aio-card-icon--mentions">
            <i class="fas fa-hashtag"></i>
          </div>
          <div class="aio-card-value">${formatNumber(mentionsInAIO)}</div>
          <div class="aio-card-label">Mentions of Your Brand</div>
        </div>
        <div class="aio-summary-card">
          <div class="aio-card-icon aio-card-icon--eye">
            <i class="fas fa-eye"></i>
          </div>
          <div class="aio-card-value">${visibilityPercentage}%</div>
          <div class="aio-card-label">% Visibility in AIO</div>
        </div>
        <div class="aio-summary-card aio-summary-card--dark">
          <div class="aio-card-icon aio-card-icon--pin">
            <i class="fas fa-map-marker-alt"></i>
          </div>
          <div class="aio-card-value">${averageAIOPosition !== null && averageAIOPosition !== undefined ? averageAIOPosition : 'N/A'}</div>
          <div class="aio-card-label">Avg Position in AIO</div>
        </div>
      </div>
    </div>
  `;

  container.innerHTML = summaryHTML;
  
  // 🆕 NUEVO: Mostrar tabla de competidores si está disponible
  if (summary.competitor_analysis && summary.competitor_analysis.length > 0) {
    displayCompetitorResults(summary.competitor_analysis, container);
  }
}

/**
 * Muestra los resultados de análisis de competidores
 * @param {Array} competitorResults - Competitor analysis data
 * @param {HTMLElement} container - DOM container
 * @param {Object} options - { mostCitedUrls, manualDomains }
 */
function displayCompetitorResults(competitorResults, container, options = {}) {
  if (!competitorResults || competitorResults.length === 0) {
    console.warn('⚠️ No hay resultados de competidores para mostrar');
    return;
  }

  console.log('📊 Datos de competidores recibidos:');
  console.table(competitorResults);

  // Log detallado de cada dominio
  competitorResults.forEach((result, index) => {
    console.log(`🏢 Dominio ${index + 1}: ${result.domain} [${result.competitor_type || 'unknown'}]`);
    console.log(`   📊 Menciones: ${result.mentions}`);
    console.log(`   👁️ Visibilidad: ${result.visibility_percentage}%`);
    console.log(`   📍 Posición media: ${result.average_position || 'N/A'}`);
  });

  // Log cited URLs info
  if (options.mostCitedUrls && options.mostCitedUrls.length > 0) {
    console.log(`🔗 Most cited URLs: ${options.mostCitedUrls.length} URLs found`);
  }
  if (options.manualDomains && options.manualDomains.length > 0) {
    console.log(`👤 Manual competitor domains: ${options.manualDomains.join(', ')}`);
  }

  // Crear tabla de competidores usando la función del módulo CompetitorAnalysis
  if (window.CompetitorAnalysis) {
    window.CompetitorAnalysis.displayCompetitorResults(competitorResults, container, options);
  } else {
    console.warn('⚠️ Módulo CompetitorAnalysis no disponible para mostrar resultados');
  }
}

function displayDetailedResults(results, container) {
  // Eliminar tabla previa si existe
  const oldTable = document.getElementById('aiOverviewTable');
  if (oldTable) oldTable.parentNode.removeChild(oldTable);

  if (!results || results.length === 0) {
    container.insertAdjacentHTML('beforeend', `
      <div style="text-align: center; padding: 2em; color: var(--text-color); opacity: 0.7;">
        <i class="fas fa-info-circle" style="font-size: 2em; margin-bottom: 0.5em;"></i>
        <p>No detailed results found to display.</p>
      </div>
    `);
    return;
  }

  // Estructura de tabla igual a Keywords
  const tableHTML = `
    <div class="ai-results-table-container" style="margin-top: 2em;">
      <h3 style="text-align: center; margin-bottom: 1em; color: var(--heading);">
        Detailed Results by Keyword
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
           title="View SERP for ${escapeHtml(result.keyword)}"
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
