/**
 * Inicializador centralizado del SessionManager
 * Evita conflictos entre múltiples sistemas de verificación
 */

// ✅ Global flag para evitar múltiples inicializaciones
window.sessionManagerInitialized = false;

function initializeSessionManagerSafely() {
    // Evitar inicialización múltiple
    if (window.sessionManagerInitialized) {
        console.log('✅ SessionManager ya inicializado, omitiendo...');
        return;
    }

    // No inicializar en páginas de login/signup
    const currentPath = window.location.pathname;
    const isAuthPage = ['/login', '/signup', '/'].includes(currentPath);
    
    if (isAuthPage) {
        console.log('🚫 No inicializar SessionManager en páginas de autenticación');
        return;
    }

    try {
        // Destruir cualquier SessionManager previo
        if (window.sessionManager) {
            console.log('🔄 Destruyendo SessionManager previo...');
            window.sessionManager.destroy();
            window.sessionManager = null;
        }

        // Inicializar nuevo SessionManager
        console.log('🚀 Inicializando SessionManager...');
        window.sessionManager = new SessionManager({
            debug: localStorage.getItem('session_debug') === 'true',
            checkInterval: 60000,  // 1 minuto
            warningTime: 300       // 5 minutos
        });

        window.sessionManagerInitialized = true;
        console.log('✅ SessionManager inicializado correctamente');

    } catch (error) {
        console.error('❌ Error inicializando SessionManager:', error);
    }
}

// ✅ Función para pausar todas las verificaciones durante transiciones
function pauseAllSessionChecks() {
    if (window.sessionManager) {
        window.sessionManager.pause();
    }
    console.log('⏸️ Verificaciones de sesión pausadas');
}

// ✅ Función para reanudar verificaciones
function resumeAllSessionChecks() {
    if (window.sessionManager) {
        window.sessionManager.resume();
    }
    console.log('▶️ Verificaciones de sesión reanudadas');
}

// ✅ Inicialización cuando el DOM esté listo
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeSessionManagerSafely);
} else {
    initializeSessionManagerSafely();
}

// ✅ Exportar funciones globales
window.pauseAllSessionChecks = pauseAllSessionChecks;
window.resumeAllSessionChecks = resumeAllSessionChecks;
window.initializeSessionManagerSafely = initializeSessionManagerSafely; 