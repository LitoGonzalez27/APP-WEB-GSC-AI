// Actualización de ui-core.js para integrar el nuevo selector de fechas

import { elems } from './utils.js';
import { 
  fetchData, 
  buildPeriodSummary, // ✅ ACTUALIZADO: usar la nueva función
  processUrlsForComparison, // ✅ NUEVO: importar función para URLs
  hasUrlComparison, // ✅ NUEVO: importar función de detección
  generateUrlsStats // ✅ NUEVO: importar estadísticas de URLs
} from './data.js';
import { showProgress, completeProgress } from './ui-progress.js';
import {
  renderSummary,
  renderKeywords,
  renderInsights,
  renderTable,
  renderTableError,
  updateGlobalKeywordData
} from './ui-render.js';
import { renderKeywordComparisonTable, clearKeywordComparisonTable } from './ui-keyword-comparison-table.js';
import { enableAIOverviewAnalysis } from './ui-ai-overview-main.js';
import { 
  initStickyActions, 
  showStickyActions, 
  hideStickyActions, 
  updateStickyData 
} from './ui-sticky-actions.js';
import { isMobileDevice, getDeviceType, optimizeForMobile, showMobileOptimizationNotice, getAdaptiveTimeouts } from './utils.js';

// ✅ IMPORTAR el nuevo selector de fechas
import { 
  initDateRangeSelector, 
  getSelectedDates, 
  validateSelectedDates 
} from './ui-date-selector.js';

// ✅ REEMPLAZAR initMonthChips con initDateRangeSelector
export function initMonthChips() {
  // Inicializar el nuevo selector de fechas en lugar de chips
  initDateRangeSelector();
  console.log('✅ Date Range Selector initialized');
}

