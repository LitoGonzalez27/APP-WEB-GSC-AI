/**
 * SessionManager - Gestión de sesiones con detección de inactividad
 * Detecta actividad del usuario y maneja la expiración automática de sesión
 */

class SessionManager {
    constructor(options = {}) {
        // Configuración por defecto
        this.config = {
            checkInterval: 60000,        // Verificar cada 60 segundos (REDUCIDO para evitar conflictos)
            warningTime: 300,           // Mostrar advertencia a los 5 minutos (300 segundos)
            keepAliveInterval: 300000,  // Enviar keepalive cada 5 minutos
            debug: false,
            ...options
        };

        // Estado interno
        this.isActive = true;
        this.lastActivity = Date.now();
        this.sessionData = null;
        this.warningShown = false;
        this.checkTimer = null;
        this.keepAliveTimer = null;
        this.activityTimeout = null;
        this.isPaused = false; // ✅ NUEVO: Estado de pausa
        this.isChecking = false; // ✅ NUEVO: Evitar verificaciones simultáneas

        // Elementos del DOM
        this.warningModal = null;
        this.countdownElement = null;

        // Inicializar
        this.init();
    }

    init() {
        this.log('SessionManager inicializado');
        this.setupActivityDetection();
        this.startSessionChecking();
        this.startKeepAlive();
        this.createWarningModal();
    }

    /**
     * Configurar detección de actividad del usuario
     */
    setupActivityDetection() {
        // Eventos que indican actividad del usuario
        const activityEvents = [
            'mousedown', 'mousemove', 'keypress', 'scroll', 
            'touchstart', 'click', 'focus', 'blur',
            'resize', 'wheel'
        ];

        // Función para manejar actividad
        const handleActivity = () => {
            this.onUserActivity();
        };

        // Agregar listeners con throttling para optimizar rendimiento
        activityEvents.forEach(event => {
            document.addEventListener(event, this.throttle(handleActivity, 1000), true);
        });

        this.log('Detección de actividad configurada');
    }

    /**
     * Manejar actividad del usuario
     */
    onUserActivity() {
        this.lastActivity = Date.now();
        this.isActive = true;

        // Si hay una advertencia mostrada, ocultarla
        if (this.warningShown) {
            this.hideWarning();
        }

        this.log('Actividad detectada');
    }

    /**
     * Iniciar verificación periódica del estado de la sesión
     */
    startSessionChecking() {
        this.checkTimer = setInterval(() => {
            this.checkSessionStatus();
        }, this.config.checkInterval);

        // Verificar inmediatamente
        this.checkSessionStatus();
    }

    /**
     * ✅ NUEVO: Pausar la verificación de la sesión
     */
    pause() {
        this.isPaused = true;
        this.log('El verificador de sesión está en pausa.');
    }

    /**
     * ✅ NUEVO: Reanudar la verificación de la sesión
     */
    resume() {
        this.isPaused = false;
        this.log('El verificador de sesión se ha reanudado.');
        // Forzar una verificación inmediata para sincronizar el estado
        this.checkSessionStatus();
    }
    
    /**
     * Verificar el estado de la sesión en el servidor
     */
    async checkSessionStatus() {
        // ✅ NUEVO: No hacer nada si el gestor está en pausa
        if (this.isPaused) {
            this.log('Verificación omitida porque el gestor está en pausa.');
            return;
        }

        // ✅ NUEVO: Evitar verificaciones simultáneas
        if (this.isChecking) {
            this.log('Verificación ya en progreso, omitiendo...');
            return;
        }

        this.isChecking = true;

        try {
            // ✅ NUEVO: Timeout para evitar bloqueos
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 segundos timeout

            const response = await fetch('/auth/status', {
                signal: controller.signal
            });
            clearTimeout(timeoutId);
            
            const data = await response.json();

            if (!data.authenticated) {
                this.handleSessionExpired(data);
                return;
            }

            // Actualizar datos de sesión
            this.sessionData = data.session || {};
            const remainingSeconds = this.sessionData.remaining_seconds || 0;

            this.log(`Sesión activa. Tiempo restante: ${remainingSeconds}s`);

            // Verificar si necesitamos mostrar advertencia
            if (remainingSeconds <= this.config.warningTime && remainingSeconds > 0) {
                this.showWarning(remainingSeconds);
            } else if (remainingSeconds <= 0) {
                this.handleSessionExpired({ session_expired: true });
            }

        } catch (error) {
            this.log('Error verificando estado de sesión:', error);
            // En caso de error de red, no hacer nada drástico
        } finally {
            this.isChecking = false; // ✅ NUEVO: Liberar el bloqueo
        }
    }

    /**
     * Iniciar sistema de keep-alive
     */
    startKeepAlive() {
        this.keepAliveTimer = setInterval(() => {
            // Siempre enviar keep-alive para verificar estado, pero indicar si hay actividad real
            this.sendKeepAlive();
        }, this.config.keepAliveInterval);
    }

