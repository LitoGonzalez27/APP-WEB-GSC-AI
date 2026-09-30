"""
Cobro de las búsquedas de SERP (Carlos, 30-sep-2026): 1 RU por búsqueda y el
plan Free bloqueado.

Las rutas de los botones de SERP del panel de Search Console (/api/serp,
/api/serp/position, /api/serp/screenshot) son las únicas que cobran. Antes
dependía de ENFORCE_QUOTAS: apagado (producción) no cobraban nada y las usaba
también el plan Free; encendido (staging), los análisis de AI Overview y Manual
AI cobraban dos veces.

Contra el Postgres desechable y con la llamada a SerpAPI sustituida por un doble.
Ejecutar:  scripts/run_tests_docker.sh -q tests/test_cobro_serp.py
"""

from datetime import datetime
from types import SimpleNamespace

import psycopg2
import psycopg2.extras
import pytest

from tests.conftest import seed_users

JSON = {"Accept": "application/json"}
CONSULTA = "keyword=zapatillas+running&site_url=sc-domain:example.com&country=esp"


def _login(client, user):
    with client.session_transaction() as sess:
        sess["user_id"] = user["id"]
        sess["user_email"] = user["email"]
        sess["user_name"] = user["name"]
        sess["last_activity"] = datetime.now().isoformat()


@pytest.fixture
def ent(flask_app, clean_db, monkeypatch):
    import quota_middleware

    user, admin, paid = seed_users()  # 1 Free, 2 admin (plan Free), 3 de pago
    llamadas = []

    def serpapi_falso(params, call_type):
        llamadas.append((dict(params), call_type))
        return True, {"organic_results": [], "ads": [], "html": ""}

    monkeypatch.setattr(quota_middleware, "_execute_serp_call", serpapi_falso)
    from services import serp_service
    quota_middleware.CALL_CACHE.clear()
    serp_service.SCREENSHOT_CACHE.clear()
    conn = psycopg2.connect(clean_db, cursor_factory=psycopg2.extras.RealDictCursor, connect_timeout=5)
    conn.autocommit = True

    def sql(consulta, params=()):
        with conn.cursor() as cur:
            cur.execute(consulta, params)
            return cur.fetchall() if cur.description else None

    yield SimpleNamespace(client=flask_app.app.test_client(), user=user, admin=admin, paid=paid,
                          llamadas=llamadas, sql=sql)
    quota_middleware.CALL_CACHE.clear()
    serp_service.SCREENSHOT_CACHE.clear()
    conn.close()


def _usado(ent, user):
    return ent.sql("SELECT quota_used FROM users WHERE id = %s", (user["id"],))[0]["quota_used"]


def _eventos(ent):
    return ent.sql("SELECT user_id, ru_consumed, source, metadata FROM quota_usage_events ORDER BY id")


@pytest.mark.parametrize("ruta", ["/api/serp", "/api/serp/position", "/api/serp/screenshot"])
def test_plan_free_recibe_paywall_sin_llamar_a_serpapi(ent, ruta):
    _login(ent.client, ent.user)

    r = ent.client.get(f"{ruta}?{CONSULTA}", headers=JSON)

    assert r.status_code == 402
    cuerpo = r.get_json()
    assert (cuerpo["error"], cuerpo["paywall"], cuerpo["quota_blocked"]) == ("paywall", True, True)
    assert cuerpo["upgrade_options"] == ["basic", "premium", "business"]
    assert ent.llamadas == [] and _eventos(ent) == []


def test_pago_cobra_1_ru_y_la_repeticion_no(ent):
    _login(ent.client, ent.paid)
    antes = _usado(ent, ent.paid)

    assert ent.client.get(f"/api/serp/position?{CONSULTA}", headers=JSON).status_code == 200
    assert ent.client.get(f"/api/serp?{CONSULTA}", headers=JSON).status_code == 200  # misma búsqueda

    assert len(ent.llamadas) == 2
    assert _usado(ent, ent.paid) == antes + 1
    eventos = _eventos(ent)
    assert [(e["user_id"], e["ru_consumed"], e["source"], e["metadata"]["admin"]) for e in eventos] == [
        (ent.paid["id"], 1, "serp_api", False)]


