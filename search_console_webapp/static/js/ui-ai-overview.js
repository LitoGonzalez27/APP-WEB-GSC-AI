// static/js/ui-ai-overview.js
import { elems } from './utils.js'; // Ensure elems is imported if used in this file
import { displayAIOverviewResults } from './ui-ai-overview-display.js'; // <-- NUEVA IMPORTACIÓN

/**
 * Enables and sets up the AI Overview analysis section.
 * This function primarily controls the display of messages related to AI Overview analysis readiness.
 * It's called during the initial setup to inform the user about the sticky buttons.
 * @param {Array<Object>} keywordData - The keyword data to be analyzed.
 * @param {string} siteUrl - The site URL for which the analysis is being performed.
 */
export function enableAIOverviewAnalysis(keywordData, siteUrl) {
  console.log('[AI OVERVIEW] Preparando análisis...', { keywordCount: keywordData?.length, siteUrl });
  
  if (!keywordData || !Array.isArray(keywordData) || keywordData.length === 0) {
    console.log('[AI OVERVIEW] No hay datos de keywords para analizar');
    if (elems.aiAnalysisMessage) {
      elems.aiAnalysisMessage.innerHTML = `
        <div class="ai-analysis-controls">
          <div>
            <i class="fas fa-info-circle"></i> No keyword data available for AI Overview analysis
          </div>
          <p style="margin-top: 1em; color: var(--text-color); opacity: 0.7;">
            First run a query with URLs to get keyword data and analyze AI Overview impact.
          </p>
        </div>
      `;
    }
    return;
  }

  if (!siteUrl) {
    console.log('[AI OVERVIEW] No se proporcionó site_url');
    if (elems.aiAnalysisMessage) {
      elems.aiAnalysisMessage.innerHTML = `
        <div class="ai-analysis-controls">
          <div>
            <i class="fas fa-exclamation-triangle"></i> Domain selection required for analysis
          </div>
        </div>
      `;
    }
    return;
  }

  console.log('[AI OVERVIEW] Configurando controles de análisis...');

  // ✅ NUEVO: Actualizar overlay si está disponible
  if (window.updateAIOverlayData) {
    window.updateAIOverlayData(keywordData, siteUrl);
  }

  console.log('[AI OVERVIEW] Listo para análisis via botones sticky');
}

/**
 * Initializes the AI Overview analysis setup.
 * This function serves as the primary export for initializing the AI Overview section.
 * It currently delegates to enableAIOverviewAnalysis.
 */
export function initAIOverviewAnalysis(keywordData, siteUrl) {
    // This function can be used to perform any initial setup for the AI Overview section
    // before the analysis is actually run via the sticky button.
    console.log('[AI OVERVIEW] Inicializando sección de análisis de AI Overview...');
    enableAIOverviewAnalysis(keywordData, siteUrl);
}

// ✅ FUNCIÓN CORREGIDA: Lógica de país para AI Overview
function getCountryForAIAnalysis() {
    const countryToUse = window.getCountryToUse ? window.getCountryToUse() : null;
    
    // ✅ NUEVO: Para AI Overview, si no hay país específico, usar país principal o España
    // Esto es porque AI Overview necesita un país específico para análisis SERP
    if (!countryToUse) {
        const fallbackCountry = window.primaryBusinessCountry ? window.primaryBusinessCountry() : 'esp';
        console.log(`🔍 AI Overview: Sin país específico, usando ${fallbackCountry} como fallback`);
        return fallbackCountry;
    }
    
    console.log(`🎯 AI Overview: Usando país específico ${countryToUse}`);
    return countryToUse;
}

/**
 * Nueva función para el fetch de análisis AI
 */
