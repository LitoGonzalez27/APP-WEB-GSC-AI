"""
Fase de fiabilidad (sep-2026), sesión: un fallo de la base de datos no cierra la
sesión del usuario.

Prueban los decoradores reales (auth_required, auth_required_no_activity_update)
y /auth/status contra el Postgres desechable de Docker, con fallos provocados de
verdad donde se puede (consulta cancelada por statement_timeout, tabla
inexistente). Contrato común (auth._comprobar_sesion):

- Fallo transitorio de la BD: 503 database_unavailable + retry, sesión intacta.
- Fallo interno: 500 internal_error, sesión intacta.
- Usuario que ya no existe: sesión cerrada, 401 user_not_found (JSON) o login.
- Expiración, suspensión y permisos: como antes.

Antes: auth_required conservaba la sesión de un usuario borrado para siempre;
el keepalive (cada 5 minutos) y /auth/status cerraban la sesión ante cualquier
fallo de la BD.

Ejecutar:  scripts/run_tests_docker.sh -q tests/test_fiabilidad_sesion.py
"""

from datetime import datetime, timedelta
from types import SimpleNamespace

import psycopg2
import pytest

from tests.conftest import seed_users

JSON = {"Accept": "application/json"}
HTML = {"Accept": "text/html"}

SQL_TRANSITORIO = "SET LOCAL statement_timeout = '50ms'; SELECT pg_sleep(0.5), u.* FROM users u WHERE u.id = %s"
SQL_ROTO = "SELECT * FROM tabla_que_no_existe WHERE id = %s"


def _login(client, user, ultima_actividad=None):
    with client.session_transaction() as sess:
        sess["user_id"] = user["id"]
        sess["user_email"] = user["email"]
        sess["user_name"] = user["name"]
        sess["last_activity"] = (ultima_actividad or datetime.now()).isoformat()


def _sesion(client):
    with client.session_transaction() as sess:
        return dict(sess)


def _sql(url, sql, params=()):
    conn = psycopg2.connect(url, connect_timeout=5)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(sql, params)
    finally:
        conn.close()


def _conexiones_prestadas():
    import database
    return 0 if database._pool is None else len(database._pool._used)


@pytest.fixture
def ent(flask_app, clean_db):
    import database

    user, admin, paid = seed_users()
    client = flask_app.app.test_client()
    _login(client, user)
    prestadas = _conexiones_prestadas()
    yield SimpleNamespace(client=client, db=clean_db, user=user, admin=admin, paid=paid, database=database)
    assert _conexiones_prestadas() == prestadas


def _bd_caida(monkeypatch, ent):
    monkeypatch.setattr(ent.database, "get_db_connection", lambda: None)


# ===========================================================================
# A. auth_required en una API JSON (/auth/user)
# ===========================================================================

def test_api_normal_200(ent):
    r = ent.client.get("/auth/user", headers=JSON)
    assert r.status_code == 200
    assert r.get_json()["id"] == ent.user["id"]


def test_api_bd_caida_503_sin_cerrar_la_sesion(ent, monkeypatch):
    _bd_caida(monkeypatch, ent)

    r = ent.client.get("/auth/user", headers=JSON)

    assert r.status_code == 503
    cuerpo = r.get_json()
    assert (cuerpo["code"], cuerpo["retry"]) == ("database_unavailable", True)
    assert cuerpo["request_id"]
    assert "auth_required" not in cuerpo  # el interceptor del frontend no lo toma como sesión caducada
    assert _sesion(ent.client)["user_id"] == ent.user["id"]


def test_api_consulta_cancelada_de_verdad_503(ent, monkeypatch):
    monkeypatch.setattr(ent.database, "_SQL_USUARIO_POR_ID", SQL_TRANSITORIO)

    r = ent.client.get("/auth/user", headers=JSON)

    assert r.status_code == 503
    assert _sesion(ent.client)["user_id"] == ent.user["id"]


def test_api_error_sql_500_sin_cerrar_la_sesion(ent, monkeypatch):
    monkeypatch.setattr(ent.database, "_SQL_USUARIO_POR_ID", SQL_ROTO)

    r = ent.client.get("/auth/user", headers=JSON)

    assert r.status_code == 500
    assert r.get_json()["code"] == "internal_error"
    assert "tabla_que_no_existe" not in r.get_data(as_text=True)
    assert _sesion(ent.client)["user_id"] == ent.user["id"]


def test_api_usuario_borrado_cierra_la_sesion(ent):
    # CAMBIADO (fase de fiabilidad): antes auth_required conservaba la sesión de
    # un usuario borrado y respondía 503 "reintenta" indefinidamente.
    with ent.client.session_transaction() as sess:
        sess["user_id"] = 999999

    r = ent.client.get("/auth/user", headers=JSON)

    assert r.status_code == 401
    cuerpo = r.get_json()
    assert (cuerpo["code"], cuerpo["auth_required"]) == ("user_not_found", True)
    assert "user_id" not in _sesion(ent.client)


def test_api_cuenta_suspendida_403(ent):
    _sql(ent.db, "UPDATE users SET is_active = false WHERE id = %s", (ent.user["id"],))

    r = ent.client.get("/auth/user", headers=JSON)

    assert r.status_code == 403
    assert r.get_json()["account_suspended"] is True