def test_pago_sin_cuota_recibe_429_de_cuota(ent):
    ent.sql("UPDATE users SET quota_used = quota_limit WHERE id = %s", (ent.paid["id"],))
    _login(ent.client, ent.paid)

    r = ent.client.get(f"/api/serp?{CONSULTA}", headers=JSON)

    assert r.status_code == 429
    cuerpo = r.get_json()
    assert cuerpo["quota_blocked"] is True and cuerpo["paywall"] is False
    assert ent.llamadas == []


def test_captura_sin_cuota_recibe_429_en_json(ent):
    ent.sql("UPDATE users SET quota_used = quota_limit WHERE id = %s", (ent.paid["id"],))
    _login(ent.client, ent.paid)

    r = ent.client.get(f"/api/serp/screenshot?{CONSULTA}")

    assert r.status_code == 429
    cuerpo = r.get_json()
    assert (cuerpo["quota_blocked"], cuerpo["paywall"]) == (True, False)
    assert cuerpo["quota_info"]["plan"]
    assert ent.llamadas == []


def test_plan_free_no_ve_una_captura_ya_generada(ent):
    # La caché de capturas no distingue usuario: el paywall va antes que ella.
    from flask import Response
    from services import serp_service
    _login(ent.client, ent.user)
    # Cualquier entrada de la caché serviría a este usuario si el paywall fuera después.
    original = serp_service._get_cached_screenshot
    serp_service._get_cached_screenshot = lambda *_: Response(b"png", mimetype="image/png")
    try:
        r = ent.client.get(f"/api/serp/screenshot?{CONSULTA}")
    finally:
        serp_service._get_cached_screenshot = original

    assert r.status_code == 402
    assert r.get_json()["paywall"] is True


def test_admin_con_plan_free_busca_sin_descontar(ent):
    _login(ent.client, ent.admin)

    r = ent.client.get(f"/api/serp?{CONSULTA}", headers=JSON)

    assert r.status_code == 200
    assert _usado(ent, ent.admin) == 0
    assert [(e["user_id"], e["metadata"]["admin"]) for e in _eventos(ent)] == [(ent.admin["id"], True)]


def test_la_busqueda_de_un_analisis_no_cobra(ent, flask_app):
    # get_serp_json sin cobrar: la usan AI Overview y Manual AI, que descuentan lo suyo.
    from flask import session
    from services.serp_service import get_serp_json

    with flask_app.app.test_request_context("/"):
        session["user_id"] = ent.paid["id"]
        datos = get_serp_json({"q": "zapatillas", "gl": "es", "api_key": "x"})

    assert "error" not in datos
    assert len(ent.llamadas) == 1 and _eventos(ent) == []


def test_solo_las_tres_rutas_de_serp_cobran():
    # Guardia: cualquier otra llamada que pase cobrar=True (un análisis, un cron)
    # volvería a cobrar dos veces lo que ya descuenta su módulo.
    import ast
    import pathlib

    raiz = pathlib.Path(__file__).resolve().parent.parent
    encontradas = set()
    for p in raiz.rglob("*.py"):
        if {"tests", "scripts", ".venv", "venv"}.intersection(p.relative_to(raiz).parts):
            continue
        arbol = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        for f in ast.walk(arbol):
            if not isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for n in ast.walk(f):
                if isinstance(n, ast.Call) and any(
                        k.arg == "cobrar" and not (isinstance(k.value, ast.Constant) and k.value.value is False)
                        and not (isinstance(k.value, ast.Name) and k.value.id == "cobrar")
                        for k in n.keywords):
                    encontradas.add(f"{p.relative_to(raiz).as_posix()}:{f.name}")
    assert encontradas == {
        "app.py:get_serp_raw_json", "app.py:get_serp_position", "app.py:get_serp_screenshot_route"}, encontradas