async function analyzeAIOverview(keywords, siteUrl, keywordCount = null) {
    // Usar la lógica de país principal del negocio
    const countryToUse = window.getCountryToUse ? window.getCountryToUse() : 'esp';
    
    const payload = {
        keywords: keywords,
        site_url: siteUrl
    };
    
    // Añadir cantidad de keywords si se especifica
    if (keywordCount) {
        payload.keyword_count = keywordCount;
        console.log(`🔢 Enviando solicitud para analizar ${keywordCount} keywords`);
    }
    
    // 🆕 NUEVO: Añadir dominios de competidores si están disponibles
    if (window.CompetitorAnalysis) {
        const competitorDomains = window.CompetitorAnalysis.getValidCompetitorDomains();
        if (competitorDomains.length > 0) {
            payload.competitor_domains = competitorDomains;
            console.log(`🥊 Incluyendo análisis de ${competitorDomains.length} competidores: ${competitorDomains.join(', ')}`);
            
            // Mostrar mensaje al usuario sobre el análisis de competidores
            if (window.showToast) {
                window.showToast(`Analyzing ${competitorDomains.length} competitor domain${competitorDomains.length > 1 ? 's' : ''} for comparison`, 'info', 3000);
            }
        }
    }
    
    // 🔍 NUEVO: Añadir configuración de exclusión de keywords
    if (window.getKeywordExclusionConfig) {
        const exclusionConfig = window.getKeywordExclusionConfig();
        if (exclusionConfig.enabled) {
            payload.keyword_exclusions = exclusionConfig;
            console.log(`🔍 Incluyendo exclusiones: ${exclusionConfig.terms.length} términos con método "${exclusionConfig.method}"`);
            
            // Mostrar mensaje al usuario sobre las exclusiones
            if (window.showToast) {
                window.showToast(`Applying ${exclusionConfig.terms.length} keyword exclusion${exclusionConfig.terms.length > 1 ? 's' : ''} (${exclusionConfig.method})`, 'info', 3000);
            }
        }
    }
    
    // Añadir país (principal del negocio, seleccionado manualmente, o fallback)
    if (countryToUse) {
        payload.country = countryToUse;
        
        // Logging descriptivo sobre qué país se está usando
        const countryName = window.getCountryName ? window.getCountryName(countryToUse) : countryToUse;
        const isPrimary = window.primaryBusinessCountry && window.primaryBusinessCountry() === countryToUse;
        const isManual = document.getElementById('countrySelect')?.value === countryToUse;
        
        if (isManual) {
            console.log(`🎯 Análisis AI Overview usando selección manual: ${countryName}`);
        } else if (isPrimary) {
            console.log(`👑 Análisis AI Overview usando país principal del negocio: ${countryName}`);
        } else {
            console.log(`🔄 Análisis AI Overview usando fallback: ${countryName}`);
        }
    }
    
    const response = await fetch('/api/analyze-ai-overview', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
    });
    
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: `HTTP ${response.status}` }));
        throw new Error(errorData.error || `Error del servidor: ${response.status}`);
    }
    
    return response.json();
}

/**
 * FUNCIÓN PRINCIPAL: Ejecutar análisis de AI Overview (exportada para botones sticky)
 * @param {Array<Object>} keywordData - The keyword data to analyze.
 * @param {string} siteUrl - The site URL for the analysis.
 * @param {HTMLElement} [buttonElement=null] - The button element that triggered the analysis, for loading state.
 * @param {HTMLElement} [statusElement=null] - The element to display status messages.
 */
