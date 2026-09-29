// Tests de static/js/session-status.js (gestor de sesión del frontend).
// Ejecutar:  node --test tests/js/*.test.cjs     (Node 18+, sin dependencias)
const test = require('node:test');
const assert = require('node:assert/strict');
const { interpretarEstadoSesion } = require('../../static/js/session-status.js');

test('200 con authenticated=true: activa', () => {
    assert.equal(interpretarEstadoSesion(200, { authenticated: true, session: {} }), 'activa');
});

test('200 con authenticated=false (expirada, usuario borrado, suspendida): terminada', () => {
    assert.equal(interpretarEstadoSesion(200, { authenticated: false, session_expired: true }), 'terminada');
    assert.equal(interpretarEstadoSesion(200, { authenticated: false, user_not_found: true }), 'terminada');
    assert.equal(interpretarEstadoSesion(200, { authenticated: false, account_suspended: true }), 'terminada');
});

test('503 de la base de datos no disponible: desconocida, nunca terminada', () => {
    const cuerpo = { success: false, code: 'database_unavailable', retry: true, request_id: 'x' };
    assert.equal(interpretarEstadoSesion(503, cuerpo), 'desconocida');
});

test('500 interno (incluso con el cuerpo antiguo authenticated=false): desconocida', () => {
    assert.equal(interpretarEstadoSesion(500, { code: 'internal_error' }), 'desconocida');
    assert.equal(interpretarEstadoSesion(500, { authenticated: false, error: 'Internal server error' }), 'desconocida');
});

test('502, 504 y 429: desconocida', () => {
    for (const status of [502, 504, 429]) {
        assert.equal(interpretarEstadoSesion(status, null), 'desconocida', String(status));
    }
});

test('401 con marcas de sesión: terminada; 401 sin ellas: desconocida', () => {
    assert.equal(interpretarEstadoSesion(401, { session_expired: true }), 'terminada');
    assert.equal(interpretarEstadoSesion(401, { auth_required: true }), 'terminada');
    assert.equal(interpretarEstadoSesion(401, { error: 'otra cosa' }), 'desconocida');
});

test('cuerpo ilegible o sin authenticated: desconocida', () => {
    assert.equal(interpretarEstadoSesion(200, null), 'desconocida');
    assert.equal(interpretarEstadoSesion(200, {}), 'desconocida');
    assert.equal(interpretarEstadoSesion(200, 'html'), 'desconocida');
});
