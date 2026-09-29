"""
Fase de fiabilidad (sep-2026): GET /admin/users/<id>/billing-details.

Prueban el flujo real (decorador admin_required + ruta + consultas) contra el
Postgres desechable de Docker. Los fallos se provocan de verdad donde se puede:
una consulta cancelada por statement_timeout (error transitorio real), una
tabla inexistente (error de programación real) o el pool agotado. Contrato:

- 200: el usuario existe (misma estructura de antes + metrics_unavailable).
- 404 user_not_found: la consulta fue bien y el usuario no existe.
- 503 database_unavailable + retry: no se pudo consultar (transitorio).
- 500 internal_error: fallo interno (SQL mal formado, error de Python).
- Un fallo técnico al comprobar al admin: 503/500, sin cerrar su sesión y sin
  ejecutar la ruta. Solo se cierra si la consulta fue bien y ya no existe.
- Cursor y conexión vuelven siempre al pool.

Ejecutar:  scripts/run_tests_docker.sh -q tests/test_fiabilidad_billing_details.py
"""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest import mock

import psycopg2
import pytest

from tests.conftest import seed_users

JSON = {"Accept": "application/json"}
HTML = {"Accept": "text/html"}

SQL_TRANSITORIO = "SET LOCAL statement_timeout = '50ms'; SELECT pg_sleep(0.5), u.* FROM users u WHERE u.id = %s"
SQL_ROTO = "SELECT * FROM tabla_que_no_existe WHERE id = %s"


def _url(user_id):
    return f"/admin/users/{user_id}/billing-details"


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


class _ConexionEspiada:
    """Envoltorio de una conexión del pool que registra cursores y cierre."""

    def __init__(self, conn, espia):
        self._conn = conn
        self._espia = espia
        self.cerrada = False

    def cursor(self, *args, **kwargs):
        if self._espia.fallar_cursor is not None:
            raise self._espia.fallar_cursor
        cur = self._conn.cursor(*args, **kwargs)
        self._espia.cursores.append(cur)
        return cur

    def close(self):
        self.cerrada = True
        self._conn.close()
        if self._espia.fallar_close is not None:
            raise self._espia.fallar_close

    def __getattr__(self, nombre):
        return getattr(self._conn, nombre)


class _Espia:
    def __init__(self, real):
        self._real = real
        self.conexiones = []
        self.cursores = []
        self.fallar_cursor = None
        self.fallar_close = None

    def __call__(self):
        conn = self._real()
        if conn is None:
            return None
        espiada = _ConexionEspiada(conn, self)
        self.conexiones.append(espiada)
        return espiada

    def todo_liberado(self):
        return all(c.cerrada for c in self.conexiones) and all(cur.closed for cur in self.cursores)


@pytest.fixture
def ent(flask_app, clean_db, monkeypatch):
    import admin_billing_panel
    import database

    user, admin, paid = seed_users()
    client = flask_app.app.test_client()
    _login(client, admin)
    espia_admin = _Espia(database.get_db_connection)
    espia_ficha = _Espia(admin_billing_panel.get_db_connection)
    monkeypatch.setattr(database, "get_db_connection", espia_admin)
    monkeypatch.setattr(admin_billing_panel, "get_db_connection", espia_ficha)
    yield SimpleNamespace(client=client, db=clean_db, user=user, admin=admin, paid=paid,
                          espia_admin=espia_admin, espia_ficha=espia_ficha,
                          database=database, panel=admin_billing_panel)
    # Ninguna prueba puede dejar conexiones prestadas.
    assert _conexiones_prestadas() == 0


# ===========================================================================
# A. Acceso (admin_required)
# ===========================================================================

def test_sin_sesion_json_401_y_html_redirige_al_login(flask_app, clean_db):
    seed_users()
    client = flask_app.app.test_client()

    r_json = client.get(_url(3), headers=JSON)
    r_html = client.get(_url(3), headers=HTML)

    assert r_json.status_code == 401
    assert r_json.get_json()["auth_required"] is True
    assert r_html.status_code == 302 and "/login" in r_html.headers["Location"]


def test_sesion_expirada_401_y_se_cierra(ent):
    _login(ent.client, ent.admin, ultima_actividad=datetime.now() - timedelta(hours=3))

    r = ent.client.get(_url(ent.paid["id"]), headers=JSON)

    assert r.status_code == 401
    assert r.get_json()["session_expired"] is True
    assert "user_id" not in _sesion(ent.client)


