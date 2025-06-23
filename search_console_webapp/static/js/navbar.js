// static/js/navbar.js - SIMPLIFICADO (sin control de tema)

class Navbar {
    constructor() {
        this.navbar = document.getElementById('navbar');
        this.navbarToggle = document.getElementById('navbarToggle');
        this.navbarMenu = document.getElementById('navbarMenu');
        this.loginBtn = document.getElementById('loginBtn');
        this.logoutBtn = document.getElementById('logoutBtn');
        this.toggleModeBtn = document.getElementById('toggleModeBtn');
        this.themeIcon = document.getElementById('themeIcon');
        
        // ✅ Estado real de autenticación
        this.isLoggedIn = false;
        this.currentUser = null;
        
        // ✅ Estado de scroll y overlay
        this.isScrolled = false;
        this.overlay = null;
        
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.handleResponsive();
        this.createOverlay();
        
        // ✅ Verificar estado de autenticación al cargar
        this.checkAuthStatus();
        this.handleAuthRedirect();
        
        // ✅ NUEVO: Escuchar cambios de tema desde utils.js
        this.listenToThemeChanges();
    }

    setupEventListeners() {
        // Toggle del menú hamburguesa
        if (this.navbarToggle) {
            this.navbarToggle.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleMobileMenu();
            });
        }

        // ✅ Botones de login/logout reales
        if (this.loginBtn) {
            this.loginBtn.addEventListener('click', () => this.handleLogin());
        }

        if (this.logoutBtn) {
            this.logoutBtn.addEventListener('click', () => this.handleLogout());
        }

        // ✅ ELIMINADO: Ya no manejamos el tema aquí
        // El botón de tema se maneja desde utils.js

        // ✅ Cerrar menú al hacer click fuera
        document.addEventListener('click', (e) => {
            if (!this.navbar.contains(e.target) && this.navbarMenu.classList.contains('active')) {
                this.closeMobileMenu();
            }
        });

        // ✅ Efecto scroll
        window.addEventListener('scroll', () => this.handleScroll(), { passive: true });

        // Cerrar menú al redimensionar ventana
        window.addEventListener('resize', () => {
            if (window.innerWidth > 768) {
                this.closeMobileMenu();
            }
        });

        // ✅ Manejo de teclas (Escape para cerrar menú)
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.navbarMenu.classList.contains('active')) {
                this.closeMobileMenu();
            }
        });
    }

    // ✅ NUEVO: Escuchar cambios de tema desde el sistema centralizado
    listenToThemeChanges() {
        window.addEventListener('themeChanged', (event) => {
            const { isDark } = event.detail;
            console.log('Navbar detectó cambio de tema:', isDark ? 'oscuro' : 'claro');
            
            // Aquí podríamos añadir lógica específica del navbar si fuera necesaria
            // Por ejemplo, cambiar animaciones o comportamientos específicos
        });
    }

    // ✅ Crear overlay para móvil
    createOverlay() {
        this.overlay = document.createElement('div');
        this.overlay.className = 'navbar-overlay';
        this.overlay.addEventListener('click', () => this.closeMobileMenu());
        document.body.appendChild(this.overlay);
    }

    // ✅ Efecto scroll para el navbar
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

    // ✅ Verificar estado de autenticación real
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

    // ✅ Manejar redirecciones de autenticación
    handleAuthRedirect() {
        const urlParams = new URLSearchParams(window.location.search);
        
        if (urlParams.get('auth_success') === 'true') {
            this.showToast('¡Login exitoso!', 'success');
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

    // ✅ Toggle móvil con animaciones
    toggleMobileMenu() {
        const isActive = this.navbarMenu.classList.toggle('active');
        this.navbarToggle.classList.toggle('active');
        this.overlay.classList.toggle('active');
        
        // Prevenir scroll del body cuando el menú está abierto
        if (isActive) {
            document.body.style.overflow = 'hidden';
            this.animateMenuItems();
        } else {
            document.body.style.overflow = '';
        }
        
        // Actualizar aria-expanded para accesibilidad
        this.navbarToggle.setAttribute('aria-expanded', isActive);
    }

    // ✅ Animación escalonada para items del menú
    animateMenuItems() {
        const menuItems = this.navbarMenu.querySelectorAll('.navbar-btn');
        menuItems.forEach((item, index) => {
            item.style.animationDelay = `${(index + 1) * 0.1}s`;
        });
    }

    closeMobileMenu() {
        this.navbarMenu.classList.remove('active');
        this.navbarToggle.classList.remove('active');
        this.overlay.classList.remove('active');
        document.body.style.overflow = '';
        this.navbarToggle.setAttribute('aria-expanded', 'false');
    }

    // ✅ Login con mejor UX
    handleLogin() {
        console.log('Redirecting to Google OAuth...');
        
        // Añadir estado de loading
        this.loginBtn.classList.add('loading');
        
        this.showToast('Redirigiendo a Google...', 'info');
        
        // Delay para mostrar el loading
        setTimeout(() => {
            window.location.href = '/auth/login';
        }, 500);
        
        this.closeMobileMenu();
    }

    // ✅ Logout mejorado
    async handleLogout() {
        try {
            // Añadir estado de loading
            this.logoutBtn.classList.add('loading');
            
            const response = await fetch('/auth/logout', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                this.setLoginStatus(false, null);
                this.showToast('Logout exitoso', 'success');
                
                // Recargar página para limpiar datos
                setTimeout(() => {
                    window.location.reload();
                }, 1000);
            } else {
                throw new Error('Logout failed');
            }
        } catch (error) {
            console.error('Error during logout:', error);
            this.showToast('Error en logout', 'error');
        } finally {
            this.logoutBtn.classList.remove('loading');
        }
        
        this.closeMobileMenu();
    }

    // ✅ Manejar estado real de autenticación
    setLoginStatus(isLoggedIn, user = null) {
        this.isLoggedIn = isLoggedIn;
        this.currentUser = user;
        this.updateAuthButtons();
    }

    updateAuthButtons() {
        if (this.isLoggedIn && this.currentUser) {
            // Mostrar botón logout con info del usuario
            this.loginBtn.style.display = 'none';
            this.logoutBtn.style.display = 'flex';
            
            // ✅ Mostrar email del usuario en el botón
            const btnText = this.logoutBtn.querySelector('.btn-text');
            if (btnText && this.currentUser.email) {
                const username = this.currentUser.email.split('@')[0];
                btnText.textContent = `${username}`;
                this.logoutBtn.title = `Conectado como ${this.currentUser.email}`;
                
                // ✅ Añadir primera letra como avatar
                const existingAvatar = this.logoutBtn.querySelector('.user-avatar');
                if (!existingAvatar) {
                    const avatar = document.createElement('span');
                    avatar.className = 'user-avatar';
                    avatar.textContent = username.charAt(0).toUpperCase();
                    this.logoutBtn.insertBefore(avatar, btnText);
                }
            }
        } else {
            // Mostrar botón login
            this.loginBtn.style.display = 'flex';
            this.logoutBtn.style.display = 'none';
            
            // Remover avatar si existe
            const avatar = this.logoutBtn.querySelector('.user-avatar');
            if (avatar) {
                avatar.remove();
            }
        }
    }

    handleResponsive() {
        // Manejo responsivo mejorado se hace principalmente con CSS
        // Aquí solo manejamos eventos específicos de JavaScript
        
        const handleResize = () => {
            if (window.innerWidth > 768 && this.navbarMenu.classList.contains('active')) {
                this.closeMobileMenu();
            }
        };

        window.addEventListener('resize', handleResize);
    }

    // ✅ Toast con mejor diseño y animaciones
    showToast(message, type = 'info') {
        // Remover toasts anteriores
        const existingToasts = document.querySelectorAll('.toast');
        existingToasts.forEach(toast => {
            toast.style.animation = 'slideOutRight 0.3s ease forwards';
            setTimeout(() => toast.remove(), 300);
        });

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        // ✅ Iconos y colores
        const icons = {
            success: { icon: 'fa-check-circle', color: '#10b981' },
            error: { icon: 'fa-exclamation-circle', color: '#ef4444' },
            warning: { icon: 'fa-exclamation-triangle', color: '#f59e0b' },
            info: { icon: 'fa-info-circle', color: '#3b82f6' }
        };
        
        const { icon, color } = icons[type] || icons.info;
        
        toast.innerHTML = `
            <div class="toast-content">
                <div class="toast-icon">
                    <i class="fas ${icon}"></i>
                </div>
                <div class="toast-text">
                    <span class="toast-message">${message}</span>
                </div>
                <button class="toast-close" onclick="this.parentElement.remove()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;

        // ✅ Estilos
        toast.style.cssText = `
            position: fixed;
            top: 90px;
            right: 20px;
            background: white;
            color: #374151;
            padding: 0;
            border-radius: 12px;
            border-left: 4px solid ${color};
            box-shadow: 0 10px 40px rgba(0,0,0,0.15);
            z-index: 10001;
            animation: slideInRight 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            min-width: 320px;
            max-width: 500px;
            overflow: hidden;
            backdrop-filter: blur(10px);
        `;

        document.body.appendChild(toast);

        // Auto-remover después de 5 segundos
        setTimeout(() => {
            if (document.body.contains(toast)) {
                toast.style.animation = 'slideOutRight 0.4s cubic-bezier(0.4, 0, 0.2, 1)';
                setTimeout(() => {
                    if (document.body.contains(toast)) {
                        toast.remove();
                    }
                }, 400);
            }
        }, 5000);
    }

    // ✅ Métodos públicos para integración externa
    getAuthStatus() {
        return {
            isAuthenticated: this.isLoggedIn,
            user: this.currentUser
        };
    }

    refreshAuth() {
        this.checkAuthStatus();
    }

    // Métodos legacy para compatibilidad
    getLoginStatus() {
        return this.isLoggedIn;
    }

    // ✅ Método para mostrar/ocultar navbar
    toggleNavbar(show = true) {
        if (show) {
            this.navbar.style.transform = 'translateY(0)';
        } else {
            this.navbar.style.transform = 'translateY(-100%)';
        }
    }
}

// Inicializar el navbar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    window.navbar = new Navbar();
});

// ✅ CSS para toasts y avatares (simplificado)
const navbarStyles = document.createElement('style');
navbarStyles.textContent = `
    /* Animaciones para toasts */
    @keyframes slideInRight {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    
    @keyframes slideOutRight {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
    
    /* Toast content */
    .toast-content {
        display: flex;
        align-items: center;
        padding: 16px 20px;
        gap: 12px;
    }
    
    .toast-icon {
        flex-shrink: 0;
        width: 24px;
        height: 24px;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    
    .toast-icon i {
        font-size: 16px;
    }
    
    .toast-text {
        flex: 1;
        min-width: 0;
    }
    
    .toast-message {
        font-size: 14px;
        font-weight: 500;
        line-height: 1.4;
    }
    
    .toast-close {
        background: none;
        border: none;
        cursor: pointer;
        padding: 4px;
        border-radius: 4px;
        color: #6b7280;
        flex-shrink: 0;
        width: 24px;
        height: 24px;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s ease;
    }
    
    .toast-close:hover {
        background-color: #f3f4f6;
        color: #374151;
    }
    
    .toast-close i {
        font-size: 12px;
    }
    
    /* Colores de iconos para toasts */
    .toast-success .toast-icon i { color: #10b981; }
    .toast-error .toast-icon i { color: #ef4444; }
    .toast-warning .toast-icon i { color: #f59e0b; }
    .toast-info .toast-icon i { color: #3b82f6; }
    
    /* Avatar de usuario */
    .user-avatar {
        width: 24px;
        height: 24px;
        border-radius: 50%;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        margin-right: 4px;
    }
    
    /* Loading state */
    .navbar-btn.loading i {
        animation: spin 1s linear infinite;
    }
    
    @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
    
    /* Transiciones para iconos de tema */
    .toggle-mode i {
        transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    /* Overlay para menú móvil */
    .navbar-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.3);
        opacity: 0;
        visibility: hidden;
        transition: all 0.3s ease;
        z-index: 999;
    }
    
    .navbar-overlay.active {
        opacity: 1;
        visibility: visible;
    }
    
    body.dark-mode .navbar-overlay {
        background: rgba(0, 0, 0, 0.6);
    }
    
    /* Dark mode para toasts */
    body.dark-mode .toast-content {
        background: #1f2937;
        color: #f9fafb;
    }
    
    body.dark-mode .toast-close {
        color: #9ca3af;
    }
    
    body.dark-mode .toast-close:hover {
        background-color: #374151;
        color: #f9fafb;
    }
    
    /* Responsive para toasts */
    @media (max-width: 768px) {
        .toast {
            left: 20px;
            right: 20px;
            min-width: auto;
            max-width: none;
        }
        
        .toast-content {
            padding: 14px 16px;
        }
        
        .toast-message {
            font-size: 13px;
        }
    }
`;
document.head.appendChild(navbarStyles);