    /**
     * Enviar señal de keep-alive al servidor
     */
    async sendKeepAlive() {
        try {
            // Verificar si el usuario ha estado activo recientemente
            const timeSinceActivity = Date.now() - this.lastActivity;
            const userActive = timeSinceActivity < this.config.keepAliveInterval;

            const response = await fetch('/auth/keepalive', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    user_active: userActive
                })
            });

            if (response.ok) {
                const data = await response.json();
                this.log(
                    `Keep-alive enviado. Usuario activo: ${data.user_active}. Tiempo restante: ${data.remaining_seconds}s`
                );
            } else {
                this.log('Error en keep-alive:', response.status);
            }

        } catch (error) {
            this.log('Error enviando keep-alive:', error);
        }
    }

    /**
     * Crear modal de advertencia de expiración
     */
    createWarningModal() {
        // Crear el modal si no existe
        if (document.getElementById('sessionWarningModal')) {
            this.warningModal = document.getElementById('sessionWarningModal');
            return;
        }

        const modalHTML = `
            <div id="sessionWarningModal" class="session-warning-modal" style="display: none;">
                <div class="session-warning-overlay"></div>
                <div class="session-warning-content">
                    <div class="session-warning-header">
                        <i class="fas fa-exclamation-triangle"></i>
                        <h3>Sesión a punto de expirar</h3>
                    </div>
                    <div class="session-warning-body">
                        <p>Tu sesión expirará en <span id="sessionCountdown" class="countdown">0</span> segundos por inactividad.</p>
                        <p>¿Deseas mantener tu sesión activa?</p>
                    </div>
                    <div class="session-warning-actions">
                        <button id="extendSessionBtn" class="btn btn-primary">
                            <i class="fas fa-refresh"></i>
                            Mantener sesión activa
                        </button>
                        <button id="logoutNowBtn" class="btn btn-secondary">
                            <i class="fas fa-sign-out-alt"></i>
                            Cerrar sesión
                        </button>
                    </div>
                </div>
            </div>
        `;

        // Agregar estilos CSS
        const styles = `
            <style>
                .session-warning-modal {
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    z-index: 10000;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }

                .session-warning-overlay {
                    position: absolute;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(0, 0, 0, 0.7);
                    backdrop-filter: blur(3px);
                }

                .session-warning-content {
                    position: relative;
                    background: white;
                    border-radius: 12px;
                    padding: 2rem;
                    max-width: 500px;
                    margin: 1rem;
                    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
                    animation: sessionWarningSlideIn 0.3s ease-out;
                }

                @keyframes sessionWarningSlideIn {
                    from {
                        opacity: 0;
                        transform: translateY(-20px) scale(0.95);
                    }
                    to {
                        opacity: 1;
                        transform: translateY(0) scale(1);
                    }
                }

                .session-warning-header {
                    display: flex;
                    align-items: center;
                    margin-bottom: 1.5rem;
                    color: #ff6b35;
                }

                .session-warning-header i {
                    font-size: 1.5rem;
                    margin-right: 0.75rem;
                }

                .session-warning-header h3 {
                    margin: 0;
                    font-size: 1.25rem;
                    font-weight: 600;
                }

                .session-warning-body {
                    margin-bottom: 2rem;
                    line-height: 1.6;
                    color: #333;
                }

                .countdown {
                    font-weight: bold;
                    color: #dc3545;
                    font-size: 1.1em;
                }

                .session-warning-actions {
                    display: flex;
                    gap: 1rem;
                    justify-content: flex-end;
                }

                .session-warning-actions .btn {
                    padding: 0.75rem 1.5rem;
                    border: none;
                    border-radius: 6px;
                    font-weight: 500;
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    gap: 0.5rem;
                    transition: all 0.2s ease;
                }

                .session-warning-actions .btn-primary {
                    background: #007bff;
                    color: white;
                }

                .session-warning-actions .btn-primary:hover {
                    background: #0056b3;
                    transform: translateY(-1px);
                }

                .session-warning-actions .btn-secondary {
                    background: #6c757d;
                    color: white;
                }

                .session-warning-actions .btn-secondary:hover {
                    background: #545b62;
                    transform: translateY(-1px);
                }

                @media (max-width: 768px) {
                    .session-warning-content {
                        margin: 1rem;
                        padding: 1.5rem;
                    }

                    .session-warning-actions {
                        flex-direction: column;
                    }

                    .session-warning-actions .btn {
                        width: 100%;
                        justify-content: center;
                    }
                }
            </style>
        `;

        // Agregar al DOM
        document.head.insertAdjacentHTML('beforeend', styles);
        document.body.insertAdjacentHTML('beforeend', modalHTML);

        // Obtener referencias
        this.warningModal = document.getElementById('sessionWarningModal');
        this.countdownElement = document.getElementById('sessionCountdown');

        // Configurar eventos
        document.getElementById('extendSessionBtn').addEventListener('click', () => {
            this.extendSession();
        });

        document.getElementById('logoutNowBtn').addEventListener('click', () => {
            this.logoutNow();
        });
    }

    /**
     * Mostrar advertencia de expiración
     */
    showWarning(remainingSeconds) {
        if (this.warningShown) return;

        this.warningShown = true;
        this.warningModal.style.display = 'flex';

        // Iniciar countdown
        this.startCountdown(remainingSeconds);

        this.log('Advertencia de expiración mostrada');
    }

    /**
     * Ocultar advertencia
     */
    hideWarning() {
        if (!this.warningShown) return;

        this.warningShown = false;
        this.warningModal.style.display = 'none';

        // Limpiar countdown
        if (this.countdownTimer) {
            clearInterval(this.countdownTimer);
            this.countdownTimer = null;
        }

        this.log('Advertencia de expiración ocultada');
    }

    /**
     * Iniciar countdown en el modal
     */
    startCountdown(initialSeconds) {
        let seconds = initialSeconds;
        
        const updateCountdown = () => {
            this.countdownElement.textContent = seconds;
            
            if (seconds <= 0) {
                clearInterval(this.countdownTimer);
                this.handleSessionExpired({ session_expired: true });
                return;
            }
            
            seconds--;
        };

        // Actualizar inmediatamente
        updateCountdown();

        // Actualizar cada segundo
        this.countdownTimer = setInterval(updateCountdown, 1000);
    }

    /**
     * Extender la sesión (respuesta del usuario)
     */
    async extendSession() {
        try {
            // Marcar actividad primero
            this.onUserActivity();
            
            // Enviar keep-alive con confirmación explícita de actividad
            const response = await fetch('/auth/keepalive', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    user_active: true  // Siempre true cuando el usuario extiende manualmente
                })
            });

            if (response.ok) {
                const data = await response.json();
                this.log('Sesión extendida manualmente. Tiempo restante:', data.remaining_seconds);
                this.hideWarning();
                
                // Mostrar mensaje de confirmación
                if (window.navbar && typeof window.navbar.showToast === 'function') {
                    window.navbar.showToast('Sesión extendida correctamente', 'success');
                }
            } else {
                this.log('Error extendiendo sesión:', response.status);
            }
            
        } catch (error) {
            this.log('Error extendiendo sesión:', error);
        }
    }

    /**
     * Cerrar sesión manualmente
     */
    async logoutNow() {
        this.hideWarning();
        
        if (window.navbar && typeof window.navbar.handleLogout === 'function') {
            window.navbar.handleLogout();
        } else {
            window.location.href = '/auth/logout';
        }
    }

    /**
     * Manejar expiración de sesión
     */
    handleSessionExpired(data) {
        this.log('Sesión expirada:', data);
        
        // Limpiar timers
        this.cleanup();

        // Mostrar mensaje
        if (window.navbar && typeof window.navbar.showToast === 'function') {
            window.navbar.showToast('Tu sesión ha expirado por inactividad. Redirigiendo...', 'warning');
        }

        // Redirigir al login
        setTimeout(() => {
            window.location.href = '/login?session_expired=true';
        }, 2000);
    }

    /**
     * Función de throttling para optimizar eventos
     */
    throttle(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        }
    }

    /**
     * Limpiar recursos
     */
    cleanup() {
        if (this.checkTimer) {
            clearInterval(this.checkTimer);
            this.checkTimer = null;
        }

        if (this.keepAliveTimer) {
            clearInterval(this.keepAliveTimer);
            this.keepAliveTimer = null;
        }

        if (this.countdownTimer) {
            clearInterval(this.countdownTimer);
            this.countdownTimer = null;
        }

        this.hideWarning();
    }

    /**
     * Logging con control de debug
     */
    log(...args) {
        if (this.config.debug) {
            console.log('[SessionManager]', ...args);
        }
    }

    /**
     * Destruir la instancia
     */
    destroy() {
        this.cleanup();
        
        // Remover modal del DOM
        if (this.warningModal) {
            this.warningModal.remove();
        }
    }
}

// ✅ MODIFICADO: No auto-inicializar, solo definir función de inicialización
// La inicialización es controlada por session-init.js

function initializeSessionManager(options = {}) {
    if (window.sessionManager) {
        console.warn('SessionManager ya está inicializado.');
        return window.sessionManager;
    }

    // Configuración por defecto
    const defaultConfig = {
        checkInterval: 60000,      // Verificar cada 60 seg (reducido para evitar conflictos)
        warningTime: 300,          // Advertencia a los 5 minutos  
        keepAliveInterval: 300000, // Keep-alive cada 5 min
        debug: localStorage.getItem('session_debug') === 'true'
    };

    // Combinar configuración por defecto con opciones pasadas
    const config = { ...defaultConfig, ...options };

    const sessionManagerInstance = new SessionManager(config);

    // Hacer la instancia accesible globalmente
    window.sessionManager = sessionManagerInstance;

    return sessionManagerInstance;
}

// ✅ NUEVO: Exportar función para uso controlado
window.initializeSessionManager = initializeSessionManager; 