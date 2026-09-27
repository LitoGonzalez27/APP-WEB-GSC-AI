"""
Comprueba que las dependencias de producción (requirements.txt) cubren todo lo
que importa el código vivo de la app.

"Código vivo" = lo alcanzable por imports desde app.py y desde los scripts que
cita railway.json. Se recorren con ast (sin ejecutarlos), se sacan los módulos
externos (ni stdlib ni del propio repo) y se intenta importar cada uno.

Uso (en una imagen con solo requirements.txt, ver scripts/check.sh):
    python scripts/check_prod_deps.py
Sale con código 1 si falta algún módulo que no esté en OPCIONALES.
"""

import ast
import importlib
import json
import re
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent

# Imports que el código ya protege con try/except y no son necesarios en producción.
OPCIONALES = {
    "scrapling",  # agent_scanner/_camoufox_probe.py: sonda local, no se usa en producción
    "brotlicffi",  # agent_scanner/httpfetch.py: alternativa a brotli, solo si brotli falta
}


def _imports(path):
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return set()
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            out.add(node.module.split(".")[0])
    return out


def live_files():
    root_mods = {p.stem: p for p in APP_DIR.glob("*.py")}
    pkgs = {p.name: p for p in APP_DIR.iterdir() if p.is_dir() and (p / "__init__.py").exists()}
    pending = ["app"]
    railway = json.loads((APP_DIR / "railway.json").read_text())
    for cron in railway.get("crons", []):
        m = re.search(r"python3\s+(\S+)\.py", cron.get("command", ""))
        if m:
            pending.append(m.group(1))
    seen, files = set(), []
    while pending:
        mod = pending.pop()
        if mod in seen:
            continue
        seen.add(mod)
        if mod in root_mods:
            mod_files = [root_mods[mod]]
        elif mod in pkgs:
            mod_files = [p for p in pkgs[mod].rglob("*.py") if "__pycache__" not in p.parts]
        else:
            continue
        files.extend(mod_files)
        for f in mod_files:
            for imp in _imports(f):
                if imp not in seen and (imp in root_mods or imp in pkgs):
                    pending.append(imp)
    return files, set(root_mods) | set(pkgs)


def main():
    files, local = live_files()
    externos = set()
    for f in files:
        externos |= _imports(f)
    externos -= local
    externos -= set(sys.stdlib_module_names)
    externos -= {"__future__"}

    faltan = []
    for mod in sorted(externos):
        try:
            importlib.import_module(mod)
        except Exception as exc:  # ImportError u otros fallos al importar
            faltan.append((mod, f"{type(exc).__name__}: {exc}"))

    print(f"Ficheros vivos: {len(files)} · módulos externos: {len(externos)}")
    print("Importables: " + ", ".join(sorted(externos - {m for m, _ in faltan})))
    graves = [(m, e) for m, e in faltan if m not in OPCIONALES]
    for mod, err in faltan:
        marca = "opcional" if mod in OPCIONALES else "FALTA"
        print(f"  {marca}: {mod} ({err[:120]})")
    if graves:
        sys.exit(1)
    print("OK: requirements.txt cubre todos los imports del código vivo")


if __name__ == "__main__":
    main()
