// static/js/ui-ai-overview-analysis.js - Lógica de análisis AI Overview

import { elems } from './utils.js';
import { showToast, createSpinner } from './ui-ai-overview-utils.js';
import { displayAIOverviewResults } from './ui-ai-overview-display.js';

// Función para obtener país seleccionado (duplicada aquí para auto-suficiencia o importable desde ui-serp-modal.js)
function getSelectedCountry() {
    const countrySelect = document.getElementById('countrySelect');
    return countrySelect ? countrySelect.value : '';
}

// Función para crear barra de progreso
function createProgressBar() {
    return `
        <div class="ai-progress-container" style="
            background: rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            padding: 1em;
            margin: 1em 0;
            border: 1px solid rgba(255, 255, 255, 0.2);
            animation: slideIn 0.3s ease-out;
        ">
            <div class="ai-progress-header" style="
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 0.5em;
            ">
                <span class="ai-progress-text" style="
                    color: var(--text-color);
                    font-weight: 500;
                ">Preparando análisis...</span>
                <span class="ai-progress-percentage" style="
                    color: var(--cta-bg);
                    font-weight: bold;
                    font-size: 1.1em;
                ">0%</span>
            </div>
            <div class="ai-progress-bar-bg" style="
                background: rgba(255, 255, 255, 0.1);
                height: 8px;
                border-radius: 4px;
                overflow: hidden;
                box-shadow: inset 0 1px 2px rgba(0,0,0,0.1);
            ">
                <div class="ai-progress-bar-fill" style="
                    background: linear-gradient(90deg, var(--cta-bg), var(--info-color));
                    height: 100%;
                    width: 0%;
                    border-radius: 4px;
                    transition: width 0.5s ease;
                    position: relative;
                    overflow: hidden;
                "></div>
            </div>
            <div class="ai-progress-details" style="
                margin-top: 0.5em;
                font-size: 0.9em;
                color: var(--text-color);
                opacity: 0.8;
                display: flex;
                justify-content: space-between;
                align-items: center;
            ">
                <span>
                    <span class="ai-progress-current">0</span> of <span class="ai-progress-total">0</span> keywords processed
                </span>
                <span class="ai-progress-spinner" style="
                    display: inline-block;
                    width: 12px;
                    height: 12px;
                    border: 2px solid var(--text-color);
                    border-top: 2px solid var(--cta-bg);
                    border-radius: 50%;
                    animation: spin 1s linear infinite;
                    opacity: 0.7;
                "></span>
            </div>
        </div>
        <style>
            @keyframes slideIn {
                from { opacity: 0; transform: translateY(-10px); }
                to { opacity: 1; transform: translateY(0); }
            }
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.7; }
            }
        </style>
    `;
}

// Función para actualizar la barra de progreso
function updateProgressBar(current, total, status = '') {
    const percentage = Math.round((current / total) * 100);
    
    const progressText = document.querySelector('.ai-progress-text');
    const progressPercentage = document.querySelector('.ai-progress-percentage');
    const progressFill = document.querySelector('.ai-progress-bar-fill');
    const progressCurrent = document.querySelector('.ai-progress-current');
    const progressTotal = document.querySelector('.ai-progress-total');
    
    if (progressText) progressText.textContent = status || `Analyzing keywords in parallel...`;
    if (progressPercentage) progressPercentage.textContent = `${percentage}%`;
    if (progressFill) progressFill.style.width = `${percentage}%`;
    if (progressCurrent) progressCurrent.textContent = current;
    if (progressTotal) progressTotal.textContent = total;
}

// Función para completar la barra de progreso
function completeProgressBar(analysisData = null) {
    const progressText = document.querySelector('.ai-progress-text');
    const progressPercentage = document.querySelector('.ai-progress-percentage');
    const progressFill = document.querySelector('.ai-progress-bar-fill');
    const progressSpinner = document.querySelector('.ai-progress-spinner');
    
    if (progressText) {
        if (analysisData && analysisData.summary) {
            const summary = analysisData.summary;
            const withAI = summary.keywords_with_ai_overview || 0;
            const total = summary.total_keywords_analyzed || 0;
            progressText.textContent = `Analysis completed! ${withAI}/${total} keywords with AI Overview detected`;
        } else {
            progressText.textContent = 'Analysis completed successfully!';
        }
    }
    
    if (progressPercentage) progressPercentage.textContent = '100%';
    if (progressSpinner) progressSpinner.style.display = 'none';
    
    if (progressFill) {
        progressFill.style.width = '100%';
        progressFill.style.background = 'linear-gradient(90deg, var(--success-color), #4CAF50)';
    }
    
    // Ocultar la barra después de 1.2 segundos
    setTimeout(() => {
        const progressContainer = document.querySelector('.ai-progress-container');
        if (progressContainer) {
            progressContainer.style.transition = 'opacity 0.5s ease';
            progressContainer.style.opacity = '0';
            setTimeout(() => progressContainer.remove(), 500);
        }
    }, 1200);
}

