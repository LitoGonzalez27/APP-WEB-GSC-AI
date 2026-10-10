/**
 * Contrato plantillas ↔ JavaScript: todo lo que el HTML llama existe.
 *
 * Un onclick="manualAI.algo()" que apunta a un método inexistente no da error
 * hasta que alguien pulsa el botón, y entonces solo sale en la consola. Así
 * estuvo roto un año el cierre del modal «Delete project» de AI Overview.
 *
 *  A. Manejadores de los paneles (manualAI, aiModeSystem, llmMonitoring): se
 *     cargan las clases reales en Node (con un DOM falso que lo acepta todo) y
 *     se mira su prototipo, así que cuenta lo que existe de verdad, también lo
 *     añadido con Object.assign desde los módulos.
 *  B. Funciones globales llamadas desde un manejador (closeModal(), etc.):
 *     tienen que estar definidas en algún JS o <script> de la app.
 *  C. Los módulos ES de AI Overview y AI Mode cargan: un import de un nombre
 *     que el módulo no exporta tumba la página entera sin aviso.
 *  D. El JS no muestra con display:'block' un elemento al que el CSS da
 *     rejilla o flex: el estilo en línea gana y la maqueta se pierde (así se
 *     descolocaron los botones de clusters). Para mostrarlo: display = ''.
 *
 * Revisa las plantillas y también el HTML que genera el JS (innerHTML con
 * onclick="..."). Ejecutar: node --test tests/js/*.test.cjs
 */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { pathToFileURL } = require('node:url');
const { register } = require('node:module');

const APP = path.resolve(__dirname, '..', '..');

// Fallos conocidos, pendientes de decisión. Cada entrada dice por qué sigue
// aquí; si se arregla, el test obliga a quitarla (no se acumulan obsoletas).
const CONOCIDOS = {
  'manualAI.hideProjectDetails': 'modal projectDetailsModal: ningún código lo abre (HTML muerto)',
  'manualAI.updateProjectName': 'campo projectNameEdit de un bloque que ya no se muestra (HTML muerto)',
  'aiModeSystem.updateProjectName': 'igual que en AI Overview',
  'manualAI.hideAnnotationModal': 'modal annotationModal: ningún código lo abre (HTML muerto)',
  'manualAI.saveAnnotation': 'modal annotationModal: ningún código lo abre (HTML muerto)',
  'aiModeSystem.hideAnnotationModal': 'igual que en AI Overview',
  'aiModeSystem.saveAnnotation': 'igual que en AI Overview',
};

const PANELES = {
  manualAI: { modulo: 'static/js/manual-ai-system-modular.js', clase: 'ManualAISystem' },
  aiModeSystem: { modulo: 'static/js/ai-mode-system-modular.js', clase: 'AIModeSystem' },
  llmMonitoring: { plantilla: 'templates/llm_monitoring.html', clase: 'LLMMonitoring' },
};

// DOM falso: cualquier propiedad, llamada o «new» devuelve el mismo objeto.
// Basta para que los módulos se evalúen; no se ejecuta la app.
function domFalso() {
  const f = function () {};
  const p = new Proxy(f, {
    get(_, k) {
      if (k === Symbol.toPrimitive) return () => '';
      if (k === 'then') return undefined; // que no parezca una promesa
      if (k === 'readyState') return 'loading'; // la app espera a DOMContentLoaded, que no llega
      if (k === 'length') return 0;
      if (k === Symbol.iterator) return function* () {};
      return p;
    },
    set: () => true,
    apply: () => p,
    construct: () => p,
    has: () => true,
  });
  return p;
}

const GLOBALES_NAVEGADOR = [
  'window', 'document', 'localStorage', 'sessionStorage', 'navigator', 'location',
  'history', 'Chart', 'ChartDataLabels', 'gridjs', 'fetch', 'HTMLElement', 'Element',
  'Node', 'CustomEvent', 'Event', 'MutationObserver', 'IntersectionObserver',
  'ResizeObserver', 'getComputedStyle', 'requestAnimationFrame', 'alert', 'confirm',
];

function metodos(Clase) {
  const nombres = new Set();
  for (let p = Clase.prototype; p && p !== Object.prototype; p = Object.getPrototypeOf(p)) {
    Object.getOwnPropertyNames(p).forEach((n) => nombres.add(n));
  }
  return nombres;
}

