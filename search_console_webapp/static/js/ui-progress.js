// =============================================
// MODERN PROGRESS MODAL - SIMPLIFIED & SMOOTH
// =============================================

// Variables
let stepsCache = [];
let fakeTimer = null;
let currentStep = 0;
let currentProgress = 0;

// Fun facts en inglés
const FUN_FACTS = [
  "Octopuses have three hearts and blue blood.",
  "Bees can recognize human faces — just like dogs!",
  "It can literally rain diamonds on Jupiter and Saturn.",
  "A single teaspoon of a neutron star would weigh about a billion tons.",
  "Flamingos aren't born pink — their color comes from what they eat.",
  "Human DNA is about 60% identical to that of bananas.",
  "There are more possible ways to shuffle a deck of cards than atoms in the known universe.",
  "A blue whale's heart is so big a human could swim through its arteries.",
  "There's an island in Japan that's inhabited only by rabbits — it's called Ōkunoshima!",
  "Sharks have existed longer than trees."
];

// Mensajes de paso en inglés
const STEP_MESSAGES = [
  "Validating dates and preparing query…",
  "Getting main period data…", 
  "Getting comparison period data…",
  "Processing URL metrics…",
  "Calculating period comparisons…",
  "Generating summaries and charts…",
  "Finishing analysis…"
];

/**
 * Mostrar el modal de progreso
 */
export function showProgress(steps) {
  console.log('🚀 Starting simple progress with steps:', steps);
  
  // Limpiar timers previos
  if (fakeTimer) {
    clearTimeout(fakeTimer);
    fakeTimer = null;
  }
  
  // Inicializar variables
  stepsCache = steps;
  currentStep = 0;
  currentProgress = 0;
  
  // Buscar modal existente
  let modal = document.getElementById('progressModal');
  
  // ✅ NUEVO: Si el modal no existe (fue removido en análisis anteriores), recrearlo
  if (!modal) {
    console.log('🔄 Modal de progreso no encontrado, recreando...');
    createProgressModal();
    modal = document.getElementById('progressModal');
  }
  
  if (!modal) {
    console.error('❌ No se pudo crear o encontrar el modal de progreso');
    return;
  }
  
  // ✅ NUEVO: Resetear estilos que podrían haber quedado del cierre anterior
  modal.style.display = '';
  modal.style.opacity = '';
  modal.style.visibility = '';
  modal.style.pointerEvents = '';
  modal.style.zIndex = '';
  modal.style.transition = '';
  
  modal.classList.add('show');
  document.body.classList.add('modal-open');
  
  // Inicializar UI
  initializeUI();
  
  // Iniciar progreso suave
  startSmoothProgress();
  
  // Iniciar fun facts
  startFunFacts();
}

/**
 * Inicializar la UI
 */
function initializeUI() {
  // Resetear progreso circular
  updateCircularProgress(0);
  
  // Resetear porcentaje
  updatePercentage(0);
  
  // Crear indicadores de pasos
  createStepIndicators();
  
  // Mostrar primer mensaje
  updateStatusMessage(stepsCache[0] || 'Starting analysis...', 'Preparing to process your data...');
  
  // Mostrar primer fun fact
  showRandomFunFact();
  
  // Configurar total de pasos
  const totalElement = document.getElementById('totalStepsNumber');
  if (totalElement) {
    totalElement.textContent = stepsCache.length;
  }
  
  // Configurar paso actual
  const currentElement = document.getElementById('currentStepNumber');
  if (currentElement) {
    currentElement.textContent = '1';
  }
}

/**
 * Iniciar progreso suave
 */
function startSmoothProgress() {
  console.log('📊 Starting smooth progress animation');
  
  function progressStep() {
    // Si ya completamos, salir
    if (currentProgress >= 90) {
      console.log('📊 Progress simulation complete at 90%');
      return;
    }
    
    // Incremento aleatorio pequeño para fluidez
    const increment = Math.random() * 2 + 0.5; // 0.5% a 2.5%
    const newProgress = Math.min(currentProgress + increment, 90);
    
    // Actualizar progreso
    updateCircularProgress(newProgress);
    updatePercentage(Math.round(newProgress));
    currentProgress = newProgress;
    
    // Actualizar paso si es necesario
    updateCurrentStep();
    
    // Continuar animación
    const delay = Math.random() * 300 + 200; // 200-500ms
    fakeTimer = setTimeout(progressStep, delay);
  }
  
  // Iniciar después de un pequeño delay
  fakeTimer = setTimeout(progressStep, 500);
}

