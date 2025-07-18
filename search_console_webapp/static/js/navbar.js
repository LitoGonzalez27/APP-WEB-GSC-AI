// static/js/navbar.js - NAVBAR MODERNO REDISEÑADO

class Navbar {
    constructor() {
        // Elementos principales
        this.navbar = document.getElementById('navbar');
        this.navbarToggle = document.getElementById('navbarToggle');
        this.navbarMenu = document.getElementById('navbarMenu');
        this.navbarOverlay = document.getElementById('navbarOverlay');
        this.mobileMenuClose = document.getElementById('mobileMenuClose');
        
        // Botones de autenticación desktop
        this.loginBtn = document.getElementById('loginBtn');
        this.logoutBtn = document.getElementById('logoutBtn');
        
        // Botones de autenticación móvil
        this.mobileLoginBtn = document.getElementById('mobileLoginBtn');
        this.mobileLogoutBtn = document.getElementById('mobileLogoutBtn');
        
        // Botones de tema
        this.toggleModeBtn = document.getElementById('toggleModeBtn');
        this.mobileToggleModeBtn = document.getElementById('mobileToggleModeBtn');
        this.themeIcon = document.getElementById('themeIcon');
        this.mobileThemeIcon = document.getElementById('mobileThemeIcon');
        this.mobileThemeText = document.getElementById('mobileThemeText');
        
        // Elementos de usuario
        this.userInfo = document.getElementById('userInfo');
        this.userName = document.getElementById('userName');
        this.loggedInNav = document.getElementById('loggedInNav');
        this.mobileUserInfo = document.getElementById('mobileUserInfo');
        this.mobileUserName = document.getElementById('mobileUserName');
        this.mobileUserEmail = document.getElementById('mobileUserEmail');
        
        // Estado de la aplicación
        this.isLoggedIn = false;
        this.currentUser = null;
        this.isScrolled = false;
        this.isMobileMenuOpen = false;
        
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.handleResponsive();
        this.checkAuthStatus();
        this.handleAuthRedirect();
        this.listenToThemeChanges();
        
        // Sincronizar estado inicial del tema
        this.syncThemeState();
        
        // Integrar con el sistema de tema existente
        this.integrateWithThemeSystem();
    }

