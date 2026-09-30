"""
Exportaciones de LLM Monitoring (Excel y PDF) fuera de llm_monitoring_routes.py.

En sep-2026 los cuerpos de export_project_excel y export_project_pdf (unas 2.900
líneas) pasaron tal cual a llm_monitoring_export_excel.py y llm_monitoring_export_pdf.py.
La ruta y la URL siguen en llm_monitoring_routes.py; el blueprint y los decoradores viven
en llm_monitoring_base.py y los helpers de informes en llm_monitoring_informes.py.

La equivalencia exacta con el código anterior se comprobó contra los proyectos 11 y 12
de staging, en solo lectura: 22 combinaciones de filtros, todas las celdas de todas las
hojas y el texto de cada página del PDF, idénticos. Estos tests vigilan en el CI que:
- las rutas siguen llamando a los módulos nuevos;
- esos módulos funcionan de punta a punta sobre un proyecto sembrado;
- el acceso sigue protegido igual.

Ejecutar:  scripts/run_tests_docker.sh -q tests/test_llm_exportaciones.py
"""

import io
from datetime import date, datetime, timedelta

import psycopg2
import pytest

from tests.conftest import seed_users

PROYECTO = 4343
BASE = f"/api/llm-monitoring/projects/{PROYECTO}"


def _sql(url, consulta, params=()):
    conn = psycopg2.connect(url, connect_timeout=5)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(consulta, params)
    finally:
        conn.close()


def _login(client, user):
    with client.session_transaction() as sess:
        sess["user_id"] = user["id"]
        sess["user_email"] = user["email"]
        sess["user_name"] = user["name"]
        sess["last_activity"] = datetime.now().isoformat()


@pytest.fixture
def ent(flask_app, clean_db):
    user, admin, paid = seed_users()
    _sql(clean_db, "INSERT INTO llm_monitoring_projects (id, user_id, name, brand_name, industry) "
                   "VALUES (%s, %s, 'Proyecto export', 'Marca', 'SEO')", (PROYECTO, paid["id"]))
    for dias, proveedor in ((1, 'openai'), (2, 'google'), (3, 'openai')):
        _sql(clean_db, """INSERT INTO llm_monitoring_results
                              (project_id, analysis_date, llm_provider, query_text, brand_name, units_consumed)
                          VALUES (%s, %s, %s, 'mejor agencia seo', 'Marca', 1)""",
             (PROYECTO, date.today() - timedelta(days=dias), proveedor))
    client = flask_app.app.test_client()
    _login(client, paid)
    return client, user, paid


def test_excel_de_punta_a_punta(ent):
    import openpyxl
    client, _, _ = ent
    r = client.get(f"{BASE}/export/excel?days=30")
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    assert "spreadsheet" in r.headers["Content-Type"]
    assert r.headers["Content-Disposition"].startswith("attachment; filename=")
    libro = openpyxl.load_workbook(io.BytesIO(r.data))
    assert libro.sheetnames[:5] == ["Project Summary", "Share of Voice", "LLM Comparison",
                                    "Daily Metrics", "Prompts & Queries"]
    resumen = [str(c) for fila in libro["Project Summary"].iter_rows(values_only=True) for c in fila if c]
    assert "Project: Proyecto export" in resumen
    assert "Marca" in resumen


def test_pdf_de_punta_a_punta(ent):
    client, _, _ = ent
    r = client.get(f"{BASE}/export/pdf?days=30&metric=weighted")
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    assert r.headers["Content-Type"] == "application/pdf"
    assert r.data[:5] == b"%PDF-"


@pytest.mark.parametrize("tipo, modulo, funcion", [
    ("excel", "llm_monitoring_export_excel", "exportar_excel"),
    ("pdf", "llm_monitoring_export_pdf", "exportar_pdf"),
])
def test_la_ruta_llama_al_modulo_nuevo(ent, monkeypatch, tipo, modulo, funcion):
    import importlib
    client, _, _ = ent
    llamadas = []
    monkeypatch.setattr(importlib.import_module(modulo), funcion,
                        lambda project_id: (llamadas.append(project_id) or "ok", 200))
    r = client.get(f"{BASE}/export/{tipo}")
    assert r.status_code == 200 and r.get_data(as_text=True) == "ok"
    assert llamadas == [PROYECTO]


