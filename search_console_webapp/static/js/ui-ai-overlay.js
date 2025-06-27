// static/js/ui-ai-overlay.js - Gestión del overlay y progreso de análisis IA

import { elems } from './utils.js';
import { runAIOverviewAnalysis } from './ui-ai-overview.js';

// Variables globales para el manejo del overlay
let currentKeywordData = null;
let currentSiteUrl = null;
let isAnalysisRunning = false;

/**
 * Inicializa la funcionalidad del overlay AI
 */
export function initAIOverlay() {
    console.log('🎯 Inicializando AI Overlay...');
    
    const executeBtn = document.getElementById('executeAIBtn');
    
    if (!executeBtn) {
        console.warn('Botón executeAIBtn no encontrado');
        return;
    }

    // Event listener para el botón de ejecutar análisis
    executeBtn.addEventListener('click', handleExecuteAnalysis);
    
    console.log('✅ AI Overlay inicializado correctamente');
}

/**
 * Actualiza los datos necesarios para habilitar el análisis
 */
export function updateAIOverlayData(keywordData, siteUrl) {
    console.log('📊 Actualizando datos AI Overlay:', { 
        keywordCount: keywordData?.length, 
        siteUrl 
    });
    
    currentKeywordData = keywordData;
    currentSiteUrl = siteUrl;
    
    const executeBtn = document.getElementById('executeAIBtn');
    const aiOverviewSection = document.getElementById('aiOverviewSection');
    
    if (executeBtn) {
        const hasValidData = keywordData && Array.isArray(keywordData) && keywordData.length > 0 && siteUrl;
        executeBtn.disabled = !hasValidData || isAnalysisRunning;
        
        if (!hasValidData) {
            executeBtn.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Datos requeridos';
        } else if (isAnalysisRunning) {
            executeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Analizando...';
        } else {
            executeBtn.innerHTML = '<i class="fas fa-play"></i> Ejecutar Análisis IA';
        }
    }
    
    // Mostrar la sección AI Overview cuando hay datos válidos
    if (aiOverviewSection && keywordData && keywordData.length > 0) {
        aiOverviewSection.style.display = 'block';
        console.log('🎯 Sección AI Overview mostrada');
    }
}

/**
 * Maneja el click en el botón de ejecutar análisis
 */
async function handleExecuteAnalysis() {
    console.log('🚀 Ejecutando análisis IA desde overlay...');
    
    if (!currentKeywordData || !currentSiteUrl || isAnalysisRunning) {
        console.warn('Análisis no disponible:', { 
            hasKeywords: !!currentKeywordData, 
            hasSiteUrl: !!currentSiteUrl, 
            isRunning: isAnalysisRunning 
        });
        return;
    }

    try {
        isAnalysisRunning = true;
        
        // Ocultar overlay inicial y mostrar progreso
        showProgressOverlay();
        
        // Iniciar progreso simple
        startSimpleProgress();
        
        // Ejecutar análisis real con progreso actualizado
        await runAIOverviewAnalysisWithProgress(currentKeywordData, currentSiteUrl);
        
        // Completar progreso y mostrar resultados
        await completeProgress();
        
        // Activar contenido real y ocultar placeholders
        activateRealContent();
        
        console.log('✅ Análisis IA completado exitosamente');
        
    } catch (error) {
        console.error('❌ Error en análisis IA:', error);
        showErrorState(error.message);
    } finally {
        isAnalysisRunning = false;
    }
}

/**
 * Muestra el overlay de progreso
 */
function showProgressOverlay() {
    const overlay = document.getElementById('aiOverlay');
    const progressOverlay = document.getElementById('aiProgressOverlay');
    
    if (overlay) {
        overlay.classList.add('hidden');
    }
    
    if (progressOverlay) {
        progressOverlay.classList.add('active');
    }
}

/**
 * Inicia el progreso simple y controlado
 */