    setupEventListeners() {
        // Toggle del menú móvil
        if (this.navbarToggle) {
            this.navbarToggle.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleMobileMenu();
            });
        }

        // Cerrar menú móvil
        if (this.mobileMenuClose) {
            this.mobileMenuClose.addEventListener('click', () => {
                this.closeMobileMenu();
            });
        }

        // Overlay para cerrar menú
        if (this.navbarOverlay) {
            this.navbarOverlay.addEventListener('click', () => {
                this.closeMobileMenu();
            });
        }

        // Botones de login desktop y móvil
        if (this.loginBtn) {
            this.loginBtn.addEventListener('click', () => this.handleLogin());
        }
        if (this.mobileLoginBtn) {
            this.mobileLoginBtn.addEventListener('click', () => this.handleLogin());
        }

        // Botones de logout desktop y móvil
        if (this.logoutBtn) {
            this.logoutBtn.addEventListener('click', () => this.handleLogout());
        }
        if (this.mobileLogoutBtn) {
            this.mobileLogoutBtn.addEventListener('click', () => this.handleLogout());
        }

        // Botones de tema desktop y móvil
        if (this.toggleModeBtn) {
            this.toggleModeBtn.addEventListener('click', () => this.handleThemeToggle());
        }
        if (this.mobileToggleModeBtn) {
            this.mobileToggleModeBtn.addEventListener('click', () => this.handleThemeToggle());
        }

        // Cerrar menú móvil al hacer click en enlaces internos
        document.addEventListener('click', (e) => {
            if (this.isMobileMenuOpen && !this.navbarMenu.contains(e.target) && !this.navbarToggle.contains(e.target)) {
                this.closeMobileMenu();
            }
        });

        // Efecto scroll
        window.addEventListener('scroll', () => this.handleScroll(), { passive: true });

        // Cerrar menú al redimensionar ventana
        window.addEventListener('resize', () => {
            if (window.innerWidth > 968 && this.isMobileMenuOpen) {
                this.closeMobileMenu();
            }
        });

        // Manejo de teclas
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isMobileMenuOpen) {
                this.closeMobileMenu();
            }
        });
    }

    // Escuchar cambios de tema desde el sistema centralizado
    listenToThemeChanges() {
        window.addEventListener('themeChanged', (event) => {
            const { isDark } = event.detail;
            this.updateThemeIcons(isDark);
        });
    }

    // Sincronizar estado inicial del tema
    syncThemeState() {
        const isDark = document.body.classList.contains('dark-mode');
        this.updateThemeIcons(isDark);
    }

    // Actualizar iconos y texto del tema
    updateThemeIcons(isDark) {
        const iconClass = isDark ? 'fa-sun' : 'fa-moon';
        const themeText = isDark ? 'Modo Claro' : 'Modo Oscuro';

        // Actualizar iconos
        if (this.themeIcon) {
            this.themeIcon.className = `fas ${iconClass}`;
        }
        if (this.mobileThemeIcon) {
            this.mobileThemeIcon.className = `fas ${iconClass}`;
        }

        // Actualizar texto móvil
        if (this.mobileThemeText) {
            this.mobileThemeText.textContent = themeText;
        }

        // Actualizar aria-label
        if (this.toggleModeBtn) {
            this.toggleModeBtn.setAttribute('aria-label', `Cambiar a ${themeText.toLowerCase()}`);
            this.toggleModeBtn.setAttribute('aria-pressed', isDark.toString());
        }
    }

    // Integrar con el sistema de tema existente
    integrateWithThemeSystem() {
        // Hacer disponible la función de toggle para utils.js
        window.navbarToggleTheme = () => {
            this.handleThemeToggle();
        };
        
        // ✅ CORREGIDO: Usar la lógica unificada de storage
        const savedTheme = localStorage.getItem('darkMode') === 'true';
        if (savedTheme) {
            document.body.classList.add('dark-mode');
            this.updateThemeIcons(true);
        }
        
        console.log('🔗 Navbar integrado con sistema de tema, tema guardado:', savedTheme);
    }

    // Manejar toggle de tema
    handleThemeToggle() {
        console.log('🎨 handleThemeToggle llamado desde navbar');
        
        // Usar lógica directa sin imports dinámicos para mejor compatibilidad
        const isDark = document.body.classList.toggle('dark-mode');
        
        // Actualizar iconos en ambos botones
        this.updateThemeIcons(isDark);
        
        // Guardar preferencia
        localStorage.setItem('darkMode', isDark.toString());
        
        // ✅ NUEVO: También actualizar la función de utils.js si está disponible
        if (window.themeUtils && window.themeUtils.storage) {
            window.themeUtils.storage.darkMode = isDark;
        }
        
        // Disparar evento personalizado para que otros componentes escuchen
        window.dispatchEvent(new CustomEvent('themeChanged', { 
            detail: { isDark } 
        }));
        
        console.log('🎨 Tema cambiado a:', isDark ? 'oscuro' : 'claro', 'localStorage:', localStorage.getItem('darkMode'));
    }



    // Efecto scroll para el navbar
    handleScroll() {
        const scrolled = window.scrollY > 20;
        
        if (scrolled !== this.isScrolled) {
            this.isScrolled = scrolled;
            
            if (scrolled) {
                this.navbar.classList.add('scrolled');
            } else {
                this.navbar.classList.remove('scrolled');
            }
        }
    }

    // Toggle del menú móvil
    toggleMobileMenu() {
        this.isMobileMenuOpen = !this.isMobileMenuOpen;
        
        if (this.isMobileMenuOpen) {
            this.openMobileMenu();
        } else {
            this.closeMobileMenu();
        }
    }

    // Abrir menú móvil
    openMobileMenu() {
        this.isMobileMenuOpen = true;
        this.navbarMenu.classList.add('active');
        this.navbarToggle.classList.add('active');
        this.navbarOverlay.classList.add('active');
        
        // Prevenir scroll del body
        document.body.style.overflow = 'hidden';
        
        // Actualizar aria-expanded
        this.navbarToggle.setAttribute('aria-expanded', 'true');
        
        // Focus en el primer elemento del menú
        setTimeout(() => {
            const firstFocusable = this.navbarMenu.querySelector('button, a');
            if (firstFocusable) {
                firstFocusable.focus();
            }
        }, 100);
    }

    // Cerrar menú móvil
    closeMobileMenu() {
        this.isMobileMenuOpen = false;
        this.navbarMenu.classList.remove('active');
        this.navbarToggle.classList.remove('active');
        this.navbarOverlay.classList.remove('active');
        
        // Restaurar scroll del body
        document.body.style.overflow = '';
        
        // Actualizar aria-expanded
        this.navbarToggle.setAttribute('aria-expanded', 'false');
    }

    // Verificar estado de autenticación
    async checkAuthStatus() {
        try {
            const response = await fetch('/auth/status');
            const data = await response.json();
            
            if (data.authenticated) {
                this.setLoginStatus(true, data.user);
            } else {
                this.setLoginStatus(false, null);
            }
        } catch (error) {
            console.error('Error checking auth status:', error);
            this.setLoginStatus(false, null);
        }
    }

    // Manejar redirecciones de autenticación
    handleAuthRedirect() {
        const urlParams = new URLSearchParams(window.location.search);
        
        if (urlParams.get('auth_success') === 'true') {
            this.showToast('¡Inicio de sesión exitoso!', 'success');
            this.checkAuthStatus();
            
            // Limpiar URL
            const newUrl = window.location.pathname;
            window.history.replaceState({}, '', newUrl);
        }
        
        const authError = urlParams.get('auth_error');
        if (authError) {
            let errorMessage = 'Error de autenticación';
            
            switch (authError) {
                case 'invalid_state':
                    errorMessage = 'Error de seguridad. Intenta de nuevo.';
                    break;
                case 'oauth_config':
                    errorMessage = 'Error de configuración OAuth.';
                    break;
                case 'callback_failed':
                    errorMessage = 'Error en callback. Intenta de nuevo.';
                    break;
            }
            
            this.showToast(errorMessage, 'error');
            
            // Limpiar URL
            const newUrl = window.location.pathname;
            window.history.replaceState({}, '', newUrl);
        }
    }

    // Manejar login
    handleLogin() {
        // Mostrar loading en ambos botones
        this.setLoadingState(true);
        
        // Mostrar toast informativo
        this.showToast('Redirigiendo a Google...', 'info');
        
        // Redirigir al endpoint de auth
        setTimeout(() => {
            window.location.href = '/auth/login';
        }, 500);
    }

    // Manejar logout
    async handleLogout() {
        try {
            // Mostrar loading
            this.setLoadingState(true);
            
            // Mostrar toast informativo
            this.showToast('Cerrando sesión...', 'info');
            
            const response = await fetch('/auth/logout', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                this.setLoginStatus(false, null);
                this.showToast('Sesión cerrada correctamente', 'success');
                
                // Cerrar menú móvil si está abierto
                if (this.isMobileMenuOpen) {
                    this.closeMobileMenu();
                }
                
                // Redirigir a la página de login después de un breve delay
                setTimeout(() => {
                    window.location.href = '/login?session_expired=true';
                }, 1500);
            } else {
                const errorData = await response.json().catch(() => ({ error: 'Error desconocido' }));
                throw new Error(errorData.error || 'Error en logout');
            }
        } catch (error) {
            console.error('Error durante logout:', error);
            this.showToast('Error al cerrar sesión. Redirigiendo...', 'error');
            
            // En caso de error, redirigir de todos modos
            setTimeout(() => {
                window.location.href = '/login?auth_error=logout_failed';
            }, 2000);
        } finally {
            this.setLoadingState(false);
        }
    }

    // Establecer estado de login
    setLoginStatus(isLoggedIn, user = null) {
        this.isLoggedIn = isLoggedIn;
        this.currentUser = user;
        this.updateAuthButtons();
        this.updateUserInfo();
    }

    // Actualizar botones de autenticación
    updateAuthButtons() {
        // Botones desktop
        if (this.loginBtn && this.logoutBtn) {
            if (this.isLoggedIn) {
                this.loginBtn.style.display = 'none';
                this.logoutBtn.style.display = 'flex';
            } else {
                this.loginBtn.style.display = 'flex';
                this.logoutBtn.style.display = 'none';
            }
        }

        // Botones móvil
        if (this.mobileLoginBtn && this.mobileLogoutBtn) {
            if (this.isLoggedIn) {
                this.mobileLoginBtn.style.display = 'none';
                this.mobileLogoutBtn.style.display = 'flex';
            } else {
                this.mobileLoginBtn.style.display = 'flex';
                this.mobileLogoutBtn.style.display = 'none';
            }
        }
    }

    // Actualizar información del usuario
    updateUserInfo() {
        if (this.isLoggedIn && this.currentUser) {
            // Desktop user info
            if (this.userInfo && this.userName) {
                this.userInfo.style.display = 'flex';
                this.userName.textContent = this.currentUser.name || 'Usuario';
            }
            
            // Navigation buttons for logged in users
            if (this.loggedInNav) {
                this.loggedInNav.style.display = 'flex';
            }

            // Mobile user info
            if (this.mobileUserInfo && this.mobileUserName && this.mobileUserEmail) {
                this.mobileUserInfo.style.display = 'flex';
                this.mobileUserName.textContent = this.currentUser.name || 'Usuario';
                this.mobileUserEmail.textContent = this.currentUser.email || 'usuario@email.com';
            }
        } else {
            // Ocultar info de usuario
            if (this.userInfo) {
                this.userInfo.style.display = 'none';
            }
            if (this.loggedInNav) {
                this.loggedInNav.style.display = 'none';
            }
            if (this.mobileUserInfo) {
                this.mobileUserInfo.style.display = 'none';
            }
        }
    }

    // Establecer estado de carga
    setLoadingState(loading) {
        const buttons = [this.loginBtn, this.logoutBtn, this.mobileLoginBtn, this.mobileLogoutBtn];
        
        buttons.forEach(btn => {
            if (btn) {
                if (loading) {
                    btn.classList.add('loading');
                    btn.disabled = true;
                } else {
                    btn.classList.remove('loading');
                    btn.disabled = false;
                }
            }
        });
    }

    // Mostrar toast/notificación
    showToast(message, type = 'info') {
        // Remover toast existente
        const existingToast = document.querySelector('.navbar-toast');
        if (existingToast) {
            existingToast.remove();
        }

        // Crear nuevo toast
        const toast = document.createElement('div');
        toast.className = `navbar-toast navbar-toast-${type}`;
        toast.innerHTML = `
            <div class="toast-content">
                <i class="fas ${this.getToastIcon(type)}"></i>
                <span>${message}</span>
            </div>
        `;

        // Estilos del toast
        Object.assign(toast.style, {
            position: 'fixed',
            top: '80px',
            right: '20px',
            background: type === 'error' ? '#dc2626' : type === 'success' ? '#059669' : '#3b82f6',
            color: 'white',
            padding: '1rem 1.5rem',
            borderRadius: '12px',
            boxShadow: '0 10px 40px rgba(0, 0, 0, 0.2)',
            zIndex: '9999',
            transform: 'translateX(400px)',
            transition: 'all 0.3s ease',
            backdropFilter: 'blur(10px)',
            maxWidth: '300px'
        });

        document.body.appendChild(toast);

        // Animar entrada
        setTimeout(() => {
            toast.style.transform = 'translateX(0)';
        }, 100);

        // Auto-remover después de 4 segundos
        setTimeout(() => {
            toast.style.transform = 'translateX(400px)';
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.remove();
                }
            }, 300);
        }, 4000);
    }

    // Obtener icono para toast
    getToastIcon(type) {
        switch (type) {
            case 'success': return 'fa-check-circle';
            case 'error': return 'fa-exclamation-circle';
            case 'warning': return 'fa-exclamation-triangle';
            default: return 'fa-info-circle';
        }
    }

    // Manejar responsive
    handleResponsive() {
        const handleResize = () => {
            if (window.innerWidth > 968 && this.isMobileMenuOpen) {
                this.closeMobileMenu();
            }
        };

        window.addEventListener('resize', handleResize);
    }

    // Métodos públicos para usar desde otros scripts
    getAuthStatus() {
        return {
            isLoggedIn: this.isLoggedIn,
            user: this.currentUser
        };
    }

    refreshAuth() {
        this.checkAuthStatus();
    }

    closeMenu() {
        if (this.isMobileMenuOpen) {
            this.closeMobileMenu();
        }
    }
}

// Inicializar navbar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    window.navbar = new Navbar();
});

// Exportar para uso en otros módulos
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Navbar;
}