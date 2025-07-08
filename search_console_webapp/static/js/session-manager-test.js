/**
 * SessionManager - VERSIÓN DE TESTING
 * Con tiempos reducidos para facilitar las pruebas
 */

class SessionManagerTest {
    constructor(options = {}) {
        // ⚠️ CONFIGURACIÓN DE TESTING - Tiempos muy reducidos
        this.config = {
            checkInterval: 5000,         // Verificar cada 5 segundos (en lugar de 30)
            warningTime: 30,            // Mostrar advertencia a los 30 segundos (en lugar de 300)
            keepAliveInterval: 15000,   // Keep-alive cada 15 segundos (en lugar de 300)
            debug: true,                // Debug siempre activado
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

        // Elementos del DOM
        this.warningModal = null;
        this.countdownElement = null;

        console.log('🧪 SessionManagerTest inicializado con configuración de testing');
        console.log('📊 Configuración:', this.config);

        // Inicializar
        this.init();
    }

    init() {
        this.log('SessionManagerTest inicializado');
        this.setupActivityDetection();
        this.startSessionChecking();
        this.startKeepAlive();
        this.createWarningModal();
        
        // ⚠️ AVISO DE TESTING
        setTimeout(() => {
            console.log('🧪 MODO TESTING ACTIVADO');
            console.log('⏰ Advertencia aparecerá cuando queden 30 segundos');
            console.log('🔄 Verificaciones cada 5 segundos');
            console.log('📡 Keep-alive cada 15 segundos');
        }, 1000);
    }

    setupActivityDetection() {
        const activityEvents = [
            'mousedown', 'mousemove', 'keypress', 'scroll', 
            'touchstart', 'click', 'focus', 'blur',
            'resize', 'wheel'
        ];

        const handleActivity = () => {
            this.onUserActivity();
        };

        activityEvents.forEach(event => {
            document.addEventListener(event, this.throttle(handleActivity, 1000), true);
        });

        this.log('Detección de actividad configurada');
    }

    onUserActivity() {
        this.lastActivity = Date.now();
        this.isActive = true;

        if (this.warningShown) {
            this.hideWarning();
        }

        this.log('🎯 Actividad detectada - Timer reseteado');
    }

    startSessionChecking() {
        this.checkTimer = setInterval(() => {
            this.checkSessionStatus();
        }, this.config.checkInterval);

        this.checkSessionStatus();
    }

    async checkSessionStatus() {
        try {
            const response = await fetch('/auth/status');
            const data = await response.json();

            if (!data.authenticated) {
                this.handleSessionExpired(data);
                return;
            }

            this.sessionData = data.session || {};
            const remainingSeconds = this.sessionData.remaining_seconds || 0;

            this.log(`🔍 Verificación: ${remainingSeconds}s restantes`);

            if (remainingSeconds <= this.config.warningTime && remainingSeconds > 0) {
                this.log(`⚠️ Tiempo crítico: ${remainingSeconds}s - Mostrando advertencia`);
                this.showWarning(remainingSeconds);
            } else if (remainingSeconds <= 0) {
                this.log('💀 Sesión expirada por servidor');
                this.handleSessionExpired({ session_expired: true });
            }

        } catch (error) {
            this.log('❌ Error verificando estado de sesión:', error);
        }
    }

    startKeepAlive() {
        this.keepAliveTimer = setInterval(() => {
            // Siempre enviar para verificar estado, pero indicar si hay actividad real
            this.sendKeepAlive();
        }, this.config.keepAliveInterval);
    }

    async sendKeepAlive() {
        try {
            // Verificar si el usuario ha estado activo recientemente
            const timeSinceActivity = Date.now() - this.lastActivity;
            const userActive = timeSinceActivity < this.config.keepAliveInterval;

            this.log(`📡 Enviando keep-alive. Usuario activo: ${userActive ? '✅' : '❌'}`);

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
                this.log(`✅ Keep-alive exitoso. Usuario activo: ${data.user_active}. Tiempo restante: ${data.remaining_seconds}s`);
            } else {
                this.log('❌ Error en keep-alive:', response.status);
            }

        } catch (error) {
            this.log('❌ Error enviando keep-alive:', error);
        }
    }