def test_usuario_sin_permisos_403(ent):
    _login(ent.client, ent.user)

    r = ent.client.get(_url(ent.paid["id"]), headers=JSON)

    assert r.status_code == 403
    assert r.get_json()["admin_required"] is True
    assert _sesion(ent.client)["user_id"] == ent.user["id"]


def test_cuenta_suspendida_403(ent):
    _sql(ent.db, "UPDATE users SET is_active = false WHERE id = %s", (ent.admin["id"],))

    r = ent.client.get(_url(ent.paid["id"]), headers=JSON)

    assert r.status_code == 403
    assert r.get_json()["account_suspended"] is True


def test_admin_que_ya_no_existe_cierra_la_sesion(ent):
    with ent.client.session_transaction() as sess:
        sess["user_id"] = 999999

    r = ent.client.get(_url(ent.paid["id"]), headers=JSON)

    assert r.status_code == 401
    assert r.get_json()["code"] == "user_not_found"
    assert "user_id" not in _sesion(ent.client)


def test_bd_no_disponible_al_comprobar_al_admin_503_sin_cerrar_sesion_ni_ejecutar(ent, monkeypatch):
    monkeypatch.setattr(ent.database, "get_db_connection", lambda: None)
    ficha = mock.Mock(side_effect=AssertionError("la ruta no debe ejecutarse"))
    monkeypatch.setattr(ent.panel, "get_user_billing_details_strict", ficha)

    r = ent.client.get(_url(ent.paid["id"]), headers=JSON)

    assert r.status_code == 503
    cuerpo = r.get_json()
    assert (cuerpo["code"], cuerpo["retry"], cuerpo["success"]) == ("database_unavailable", True, False)
    assert cuerpo["request_id"]
    assert _sesion(ent.client)["user_id"] == ent.admin["id"]
    ficha.assert_not_called()


def test_bd_no_disponible_en_navegacion_html_503_con_reintentar(ent, monkeypatch):
    monkeypatch.setattr(ent.database, "get_db_connection", lambda: None)

    r = ent.client.get("/admin/users", headers=HTML)

    assert r.status_code == 503
    assert r.mimetype == "text/html"
    html = r.get_data(as_text=True)
    assert "Reintentar" in html and "no disponible" in html
    assert _sesion(ent.client)["user_id"] == ent.admin["id"]


def test_consulta_del_admin_cancelada_de_verdad_503(ent, monkeypatch):
    monkeypatch.setattr(ent.database, "_SQL_USUARIO_POR_ID", SQL_TRANSITORIO)

    r = ent.client.get(_url(ent.paid["id"]), headers=JSON)

    assert r.status_code == 503
    assert r.get_json()["code"] == "database_unavailable"
    assert _sesion(ent.client)["user_id"] == ent.admin["id"]
    assert ent.espia_admin.todo_liberado()


def test_error_sql_al_comprobar_al_admin_500_sin_cerrar_sesion_ni_ejecutar(ent, monkeypatch):
    monkeypatch.setattr(ent.database, "_SQL_USUARIO_POR_ID", SQL_ROTO)
    ficha = mock.Mock(side_effect=AssertionError("la ruta no debe ejecutarse"))
    monkeypatch.setattr(ent.panel, "get_user_billing_details_strict", ficha)

    r = ent.client.get(_url(ent.paid["id"]), headers=JSON)

    assert r.status_code == 500
    cuerpo = r.get_json()
    assert cuerpo["code"] == "internal_error" and "retry" not in cuerpo
    assert "tabla_que_no_existe" not in r.get_data(as_text=True)  # sin SQL al navegador
    assert _sesion(ent.client)["user_id"] == ent.admin["id"]
    ficha.assert_not_called()
    assert ent.espia_admin.todo_liberado()


def test_otra_ruta_de_admin_con_bd_caida_tampoco_cierra_la_sesion(ent, monkeypatch):
    monkeypatch.setattr(ent.database, "get_db_connection", lambda: None)

    r = ent.client.get("/admin/api/costs", headers=JSON)

    assert r.status_code == 503
    assert _sesion(ent.client)["user_id"] == ent.admin["id"]


# ===========================================================================
# B. Usuario objetivo (la ficha)
# ===========================================================================

