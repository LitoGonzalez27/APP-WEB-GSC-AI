// ui-keyword-comparison-table.js — MIGRADO A GRID.JS (reemplaza completamente el archivo existente)

import { elems } from './utils.js';
import { createKeywordsGridTable } from './ui-keywords-gridjs.js';
import { 
  formatInteger, 
  formatPercentage, 
  formatPosition, 
  formatPercentageChange, 
  formatPositionDelta,
  escapeHtml as escapeHtmlUtil
} from './number-utils.js';

let keywordComparisonGridTable = null;

// ✅ REMOVIDO: Funciones duplicadas - ahora se usan las del módulo centralizado number-utils.js

// ✅ FUNCIÓN para determinar el tipo de análisis
function getAnalysisType(keywordData, periods = null) {
  if (!keywordData || keywordData.length === 0) return 'empty';
  
  // ✅ CORREGIDO: Primero verificar si el usuario seleccionó comparación
  if (periods && periods.has_comparison && periods.comparison) {
    console.log('🔍 Usuario seleccionó comparación explícitamente para keywords - forzando modo comparison');
    return 'comparison';
  }
  
  // Verificar si hay datos de comparación reales (lógica original)
  const hasComparison = keywordData.some(row => 
    (row.clicks_m2 > 0 || row.impressions_m2 > 0) && 
    row.delta_clicks_percent !== 'New'
  );
  
  return hasComparison ? 'comparison' : 'single';
}

// ✅ FUNCIÓN para actualizar headers de tabla según el tipo
function updateTableHeaders(analysisType) {
  const table = document.getElementById('keywordComparisonTable');
  if (!table) return;
  
  const headers = table.querySelectorAll('thead th');
  
  if (analysisType === 'single') {
    // Headers para período único
    if (headers[2]) headers[2].textContent = 'Clicks';
    if (headers[3]) headers[3].style.display = 'none'; // Ocultar P2
    if (headers[4]) headers[4].style.display = 'none'; // Ocultar Delta
    if (headers[5]) headers[5].textContent = 'Impressions P1';
    if (headers[6]) headers[6].style.display = 'none'; // Ocultar P2
    if (headers[7]) headers[7].style.display = 'none'; // Ocultar Delta
    if (headers[8]) headers[8].textContent = 'CTR (%)';
    if (headers[9]) headers[9].style.display = 'none'; // Ocultar P2
    if (headers[10]) headers[10].style.display = 'none'; // Ocultar Delta
    if (headers[11]) headers[11].textContent = 'Position';
    if (headers[12]) headers[12].style.display = 'none'; // Ocultar P2
    if (headers[13]) headers[13].style.display = 'none'; // Ocultar Delta
  } else {
    // Headers para comparación (mostrar todos)
    if (headers[2]) headers[2].textContent = 'Clicks P1';
    if (headers[3]) {
      headers[3].style.display = '';
      headers[3].textContent = 'Clicks P2';
    }
    if (headers[4]) {
      headers[4].style.display = '';
      headers[4].textContent = 'ΔClicks (%)';
    }
    if (headers[5]) headers[5].textContent = 'Impressions P1';
    if (headers[6]) {
      headers[6].style.display = '';
      headers[6].textContent = 'Impressions P2';
    }
    if (headers[7]) {
      headers[7].style.display = '';
      headers[7].textContent = 'ΔImp. (%)';
    }
    if (headers[8]) headers[8].textContent = 'CTR P1 (%)';
    if (headers[9]) {
      headers[9].style.display = '';
      headers[9].textContent = 'CTR P2 (%)';
    }
    if (headers[10]) {
      headers[10].style.display = '';
      headers[10].textContent = 'ΔCTR (%)';
    }
    if (headers[11]) headers[11].textContent = 'Pos P1';
    if (headers[12]) {
      headers[12].style.display = '';
      headers[12].textContent = 'Pos P2';
    }
    if (headers[13]) {
      headers[13].style.display = '';
      headers[13].textContent = 'ΔPos';
    }
  }
}

// ✅ REMOVIDO: Funciones de parsing duplicadas - ahora se usan las del módulo centralizado

export function renderKeywordComparisonTable(keywordData, periods = null) {
  const container = document.getElementById('keywordComparisonBlock');
  if (!container) return;

  // ✅ Limpiar Grid.js anterior si existe
  if (keywordComparisonGridTable && keywordComparisonGridTable.destroy) {
    try {
      keywordComparisonGridTable.destroy();
      console.log('✅ Grid.js anterior destruido');
    } catch (e) {
      console.warn('⚠️ Error destruyendo Grid.js anterior:', e);
    }
    keywordComparisonGridTable = null;
  }

  // ✅ Determinar tipo de análisis
  const analysisType = getAnalysisType(keywordData, periods);
  console.log(`📊 Tipo de análisis: ${analysisType}, Keywords: ${keywordData ? keywordData.length : 0}`);

  if (!keywordData || keywordData.length === 0) {
    // Mostrar mensaje de no hay datos
    container.innerHTML = `
      <div class="no-aio-message">
        <i class="fas fa-search"></i>
        <h3>No Keywords Found</h3>
        <p>No keyword data for the selected URLs and period.</p>
      </div>
    `;
    return;
  }

  // ✅ CREAR TABLA GRID.JS
  try {
    console.log('🔧 Creando tabla Grid.js...', { 
      analysisType, 
      rowsCount: keywordData.length
    });
    
    // Crear Grid.js table
    keywordComparisonGridTable = createKeywordsGridTable(keywordData, analysisType, container);
    
    if (keywordComparisonGridTable) {
      console.log('✅ Tabla Grid.js de keywords creada exitosamente');
    } else {
      console.warn('⚠️ No se pudo crear tabla Grid.js de keywords');
    }
    
  } catch (error) {
    console.error('❌ Error al crear tabla Grid.js de keywords:', error);
    
    // Fallback - mostrar mensaje de error
    container.innerHTML = `
      <div class="no-aio-message">
        <i class="fas fa-exclamation-triangle"></i>
        <h3>Error Loading Table</h3>
        <p>There was an error loading the keywords table. Please try refreshing the page.</p>
      </div>
    `;
  }

  // ✅ Actualizar título de la sección si existe
  const titleElement = document.querySelector('#keywordsSection h2');
  if (titleElement) {
    if (analysisType === 'single') {
      titleElement.textContent = 'Keyword Performance - Single Period';
    } else {
      titleElement.textContent = 'Keyword Performance';
    }
  }
}

export function clearKeywordComparisonTable() {
  if (keywordComparisonGridTable && keywordComparisonGridTable.destroy) {
    try {
      keywordComparisonGridTable.destroy();
      console.log('✅ Grid.js de keywords limpiado');
    } catch (e) {
      console.warn('⚠️ Error al limpiar Grid.js de keywords:', e);
    }
    keywordComparisonGridTable = null;
  }
  
  const container = document.getElementById('keywordComparisonBlock');
  if (container) {
    container.innerHTML = '';
  }
}