@pytest.mark.parametrize("tipo", ["excel", "pdf"])
def test_el_proyecto_de_otro_usuario_no_se_exporta(ent, tipo):
    """El admin pasa el filtro de plan (el gratuito se queda en un 402 antes de llegar)
    y no es el dueño: es validate_project_ownership quien tiene que cortar."""
    client, _, _ = ent
    from tests.conftest import seed_users  # noqa: F401  (usuarios ya sembrados en ent)
    import database
    conn = database.get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, email, name FROM users WHERE role = 'admin' ORDER BY id LIMIT 1")
        admin = dict(cur.fetchone())
    finally:
        conn.close()
    _login(client, admin)
    r = client.get(f"{BASE}/export/{tipo}", headers={"Accept": "application/json"})
    assert r.status_code == 403


def test_el_gratuito_se_queda_en_el_filtro_de_plan(ent):
    client, user, _ = ent
    _login(client, user)
    r = client.get(f"{BASE}/export/excel", headers={"Accept": "application/json"})
    assert r.status_code == 402


@pytest.mark.parametrize("modulo", ["llm_monitoring_routes", "llm_monitoring_informes", "llm_monitoring_base",
                                    "llm_monitoring_rutas_modelos",
                                    "llm_monitoring_export_excel", "llm_monitoring_export_pdf"])
def test_ningun_nombre_global_falta_en_los_modulos_de_llm(flask_app, modulo):
    """Tras partir llm_monitoring_routes.py (sep-2026): todo nombre global que usa cualquier
    función de estos módulos existe en su módulo. Sin esto, un helper que se quedara sin
    importar solo fallaría con un NameError en plena petición."""
    import builtins
    import importlib
    import inspect
    import symtable
    mod = importlib.import_module(modulo)

    def globales(tabla):
        if tabla.get_type() == "function":
            for s in tabla.get_symbols():
                if s.is_global() and s.is_referenced():
                    yield tabla.get_name(), s.get_name()
        for hija in tabla.get_children():
            yield from globales(hija)

    raiz = symtable.symtable(inspect.getsource(mod), mod.__file__, "exec")
    faltan = sorted({f"{f}: {n}" for f, n in globales(raiz)
                     if not hasattr(mod, n) and not hasattr(builtins, n)})
    assert faltan == []


def test_sin_sesion_no_se_exporta(flask_app, clean_db):
    r = flask_app.app.test_client().get(f"{BASE}/export/excel", headers={"Accept": "application/json"})
    assert r.status_code == 401


def test_las_rutas_exponen_los_mismos_helpers_que_informes(flask_app):
    """llm_monitoring_routes vuelve a exponer los helpers de informes (sep-2026): mismo objeto,
    no una copia; y nada de informes vuelve a definirse en las rutas."""
    import ast
    import inspect
    import llm_monitoring_informes as informes
    import llm_monitoring_routes as rutas
    definidos = [n.name if isinstance(n, (ast.FunctionDef, ast.ClassDef)) else n.targets[0].id
                 for n in ast.parse(inspect.getsource(informes)).body
                 if isinstance(n, (ast.FunctionDef, ast.ClassDef))
                 or (isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name))]
    definidos = [n for n in definidos if n != "logger"]
    assert len(definidos) == 27
    assert [n for n in definidos if getattr(rutas, n, None) is not getattr(informes, n)] == []
    en_rutas = {n.name for n in ast.parse(inspect.getsource(rutas)).body
                if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    assert en_rutas & set(definidos) == set()


def test_las_rutas_exponen_el_blueprint_y_los_decoradores_de_la_base(flask_app):
    """El blueprint, el control de acceso y los decoradores viven en llm_monitoring_base
    (sep-2026): las rutas los exponen como el mismo objeto y el blueprint registrado en la
    app es ese mismo, con enforce_llm_access como único control previo."""
    import llm_monitoring_base as base
    import llm_monitoring_routes as rutas
    nombres = ["llm_monitoring_bp", "_INITIAL_ANALYSIS_RUNNING", "_INITIAL_ANALYSIS_RUNNING_LOCK",
               "_safe_notify_email", "_is_initial_analysis_running", "_mark_initial_analysis_running",
               "_clear_initial_analysis_running", "enforce_llm_access", "validate_project_ownership",
               "_ensure_cron_token_or_admin"]
    assert [n for n in nombres if getattr(rutas, n) is not getattr(base, n)] == []
    app = flask_app.app
    assert app.blueprints["llm_monitoring"] is base.llm_monitoring_bp
    assert app.before_request_funcs.get("llm_monitoring") == [base.enforce_llm_access]