// Nueva función para el fetch de análisis AI
async function analyzeAIOverview(keywords, siteUrl) {
    // ✅ NUEVA LÓGICA: Usar la misma lógica que SERP para consistencia
    const countrySelect = document.getElementById('countrySelect');
    const selectedCountry = countrySelect ? countrySelect.value : '';
    
    const payload = {
        keywords: keywords,
        site_url: siteUrl
    };
    
    // Solo añadir país si hay uno específico seleccionado
    // Si está vacío, el backend usará detección dinámica del país con más clics
    if (selectedCountry) {
        payload.country = selectedCountry;
        const countryName = window.getCountryName ? window.getCountryName(selectedCountry) : selectedCountry;
        console.log(`🎯 Análisis AI Overview con país específico: ${countryName}`);
    } else {
        console.log(`🌍 Análisis AI Overview sin país específico - backend usará país con más clics dinámicamente`);
    }
    
    // Timeout aumentado para análisis paralelo
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 120000); // 2 minutos
    
    try {
        const response = await fetch('/api/analyze-ai-overview', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload),
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        // ✅ NUEVO FASE 4.5: Manejar paywalls
        if (response.status === 402) {
            // Paywall - usuario Free
            const data = await response.json().catch(() => ({}));
            if (window.showPaywall) {
                window.showPaywall('AI Overview Analysis', data.upgrade_options || ['basic', 'premium', 'business']);
            }
            throw new Error('This feature requires a paid plan. Upgrade to unlock it.');
        }

        if (response.status === 429) {
            // Quota exceeded
            const data = await response.json().catch(() => ({}));
            if (window.showQuotaExceeded) {
                window.showQuotaExceeded(data.quota_info || {});
            }
            throw new Error("You've reached your monthly analysis limit. Upgrade your plan to continue.");
        }

        if (response.status === 400) {
            throw new Error('Something went wrong with your request. Please try again.');
        }

        if (response.status >= 500) {
            throw new Error('Our servers are having a moment. Please try again in a few seconds.');
        }

        if (!response.ok) {
            throw new Error('Something went wrong with your request. Please try again.');
        }

        return response.json();
    } catch (error) {
        clearTimeout(timeoutId);
        if (error.name === 'AbortError') {
            throw new Error('Analysis took too long. Try with fewer keywords.');
        }
        throw error;
    }
}