/**
 * Actualizar paso actual basado en progreso
 */
function updateCurrentStep() {
  const stepProgress = Math.floor((currentProgress / 90) * stepsCache.length);
  
  if (stepProgress > currentStep && stepProgress < stepsCache.length) {
    currentStep = stepProgress;
    
    // Actualizar mensaje de estado
    const stepName = stepsCache[currentStep];
    const friendlyMessage = getFriendlyMessage(stepName);
    updateStatusMessage(friendlyMessage.title, friendlyMessage.detail);
    
    // Actualizar contador de pasos
    const currentElement = document.getElementById('currentStepNumber');
    if (currentElement) {
      currentElement.textContent = currentStep + 1;
    }
    
    // Actualizar indicador visual
    updateStepIndicator(currentStep);
    
    console.log(`📊 Advanced to step ${currentStep + 1}: ${friendlyMessage.title}`);
  }
}

/**
 * Actualizar progreso circular
 */
function updateCircularProgress(percentage) {
  const circle = document.getElementById('progressCircleFill');
  if (!circle) return;
  
  const circumference = 2 * Math.PI * 54; // radio = 54
  const offset = circumference - (percentage / 100) * circumference;
  circle.style.strokeDashoffset = offset;
}

/**
 * Actualizar porcentaje mostrado
 */
function updatePercentage(percentage) {
  const element = document.getElementById('progressPercentageNumber');
  if (element) {
    element.textContent = percentage;
  }
}

/**
 * Actualizar mensaje de estado
 */
function updateStatusMessage(title, detail) {
  const titleElement = document.getElementById('progressCurrentStep');
  const detailElement = document.getElementById('progressCurrentDetail');
  
  if (titleElement) {
    titleElement.textContent = title;
  }
  
  if (detailElement) {
    detailElement.textContent = detail;
  }
}

/**
 * Crear indicadores de pasos
 */
function createStepIndicators() {
  const container = document.getElementById('progressStepsContainer');
  if (!container) return;
  
  container.innerHTML = '';
  
  stepsCache.forEach((step, index) => {
    const stepElement = document.createElement('div');
    stepElement.className = 'progress-step-item';
    stepElement.setAttribute('data-step', index);
    container.appendChild(stepElement);
  });
}

/**
 * Actualizar indicador de paso
 */
function updateStepIndicator(stepIndex) {
  // Marcar pasos anteriores como completados
  for (let i = 0; i < stepIndex; i++) {
    const element = document.querySelector(`[data-step="${i}"]`);
    if (element) {
      element.classList.remove('active');
      element.classList.add('completed');
    }
  }
  
  // Marcar paso actual como activo
  const currentElement = document.querySelector(`[data-step="${stepIndex}"]`);
  if (currentElement) {
    currentElement.classList.remove('completed');
    currentElement.classList.add('active');
  }
}

/**
 * Obtener mensaje amigable para un paso
 */
function getFriendlyMessage(stepName) {
  const lowerName = stepName.toLowerCase();
  
  if (lowerName.includes('validat')) {
    return {
      title: "Validating Parameters",
      detail: "Checking your date ranges and authentication"
    };
  } else if (lowerName.includes('main') || lowerName.includes('primary')) {
    return {
      title: "Fetching Primary Data",
      detail: "Retrieving Search Console metrics for your selected period"
    };
  } else if (lowerName.includes('comparison')) {
    return {
      title: "Fetching Comparison Data",
      detail: "Getting comparison period metrics for analysis"
    };
  } else if (lowerName.includes('url') || lowerName.includes('page')) {
    return {
      title: "Processing URL Metrics",
      detail: "Analyzing individual page performance data"
    };
  } else if (lowerName.includes('calculat') || lowerName.includes('compar')) {
    return {
      title: "Calculating Changes",
      detail: "Computing performance deltas and trends"
    };
  } else if (lowerName.includes('generat') || lowerName.includes('summar') || lowerName.includes('chart')) {
    return {
      title: "Generating Reports",
      detail: "Creating summaries, charts and insights"
    };
  } else if (lowerName.includes('finish') || lowerName.includes('final')) {
    return {
      title: "Finalizing Analysis",
      detail: "Preparing your performance dashboard"
    };
  } else {
    return {
      title: stepName,
      detail: "Processing your Search Console data..."
    };
  }
}

/**
 * Iniciar fun facts
 */