// ✅ ACTUALIZAR handleFormSubmit para trabajar con fechas específicas
export async function handleFormSubmit(e) {
  e.preventDefault();
  if (!elems.form) {
    console.error("Formulario no encontrado.");
    alert("Error: formulario no disponible.");
    return;
  }

  // ✅ NUEVO: Detección móvil mejorada y optimizaciones automáticas
  const isMobile = isMobileDevice();
  const deviceType = getDeviceType();
  const adaptiveTimeouts = getAdaptiveTimeouts();
  
  if (isMobile) {
    console.log(`📱 ${deviceType} detectado - aplicando optimizaciones avanzadas`);
    
    // Aplicar optimizaciones móviles automáticamente
    optimizeForMobile();
    
    // Mostrar notificación optimizada para móviles
    showMobileOptimizationNotice();
  }

  // ✅ NUEVO: Validar fechas seleccionadas
  const dateValidation = validateSelectedDates();
  if (!dateValidation.isValid) {
    const errorMessage = dateValidation.errors.join('\n');
    alert(`Error en las fechas seleccionadas:\n\n${errorMessage}`);
    return;
  }

  // ✅ NUEVO: Obtener fechas del selector
  const selectedDates = getSelectedDates();
  if (!selectedDates) {
    alert('Error: no se pudieron obtener las fechas seleccionadas.');
    return;
  }

  console.log('📅 Fechas seleccionadas:', selectedDates);

  // ✅ ARREGLO CRÍTICO: Verificar que site_url esté seleccionado
  if (!elems.siteUrlSelect || !elems.siteUrlSelect.value) {
    alert('Error: You must select a domain before continuing.');
    return;
  }

  // ✅ NUEVO: Validación de compatibilidad de dominios
  const urlsInput = document.querySelector('textarea[name="urls"]');
  if (urlsInput && urlsInput.value.trim()) {
    // Importar DataValidator dinámicamente
    const { DataValidator } = await import('./ui-validations.js');
    const validator = new DataValidator();
    
    const urls = urlsInput.value.trim().split('\n').filter(url => url.trim());
    const selectedProperty = elems.siteUrlSelect.value;
    
    console.log('🔍 Ejecutando validación de dominios...', {
      selectedProperty,
      urlCount: urls.length
    });
    
    const domainValidation = validator.validateDomainCompatibility(urls, selectedProperty);
    
    if (!domainValidation.isValid) {
      console.error('❌ Validación de dominio fallida:', domainValidation.errors);
      alert(domainValidation.errors.join('\n\n'));
      return;
    }
    
    if (domainValidation.warnings && domainValidation.warnings.length > 0) {
      console.warn('⚠️ Advertencias de validación:', domainValidation.warnings);
      // Las advertencias no bloquean el envío, solo se logean
    }
    
    console.log('✅ Validación de dominios exitosa');
  }

  // ✅ NUEVO: Validaciones específicas para móviles
  if (isMobile) {
    const urlsInput = document.querySelector('textarea[name="urls"]');
    if (urlsInput && urlsInput.value.trim()) {
      const urls = urlsInput.value.trim().split('\n').filter(u => u.trim());
      if (urls.length > 10) {
        const confirmResult = confirm(`Tienes ${urls.length} URLs para analizar. En dispositivos móviles se recomienda máximo 10 URLs para evitar timeouts.\n\n¿Quieres continuar de todos modos?`);
        if (!confirmResult) {
          return;
        }
      }
    }
    
    // Validar períodos largos en móviles
    if (selectedDates.currentPeriod) {
      const startDate = new Date(selectedDates.currentPeriod.startDate);
      const endDate = new Date(selectedDates.currentPeriod.endDate);
      const daysDiff = Math.ceil((endDate - startDate) / (1000 * 60 * 60 * 24));
      
      if (daysDiff > 90) {
        const confirmResult = confirm(`Has seleccionado un período de ${daysDiff} días. En dispositivos móviles se recomienda máximo 90 días para evitar timeouts.\n\n¿Quieres continuar de todos modos?`);
        if (!confirmResult) {
          return;
        }
      }
    }
  }

  const formData = new FormData(elems.form);

  // ✅ ARREGLO CRÍTICO: Asegurar que site_url se incluya
  formData.set('site_url', elems.siteUrlSelect.value);

  // ✅ NUEVO: Agregar fechas específicas al FormData
  formData.set('current_start_date', selectedDates.currentPeriod.startDate);
  formData.set('current_end_date', selectedDates.currentPeriod.endDate);
  
  // Agregar datos de comparación si existen
  if (selectedDates.hasComparison && selectedDates.comparisonPeriod) {
    formData.set('has_comparison', 'true');
    formData.set('comparison_start_date', selectedDates.comparisonPeriod.startDate);
    formData.set('comparison_end_date', selectedDates.comparisonPeriod.endDate);
    formData.set('comparison_mode', selectedDates.comparisonMode);
  } else {
    formData.set('has_comparison', 'false');
  }

  // ✅ ARREGLO: Obtener match_type de los radio buttons
  const matchTypeElement = document.querySelector('input[name="match_type"]:checked');
  if (matchTypeElement) {
    formData.set('match_type', matchTypeElement.value);
  } else {
    formData.set('match_type', 'contains'); // default value
  }

  // ✅ CORREGIDO: Lógica de país que respeta "Todos los países"
  const countryToUse = window.getCountryToUse ? window.getCountryToUse() : null;

  // ✅ NUEVO: Solo añadir al FormData si hay un país específico seleccionado
  if (countryToUse) {
    formData.set('country', countryToUse);
    const countryName = window.getCountryName ? window.getCountryName(countryToUse) : countryToUse;
    console.log(`🎯 Consulta con filtro de país: ${countryName}`);
  } else {
    // ✅ NUEVO: Explícitamente NO añadir 'country' al FormData
    // Esto hace que el backend NO aplique filtro de país = todos los países
    console.log('🌍 Consulta SIN filtro de país (todos los países)');
  }

  // ✅ DEBUGGING: Log del FormData para verificar
  console.log('📋 Datos que se enviarán:');
  const hasCountryFilter = formData.has('country');
  console.log(`  Filtro de país: ${hasCountryFilter ? `SÍ (${formData.get('country')})` : 'NO (todos los países)'}`);

  for (const [key, value] of formData.entries()) {
    console.log(`  ${key}: ${value}`);
  }

  // Reset UI
  hideStickyActions();
  
  [
    elems.insightsSection, elems.performanceSection,
    elems.keywordsSection, elems.resultsSection,
    elems.downloadBlock, elems.aiOverviewSection
  ].forEach(el => el && (el.style.display = 'none'));

  [
    elems.insightsTitle, elems.performanceTitle,
    elems.keywordsTitle, elems.resultsTitle,
    elems.keywordComparisonTableTitle, elems.aiOverviewTitle
  ].forEach(el => el && (el.style.display = 'none'));

  if (elems.disclaimerBlock) elems.disclaimerBlock.innerHTML = '';
  if (elems.keywordOverviewDiv) elems.keywordOverviewDiv.innerHTML = '';
  if (elems.keywordCategoryDiv) elems.keywordCategoryDiv.innerHTML = '';
  clearKeywordComparisonTable();
  
  // ✅ MEJORADO: No limpiar tableBody aquí, se hará en renderTable con cleanupPreviousTable()
  // Esto evita conflictos y permite una limpieza más robusta
  console.log('🔄 Preparando para nueva consulta - limpieza básica realizada');
  
  if (elems.aiAnalysisMessage) elems.aiAnalysisMessage.innerHTML = '';
  if (elems.aiOverviewResultsContainer) elems.aiOverviewResultsContainer.innerHTML = '';

  window.currentData = null;
  window.currentAIOverviewData = null;

  // ✅ NUEVO: Extraer parámetros para la estimación de tiempo
  const urlsValue = formData.get('urls') || '';
  const urlCount = urlsValue.trim() === '' ? 0 : urlsValue.trim().split(/\r\n|\r|\n/).length;
  const countrySelected = !!formData.get('country');
  const matchType = formData.get('match_type') || 'contains';
  const analysisParams = { urlCount, countrySelected, matchType };

  // ✅ NUEVO: Advertencia para más de 25 URLs
  if (urlCount > 25) {
    const confirmation = window.confirm(
        `Estás a punto de analizar ${urlCount} URLs. ` +
        `El proceso puede tardar mucho tiempo (más de 15 minutos) y podría fallar.\n\n` +
        `¿Deseas continuar de todas formas?`
    );
    if (!confirmation) {
        console.log('Análisis cancelado por el usuario debido al alto número de URLs.');
        // Reactivar el botón de envío si el usuario cancela
        const submitButton = document.querySelector('#urlForm button[type="submit"]');
        if (submitButton) {
            submitButton.disabled = false;
            submitButton.innerHTML = '<i class="fas fa-search"></i> Analyze Performance';
        }
        return; // Detener el proceso
    }
  }

  // ✅ NUEVO: Pasos de progreso actualizados para fechas específicas y móviles
  let steps = [
    'Validating dates and preparing query…',
    'Getting main period data…',
    selectedDates.hasComparison ? 'Getting comparison period data…' : null,
    'Processing URL metrics…',
    selectedDates.hasComparison ? 'Calculating period comparisons…' : null,
    'Generating summaries and charts…',
    'Finishing analysis…'
  ].filter(Boolean); // Eliminar elementos null

  // ✅ NUEVO: Mensaje adicional para móviles
  if (isMobile) {
    steps.push('Optimizing results for mobile display…');
  }

  showProgress(steps, analysisParams);

  try {
    const data = await fetchData(formData);
    
    if (data.error && data.reauth_required) {
        alert(data.error + "\nPor favor, recarga la página para re-autenticar.");
        completeProgress();
        return;
    }
    
    if (data.error) {
        // ✅ NUEVO: Mensaje de error más claro para móviles
        let errorMessage = "Error del servidor: " + data.error;
        if (isMobile && (data.error.includes('timeout') || data.error.includes('tardando'))) {
          errorMessage += "\n\n💡 Consejo para móviles: Intenta con un período más corto o menos URLs.";
        }
        alert(errorMessage);
        renderTableError();
        if(elems.keywordComparisonTableBody) {
          elems.keywordComparisonTableBody.innerHTML = '<tr><td colspan="13">Error al cargar datos del servidor.</td></tr>';
        }
        if(elems.keywordsSection) elems.keywordsSection.style.display = 'block';
        if(elems.keywordComparisonTableTitle) elems.keywordComparisonTableTitle.style.display = 'block';
        completeProgress();
        return;
    }

    window.currentData = data;

    // ✅ NUEVO: Procesar información del modo de análisis
    if (data.analysis_info) {
      console.log('📊 Modo de análisis:', data.analysis_info);
      
      // Mostrar información del modo de análisis en la UI
      if (window.displayAnalysisMode) {
        window.displayAnalysisMode(data.analysis_info);
      }
    }

    // ✅ DEBUGGING: Log de datos recibidos
    console.log('📊 Datos recibidos:', {
      keywordStats: data.keywordStats,
      keywordComparisonCount: data.keyword_comparison_data?.length || 0,
      urlsCount: data.pages?.length || 0,
      summaryCount: data.summary?.length || 0,
      periods: data.periods,
      analysisMode: data.analysis_mode
    });

    // ✅ NUEVO: Actualizar datos globales de keywords para los modales
    updateGlobalKeywordData(data.keyword_comparison_data || []);

    // ✅ MODIFICADO: Usar datos de summary para métricas agregadas, pages para tabla
    const summaryData = data.summary && data.summary.length > 0 ? data.summary : data.pages;
    const summary = buildPeriodSummary(summaryData, data.periods);
    renderSummary(summary);

    renderKeywords(data.keywordStats);
    
    // ✅ CAMBIO PRINCIPAL: Pasar también la información de períodos
    renderKeywordComparisonTable(data.keyword_comparison_data || [], data.periods);

    const siteUrlForAI = elems.siteUrlSelect ? elems.siteUrlSelect.value : '';
    enableAIOverviewAnalysis(data.keyword_comparison_data || [], siteUrlForAI);

    renderInsights(summary);
    
    // ✅ NUEVO: Renderizar tabla de URLs con nueva lógica
    renderTable(data.pages);

    // ✅ NUEVO: Generar estadísticas adicionales de URLs si hay comparación
    if (hasUrlComparison(data.pages)) {
      const urlsData = processUrlsForComparison(data.pages, data.periods);
      const urlsStats = generateUrlsStats(urlsData);
      console.log('📋 Estadísticas de URLs generadas:', urlsStats);
      
      // ✅ ELIMINADO: Ya no agregamos conteo dinámico al título - se mantiene limpio como "URLs Performance"
    }

    const keywordData = data.keyword_comparison_data || [];
    updateStickyData(keywordData, siteUrlForAI);
    
    // ✅ NUEVO: Actualizar datos del overlay AI
    if (window.updateAIOverlayData) {
      window.updateAIOverlayData(keywordData, siteUrlForAI);
    }
    
    showStickyActions();

    // ✅ NUEVO: Mensaje de éxito para móviles
    if (isMobile) {
      console.log('✅ Análisis completado exitosamente en dispositivo móvil');
    }

  } catch (err) {
    console.error("Error en handleFormSubmit:", err);
    
    // ✅ NUEVO: Mensaje de error específico para móviles con timeouts adaptativos
    let errorMessage = "Se produjo un error al procesar tu solicitud: " + err.message;
    
    if (isMobile) {
      if (err.message.includes('timeout') || err.message.includes('tardando')) {
        errorMessage += `\n\n📱 Problema común en dispositivos ${deviceType}:`;
        errorMessage += `\n• Timeout extendido a ${adaptiveTimeouts.request.timeout / 1000}s para móviles`;
        errorMessage += `\n• Reintentos automáticos: ${adaptiveTimeouts.request.retry}`;
        errorMessage += "\n\n💡 Soluciones:";
        errorMessage += "\n• Reduce el número de URLs";
        errorMessage += "\n• Selecciona un período más corto";
        errorMessage += "\n• Verifica tu conexión a internet";
        errorMessage += "\n• Intenta desde WiFi en lugar de datos móviles";
      } else if (err.message.includes('conexión') || err.message.includes('network')) {
        errorMessage += "\n\n📱 Problema de conexión en móvil:";
        errorMessage += "\n• Verifica que tengas buena señal";
        errorMessage += "\n• Intenta conectarte a WiFi";
        errorMessage += "\n• Cierra otras apps que usen internet";
        errorMessage += `\n• Sistema de reintentos: ${adaptiveTimeouts.request.retry} intentos`;
      }
    }
    
    alert(errorMessage);
    renderTableError();
    if(elems.keywordComparisonTableBody) {
      elems.keywordComparisonTableBody.innerHTML = '<tr><td colspan="13">Error al procesar la solicitud.</td></tr>';
    }
    if(elems.keywordsSection) elems.keywordsSection.style.display = 'block';
    if(elems.keywordComparisonTableTitle) elems.keywordComparisonTableTitle.style.display = 'block';
  } finally {
    completeProgress();
  }
}