export async function handleAIOverviewAnalysis(aiOverviewResults, setAIOverviewResults) {
  const analyzeBtn = document.getElementById('analyzeAIOverviewBtn');
  const statusSpan = document.getElementById('aiAnalysisStatus');
  const resultsContainer = document.getElementById('aiOverviewResultsContainer');
  
  // Debug inicial de elementos
  console.log('🔍 Debug elementos AI Analysis:', {
    analyzeBtn: !!analyzeBtn,
    statusSpan: !!statusSpan,
    resultsContainer: !!resultsContainer,
    aiSection: !!document.getElementById('aiOverviewSection')
  });
  
  if (!analyzeBtn || !resultsContainer) {
    console.error('Elementos requeridos no encontrados para análisis AI Overview');
    return;
  }

  const keywordData = analyzeBtn.dataset.keywordData;
  const siteUrl = analyzeBtn.dataset.siteUrl;
  
  if (!keywordData || !siteUrl) {
    showToast('No data available for analysis', 'error');
    return;
  }

  let parsedKeywordData;
  try {
    parsedKeywordData = JSON.parse(keywordData);
  } catch (e) {
    console.error('Error parseando datos de keywords:', e);
    showToast('Error in keyword data', 'error');
    return;
  }

  if (!parsedKeywordData.length) {
    showToast('No keyword data to analyze', 'warning');
    return;
  }

  const originalText = analyzeBtn.innerHTML;
  analyzeBtn.disabled = true;
  analyzeBtn.innerHTML = `${createSpinner()} Analyzing...`;
  
  if (statusSpan) {
    statusSpan.textContent = 'Selecting top keywords by traffic...';
    statusSpan.style.color = '#17a2b8';
  }

  // IMPORTANTE: Mostrar la sección ANTES de crear la barra de progreso
  const aiSection = document.getElementById('aiOverviewSection');
  if (aiSection) {
    aiSection.style.display = 'block';
    console.log('🎯 Sección AI Overview mostrada para barra de progreso');
  } else {
    console.warn('⚠️ Elemento aiOverviewSection no encontrado');
  }

  resultsContainer.innerHTML = '';
  
  // Crear y mostrar barra de progreso
  const progressBarHTML = createProgressBar();
  resultsContainer.innerHTML = progressBarHTML;
  
  // La animación de entrada es inmediata (sin delay artificial)
  
  try {
    // ✅ NUEVO: Simplificado - tomar top 30 keywords por clics directamente
    console.log(`[AI DEBUG] Analizando top keywords de ${parsedKeywordData.length} total`, parsedKeywordData);
    
    // Actualizar progreso: seleccionando keywords
            updateProgressBar(0, 30, 'Selecting top keywords by clicks...');
    
    // Ordenar por clics descendente y tomar las top 30
    const topKeywords = parsedKeywordData
      .sort((a, b) => (b.clicks_m1 || 0) - (a.clicks_m1 || 0))
      .slice(0, 30);
    
    console.log('[AI DEBUG] Top keywords seleccionadas:', topKeywords);

    if (statusSpan) {
      statusSpan.textContent = `Analyzing ${topKeywords.length} keywords in parallel (optimized)...`;
      statusSpan.style.color = '#17a2b8';
    }

    if (topKeywords.length === 0) {
      handleNoKeywordsFound(setAIOverviewResults, statusSpan, resultsContainer);
      return;
    }

    console.log(`[AI DEBUG] Enviando a análisis top ${topKeywords.length} keywords:`, topKeywords.map(k => k.keyword).slice(0, 5), '...');

    // Actualizar progreso: iniciando análisis
    updateProgressBar(0, topKeywords.length, `Starting parallel analysis of ${topKeywords.length} keywords...`);
    
    // Notificación de inicio
    showToast(`Starting parallel analysis of ${topKeywords.length} keywords`, 'info', 3000);
    
    // Simular progreso durante el análisis
    const progressInterval = setInterval(() => {
      const current = Math.min(
        document.querySelector('.ai-progress-current')?.textContent || 0,
        topKeywords.length - 5
      );
      const nextValue = parseInt(current) + Math.floor(Math.random() * 3) + 1;
      if (nextValue < topKeywords.length) {
                    updateProgressBar(nextValue, topKeywords.length, 'Processing keywords in parallel...');
      }
    }, 2000);

    // ✅ SIMPLIFICADO: Análisis directo sin filtrado previo
    const analysisData = await analyzeAIOverview(topKeywords, siteUrl);
    
    // Detener simulación de progreso
    clearInterval(progressInterval);
    
    // Completar barra de progreso
    completeProgressBar(analysisData);
    
    // Mostrar notificación de éxito
    if (analysisData && analysisData.summary) {
      const summary = analysisData.summary;
      const withAI = summary.keywords_with_ai_overview || 0;
      const total = summary.total_keywords_analyzed || 0;
              showToast(`Analysis completed: ${withAI}/${total} keywords with AI Overview`, 'success', 4000);
    } else {
              showToast('AI Overview analysis completed successfully', 'success');
    }

    console.log('[AI DEBUG] Datos recibidos del análisis:', analysisData);

    // ✅ FASE 4: Manejar errores de quota específicamente
    if (analysisData.error) {
      // Verificar si hay errores de quota en los resultados
      const quotaErrors = analysisData.results ? 
        analysisData.results.filter(result => result.error === 'quota_exceeded') : [];
      
      if (quotaErrors.length > 0) {
        console.warn(`🚫 ${quotaErrors.length} keywords bloqueadas por quota`);
        
        // Mostrar UI de quota si hay errores de quota
        const quotaInfo = quotaErrors[0].quota_info || {};
        if (window.QuotaUI) {
          window.QuotaUI.showBlockModal({
            error: analysisData.error,
            quota_blocked: true,
            quota_info: quotaInfo,
            action_required: quotaErrors[0].action_required || 'upgrade'
          });
        }
        
        // Si todos están bloqueados por quota, no continuar
        if (quotaErrors.length === analysisData.results.length) {
          throw new Error(`Analysis blocked: ${analysisData.error}. Please upgrade your plan to continue.`);
        }
        
        // Si solo algunos están bloqueados, mostrar warning y continuar con los exitosos
        showToast(`⚠️ ${quotaErrors.length} keywords blocked by quota limit. Consider upgrading for full analysis.`, 'warning', 6000);
      } else {
        // Error normal, no de quota
        throw new Error(analysisData.error);
      }
    }

    const displayData = {
      analysis: analysisData,
      candidates: { 
        total_candidates: topKeywords.length,
        top_candidates: topKeywords,
        criteria_summary: {
          criteria: ['Top keywords by clicks (no additional filters)'],
          total_evaluated: parsedKeywordData.length
        }
      },
      summary: analysisData.summary || {},
      keywordResults: analysisData.results || [],
      clusters_analysis: analysisData.clusters_analysis || null  // 🆕 NUEVO: Añadir clusters analysis
    };

    setAIOverviewResults(displayData);
    
    // Logging de guardado global
    if (window) {
      window.currentAIOverviewData = displayData;
      console.log('[AI DEBUG] Guardado en window.currentAIOverviewData:', window.currentAIOverviewData);
    }
    
    console.log('Mostrando resultados:', {
      summary: displayData.summary,
      keywordResults: displayData.keywordResults
    });

    displayAIOverviewResults(displayData);
    
    if (statusSpan) {
      statusSpan.textContent = `Análisis completo`;
      statusSpan.style.color = '#28a745';
    }

  } catch (error) {
    // Limpiar intervalos y progreso en caso de error
    if (typeof progressInterval !== 'undefined') {
      clearInterval(progressInterval);
    }
    
    // Mostrar error en la barra de progreso
    const progressContainer = document.querySelector('.ai-progress-container');
    if (progressContainer) {
      const progressText = document.querySelector('.ai-progress-text');
      const progressFill = document.querySelector('.ai-progress-bar-fill');
      
      if (progressText) progressText.textContent = 'Error en el análisis';
      if (progressFill) {
        progressFill.style.background = 'var(--error-color)';
        progressFill.style.width = '100%';
      }
      
      // Ocultar después de 3 segundos
      setTimeout(() => {
        progressContainer.style.transition = 'opacity 0.5s ease';
        progressContainer.style.opacity = '0';
        setTimeout(() => progressContainer.remove(), 500);
      }, 3000);
    }
    
    handleAnalysisError(error, statusSpan, resultsContainer);
    
  } finally {
    analyzeBtn.disabled = false;
    analyzeBtn.innerHTML = originalText;
  }
}

