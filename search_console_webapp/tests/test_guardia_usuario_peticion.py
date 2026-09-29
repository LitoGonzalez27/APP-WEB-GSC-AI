"""
Guardia estática (fase de fiabilidad 2, sep-2026).

get_current_user() devuelve el usuario tal como se leyó al empezar la petición.
Si una función escribe en `users` y después vuelve a pedir el usuario de la
sesión, recibe los datos de antes de escribir. Hoy hay tres casos y los tres
solo usan el id (que no cambia). Este test falla si aparece uno nuevo: en ese
caso, leer con get_user_by_id() o añadirlo aquí explicando por qué es seguro.

Heurística: una función "escribe en users" si su código contiene UPDATE users o
llama (hasta dos niveles, por nombre) a una que lo hace.
"""

import ast
import pathlib

RAIZ = pathlib.Path(__file__).resolve().parent.parent
EXCLUIR = {"tests", "scripts", ".venv", "venv", "node_modules", "__pycache__"}
LECTORAS = {"get_current_user", "get_current_user_strict"}

# función -> por qué es seguro que lea tras escribir
PERMITIDAS = {
    "analyze_ai_overview_route": "solo usa el id para guardar el análisis y registrar la cuota",
    "toggle_user_status": "solo usa el id del admin para el registro de auditoría",
    "update_user_role_route": "solo usa el id del admin para el registro de auditoría",
}


def _ficheros():
    for p in RAIZ.rglob("*.py"):
        if not EXCLUIR.intersection(p.relative_to(RAIZ).parts):
            yield p


def _arboles():
    for p in _ficheros():
        src = p.read_text(encoding="utf-8", errors="replace")
        try:
            yield p, src, ast.parse(src)
        except SyntaxError:
            continue


def _llamadas_propias(funcion):
    """Llamadas del cuerpo de `funcion`, sin entrar en funciones anidadas."""
    pendientes = list(funcion.body)
    while pendientes:
        nodo = pendientes.pop()
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        if isinstance(nodo, ast.Call):
            f = nodo.func
            nombre = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
            if nombre:
                yield nombre, nodo.lineno
        pendientes.extend(ast.iter_child_nodes(nodo))


def _funciones():
    for p, src, arbol in _arboles():
        for nodo in ast.walk(arbol):
            if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
                yield p, src, nodo


def test_ninguna_funcion_nueva_lee_el_usuario_tras_escribir_en_users():
    funciones = list(_funciones())
    escritoras = {
        f.name for _, src, f in funciones
        if "update users" in " ".join((ast.get_source_segment(src, f) or "").lower().split())
    }
    for _ in range(2):
        escritoras |= {f.name for _, _, f in funciones
                       if any(n in escritoras for n, _ in _llamadas_propias(f))}
    assert "consume_user_quota" in escritoras  # la heurística ve las escrituras de cuota

    sospechosas = []
    for p, _, f in funciones:
        llamadas = list(_llamadas_propias(f))
        escrituras = [l for n, l in llamadas if n in escritoras]
        lecturas_tras = [l for n, l in llamadas if n in LECTORAS and any(e < l for e in escrituras)]
        if lecturas_tras and f.name not in PERMITIDAS:
            sospechosas.append(f"{p.relative_to(RAIZ)}:{lecturas_tras[0]} {f.name}")

    assert not sospechosas, (
        "Estas funciones piden el usuario de la sesión después de escribir en users y "
        "recibirán los datos de antes (get_current_user() reutiliza la lectura de la "
        f"petición). Usa get_user_by_id() o justifica el caso en PERMITIDAS: {sospechosas}")


def test_las_permitidas_siguen_existiendo():
    nombres = {f.name for _, _, f in _funciones()}
    assert set(PERMITIDAS) <= nombres, set(PERMITIDAS) - nombres
