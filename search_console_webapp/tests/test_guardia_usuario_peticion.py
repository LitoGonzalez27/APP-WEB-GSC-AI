"""
Guardia estática (fase de fiabilidad 2, sep-2026).

get_current_user() (y get_current_user_strict, is_user_admin, is_user_active,
is_user_ai_enabled) devuelve el usuario tal como se leyó al empezar la
petición. Si una función escribe en `users` y después vuelve a pedirlo, recibe
los datos de antes de escribir. Este test falla si aparece un caso nuevo: en
ese caso, leer con get_user_by_id() o añadirlo a PERMITIDAS explicando por qué
es seguro (hoy todos los casos usan solo el id o el rol, que no cambian).

Heurística (por nombre de función, en todo el código vivo):
- escribe en users: sus cadenas contienen UPDATE/INSERT INTO/DELETE FROM users,
  o llama, a cualquier profundidad, a una función que lo hace;
- lee el usuario de la sesión: llama a una de las funciones de arriba o, a
  cualquier profundidad, a una función que lo hace;
- "después": más abajo en la función, o dentro de un bucle que también escribe;
  el SQL escrito en la propia función cuenta como escritura en su línea.
En las llamadas por atributo (service.analyze_project) las rutas no cuentan como
destino, para no confundir un método con una ruta homónima; en las llamadas por
nombre simple, sí.
"""

import ast
import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parent.parent
EXCLUIR = {"tests", "scripts", ".venv", "venv", "node_modules", "__pycache__", ".claude"}
LECTORAS_BASE = {"get_current_user", "get_current_user_strict", "is_user_admin", "is_user_active", "is_user_ai_enabled"}
SQL_ESCRIBE_USERS = re.compile(r'\b(update|insert\s+into|delete\s+from)\s+(public\.)?"?users\b', re.I)
BUCLES = (ast.For, ast.AsyncFor, ast.While)
ANIDADAS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)

# "fichero:función" -> por qué es seguro que lea tras escribir
PERMITIDAS = {
    "app.py:analyze_ai_overview_route": "solo usa el id para guardar el análisis y registrar la cuota",
    "auth.py:toggle_user_status": "solo usa el id del admin para el registro de auditoría",
    "auth.py:update_user_role_route": "solo usa el id del admin para el registro de auditoría",
    "auth.py:admin_users": "la escritura son usuarios de ejemplo (desactivada en Railway); la plantilla solo usa el id",
    "auth.py:auth_callback": "create_user y los UPDATE van en la rama de registro; la lectura, en la de vincular, y solo usa el id",
    "billing_routes.py:billing_checkout": "escribe stripe_customer_id; después solo mira el rol (is_user_admin)",
    "manual_ai/services/cron_service.py:_process_projects":
        "cron sin petición: run_project_analysis recibe user_id y lee con get_user_by_id",
    "ai_mode_projects/services/cron_service.py:_process_projects":
        "cron sin petición: run_project_analysis recibe user_id y lee con get_user_by_id",
}


def _funciones():
    for p in sorted(RAIZ.rglob("*.py")):
        rel = p.relative_to(RAIZ)
        if EXCLUIR.intersection(rel.parts):
            continue
        try:
            arbol = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for nodo in ast.walk(arbol):
            if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
                yield rel.as_posix(), nodo


def _propios(funcion):
    """Nodos del cuerpo de `funcion` sin entrar en funciones o clases anidadas,
    con la lista de bucles que los contienen."""
    pendientes = [(n, ()) for n in funcion.body]
    while pendientes:
        nodo, bucles = pendientes.pop()
        if isinstance(nodo, ANIDADAS):
            continue
        yield nodo, bucles
        dentro = bucles + (id(nodo),) if isinstance(nodo, BUCLES) else bucles
        pendientes.extend((h, dentro) for h in ast.iter_child_nodes(nodo))


def _analizar():
    datos = []
    for ruta, f in _funciones():
        llamadas, sql = [], []
        for nodo, bucles in _propios(f):
            if isinstance(nodo, ast.Call):
                fn = nodo.func
                nombre = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)
                if nombre:
                    llamadas.append((nombre, nodo.lineno, bucles, isinstance(fn, ast.Attribute)))
            elif isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
                if SQL_ESCRIBE_USERS.search(" ".join(nodo.value.split())):
                    sql.append((nodo.lineno, bucles))
        es_ruta = any("route(" in ast.unparse(d) for d in f.decorator_list)
        datos.append((ruta, f.name, llamadas, sql, es_ruta))
    return datos


def _cierre(datos, semilla):
    """Nombres de las funciones que cumplen la propiedad (directamente o a
    través de otras). Devuelve (todas, sin_rutas): por nombre simple se usa la
    primera; por atributo, la segunda."""
    base = {(nombre, es_ruta) for _, nombre, _, _, es_ruta in datos if nombre in semilla}
    todas = set(semilla) | {n for n, _ in base}
    sin_rutas = set(semilla) | {n for n, es_ruta in base if not es_ruta}
    while True:
        nuevas = [(nombre, es_ruta) for _, nombre, llamadas, _, es_ruta in datos
                  if (nombre not in todas or (not es_ruta and nombre not in sin_rutas))
                  and any(_llama_a(c, todas, sin_rutas) for c in llamadas)]
        if not nuevas:
            return todas, sin_rutas
        for nombre, es_ruta in nuevas:
            todas.add(nombre)
            if not es_ruta:
                sin_rutas.add(nombre)


def _llama_a(llamada, todas, sin_rutas):
    nombre, _linea, _bucles, por_atributo = llamada
    return nombre in (sin_rutas if por_atributo else todas)


def _sospechosas():
    datos = _analizar()
    escritoras = _cierre(datos, {nombre for _, nombre, _, sql, _ in datos if sql})
    lectoras = _cierre(datos, LECTORAS_BASE)
    resultado = {}
    for ruta, nombre, llamadas, sql, _ in datos:
        escrituras = [(l, set(b)) for l, b in sql]
        escrituras += [(c[1], set(c[2])) for c in llamadas if _llama_a(c, *escritoras)]
        for c in llamadas:
            _n, l, b, _a = c
            if _llama_a(c, *lectoras) and any(le < l or (set(b) & be) for le, be in escrituras):
                resultado.setdefault(f"{ruta}:{nombre}", l)
    return resultado, escritoras[0], lectoras[0]


def test_la_heuristica_ve_lo_que_debe():
    _, escritoras, lectoras = _sospechosas()
    assert {"consume_user_quota", "update_user_role", "create_user"} <= escritoras
    assert {"run_project_analysis", "_comprobar_sesion"} <= lectoras


def test_ninguna_funcion_nueva_lee_el_usuario_tras_escribir_en_users():
    sospechosas, _, _ = _sospechosas()
    nuevas = {k: v for k, v in sospechosas.items() if k not in PERMITIDAS}
    assert not nuevas, (
        "Estas funciones piden el usuario de la sesión después de escribir en users y "
        "recibirán los datos de antes (get_current_user() reutiliza la lectura de la "
        f"petición). Usa get_user_by_id() o justifica el caso en PERMITIDAS: {nuevas}")


def test_las_permitidas_siguen_siendo_necesarias():
    sospechosas, _, _ = _sospechosas()
    sobran = set(PERMITIDAS) - set(sospechosas)
    assert not sobran, f"Ya no leen tras escribir; quítalas de PERMITIDAS: {sobran}"
