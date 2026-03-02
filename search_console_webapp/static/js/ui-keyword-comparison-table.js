// ui-keyword-comparison-table.js — MIGRADO A GRID.JS (reemplaza completamente el archivo existente)

import { createKeywordsGridTable } from './ui-keywords-gridjs.js';

let keywordComparisonGridTable = null;

function getKeywordComparisonGridMount(container) {
  if (!container) return null;
  return container.querySelector('#keywordComparisonGridMount') || container;
}

function getKeywordQuickFiltersHost(container) {
  if (!container) return null;
  return container.querySelector('#keywordQuickFiltersHost') || null;
}

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

// ✅ REMOVIDO: Funciones de parsing duplicadas - ahora se usan las del módulo centralizado

export function renderKeywordComparisonTable(keywordData, periods = null) {
  const container = document.getElementById('keywordComparisonBlock');
  if (!container) return;
  const gridMount = getKeywordComparisonGridMount(container);
  const quickFiltersHost = getKeywordQuickFiltersHost(container);

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
    if (quickFiltersHost) quickFiltersHost.innerHTML = '';
    if (gridMount) {
      gridMount.innerHTML = `
      <div class="no-aio-message">
        <i class="fas fa-search"></i>
        <h3>No Keywords Found</h3>
        <p>No keyword data for the selected URLs and period.</p>
      </div>
    `;
    }
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
    // Guardar referencia global para restaurar tras Clear All
    window.lastKeywordsData = keywordData;
    window.lastKeywordsAnalysisType = analysisType;
    
    if (keywordComparisonGridTable) {
      console.log('✅ Tabla Grid.js de keywords creada exitosamente');
    } else {
      console.warn('⚠️ No se pudo crear tabla Grid.js de keywords');
    }
    
  } catch (error) {
    console.error('❌ Error al crear tabla Grid.js de keywords:', error);
    
    // Fallback - mostrar mensaje de error
    if (gridMount) {
      gridMount.innerHTML = `
      <div class="no-aio-message">
        <i class="fas fa-exclamation-triangle"></i>
        <h3>Error Loading Table</h3>
        <p>There was an error loading the keywords table. Please try refreshing the page.</p>
      </div>
    `;
    }
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
    const gridMount = getKeywordComparisonGridMount(container);
    const quickFiltersHost = getKeywordQuickFiltersHost(container);
    if (gridMount) gridMount.innerHTML = '';
    if (quickFiltersHost) quickFiltersHost.innerHTML = '';
  }
}

// ✅ NUEVO: Función para obtener la instancia de Grid.js (para cleanup desde ui-render)
export function getKeywordComparisonGridTable() {
  return keywordComparisonGridTable;
}
