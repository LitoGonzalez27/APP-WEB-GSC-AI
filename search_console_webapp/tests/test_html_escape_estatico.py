"""
Escapado de HTML único (sep-2026): comprobaciones estáticas del frontend.

static/js/html-escape.js es la única implementación. Estos tests fallan si:
- vuelve a aparecer una copia propia (truco del DOM o cadena de replace), que
  es como se colaron las versiones que no escapaban comillas;
- un módulo ES usa globalThis.ClicandseoHtml sin importar html-escape.js;
- una plantilla usa window.ClicandseoHtml (en un script clásico o en línea)
  sin cargar antes html-escape.js;
- un fichero con import/export se carga como script clásico (error de sintaxis);
- un dato va dentro de un manejador en línea (onclick="...${x}...") sin
  ClicandseoHtml.jsArg(x): ahí el navegador decodifica las entidades antes de
  ejecutar el JS (se exceptúan números y constantes, listados por fichero);
- reaparecen los parches que no protegen: escapeHtml(x).replace(/'/g, "\\'"),
  JSON.stringify(x).replace(/"/g, '&quot;') o un escapado parcial de < >.

No ve manejadores montados concatenando cadenas con + ni con setAttribute
('onclick', ...): hoy no hay ninguno con datos (revisado a mano, sep-2026).

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
CADENA_REPLACE = re.compile(r"""replace\(/&/g,\s*['"]&amp;['"]\)|['"]&['"]\s*:\s*['"]&amp;['"]|replace\(/</g,\s*['"]&lt;['"]\)""")
PARCHES = re.compile(r"""escape\w*\([^)]*\)\.replace\(/'/g|JSON\.stringify\([^)]*\)\.replace\(/"/g""")
INICIO_MANEJADOR = re.compile(r"""\bon[a-z]+\s*=\s*(\\?["'])""")
EXPRESION_SEGURA = re.compile(r"^(?:(?:window|globalThis)\.)?ClicandseoHtml\.jsArg\(|^Number\(|^[\w.]+\.id$|^(?:index|i|idx)$")
# (fichero, expresión) -> por qué es seguro dentro de on*="..."
EN_MANEJADOR_PERMITIDOS = {
    ("static/js/quota-ui.js", "plan"): "constante del código ('basic' / 'premium')",
    ("static/js/ui-render.js", "range"): "rango de fechas fijo",
    ("templates/admin_simple.html", "moduleKey"): "clave de módulo fija",
    ("templates/admin_simple.html", "on ? 'off' : 'auto'"): "constante",
    ("templates/project_access.html", "member.user_id"): "id numérico",
    ("static/js/llm_monitoring/llm-monitoring-fanout.js", "page - 1"): "número de página",
    ("static/js/llm_monitoring/llm-monitoring-fanout.js", "page + 1"): "número de página",
    ("static/js/llm_monitoring/llm-monitoring-responses.js", "globalIndex"): "índice numérico",
    ("static/js/topic-clusters.js", "clusterIndex"): "índice numérico",
    ("static/js/topic-clusters.js", "termIndex"): "índice numérico",
    ("static/js/llm_monitoring/llm-monitoring-projects.js", "configuredQueries"): "Number(...)",
    ("static/js/llm_monitoring/llm-monitoring-projects.js", "safeProjectName"): "resultado de jsArg",
    ("static/js/manual-ai/manual-ai-projects.js", "safeName"): "resultado de jsArg",
    ("static/js/ai-mode-projects/ai-mode-projects.js", "safeName"): "resultado de jsArg",
    ("static/js/manual-ai/manual-ai-analytics-domains.js", "safeDomainInitial"): "una letra o número",
    ("static/js/manual-ai/manual-ai-analytics-domains.js", "safeDetectedInitial"): "una letra o número",
    ("static/js/manual-ai/manual-ai-analytics-urls.js", "safeUrlDomainInitial"): "una letra o número",
    ("static/js/ai-mode-projects/ai-mode-analytics-domains.js", "safeDomainInitial"): "una letra o número",
    ("static/js/ai-mode-projects/ai-mode-analytics-domains.js", "safeDetectedInitial"): "una letra o número",
    ("static/js/ai-mode-projects/ai-mode-analytics-urls.js", "safeUrlDomainInitial"): "una letra o número",
}


def _valor_atributo(texto, pos, comilla):
    """Valor de un atributo desde `pos` (tras la comilla) hasta su cierre, sin
    cortar dentro de ${...} (que puede llevar comillas y llaves)."""
    i, prof, n = pos, 0, len(texto)
    while i < n:
        c = texto[i]
        if prof == 0:
            if texto.startswith(comilla, i):
                return texto[pos:i]
            if texto.startswith("${", i):
                prof, i = 1, i + 2
                continue
            if c == "`":
                return None
        elif c == "{":
            prof += 1
        elif c == "}":
            prof -= 1
        elif c in "\"'`":
            j = i + 1
            while j < n and texto[j] != c:
                j += 2 if texto[j] == "\\" else 1
            i = j
        i += 1
    return None


def _expresiones(valor):
    out, i = [], 0
    while (k := valor.find("${", i)) >= 0:
        prof, j = 1, k + 2
        while j < len(valor) and prof:
            prof += {"{": 1, "}": -1}.get(valor[j], 0)
            j += 1
        out.append(valor[k + 2:j - 1].strip())
        i = j
    return out + [m.strip() for m in re.findall(r"\{\{(.*?)\}\}", valor)]


def _js():
    return [p for p in JS.rglob("*.js") if not p.name.endswith(".min.js") and p != COMPARTIDO]


def _rel(p):
    return p.relative_to(APP).as_posix()


def _es_modulo(texto):
    return re.search(r"^\s*(import|export)\s", texto, re.M) is not None


def _plantillas():
    return sorted(PLANTILLAS.rglob("*.html"))


def test_no_quedan_copias_propias_del_escapado():
    copias = []
    for p in _js() + _plantillas():
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
    for plantilla in _plantillas():
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
    fallos = [f"{pl.name}: {ruta}" for pl in _plantillas()
              for _pos, ruta, es_modulo, _c in _scripts_de(pl) if ruta in modulos and not es_modulo]
    assert not fallos, fallos


def test_el_compartido_no_usa_sintaxis_de_modulo():
    # Se carga con <script> clásico y con import: no puede llevar import/export.
    assert not _es_modulo(COMPARTIDO.read_text(encoding="utf-8"))


def test_los_datos_en_manejadores_en_linea_van_con_jsarg():
    # Dentro de on*="..." el navegador decodifica las entidades antes de ejecutar
    # el JS: un dato solo es seguro con jsArg (o si es un número o una constante).
    fallos, usados = [], set()
    for p in _js() + _plantillas():
        texto = p.read_text(encoding="utf-8", errors="replace")
        for m in INICIO_MANEJADOR.finditer(texto):
            valor = _valor_atributo(texto, m.end(), m.group(1))
            for expr in _expresiones(valor or ""):
                clave = (_rel(p), expr)
                if EXPRESION_SEGURA.search(expr):
                    continue
                if clave in EN_MANEJADOR_PERMITIDOS:
                    usados.add(clave)
                    continue
                fallos.append(f"{_rel(p)}:{texto.count(chr(10), 0, m.start()) + 1} ${{{expr}}}")
    assert not fallos, f"Pasa los datos con ClicandseoHtml.jsArg(x): {fallos}"
    assert not set(EN_MANEJADOR_PERMITIDOS) - usados, set(EN_MANEJADOR_PERMITIDOS) - usados


def test_no_reaparecen_parches_que_no_protegen():
    fallos = []
    for p in _js() + _plantillas():
        texto = p.read_text(encoding="utf-8", errors="replace")
        for m in PARCHES.finditer(texto):
            fallos.append(f"{_rel(p)}:{texto.count(chr(10), 0, m.start()) + 1}")
    assert not fallos, f"Usa ClicandseoHtml.jsArg(x) (datos en onclick) o escapeHtml: {fallos}"
