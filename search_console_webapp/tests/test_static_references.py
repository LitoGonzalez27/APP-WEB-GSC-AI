"""
Toda referencia literal a un fichero estático apunta a un fichero que existe.

Cubre las plantillas (url_for('static', filename=...) y rutas /static/...),
los url_for de Python y los imports entre módulos JS (estáticos y dinámicos).
Existe para que borrar un JS, un CSS o una imagen que alguien sí usa no pase
desapercibido: la foto de rutas no lo detecta porque /static es una sola ruta.
"""

import re
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
STATIC = APP_DIR / "static"

URL_FOR = re.compile(r"""url_for\(\s*['"]static['"]\s*,\s*filename\s*=\s*['"]([^'"{}]+)['"]""")
STATIC_PATH = re.compile(r"""(?:src|href)\s*=\s*['"]/static/([^'"?#{}]+)""")
JS_IMPORT = re.compile(r"""(?:import\s+(?:[^'"]*?\s+from\s+)?|import\s*\(\s*)['"](\.{1,2}/[^'"]+)['"]""")


def _templates():
    for path in APP_DIR.rglob("*.html"):
        parts = set(path.relative_to(APP_DIR).parts)
        if parts & {"static", "tests", "scripts", "node_modules", ".claude"}:
            continue
        yield path


def test_referencias_estaticas_de_plantillas_y_python_existen():
    faltan = []
    python = [
        p for p in APP_DIR.rglob("*.py")
        if not (set(p.relative_to(APP_DIR).parts) & {"tests", "scripts", ".claude"})
    ]
    # En plantillas: url_for y rutas /static/. En Python solo url_for: hay HTML de
    # ejemplo con /static/ (p. ej. agent_scanner/selftest.py) que no es de la app.
    fuentes = [(p, (URL_FOR, STATIC_PATH)) for p in _templates()] + [(p, (URL_FOR,)) for p in python]
    for path, patrones in fuentes:
        text = path.read_text(encoding="utf-8", errors="replace")
        for patron in patrones:
            for ref in patron.findall(text):
                if not (STATIC / ref).exists():
                    faltan.append(f"{path.relative_to(APP_DIR)} -> static/{ref}")
    assert not faltan, "Referencias a estáticos que no existen:\n" + "\n".join(sorted(set(faltan)))


def test_imports_entre_modulos_js_existen():
    faltan = []
    for path in STATIC.rglob("*.js"):
        text = path.read_text(encoding="utf-8", errors="replace")
        for ref in JS_IMPORT.findall(text):
            if not (path.parent / ref).resolve().exists():
                faltan.append(f"{path.relative_to(APP_DIR)} -> {ref}")
    assert not faltan, "Imports JS a ficheros que no existen:\n" + "\n".join(sorted(set(faltan)))