function handleNoKeywordsFound(setAIOverviewResults, statusSpan, resultsContainer) {
  const results = { 
    candidates: { 
      total_candidates: 0,
      top_candidates: [],
      criteria_summary: {
                  criteria: ['Top keywords by clicks'],
        total_evaluated: 0
      }
    }, 
    analysis: { 
      summary: { 
        total_keywords_analyzed: 0, 
        keywords_with_ai_overview: 0, 
        keywords_with_ai_source: 0, 
        total_estimated_clicks_lost: 0
      }, 
      results: [] 
    } 
  };
  setAIOverviewResults(results);
  displayAIOverviewResults(results);
  if (statusSpan) {
    statusSpan.textContent = 'No keywords found to analyze.';
    statusSpan.style.color = '#17a2b8';
  }
      showToast('No keywords available for AI Overview analysis', 'info');
}

function handleAnalysisError(error, statusSpan, resultsContainer) {
  console.error('Error en analisis AI Overview:', error);

  // Map raw/technical errors to friendly user-facing messages
  const friendlyMessage = getFriendlyErrorMessage(error);

  resultsContainer.innerHTML = `
    <div class="alert alert-danger" style="
      background: rgba(220, 53, 69, 0.1);
      color: #721c24;
      padding: 1em;
      border-radius: 8px;
      border: 1px solid rgba(220, 53, 69, 0.2);
      margin: 1em 0;
    ">
      <h4><i class="fas fa-exclamation-triangle"></i> Analysis Error</h4>
      <p>${friendlyMessage}</p>
    </div>
  `;

  showToast(friendlyMessage, 'error', 5000);

  if (statusSpan) {
    statusSpan.textContent = 'Analysis error';
    statusSpan.style.color = '#dc3545';
  }
}

function getFriendlyErrorMessage(error) {
  const msg = (error && error.message) ? error.message : String(error);

  // Already-friendly messages from analyzeAIOverview (402, 429, 400, 500)
  if (msg.includes('monthly analysis limit') ||
      msg.includes('paid plan') ||
      msg.includes('Upgrade')) {
    return msg;
  }

  // Network / connectivity errors
  if (msg.includes('Failed to fetch') ||
      msg.includes('NetworkError') ||
      msg.includes('network') ||
      msg.includes('ERR_INTERNET_DISCONNECTED')) {
    return 'Connection lost. Please check your internet and try again.';
  }

  // Timeout from AbortController
  if (msg.includes('took too long') || msg.includes('aborted') || msg.includes('timeout')) {
    return 'Analysis took too long. Try with fewer keywords.';
  }

  // Raw HTTP status codes that might leak through
  if (/HTTP\s*4(00|02|29)/i.test(msg) || /status\s*4(00|02|29)/i.test(msg) || /\b400\b/.test(msg)) {
    return 'Something went wrong with your request. Please try again.';
  }
  if (/HTTP\s*5\d{2}/i.test(msg) || /status\s*5\d{2}/i.test(msg) || /\b500\b/.test(msg)) {
    return 'Our servers are having a moment. Please try again in a few seconds.';
  }

  // Generic server error prefix
  if (msg.toLowerCase().startsWith('server error')) {
    return 'Our servers are having a moment. Please try again in a few seconds.';
  }

  // Fallback: return the original message (it is already friendly from our throw statements)
  return msg;
}