function startFunFacts() {
  let factIndex = 0;
  
  function showNextFact() {
    showFunFact(FUN_FACTS[factIndex]);
    factIndex = (factIndex + 1) % FUN_FACTS.length;
    
    // Cambiar cada 8 segundos
    setTimeout(showNextFact, 8000);
  }
  
  // Iniciar después de 6 segundos
  setTimeout(showNextFact, 6000);
}

/**
 * Mostrar fun fact
 */
function showFunFact(fact) {
  const element = document.getElementById('progressFunFact');
  if (!element) return;
  
  const span = element.querySelector('span');
  if (span) {
    span.textContent = fact;
  }
}

/**
 * Mostrar fun fact aleatorio
 */
function showRandomFunFact() {
  const randomFact = FUN_FACTS[Math.floor(Math.random() * FUN_FACTS.length)];
  showFunFact(randomFact);
}

/**
 * Completar progreso con detección móvil y cierre robusto
 */
export function completeProgress() {
  console.log('✅ Completing progress');
  
  // Detectar dispositivo móvil
  const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
                   window.innerWidth <= 768 ||
                   'ontouchstart' in window ||
                   navigator.maxTouchPoints > 0;
  
  console.log(`📱 Device detection: ${isMobile ? 'Mobile' : 'Desktop'}`);
  
  // Limpiar timer
  if (fakeTimer) {
    clearTimeout(fakeTimer);
    fakeTimer = null;
  }
  
  // Completar al 100%
  updateCircularProgress(100);
  updatePercentage(100);
  
  // Marcar todos los pasos como completados
  stepsCache.forEach((_, index) => {
    const element = document.querySelector(`[data-step="${index}"]`);
    if (element) {
      element.classList.remove('active');
      element.classList.add('completed');
    }
  });
  
  // Mensaje final
  updateStatusMessage("Analysis Complete!", "Your performance dashboard is ready");
  
  // Actualizar tiempo estimado
  const timeElement = document.getElementById('timeEstimate');
  if (timeElement) {
    timeElement.textContent = "Complete!";
    timeElement.style.color = '#28a745';
  }
  
  // Fun fact final
  setTimeout(() => {
    const factElement = document.getElementById('progressFunFact');
    if (factElement) {
      const span = factElement.querySelector('span');
      const icon = factElement.querySelector('i');
      if (span && icon) {
        icon.className = 'fas fa-check-circle';
        span.textContent = "Your detailed performance analysis is now available below!";
        factElement.style.background = 'rgba(40, 167, 69, 0.1)';
        factElement.style.borderColor = 'rgba(40, 167, 69, 0.3)';
      }
    }
  }, 1000);
  
  // ✅ NUEVO: Configurar timeouts adaptativos con delay adicional para renderizado
  const mobileDelayMultiplier = isMobile ? 2.5 : 1;
  const renderingDelay = isMobile ? 2000 : 1000; // Tiempo extra para renderizado
  const baseDelay = (isMobile ? 4000 : 2500) + renderingDelay; // Sumar delay de renderizado
  const maxAttempts = isMobile ? 5 : 3;
  
  console.log(`⏱️ Using ${isMobile ? 'mobile' : 'desktop'} timeouts: base=${baseDelay}ms (incluye ${renderingDelay}ms para renderizado), maxAttempts=${maxAttempts}`);
  
  // ✅ NUEVO: Verificar si hay resultados que renderizar antes de cerrar
  let hasResultsToRender = false;
  
  // Verificar elementos que indican que hay resultados
  const checkForResults = () => {
    const resultsTables = document.querySelectorAll('#resultsTable, #keywordComparisonTable');
    const resultsSection = document.getElementById('resultsSection');
    const keywordsSection = document.getElementById('keywordsSection');
    
    hasResultsToRender = Array.from(resultsTables).some(table => {
      const tbody = table.querySelector('tbody');
      return tbody && tbody.children.length > 0;
    }) || (resultsSection && resultsSection.style.display !== 'none') ||
         (keywordsSection && keywordsSection.style.display !== 'none');
    
    console.log(`🔍 Results to render check: ${hasResultsToRender}`);
    return hasResultsToRender;
  };
  
  // Sistema de cierre robusto con múltiples intentos
  let closeAttempt = 0;
  
  function attemptModalClose() {
    closeAttempt++;
    const modal = document.getElementById('progressModal');
    
    console.log(`🔄 Close attempt ${closeAttempt}/${maxAttempts} - Modal found: ${!!modal}`);
    
    if (modal) {
      // ✅ NUEVO: En móviles, verificar si los resultados están listos antes de cerrar
      if (isMobile && closeAttempt === 1) {
        const resultsReady = checkForResults();
        if (!resultsReady) {
          console.log('📱 Mobile device: Waiting for results to render before closing modal...');
          // Esperar un poco más para que se rendericen los resultados
          setTimeout(attemptModalClose, 1500);
          return;
        }
      }
      
      // Verificar si el modal ya está oculto
      const isVisible = modal.classList.contains('show') || 
                       getComputedStyle(modal).display !== 'none';
      
      if (isVisible) {
        console.log(`🚪 Closing modal (attempt ${closeAttempt})`);
        
        // ✅ NUEVO: Mensaje de estado antes del cierre
        updateStatusMessage("Displaying Results", "Loading your dashboard...");
        
        // Cierre gradual para móviles para permitir renderizado
        if (isMobile) {
          // Primero reducir opacidad gradualmente
          modal.style.transition = 'opacity 0.5s ease-out';
          modal.style.opacity = '0.7';
          
          setTimeout(() => {
            modal.style.opacity = '0.3';
            setTimeout(() => {
              modal.style.transition = 'none';
              modal.style.opacity = '0';
              modal.style.visibility = 'hidden';
              modal.style.pointerEvents = 'none';
              modal.classList.remove('show');
            }, 250);
          }, 250);
        } else {
          modal.classList.remove('show');
        }
        
        document.body.classList.remove('modal-open');
        
        // Reset inmediato de variables
        currentProgress = 0;
        currentStep = 0;
        stepsCache = [];
        
        // Verificar cierre después de un tiempo
        setTimeout(() => {
          verifyModalClosed(closeAttempt);
        }, isMobile ? 800 : 300);
        
      } else {
        console.log('✅ Modal already closed');
        finalizeCleanup();
      }
    } else {
      console.log('❌ Modal element not found');
      finalizeCleanup();
    }
  }
  
  function verifyModalClosed(attemptNumber) {
    const modal = document.getElementById('progressModal');
    
    if (modal) {
      const isStillVisible = modal.classList.contains('show') || 
                            getComputedStyle(modal).display !== 'none' ||
                            parseFloat(getComputedStyle(modal).opacity) > 0.1;
      
      if (isStillVisible && closeAttempt < maxAttempts) {
        console.log(`⚠️ Modal still visible after attempt ${attemptNumber}, retrying...`);
        
        // Incrementar delay para el siguiente intento
        const retryDelay = baseDelay * (closeAttempt * 0.5);
        setTimeout(attemptModalClose, retryDelay);
        
      } else if (isStillVisible && closeAttempt >= maxAttempts) {
        console.log('🆘 Max attempts reached, forcing modal close');
        forceModalClose();
        
      } else {
        console.log('✅ Modal successfully closed');
        finalizeCleanup();
      }
    } else {
      console.log('✅ Modal removed from DOM');
      finalizeCleanup();
    }
  }
  
  function forceModalClose() {
    console.log('🔨 Force closing modal');
    const modal = document.getElementById('progressModal');
    
    if (modal) {
      // Remover todas las clases y estilos
      modal.classList.remove('show');
      modal.style.display = 'none';
      modal.style.opacity = '0';
      modal.style.visibility = 'hidden';
      modal.style.pointerEvents = 'none';
      modal.style.zIndex = '-9999';
      
      // ✅ MEJORADO: No remover del DOM para evitar problemas en análisis posteriores
      // El modal se reutilizará en futuros análisis
      console.log('🔄 Modal ocultado pero mantenido en DOM para reutilización');
    }
    
    // Limpiar body
    document.body.classList.remove('modal-open');
    document.body.style.overflow = '';
    
    finalizeCleanup();
  }
  
  function finalizeCleanup() {
    console.log('🧹 Finalizing cleanup');
    
    // Reset completo de variables
    currentProgress = 0;
    currentStep = 0;
    stepsCache = [];
    
    // Limpiar cualquier timer restante
    if (fakeTimer) {
      clearTimeout(fakeTimer);
      fakeTimer = null;
    }
    
    // Restaurar body scroll
    document.body.style.overflow = '';
    document.body.classList.remove('modal-open');
    
    // ✅ NUEVO: Verificar que los resultados sean visibles después del cierre
    setTimeout(() => {
      const resultsVisible = checkForResults();
      console.log(`📊 Results visible after modal close: ${resultsVisible}`);
      
      if (resultsVisible) {
        // Scroll suave hacia los resultados en móviles
        if (isMobile) {
          const resultsSection = document.getElementById('resultsSection') || 
                               document.getElementById('keywordsSection');
          if (resultsSection) {
            resultsSection.scrollIntoView({ 
              behavior: 'smooth', 
              block: 'start' 
            });
          }
        }
      }
    }, 500);
    
    // Trigger evento personalizado para notificar que el modal se cerró
    document.dispatchEvent(new CustomEvent('progressModalClosed', {
      detail: { 
        device: isMobile ? 'mobile' : 'desktop',
        attempts: closeAttempt,
        hasResults: hasResultsToRender
      }
    }));
    
    console.log('✅ Progress modal cleanup complete');
  }
  
  // Iniciar el primer intento de cierre después del delay base
  console.log(`⏰ Scheduling modal close in ${baseDelay}ms`);
  setTimeout(attemptModalClose, baseDelay);
}

