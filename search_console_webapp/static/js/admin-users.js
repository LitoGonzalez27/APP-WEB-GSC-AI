// static/js/admin-users.js - Gestión de usuarios administrativos
// ✅ Arquitectura limpia y modular

class AdminUsersManager {
    constructor() {
        this.allUsers = [];
        this.filteredUsers = [];
        this.modalsInitialized = false;
        
        this.init();
    }
    
    // ========================================
    // INICIALIZACIÓN
    // ========================================
    
    init() {
        console.log('🚀 Inicializando AdminUsersManager...');
        
        // Esperar a que el DOM esté listo
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.setupAll());
        } else {
            this.setupAll();
        }
    }
    
    setupAll() {
        this.loadInitialData();
        this.initializeModals();
        this.setupEventListeners();
        this.makeGloballyAvailable();
        
        // Debug después de inicialización
        setTimeout(() => {
            this.debugSetup();
        }, 100);
    }
    
    // ========================================
    // GESTIÓN DE DATOS
    // ========================================
    
    loadInitialData() {
        try {
            const rows = document.querySelectorAll('tbody tr');
            console.log('📊 Cargando datos - Filas encontradas:', rows.length);
            
            this.allUsers = Array.from(rows).map(row => {
                const userNameElement = row.querySelector('.user-name');
                const emailElement = row.querySelector('td:nth-child(2)');
                
                return {
                    id: row.dataset.userId,
                    role: row.dataset.userRole,
                    status: row.dataset.userStatus,
                    name: userNameElement ? userNameElement.textContent : 'Sin nombre',
                    email: emailElement ? emailElement.textContent : 'Sin email',
                    element: row
                };
            });
            
            this.filteredUsers = [...this.allUsers];
            console.log('✅ Usuarios cargados exitosamente:', this.allUsers.length);
            
            // Actualizar estadísticas si es necesario
            this.updateStatsIfNeeded();
            
        } catch (error) {
            console.error('❌ Error en loadInitialData:', error);
            this.allUsers = [];
            this.filteredUsers = [];
        }
    }
    
    updateStatsIfNeeded() {
        const totalUsersElement = document.querySelector('.stat-number');
        if (totalUsersElement && totalUsersElement.textContent.trim() === '0' && this.allUsers.length > 0) {
            console.log('🔧 Las estadísticas del backend están en 0, calculando desde frontend...');
            
            const activeUsers = this.allUsers.filter(user => user.status === 'active').length;
            const inactiveUsers = this.allUsers.length - activeUsers;
            
            const statNumbers = document.querySelectorAll('.stat-number');
            if (statNumbers.length >= 3) {
                statNumbers[0].textContent = this.allUsers.length;
                statNumbers[1].textContent = activeUsers;
                statNumbers[2].textContent = inactiveUsers;
            }
            
            console.log('✅ Estadísticas actualizadas desde frontend:', {
                total: this.allUsers.length,
                active: activeUsers,
                inactive: inactiveUsers
            });
        }
    }
    
    // ========================================
    // GESTIÓN DE MODALES
    // ========================================
    
    initializeModals() {
        console.log('🔧 Inicializando sistema de modales...');
        
        // Verificar que los modales existen
        const userDetailsModal = document.getElementById('userDetailsModal');
        const confirmModal = document.getElementById('confirmModal');
        
        if (!userDetailsModal || !confirmModal) {
            console.error('❌ Modales no encontrados en el DOM');
            return;
        }
        
        // Limpiar cualquier estilo residual
        this.resetModalStyles(userDetailsModal);
        this.resetModalStyles(confirmModal);
        
        // Configurar event listeners de modales
        this.setupModalEventListeners();
        
        this.modalsInitialized = true;
        console.log('✅ Modales inicializados correctamente');
        
        // Debug automático después de inicialización
        setTimeout(() => {
            this.debugSetup();
        }, 500);
    }
    
    resetModalStyles(modal) {
        // Limpiar todos los estilos inline
        modal.style.cssText = '';
        modal.className = 'modal';
        
        // Asegurar que el modal esté oculto inicialmente
        modal.style.display = 'none';
    }
    
    setupModalEventListeners() {
        // Event listeners para cerrar modales
        document.querySelectorAll('.modal-close').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const modal = e.target.closest('.modal');
                if (modal) {
                    this.closeModal(modal.id);
                }
            });
        });
        
        // Clicks fuera del modal
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    this.closeModal(modal.id);
                }
            });
        });
        
        // Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeAllModals();
            }
        });
    }
    
    openModal(modalId) {
        console.log('🔓 Abriendo modal:', modalId);
        
        const modal = document.getElementById(modalId);
        if (!modal) {
            console.error('❌ Modal no encontrado:', modalId);
            return false;
        }
        
        // Limpiar estados previos
        this.closeAllModals();
        
        // Aplicar estilos directamente para máximo control
        modal.style.cssText = `
            display: flex !important;
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            width: 100vw !important;
            height: 100vh !important;
            background-color: rgba(0, 0, 0, 0.6) !important;
            z-index: 10000 !important;
            align-items: center !important;
            justify-content: center !important;
            backdrop-filter: blur(2px) !important;
        `;
        
        // Añadir clase para animaciones
        modal.classList.add('modal-active');
        
        // Prevenir scroll del body
        document.body.style.overflow = 'hidden';
        document.body.classList.add('modal-open');
        
        // Verificar que se abrió correctamente
        setTimeout(() => {
            const isVisible = modal.offsetParent !== null;
            console.log('✅ Modal visible:', isVisible, 'ID:', modalId);
            
            if (!isVisible) {
                console.error('⚠️ Modal no visible después de abrirlo, aplicando fix adicional...');
                // Fix adicional
                modal.style.visibility = 'visible';
                modal.style.opacity = '1';
                modal.style.pointerEvents = 'auto';
            }
        }, 50);
        
        console.log('✅ Modal configurado como abierto:', modalId);
        return true;
    }
    
    closeModal(modalId) {
        console.log('🔒 Cerrando modal:', modalId);
        
        const modal = document.getElementById(modalId);
        if (!modal) {
            console.error('❌ Modal no encontrado:', modalId);
            return;
        }
        
        // Limpiar todos los estilos
        modal.style.cssText = '';
        modal.style.display = 'none';
        modal.classList.remove('modal-active');
        
        // Restaurar body
        document.body.style.overflow = '';
        document.body.classList.remove('modal-open');
        
        console.log('✅ Modal cerrado:', modalId);
    }
    
    closeAllModals() {
        const modals = document.querySelectorAll('.modal');
        modals.forEach(modal => {
            modal.style.cssText = '';
            modal.style.display = 'none';
            modal.classList.remove('modal-active');
        });
        
        document.body.style.overflow = '';
        document.body.classList.remove('modal-open');
    }
    
    // ========================================
    // ACCIONES DE USUARIOS
    // ========================================
    
    async showUserDetails(userId) {
        console.log('🔍 Mostrando detalles para userId:', userId);
        
        const user = this.allUsers.find(u => String(u.id) === String(userId));
        if (!user) {
            console.error('❌ Usuario no encontrado para ID:', userId);
            this.showNotification('Usuario no encontrado', 'error');
            return;
        }
        
        const row = user.element;
        
        try {
            // Llenar información del modal
            this.setElementText('detailId', userId);
            this.setElementText('detailName', user.name || 'Sin nombre');
            this.setElementText('detailEmail', user.email || 'Sin email');
            this.setElementText('detailRole', user.role === 'admin' ? 'Administrador' : 'Usuario');
            this.setElementText('detailStatus', user.status === 'active' ? 'Activo' : 'Inactivo');
            
            // Fecha de creación
            const dateElement = row.querySelector('.date');
            const timeElement = row.querySelector('.time');
            const dateText = dateElement ? dateElement.textContent : 'Sin fecha';
            const timeText = timeElement ? timeElement.textContent : '--:--';
            this.setElementText('detailCreated', `${dateText} ${timeText}`);
            
            // Tipo de autenticación
            const hasPassword = row.querySelector('.reset-password') !== null;
            this.setElementText('detailAuthType', hasPassword ? 'Email y contraseña' : 'Google OAuth');
            
            // Información adicional
            this.setElementText('detailLastLogin', 'No disponible');
            this.setElementText('detailLoginCount', 'No disponible');
            
            // Abrir modal
            this.openModal('userDetailsModal');
            
        } catch (error) {
            console.error('Error mostrando detalles del usuario:', error);
            this.showNotification('Error cargando detalles del usuario', 'error');
        }
    }
    
    deleteUser(userId, userName) {
        console.log('🗑️ Preparando eliminación para:', userId, userName);
        
        this.setElementText('confirmTitle', 'Eliminar Usuario');
        this.setElementText('confirmMessage', `¿Estás seguro de que quieres eliminar al usuario "${userName}"? Esta acción no se puede deshacer.`);
        
        // Configurar acción de confirmación
        const confirmBtn = document.getElementById('confirmAction');
        if (confirmBtn) {
            // Limpiar listeners previos
            confirmBtn.replaceWith(confirmBtn.cloneNode(true));
            const newConfirmBtn = document.getElementById('confirmAction');
            
            newConfirmBtn.addEventListener('click', async () => {
                this.closeModal('confirmModal');
                await this.executeUserDeletion(userId, userName);
            });
        }
        
        // Abrir modal de confirmación
        this.openModal('confirmModal');
    }
    
    async executeUserDeletion(userId, userName) {
        try {
            const response = await fetch(`/admin/users/${userId}/delete`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showNotification(result.message, 'success');
                
                // Remover de la tabla
                const row = document.querySelector(`tr[data-user-id="${userId}"]`);
                if (row) {
                    row.remove();
                }
                
                // Actualizar datos locales
                this.loadInitialData();
                this.filterUsers();
            } else {
                this.showNotification(result.error, 'error');
            }
        } catch (error) {
            console.error('Error:', error);
            this.showNotification('Error de conexión al eliminar usuario', 'error');
        }
    }
    
    async toggleUserStatus(userId, currentStatus) {
        try {
            const response = await fetch(`/admin/users/${userId}/toggle-status`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showNotification(result.message, 'success');
                
                // Actualizar UI
                const row = document.querySelector(`tr[data-user-id="${userId}"]`);
                const statusBadge = row.querySelector('.status-badge');
                const toggleBtn = row.querySelector('.toggle-status');
                
                if (result.is_active) {
                    statusBadge.className = 'status-badge active';
                    statusBadge.innerHTML = '<i class="fas fa-check-circle"></i> Activo';
                    toggleBtn.innerHTML = '<i class="fas fa-user-slash"></i>';
                    toggleBtn.title = 'Desactivar usuario';
                    row.dataset.userStatus = 'active';
                } else {
                    statusBadge.className = 'status-badge inactive';
                    statusBadge.innerHTML = '<i class="fas fa-times-circle"></i> Inactivo';
                    toggleBtn.innerHTML = '<i class="fas fa-user-check"></i>';
                    toggleBtn.title = 'Activar usuario';
                    row.dataset.userStatus = 'inactive';
                }
                
                toggleBtn.dataset.currentStatus = result.is_active;
                
                // Actualizar datos locales
                this.loadInitialData();
            } else {
                this.showNotification(result.error, 'error');
            }
        } catch (error) {
            console.error('Error:', error);
            this.showNotification('Error de conexión', 'error');
        }
    }
    
    // ========================================
    // FILTROS Y BÚSQUEDA
    // ========================================
    
    filterUsers() {
        const searchTerm = this.getElementValue('searchInput').toLowerCase();
        const roleFilter = this.getElementValue('roleFilter');
        const statusFilter = this.getElementValue('statusFilter');
        
        this.filteredUsers = this.allUsers.filter(user => {
            const matchesSearch = user.name.toLowerCase().includes(searchTerm) || 
                                user.email.toLowerCase().includes(searchTerm);
            const matchesRole = !roleFilter || user.role === roleFilter;
            const matchesStatus = !statusFilter || user.status === statusFilter;
            
            return matchesSearch && matchesRole && matchesStatus;
        });
        
        // Mostrar/ocultar filas
        this.allUsers.forEach(user => {
            const shouldShow = this.filteredUsers.includes(user);
            user.element.style.display = shouldShow ? '' : 'none';
        });
        
        this.updateResultsInfo();
    }
    
    updateResultsInfo() {
        const total = this.filteredUsers.length;
        const pageInfo = document.querySelector('.page-info');
        if (pageInfo) {
            pageInfo.textContent = `Mostrando ${total} usuario${total !== 1 ? 's' : ''}`;
        }
    }
    
    clearFilters() {
        this.setElementValue('searchInput', '');
        this.setElementValue('roleFilter', '');
        this.setElementValue('statusFilter', '');
        this.filterUsers();
    }
    
    // ========================================
    // EVENT LISTENERS
    // ========================================
    
    setupEventListeners() {
        console.log('⚡ Configurando event listeners...');
        
        // Filtros
        this.addEventListener('searchInput', 'input', () => this.filterUsers());
        this.addEventListener('roleFilter', 'change', () => this.filterUsers());
        this.addEventListener('statusFilter', 'change', () => this.filterUsers());
        
        // Dropdown de usuario
        this.setupUserDropdown();
        
        // Logout
        this.addEventListener('.logout-btn', 'click', this.logout);
        
        // Acciones de usuarios (delegación de eventos)
        document.addEventListener('click', (e) => {
            const target = e.target.closest('button');
            if (!target) return;
            
            if (target.classList.contains('view-details')) {
                const userId = target.dataset.userId;
                console.log('🔍 Click en view-details, User ID:', userId);
                this.showUserDetails(userId);
            }
            
            if (target.classList.contains('delete-user')) {
                const userId = target.dataset.userId;
                const userName = target.dataset.userName;
                console.log('🗑️ Click en delete-user, User ID:', userId);
                this.deleteUser(userId, userName);
            }
            
            if (target.classList.contains('toggle-status')) {
                const userId = target.dataset.userId;
                const currentStatus = target.dataset.currentStatus === 'true';
                this.toggleUserStatus(userId, currentStatus);
            }
        });
        
        console.log('✅ Event listeners configurados');
    }
    
    setupUserDropdown() {
        const userBtn = document.querySelector('.user-btn');
        const userDropdown = document.querySelector('.user-dropdown-menu');
        
        if (userBtn && userDropdown) {
            userBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                userDropdown.classList.toggle('show');
            });
            
            document.addEventListener('click', () => {
                userDropdown.classList.remove('show');
            });
        }
    }
    
    // ========================================
    // UTILIDADES
    // ========================================
    
    setElementText(id, text) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = text;
        }
    }
    
    setElementValue(id, value) {
        const element = document.getElementById(id);
        if (element) {
            element.value = value;
        }
    }
    
    getElementValue(id) {
        const element = document.getElementById(id);
        return element ? element.value : '';
    }
    
    addEventListener(selector, event, handler) {
        const element = typeof selector === 'string' ? 
            (selector.startsWith('.') || selector.startsWith('#') ? 
                document.querySelector(selector) : 
                document.getElementById(selector)) 
            : selector;
        
        if (element) {
            element.addEventListener(event, handler);
        }
    }
    
    showNotification(message, type = 'info') {
        const notifications = document.getElementById('notifications');
        if (!notifications) return;
        
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        
        const icons = {
            success: 'fas fa-check-circle',
            error: 'fas fa-exclamation-circle',
            warning: 'fas fa-exclamation-triangle',
            info: 'fas fa-info-circle'
        };
        
        notification.innerHTML = `
            <i class="${icons[type]}"></i>
            <span>${message}</span>
            <button class="notification-close" onclick="this.parentElement.remove()">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        notifications.appendChild(notification);
        
        setTimeout(() => {
            notification.remove();
        }, 5000);
    }
    
    async logout() {
        try {
            const response = await fetch('/auth/logout', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.ok) {
                window.location.href = '/login';
            } else {
                console.error('Error en logout');
            }
        } catch (error) {
            console.error('Error en logout:', error);
        }
    }
    
    // ========================================
    // DEBUGGING
    // ========================================
    
    debugSetup() {
        console.log('🔍 === DIAGNÓSTICO COMPLETO DE ADMIN USERS ===');
        
        // 1. Verificar botones
        const viewDetailsButtons = document.querySelectorAll('.view-details');
        const deleteButtons = document.querySelectorAll('.delete-user');
        const toggleButtons = document.querySelectorAll('.toggle-status');
        
        console.log('📊 Botones encontrados:');
        console.log('  - view-details:', viewDetailsButtons.length);
        console.log('  - delete-user:', deleteButtons.length);
        console.log('  - toggle-status:', toggleButtons.length);
        
        // 2. Verificar modales
        const userDetailsModal = document.getElementById('userDetailsModal');
        const confirmModal = document.getElementById('confirmModal');
        
        console.log('🎭 Modales:');
        console.log('  - userDetailsModal:', !!userDetailsModal);
        console.log('  - confirmModal:', !!confirmModal);
        
        // 3. Verificar filas de usuarios
        const userRows = document.querySelectorAll('tbody tr[data-user-id]');
        console.log('👥 Filas de usuarios:', userRows.length);
        
        if (userRows.length > 0) {
            const firstRow = userRows[0];
            console.log('🔍 Primera fila de ejemplo:');
            console.log('  - data-user-id:', firstRow.dataset.userId);
            console.log('  - data-user-role:', firstRow.dataset.userRole);
            console.log('  - data-user-status:', firstRow.dataset.userStatus);
            
            const detailsBtn = firstRow.querySelector('.view-details');
            const deleteBtn = firstRow.querySelector('.delete-user');
            console.log('  - Botón view-details:', !!detailsBtn);
            console.log('  - Botón delete-user:', !!deleteBtn);
        }
        
        // 4. Verificar datos cargados
        console.log('📦 Datos internos:');
        console.log('  - allUsers.length:', this.allUsers.length);
        console.log('  - filteredUsers.length:', this.filteredUsers.length);
        console.log('  - modalsInitialized:', this.modalsInitialized);
        
        // 5. Test manual de apertura de modal
        this.debugModalTest();
    }
    
    debugModalTest() {
        console.log('🧪 === TEST MANUAL DE MODALES ===');
        
        const userDetailsModal = document.getElementById('userDetailsModal');
        const confirmModal = document.getElementById('confirmModal');
        
        if (userDetailsModal) {
            console.log('🔍 Probando userDetailsModal...');
            console.log('  - display actual:', window.getComputedStyle(userDetailsModal).display);
            console.log('  - visibility:', window.getComputedStyle(userDetailsModal).visibility);
            console.log('  - z-index:', window.getComputedStyle(userDetailsModal).zIndex);
            console.log('  - offsetParent:', userDetailsModal.offsetParent);
            
            // Test directo
            this.openModal('userDetailsModal');
            
            setTimeout(() => {
                console.log('  - Después de openModal:');
                console.log('    - display:', userDetailsModal.style.display);
                console.log('    - classes:', userDetailsModal.className);
                console.log('    - offsetParent:', userDetailsModal.offsetParent);
                
                this.closeModal('userDetailsModal');
            }, 100);
        }
        
        if (confirmModal) {
            setTimeout(() => {
                console.log('🔍 Probando confirmModal...');
                console.log('  - display actual:', window.getComputedStyle(confirmModal).display);
                
                this.openModal('confirmModal');
                
                setTimeout(() => {
                    console.log('  - Después de openModal:');
                    console.log('    - display:', confirmModal.style.display);
                    console.log('    - offsetParent:', confirmModal.offsetParent);
                    
                    this.closeModal('confirmModal');
                }, 100);
            }, 500);
        }
    }
    
    // Función global para testing desde consola
    testModalDirect(modalId) {
        console.log(`🧪 Test directo de modal: ${modalId}`);
        
        const modal = document.getElementById(modalId);
        if (!modal) {
            console.error('❌ Modal no encontrado:', modalId);
            return;
        }
        
        console.log('Modal antes:', {
            display: modal.style.display,
            classes: modal.className,
            offsetParent: modal.offsetParent
        });
        
        // Abrir con estilos forzados
        modal.style.cssText = `
            display: flex !important;
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            width: 100vw !important;
            height: 100vh !important;
            background-color: rgba(0, 0, 0, 0.8) !important;
            z-index: 99999 !important;
            align-items: center !important;
            justify-content: center !important;
        `;
        
        modal.classList.add('modal-active');
        
        setTimeout(() => {
            console.log('Modal después:', {
                display: modal.style.display,
                classes: modal.className,
                offsetParent: modal.offsetParent,
                visible: modal.offsetParent !== null
            });
        }, 50);
        
        // Auto cerrar después de 3 segundos
        setTimeout(() => {
            modal.style.cssText = '';
            modal.style.display = 'none';
            modal.classList.remove('modal-active');
            console.log('✅ Modal cerrado automáticamente');
        }, 3000);
    }
    
    // ========================================
    // FUNCIONES GLOBALES PARA DEBUGGING
    // ========================================
    
    makeGloballyAvailable() {
        window.adminManager = this;
        
        // Funciones de debug globales
        window.debugAdminUsers = () => this.debugSetup();
        window.testModal = (modalId) => this.testModalDirect(modalId);
        window.forceOpenModal = (modalId) => {
            console.log(`🔧 Forzando apertura de ${modalId}...`);
            this.openModal(modalId);
        };
        window.showTestUserDetails = () => {
            console.log('🧪 Test de showUserDetails...');
            if (this.allUsers.length > 0) {
                this.showUserDetails(this.allUsers[0].id);
            } else {
                console.log('❌ No hay usuarios para probar');
            }
        };
        
        console.log('🌍 Funciones globales disponibles:');
        console.log('  - debugAdminUsers()');
        console.log('  - testModal(modalId)');
        console.log('  - forceOpenModal(modalId)');
        console.log('  - showTestUserDetails()');
    }
}

// ========================================
// INICIALIZACIÓN AUTOMÁTICA
// ========================================

// Inicializar cuando se carga el script
const adminUsersManager = new AdminUsersManager(); 