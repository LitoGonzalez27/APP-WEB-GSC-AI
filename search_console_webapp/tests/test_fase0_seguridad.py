"""
Tests de los arreglos de seguridad de la fase 0 de la limpieza (sep-2026).

Google, SerpAPI y la red no se tocan: el flujo OAuth se simula con un Flow
falso y la información de usuario de Google con un parche. Todo corre contra
la base desechable de Docker (scripts/run_tests_docker.sh).
"""

import os
from datetime import datetime
from types import SimpleNamespace
from unittest import mock

import pytest

from tests.conftest import seed_users


def _login_session(client, user):
    with client.session_transaction() as sess:
        sess["user_id"] = user["id"]
        sess["user_email"] = user["email"]
        sess["user_name"] = user["name"]
        sess["last_activity"] = datetime.now().isoformat()


def _fetch_one(sql, params=()):
    import database
    conn = database.get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchone()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# /debug-ai-detection: solo admin y sin clave de SerpAPI en la respuesta
# ---------------------------------------------------------------------------

class TestDebugAiDetection:
    def test_usuarios_no_admin_reciben_403(self, flask_app, clean_db):
        user, _admin, paid = seed_users()
        for who in (user, paid):
            client = flask_app.app.test_client()
            _login_session(client, who)
            resp = client.post("/debug-ai-detection", json={"keyword": "x", "site_url": "https://a.com"})
            assert resp.status_code == 403

    def test_admin_la_usa_y_la_clave_sale_oculta(self, flask_app, clean_db):
        _user, admin, _paid = seed_users()
        client = flask_app.app.test_client()
        _login_session(client, admin)
        serp = {"organic_results": [], "search_metadata": {"id": "x"}}
        with mock.patch.object(flask_app, "get_serp_json", return_value=serp), \
             mock.patch.object(flask_app, "detect_ai_overview_elements", return_value={
                 "has_ai_overview": False, "domain_is_ai_source": False, "total_elements": 0,
                 "domain_ai_source_position": None, "domain_ai_source_link": None,
                 "ai_overview_detected": [], "impact_score": 0, "elements_before_organic": 0}):
            resp = client.post("/debug-ai-detection", json={"keyword": "zapatos", "site_url": "https://a.com", "country": "esp"})
        assert resp.status_code == 200
        body = resp.get_json()
        used = body.get("serp_params_used") or body.get("debug_info", {}).get("serp_params_used")
        assert used is not None, body.keys()
        assert used["api_key"] == "***REDACTED***"
        assert os.environ["SERPAPI_KEY"] not in resp.get_data(as_text=True)

    def test_admin_sin_keyword_sigue_dando_400(self, flask_app, clean_db):
        _user, admin, _paid = seed_users()
        client = flask_app.app.test_client()
        _login_session(client, admin)
        resp = client.post("/debug-ai-detection", json={"site_url": "https://a.com"})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# /auth/callback: el state se exige, se consume y se compara
# ---------------------------------------------------------------------------

class TestOAuthState:
    def test_sin_state_en_sesion_ni_en_url_se_rechaza(self, flask_app, clean_db):
        client = flask_app.app.test_client()
        resp = client.get("/auth/callback?code=abc")
        assert resp.status_code == 302
        assert "auth_error=invalid_state" in resp.headers["Location"]

    def test_state_distinto_se_rechaza(self, flask_app, clean_db):
        client = flask_app.app.test_client()
        with client.session_transaction() as sess:
            sess["state"] = "correcto"
        resp = client.get("/auth/callback?state=otro&code=abc")
        assert "auth_error=invalid_state" in resp.headers["Location"]

    def test_state_correcto_pasa_y_se_consume(self, flask_app, clean_db):
        import auth
        client = flask_app.app.test_client()
        with client.session_transaction() as sess:
            sess["state"] = "correcto"
        # create_flow -> None: si se llega ahí, la comprobación del state pasó
        with mock.patch.object(auth, "create_flow", return_value=None):
            resp = client.get("/auth/callback?state=correcto&code=abc")
        assert "auth_error=oauth_config" in resp.headers["Location"]
        with client.session_transaction() as sess:
            assert "state" not in sess


# ---------------------------------------------------------------------------
# /auth/login y /auth/signup: next solo del propio sitio
# ---------------------------------------------------------------------------

class _FakeFlowStart:
    def authorization_url(self, **kwargs):
        return "https://accounts.google.com/o/oauth2/auth?fake=1", kwargs.get("state")


@pytest.mark.parametrize("route", ["/auth/login", "/auth/signup"])
@pytest.mark.parametrize(
    "next_value, se_guarda",
    [
        ("https://evil.example.com/robar", False),
        ("//evil.example.com/robar", False),
        ("/project-invitations/accept?token=t", True),
        ("/billing/checkout/basic?source=pricing", True),
        # URL absoluta del propio host: la que manda billing_routes vía /login
        ("http://localhost/billing/checkout/basic?source=pricing", True),
    ],
)
def test_next_solo_del_propio_sitio(flask_app, clean_db, route, next_value, se_guarda):
    import auth
    client = flask_app.app.test_client()
    with mock.patch.object(auth, "create_flow", return_value=_FakeFlowStart()):
        resp = client.get(route, query_string={"next": next_value})
    assert resp.status_code == 302
    with client.session_transaction() as sess:
        if se_guarda:
            assert sess.get("auth_next") == next_value
        else:
            assert "auth_next" not in sess


