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
        
        // Limpiar TODOS los timers y animaciones en caso de error
        if (aiProgressTimer) { clearTimeout(aiProgressTimer); aiProgressTimer = null; }
        if (smoothAnimationId) { cancelAnimationFrame(smoothAnimationId); smoothAnimationId = null; }
        if (window.simpleProgressTimeout) { clearTimeout(window.simpleProgressTimeout); window.simpleProgressTimeout = null; }
        
        // ✅ NUEVO: Para paywalls/quotas, mostrar modal pero NO error genérico
        if (error.message === 'paywall' || error.message === 'quota_exceeded') {
            console.log('🚫 Paywall/quota error - modal mostrado, ocultando progreso');
            // Ocultar overlay de progreso inmediatamente
            const progressOverlay = document.getElementById('aiProgressOverlay');
            if (progressOverlay) {
                progressOverlay.classList.remove('active');
            }
            // NO mostrar showErrorState para paywalls (ya tienen modal)
        } else {
            // Solo mostrar error genérico para errores reales
            showErrorState(error.message);
        }
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
 * 🔄 MEJORADA v2: Progreso suave con interpolación frame-by-frame
 */
let smoothAnimationId = null;
let smoothPhases = [];
let smoothCurrentPct = 0;

function startRealisticProgress(keywordCount) {
    console.log(`🚀 Iniciando progreso fluido para ${keywordCount} keywords`);

    // Limpiar cualquier timer/animación anterior
    if (aiProgressTimer) { clearTimeout(aiProgressTimer); aiProgressTimer = null; }
    if (smoothAnimationId) { cancelAnimationFrame(smoothAnimationId); smoothAnimationId = null; }

    totalEstimatedTime = calculateAIAnalysisTime(keywordCount) * 1000;
    startTime = Date.now();
    currentPhase = 0;
    smoothCurrentPct = 3; // arrancamos desde el 3% que ya tiene startSimpleProgress

    // Fases con timestamps acumulados
    smoothPhases = [
        { pct: 10,  message: 'Preparing analysis...',     details: `Configuring for ${keywordCount} keywords`,  step: 1 },
        { pct: 20,  message: 'Connecting to APIs...',      details: 'Authenticating connections',                step: 1 },
        { pct: 38,  message: 'Querying SERPs...',          details: `Processing ${keywordCount} keywords`,       step: 2 },
        { pct: 56,  message: 'Analyzing results...',       details: 'Processing SERP data and rankings',         step: 2 },
        { pct: 72,  message: 'Detecting AI Overview...',   details: 'Analyzing AI presence in results',          step: 3 },
        { pct: 85,  message: 'Processing metrics...',      details: 'Calculating statistics',                    step: 3 },
        { pct: 95,  message: 'Finalizing analysis...',     details: 'Preparing visualization',                   step: 4 }
    ];

    // Calcular timestamps de inicio/fin para cada fase
    const timeSlices = [0.06, 0.08, 0.24, 0.20, 0.17, 0.15, 0.10];
    let accumulated = 0;
    smoothPhases.forEach((p, i) => {
        p.startTime = startTime + accumulated * totalEstimatedTime;
        accumulated += timeSlices[i];
        p.endTime = startTime + accumulated * totalEstimatedTime;
    });

    // Arrancar el loop de animación
    smoothAnimationTick();
}

function smoothAnimationTick() {
    const now = Date.now();
    const elapsed = now - startTime;
    const totalPct = Math.min((elapsed / totalEstimatedTime) * 97, 97); // Max 97% until real completion

    // Encontrar la fase actual
    let activePhase = smoothPhases[0];
    for (let i = smoothPhases.length - 1; i >= 0; i--) {
        if (now >= smoothPhases[i].startTime) {
            activePhase = smoothPhases[i];
            currentPhase = i;
            break;
        }
    }

    // Interpolar suavemente hacia el porcentaje objetivo
    const targetPct = Math.min(totalPct, activePhase.pct);
    // Easing: avanza más rápido al principio de cada fase, más lento al final
    smoothCurrentPct += (targetPct - smoothCurrentPct) * 0.08;

    // Actualizar UI con valores interpolados
    updateProgressSmooth(smoothCurrentPct, activePhase.message, activePhase.details, activePhase.step);

    // Continuar animación si no hemos llegado al máximo
    if (smoothCurrentPct < 96.5) {
        smoothAnimationId = requestAnimationFrame(smoothAnimationTick);
    } else {
        smoothAnimationId = null;
        console.log('✅ Progreso suave alcanzó el límite pre-completado');
    }
}

/**
 * Actualización de UI optimizada — sin accesos DOM redundantes
 */
