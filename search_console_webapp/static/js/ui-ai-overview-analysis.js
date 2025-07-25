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
                    <span class="ai-progress-current">0</span> de <span class="ai-progress-total">0</span> keywords procesadas
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
    
    if (progressText) progressText.textContent = status || `Analizando keywords en paralelo...`;
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
            progressText.textContent = `¡Análisis completado! ${withAI}/${total} keywords con AI Overview detectado`;
        } else {
            progressText.textContent = '¡Análisis completado exitosamente!';
        }
    }
    
    if (progressPercentage) progressPercentage.textContent = '100%';
    if (progressSpinner) progressSpinner.style.display = 'none';
    
    if (progressFill) {
        progressFill.style.width = '100%';
        progressFill.style.background = 'linear-gradient(90deg, var(--success-color), #4CAF50)';
    }
    
    // Ocultar la barra después de 3 segundos para dar tiempo a leer el resultado
    setTimeout(() => {
        const progressContainer = document.querySelector('.ai-progress-container');
        if (progressContainer) {
            progressContainer.style.transition = 'opacity 0.5s ease';
            progressContainer.style.opacity = '0';
            setTimeout(() => progressContainer.remove(), 500);
        }
    }, 3000);
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
        return response.json();
    } catch (error) {
        clearTimeout(timeoutId);
        if (error.name === 'AbortError') {
            throw new Error('El análisis ha tardado demasiado tiempo. Intenta con menos keywords.');
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
    showToast('No hay datos disponibles para análisis', 'error');
    return;
  }

  let parsedKeywordData;
  try {
    parsedKeywordData = JSON.parse(keywordData);
  } catch (e) {
    console.error('Error parseando datos de keywords:', e);
    showToast('Error en los datos de keywords', 'error');
    return;
  }

  if (!parsedKeywordData.length) {
    showToast('No hay datos de keywords para analizar', 'warning');
    return;
  }

  const originalText = analyzeBtn.innerHTML;
  analyzeBtn.disabled = true;
  analyzeBtn.innerHTML = `${createSpinner()} Analizando...`;
  
  if (statusSpan) {
    statusSpan.textContent = 'Seleccionando top keywords por tráfico...';
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
  
  // Pequeño delay para que la animación de entrada sea visible
  await new Promise(resolve => setTimeout(resolve, 100));
  
  try {
    // ✅ NUEVO: Simplificado - tomar top 30 keywords por clics directamente
    console.log(`[AI DEBUG] Analizando top keywords de ${parsedKeywordData.length} total`, parsedKeywordData);
    
    // Actualizar progreso: seleccionando keywords
    updateProgressBar(0, 30, 'Seleccionando top keywords por clics...');
    
    // Ordenar por clics descendente y tomar las top 30
    const topKeywords = parsedKeywordData
      .sort((a, b) => (b.clicks_m1 || 0) - (a.clicks_m1 || 0))
      .slice(0, 30);
    
    console.log('[AI DEBUG] Top keywords seleccionadas:', topKeywords);

    if (statusSpan) {
      statusSpan.textContent = `Analizando ${topKeywords.length} keywords en paralelo (optimizado)...`;
      statusSpan.style.color = '#17a2b8';
    }

    if (topKeywords.length === 0) {
      handleNoKeywordsFound(setAIOverviewResults, statusSpan, resultsContainer);
      return;
    }

    console.log(`[AI DEBUG] Enviando a análisis top ${topKeywords.length} keywords:`, topKeywords.map(k => k.keyword).slice(0, 5), '...');

    // Actualizar progreso: iniciando análisis
    updateProgressBar(0, topKeywords.length, `Iniciando análisis paralelo de ${topKeywords.length} keywords...`);
    
    // Notificación de inicio
    showToast(`Iniciando análisis paralelo de ${topKeywords.length} keywords`, 'info', 3000);
    
    // Simular progreso durante el análisis
    const progressInterval = setInterval(() => {
      const current = Math.min(
        document.querySelector('.ai-progress-current')?.textContent || 0,
        topKeywords.length - 5
      );
      const nextValue = parseInt(current) + Math.floor(Math.random() * 3) + 1;
      if (nextValue < topKeywords.length) {
        updateProgressBar(nextValue, topKeywords.length, 'Procesando keywords en paralelo...');
      }
    }, 1000);

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
      showToast(`Análisis completado: ${withAI}/${total} keywords con AI Overview`, 'success', 4000);
    } else {
      showToast('Análisis de AI Overview completado exitosamente', 'success');
    }

    console.log('[AI DEBUG] Datos recibidos del análisis:', analysisData);

    if (analysisData.error) {
      throw new Error(analysisData.error);
    }

    const displayData = {
      analysis: analysisData,
      candidates: { 
        total_candidates: topKeywords.length,
        top_candidates: topKeywords,
        criteria_summary: {
          criteria: ['Top keywords por clics (sin filtros adicionales)'],
          total_evaluated: parsedKeywordData.length
        }
      },
      summary: analysisData.summary || {},
      keywordResults: analysisData.results || []
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
        criteria: ['Top keywords por clics'],
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
    statusSpan.textContent = 'No se encontraron keywords para analizar.';
    statusSpan.style.color = '#17a2b8';
  }
  showToast('No hay keywords disponibles para análisis AI Overview', 'info');
}

function handleAnalysisError(error, statusSpan, resultsContainer) {
  console.error('Error en análisis AI Overview:', error);
  
  resultsContainer.innerHTML = `
    <div class="alert alert-danger" style="
      background: rgba(220, 53, 69, 0.1);
      color: #721c24;
      padding: 1em;
      border-radius: 8px;
      border: 1px solid rgba(220, 53, 69, 0.2);
      margin: 1em 0;
    ">
      <h4><i class="fas fa-exclamation-triangle"></i> Error en el análisis</h4>
      <p>${error.message}</p>
      <p><small>Por favor, verifica tu conexión y vuelve a intentarlo.</small></p>
    </div>
  `;
  
  showToast(`Error: ${error.message}`, 'error', 5000);
  
  if (statusSpan) {
    statusSpan.textContent = 'Error en el análisis';
    statusSpan.style.color = '#dc3545';
  }
}