"""
AI Mode: una respuesta de error de SerpAPI no es un resultado.

Hasta oct-2026, _analyze_keyword pasaba al parser la respuesta {'error': ...} de
SerpAPI («We couldn't get valid results…», «Google hasn't returned any
results…») y también se tragaba las excepciones (timeout, red) devolviendo un
resultado vacío. En los dos casos se guardaba en ai_mode_results una fila con
brand_mentioned=False, se cobraba 1 RU (evento 'ai_mode' en quota_usage_events)
y with_backoff no reintentaba porque nunca le llegaba una excepción.

Ahora, como en Manual AI, el error lanza excepción, with_backoff reintenta y, si
sigue fallando, la keyword cuenta como fallida: ni se guarda ni se cobra, y el
cron la cuenta en su email de fin de cron.

Base desechable de Docker (scripts/run_tests_docker.sh); SerpAPI es un doble.
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://dummy:dummy@localhost:5432/dummy")

import json  # noqa: E402
import logging  # noqa: E402
from datetime import date, datetime  # noqa: E402

import psycopg2  # noqa: E402
import psycopg2.extras  # noqa: E402
import pytest  # noqa: E402
import serpapi  # noqa: E402

from ai_mode_projects.services import analysis_service as analysis_mod  # noqa: E402
from ai_mode_projects.utils import decorators as decorators_mod  # noqa: E402
from tests.conftest import seed_users  # noqa: E402

ID_PAGO = 3  # usuario semilla de pago (plan business, cuota 15000)
MARCA = "Clicandseo"

SIN_RESULTADOS_VALIDOS = "We couldn't get valid results for this search. Please try again later."
SIN_RESULTADOS = "Google hasn't returned any results for this query."
CLAVE_INVALIDA = "Invalid API key. Your API key should be here: https://serpapi.com/manage-api-key"

RESPUESTA_BUENA = {
    "search_metadata": {"status": "Success"},
    "text_blocks": [{"type": "paragraph", "snippet": "Herramientas de visibilidad en IA."}],
    "references": [
        {"index": 0, "title": "Clicandseo", "link": "https://clicandseo.com/", "source": "clicandseo.com"},
        {"index": 1, "title": "Otra", "link": "https://example.com/", "source": "example.com"},
    ],
}


# ---------------------------------------------------------------------------
# Infraestructura
# ---------------------------------------------------------------------------

class _Db:
    def __init__(self, conn):
        self.conn = conn

    def all(self, sql, params=None):
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def one(self, sql, params=None):
        rows = self.all(sql, params)
        return rows[0] if rows else None

    def proyecto(self, keywords, nombre="Proyecto AI Mode"):
        pid = self.one(
            """INSERT INTO ai_mode_projects (user_id, name, brand_name, country_code)
               VALUES (%s, %s, %s, 'ES') RETURNING id""",
            (ID_PAGO, nombre, MARCA),
        )["id"]
        for kw in keywords:
            self.all("INSERT INTO ai_mode_keywords (project_id, keyword) VALUES (%s, %s) RETURNING id", (pid, kw))
        return pid

    def resultados(self, pid):
        return self.all(
            """SELECT keyword, analysis_date, brand_mentioned, total_sources, raw_ai_mode_data
                 FROM ai_mode_results WHERE project_id = %s ORDER BY id""",
            (pid,),
        )

    def eventos_ai_mode(self):
        return self.all(
            "SELECT user_id, ru_consumed, keyword FROM quota_usage_events WHERE source = 'ai_mode' ORDER BY id"
        )

    def quota_used(self):
        return self.one("SELECT quota_used FROM users WHERE id = %s", (ID_PAGO,))["quota_used"]


@pytest.fixture
def db(clean_db):
    seed_users()
    conn = psycopg2.connect(clean_db, cursor_factory=psycopg2.extras.RealDictCursor, connect_timeout=5)
    conn.autocommit = True
    try:
        yield _Db(conn)
    finally:
        conn.close()


class _SerpApiDoble:
    """Sustituye a serpapi.GoogleSearch. `respuestas[q]` es la lista de lo que
    devuelve cada llamada para esa keyword (dict o excepción); la última se repite."""

    def __init__(self):
        self.respuestas = {}
        self.llamadas = []

    def __call__(self, params):
        doble = self

        class _Busqueda:
            def get_dict(self):
                q = params["q"]
                doble.llamadas.append({**params, "_timeout": getattr(self, "timeout", None)})
                cola = doble.respuestas[q]
                r = cola.pop(0) if len(cola) > 1 else cola[0]
                if isinstance(r, BaseException):
                    raise r
                return json.loads(json.dumps(r))  # copia: el código la modifica in place

        return _Busqueda()

    def llamadas_de(self, q):
        return [p for p in self.llamadas if p["q"] == q]


@pytest.fixture
def serp(monkeypatch):
    doble = _SerpApiDoble()
    monkeypatch.setattr(serpapi, "GoogleSearch", doble)
    monkeypatch.setenv("SERPAPI_KEY", "clave-ficticia")
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    # Sin esperas reales entre reintentos ni por el rate limiting
    monkeypatch.setattr(decorators_mod.time, "sleep", lambda s: None)
    monkeypatch.setattr(analysis_mod.time, "sleep", lambda s: None)
    return doble


def _analizar(pid, force_overwrite=False, resumen=None):
    kwargs = {"resumen": resumen} if resumen is not None else {}
    return analysis_mod.AnalysisService().run_project_analysis(
        pid, force_overwrite=force_overwrite, user_id=ID_PAGO, **kwargs
    )


# ---------------------------------------------------------------------------
# 1. Un error de SerpAPI no se guarda ni se cobra
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("respuesta", [
    pytest.param({"error": SIN_RESULTADOS_VALIDOS}, id="couldnt-get-valid-results"),
    pytest.param({"error": SIN_RESULTADOS, "search_metadata": {"status": "Success"}}, id="sin-resultados"),
    pytest.param({"error": CLAVE_INVALIDA}, id="clave-invalida"),
    pytest.param({}, id="respuesta-vacia"),
    pytest.param(TimeoutError("Read timed out. (read timeout=60)"), id="timeout"),
    pytest.param(ConnectionError("Connection aborted."), id="red"),
])
def test_error_de_serpapi_no_se_guarda_ni_se_cobra(db, serp, respuesta):
    pid = db.proyecto(["mejor herramienta seo ia"])
    serp.respuestas["mejor herramienta seo ia"] = [respuesta]
    resumen = {}

    resultado = _analizar(pid, resumen=resumen)

    assert db.resultados(pid) == []
    assert db.eventos_ai_mode() == []
    assert db.quota_used() == 0
    assert resultado == []
    assert resumen == {"keywords_fallidas": 1}
    # with_backoff reintenta como en Manual AI: 3 intentos en total
    assert len(serp.llamadas_de("mejor herramienta seo ia")) == 3


def test_error_pasajero_se_reintenta_y_se_guarda_el_bueno(db, serp):
    pid = db.proyecto(["mejor herramienta seo ia"])
    serp.respuestas["mejor herramienta seo ia"] = [{"error": SIN_RESULTADOS_VALIDOS}, RESPUESTA_BUENA]
    resumen = {}

    resultado = _analizar(pid, resumen=resumen)

    filas = db.resultados(pid)
    assert [(f["keyword"], f["brand_mentioned"], f["total_sources"]) for f in filas] == [
        ("mejor herramienta seo ia", True, 2)
    ]
    assert "error" not in filas[0]["raw_ai_mode_data"]
    assert [(e["ru_consumed"], e["keyword"]) for e in db.eventos_ai_mode()] == [(1, "mejor herramienta seo ia")]
    assert db.quota_used() == 1
    assert len(resultado) == 1 and resultado[0]["brand_mentioned"] is True
    assert resumen == {"keywords_fallidas": 0}
    assert len(serp.llamadas_de("mejor herramienta seo ia")) == 2


def test_fallo_parcial_guarda_y_cobra_solo_las_buenas(db, serp):
    pid = db.proyecto(["kw buena", "kw mala"])
    serp.respuestas["kw buena"] = [RESPUESTA_BUENA]
    serp.respuestas["kw mala"] = [{"error": SIN_RESULTADOS}]
    resumen = {}

    resultado = _analizar(pid, resumen=resumen)

    assert [f["keyword"] for f in db.resultados(pid)] == ["kw buena"]
    assert [e["keyword"] for e in db.eventos_ai_mode()] == ["kw buena"]
    assert db.quota_used() == 1
    assert [r["keyword"] for r in resultado] == ["kw buena"]
    assert resumen == {"keywords_fallidas": 1}


def test_la_llamada_a_serpapi_lleva_timeout(db, serp):
    """Sin timeout la librería espera hasta 60.000 s y una lectura colgada para el cron."""
    from quota_middleware import SERPAPI_TIMEOUT_SECONDS
    pid = db.proyecto(["kw"])
    serp.respuestas["kw"] = [RESPUESTA_BUENA]

    _analizar(pid)

    assert [p["_timeout"] for p in serp.llamadas] == [SERPAPI_TIMEOUT_SECONDS]


def test_un_fallo_del_parser_no_repite_la_busqueda_ni_se_guarda(db, serp, monkeypatch, caplog):
    """Solo se reintenta la llamada a SerpAPI (como fetch_serp de Manual AI): repetir una
    búsqueda buena porque falle el parser no cambia nada y SerpAPI la cobra otra vez."""
    def parser_roto(self, serp_data, brand_name):
        raise ValueError("parser roto")
    monkeypatch.setattr(analysis_mod.AnalysisService, "_parse_ai_mode_response", parser_roto)
    pid = db.proyecto(["kw"])
    serp.respuestas["kw"] = [RESPUESTA_BUENA]
    resumen = {}

    with caplog.at_level(logging.WARNING):
        _analizar(pid, resumen=resumen)

    assert len(serp.llamadas_de("kw")) == 1
    assert db.resultados(pid) == [] and db.eventos_ai_mode() == []
    assert resumen == {"keywords_fallidas": 1}
    assert len(_errores(caplog)) == 1


def test_reference_con_title_null_no_rompe_el_parser(db, serp):
    con_title_null = {**RESPUESTA_BUENA, "references": [
        {"index": 0, "title": None, "link": "https://clicandseo.com/", "source": "clicandseo.com"}]}
    pid = db.proyecto(["kw"])
    serp.respuestas["kw"] = [con_title_null]

    _analizar(pid)

    assert [(f["brand_mentioned"], f["total_sources"]) for f in db.resultados(pid)] == [(True, 1)]


def test_sin_conexion_al_guardar_no_se_cobra(db, serp, monkeypatch):
    """Antes create_result hacía return sin conexión y la keyword se cobraba sin fila."""
    from ai_mode_projects.models import result_repository
    pid = db.proyecto(["kw"])
    serp.respuestas["kw"] = [RESPUESTA_BUENA]
    monkeypatch.setattr(result_repository, "get_db_connection", lambda: None)
    resumen = {}

    resultado = _analizar(pid, resumen=resumen)

    assert resultado == [] and resumen == {"keywords_fallidas": 1}
    assert db.resultados(pid) == [] and db.eventos_ai_mode() == [] and db.quota_used() == 0


def test_sin_resumen_el_contrato_de_retorno_no_cambia(db, serp):
    """Sin `resumen` se sigue recibiendo la lista, como antes."""
    pid = db.proyecto(["kw buena", "kw mala"])
    serp.respuestas["kw buena"] = [RESPUESTA_BUENA]
    serp.respuestas["kw mala"] = [{"error": SIN_RESULTADOS}]

    resultado = analysis_mod.AnalysisService().run_project_analysis(pid, force_overwrite=False, user_id=ID_PAGO)

    assert isinstance(resultado, list) and [r["keyword"] for r in resultado] == ["kw buena"]


# ---------------------------------------------------------------------------
# 2. Análisis manual con sobreescritura: un fallo no borra el resultado bueno del día
# ---------------------------------------------------------------------------

def test_sobreescritura_que_falla_conserva_el_resultado_del_dia(db, serp):
    pid = db.proyecto(["mejor herramienta seo ia"])
    serp.respuestas["mejor herramienta seo ia"] = [RESPUESTA_BUENA]
    _analizar(pid)
    assert [f["brand_mentioned"] for f in db.resultados(pid)] == [True]

    serp.respuestas["mejor herramienta seo ia"] = [{"error": SIN_RESULTADOS_VALIDOS}]
    resumen = {}
    _analizar(pid, force_overwrite=True, resumen=resumen)

    filas = db.resultados(pid)
    assert [(f["brand_mentioned"], f["analysis_date"]) for f in filas] == [(True, date.today())]
    assert "error" not in filas[0]["raw_ai_mode_data"]
    assert len(db.eventos_ai_mode()) == 1  # solo el primer análisis
    assert resumen == {"keywords_fallidas": 1}


def test_sobreescritura_que_falla_al_guardar_conserva_el_resultado_del_dia(db, serp):
    """La sustitución va en una sola sentencia (upsert): si falla, el anterior sigue."""
    pid = db.proyecto(["mejor herramienta seo ia"])
    serp.respuestas["mejor herramienta seo ia"] = [RESPUESTA_BUENA]
    _analizar(pid)

    sin_marca = {**RESPUESTA_BUENA, "references": [RESPUESTA_BUENA["references"][1]]}
    serp.respuestas["mejor herramienta seo ia"] = [sin_marca]
    db.all("""CREATE FUNCTION test_ai_mode_fallo() RETURNS trigger LANGUAGE plpgsql AS
              $$ BEGIN RAISE EXCEPTION 'fallo simulado al guardar'; END $$;
              CREATE TRIGGER test_ai_mode_fallo BEFORE UPDATE ON ai_mode_results
              FOR EACH ROW EXECUTE FUNCTION test_ai_mode_fallo(); SELECT 1""")
    try:
        resumen = {}
        _analizar(pid, force_overwrite=True, resumen=resumen)
    finally:
        db.all("""DROP TRIGGER IF EXISTS test_ai_mode_fallo ON ai_mode_results;
                  DROP FUNCTION IF EXISTS test_ai_mode_fallo(); SELECT 1""")

    assert [(f["brand_mentioned"], f["total_sources"]) for f in db.resultados(pid)] == [(True, 2)]
    assert len(db.eventos_ai_mode()) == 1
    assert resumen == {"keywords_fallidas": 1}


def test_sobreescritura_que_funciona_sustituye_el_resultado(db, serp):
    pid = db.proyecto(["mejor herramienta seo ia"])
    serp.respuestas["mejor herramienta seo ia"] = [RESPUESTA_BUENA]
    _analizar(pid)

    sin_marca = {**RESPUESTA_BUENA, "references": [RESPUESTA_BUENA["references"][1]]}
    serp.respuestas["mejor herramienta seo ia"] = [sin_marca]
    _analizar(pid, force_overwrite=True)

    assert [(f["brand_mentioned"], f["total_sources"]) for f in db.resultados(pid)] == [(False, 1)]
    assert len(db.eventos_ai_mode()) == 2


def _cliente_con_sesion(flask_app, db):
    usuario = db.one("SELECT id, email, name FROM users WHERE id = %s", (ID_PAGO,))
    cliente = flask_app.app.test_client()
    with cliente.session_transaction() as sesion:
        sesion["user_id"] = usuario["id"]
        sesion["user_email"] = usuario["email"]
        sesion["user_name"] = usuario["name"]
        sesion["last_activity"] = datetime.now().isoformat()
    return cliente


def test_ruta_analisis_manual_sin_ninguna_keyword_valida_da_503(flask_app, db, serp):
    pid = db.proyecto(["mejor herramienta seo ia"])
    serp.respuestas["mejor herramienta seo ia"] = [RESPUESTA_BUENA]
    _analizar(pid)
    serp.respuestas["mejor herramienta seo ia"] = [{"error": SIN_RESULTADOS_VALIDOS}]

    r = _cliente_con_sesion(flask_app, db).post(
        f"/ai-mode-projects/api/projects/{pid}/analyze", headers={"Accept": "application/json"})

    # Antes: 400 «No keywords available for analysis» y el resultado bueno del día borrado
    assert r.status_code == 503
    assert r.get_json() == {"success": False, "error": "Analysis service temporarily unavailable",
                            "keywords_failed": 1}
    assert [f["brand_mentioned"] for f in db.resultados(pid)] == [True]
    assert len(db.eventos_ai_mode()) == 1


def test_ruta_analisis_manual_con_fallo_parcial_da_200(flask_app, db, serp):
    pid = db.proyecto(["kw buena", "kw mala"])
    serp.respuestas["kw buena"] = [RESPUESTA_BUENA]
    serp.respuestas["kw mala"] = [{"error": SIN_RESULTADOS}]

    r = _cliente_con_sesion(flask_app, db).post(
        f"/ai-mode-projects/api/projects/{pid}/analyze", headers={"Accept": "application/json"})

    assert r.status_code == 200
    assert r.get_json()["results_count"] == 1
    assert [f["keyword"] for f in db.resultados(pid)] == ["kw buena"]


# ---------------------------------------------------------------------------
# 3. Nivel de log (criterio de services.serp_service.nivel_error_serpapi)
# ---------------------------------------------------------------------------

def _errores(caplog):
    return [r for r in caplog.records if r.levelno >= logging.ERROR]


@pytest.mark.parametrize("mensaje", [SIN_RESULTADOS_VALIDOS, SIN_RESULTADOS])
def test_error_pasajero_definitivo_es_warning_y_no_avisa(db, serp, caplog, mensaje):
    pid = db.proyecto(["kw"])
    serp.respuestas["kw"] = [{"error": mensaje}]

    with caplog.at_level(logging.WARNING):
        _analizar(pid)

    assert _errores(caplog) == []
    assert any(r.levelno == logging.WARNING and "kw" in r.getMessage() and mensaje in r.getMessage()
               for r in caplog.records)


@pytest.mark.parametrize("respuesta", [
    pytest.param({"error": CLAVE_INVALIDA}, id="clave-invalida"),
    pytest.param(TimeoutError("Read timed out."), id="timeout"),
])
def test_error_real_definitivo_es_error(db, serp, caplog, respuesta):
    pid = db.proyecto(["kw"])
    serp.respuestas["kw"] = [respuesta]

    with caplog.at_level(logging.WARNING):
        _analizar(pid)

    errores = _errores(caplog)
    assert len(errores) == 1
    assert "kw" in errores[0].getMessage()


def test_reintento_que_sale_bien_no_deja_errores(db, serp, caplog):
    pid = db.proyecto(["kw"])
    serp.respuestas["kw"] = [{"error": CLAVE_INVALIDA}, RESPUESTA_BUENA]

    with caplog.at_level(logging.WARNING):
        _analizar(pid)

    assert _errores(caplog) == []
    filas = db.resultados(pid)
    assert [f["brand_mentioned"] for f in filas] == [True]
    assert "error" not in filas[0]["raw_ai_mode_data"]
    assert len(serp.llamadas_de("kw")) == 2


# ---------------------------------------------------------------------------
# 4. Cron: qué cuenta como fallido y qué llega al email de fin de cron
# ---------------------------------------------------------------------------

@pytest.fixture
def cron(monkeypatch):
    from ai_mode_projects.services.cron_service import CronService
    emails = []
    monkeypatch.setattr(CronService, "_send_completion_email", staticmethod(lambda stats: emails.append(stats)))
    servicio = CronService()
    servicio.emails = emails
    return servicio


def _snapshots(db, pid):
    return db.all("SELECT snapshot_date FROM ai_mode_snapshots WHERE project_id = %s", (pid,))


def test_cron_proyecto_sin_ninguna_keyword_analizada_es_fallido(db, serp, cron):
    caido = db.proyecto(["a1", "a2"], nombre="Todo falla")
    serp.respuestas["a1"] = [{"error": SIN_RESULTADOS_VALIDOS}]
    serp.respuestas["a2"] = [TimeoutError("Read timed out.")]

    resultado = cron.run_daily_analysis_for_all_projects()

    assert resultado["success"] is True
    assert (resultado["successful"], resultado["failed"], resultado["skipped"]) == (0, 1, 0)
    assert resultado["total_keywords"] == 0
    assert resultado["keywords_fallidas"] == 2
    assert db.resultados(caido) == [] and db.eventos_ai_mode() == []
    # Sin datos del día no hay snapshot (antes salía uno con visibilidad 0 %)
    assert _snapshots(db, caido) == []
    assert cron.emails == [resultado]


def test_cron_proyecto_con_fallo_parcial_es_ok_y_cuenta_las_fallidas(db, serp, cron):
    parcial = db.proyecto(["b1", "b2"], nombre="Parcial")
    serp.respuestas["b1"] = [RESPUESTA_BUENA]
    serp.respuestas["b2"] = [{"error": SIN_RESULTADOS}]

    resultado = cron.run_daily_analysis_for_all_projects()

    assert (resultado["successful"], resultado["failed"], resultado["skipped"]) == (1, 0, 0)
    assert resultado["total_keywords"] == 1
    assert resultado["keywords_fallidas"] == 1
    assert [f["keyword"] for f in db.resultados(parcial)] == ["b1"]
    assert len(_snapshots(db, parcial)) == 1


def test_cron_proyecto_parado_por_su_tope_cuenta_como_saltado(db, serp, cron):
    """Antes 'project_quota_exceeded' contaba como OK, con snapshot y len(dict) keywords."""
    pid = db.proyecto(["d1"])
    db.all("UPDATE ai_mode_projects SET monthly_ru_limit = 0 WHERE id = %s RETURNING id", (pid,))
    serp.respuestas["d1"] = [RESPUESTA_BUENA]

    resultado = cron.run_daily_analysis_for_all_projects()

    assert (resultado["successful"], resultado["failed"], resultado["skipped"]) == (0, 0, 1)
    assert resultado["total_keywords"] == 0
    assert _snapshots(db, pid) == [] and serp.llamadas == []


def test_cron_proyecto_sin_usuario_cuenta_como_fallido(db, serp, cron, monkeypatch):
    pid = db.proyecto(["e1"])
    monkeypatch.setattr(analysis_mod, "get_user_by_id", lambda user_id: None)

    resultado = cron.run_daily_analysis_for_all_projects()

    assert (resultado["successful"], resultado["failed"], resultado["skipped"]) == (0, 1, 0)
    assert resultado["total_keywords"] == 0
    assert _snapshots(db, pid) == []


def test_cron_sin_fallos(db, serp, cron):
    pid = db.proyecto(["c1"])
    serp.respuestas["c1"] = [RESPUESTA_BUENA]

    resultado = cron.run_daily_analysis_for_all_projects()

    assert (resultado["successful"], resultado["failed"]) == (1, 0)
    assert resultado["keywords_fallidas"] == 0
    assert len(db.resultados(pid)) == 1


@pytest.mark.parametrize("stats, fila, severidad", [
    pytest.param({"success": True, "successful": 2, "failed": 0, "skipped": 0, "total_keywords": 20,
                  "keywords_fallidas": 3}, "Keywords sin analizar (ni guardadas ni cobradas)", "warning",
                 id="ai-mode-con-fallidas"),
    pytest.param({"success": True, "successful": 2, "failed": 0, "skipped": 0, "total_keywords": 20,
                  "keywords_fallidas": 0}, "Keywords sin analizar (ni guardadas ni cobradas)", "ok",
                 id="ai-mode-sin-fallidas"),
    pytest.param({"success": True, "successful": 2, "failed": 0, "skipped": 0, "total_keywords": 20},
                 None, "ok", id="manual-ai-sin-el-campo"),
])
def test_email_de_fin_de_cron(monkeypatch, stats, fila, severidad):
    import cron_alerts
    import email_service

    enviados = []
    monkeypatch.setattr(cron_alerts, "_get_config", lambda: {
        "enabled": True, "email": "avisos@example.com", "environment": "test", "duration_min_threshold": 60,
    })
    monkeypatch.setattr(email_service, "send_email", lambda to, subject, html: enviados.append((subject, html)) or True)

    r = cron_alerts.send_simple_run_completion_email("AI Mode", stats)

    assert r == {"email_sent": True, "severity": severidad}
    asunto, html = enviados[0]
    if fila:
        assert fila in html
        assert f">{stats['keywords_fallidas']}<" in html
    else:
        assert "sin analizar" not in html
    if stats.get("keywords_fallidas"):
        assert asunto.endswith(f"· {stats['keywords_fallidas']} sin analizar")
    else:
        assert "sin analizar" not in asunto
