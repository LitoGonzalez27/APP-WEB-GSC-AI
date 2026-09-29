/**
 * Escapado de HTML único para todo el frontend (sep-2026).
 *
 * Había ~25 copias de escapeHtml con comportamientos distintos. Las basadas en
 * el truco del DOM (textContent -> innerHTML) no escapan comillas, así que un
 * dato de usuario dentro de un atributo (title="...", value="...") podía
 * cerrarlo e inyectar código. Esta versión escapa & < > " ' siempre.
 *
 * Se carga como script normal (window.ClicandseoHtml) y también desde módulos
 * ES con `import './html-escape.js'` (solo por efecto: define el global). En
 * Node (tests) se exporta con module.exports.
 *
 * Contrato: null y undefined dan ''; cualquier otro valor se convierte con
 * String() y se escapa. Las copias que devolvían '' para lo que no fuera texto
 * conservan esa comprobación en su propio fichero.
 *
 * Para pasar un dato a un manejador en línea (onclick="..."), jsArg().
 */
(function (raiz) {
    'use strict';

    var ENTIDADES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

    function escapeHtml(valor) {
        if (valor === null || valor === undefined) return '';
        return String(valor).replace(/[&<>"']/g, function (c) { return ENTIDADES[c]; });
    }

    // Valor para un manejador en línea: onclick="f(${ClicandseoHtml.jsArg(x)})".
    // Dentro de on*="..." el navegador decodifica las entidades ANTES de ejecutar
    // el JS, así que escapeHtml solo no basta: 'x' con un apóstrofo cierra la
    // cadena. Aquí el valor se convierte en literal JS con JSON (comillas y
    // barras escapadas) y después se escapa para el atributo. El JS recibe
    // exactamente el valor (undefined llega como null).
    function jsArg(valor) {
        return escapeHtml(JSON.stringify(valor === undefined ? null : valor));
    }

    var api = Object.freeze({ escapeHtml: escapeHtml, jsArg: jsArg });

    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    if (raiz) raiz.ClicandseoHtml = api;
})(typeof globalThis !== 'undefined' ? globalThis : (typeof self !== 'undefined' ? self : this));