function startSimpleProgress() {
    // Solo progreso inicial básico
    updateProgress(5, 'Seleccionando keywords prioritarias...', 'Analizando clics y rendimiento', 1);
    
    setTimeout(() => {
        updateProgress(15, 'Preparando análisis...', 'Iniciando consultas SERP', 2);
    }, 1000);
    
    // El resto del progreso será manejado por la función del análisis real
}

/**
 * Actualiza la barra de progreso
 */
function updateProgress(percentage, status, details, activeStep) {
    const progressCircle = document.getElementById('progressCircle');
    const progressPercentage = document.getElementById('progressPercentage');
    const progressStatus = document.getElementById('progressStatus');
    const progressDetails = document.getElementById('progressDetails');
    
    if (progressCircle) {
        const circumference = 2 * Math.PI * 45; // radio = 45
        const offset = circumference - (percentage / 100) * circumference;
        progressCircle.style.strokeDashoffset = offset;
    }
    
    if (progressPercentage) {
        progressPercentage.textContent = `${percentage}%`;
    }
    
    if (progressStatus) {
        progressStatus.textContent = status;
    }
    
    if (progressDetails) {
        progressDetails.textContent = details;
    }
    
    // Actualizar pasos
    for (let i = 1; i <= 4; i++) {
        const stepElement = document.getElementById(`step${i}`);
        if (stepElement) {
            stepElement.classList.remove('active', 'completed');
            if (i < activeStep) {
                stepElement.classList.add('completed');
            } else if (i === activeStep) {
                stepElement.classList.add('active');
            }
        }
    }
}

/**
 * Actualiza el progreso desde el análisis real (función exportada)
 */
export function updateRealProgress(percentage, message) {
    // Actualizar con datos reales (tiene preferencia sobre progreso automático)
    const step = percentage < 25 ? 1 : percentage < 50 ? 2 : percentage < 75 ? 3 : 4;
    updateProgress(percentage, message || 'Procesando...', 'Análisis en curso', step);
}

/**
 * Completa el progreso
 */
async function completeProgress() {
    // Detener cualquier progreso simulado
    if (window.aiProgressTimeout) {
        clearTimeout(window.aiProgressTimeout);
    }
    
    // Completar al 100%
    updateProgress(100, 'Análisis completado!', 'Preparando resultados...', 4);
    
    // Marcar todos los pasos como completados
    for (let i = 1; i <= 4; i++) {
        const stepElement = document.getElementById(`step${i}`);
        if (stepElement) {
            stepElement.classList.add('completed');
            stepElement.classList.remove('active');
        }
    }
    
    // Esperar un momento antes de ocultar
    await new Promise(resolve => setTimeout(resolve, 1500));
    
    // Ocultar overlay de progreso
    const progressOverlay = document.getElementById('aiProgressOverlay');
    if (progressOverlay) {
        progressOverlay.classList.remove('active');
    }
}

/**
 * Activa el contenido real y oculta placeholders
 */
function activateRealContent() {
    const contentWrapper = document.getElementById('aiContentWrapper');
    const placeholderData = document.getElementById('aiPlaceholderData');
    const analysisMessage = document.getElementById('aiAnalysisMessage');
    const resultsContainer = document.getElementById('aiOverviewResultsContainer');
    
    if (contentWrapper) {
        contentWrapper.classList.remove('blurred');
        contentWrapper.classList.add('active');
    }
    
    if (placeholderData) {
        placeholderData.style.display = 'none';
    }
    
    if (analysisMessage) {
        analysisMessage.style.display = 'block';
    }
    
    if (resultsContainer) {
        resultsContainer.style.display = 'block';
    }
    
    console.log('🎯 Contenido real activado');
}

/**
 * Muestra estado de error
 */
function showErrorState(errorMessage) {
    const progressOverlay = document.getElementById('aiProgressOverlay');
    const overlay = document.getElementById('aiOverlay');
    
    // Ocultar progreso
    if (progressOverlay) {
        progressOverlay.classList.remove('active');
    }
    
    // Mostrar overlay con mensaje de error
    if (overlay) {
        overlay.classList.remove('hidden');
        overlay.innerHTML = `
            <div class="ai-overlay-content">
                <i class="fas fa-exclamation-triangle ai-overlay-icon" style="color: #f44336;"></i>
                <h3 class="ai-overlay-title">Error en el Análisis</h3>
                <p class="ai-overlay-subtitle">${errorMessage}</p>
                <button class="btn-execute-ai" onclick="location.reload()">
                    <i class="fas fa-refresh"></i>
                    Reintentar
                </button>
            </div>
        `;
    }
    
    console.error('💥 Estado de error mostrado:', errorMessage);
}

