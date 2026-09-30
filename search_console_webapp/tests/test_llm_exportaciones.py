"""
Exportaciones de LLM Monitoring (Excel y PDF) fuera de llm_monitoring_routes.py.

En sep-2026 los cuerpos de export_project_excel y export_project_pdf (unas 2.900
líneas) pasaron tal cual a llm_monitoring_export_excel.py y llm_monitoring_export_pdf.py.
La ruta, sus decoradores y la URL siguen en llm_monitoring_routes.py.

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


@pytest.mark.parametrize("modulo, funcion", [
    ("llm_monitoring_export_excel", "exportar_excel"),
    ("llm_monitoring_export_pdf", "exportar_pdf"),
])
def test_todos_los_nombres_globales_de_la_exportacion_existen(flask_app, modulo, funcion):
    """Sin esto, un nombre que faltara al importar solo fallaría con un NameError en plena descarga."""
    import builtins
    import importlib
    import inspect
    import symtable
    mod = importlib.import_module(modulo)
    tabla = symtable.symtable(inspect.getsource(mod), mod.__file__, "exec")

    def globales(t):
        for s in t.get_symbols():
            if s.is_global() or (s.is_free() is False and s.is_referenced() and not s.is_local()
                                 and not s.is_parameter() and t.get_type() == "function"
                                 and not s.is_imported() and not s.is_assigned()):
                yield s.get_name()
        for hijo in t.get_children():
            yield from globales(hijo)

    funcion_t = next(t for t in tabla.get_children() if t.get_name() == funcion)
    faltan = sorted({n for n in globales(funcion_t)
                     if not hasattr(mod, n) and not hasattr(builtins, n)})
    assert faltan == []


def test_sin_sesion_no_se_exporta(flask_app, clean_db):
    r = flask_app.app.test_client().get(f"{BASE}/export/excel", headers={"Accept": "application/json"})
    assert r.status_code == 401