CAMPOS_QUE_USA_EL_FRONTEND = {
    "id", "email", "name", "plan", "billing_status", "stripe_customer_id", "current_period_start",
    "current_period_end", "quota_limit", "quota_used", "quota_reset_date", "custom_quota_limit",
    "custom_quota_notes", "custom_quota_assigned_by", "custom_quota_assigned_date",
    "custom_llm_prompts_limit", "custom_llm_monthly_units_limit", "custom_manual_ai_max_projects",
    "custom_manual_ai_keywords_limit", "custom_ai_mode_max_projects", "custom_ai_mode_keywords_limit",
    "custom_llm_max_projects", "ai_overview_paused_until", "ai_overview_paused_reason",
    "serp_ru_month", "llm_units_month", "llm_cost_month", "llm_active_projects",
    "ai_mode_paused_projects", "llm_paused_projects", "aio_total", "aio_active", "aim_total",
    "aim_active", "llm_total", "llm_active", "invitations_sent", "invitations_accepted",
    "invitations_pending", "usage_history", "quota_percentage",
}


def test_usuario_existente_200_con_la_estructura_de_siempre(ent):
    _sql(ent.db, "INSERT INTO manual_ai_projects (user_id, name, domain, is_active)"
                 " VALUES (%s, 'p', 'ejemplo.invalid', true)", (ent.paid["id"],))

    r = ent.client.get(_url(ent.paid["id"]), headers=JSON)

    assert r.status_code == 200
    cuerpo = r.get_json()
    assert cuerpo["success"] is True
    u = cuerpo["user"]
    assert CAMPOS_QUE_USA_EL_FRONTEND <= set(u)
    assert (u["id"], u["plan"], u["aio_total"], u["aio_active"]) == (ent.paid["id"], "business", 1, 1)
    assert u["metrics_unavailable"] == []
    assert isinstance(u["usage_history"], list) and u["serp_ru_month"] == 0
    assert ent.espia_ficha.todo_liberado() and ent.espia_admin.todo_liberado()


def test_usuario_inexistente_404(ent):
    r = ent.client.get(_url(999999), headers=JSON)

    assert r.status_code == 404
    assert r.get_json() == {"success": False, "error": "Usuario no encontrado", "code": "user_not_found"}
    assert ent.espia_ficha.todo_liberado()


def test_sin_conexion_para_la_ficha_503(ent, monkeypatch):
    monkeypatch.setattr(ent.panel, "get_db_connection", lambda: None)

    r = ent.client.get(_url(ent.paid["id"]), headers=JSON)

    assert r.status_code == 503
    assert r.get_json()["retry"] is True
    assert _sesion(ent.client)["user_id"] == ent.admin["id"]


def test_pool_agotado_de_verdad_503_y_luego_se_recupera(ent, monkeypatch):
    monkeypatch.setenv("DB_POOL_WAIT_SECONDS", "0.2")
    prestadas = []
    try:
        while True:
            conn = ent.espia_admin._real()
            if conn is None:
                break
            prestadas.append(conn)
        r = ent.client.get(_url(ent.paid["id"]), headers=JSON)
        assert r.status_code == 503
        assert r.get_json()["code"] == "database_unavailable"
        assert _sesion(ent.client)["user_id"] == ent.admin["id"]
    finally:
        for conn in prestadas:
            conn.close()

    # Misma sesión, pool liberado: vuelve a funcionar.
    assert ent.client.get(_url(ent.paid["id"]), headers=JSON).status_code == 200


def test_consulta_de_la_ficha_cancelada_de_verdad_503(ent, monkeypatch):
    monkeypatch.setattr(ent.panel, "_SQL_FICHA_USUARIO", SQL_TRANSITORIO)

    r = ent.client.get(_url(ent.paid["id"]), headers=JSON)

    assert r.status_code == 503
    assert r.get_json()["retry"] is True
    assert ent.espia_ficha.todo_liberado()


def test_error_sql_en_la_ficha_500_nunca_404(ent, monkeypatch):
    monkeypatch.setattr(ent.panel, "_SQL_FICHA_USUARIO", SQL_ROTO)

    r = ent.client.get(_url(ent.paid["id"]), headers=JSON)

    assert r.status_code == 500
    cuerpo = r.get_json()
    assert (cuerpo["code"], cuerpo["success"]) == ("internal_error", False)
    assert "tabla_que_no_existe" not in r.get_data(as_text=True)
    assert ent.espia_ficha.todo_liberado()


def test_error_de_python_en_la_ficha_500(ent, monkeypatch):
    monkeypatch.setattr(ent.panel, "_get_project_counts_by_user", mock.Mock(side_effect=TypeError("fallo")))

    r = ent.client.get(_url(ent.paid["id"]), headers=JSON)

    assert r.status_code == 500
    assert r.get_json()["code"] == "internal_error"
    assert ent.espia_ficha.todo_liberado()