// ✅ FUNCIÓN auxiliar para formatear períodos en títulos
function formatPeriodForTitle(period) {
  if (!period.start_date || !period.end_date) return 'Undefined period';
  
  const startDate = new Date(period.start_date);
  const endDate = new Date(period.end_date);
  
  // Si es el mismo día
  if (period.start_date === period.end_date) {
    return startDate.toLocaleDateString('es-ES', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric'
    });
  }
  
  // Si es el mismo mes
  if (startDate.getMonth() === endDate.getMonth() && startDate.getFullYear() === endDate.getFullYear()) {
    return `${startDate.getDate()}-${endDate.getDate()} ${startDate.toLocaleDateString('es-ES', { month: 'short', year: 'numeric' })}`;
  }
  
  // Período completo
  const startStr = startDate.toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit' });
  const endStr = endDate.toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit', year: 'numeric' });
  
  return `${startStr} - ${endStr}`;
}

// ✅ MANTENER initDownloadExcel sin cambios
export function initDownloadExcel() {
  initStickyActions();
  
  if (elems.downloadExcelBtn) {
    console.log('⚠️ Botón Excel original detectado - debería estar oculto en favor de botones sticky');
  }
}

// ✅ NUEVA función para debugging del selector de fechas
window.debugDateSelector = function() {
  if (window.dateSelector) {
    console.log('=== DEBUG DATE SELECTOR ===');
    console.log('Fechas seleccionadas:', window.dateSelector.getFormattedDates());
    console.log('Validación:', window.dateSelector.validateDates());
    console.log('Período actual:', window.dateSelector.currentPeriod);
    console.log('Período comparación:', window.dateSelector.comparisonPeriod);
    console.log('Modo comparación:', window.dateSelector.comparisonMode);
    console.log('==========================');
  } else {
    console.warn('Date selector not initialized');
  }
};

// ✅ NUEVA función para debugging de URLs
window.debugUrlsTable = function() {
  if (window.currentData && window.currentData.pages) {
    console.log('=== DEBUG URLS TABLE ===');
    const hasComparison = hasUrlComparison(window.currentData.pages);
    console.log('¿Tiene comparación?:', hasComparison);
    console.log('Total páginas:', window.currentData.pages.length);
    
    window.currentData.pages.forEach((page, index) => {
      console.log(`Página ${index + 1}:`, {
        url: page.URL,
        metricsCount: page.Metrics ? page.Metrics.length : 0,
        metrics: page.Metrics
      });
    });
    
    if (hasComparison) {
      const processedUrls = processUrlsForComparison(window.currentData.pages, window.currentData.periods);
      console.log('URLs procesadas:', processedUrls);
      
      const stats = generateUrlsStats(processedUrls);
      console.log('Estadísticas:', stats);
    }
    console.log('========================');
  } else {
    console.warn('No data loaded for debugging');
  }
};