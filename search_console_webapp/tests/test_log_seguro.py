"""
Fase de fiabilidad 2 (sep-2026): los logs no guardan los secretos que viajan en
la URL (código y state del retorno de Google, token de restablecer contraseña,
de invitación a proyectos y de aprobación de modelos).

Werkzeug escribía la línea completa de cada petición en el log de Railway; un
token de contraseña vigente leído del log bastaba para cambiar la contraseña.

Ejecutar:  scripts/run_tests_docker.sh -q tests/test_log_seguro.py
"""

import logging
import threading
import urllib.request

import pytest

from services.log_seguro import FiltroSecretosEnUrl, MARCA, instalar_filtro_secretos, ocultar_secretos_en_url


@pytest.mark.parametrize("url, esperado", [
    ("/auth/callback?state=abc123&code=4/0AXlq-_zz&scope=email+profile&authuser=0",
     f"/auth/callback?state={MARCA}&code={MARCA}&scope=email+profile&authuser=0"),
    ("/reset-password?token=Zt9-kq_Lm", f"/reset-password?token={MARCA}"),
    ("/project-invitations/accept?token=abc", f"/project-invitations/accept?token={MARCA}"),
    ("/api/llm-monitoring/models/approve?token=abc&x=1", f"/api/llm-monitoring/models/approve?token={MARCA}&x=1"),
    ("/x?TOKEN=abc", f"/x?TOKEN={MARCA}"),
    ("/x?api_key=abc&key=def", f"/x?api_key={MARCA}&key={MARCA}"),
    ("/auth/check-email?email=ana%40x.com", f"/auth/check-email?email={MARCA}"),
    # El login lleva el token de la invitación dentro de next, codificado; Werkzeug
    # deja %3D sin decodificar.
    ("/auth/login?next=/project-invitations/accept?token%3DT123&x=1",
     f"/auth/login?next=/project-invitations/accept?token={MARCA}&x=1"),
    ("/signup?next=%2Fproject-invitations%2Faccept%3Ftoken%3DT9",
     f"/signup?next=/project-invitations/accept?token={MARCA}"),
    ("/x?next=%252Freset-password%253Ftoken%253DDD", f"/x?next=/reset-password?token={MARCA}"),
])
def test_oculta_los_parametros_secretos(url, esperado):
    assert ocultar_secretos_en_url(url) == esperado


@pytest.mark.parametrize("url", [
    "/search?keyword=seo&country=es",   # 'keyword' no es 'key'
    "/x?monkey=1&codes=2&statement=3",   # nombres que solo se parecen
    "/login?user_not_found=true",
    "/dashboard",
    "/search?q=caf%C3%A9&page=2",       # codificado pero sin secretos: se deja igual
])
def test_no_toca_lo_que_no_es_secreto(url):
    assert ocultar_secretos_en_url(url) == url


def test_linea_de_werkzeug_completa():
    linea = '1.2.3.4 - - [29/Sep/2026 16:04:04] "GET /reset-password?token=Zt9 HTTP/1.1" 302 -'
    assert ocultar_secretos_en_url(linea) == (
        f'1.2.3.4 - - [29/Sep/2026 16:04:04] "GET /reset-password?token={MARCA} HTTP/1.1" 302 -')


def test_el_filtro_nunca_descarta_ni_rompe_un_registro():
    filtro = FiltroSecretosEnUrl()
    con_args = logging.LogRecord("x", logging.INFO, __file__, 1, "GET %s", ("/r?token=abc",), None)
    roto = logging.LogRecord("x", logging.INFO, __file__, 1, "%s %s", ("solo uno",), None)
    normal = logging.LogRecord("x", logging.INFO, __file__, 1, "sin secretos %s", ("aquí",), None)

    assert filtro.filter(con_args) is True
    assert con_args.getMessage() == f"GET /r?token={MARCA}"
    assert filtro.filter(roto) is True          # el mensaje mal formado sigue su camino
    assert filtro.filter(normal) is True
    assert (normal.msg, normal.args) == ("sin secretos %s", ("aquí",))  # sin tocar


def test_instalar_es_idempotente():
    instalar_filtro_secretos()
    instalar_filtro_secretos()
    registro = logging.getLogger("werkzeug")
    assert sum(isinstance(f, FiltroSecretosEnUrl) for f in registro.filters) == 1


def test_servidor_real_no_escribe_el_token_en_el_log(flask_app, clean_db, caplog):
    # Petición de verdad a un servidor Werkzeug (el mismo que usa Railway con
    # `python3 app.py`), no al cliente de pruebas, que no registra peticiones.
    from werkzeug.serving import make_server

    servidor = make_server("127.0.0.1", 0, flask_app.app)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    abridor = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with caplog.at_level(logging.INFO, logger="werkzeug"):
            abridor.open(f"http://127.0.0.1:{servidor.port}/reset-password?token=SECRETO-DE-PRUEBA-123", timeout=10)
    finally:
        servidor.shutdown()
        hilo.join(timeout=5)

    lineas = [r.getMessage() for r in caplog.records if r.name == "werkzeug"]
    assert any(f"/reset-password?token={MARCA}" in linea for linea in lineas), lineas
    assert "SECRETO-DE-PRUEBA-123" not in caplog.text


def test_oculta_secretos_en_la_traza_de_una_excepcion():
    filtro = FiltroSecretosEnUrl()
    try:
        raise ValueError("fallo al pedir https://api.example.invalid/x?api_key=CLAVE-SECRETA&q=1")
    except ValueError:
        import sys
        registro = logging.LogRecord("x", logging.ERROR, __file__, 1, "error", (), sys.exc_info())

    assert filtro.filter(registro) is True
    texto = logging.Formatter().format(registro)
    assert "CLAVE-SECRETA" not in texto
    assert f"api_key={MARCA}&q=1" in texto


def test_importar_la_app_instala_el_filtro(flask_app):
    # En un proceso nuevo, sin que ningún test lo haya instalado antes.
    import os
    import subprocess
    import sys
    codigo = ("import logging, app; from services.log_seguro import FiltroSecretosEnUrl as F; "
              "w = logging.getLogger('werkzeug').filters; r = [h.filters for h in logging.getLogger().handlers]; "
              "assert any(isinstance(f, F) for f in w), 'werkzeug sin filtro'; "
              "assert r and all(any(isinstance(f, F) for f in fs) for fs in r), 'handlers raíz sin filtro'")
    resultado = subprocess.run([sys.executable, "-c", codigo], cwd=os.path.dirname(os.path.dirname(__file__)),
                               env=dict(os.environ), capture_output=True, text=True, timeout=120)
    assert resultado.returncode == 0, resultado.stderr[-2000:]
