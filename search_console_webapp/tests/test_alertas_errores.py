"""
Avisos por email de los errores de la aplicación y del saldo de SerpAPI (sep-2026).

Ejecutar:  scripts/run_tests_docker.sh -q tests/test_alertas_errores.py
"""

import logging
import threading
import time
from unittest import mock

import pytest

from services import alertas_errores
from services.alertas_errores import AvisoErrores


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture
def aviso():
    enviados = []
    reloj = Reloj()
    h = AvisoErrores(lambda asunto, html: enviados.append((asunto, html)), "production",
                     agrupar=60, intervalo=900, reloj=reloj)
    registro = logging.getLogger("prueba.avisos")
    registro.addHandler(h)
    registro.propagate = False
    yield h, registro, enviados, reloj
    registro.removeHandler(h)
    registro.propagate = True


def test_agrupa_por_tipo_y_espera_para_juntar_rafagas(aviso):
    h, registro, enviados, reloj = aviso
    for _ in range(3):
        registro.error("fallo al guardar el análisis")
    try:
        raise ValueError("x")
    except ValueError:
        registro.exception("fallo con traza")

    assert h.enviar_si_toca() is False and enviados == []   # aún agrupando
    reloj.t += 61
    assert h.enviar_si_toca() is True

    assert len(enviados) == 1
    asunto, html = enviados[0]
    assert asunto == "[PRODUCTION] Clicandseo: 4 error(es) de 2 tipo(s)"
    assert "<b>3</b>" in html and "fallo al guardar el análisis" in html
    assert "ValueError" in html  # la traza va en el email


def test_intervalo_minimo_entre_emails(aviso):
    h, registro, enviados, reloj = aviso
    registro.error("uno")
    reloj.t += 61
    h.enviar_si_toca()
    registro.error("dos")
    reloj.t += 61
    assert h.enviar_si_toca() is False  # menos de 15 min desde el anterior
    reloj.t += 900
    assert h.enviar_si_toca() is True
    assert len(enviados) == 2


def _registrar(registro, mensaje):
    registro.error(mensaje)  # siempre la misma línea: el mismo tipo de error


def test_tope_diario_con_reserva_para_tipos_nuevos():
    enviados, reloj, dia = [], Reloj(), {"d": 1}
    h = AvisoErrores(lambda a, b: enviados.append(a), "production", agrupar=0, intervalo=0,
                     reloj=reloj, max_dia=3, hoy=lambda: dia["d"], reserva_tipos_nuevos=1)
    registro = logging.getLogger("prueba.tope")
    registro.addHandler(h)
    registro.propagate = False
    try:
        for i in range(4):                 # el mismo fallo repetido
            _registrar(registro, f"repetido {i}")
            h.enviar_si_toca()
        assert len(enviados) == 2          # el tercer email queda para un tipo nuevo
        registro.error("fallo distinto")   # otra línea: tipo nuevo
        assert h.enviar_si_toca() is True and len(enviados) == 3
        assert "2 tipo(s)" in enviados[-1]  # va junto con la repetición pendiente
        registro.error("otro distinto más")
        assert h.enviar_si_toca() is False and len(enviados) == 3   # tope del día
        dia["d"] = 2
        assert h.enviar_si_toca() is True and len(enviados) == 4
    finally:
        registro.removeHandler(h)
        registro.propagate = True


def test_ignora_el_ruido_y_los_warning(aviso):
    h, registro, enviados, reloj = aviso
    registro.error("❌ Missing Stripe signature")
    # Webhook con firma o cuerpo inválidos: lo puede mandar cualquiera
    registro.error("❌ Invalid signature with provided secrets: No signatures found")
    registro.error("❌ Error processing webhook: Invalid signature", exc_info=(ValueError, ValueError("x"), None))
    registro.error("❌ Invalid payload: Expecting value")
    registro.error("❌ Error processing webhook: Invalid payload")
    registro.warning("solo un aviso")
    reloj.t += 61
    assert h.enviar_si_toca() is True and enviados == []


