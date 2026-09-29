/*
 * Interpretación de la respuesta de GET /auth/status para el gestor de sesión
 * (session-manager.js). Fase de fiabilidad (sep-2026): un fallo del servidor
 * (503 si la base de datos no está disponible, 500, 429, error de red) NO es
 * "sesión terminada"; antes el gestor cerraba la sesión del usuario en cuanto
 * la respuesta no traía authenticated=true.
 *
 * Devuelve 'activa', 'terminada' o 'desconocida' (no hacer nada y reintentar
 * en la próxima comprobación). Función pura: node --test tests/js/*.test.cjs
 */
(function (raiz) {
    'use strict';

    function interpretarEstadoSesion(status, datos) {
        const d = datos && typeof datos === 'object' ? datos : null;
        if (status === 401) {
            return d && (d.session_expired === true || d.auth_required === true) ? 'terminada' : 'desconocida';
        }
        if (status !== 200 || !d) return 'desconocida';
        if (d.authenticated === true) return 'activa';
        if (d.authenticated === false) return 'terminada';
        return 'desconocida';
    }

    const api = { interpretarEstadoSesion };
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    } else {
        raiz.SessionStatus = api;
    }
})(typeof window !== 'undefined' ? window : globalThis);