def test_api_sesion_expirada_401_y_se_cierra(ent):
    _login(ent.client, ent.user, ultima_actividad=datetime.now() - timedelta(hours=3))

    r = ent.client.get("/auth/user", headers=JSON)

    assert r.status_code == 401
    assert r.get_json()["session_expired"] is True
    assert "user_id" not in _sesion(ent.client)


def test_api_tras_una_caida_la_misma_sesion_vuelve_a_funcionar(ent, monkeypatch):
    with monkeypatch.context() as m:
        _bd_caida(m, ent)
        assert ent.client.get("/auth/user", headers=JSON).status_code == 503

    assert ent.client.get("/auth/user", headers=JSON).status_code == 200


# ===========================================================================
# B. auth_required en una página HTML (/profile)
# ===========================================================================

def test_pagina_bd_caida_503_con_reintentar_sin_mandar_al_login(ent, monkeypatch):
    # CAMBIADO: antes redirigía a /login?auth_error=user_lookup_failed.
    _bd_caida(monkeypatch, ent)

    r = ent.client.get("/profile", headers=HTML)

    assert r.status_code == 503
    assert r.mimetype == "text/html"
    assert "Reintentar" in r.get_data(as_text=True)
    assert _sesion(ent.client)["user_id"] == ent.user["id"]


def test_pagina_usuario_borrado_va_al_login_y_cierra_la_sesion(ent):
    with ent.client.session_transaction() as sess:
        sess["user_id"] = 999999

    r = ent.client.get("/profile", headers=HTML)

    assert r.status_code == 302
    assert r.headers["Location"].endswith("/login?user_not_found=true")
    assert "user_id" not in _sesion(ent.client)


def test_checkout_sin_sesion_conserva_el_plan_en_el_login(flask_app, clean_db):
    seed_users()
    client = flask_app.app.test_client()

    r = client.get("/billing/checkout/premium?interval=annual", headers=HTML)

    assert r.status_code == 302
    assert r.headers["Location"].endswith(
        "/login?auth_required=true&plan=premium&interval=annual&source=direct")


# ===========================================================================
# C. /auth/keepalive (auth_required_no_activity_update, cada 5 minutos)
# ===========================================================================

def test_keepalive_bd_caida_503_sin_cerrar_la_sesion(ent, monkeypatch):
    # CAMBIADO: antes cerraba la sesión y respondía 401 auth_required, y el
    # interceptor del frontend mandaba al usuario al login.
    _bd_caida(monkeypatch, ent)

    r = ent.client.post("/auth/keepalive", json={"user_active": True})

    assert r.status_code == 503
    assert "auth_required" not in r.get_json()
    assert _sesion(ent.client)["user_id"] == ent.user["id"]


def test_keepalive_usuario_borrado_401_y_cierra(ent):
    with ent.client.session_transaction() as sess:
        sess["user_id"] = 999999

    r = ent.client.post("/auth/keepalive", json={"user_active": True})

    assert r.status_code == 401
    assert r.get_json()["auth_required"] is True
    assert "user_id" not in _sesion(ent.client)


def test_keepalive_no_cuenta_como_actividad(ent):
    hace_diez_minutos = datetime.now() - timedelta(minutes=10)
    _login(ent.client, ent.user, ultima_actividad=hace_diez_minutos)

    r = ent.client.post("/auth/keepalive", json={"user_active": False})

    assert r.status_code == 200
    assert _sesion(ent.client)["last_activity"] == hace_diez_minutos.isoformat()


# ===========================================================================
# D. /auth/status (lo consulta el gestor de sesión)
# ===========================================================================

def test_status_normal(ent):
    r = ent.client.get("/auth/status", headers=JSON)
    assert r.status_code == 200
    assert r.get_json()["authenticated"] is True


def test_status_bd_caida_503_nunca_authenticated_false(ent, monkeypatch):
    # CAMBIADO: antes respondía authenticated=False (user_not_found) y el
    # gestor de sesión del frontend cerraba la sesión del usuario.
    _bd_caida(monkeypatch, ent)

    r = ent.client.get("/auth/status", headers=JSON)

    assert r.status_code == 503
    cuerpo = r.get_json()
    assert "authenticated" not in cuerpo
    assert (cuerpo["code"], cuerpo["retry"]) == ("database_unavailable", True)
    assert _sesion(ent.client)["user_id"] == ent.user["id"]


def test_status_error_interno_500_nunca_authenticated_false(ent, monkeypatch):
    monkeypatch.setattr(ent.database, "_SQL_USUARIO_POR_ID", SQL_ROTO)

    r = ent.client.get("/auth/status", headers=JSON)

    assert r.status_code == 500
    assert "authenticated" not in r.get_json()


def test_status_usuario_borrado_no_autenticado(ent):
    with ent.client.session_transaction() as sess:
        sess["user_id"] = 999999

    r = ent.client.get("/auth/status", headers=JSON)

    assert r.status_code == 200
    assert r.get_json() == {"authenticated": False, "user_not_found": True, "time_remaining": 0}