def test_oculta_secretos_y_emails(aviso):
    h, registro, enviados, reloj = aviso
    registro.error("fallo para ana.garcia@example.com en /reset-password?token=SECRETO123")
    reloj.t += 61
    h.enviar_si_toca()
    html = enviados[0][1]
    assert "ana.garcia@example.com" not in html and "a***@example.com" in html
    assert "SECRETO123" not in html


@pytest.mark.parametrize("texto, secreto", [
    ("Authorization: Bearer ya29.a0AfH6SMBxxxxxxxx", "ya29.a0AfH6SMBxxxxxxxx"),
    ("stripe falló con sk_live_51Habcdefghijk", "sk_live_51Habcdefghijk"),
    ("openai: sk-proj-abcdefghijklmnop1234", "sk-proj-abcdefghijklmnop1234"),
    ("Detalles: {'api_key': 'AbCdEf123456', 'model': 'x'}", "AbCdEf123456"),
    ('respuesta {"password": "hunter2hunter2"}', "hunter2hunter2"),
    ("client_secret=GOCSPX-abcdef123", "GOCSPX-abcdef123"),
])
def test_oculta_otros_secretos(texto, secreto):
    assert secreto not in alertas_errores._limpiar(texto)


def test_limpiar_un_texto_enorme_es_rapido():
    """Con [..]* delante de la @ tardaba ~4 s con 60.000 caracteres (con el cerrojo cogido)."""
    inicio = time.perf_counter()
    alertas_errores._limpiar("a" * 200_000)
    assert time.perf_counter() - inicio < 0.5


def test_la_traza_se_limpia_antes_de_recortarla(aviso):
    h, registro, enviados, reloj = aviso
    try:
        raise RuntimeError("fallo en /callback?token=" + "S" * 40 + " " + "x" * 2480)
    except RuntimeError:
        registro.exception("con traza larga")
    reloj.t += 61
    h.enviar_si_toca()
    assert "S" * 40 not in enviados[0][1]


def test_un_envio_que_falla_no_rompe_nada(aviso):
    h, registro, enviados, reloj = aviso
    h._enviar = lambda *a: (_ for _ in ()).throw(RuntimeError("smtp caído"))
    registro.error("uno")
    reloj.t += 61
    assert h.enviar_si_toca() is True  # se descarta sin lanzar


def test_no_se_realimenta_con_errores_del_propio_envio():
    enviados = []

    def enviar(asunto, html):
        logging.getLogger("prueba.envio").error("el SMTP falló")  # mientras envía
        enviados.append(asunto)

    h = AvisoErrores(enviar, "production", agrupar=0, intervalo=0)
    registro = logging.getLogger("prueba.envio")
    registro.addHandler(h)
    registro.propagate = False
    try:
        registro.error("error real")
        for _ in range(50):
            if enviados:
                break
            time.sleep(0.1)
        time.sleep(0.3)
        assert enviados == ["[PRODUCTION] Clicandseo: 1 error(es) de 1 tipo(s)"]
        assert h._pendientes == {}
    finally:
        registro.removeHandler(h)
        registro.propagate = True


def test_al_salir_el_proceso_manda_lo_pendiente_sin_esperar(aviso):
    """sys.exit tras un error de arranque: el hilo daemon moría antes de agrupar."""
    h, registro, enviados, reloj = aviso
    registro.critical("No se pudo conectar a la base de datos")
    assert h.vaciar(espera=5) is True          # sin avanzar el reloj
    assert len(enviados) == 1 and "No se pudo conectar" in enviados[0][1]
    assert h.vaciar(espera=5) is False         # nada más pendiente


