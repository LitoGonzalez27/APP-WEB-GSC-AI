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
  
  // Mostrar modal
  const modal = document.getElementById('progressModal');
  if (!modal) {
    console.error('Modal not found');
    return;
  }
  
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
      
      // Remover del DOM si es necesario
      if (isMobile) {
        setTimeout(() => {
          if (modal.parentNode) {
            modal.parentNode.removeChild(modal);
          }
        }, 100);
      }
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