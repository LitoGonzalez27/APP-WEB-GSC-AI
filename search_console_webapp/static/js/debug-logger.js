// static/js/debug-logger.js
// Sistema de logging que funciona incluso con console silencer activo

/**
 * Logger personalizado que usa console.error (no silenciado) para mensajes de debug
 * Solo activo cuando se habilita explícitamente
 */
class DebugLogger {
  constructor() {
    // Guardar referencias originales antes del silencer
    this.originalLog = console.log;
    this.originalInfo = console.info;
    this.originalWarn = console.warn;
    this.originalError = console.error;
    
    // Estado de debug (se puede activar con window.enableDebugLogs())
    this.enabled = this.checkDebugMode();
    
    if (this.enabled) {
      this.log('🔧 Debug Logger habilitado');
    }
  }

  checkDebugMode() {
    // Verificar si debug está habilitado via URL o localStorage
    const urlParams = new URLSearchParams(window.location.search);
    const urlDebug = urlParams.get('debugLogs') === '1' || urlParams.get('debug') === '1';
    const storageDebug = localStorage.getItem('debugLogs') === 'true';
    
    return urlDebug || storageDebug || this.isLocalhost();
  }

  isLocalhost() {
    const host = window.location.hostname;
    return host === 'localhost' || host === '127.0.0.1' || host.endsWith('.local');
  }

  log(...args) {
    if (!this.enabled) return;
    
    // Usar console.error ya que no está silenciado, pero con prefijo para distinguir
    const timestamp = new Date().toISOString().substr(11, 12);
    this.originalError.call(console, `[DEBUG ${timestamp}]`, ...args);
  }

  info(...args) {
    this.log('ℹ️', ...args);
  }

  warn(...args) {
    this.log('⚠️', ...args);
  }

  error(...args) {
    this.log('❌', ...args);
  }

  success(...args) {
    this.log('✅', ...args);
  }

  // Método para activar/desactivar desde la consola
  enable() {
    this.enabled = true;
    localStorage.setItem('debugLogs', 'true');
    this.log('🔧 Debug logging habilitado (persistente)');
  }

  disable() {
    this.enabled = false;
    localStorage.removeItem('debugLogs');
    console.log('Debug logging deshabilitado');
  }

  // Log específico para el botón PDF
  pdfButton(action, data) {
    this.log(`📄 [PDF BUTTON] ${action}`, data);
  }

  // Log específico para datos de AI
  aiData(action, data) {
    this.log(`🤖 [AI DATA] ${action}`, data);
  }
}

// Crear instancia global
window.debugLogger = new DebugLogger();

// Exponer métodos de conveniencia
window.enableDebugLogs = () => window.debugLogger.enable();
window.disableDebugLogs = () => window.debugLogger.disable();

// Log de inicialización
if (window.debugLogger.enabled) {
  window.debugLogger.log('🚀 Debug Logger inicializado y listo');
}