/**
 * Reinicia el overlay a su estado inicial
 */
export function resetAIOverlay() {
    const contentWrapper = document.getElementById('aiContentWrapper');
    const placeholderData = document.getElementById('aiPlaceholderData');
    const analysisMessage = document.getElementById('aiAnalysisMessage');
    const resultsContainer = document.getElementById('aiOverviewResultsContainer');
    const overlay = document.getElementById('aiOverlay');
    const progressOverlay = document.getElementById('aiProgressOverlay');
    
    // Limpiar intervalos y timeouts de progreso
    if (window.aiProgressInterval) {
        clearInterval(window.aiProgressInterval);
    }
    if (window.aiProgressTimeout) {
        clearTimeout(window.aiProgressTimeout);
    }
    
    // Resetear estados
    if (contentWrapper) {
        contentWrapper.classList.add('blurred');
        contentWrapper.classList.remove('active');
    }
    
    if (placeholderData) {
        placeholderData.style.display = 'block';
    }
    
    if (analysisMessage) {
        analysisMessage.style.display = 'none';
    }
    
    if (resultsContainer) {
        resultsContainer.style.display = 'none';
    }
    
    if (overlay) {
        overlay.classList.remove('hidden');
        // Restaurar contenido original del overlay
        overlay.innerHTML = `
            <div class="ai-overlay-content">
                <i class="fas fa-robot ai-overlay-icon"></i>
                <h3 class="ai-overlay-title">Análisis AI Overview</h3>
                <p class="ai-overlay-subtitle">
                    Analiza el impacto de AI Overview en tus keywords y descubre oportunidades de visibilidad
                </p>
                <button class="btn-execute-ai" id="executeAIBtn" disabled>
                    <i class="fas fa-play"></i>
                    Ejecutar Análisis IA
                </button>
            </div>
        `;
        
        // Re-añadir event listener
        const newExecuteBtn = document.getElementById('executeAIBtn');
        if (newExecuteBtn) {
            newExecuteBtn.addEventListener('click', handleExecuteAnalysis);
        }
    }
    
    if (progressOverlay) {
        progressOverlay.classList.remove('active');
    }
    
    isAnalysisRunning = false;
    
    console.log('🔄 AI Overlay reiniciado');
}

/**
 * Ejecuta el análisis IA con actualizaciones de progreso más realistas
 */
async function runAIOverviewAnalysisWithProgress(keywordData, siteUrl) {
    // Progreso secuencial simple sin competencia
    
    // Limpiar cualquier progreso anterior
    if (window.aiProgressTimeout) {
        clearTimeout(window.aiProgressTimeout);
    }
    
    // Progreso controlado durante el análisis
    setTimeout(() => {
        updateProgress(30, 'Conectando con APIs...', `Analizando ${keywordData.length} keywords`, 2);
    }, 2000);
    
    setTimeout(() => {
        updateProgress(50, 'Consultando SERPs...', 'Obteniendo resultados de búsqueda', 2);
    }, 4000);
    
    setTimeout(() => {
        updateProgress(70, 'Detectando AI Overview...', 'Analizando presencia de IA', 3);
    }, 8000);
    
    setTimeout(() => {
        updateProgress(85, 'Procesando resultados...', 'Calculando métricas finales', 4);
    }, 12000);
    
    // Ejecutar el análisis real
    const result = await runAIOverviewAnalysis(currentKeywordData, currentSiteUrl);
    
    return result;
}

/**
 * Verifica si el análisis está en curso
 */
export function isAIAnalysisRunning() {
    return isAnalysisRunning;
} 