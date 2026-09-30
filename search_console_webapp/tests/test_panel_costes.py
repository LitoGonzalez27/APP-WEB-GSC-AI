"""
Panel de costes del admin: búsquedas de SerpAPI atribuidas a Clicandseo.

Hasta sep-2026 solo contaba 'serp_api' y 'ai_mode', suponiendo que el middleware
registraba como 'serp_api' las búsquedas de Manual AI y AI Overview. En
producción nunca lo hizo, y el panel mostraba una fracción del gasto real.
Ahora cuentan Manual AI y AI Overview (1 RU = 1 búsqueda), AI Mode, la vista de
SERP y las expansiones de AIO de Manual AI, y la diferencia con el dato oficial
de SerpAPI se muestra como consumo de otros servicios de la misma clave.

Ejecutar:  scripts/run_tests_docker.sh -q tests/test_panel_costes.py
"""

import json
from datetime import date, datetime

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
              "total_searches_left": 14900, "plan_renewal_date": None, "account_status": "Active"}
    monkeypatch.setattr(admin_cost_panel, "get_serpapi_account", lambda force_refresh=False: dict(cuenta))
    monkeypatch.delenv("SERPAPI_COST_PER_SEARCH_USD", raising=False)
    yield sql, paid, admin
    conn.close()


def _evento(sql, user_id, source, ru):
    sql("INSERT INTO quota_usage_events (user_id, ru_consumed, source, timestamp) VALUES (%s, %s, %s, now())",
        (user_id, ru, source))


def _resultado_manual_ai(sql, user_id, intentos, refetches):
    proyecto = sql("INSERT INTO manual_ai_projects (user_id, name, domain) VALUES (%s, 'P', 'example.com') RETURNING id",
                   (user_id,))[0][0]
    keyword = sql("INSERT INTO manual_ai_keywords (project_id, keyword) VALUES (%s, 'kw') RETURNING id", (proyecto,))[0][0]
    datos = {"aio_expansion": {"status": "expanded", "attempts": intentos, "refetches": refetches}}
    sql("""INSERT INTO manual_ai_results (project_id, keyword_id, analysis_date, keyword, domain, ai_analysis_data)
           VALUES (%s, %s, %s, 'kw', 'example.com', %s)""", (proyecto, keyword, date.today(), json.dumps(datos)))


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
    # Oficial 100 - atribuido 60 = 40 de otros servicios que usan la misma clave
    assert serp["other_consumers_month"] == 40


def test_sin_dato_oficial_no_calcula_otros_consumidores(db, monkeypatch):
    import admin_cost_panel
    monkeypatch.setattr(admin_cost_panel, "get_serpapi_account", lambda force_refresh=False: None)
    assert admin_cost_panel.get_costs_dashboard()["serp"]["other_consumers_month"] is None