function ficheros(dir, ext, fuera = ['vendor', 'node_modules']) {
  const out = [];
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) { if (!fuera.includes(e.name)) out.push(...ficheros(p, ext, fuera)); }
    else if (ext.test(e.name)) out.push(p);
  }
  return out;
}

const FUENTES = [...ficheros(path.join(APP, 'templates'), /\.html$/), ...ficheros(path.join(APP, 'static', 'js'), /\.js$/)];
const TEXTOS = new Map(FUENTES.map((f) => [f, fs.readFileSync(f, 'utf8')]));

// Todos los manejadores en línea (on...="...") con su fichero y línea
function manejadores() {
  const out = [];
  for (const [f, t] of TEXTOS) {
    for (const m of t.matchAll(/\bon[a-z]+\s*=\s*(\\?["'])(.*?)\1/g)) {
      out.push({ codigo: m[2], donde: `${path.relative(APP, f)}:${t.slice(0, m.index).split('\n').length}` });
    }
  }
  return out;
}

async function cargarClases() {
  // AI Mode importa con rutas absolutas (/static/js/...) y alguno lleva ?v=
  const hooks = `const BASE=${JSON.stringify(pathToFileURL(APP).href)};
    export async function resolve(s, c, n) { return n(s.startsWith('/static/') ? BASE + s : s.split('?')[0], c); }`;
  register('data:text/javascript,' + encodeURIComponent(hooks));

  const dom = domFalso();
  for (const k of GLOBALES_NAVEGADOR) {
    try { globalThis[k] = dom; } catch { Object.defineProperty(globalThis, k, { value: dom, configurable: true }); }
  }
  const consola = { ...console };
  for (const k of ['log', 'info', 'warn', 'debug']) console[k] = () => {};

  const clases = {};
  try {
    for (const [global, cfg] of Object.entries(PANELES)) {
      if (cfg.modulo) {
        const mod = await import(pathToFileURL(path.join(APP, cfg.modulo)).href);
        clases[global] = metodos(mod[cfg.clase] || mod.default);
      } else {
        // Scripts clásicos: en el orden de la plantilla, en un mismo contexto
        const ctx = vm.createContext({
          ...Object.fromEntries(GLOBALES_NAVEGADOR.map((k) => [k, dom])),
          console: { log() {}, info() {}, warn() {}, debug() {}, error() {} },
          setTimeout: () => 0, clearTimeout: () => {}, setInterval: () => 0, clearInterval: () => {},
        });
        const tpl = fs.readFileSync(path.join(APP, cfg.plantilla), 'utf8');
        for (const m of tpl.matchAll(/<script\s+src="\{\{\s*url_for\('static',\s*filename='([^']+)'\)\s*\}\}/g)) {
          const f = path.join(APP, 'static', m[1]);
          vm.runInContext(fs.readFileSync(f, 'utf8'), ctx, { filename: f });
        }
        clases[global] = metodos(vm.runInContext(cfg.clase, ctx));
      }
    }
  } finally {
    Object.assign(console, consola);
  }
  return clases;
}

test('A y C. los manejadores de los paneles llaman a métodos que existen', async () => {
  const clases = await cargarClases(); // C: si un import no existe, falla aquí
  for (const [g, m] of Object.entries(clases)) assert.ok(m.size > 50, `${g}: solo ${m.size} métodos, ¿cargó bien?`);

  const rotos = new Map();
  let revisados = 0;
  const llamada = /(?<![\w$.])(?:window\.)?(manualAI|aiModeSystem|llmMonitoring)\??\.([A-Za-z_$][\w$]*)\s*\(/g;
  for (const { codigo, donde } of manejadores()) {
    for (const [, g, metodo] of codigo.matchAll(llamada)) {
      revisados++;
      if (clases[g].has(metodo)) continue;
      const clave = `${g}.${metodo}`;
      if (!rotos.has(clave)) rotos.set(clave, []);
      rotos.get(clave).push(donde);
    }
  }
  assert.ok(revisados > 100, `solo ${revisados} manejadores revisados: ¿ha cambiado el formato?`);

  const nuevos = [...rotos].filter(([k]) => !(k in CONOCIDOS));
  assert.deepStrictEqual(
    nuevos.map(([k, d]) => `${k}()  ←  ${d.join(', ')}`), [],
    'Botones que llaman a un método que no existe (no harán nada al pulsarlos)',
  );
  const arreglados = Object.keys(CONOCIDOS).filter((k) => !rotos.has(k));
  assert.deepStrictEqual(arreglados, [], 'Ya funcionan: quítalos de CONOCIDOS');
});

test('B. las funciones globales que llama el HTML están definidas', () => {
  const todo = [...TEXTOS.values()].join('\n');
  const definida = (n) => new RegExp(
    `function\\s+${n}\\s*\\(|(?:window\\.|\\b(?:const|let|var)\\s+)${n}\\s*=|\\b${n}\\s*=\\s*(?:async\\s*)?(?:function|\\()`,
  ).test(todo);
  // Del lenguaje o del navegador: no se definen en la app
  const nativas = new Set([
    'if', 'for', 'while', 'switch', 'return', 'function', 'typeof', 'new', 'catch',
    'alert', 'confirm', 'prompt', 'setTimeout', 'setInterval', 'clearTimeout', 'fetch',
    'parseInt', 'parseFloat', 'String', 'Number', 'Boolean', 'encodeURIComponent',
    'decodeURIComponent', 'event', 'open', 'print', 'history', 'f',
  ]);
  const faltan = new Map();
  for (const { codigo, donde } of manejadores()) {
    // Fuera cadenas e interpolaciones (${...}, {{ ... }}) para no leer llamadas dentro
    const limpio = codigo.replace(/'[^']*'|`[^`]*`|\$\{[^}]*\}|\{\{.*?\}\}/g, "''");
    for (const [, n] of limpio.matchAll(/(?<![\w$.])([A-Za-z_$][\w$]*)\s*\(/g)) {
      if (nativas.has(n) || definida(n)) continue;
      if (!faltan.has(n)) faltan.set(n, []);
      faltan.get(n).push(donde);
    }
  }
  assert.deepStrictEqual([...faltan].map(([n, d]) => `${n}()  ←  ${d.join(', ')}`), [],
    'Funciones llamadas desde el HTML que no están definidas en ningún sitio');
});

test("D. no se fuerza display:'block' sobre elementos con rejilla o flex", () => {
  // id → clases, de las plantillas
  const clasesDe = new Map();
  for (const [f, t] of TEXTOS) {
    if (!f.endsWith('.html')) continue;
    for (const [tag] of t.matchAll(/<[a-zA-Z][^>]*>/g)) {
      const id = /\bid="([\w-]+)"/.exec(tag);
      if (!id) continue;
      const cls = /\bclass="([^"]*)"/.exec(tag);
      clasesDe.set(id[1], new Set((cls ? cls[1] : '').split(/\s+/).filter(Boolean)));
    }
  }
  // Clases/ids a los que alguna regla CSS da display grid o flex (último
  // compuesto del selector, que es el elemento al que se aplica)
  const conMaqueta = new Set();
  for (const f of ficheros(path.join(APP, 'static'), /\.css$/)) {
    const css = fs.readFileSync(f, 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
    for (const [, sel, cuerpo] of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
      if (!/display\s*:\s*(?:inline-)?(?:grid|flex)/.test(cuerpo)) continue;
      for (const s of sel.split(',')) {
        const ultimo = s.trim().split(/[\s>+~]+/).pop() || '';
        for (const [tok] of ultimo.matchAll(/[#.][\w-]+/g)) conMaqueta.add(tok);
      }
    }
  }
  const malos = [];
  for (const [f, t] of TEXTOS) {
    if (!f.endsWith('.js')) continue;
    for (const m of t.matchAll(/([\w$.()'"-]+?)\.style\.display\s*=\s*([^;\n]*)/g)) {
      if (!/['"]block['"]/.test(m[2])) continue;
      let id = (/getElementById\(\s*['"]([\w-]+)['"]/.exec(m[1]) || [])[1];
      if (!id) { // variable: su último getElementById antes de esta línea
        const v = m[1].split('.').pop().replace(/[^\w$]/g, '');
        const antes = [...t.slice(0, m.index).matchAll(new RegExp(`\\b${v}\\s*=\\s*document\\.getElementById\\(\\s*['"]([\\w-]+)['"]`, 'g'))];
        id = antes.length ? antes[antes.length - 1][1] : null;
      }
      if (!id || !clasesDe.has(id)) continue;
      const choca = ['#' + id, ...[...clasesDe.get(id)].map((c) => '.' + c)].filter((k) => conMaqueta.has(k));
      if (choca.length) malos.push(`${path.relative(APP, f)}:${t.slice(0, m.index).split('\n').length}  #${id} (${choca.join(', ')} es grid/flex)`);
    }
  }
  assert.deepStrictEqual(malos, [], "display:'block' anula la rejilla/flex del CSS; usa display = ''");
});
