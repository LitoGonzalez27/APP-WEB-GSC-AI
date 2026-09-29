// Tests de static/js/html-escape.js y de las funciones de escapado que lo usan.
// Ejecutar:  node --test tests/js/*.test.cjs     (Node 18+, sin dependencias)
//
// Cada fichero conserva su función local (escapeHtml, escapeForAttribute...)
// pero ahora delega en el escapado único. Aquí se extrae el código REAL de cada
// función del fichero y se compara con la versión anterior (copiada tal cual
// de git): el texto que ve el usuario debe ser el mismo y la salida no debe
// dejar comillas ni < > sin escapar (lo que permitía salirse de un atributo).
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = require('../../static/js/html-escape.js');
const RAIZ = path.join(__dirname, '..', '..');

// --- utilidades -----------------------------------------------------------

// Lo que ve el usuario: el texto tras decodificar las entidades.
function decodificar(s) {
    return s.replace(/&(amp|lt|gt|quot|nbsp|#0*39);/g, (_, e) => (
        { amp: '&', lt: '<', gt: '>', quot: '"', nbsp: ' ' }[e] || "'"));
}

// Serialización de un nodo de texto según el estándar HTML (lo que devolvía
// div.textContent = x; div.innerHTML): & < > y el espacio duro, sin comillas.
function trucoDom(text) {
    const t = text === null || text === undefined ? '' : String(text);
    return t.replace(/&/g, '&amp;').replace(/ /g, '&nbsp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// Extrae una función (declaración o método) del fichero, con llaves equilibradas.
function extraer(ruta, cabecera) {
    const src = fs.readFileSync(path.join(RAIZ, ruta), 'utf8');
    const i = src.indexOf(cabecera);
    assert.ok(i >= 0, `${ruta}: no encuentro «${cabecera}»`);
    let j = src.indexOf('{', i), nivel = 0, k = j;
    for (; k < src.length; k++) {
        if (src[k] === '{') nivel++;
        else if (src[k] === '}' && --nivel === 0) break;
    }
    const firma = cabecera.replace(/^export\s+/, '').replace(/^function\s+/, '').replace(/\s*\{$/, '');
    return `function ${firma} ${src.slice(j, k + 1)}`;
}

function compilar(codigo, nombre, extra = {}) {
    const ctx = vm.createContext({ ClicandseoHtml: html, globalThis: { ClicandseoHtml: html },
                                   window: { ClicandseoHtml: html }, String, ...extra });
    vm.runInContext(codigo, ctx);
    return ctx[nombre];
}

const ENTRADAS = ['', 'abc', '<b>hola</b>', 'a & b', '"entre comillas"', "O'Brien", ' x',
    '&amp;', 'ñandú 😀', '" onmouseover="alert(1)', "' onfocus='x", '<img src=x onerror=alert(1)>',
    0, 5, -1.5, NaN, true, false, null, undefined, [], ['a', 'b'], {}];

function sinRomperAtributos(salida) {
    return !/["'<>]/.test(salida);
}

// --- el escapado único ----------------------------------------------------

test('escapa & < > " \' y nada más', () => {
    assert.equal(html.escapeHtml(`<a title="x" data-y='z'>&</a>`),
        '&lt;a title=&quot;x&quot; data-y=&#39;z&#39;&gt;&amp;&lt;/a&gt;');
    assert.equal(html.escapeHtml('ñandú 😀  '), 'ñandú 😀  ');
});

test('null y undefined dan cadena vacía; lo demás se convierte con String()', () => {
    assert.equal(html.escapeHtml(null), '');
    assert.equal(html.escapeHtml(undefined), '');
    assert.equal(html.escapeHtml(0), '0');
    assert.equal(html.escapeHtml(false), 'false');
    assert.equal(html.escapeHtml(['a', '<b>']), 'a,&lt;b&gt;');
});

test('el texto que ve el usuario es el original y nunca sale del atributo', () => {
    for (const x of ENTRADAS) {
        const s = html.escapeHtml(x);
        assert.ok(sinRomperAtributos(s), `${JSON.stringify(x)} -> ${s}`);
        assert.equal(decodificar(s), x === null || x === undefined ? '' : String(x));
    }
});

test('la API es de solo lectura y queda en globalThis.ClicandseoHtml', () => {
    assert.ok(Object.isFrozen(html));
    assert.equal(globalThis.ClicandseoHtml, html);
});

// --- cada función que ahora delega: mismo texto visible que antes ----------

const TIPO_TEXTO = `function antigua(unsafe) {
  if (typeof unsafe !== 'string') return '';
  return unsafe.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}`;
const CASOS = [
    // [fichero, cabecera de la función actual, versión anterior, ¿ya escapaba comillas?]
    // Las escapeForAttribute de las tablas Grid.js no se tocan: no escapan & a
    // propósito (un dato con &amp; se sigue viendo como antes) y ya escapan comillas.
    ['static/js/ui-serp-modal.js', 'function escapeHtml(unsafe) {', TIPO_TEXTO, true],
    ['static/js/ui-aio-recommendations-modal.js', 'function escapeHtml(unsafe) {', TIPO_TEXTO, true],
    ['static/js/competitor-analysis.js', 'function escapeHtmlAttr(unsafe) {', TIPO_TEXTO, true],
    ['static/js/manual-ai/manual-ai-analytics-urls.js', 'function escapeHtml(unsafe) {', TIPO_TEXTO, true],
    ['static/js/manual-ai/manual-ai-competitors.js', 'function escapeHtml(unsafe) {', TIPO_TEXTO, true],
    ['static/js/manual-ai/manual-ai-analytics-domains.js', 'function escapeHtml(unsafe) {', TIPO_TEXTO, true],
    ['static/js/ai-mode-projects/ai-mode-analytics-domains.js', 'function escapeHtml(unsafe) {', TIPO_TEXTO, true],
    ['static/js/ai-mode-projects/ai-mode-analytics-urls.js', 'function escapeHtml(unsafe) {', TIPO_TEXTO, true],
    ['static/js/ui-render.js', 'function escapeHtml(text) {',
        "function antigua(text) { if (typeof text !== 'string') return ''; return DOM(text); }", false],
    ['static/js/number-utils.js', 'export function escapeHtml(text) {', 'function antigua(text) { return DOM(text); }', false],
    ['static/js/topic-clusters.js', 'escapeHtml(text) {', 'function antigua(text) { return DOM(text); }', false],
    ['static/js/keyword-exclusion.js', 'escapeHtml(text) {', 'function antigua(text) { return DOM(text); }', false],
    ['static/js/topic-clusters-visualization.js', 'function escapeHtml(text) {', 'function antigua(text) { return DOM(text); }', false],
    ['static/js/llm_monitoring/llm-monitoring-core.js', 'escapeHtml(text) {', 'function antigua(text) { return DOM(text); }', false],
    ['static/js/pending-invitations-banner.js', 'function esc(value) {',
        "function antigua(value) { return DOM(String(value == null ? '' : value)); }"],
    ['static/js/ui-ai-overview-utils.js', 'export function escapeHtml(text) {',
        "function antigua(text) { if (text == null) return ''; return String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\"/g, '&quot;').replace(/'/g, '&#039;'); }", true],
    ['static/js/manual-ai/manual-ai-utils.js', 'export function escapeHtml(text) {',
        "function antigua(text) { return String(text ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\"/g, '&quot;').replace(/'/g, '&#039;'); }", true],
    ['static/js/ai-mode-projects/ai-mode-utils.js', 'export function escapeHtml(text) {',
        "function antigua(text) { return String(text ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\"/g, '&quot;').replace(/'/g, '&#039;'); }", true],
    ['static/js/ui-keywords-gridjs.js', 'function escapeHtmlLocal(text) {',
        "function antigua(text) { const m = {'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#039;'}; return String(text || '').replace(/[&<>\"']/g, c => m[c]); }", true],
];

for (const [ruta, cabecera, antigua] of CASOS) {
    test(`${ruta} :: ${cabecera.replace(/ \{$/, '')} — mismo texto visible y sin romper atributos`, () => {
        const nombre = cabecera.replace(/^export\s+/, '').replace(/^function\s+/, '').split('(')[0];
        const nueva = compilar(extraer(ruta, cabecera), nombre);
        const vieja = compilar(antigua, 'antigua', { DOM: trucoDom });
        for (const x of ENTRADAS) {
            let esperado;
            try { esperado = vieja(x); } catch (e) { continue; }  // la antigua lanzaba: la nueva ya no
            const obtenido = nueva(x);
            assert.equal(decodificar(obtenido), decodificar(esperado), `${JSON.stringify(x)}: antes «${esperado}», ahora «${obtenido}»`);
            assert.ok(sinRomperAtributos(obtenido), `${JSON.stringify(x)} -> ${obtenido}`);
        }
    });
}

test('escapeAttr de LLM Monitoring sigue escapando comillas', () => {
    const src = extraer('static/js/llm_monitoring/llm-monitoring-core.js', 'escapeHtml(text) {')
        + '\n' + extraer('static/js/llm_monitoring/llm-monitoring-core.js', 'escapeAttr(text) {');
    const ctx = vm.createContext({ window: { ClicandseoHtml: html }, String });
    vm.runInContext(src + '\nvar obj = { escapeHtml, escapeAttr };', ctx);
    assert.equal(ctx.obj.escapeAttr(`a"b'c<d>`), 'a&quot;b&#39;c&lt;d&gt;');
});

test('los nombres de cluster ya no pueden salirse de title="..."', () => {
    for (const ruta of ['static/js/manual-ai/manual-ai-clusters.js', 'static/js/ai-mode-projects/ai-mode-projects.js',
                        'static/js/ai-mode-projects/ai-mode-clusters.js']) {
        const src = fs.readFileSync(path.join(RAIZ, ruta), 'utf8');
        assert.ok(src.includes('const escapedName = escapeHtml(cluster.name);'), ruta);
        assert.ok(!src.includes("cluster.name.replace(/</g, '&lt;')"), ruta);
    }
});

test('las escapeForAttribute de las tablas siguen igual (atributos normales: title, data-*, href)', () => {
    for (const [ruta, cabecera] of [['static/js/ui-keywords-gridjs.js', 'function escapeForAttribute(text) {'],
                                    ['static/js/ui-urls-gridjs.js', 'function escapeForAttribute(str) {'],
                                    ['static/js/ui-url-keywords-gridjs.js', 'function escapeForAttribute(str) {'],
                                    ['static/js/ui-detailed-results-gridjs.js', 'function escapeForAttribute(str) {']]) {
        const f = compilar(extraer(ruta, cabecera), 'escapeForAttribute');
        assert.equal(f(`a"b'c&amp;`).replace(/&#0?39;/g, "'"), "a&quot;b'c&amp;", ruta);
    }
});


// --- jsArg: datos dentro de manejadores en línea (onclick="f(...)") ----------

// Lo que hace el navegador con onclick="...": decodifica las entidades del
// atributo y ejecuta el JS resultante.
function ejecutarManejador(atributo) {
    const js = decodificar(atributo);
    let recibido;
    const f = new Function('f', js);
    f((x) => { recibido = x; });
    return recibido;
}

test('jsArg: el manejador recibe exactamente el dato, sin romper el atributo ni el JS', () => {
    const datos = ["Qu'est-ce que Acme ?", "What's the best CRM?", "mcdonald's menu", 'a"b', "x');alert(1);//",
        '&quot;);alert(1);//', '</script><b>', 'c:\\dir', '\u2028\u2029', '', 0, 12.5, true, null,
        { id: 3, name: "O'Brien \"Jr\" & Co" }, ['a', "b'c"]];
    for (const x of datos) {
        const arg = html.jsArg(x);
        assert.ok(sinRomperAtributos(arg), `${JSON.stringify(x)} -> ${arg}`);
        assert.deepEqual(ejecutarManejador(`f(${arg})`), x, JSON.stringify(x));
    }
    assert.equal(ejecutarManejador(`f(${html.jsArg(undefined)})`), null);
});

test('antes: escapeHtml + replace de apóstrofo ya no protege dentro de onclick (el fallo que corrige jsArg)', () => {
    const viejo = (s) => html.escapeHtml(s).replace(/'/g, "\\'");  // el patrón de llm-monitoring-queries.js
    assert.throws(() => ejecutarManejador(`f('${viejo("Qu'est-ce que Acme ?")}')`), SyntaxError);
});