def test_errores_distintos_en_rutas_distintas_son_tipos_distintos(aviso):
    """Flask registra todas las excepciones desde la misma línea: la firma sale de la traza."""
    from flask import Flask
    h, _registro, enviados, reloj = aviso
    app = Flask("prueba_firmas")
    app.config["PROPAGATE_EXCEPTIONS"] = False
    app.logger.addHandler(h)

    @app.route("/a")
    def ruta_a():
        return {}["falta_a"]

    @app.route("/b")
    def ruta_b():
        return {}["falta_b"]

    try:
        cliente = app.test_client()
        cliente.get("/a"), cliente.get("/a"), cliente.get("/b")
    finally:
        app.logger.removeHandler(h)
    reloj.t += 61
    h.enviar_si_toca()
    asunto, html = enviados[0]
    assert asunto == "[PRODUCTION] Clicandseo: 3 error(es) de 2 tipo(s)"
    assert "falta_a" in html and "falta_b" in html


def test_no_se_instala_fuera_de_railway(monkeypatch):
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    assert alertas_errores.instalar_avisos_de_errores() is None


def test_se_instala_en_railway_y_se_puede_apagar(monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.setenv("ERROR_ALERTS_ENABLED", "false")
    assert alertas_errores.instalar_avisos_de_errores() is None
    monkeypatch.setenv("ERROR_ALERTS_ENABLED", "true")
    anterior = threading.excepthook
    al_salir = []
    monkeypatch.setattr(alertas_errores.atexit, "register", al_salir.append)
    h = alertas_errores.instalar_avisos_de_errores()
    try:
        assert isinstance(h, AvisoErrores)
        assert alertas_errores.instalar_avisos_de_errores() is h  # no duplica
        assert al_salir == [h.vaciar]
    finally:
        logging.getLogger().removeHandler(h)
        threading.excepthook = anterior


def test_las_excepciones_sin_capturar_de_un_hilo_se_registran(caplog):
    anterior = threading.excepthook
    alertas_errores._registrar_excepciones_de_hilos()
    try:
        with caplog.at_level(logging.ERROR, logger="hilos"):
            hilo = threading.Thread(target=lambda: 1 / 0, name="hilo-que-falla")
            hilo.start()
            hilo.join()
        assert any(r.name == "hilos" and "hilo-que-falla" in r.getMessage() and r.exc_info for r in caplog.records)
    finally:
        threading.excepthook = anterior


def test_una_excepcion_en_una_ruta_de_flask_llega_al_aviso(aviso):
    from flask import Flask
    h, _registro, enviados, reloj = aviso
    app = Flask("prueba_avisos")
    app.config["PROPAGATE_EXCEPTIONS"] = False
    app.logger.addHandler(h)

    @app.route("/boom")
    def boom():
        raise KeyError("clave")

    try:
        assert app.test_client().get("/boom").status_code == 500
    finally:
        app.logger.removeHandler(h)
    reloj.t += 61
    h.enviar_si_toca()
    assert enviados and "KeyError" in enviados[0][1]


# --- Saldo de SerpAPI (cron diario de quota-reset) -------------------------------

@pytest.fixture
def cron(flask_app, monkeypatch):
    import cron_routes
    monkeypatch.setitem(cron_routes._ultimo_aviso_saldo, "cuando", None)
    return cron_routes


def test_un_codigo_de_google_caducado_no_dispara_avisos(flask_app, clean_db, caplog):
    """InvalidGrantError lo provoca cualquiera con un code inventado: WARNING, un solo registro."""
    import auth
    from oauthlib.oauth2.rfc6749.errors import InvalidGrantError

    class Flujo:
        def fetch_token(self, **kwargs):
            raise InvalidGrantError()

    client = flask_app.app.test_client()
    with client.session_transaction() as sess:
        sess["state"] = "s1"
    with caplog.at_level(logging.WARNING, logger="auth"), mock.patch.object(auth, "create_flow", return_value=Flujo()):
        resp = client.get("/auth/callback?state=s1&code=inventado")
    assert "auth_error=callback_failed" in resp.headers["Location"]
    del_callback = [r for r in caplog.records if "auth_callback" in r.getMessage()]
    assert [r.levelname for r in del_callback] == ["WARNING"]


def test_otro_fallo_del_callback_sigue_siendo_error_con_traza(flask_app, clean_db, caplog):
    import auth

    class Flujo:
        def fetch_token(self, **kwargs):
            raise RuntimeError("fallo inesperado")

    client = flask_app.app.test_client()
    with client.session_transaction() as sess:
        sess["state"] = "s1"
    with caplog.at_level(logging.WARNING, logger="auth"), mock.patch.object(auth, "create_flow", return_value=Flujo()):
        client.get("/auth/callback?state=s1&code=abc")
    del_callback = [r for r in caplog.records if "auth_callback" in r.getMessage()]
    assert len(del_callback) == 1 and del_callback[0].levelname == "ERROR" and del_callback[0].exc_info


@pytest.mark.parametrize("quedan, avisa", [(2999, True), (3000, False), (25000, False)])
def test_aviso_de_saldo_de_serpapi(cron, monkeypatch, quedan, avisa):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CRON_ALERTS_ENABLED", "true")
    monkeypatch.delenv("SERPAPI_ALERT_MIN_SEARCHES", raising=False)
    enviados = []
    cuenta = {"total_searches_left": quedan, "plan_name": "Production Plan", "searches_per_month": 15000,
              "plan_searches_left": 0, "extra_credits": quedan, "plan_renewal_date": "2026-10-30"}
    pedido = {}

    def cuenta_de(**kwargs):
        pedido.update(kwargs)
        return cuenta
    r = cron._run_serpapi_balance_check(get_account=cuenta_de,
                                        enviar=lambda to, asunto, html: enviados.append(asunto) or True)
    assert r["alert"] is avisa
    assert enviados == ([f"[PRODUCTION] SerpAPI: quedan {quedan} búsquedas"] if avisa else [])
    assert pedido == {"force_refresh": True, "dato_viejo_si_falla": False}


def test_saldo_de_serpapi_avisa_si_no_se_puede_consultar(cron, monkeypatch):
    """Clave revocada o cuenta suspendida: es el peor caso y antes no avisaba."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CRON_ALERTS_ENABLED", "true")
    enviados = []
    r = cron._run_serpapi_balance_check(get_account=lambda **_: None,
                                        enviar=lambda to, asunto, html: enviados.append(asunto) or True)
    assert r["alert"] is True and r["checked"] is False
    assert enviados == ["[PRODUCTION] SerpAPI: no se pudo consultar el saldo"]


def test_saldo_de_serpapi_un_solo_email_si_el_cron_se_repite(cron, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CRON_ALERTS_ENABLED", "true")
    enviados, t = [], {"v": 1000.0}

    def comprobar():
        return cron._run_serpapi_balance_check(get_account=lambda **_: {"total_searches_left": 10},
                                               enviar=lambda to, a, h: enviados.append(a) or True,
                                               reloj=lambda: t["v"])
    comprobar()
    t["v"] += 3600
    assert comprobar()["email_sent"] is False
    t["v"] += 20 * 3600
    comprobar()
    assert len(enviados) == 2


def test_saldo_de_serpapi_no_lanza_con_un_umbral_mal_escrito(cron, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SERPAPI_ALERT_MIN_SEARCHES", "tres mil")
    r = cron._run_serpapi_balance_check(get_account=lambda **_: {"total_searches_left": 10}, enviar=lambda *a: True)
    assert r == {"checked": False, "reason": "error"}


def test_saldo_de_serpapi_solo_desde_produccion(cron, monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    r = cron._run_serpapi_balance_check(get_account=lambda **_: {"total_searches_left": 1}, enviar=lambda *a: True)
    assert r == {"checked": False, "reason": "solo en producción"}


def test_saldo_de_serpapi_respeta_el_interruptor(cron, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CRON_ALERTS_ENABLED", "false")
    enviados = []
    r = cron._run_serpapi_balance_check(get_account=lambda **_: {"total_searches_left": 1},
                                        enviar=lambda *a: enviados.append(a))
    assert r["alert"] is True and enviados == []
