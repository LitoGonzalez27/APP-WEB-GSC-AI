/*
 * Interpretación de la respuesta de GET /admin/users/<id>/billing-details, que
 * usan el modal "Ver" y la precarga del modal "Custom Quota" del panel de admin.
 *
 * Contrato del servidor (fase de fiabilidad, sep-2026):
 *   200 {success: true, user}                -> datos (user.metrics_unavailable
 *                                               lista las métricas no disponibles)
 *   404 {code: 'user_not_found'}             -> el usuario no existe
 *   503 {code: 'database_unavailable', retry} -> no se pudo consultar: reintentar
 *   500 {code: 'internal_error'}             -> fallo interno
 *   401 / 403                                -> sesión o permisos
 * Un 503 no es "usuario no encontrado" ni cierra la sesión.
 *
 * Funciones puras (sin DOM): se prueban con `node --test tests/js/*.test.cjs`.
 */
(function (raiz) {
    'use strict';

    function referencia(cuerpo) {
        return cuerpo && cuerpo.request_id ? ` (ref. ${cuerpo.request_id})` : '';
    }

    function interpretarRespuestaDetalles(status, cuerpo) {
        const c = cuerpo && typeof cuerpo === 'object' ? cuerpo : null;
        if (status === 200 && c && c.success && c.user) {
            return {
                tipo: 'ok',
                user: c.user,
                reintentable: false,
                mensaje: '',
                metricasNoDisponibles: Array.isArray(c.user.metrics_unavailable) ? c.user.metrics_unavailable : [],
            };
        }
        if (status === 404) {
            return { tipo: 'no_existe', reintentable: false, mensaje: 'Este usuario no existe (puede haberse eliminado).' };
        }
        if (status === 503) {
            return {
                tipo: 'no_disponible',
                reintentable: true,
                mensaje: 'Servicio no disponible temporalmente. Reintenta en unos segundos.' + referencia(c),
            };
        }
        if (status === 401) {
            return { tipo: 'sesion', reintentable: false, mensaje: 'Tu sesión ha caducado. Vuelve a iniciar sesión.' };
        }
        if (status === 403) {
            return { tipo: 'permisos', reintentable: false, mensaje: 'No tienes permisos para ver este usuario.' };
        }
        return { tipo: 'error', reintentable: false, mensaje: 'Error interno al cargar los datos del usuario.' + referencia(c) };
    }

    /* Lee una Response de fetch. Si el servidor redirigió al login (sesión
       perdida en una petición sin cabeceras JSON), lo trata como sesión. */
    async function leerRespuesta(response) {
        if (response.redirected && /\/login/.test(response.url || '')) {
            return interpretarRespuestaDetalles(401, null);
        }
        let cuerpo = null;
        try {
            cuerpo = await response.json();
        } catch (_) {
            cuerpo = null;
        }
        return interpretarRespuestaDetalles(response.status, cuerpo);
    }

    /* Texto de una métrica: null/undefined = no disponible (nunca 0). */
    function valorMetrica(valor, formato) {
        if (valor === null || valor === undefined) return 'No disponible';
        return formato ? formato(valor) : String(valor);
    }

    const api = { interpretarRespuestaDetalles, leerRespuesta, valorMetrica };
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    } else {
        raiz.AdminBillingDetails = api;
    }
})(typeof window !== 'undefined' ? window : globalThis);