# ---------------------------------------------------------------------------
# Login con Google completo (simulado): cookie sin client_secret, conexión
# guardada igual que antes y bloqueo de emails no verificados por Google
# ---------------------------------------------------------------------------

class _FakeFlowCallback:
    def __init__(self):
        self.credentials = SimpleNamespace(
            token="ya29.token-falso",
            refresh_token="1//refresh-falso",
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.environ.get("GOOGLE_CLIENT_ID"),
            client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
            scopes=["openid", "email"],
        )

    def fetch_token(self, **kwargs):
        return None


def _google_login(flask_app, email, verified_email):
    import auth
    client = flask_app.app.test_client()
    with client.session_transaction() as sess:
        sess["state"] = "s1"
        sess["oauth_action"] = "login"
    info = {"id": "google-123", "email": email, "name": "Usuario Test", "picture": None,
            "verified_email": verified_email}
    with mock.patch.object(auth, "create_flow", return_value=_FakeFlowCallback()), \
         mock.patch.object(auth, "get_user_info_from_temp_credentials", return_value=info):
        resp = client.get("/auth/callback?state=s1&code=abc")
    return client, resp


class TestGoogleLogin:
    @pytest.mark.parametrize("verified", [True, None])
    def test_login_vincula_y_la_cookie_no_lleva_client_secret(self, flask_app, clean_db, verified):
        user, _admin, _paid = seed_users()
        client, resp = _google_login(flask_app, user["email"], verified)
        assert resp.status_code == 302
        assert "auth_error" not in resp.headers["Location"]
        with client.session_transaction() as sess:
            assert sess["user_id"] == user["id"]
            creds = sess["credentials"]
            assert "client_secret" not in creds
            assert creds["client_id"] == os.environ["GOOGLE_CLIENT_ID"]
        row = _fetch_one("SELECT google_id FROM users WHERE id = %s", (user["id"],))
        assert row["google_id"] == "google-123"
        # La conexión persistida se sigue guardando con el secreto, como antes
        conn_row = _fetch_one("SELECT client_id, client_secret FROM oauth_connections WHERE user_id = %s", (user["id"],))
        assert conn_row is not None
        assert conn_row["client_id"] == os.environ["GOOGLE_CLIENT_ID"]
        assert conn_row["client_secret"] == os.environ["GOOGLE_CLIENT_SECRET"]

    def test_email_no_verificado_por_google_no_entra_ni_vincula(self, flask_app, clean_db):
        user, _admin, _paid = seed_users()
        client, resp = _google_login(flask_app, user["email"], False)
        assert "auth_error=email_not_verified" in resp.headers["Location"]
        with client.session_transaction() as sess:
            assert "user_id" not in sess
            assert "credentials" not in sess
            assert "temp_credentials" not in sess
        row = _fetch_one("SELECT google_id FROM users WHERE id = %s", (user["id"],))
        assert row["google_id"] is None


# ---------------------------------------------------------------------------
# Construcción de credenciales sin secreto en la cookie
# ---------------------------------------------------------------------------

class TestClientSecret:
    def test_secreto_del_entorno_si_coincide_el_client_id(self, flask_app):
        import auth
        assert auth._oauth_client_secret(os.environ["GOOGLE_CLIENT_ID"], "guardado-viejo") == os.environ["GOOGLE_CLIENT_SECRET"]

    def test_secreto_guardado_si_es_otro_cliente(self, flask_app):
        import auth
        assert auth._oauth_client_secret("otro-cliente.apps.googleusercontent.com", "guardado") == "guardado"

    @pytest.mark.parametrize("cookie_antigua", [False, True])
    def test_get_user_credentials_con_y_sin_secreto_en_la_cookie(self, flask_app, cookie_antigua):
        import auth
        creds = {
            "token": "t", "refresh_token": "r", "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": os.environ["GOOGLE_CLIENT_ID"], "scopes": ["openid"],
        }
        if cookie_antigua:
            creds["client_secret"] = "secreto-en-cookie-antigua"
        with flask_app.app.test_request_context():
            from flask import session
            session["user_id"] = 1
            session["credentials"] = creds
            built = auth.get_user_credentials()
        assert built is not None
        assert built.client_secret == os.environ["GOOGLE_CLIENT_SECRET"]

    def test_credentials_for_session_quita_solo_el_secreto(self, flask_app):
        import auth
        full = {"token": "t", "client_id": "c", "client_secret": "s", "scopes": ["x"]}
        assert auth._credentials_for_session(full) == {"token": "t", "client_id": "c", "scopes": ["x"]}
        assert auth._credentials_for_session(None) is None