function updateProgressSmooth(percentage, status, details, activeStep) {
    const progressCircle = document.getElementById('progressCircle');
    const progressPercentage = document.getElementById('progressPercentage');
    const progressStatus = document.getElementById('progressStatus');
    const progressDetails = document.getElementById('progressDetails');

    if (progressCircle) {
        const circumference = 2 * Math.PI * 45;
        const offset = circumference - (percentage / 100) * circumference;
        progressCircle.style.strokeDashoffset = offset;
    }

    const roundedPct = Math.round(percentage);
    if (progressPercentage && progressPercentage._lastPct !== roundedPct) {
        progressPercentage.textContent = `${roundedPct}%`;
        progressPercentage._lastPct = roundedPct;
    }

    if (progressStatus && progressStatus._lastMsg !== status) {
        progressStatus.textContent = status;
        progressStatus._lastMsg = status;
    }

    if (progressDetails && progressDetails._lastDet !== details) {
        progressDetails.textContent = details;
        progressDetails._lastDet = details;
    }

    // Tiempo restante — actualizar cada ~30 frames para evitar parpadeo
    if (totalEstimatedTime > 0 && roundedPct % 2 === 0) {
        const timeRemainingElement = document.getElementById('timeRemaining');
        if (timeRemainingElement) {
            const remainingMs = Math.max(0, totalEstimatedTime - (Date.now() - startTime));
            const remainingSec = Math.ceil(remainingMs / 1000);
            if (remainingSec > 0) {
                timeRemainingElement.textContent = `${formatEstimatedTime(remainingSec)} remaining`;
                timeRemainingElement.style.color = '#94A3B8';
            } else {
                timeRemainingElement.textContent = 'Almost done...';
                timeRemainingElement.style.color = '#28a745';
            }
        }
    }

    // Pasos — solo actualizar cuando cambian
    for (let i = 1; i <= 4; i++) {
        const stepElement = document.getElementById(`step${i}`);
        if (stepElement) {
            const shouldBeCompleted = i < activeStep;
            const shouldBeActive = i === activeStep;
            if (shouldBeCompleted && !stepElement.classList.contains('completed')) {
                stepElement.classList.remove('active');
                stepElement.classList.add('completed');
            } else if (shouldBeActive && !stepElement.classList.contains('active')) {
                stepElement.classList.remove('completed');
                stepElement.classList.add('active');
            }
        }
    }
}

/**
 * Wrapper — redirige a updateProgressSmooth para mantener compatibilidad
 */
function updateProgress(percentage, status, details, activeStep) {
    updateProgressSmooth(percentage, status, details, activeStep);
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
    
    // Iniciar progreso realista (guardar timer para poder cancelarlo)
    window.simpleProgressTimeout = setTimeout(() => {
        startRealisticProgress(selectedCount);
    }, 500);
}

/**
 * 🔄 MODIFICADA: Completa progreso con cleanup mejorado
 */
async function completeProgress() {
    console.log('🏁 Completando progreso...');

    // Cancelar TODAS las animaciones y timers
    if (aiProgressTimer) { clearTimeout(aiProgressTimer); aiProgressTimer = null; }
    if (smoothAnimationId) { cancelAnimationFrame(smoothAnimationId); smoothAnimationId = null; }
    if (window.simpleProgressTimeout) { clearTimeout(window.simpleProgressTimeout); window.simpleProgressTimeout = null; }

    // Animar suavemente de la posición actual hasta 100%
    const finalStart = smoothCurrentPct || 90;
    const finalDuration = 600; // 600ms para animar hasta 100%
    const finalStartTime = Date.now();

    await new Promise(resolve => {
        function animateToComplete() {
            const elapsed = Date.now() - finalStartTime;
            const t = Math.min(elapsed / finalDuration, 1);
            // Ease-out cubic
            const eased = 1 - Math.pow(1 - t, 3);
            const pct = finalStart + (100 - finalStart) * eased;

            updateProgressSmooth(pct, 'Analysis completed!', 'Preparing results...', 4);

            if (t < 1) {
                requestAnimationFrame(animateToComplete);
            } else {
                resolve();
            }
        }
        requestAnimationFrame(animateToComplete);
    });

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

    // Breve pausa para que el usuario vea el 100% (reducida de 2s a 800ms)
    await new Promise(resolve => setTimeout(resolve, 800));

    // Ocultar overlay de progreso con fade
    const progressOverlay = document.getElementById('aiProgressOverlay');
    if (progressOverlay) {
        progressOverlay.classList.remove('active');
    }

    // Limpiar variables
    totalEstimatedTime = 0;
    currentPhase = 0;
    startTime = 0;
    smoothCurrentPct = 0;
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
    
    // Limpiar timer de startSimpleProgress
    if (window.simpleProgressTimeout) {
        clearTimeout(window.simpleProgressTimeout);
        window.simpleProgressTimeout = null;
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
                        <option value="50" selected>50 keywords</option>
                        <option value="100">100 keywords</option>
                        <option value="200">200 keywords</option>
                        <option value="300">300 keywords</option>
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

// ✅ NUEVO: Hacer las funciones disponibles globalmente
window.resetAIOverlay = resetAIOverlay;
window.updateAIOverlayData = updateAIOverlayData;

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