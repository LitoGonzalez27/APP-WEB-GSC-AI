// Tests de interpretarBloqueoSerp (static/js/ui-serp-modal.js): el modal de SERP
// muestra el aviso de mejorar plan (402) o el de cuota agotada (429 con
// quota_blocked) en vez de un error. Se extrae el código real de la función.
// Ejecutar:  node --test tests/js/*.test.cjs
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function cargar() {
    const src = fs.readFileSync(path.join(__dirname, '..', '..', 'static/js/ui-serp-modal.js'), 'utf8');
    const i = src.indexOf('export function interpretarBloqueoSerp(');
    assert.ok(i >= 0);
    let j = src.indexOf('{', i), nivel = 0, k = j;
    for (; k < src.length; k++) {
        if (src[k] === '{') nivel++;
        else if (src[k] === '}' && --nivel === 0) break;
    }
    const llamadas = [];
    const window = {
        showPaywall: (...a) => llamadas.push(['paywall', ...a]),
        showQuotaExceeded: (...a) => llamadas.push(['cuota', ...a]),
    };
    const ctx = vm.createContext({ window });
    vm.runInContext('function interpretarBloqueoSerp' + src.slice(src.indexOf('(', i), k + 1), ctx);
    return { f: ctx.interpretarBloqueoSerp, llamadas };
}

test('402: aviso de mejorar plan con las opciones del servidor', () => {
    const { f, llamadas } = cargar();
    assert.equal(f(402, { upgrade_options: ['premium'] }), 'SERP view is available on paid plans.');
    assert.deepEqual(llamadas, [['paywall', 'SERP View', ['premium']]]);
});

test('429 con quota_blocked: aviso de cuota agotada', () => {
    const { f, llamadas } = cargar();
    assert.equal(f(429, { quota_blocked: true, quota_info: { remaining: 0 } }), 'You have used all your monthly quota.');
    assert.deepEqual(llamadas, [['cuota', { remaining: 0 }]]);
});

test('429 del limitador (sin quota_blocked) y el resto: no es un bloqueo', () => {
    const { f, llamadas } = cargar();
    assert.equal(f(429, { error: 'rate limit' }), null);
    assert.equal(f(500, {}), null);
    assert.equal(f(200, { organic_results: [] }), null);
    assert.deepEqual(llamadas, []);
});
