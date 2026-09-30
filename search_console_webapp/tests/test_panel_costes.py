"""
Panel de costes del admin: búsquedas de SerpAPI atribuidas a Clicandseo.

Hasta sep-2026 solo contaba 'serp_api' y 'ai_mode', suponiendo que el middleware
registraba como 'serp_api' las búsquedas de Manual AI y AI Overview. En
producción nunca lo hizo, y el panel mostraba una fracción del gasto real.
Ahora cuentan Manual AI y AI Overview (1 RU = 1 búsqueda), AI Mode, la vista de
SERP y las expansiones de AIO de Manual AI, y la diferencia con el dato oficial
de SerpAPI se muestra como consumo de staging y otros servicios de la misma clave.
El dato oficial cuenta desde la renovación del plan (no desde el día 1), así que
lo nuestro se cuenta en ese mismo ciclo.

Ejecutar:  scripts/run_tests_docker.sh -q tests/test_panel_costes.py
"""

import json
from datetime import date, datetime, timedelta

import psycopg2
import pytest

from tests.conftest import seed_users


@pytest.fixture
def db(flask_app, clean_db, monkeypatch):
    import admin_cost_panel
    user, admin, paid = seed_users()
    conn = psycopg2.connect(clean_db, connect_timeout=5)
    conn.autocommit = True

    def sql(consulta, params=()):
        with conn.cursor() as cur:
            cur.execute(consulta, params)
            return cur.fetchall() if cur.description else None

    cuenta = {"plan_name": "Production Plan", "plan_monthly_price": 150.0, "searches_per_month": 15000,
              "this_month_usage": 100, "plan_searches_left": 14900, "extra_credits": 0,
              "total_searches_left": 14900, "account_status": "Active",
              # ciclo que empieza como muy tarde hoy: los eventos de hoy caen dentro
              "plan_renewal_date": (date.today() + timedelta(days=1)).isoformat()}
    monkeypatch.setattr(admin_cost_panel, "get_serpapi_account", lambda force_refresh=False: dict(cuenta))
    monkeypatch.delenv("SERPAPI_COST_PER_SEARCH_USD", raising=False)
    sql.cuenta = cuenta
    yield sql, paid, admin
    conn.close()


def _evento(sql, user_id, source, ru, cuando=None):
    sql("INSERT INTO quota_usage_events (user_id, ru_consumed, source, timestamp) "
        "VALUES (%s, %s, %s, COALESCE(%s, now()))", (user_id, ru, source, cuando))


def _resultado_manual_ai(sql, user_id, intentos, refetches, dia=None):
    proyecto = sql("INSERT INTO manual_ai_projects (user_id, name, domain) "
                   "VALUES (%s, 'P' || gen_random_uuid(), 'example.com') RETURNING id", (user_id,))[0][0]
    keyword = sql("INSERT INTO manual_ai_keywords (project_id, keyword) VALUES (%s, 'kw') RETURNING id", (proyecto,))[0][0]
    datos = {"aio_expansion": {"status": "expanded", "attempts": intentos, "refetches": refetches}}
    sql("""INSERT INTO manual_ai_results (project_id, keyword_id, analysis_date, keyword, domain, ai_analysis_data)
           VALUES (%s, %s, %s, 'kw', 'example.com', %s)""", (proyecto, keyword, dia or date.today(), json.dumps(datos)))


def test_cuenta_todas_las_busquedas_de_clicandseo(db):
    import admin_cost_panel
    sql, paid, admin = db
    _evento(sql, paid["id"], "manual_ai", 40)    # antes no contaba
    _evento(sql, paid["id"], "ai_overview", 10)  # antes no contaba
    _evento(sql, paid["id"], "ai_mode", 5)
    _evento(sql, paid["id"], "serp_api", 2)      # vista de SERP
    _resultado_manual_ai(sql, admin["id"], intentos=2, refetches=1)  # 3 búsquedas extra

    datos = admin_cost_panel.get_costs_dashboard()

    serp = datos["serp"]
    assert serp["totals"]["searches_month"] == 40 + 10 + 5 + 2 + 3
    assert serp["totals"]["expansions_month"] == 3
    por_usuario = {u["user_id"]: u["serp_searches"] for u in datos["per_user"]}
    assert por_usuario == {paid["id"]: 57, admin["id"]: 3}
    # 150 $ / 15.000 búsquedas = 0,01 $ por búsqueda
    assert serp["cost_per_search"] == pytest.approx(0.01)
    assert datos["summary"]["serp_cost_month_usd"] == pytest.approx(0.60)
    # Oficial 100 - atribuido 60 = 40 de staging y otros servicios que usan la misma clave
    assert serp["clicandseo_cycle"] == 60
    assert serp["other_consumers_cycle"] == 40
    # Las expansiones salen como fila propia en la atribución y cuentan como facturables
    filas = {f["source"]: f for f in serp["by_source_month"]}
    assert filas[admin_cost_panel.FUENTE_EXPANSIONES] == {
        "source": admin_cost_panel.FUENTE_EXPANSIONES, "events": 1, "ru": 3}
    assert admin_cost_panel.FUENTE_EXPANSIONES in serp["billable_sources"]