    createWarningModal() {
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
                        <h3>🧪 TESTING - Sesión a punto de expirar</h3>
                    </div>
                    <div class="session-warning-body">
                        <p><strong>MODO TESTING ACTIVADO</strong></p>
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

        const styles = `
            <style>
                .session-warning-modal {
                    position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: 10000;
                    display: flex; align-items: center; justify-content: center;
                }
                .session-warning-overlay {
                    position: absolute; top: 0; left: 0; width: 100%; height: 100%;
                    background: rgba(0, 0, 0, 0.7); backdrop-filter: blur(3px);
                }
                .session-warning-content {
                    position: relative; background: white; border-radius: 12px; padding: 2rem;
                    max-width: 500px; margin: 1rem; box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
                    animation: sessionWarningSlideIn 0.3s ease-out;
                }
                @keyframes sessionWarningSlideIn {
                    from { opacity: 0; transform: translateY(-20px) scale(0.95); }
                    to { opacity: 1; transform: translateY(0) scale(1); }
                }
                .session-warning-header { display: flex; align-items: center; margin-bottom: 1.5rem; color: #ff6b35; }
                .session-warning-header i { font-size: 1.5rem; margin-right: 0.75rem; }
                .session-warning-header h3 { margin: 0; font-size: 1.25rem; font-weight: 600; }
                .session-warning-body { margin-bottom: 2rem; line-height: 1.6; color: #333; }
                .countdown { font-weight: bold; color: #dc3545; font-size: 1.1em; }
                .session-warning-actions { display: flex; gap: 1rem; justify-content: flex-end; }
                .session-warning-actions .btn {
                    padding: 0.75rem 1.5rem; border: none; border-radius: 6px; font-weight: 500;
                    cursor: pointer; display: flex; align-items: center; gap: 0.5rem; transition: all 0.2s ease;
                }
                .btn-primary { background: #007bff; color: white; }
                .btn-primary:hover { background: #0056b3; transform: translateY(-1px); }
                .btn-secondary { background: #6c757d; color: white; }
                .btn-secondary:hover { background: #545b62; transform: translateY(-1px); }
            </style>
        `;

        document.head.insertAdjacentHTML('beforeend', styles);
        document.body.insertAdjacentHTML('beforeend', modalHTML);

        this.warningModal = document.getElementById('sessionWarningModal');
        this.countdownElement = document.getElementById('sessionCountdown');

        document.getElementById('extendSessionBtn').addEventListener('click', () => {
            this.extendSession();
        });

        document.getElementById('logoutNowBtn').addEventListener('click', () => {
            this.logoutNow();
        });
    }

    showWarning(remainingSeconds) {
        if (this.warningShown) return;

        this.warningShown = true;
        this.warningModal.style.display = 'flex';
        this.startCountdown(remainingSeconds);

        this.log('⚠️ Advertencia de expiración mostrada');
    }

    hideWarning() {
        if (!this.warningShown) return;

        this.warningShown = false;
        this.warningModal.style.display = 'none';

        if (this.countdownTimer) {
            clearInterval(this.countdownTimer);
            this.countdownTimer = null;
        }

        this.log('✅ Advertencia de expiración ocultada');
    }

    startCountdown(initialSeconds) {
        let seconds = initialSeconds;
        
        const updateCountdown = () => {
            this.countdownElement.textContent = seconds;
            this.log(`⏱️ Countdown: ${seconds}s restantes`);
            
            if (seconds <= 0) {
                clearInterval(this.countdownTimer);
                this.handleSessionExpired({ session_expired: true });
                return;
            }
            
            seconds--;
        };

        updateCountdown();
        this.countdownTimer = setInterval(updateCountdown, 1000);
    }

    async extendSession() {
        try {
            this.log('🔄 Usuario eligió extender sesión');
            
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
                this.log('✅ Sesión extendida manualmente. Tiempo restante:', data.remaining_seconds);
                this.hideWarning();
                
                if (window.navbar && typeof window.navbar.showToast === 'function') {
                    window.navbar.showToast('✅ Sesión extendida correctamente', 'success');
                }
            } else {
                this.log('❌ Error extendiendo sesión:', response.status);
            }
            
        } catch (error) {
            this.log('❌ Error extendiendo sesión:', error);
        }
    }

    async logoutNow() {
        this.log('🚪 Usuario eligió cerrar sesión');
        this.hideWarning();
        
        if (window.navbar && typeof window.navbar.handleLogout === 'function') {
            window.navbar.handleLogout();
        } else {
            window.location.href = '/auth/logout';
        }
    }

    handleSessionExpired(data) {
        this.log('💀 Sesión expirada:', data);
        this.cleanup();

        if (window.navbar && typeof window.navbar.showToast === 'function') {
            window.navbar.showToast('Tu sesión ha expirado por inactividad. Redirigiendo...', 'warning');
        }

        setTimeout(() => {
            window.location.href = '/login?session_expired=true';
        }, 2000);
    }

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

    log(...args) {
        console.log('[SessionManagerTest]', ...args);
    }

    destroy() {
        this.cleanup();
        
        if (this.warningModal) {
            this.warningModal.remove();
        }
    }
}

// ⚠️ SOLO PARA TESTING - No usar en producción
window.SessionManagerTest = SessionManagerTest; 