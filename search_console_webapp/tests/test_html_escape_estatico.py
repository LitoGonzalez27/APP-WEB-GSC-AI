"""
Escapado de HTML único (sep-2026): comprobaciones estáticas del frontend.

static/js/html-escape.js es la única implementación. Estos tests fallan si:
- vuelve a aparecer una copia propia (truco del DOM o cadena de replace), que
  es como se colaron las versiones que no escapaban comillas;
- un módulo ES usa globalThis.ClicandseoHtml sin importar html-escape.js;
- una plantilla usa window.ClicandseoHtml (en un script clásico o en línea)
  sin cargar antes html-escape.js;
- un fichero con import/export se carga como script clásico (error de sintaxis).

Las escapeForAttribute de las tablas Grid.js se quedan como estaban a
propósito: no escapan & (un dato que trae &amp; se sigue viendo igual) y ya
escapan comillas. Ver tests/js/html-escape.test.cjs.
"""

import pathlib
import re

APP = pathlib.Path(__file__).resolve().parent.parent
JS = APP / "static" / "js"
PLANTILLAS = APP / "templates"
COMPARTIDO = JS / "html-escape.js"

PERMITIDAS = {  # fichero -> motivo
    "static/js/ui-keywords-gridjs.js": "escapeForAttribute: solo comillas, conserva entidades",
    "static/js/ui-urls-gridjs.js": "escapeForAttribute: solo comillas y < >, conserva entidades",
    "static/js/ui-url-keywords-gridjs.js": "escapeForAttribute: solo comillas y < >, conserva entidades",
    "static/js/ui-detailed-results-gridjs.js": "escapeForAttribute: solo comillas, conserva entidades",
}

TRUCO_DOM = re.compile(r"textContent\s*=\s*[^;\n]+;?\s*(?:\n[^\n]*){0,2}?return\s+\w+\.innerHTML", re.M)
CADENA_REPLACE = re.compile(r"""replace\(/&/g,\s*['"]&amp;['"]\)|['"]&['"]\s*:\s*['"]&amp;['"]""")


def _js():
    return [p for p in JS.rglob("*.js") if not p.name.endswith(".min.js") and p != COMPARTIDO]


def _rel(p):
    return p.relative_to(APP).as_posix()


def _es_modulo(texto):
    return re.search(r"^\s*(import|export)\s", texto, re.M) is not None


def test_no_quedan_copias_propias_del_escapado():
    copias = []
    for p in _js() + list(PLANTILLAS.glob("*.html")):
        texto = p.read_text(encoding="utf-8", errors="replace")
        if TRUCO_DOM.search(texto) or (CADENA_REPLACE.search(texto) and _rel(p) not in PERMITIDAS):
            copias.append(_rel(p))
    assert not copias, f"Usa ClicandseoHtml.escapeHtml (static/js/html-escape.js), no una copia: {copias}"


def test_los_modulos_que_usan_el_global_importan_html_escape():
    sin_import = []
    for p in _js():
        texto = p.read_text(encoding="utf-8", errors="replace")
        if "globalThis.ClicandseoHtml" not in texto:
            continue
        imports = re.findall(r"^\s*import\s+['\"]([^'\"]+)['\"]", texto, re.M)
        if not any((p.parent / i).resolve() == COMPARTIDO.resolve() for i in imports):
            sin_import.append(_rel(p))
    assert not sin_import, sin_import


def _scripts_de(plantilla):
    """(posición, src o None si es en línea, es_modulo, contenido en línea)."""
    texto = plantilla.read_text(encoding="utf-8", errors="replace")
    for m in re.finditer(r"<script\b([^>]*)>(.*?)</script>", texto, re.S | re.I):
        atributos, cuerpo = m.group(1), m.group(2)
        src = re.search(r"""filename=['"]([^'"]+)['"]|src=['"]([^'"{]+)['"]""", atributos)
        ruta = (src.group(1) or src.group(2)) if src else None
        yield m.start(), ruta, 'type="module"' in atributos or "type='module'" in atributos, cuerpo


def test_las_plantillas_cargan_html_escape_antes_de_usarlo():
    clasicos = {p.relative_to(APP / "static").as_posix() for p in _js()
                if "window.ClicandseoHtml" in p.read_text(encoding="utf-8", errors="replace")}
    assert clasicos, "esperaba scripts clásicos que usan window.ClicandseoHtml"
    fallos = []
    for plantilla in PLANTILLAS.glob("*.html"):
        cargado = None
        for pos, ruta, _modulo, cuerpo in _scripts_de(plantilla):
            if ruta and ruta.endswith("js/html-escape.js"):
                cargado = pos
                continue
            usa = (ruta in clasicos) if ruta else ("ClicandseoHtml" in cuerpo)
            if usa and (cargado is None or cargado > pos):
                fallos.append(f"{plantilla.name}: {ruta or 'script en línea'}")
    assert not fallos, f"Falta <script src=js/html-escape.js> antes de: {fallos}"


def test_ningun_modulo_es_se_carga_como_script_clasico():
    modulos = {p.relative_to(APP / "static").as_posix() for p in _js()
               if _es_modulo(p.read_text(encoding="utf-8", errors="replace"))}
    fallos = [f"{pl.name}: {ruta}" for pl in PLANTILLAS.glob("*.html")
              for _pos, ruta, es_modulo, _c in _scripts_de(pl) if ruta in modulos and not es_modulo]
    assert not fallos, fallos


def test_el_compartido_no_usa_sintaxis_de_modulo():
    # Se carga con <script> clásico y con import: no puede llevar import/export.
    assert not _es_modulo(COMPARTIDO.read_text(encoding="utf-8"))