export async function runAIOverviewAnalysis(keywordData, siteUrl, buttonElement = null, statusElement = null) {
  console.log('[AI OVERVIEW] 🚀 Iniciando análisis completo...', { 
    keywordCount: keywordData?.length, 
    siteUrl,
    hasButton: !!buttonElement 
  });

  // Validaciones iniciales
  if (!keywordData || !Array.isArray(keywordData) || keywordData.length === 0) {
    const errorMsg = 'No keyword data available to analyze';
    console.error('[AI OVERVIEW] ❌', errorMsg);
    if (statusElement) statusElement.textContent = errorMsg;
    throw new Error(errorMsg);
  }

  if (!siteUrl) {
    const errorMsg = 'Valid site_url required';
    console.error('[AI OVERVIEW] ❌', errorMsg);
    if (statusElement) statusElement.textContent = errorMsg;
    throw new Error(errorMsg);
  }

  // Configurar estado de loading si hay botón
  const originalButtonText = buttonElement?.innerHTML;
  if (buttonElement) {
    buttonElement.disabled = true;
    buttonElement.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Analizando...';
  }

  try {
    // Mostrar sección AI Overview al inicio para que sea visible durante el progreso
    if (elems.aiOverviewSection) {
      elems.aiOverviewSection.style.display = 'block';
      console.log('🎯 Sección AI Overview mostrada para progreso (sticky button)');
    } else {
      console.warn('⚠️ Elemento elems.aiOverviewSection no encontrado');
    }
    
    // ✅ NUEVO: Obtener cantidad seleccionada por usuario
    const keywordCountSelect = document.getElementById('keywordCountSelect');
    const selectedCount = keywordCountSelect ? parseInt(keywordCountSelect.value) : 50;
    
    console.log(`[AI OVERVIEW] 📊 Usuario seleccionó analizar ${selectedCount} keywords`);
    if (statusElement) statusElement.textContent = `Selecting top ${selectedCount} keywords by clicks...`;

    // Ordenar por clics descendente y tomar la cantidad seleccionada
    let topKeywords = keywordData
      .sort((a, b) => (b.clicks_m1 || 0) - (a.clicks_m1 || 0))
      .slice(0, selectedCount);

    console.log(`[AI OVERVIEW] ✅ Top ${selectedCount} keywords seleccionadas antes de exclusiones:`, topKeywords.length);

    // 🔍 APLICAR EXCLUSIONES DE KEYWORDS
    const exclusionConfig = window.getKeywordExclusionConfig ? window.getKeywordExclusionConfig() : { enabled: false };
    
    if (exclusionConfig.enabled && exclusionConfig.terms.length > 0) {
        console.log(`[AI OVERVIEW] 🔍 Aplicando exclusiones: ${exclusionConfig.terms.length} términos con método "${exclusionConfig.method}"`);
        
        const beforeExclusion = topKeywords.length;
        topKeywords = window.filterKeywordsWithExclusion ? window.filterKeywordsWithExclusion(topKeywords) : topKeywords;
        const afterExclusion = topKeywords.length;
        const excluded = beforeExclusion - afterExclusion;
        
        console.log(`[AI OVERVIEW] ✅ Exclusiones aplicadas: ${beforeExclusion} → ${afterExclusion} (excluidas: ${excluded})`);
        
        // Si después de las exclusiones tenemos menos keywords, completar hasta el límite original
        if (topKeywords.length < selectedCount && keywordData.length > selectedCount) {
            console.log(`[AI OVERVIEW] 🔄 Completando keywords después de exclusiones...`);
            
            // Obtener keywords adicionales que no estén excluidas
            const remainingKeywords = keywordData
                .sort((a, b) => (b.clicks_m1 || 0) - (a.clicks_m1 || 0))
                .slice(selectedCount) // Tomar las que siguen después del límite original
                .filter(keyword => !window.keywordExclusion.shouldExcludeKeyword(keyword.keyword));
            
            const needed = selectedCount - topKeywords.length;
            const additional = remainingKeywords.slice(0, needed);
            
            topKeywords = topKeywords.concat(additional);
            console.log(`[AI OVERVIEW] ✅ Añadidas ${additional.length} keywords adicionales. Total: ${topKeywords.length}`);
        }
    } else {
        console.log(`[AI OVERVIEW] ⚪ Sin exclusiones configuradas`);
    }

    console.log(`[AI OVERVIEW] ✅ Keywords finales para análisis:`, topKeywords.length);

    // Verificar si hay keywords
    if (topKeywords.length === 0) {
      console.log('[AI OVERVIEW] ⚠️ No se encontraron keywords para análisis');
      if (statusElement) statusElement.textContent = 'No keywords found';
      
      // Mostrar mensaje en la UI
      displayAIOverviewResults({
        summary: { 
          total_keywords_analyzed: 0, 
          keywords_with_ai_overview: 0, 
          keywords_as_ai_source: 0, 
          total_estimated_clicks_lost: 0 
        },
        keywordResults: []
      });
      
      if (elems.aiOverviewResultsContainer) {
        elems.aiOverviewResultsContainer.insertAdjacentHTML('afterbegin', `
          <div class="ai-overview-summary" style="margin-bottom: 2em; padding: 1.5em; background: rgba(255,193,7,0.1); border-radius: 8px; border-left: 4px solid #ffc107;">
            <h3 style="color: #ffc107;"><i class="fas fa-info-circle"></i> No keywords for analysis</h3>
            <p>No keywords with sufficient traffic were found to analyze.</p>
          </div>
        `);
      }

      if (elems.aiOverviewSection) {
        elems.aiOverviewSection.style.display = 'block';
      }

      return { keywords: [] };
    }

    // ✅ DIRECTO: Análisis de AI Overview sin filtrado previo
    console.log(`[AI OVERVIEW] 🤖 Iniciando análisis SERP directo de ${topKeywords.length} keywords...`);
    if (statusElement) statusElement.textContent = `Analyzing ${topKeywords.length} keywords...`;
    
    // ✅ LLAMADA AL ANÁLISIS REAL con cantidad seleccionada
    const analysisData = await analyzeAIOverview(topKeywords, siteUrl, selectedCount);

    if (analysisData.error) {
      throw new Error(analysisData.error);
    }

    // ✅ PROCESAR Y MOSTRAR RESULTADOS
    const displayData = {
      analysis: analysisData,
      candidates: { 
        total_candidates: topKeywords.length,
        top_candidates: topKeywords,
        criteria_summary: {
          criteria: ['Top keywords by clicks (no additional filters)'],
          total_evaluated: keywordData.length
        }
      },
      summary: analysisData.summary || {},
      keywordResults: analysisData.results || []
    };

    // Guardar en variable global para descarga Excel
    if (window) {
      window.currentAIOverviewData = displayData;
      console.log('[AI DEBUG] Guardado en window.currentAIOverviewData:', window.currentAIOverviewData);
    }

    console.log('[AI OVERVIEW] ✅ Mostrando resultados:', {
      summary: displayData.summary,
      keywordResults: displayData.keywordResults?.length || 0
    });

    displayAIOverviewResults(displayData);
    
    if (statusElement) statusElement.textContent = 'Analysis complete';
    
    return displayData;
      
  } catch (error) {
    console.error('[AI OVERVIEW] ❌ Error en análisis:', error);
    
    // Mostrar error en la UI
    if (elems.aiOverviewResultsContainer) {
        elems.aiOverviewResultsContainer.innerHTML = '';
        elems.aiOverviewResultsContainer.insertAdjacentHTML('afterbegin', `
            <div class="ai-overview-summary" style="
                background: rgba(220, 53, 69, 0.1);
                color: #dc3545;
                padding: 1.5em;
                border-radius: 8px;
                border: 1px solid rgba(220, 53, 69, 0.2);
                margin-bottom: 2em;
            ">
                <h3 style="text-align: center; color: #dc3545; margin-bottom: 1em;">
                    <i class="fas fa-exclamation-triangle"></i> Analysis Error
                </h3>
                <p style="text-align: center;">${error.message}</p>
                <p style="text-align: center; margin-top: 1em; font-size: 0.9em; opacity: 0.8;">
                    Please check your internet connection and try again.
                </p>
            </div>
        `);
    }
      
    // Mostrar sección para que se vea el error
    if (elems.aiOverviewSection) {
      elems.aiOverviewSection.style.display = 'block';
    }
    
    if (statusElement) statusElement.textContent = 'Analysis error';

    throw error;
  } finally {
    // Restaurar botón si existe
    if (buttonElement && originalButtonText) {
      buttonElement.disabled = false;
      buttonElement.innerHTML = originalButtonText;
    }
  }
}