def test_metrica_con_error_sql_queda_no_disponible_y_el_resto_se_calcula(ent, monkeypatch):
    _sql(ent.db, "INSERT INTO manual_ai_projects (user_id, name, domain, is_active)"
                 " VALUES (%s, 'p', 'ejemplo.invalid', true)", (ent.paid["id"],))
    monkeypatch.setattr(ent.panel, "_get_serp_usage_by_user",
                        lambda cur: cur.execute("SELECT * FROM tabla_que_no_existe"))

    r = ent.client.get(_url(ent.paid["id"]), headers=JSON)

    assert r.status_code == 200
    u = r.get_json()["user"]
    assert u["serp_ru_month"] is None  # no disponible, nunca 0
    assert u["metrics_unavailable"] == ["serp_usage"]
    # La transacción se recuperó: las métricas siguientes se calculan.
    assert (u["ru_month"], u["aio_total"]) == (0, 1)


def test_metrica_que_se_traga_el_error_tambien_queda_no_disponible(ent, monkeypatch):
    def invitaciones_que_tragan(cur):
        try:
            cur.execute("SELECT * FROM tabla_que_no_existe")
        except Exception:
            return {}
    monkeypatch.setattr(ent.panel, "_get_invitations_by_user", invitaciones_que_tragan)

    r = ent.client.get(_url(ent.paid["id"]), headers=JSON)

    assert r.status_code == 200
    u = r.get_json()["user"]
    assert (u["invitations_sent"], u["invitations_accepted"], u["invitations_pending"]) == (None, None, None)
    assert u["metrics_unavailable"] == ["invitations"]
    assert u["aio_total"] == 0


def test_metrica_cancelada_por_la_bd_es_503_no_una_metrica_vacia(ent, monkeypatch):
    monkeypatch.setattr(ent.panel, "_get_ru_usage_by_user",
                        lambda cur: cur.execute("SET LOCAL statement_timeout = '50ms'; SELECT pg_sleep(0.5)"))

    r = ent.client.get(_url(ent.paid["id"]), headers=JSON)

    assert r.status_code == 503
    assert ent.espia_ficha.todo_liberado()


# ===========================================================================
# C. Recursos y recuperación
# ===========================================================================

def test_fallo_al_crear_el_cursor_devuelve_la_conexion(ent):
    ent.espia_ficha.fallar_cursor = psycopg2.InterfaceError("connection already closed")

    r = ent.client.get(_url(ent.paid["id"]), headers=JSON)

    assert r.status_code == 503
    assert [c.cerrada for c in ent.espia_ficha.conexiones] == [True]


def test_fallo_al_devolver_la_conexion_no_oculta_el_error_original(ent, monkeypatch):
    monkeypatch.setattr(ent.panel, "_SQL_FICHA_USUARIO", SQL_TRANSITORIO)
    ent.espia_ficha.fallar_close = RuntimeError("fallo al devolver")

    r = ent.client.get(_url(ent.paid["id"]), headers=JSON)

    # La respuesta corresponde al error original (transitorio), no al del cierre.
    assert r.status_code == 503
    assert r.get_json()["code"] == "database_unavailable"


def test_tras_una_caida_transitoria_la_misma_sesion_vuelve_a_funcionar(ent, monkeypatch):
    with monkeypatch.context() as m:
        m.setattr(ent.database, "get_db_connection", lambda: None)
        assert ent.client.get(_url(ent.paid["id"]), headers=JSON).status_code == 503

    r = ent.client.get(_url(ent.paid["id"]), headers=JSON)

    assert r.status_code == 200
    assert r.get_json()["user"]["id"] == ent.paid["id"]


# ===========================================================================
# D. Compatibilidad de los contratos antiguos (consumidores fuera del piloto)
# ===========================================================================

def test_get_user_by_id_antiguo_sigue_devolviendo_none_ante_fallos(ent, monkeypatch):
    assert ent.database.get_user_by_id(ent.paid["id"])["id"] == ent.paid["id"]
    assert ent.database.get_user_by_id(999999) is None
    monkeypatch.setattr(ent.database, "_SQL_USUARIO_POR_ID", SQL_ROTO)
    assert ent.database.get_user_by_id(ent.paid["id"]) is None


def test_get_user_billing_details_antiguo_sigue_devolviendo_none_ante_fallos(ent, monkeypatch):
    assert ent.panel.get_user_billing_details(ent.paid["id"])["id"] == ent.paid["id"]
    monkeypatch.setattr(ent.panel, "_SQL_FICHA_USUARIO", SQL_ROTO)
    assert ent.panel.get_user_billing_details(ent.paid["id"]) is None