def test_otros_servicios_se_cuentan_en_el_ciclo_de_serpapi(db):
    """El dato oficial empieza en la renovación: lo de antes del ciclo no se resta."""
    import admin_cost_panel
    sql, paid, admin = db
    sql.cuenta["plan_renewal_date"] = (date.today() + timedelta(days=20)).isoformat()
    ciclo = admin_cost_panel.inicio_ciclo_serpapi(sql.cuenta)
    assert ciclo < date.today()
    antes = datetime.combine(ciclo - timedelta(days=1), datetime.min.time()).replace(hour=12)
    _evento(sql, paid["id"], "manual_ai", 500, cuando=antes)                      # ciclo anterior
    _evento(sql, paid["id"], "manual_ai", 30)                                     # este ciclo
    _resultado_manual_ai(sql, admin["id"], 4, 0, dia=ciclo - timedelta(days=1))  # ciclo anterior
    _resultado_manual_ai(sql, admin["id"], 2, 0, dia=ciclo)                       # este ciclo

    serp = admin_cost_panel.get_costs_dashboard()["serp"]

    assert serp["cycle_start"] == ciclo.isoformat()
    assert serp["clicandseo_cycle"] == 32
    assert serp["other_consumers_cycle"] == 100 - 32


def test_desfase_del_dia_de_renovacion_no_es_una_alarma(db):
    """Lo gastado el día de renovar antes de la hora de SerpAPI entra en nuestro ciclo y no en el suyo."""
    import admin_cost_panel
    sql, paid, _ = db
    sql.cuenta["plan_renewal_date"] = (date.today() + timedelta(days=20)).isoformat()
    ciclo = admin_cost_panel.inicio_ciclo_serpapi(sql.cuenta)
    primer_dia = datetime.combine(ciclo, datetime.min.time()).replace(hour=3)
    _evento(sql, paid["id"], "manual_ai", 120, cuando=primer_dia)   # cron antes de renovar
    serp = admin_cost_panel.get_costs_dashboard()["serp"]
    assert serp["other_consumers_cycle"] == 100 - 120
    assert serp["cycle_first_day_searches"] == 120   # la plantilla lo muestra como margen


def test_si_lo_atribuido_supera_al_oficial_se_ve_en_negativo(db):
    """Antes se recortaba a 0 y escondía un doble conteo."""
    import admin_cost_panel
    sql, paid, _ = db
    _evento(sql, paid["id"], "manual_ai", 130)
    assert admin_cost_panel.get_costs_dashboard()["serp"]["other_consumers_cycle"] == -30


def test_las_expansiones_antiguas_no_se_leen(db):
    """manual_ai_results pesa 1,7 GB en producción: solo se leen los dos últimos meses."""
    import admin_cost_panel
    sql, _, admin = db
    _resultado_manual_ai(sql, admin["id"], 7, 0, dia=date.today() - timedelta(days=75))
    totales = admin_cost_panel.get_costs_dashboard()["serp"]["totals"]
    assert totales["searches_prev_month"] == 0 and totales["searches_month"] == 0


def test_sin_dato_oficial_no_calcula_otros_consumidores(db, monkeypatch):
    import admin_cost_panel
    monkeypatch.setattr(admin_cost_panel, "get_serpapi_account", lambda force_refresh=False: None)
    serp = admin_cost_panel.get_costs_dashboard()["serp"]
    assert serp["other_consumers_cycle"] is None and serp["clicandseo_cycle"] is None


