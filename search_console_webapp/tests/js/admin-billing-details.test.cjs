// Tests de static/js/admin-billing-details.js (modal "Ver" del panel de admin).
// Ejecutar:  node --test tests/js/*.test.cjs     (Node 18+, sin dependencias)
const test = require('node:test');
const assert = require('node:assert/strict');
const {
    interpretarRespuestaDetalles,
    leerRespuesta,
    valorMetrica,
} = require('../../static/js/admin-billing-details.js');

function respuesta(status, cuerpo, extra = {}) {
    return {
        status,
        redirected: false,
        url: 'https://app.test/admin/users/3/billing-details',
        json: async () => {
            if (cuerpo === undefined) throw new SyntaxError('Unexpected token <');
            return cuerpo;
        },
        ...extra,
    };
}

test('200 con datos: ok y lista de métricas no disponibles', () => {
    const r = interpretarRespuestaDetalles(200, {
        success: true,
        user: { id: 3, metrics_unavailable: ['serp_usage'] },
    });
    assert.equal(r.tipo, 'ok');
    assert.equal(r.user.id, 3);
    assert.deepEqual(r.metricasNoDisponibles, ['serp_usage']);
});

test('404: el usuario no existe, no se reintenta', () => {
    const r = interpretarRespuestaDetalles(404, { success: false, code: 'user_not_found' });
    assert.equal(r.tipo, 'no_existe');
    assert.equal(r.reintentable, false);
    assert.match(r.mensaje, /no existe/);
});

test('503: no disponible y reintentable; nunca "no encontrado" ni sesión', () => {
    const r = interpretarRespuestaDetalles(503, {
        success: false, code: 'database_unavailable', retry: true, request_id: 'abc123',
    });
    assert.equal(r.tipo, 'no_disponible');
    assert.equal(r.reintentable, true);
    assert.doesNotMatch(r.mensaje, /no existe|no encontrado|sesión/i);
    assert.match(r.mensaje, /abc123/);
});

test('500: error interno con referencia, sin reintento automático', () => {
    const r = interpretarRespuestaDetalles(500, { code: 'internal_error', request_id: 'x9' });
    assert.equal(r.tipo, 'error');
    assert.equal(r.reintentable, false);
    assert.match(r.mensaje, /interno.*x9/);
});

test('401 y 403: sesión y permisos', () => {
    assert.equal(interpretarRespuestaDetalles(401, { auth_required: true }).tipo, 'sesion');
    assert.equal(interpretarRespuestaDetalles(403, { admin_required: true }).tipo, 'permisos');
});

test('200 sin success (cuerpo inesperado) no se toma como datos', () => {
    assert.equal(interpretarRespuestaDetalles(200, null).tipo, 'error');
    assert.equal(interpretarRespuestaDetalles(200, { success: false }).tipo, 'error');
});

test('leerRespuesta: cuerpo que no es JSON (HTML) es un error, no datos', async () => {
    const r = await leerRespuesta(respuesta(500, undefined));
    assert.equal(r.tipo, 'error');
});

test('leerRespuesta: redirección al login se trata como sesión', async () => {
    const r = await leerRespuesta(respuesta(200, undefined, {
        redirected: true, url: 'https://app.test/login?auth_required=true',
    }));
    assert.equal(r.tipo, 'sesion');
});

test('leerRespuesta: 503 con JSON', async () => {
    const r = await leerRespuesta(respuesta(503, { code: 'database_unavailable', retry: true }));
    assert.equal(r.tipo, 'no_disponible');
    assert.equal(r.reintentable, true);
});

test('valorMetrica: null o ausente es "No disponible", 0 es 0', () => {
    assert.equal(valorMetrica(null, (v) => `${v} RU`), 'No disponible');
    assert.equal(valorMetrica(undefined), 'No disponible');
    assert.equal(valorMetrica(0, (v) => `${v} RU`), '0 RU');
    assert.equal(valorMetrica(7), '7');
});
