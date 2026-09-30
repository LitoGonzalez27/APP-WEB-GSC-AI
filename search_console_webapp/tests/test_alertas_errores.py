"""
Avisos por email de los errores de la aplicación y del saldo de SerpAPI (oct-2026).

Ejecutar:  scripts/run_tests_docker.sh -q tests/test_alertas_errores.py
"""

import logging
import threading
import time

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


def test_tope_diario_de_emails():
    enviados, reloj, dia = [], Reloj(), {"d": 1}
    h = AvisoErrores(lambda a, b: enviados.append(a), "production", agrupar=0, intervalo=0,
                     reloj=reloj, max_dia=2, hoy=lambda: dia["d"])
    registro = logging.getLogger("prueba.tope")
    registro.addHandler(h)
    registro.propagate = False
    try:
        for i in range(3):
            registro.error(f"error {i}")
            h.enviar_si_toca()
        assert len(enviados) == 2          # el tercero espera al día siguiente
        dia["d"] = 2
        assert h.enviar_si_toca() is True and len(enviados) == 3
    finally:
        registro.removeHandler(h)
        registro.propagate = True


def test_ignora_el_ruido_y_los_warning(aviso):
    h, registro, enviados, reloj = aviso
    registro.error("❌ Missing Stripe signature")
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


def test_no_se_instala_fuera_de_railway(monkeypatch):
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    assert alertas_errores.instalar_avisos_de_errores() is None


def test_se_instala_en_railway_y_se_puede_apagar(monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.setenv("ERROR_ALERTS_ENABLED", "false")
    assert alertas_errores.instalar_avisos_de_errores() is None
    monkeypatch.setenv("ERROR_ALERTS_ENABLED", "true")
    anterior = threading.excepthook
    h = alertas_errores.instalar_avisos_de_errores()
    try:
        assert isinstance(h, AvisoErrores)
        assert alertas_errores.instalar_avisos_de_errores() is h  # no duplica
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
def cron(flask_app):
    import cron_routes
    return cron_routes


@pytest.mark.parametrize("quedan, avisa", [(2999, True), (3000, False), (25000, False)])
def test_aviso_de_saldo_de_serpapi(cron, monkeypatch, quedan, avisa):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CRON_ALERTS_ENABLED", "true")
    monkeypatch.delenv("SERPAPI_ALERT_MIN_SEARCHES", raising=False)
    enviados = []
    cuenta = {"total_searches_left": quedan, "plan_name": "Production Plan", "searches_per_month": 15000,
              "plan_searches_left": 0, "extra_credits": quedan, "plan_renewal_date": "2026-10-30"}
    r = cron._run_serpapi_balance_check(get_account=lambda force_refresh=False: cuenta,
                                        enviar=lambda to, asunto, html: enviados.append(asunto) or True)
    assert r["alert"] is avisa
    assert enviados == ([f"[PRODUCTION] SerpAPI: quedan {quedan} búsquedas"] if avisa else [])


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
