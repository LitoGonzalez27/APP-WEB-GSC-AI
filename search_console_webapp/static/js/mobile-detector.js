/**
 * mobile-detector.js - Detector de dispositivos móviles del lado del cliente
 * Funciona como respaldo para la detección del servidor
 */

class MobileDetector {
    constructor() {
        this.isMobile = false;
        this.isTablet = false;
        this.deviceType = 'desktop';
        this.screenSize = {
            width: window.innerWidth,
            height: window.innerHeight
        };
        
        this.init();
    }

    init() {
        this.detectDevice();
        this.setupEventListeners();
        this.checkInitialState();
    }

    detectDevice() {
        const userAgent = navigator.userAgent.toLowerCase();
        
        // Detectar dispositivos móviles
        const mobilePatterns = [
            /android/i,
            /webos/i,
            /iphone/i,
            /ipad/i,
            /ipod/i,
            /blackberry/i,
            /iemobile/i,
            /opera mini/i,
            /mobile/i,
            /phone/i
        ];

        // Detectar tablets específicamente
        const tabletPatterns = [
            /ipad/i,
            /tablet/i,
            /kindle/i,
            /playbook/i,
            /android(?!.*mobile)/i
        ];

        // Verificar si es tablet
        this.isTablet = tabletPatterns.some(pattern => pattern.test(userAgent));

        // Verificar si es móvil (excluyendo tablets)
        if (!this.isTablet) {
            this.isMobile = mobilePatterns.some(pattern => pattern.test(userAgent));
        }

        // Detectar por tamaño de pantalla como respaldo
        this.screenSize = {
            width: window.innerWidth,
            height: window.innerHeight
        };

        // Si la pantalla es muy pequeña, considerarlo móvil
        if (!this.isTablet && this.screenSize.width < 768) {
            this.isMobile = true;
        }

        // Determinar tipo de dispositivo
        if (this.isMobile) {
            this.deviceType = 'mobile';
        } else if (this.isTablet) {
            this.deviceType = 'tablet';
        } else {
            this.deviceType = 'desktop';
        }

        console.log(`📱 Dispositivo detectado: ${this.deviceType}`, {
            isMobile: this.isMobile,
            isTablet: this.isTablet,
            screenSize: this.screenSize,
            userAgent: navigator.userAgent
        });
    }

    setupEventListeners() {
        // Escuchar cambios de orientación
        window.addEventListener('orientationchange', () => {
            setTimeout(() => {
                this.detectDevice();
                this.checkIfShouldRedirect();
            }, 300);
        });

        // Escuchar cambios de tamaño de ventana
        window.addEventListener('resize', () => {
            this.detectDevice();
            this.checkIfShouldRedirect();
        });

        // Escuchar cambios de visibilidad (cuando el usuario vuelve a la página)
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                this.checkIfShouldRedirect();
            }
        });
    }

    checkInitialState() {
        // Verificar si estamos en la página principal y deberíamos estar en la página de error
        const isIndexPage = window.location.pathname === '/' || window.location.pathname === '/index.html';
        
        if (isIndexPage && this.shouldBlockAccess()) {
            console.log('🚫 Dispositivo móvil detectado en página principal, redirigiendo...');
            this.redirectToMobileError();
        }
    }

    shouldBlockAccess() {
        // Bloquear solo móviles, permitir tablets
        return this.isMobile && !this.isTablet;
    }

    checkIfShouldRedirect() {
        const isIndexPage = window.location.pathname === '/' || window.location.pathname === '/index.html';
        const isMobileErrorPage = window.location.pathname === '/mobile-not-supported';
        
        if (isIndexPage && this.shouldBlockAccess()) {
            console.log('🚫 Redirigiendo a página de error móvil...');
            this.redirectToMobileError();
        } else if (isMobileErrorPage && !this.shouldBlockAccess()) {
            console.log('✅ Dispositivo compatible detectado, redirigiendo a página principal...');
            this.redirectToMainApp();
        }
    }

    redirectToMobileError() {
        // Mostrar mensaje antes de redirigir
        this.showMobileWarning();
        
        // Redirigir después de un pequeño delay
        setTimeout(() => {
            window.location.href = '/mobile-not-supported';
        }, 1500);
    }

    redirectToMainApp() {
        window.location.href = '/';
    }

    showMobileWarning() {
        // Crear y mostrar un mensaje de advertencia
        const warning = document.createElement('div');
        warning.id = 'mobile-warning';
        warning.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(102, 126, 234, 0.95);
            color: white;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            z-index: 10000;
            font-family: 'Inter', sans-serif;
            text-align: center;
            padding: 20px;
            box-sizing: border-box;
        `;

        warning.innerHTML = `
            <div style="animation: pulse 1s infinite;">
                <i class="fas fa-mobile-alt" style="font-size: 3rem; margin-bottom: 20px;"></i>
            </div>
            <h2 style="margin: 0 0 10px 0; font-size: 1.5rem;">Dispositivo Móvil Detectado</h2>
            <p style="margin: 0; font-size: 1rem; opacity: 0.9;">Redirigiendo a página de información...</p>
            <div style="margin-top: 20px;">
                <div style="width: 30px; height: 30px; border: 3px solid rgba(255,255,255,0.3); border-top: 3px solid white; border-radius: 50%; animation: spin 1s linear infinite;"></div>
            </div>
            <style>
                @keyframes pulse {
                    0% { transform: scale(1); }
                    50% { transform: scale(1.1); }
                    100% { transform: scale(1); }
                }
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
            </style>
        `;

        document.body.appendChild(warning);
    }

    // Métodos públicos para usar desde otros scripts
    getDeviceType() {
        return this.deviceType;
    }

    getScreenSize() {
        return this.screenSize;
    }

    getDeviceInfo() {
        return {
            isMobile: this.isMobile,
            isTablet: this.isTablet,
            deviceType: this.deviceType,
            screenSize: this.screenSize,
            userAgent: navigator.userAgent,
            shouldBlock: this.shouldBlockAccess()
        };
    }

    // Método para forzar verificación (útil para testing)
    forceCheck() {
        this.detectDevice();
        this.checkIfShouldRedirect();
    }
}

// Inicializar el detector cuando se cargue la página
let mobileDetector = null;

// Función para inicializar el detector
function initMobileDetector() {
    if (!mobileDetector) {
        mobileDetector = new MobileDetector();
    }
    return mobileDetector;
}

// Función para verificar si es móvil (compatible con el código existente)
function isMobileDevice() {
    if (!mobileDetector) {
        initMobileDetector();
    }
    return mobileDetector.isMobile;
}

// Función para obtener el tipo de dispositivo
function getDeviceType() {
    if (!mobileDetector) {
        initMobileDetector();
    }
    return mobileDetector.getDeviceType();
}

// Inicializar automáticamente cuando se cargue el DOM
document.addEventListener('DOMContentLoaded', () => {
    initMobileDetector();
});

// También inicializar si el script se carga después del DOM
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMobileDetector);
} else {
    initMobileDetector();
}

// Exportar para uso en otros módulos
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { MobileDetector, initMobileDetector, isMobileDevice, getDeviceType };
}

// Hacer disponible globalmente para compatibilidad
window.MobileDetector = MobileDetector;
window.initMobileDetector = initMobileDetector;
window.isMobileDevice = isMobileDevice;
window.getDeviceType = getDeviceType; 