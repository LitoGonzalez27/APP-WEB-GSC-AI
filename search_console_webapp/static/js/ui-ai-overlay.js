// static/js/ui-ai-overlay.js - Gestión del overlay y progreso de análisis IA

import { elems } from './utils.js';
import { runAIOverviewAnalysis } from './ui-ai-overview.js';

// Variables globales para el manejo del overlay
let currentKeywordData = null;
let currentSiteUrl = null;
let isAnalysisRunning = false;
// 🆕 NUEVO: Variables para progreso fidedigno
let aiProgressTimer = null;
let totalEstimatedTime = 0;
let currentPhase = 0;
let startTime = 0;

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
                    executeBtn.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Data Required';
    } else if (isAnalysisRunning) {
        executeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Analyzing...';
    } else {
        executeBtn.innerHTML = '<i class="fas fa-play"></i> Start AI Analysis';
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
 * 🆕 NUEVA: Calcula tiempo estimado basado en cantidad de keywords
 */
function calculateAIAnalysisTime(keywordCount) {
    // Tiempo base por keyword (basado en experiencia real)
    const baseTimePerKeyword = 1.5; // 1.5 segundos por keyword
    const overheadTime = 8; // tiempo fijo de conexión y setup
    const parallelFactor = 0.7; // factor de paralelización (30% más eficiente)
    
    const totalTime = ((keywordCount * baseTimePerKeyword) + overheadTime) * parallelFactor;
    
    console.log(`⏱️ Tiempo estimado para ${keywordCount} keywords: ${Math.round(totalTime)}s`);
    return Math.round(totalTime);
}

/**
 * 🆕 NUEVA: Formatea tiempo en formato amigable
 */
function formatEstimatedTime(seconds) {
    if (seconds < 60) {
        return `~${seconds} seconds`;
    }
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    
    if (remainingSeconds === 0) {
        return `~${minutes} minute${minutes > 1 ? 's' : ''}`;
    }
    
    return `~${minutes}m ${remainingSeconds}s`;
}

/**
 * 🔄 MODIFICADA: Inicia progreso realista basado en cantidad de keywords
 */
function startRealisticProgress(keywordCount) {
    console.log(`🚀 Iniciando progreso realista para ${keywordCount} keywords`);
    
    // Limpiar cualquier timer anterior
    if (aiProgressTimer) {
        clearTimeout(aiProgressTimer);
        aiProgressTimer = null;
    }
    
    // Calcular tiempo total estimado
    totalEstimatedTime = calculateAIAnalysisTime(keywordCount) * 1000; // en milisegundos
    startTime = Date.now();
    currentPhase = 0;
    
    // Definir fases proporcionales al trabajo real
    const phases = [
        { 
            percentage: 12, 
            message: 'Preparing analysis...', 
            details: `Configuring analysis for ${keywordCount} keywords`,
            duration: totalEstimatedTime * 0.08 // 8% del tiempo total
        },
        { 
            percentage: 25, 
            message: 'Connecting to APIs...', 
            details: 'Authenticating and establishing connections',
            duration: totalEstimatedTime * 0.10 // 10% del tiempo total
        },
        { 
            percentage: 65, 
            message: 'Querying SERPs...', 
            details: `Processing ${keywordCount} keywords in parallel`,
            duration: totalEstimatedTime * 0.55 // 55% del tiempo total (la mayor parte)
        },
        { 
            percentage: 80, 
            message: 'Detecting AI Overview...', 
            details: 'Analyzing AI presence in results',
            duration: totalEstimatedTime * 0.15 // 15% del tiempo total
        },
        { 
            percentage: 92, 
            message: 'Processing results...', 
            details: 'Calculating metrics and statistics',
            duration: totalEstimatedTime * 0.10 // 10% del tiempo total
        },
        { 
            percentage: 98, 
            message: 'Finalizing analysis...', 
            details: 'Preparing data visualization',
            duration: totalEstimatedTime * 0.02 // 2% del tiempo total
        }
    ];
    
    // Función para ejecutar cada fase
    function executePhase(phaseIndex) {
        if (phaseIndex >= phases.length) {
            console.log('✅ Todas las fases de progreso completadas');
            return;
        }
        
        const phase = phases[phaseIndex];
        currentPhase = phaseIndex;
        
        console.log(`📊 Fase ${phaseIndex + 1}: ${phase.message} (${phase.percentage}%)`);
        updateProgress(phase.percentage, phase.message, phase.details, Math.min(phaseIndex + 1, 4));
        
        // Programar siguiente fase
        aiProgressTimer = setTimeout(() => {
            executePhase(phaseIndex + 1);
        }, phase.duration);
    }
    
    // Iniciar con progreso inicial inmediato
    updateProgress(5, 'Starting analysis...', `Analyzing ${keywordCount} selected keywords`, 1);
    
    // Comenzar las fases después de un breve delay
    setTimeout(() => executePhase(0), 800);
}

/**
 * 🔄 MODIFICADA: Actualiza progreso con información más detallada
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
        progressPercentage.textContent = `${Math.round(percentage)}%`;
    }
    
    if (progressStatus) {
        progressStatus.textContent = status;
    }
    
    if (progressDetails) {
        progressDetails.textContent = details;
    }
    
    // 🆕 NUEVO: Actualizar tiempo restante estimado
    const timeRemainingElement = document.getElementById('timeRemaining');
    if (timeRemainingElement && totalEstimatedTime > 0) {
        const elapsedTime = Date.now() - startTime;
        const remainingTime = Math.max(0, totalEstimatedTime - elapsedTime);
        const remainingSeconds = Math.ceil(remainingTime / 1000);
        
        if (remainingSeconds > 0) {
            timeRemainingElement.textContent = `${formatEstimatedTime(remainingSeconds)} remaining`;
            timeRemainingElement.style.color = '#667eea';
        } else {
            timeRemainingElement.textContent = 'Almost done...';
            timeRemainingElement.style.color = '#28a745';
        }
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
 * 🔄 MODIFICADA: Inicia progreso simple considerando cantidad de keywords
 */
function startSimpleProgress() {
    // Obtener cantidad de keywords seleccionada del dropdown
    const keywordCountSelect = document.getElementById('keywordCountSelect');
    const selectedCount = keywordCountSelect ? parseInt(keywordCountSelect.value) : 50;
    
    console.log(`🎯 Iniciando progreso para ${selectedCount} keywords seleccionadas`);
    
    // Mostrar tiempo estimado en la UI
    const estimatedSeconds = calculateAIAnalysisTime(selectedCount);
    const progressDetails = document.getElementById('progressDetails');
    if (progressDetails) {
        progressDetails.textContent = `Estimated analysis: ${formatEstimatedTime(estimatedSeconds)}`;
    }
    
    // Progreso inicial inmediato
    updateProgress(3, 'Validating configuration...', `Preparing analysis of ${selectedCount} keywords`, 1);
    
    // Iniciar progreso realista
    setTimeout(() => {
        startRealisticProgress(selectedCount);
    }, 500);
}

/**
 * 🔄 MODIFICADA: Completa progreso con cleanup mejorado
 */
async function completeProgress() {
    console.log('🏁 Completando progreso...');
    
    // Limpiar cualquier timer de progreso
    if (aiProgressTimer) {
        clearTimeout(aiProgressTimer);
        aiProgressTimer = null;
    }
    
    // Progreso final
    updateProgress(100, 'Analysis completed!', 'Preparing results visualization...', 4);
    
    // Marcar todos los pasos como completados
    for (let i = 1; i <= 4; i++) {
        const stepElement = document.getElementById(`step${i}`);
        if (stepElement) {
            stepElement.classList.add('completed');
            stepElement.classList.remove('active');
        }
    }
    
    // Actualizar tiempo final
    const timeRemainingElement = document.getElementById('timeRemaining');
    if (timeRemainingElement) {
        timeRemainingElement.textContent = 'Complete!';
        timeRemainingElement.style.color = '#28a745';
    }
    
    // Esperar un momento antes de ocultar (permitir que usuario vea el 100%)
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    // Ocultar overlay de progreso
    const progressOverlay = document.getElementById('aiProgressOverlay');
    if (progressOverlay) {
        progressOverlay.classList.remove('active');
    }
    
    // Limpiar variables
    totalEstimatedTime = 0;
    currentPhase = 0;
    startTime = 0;
}

/**
 * 🔄 REEXPORTADA: Actualiza el progreso desde el análisis real (función exportada)
 */
export function updateRealProgress(percentage, message) {
    // Actualizar con datos reales (tiene preferencia sobre progreso automático)
    const step = percentage < 25 ? 1 : percentage < 50 ? 2 : percentage < 75 ? 3 : 4;
    const details = message ? 'Analysis in progress' : `Processing keywords...`;
    updateProgress(percentage, message || 'Processing...', details, step);
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
                <h3 class="ai-overlay-title">Analysis Error</h3>
                <p class="ai-overlay-subtitle">${errorMessage}</p>
                <button class="btn-execute-ai" onclick="location.reload()">
                    <i class="fas fa-refresh"></i>
                    Retry
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
    
    // 🆕 NUEVO: Limpiar timers y variables de progreso fidedigno
    if (aiProgressTimer) {
        clearTimeout(aiProgressTimer);
        aiProgressTimer = null;
    }
    
    // Limpiar intervalos y timeouts de progreso (legacy)
    if (window.aiProgressInterval) {
        clearInterval(window.aiProgressInterval);
    }
    if (window.aiProgressTimeout) {
        clearTimeout(window.aiProgressTimeout);
    }
    
    // 🆕 NUEVO: Resetear variables de progreso fidedigno
    totalEstimatedTime = 0;
    currentPhase = 0;
    startTime = 0;
    
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
                <h3 class="ai-overlay-title">Execute AI Analysis</h3>
                <p class="ai-overlay-subtitle">
                    Analyze the impact of AI Overview on your keywords and discover visibility opportunities
                </p>
                
                <!-- Dropdown de cantidad de keywords -->
                <div class="ai-keyword-count-selector">
                    <label for="keywordCountSelect">
                        <i class="fas fa-list-ol"></i> Keywords to analyze:
                    </label>
                    <select id="keywordCountSelect">
                        <option value="25">25 keywords</option>
                        <option value="50" selected>50 keywords</option>
                        <option value="100">100 keywords</option>
                        <option value="150">150 keywords</option>
                    </select>
                </div>
                
                <button class="btn-execute-ai" id="executeAIBtn" disabled>
                    <i class="fas fa-play"></i>
                    Start AI Analysis
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
 * 🔄 MODIFICADA: Ejecuta el análisis con progreso fidedigno
 */
async function runAIOverviewAnalysisWithProgress(keywordData, siteUrl) {
    console.log(`🚀 Ejecutando análisis con progreso fidedigno para ${keywordData.length} keywords`);
    
    // Limpiar cualquier progreso anterior
    if (aiProgressTimer) {
        clearTimeout(aiProgressTimer);
        aiProgressTimer = null;
    }
    
    // El progreso ya se inició en startSimpleProgress(), 
    // aquí solo ejecutamos el análisis real
    const result = await runAIOverviewAnalysis(currentKeywordData, currentSiteUrl);
    
    return result;
}

/**
 * Verifica si el análisis está en curso
 */
export function isAIAnalysisRunning() {
    return isAnalysisRunning;
} 