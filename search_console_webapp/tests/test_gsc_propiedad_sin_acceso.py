"""
Propiedad de Search Console a la que la cuenta de Google ya no tiene acceso (oct-2026).

El 2-oct, cada vez que un usuario abría la herramienta llegaba un email de error: la
app pedía los países de su primera propiedad (alimonhoreca.com), Google respondía 403
«User does not have sufficient permission» y /get-available-countries lo trataba como
un 500 con ERROR. La lista guardada en gsc_properties estaba desfasada y nunca se
limpiaba, así que se repetía en cada carga.

Ahora un 403 de Google es un aviso (sin email), la respuesta dice qué pasa y, si quien
respondió fue la conexión de la propia propiedad, esta se retira de la lista.

Ejecutar:  scripts/run_tests_docker.sh -q tests/test_gsc_propiedad_sin_acceso.py
"""

import logging
from datetime import datetime
from types import SimpleNamespace

import psycopg2
import psycopg2.extras
import pytest
from googleapiclient.errors import HttpError

from tests.conftest import seed_users

SITE = "https://sin-acceso.example/"


def _login(client, user):
    with client.session_transaction() as sess:
        sess["user_id"] = user["id"]
        sess["user_email"] = user["email"]
        sess["user_name"] = user["name"]
        sess["last_activity"] = datetime.now().isoformat()


class _ServicioGSC:
    """searchanalytics().query().execute() que responde con el HttpError indicado."""

    def __init__(self, status):
        self.status = status

    def searchanalytics(self):
        return self

    def query(self, **kwargs):
        return self

    def execute(self):
        contenido = b'{"error": {"message": "User does not have sufficient permission for site."}}'
        raise HttpError(SimpleNamespace(status=self.status, reason="Forbidden"), contenido)


@pytest.fixture
def ent(flask_app, clean_db):
    user, admin, _paid = seed_users()
    conn = psycopg2.connect(clean_db, cursor_factory=psycopg2.extras.RealDictCursor, connect_timeout=5)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO oauth_connections (user_id, google_email) VALUES (%s, %s) RETURNING id",
        (user["id"], "cuenta@example.invalid"),
    )
    cur.execute(
        "INSERT INTO gsc_properties (user_id, connection_id, site_url, permission_level, verified) "
        "VALUES (%s, %s, %s, 'siteOwner', TRUE)",
        (user["id"], cur.fetchone()["id"], SITE),
    )

    def propiedades(user_id):
        cur.execute("SELECT site_url FROM gsc_properties WHERE user_id = %s", (user_id,))
        return [r["site_url"] for r in cur.fetchall()]

    yield SimpleNamespace(app=flask_app, client=flask_app.app.test_client(), user=user, admin=admin,
                          propiedades=propiedades)
    conn.close()


def _pedir_paises(ent):
    return ent.client.post("/get-available-countries", json={"site_url": SITE},
                           headers={"Accept": "application/json"})


def _errores(caplog):
    return [r for r in caplog.records if r.levelno >= logging.ERROR]


def test_403_de_google_avisa_y_retira_la_propiedad(ent, monkeypatch, caplog):
    import auth
    monkeypatch.setattr(auth, "get_authenticated_service_for_connection", lambda *a, **k: _ServicioGSC(403))
    _login(ent.client, ent.user)

    with caplog.at_level(logging.WARNING):
        resp = _pedir_paises(ent)

    assert resp.status_code == 403
    assert resp.get_json()["error_type"] == "gsc_no_access"
    assert resp.get_json()["property_removed"] is True
    assert ent.propiedades(ent.user["id"]) == []
    assert _errores(caplog) == []          # sin ERROR no hay email de alerta


def test_otro_error_de_google_sigue_siendo_500_y_no_toca_la_lista(ent, monkeypatch, caplog):
    import auth
    monkeypatch.setattr(auth, "get_authenticated_service_for_connection", lambda *a, **k: _ServicioGSC(500))
    _login(ent.client, ent.user)

    with caplog.at_level(logging.WARNING):
        resp = _pedir_paises(ent)

    assert resp.status_code == 500
    assert ent.propiedades(ent.user["id"]) == [SITE]
    assert _errores(caplog)


def test_403_con_la_sesion_generica_no_retira_nada(ent, monkeypatch):
    """Un admin consulta una propiedad ajena con su sesión: su 403 no prueba nada sobre el dueño."""
    monkeypatch.setattr(ent.app, "get_authenticated_service", lambda *a, **k: _ServicioGSC(403))
    _login(ent.client, ent.admin)

    resp = _pedir_paises(ent)

    assert resp.status_code == 403
    assert resp.get_json()["property_removed"] is False
    assert ent.propiedades(ent.user["id"]) == [SITE]