/**
 * ✅ NUEVA FUNCIÓN: Crear el modal de progreso si no existe
 */
function createProgressModal() {
  console.log('🛠️ Creando modal de progreso...');
  
  const modalHTML = `
    <div id="progressModal" class="modal" role="dialog" aria-labelledby="progressModalTitle" aria-describedby="progressModalDesc">
      <div class="modal-dialog">
        <div class="progress-modal-content">
          <!-- Header with branding -->
          <div class="progress-modal-header">
            <div class="progress-brand">
              <div class="progress-logo" aria-hidden="true">
                <i class="fas fa-chart-line"></i>
              </div>
              <div class="progress-brand-text">
                <h3 id="progressModalTitle">Performance Analysis</h3>
                <p id="progressModalDesc">Processing your Search Console data</p>
              </div>
            </div>
            <div class="progress-time-estimate">
              <span class="time-label">Estimated time:</span>
              <span class="time-value" id="timeEstimate" aria-live="polite">~45 seconds</span>
            </div>
          </div>

          <!-- Main progress section -->
          <div class="progress-modal-body">
            <div class="progress-main-display">
              <!-- Circular progress -->
              <div class="progress-circle-container">
                <svg class="progress-circle" viewBox="0 0 120 120" aria-hidden="true">
                  <defs>
                    <linearGradient id="progressGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                      <stop offset="0%" style="stop-color:#4285f4;stop-opacity:1" />
                      <stop offset="50%" style="stop-color:#34a853;stop-opacity:1" />
                      <stop offset="100%" style="stop-color:#ea4335;stop-opacity:1" />
                    </linearGradient>
                  </defs>
                  <circle 
                    class="progress-circle-bg" 
                    cx="60" 
                    cy="60" 
                    r="54" 
                    fill="none" 
                    stroke="rgba(255,255,255,0.1)" 
                    stroke-width="8">
                  </circle>
                  <circle 
                    class="progress-circle-fill" 
                    id="progressCircleFill"
                    cx="60" 
                    cy="60" 
                    r="54" 
                    fill="none" 
                    stroke="url(#progressGradient)" 
                    stroke-width="8" 
                    stroke-linecap="round"
                    stroke-dasharray="339.292"
                    stroke-dashoffset="339.292"
                    transform="rotate(-90 60 60)">
                  </circle>
                </svg>
                <div class="progress-percentage">
                  <span id="progressPercentageNumber" aria-live="polite">0</span>%
                </div>
              </div>

              <!-- Status display -->
              <div class="progress-status">
                <h4 id="progressCurrentStep" aria-live="polite">Starting analysis...</h4>
                <p id="progressCurrentDetail">Preparing to process your data...</p>
                
                <div class="progress-step-counter">
                  Step <span id="currentStepNumber" aria-live="polite">1</span> of <span id="totalStepsNumber">7</span>
                </div>
              </div>
            </div>

            <!-- Step indicators -->
            <div class="progress-steps-visual">
              <div id="progressStepsContainer" class="progress-steps-container" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"></div>
            </div>

            <!-- Fun facts section -->
            <div class="progress-fun-section">
              <div id="progressFunFact" class="progress-fun-fact">
                <i class="fas fa-lightbulb" aria-hidden="true"></i>
                <span>Did you know? Loading fun facts...</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;
  
  // Insertar el modal en el body
  document.body.insertAdjacentHTML('beforeend', modalHTML);
  
  console.log('✅ Modal de progreso creado exitosamente');
}