@pytest.mark.parametrize("renovacion, inicio", [
    ("2026-10-30", date(2026, 9, 30)),
    ("2026-03-31", date(2026, 2, 28)),
    ("2028-03-31", date(2028, 2, 29)),
    ("2026-05-31", date(2026, 4, 30)),
    ("2026-01-15", date(2025, 12, 15)),
    ("2026-12-15", date(2026, 11, 15)),
])
def test_inicio_del_ciclo_de_serpapi(renovacion, inicio):
    import admin_cost_panel
    assert admin_cost_panel.inicio_ciclo_serpapi({"plan_renewal_date": renovacion}, hoy=inicio) == inicio


@pytest.mark.parametrize("renovacion", [None, "", "basura", "2026-02-30",
                                        "2026-09-01",    # renovación ya pasada: dato de cuenta viejo
                                        "2026-09-29",    # ídem, solo un día
                                        "2026-12-30"])   # a más de un mes: el ciclo aún no ha empezado
def test_ciclo_de_serpapi_sin_sentido_no_se_usa(renovacion):
    import admin_cost_panel
    assert admin_cost_panel.inicio_ciclo_serpapi({"plan_renewal_date": renovacion}, hoy=date(2026, 9, 30)) is None


def test_el_dia_de_la_renovacion_no_da_cifra_de_otros(db):
    """Contamos desde las 00:00 y SerpAPI desde la hora de renovar: saldría negativo sin serlo."""
    import admin_cost_panel
    sql, paid, _ = db
    hoy = date.today()
    renovacion = next((hoy + timedelta(days=d) for d in range(26, 33)
                       if admin_cost_panel.inicio_ciclo_serpapi({"plan_renewal_date": (hoy + timedelta(days=d)).isoformat()}) == hoy),
                      None)
    if renovacion is None:
        pytest.skip("hoy no hay fecha de renovación cuyo ciclo empiece hoy (fin de mes corto)")
    sql.cuenta["plan_renewal_date"] = renovacion.isoformat()
    sql.cuenta["this_month_usage"] = 1
    _evento(sql, paid["id"], "manual_ai", 300)   # cron de esta mañana, antes de renovar
    serp = admin_cost_panel.get_costs_dashboard()["serp"]
    assert serp["cycle_renewal_day"] is True and serp["other_consumers_cycle"] is None
    assert serp["clicandseo_cycle"] == 300


def test_toda_consulta_sobre_manual_ai_results_filtra_por_fecha():
    """1,7 GB en producción: sin filtro por analysis_date (con índice) el panel recorre todo el histórico."""
    import ast
    import pathlib
    import re
    fuente = pathlib.Path(__file__).resolve().parent.parent.joinpath("admin_cost_panel.py").read_text()
    literales = [ast.get_source_segment(fuente, n) or "" for n in ast.walk(ast.parse(fuente))
                 if isinstance(n, (ast.JoinedStr, ast.Constant))]
    # solo literales completos (no los trozos de dentro de un f-string)
    consultas = [t for t in literales if "FROM manual_ai_results" in t and (t[:1] in "\"'" or t[:2] in ('f"', "f'"))]
    assert len(consultas) == 3
    for consulta in consultas:
        # en el WHERE de la propia consulta (un FILTER de fuera no evita leer la tabla entera)
        assert re.search(r"FROM manual_ai_results r\s+(?:JOIN[^\n]*\s+)?WHERE\s+r\.analysis_date\s*>=", consulta), consulta


def test_si_falla_la_cuenta_no_escribe_la_clave_en_el_log(monkeypatch, caplog):
    """El mensaje de requests lleva la URL con ?api_key=: antes acababa en los logs."""
    import requests
    import admin_cost_panel
    monkeypatch.setenv("SERPAPI_KEY", "clave-secreta-de-prueba")
    respuesta = requests.Response()
    respuesta.status_code = 401

    def falla(*a, **k):
        raise requests.HTTPError("401 Client Error: Unauthorized for url: "
                                 "https://serpapi.com/account?api_key=clave-secreta-de-prueba", response=respuesta)
    monkeypatch.setattr(admin_cost_panel.requests, "get", falla)
    monkeypatch.setitem(admin_cost_panel._serpapi_account_cache, "data", {"total_searches_left": 5})

    with caplog.at_level("WARNING"):
        viejo = admin_cost_panel.get_serpapi_account(force_refresh=True)
        estricto = admin_cost_panel.get_serpapi_account(force_refresh=True, dato_viejo_si_falla=False)

    assert viejo == {"total_searches_left": 5} and estricto is None
    assert "clave-secreta-de-prueba" not in caplog.text and "HTTP 401" in caplog.text
