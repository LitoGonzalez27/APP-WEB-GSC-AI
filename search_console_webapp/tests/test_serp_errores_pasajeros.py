"""
Errores de SerpAPI que no son un fallo de la app (oct-2026).

En el cron de Manual AI del 1-oct, tres respuestas de error de SerpAPI dispararon tres
avisos por email: dos «try again later» tras 90 s y una expansión de AI Overview sin
resultados. El cron terminó sin fallidos. Ahora se registran como WARNING, y el aviso
por email solo recoge ERROR. Los errores reales del proveedor siguen siendo ERROR.

Ejecutar:  scripts/run_tests_docker.sh -q tests/test_serp_errores_pasajeros.py
"""

import logging

import pytest

PASAJEROS = [
    "We couldn't get valid results for this search. Please try again later.",
    "Google hasn't returned any results for this query.",
    "Google has not returned any results for this query.",
]
REALES = [
    "Invalid API key. Your API key should be here: https://serpapi.com/manage-api-key",
    "Your account has run out of searches.",
    "Your searches for the month are exhausted. You can upgrade plans on SerpApi.com website.",
    "Your account has been suspended.",
    "Missing query `q` parameter.",
    "Unsupported `xx` gl parameter.",
    # Un error real con «try again later» no debe quedar silenciado
    "Your hourly searches limit has been reached. Please try again later.",
]


@pytest.fixture
def serp(flask_app, monkeypatch):
    from services import serp_service
    estado = {}
    monkeypatch.setattr(serp_service, "quota_protected_serp_call",
                        lambda params, tipo, cobrar=False, usuario=None: (False, estado["respuesta"]))
    return serp_service, estado


def _niveles(caplog, texto):
    return [r.levelno for r in caplog.records if texto in r.getMessage()]


@pytest.mark.parametrize("mensaje", PASAJEROS)
def test_json_error_pasajero_es_warning(serp, caplog, mensaje):
    serp_service, estado = serp
    estado["respuesta"] = {"search_metadata": {"status": "Error"}, "error": mensaje}
    with caplog.at_level(logging.WARNING, logger="services.serp_service"):
        r = serp_service.get_serp_json({"q": "kw"})
    assert r["error"] == mensaje and r["organic_results"] == []
    assert _niveles(caplog, "Error en SerpAPI") == [logging.WARNING]


@pytest.mark.parametrize("mensaje", REALES)
def test_json_error_real_sigue_siendo_error(serp, caplog, mensaje):
    serp_service, estado = serp
    estado["respuesta"] = {"error": mensaje}
    with caplog.at_level(logging.WARNING, logger="services.serp_service"):
        serp_service.get_serp_json({"q": "kw"})
    assert _niveles(caplog, "Error en SerpAPI") == [logging.ERROR]


@pytest.mark.parametrize("mensaje, nivel", [(PASAJEROS[0], logging.WARNING), (REALES[0], logging.ERROR)])
def test_html_mismo_criterio(serp, caplog, mensaje, nivel):
    serp_service, estado = serp
    estado["respuesta"] = {"error": mensaje}
    with caplog.at_level(logging.WARNING, logger="services.serp_service"):
        html, bloqueo, error = serp_service._serp_html({"q": "kw"})
    assert html is None and bloqueo is None and error == mensaje
    assert _niveles(caplog, "Error en SerpAPI HTML") == [nivel]


def test_un_error_pasajero_no_llega_al_aviso_por_email(serp):
    """El handler de avisos solo recoge ERROR: un WARNING no deja nada pendiente."""
    from services.alertas_errores import AvisoErrores
    serp_service, estado = serp
    aviso = AvisoErrores(lambda a, h: None, "production")
    aviso._arrancar_hilo = lambda: None
    registro = logging.getLogger("services.serp_service")
    registro.addHandler(aviso)
    try:
        estado["respuesta"] = {"error": PASAJEROS[0]}
        serp_service.get_serp_json({"q": "kw"})
        assert aviso._pendientes == {}
        estado["respuesta"] = {"error": REALES[0]}
        serp_service.get_serp_json({"q": "kw"})
        assert len(aviso._pendientes) == 1
    finally:
        registro.removeHandler(aviso)


def test_un_resultado_que_no_es_un_dict_no_rompe(serp, caplog):
    serp_service, estado = serp
    estado["respuesta"] = "respuesta inesperada"
    with caplog.at_level(logging.WARNING, logger="services.serp_service"):
        r = serp_service.get_serp_json({"q": "kw"})
    assert r["error"] == "respuesta inesperada" and r["organic_results"] == []
    assert _niveles(caplog, "Error en SerpAPI") == [logging.ERROR]


@pytest.mark.parametrize("mensaje, nivel", [(PASAJEROS[1], logging.WARNING), (REALES[0], logging.ERROR)])
def test_analisis_de_ai_overview_mismo_criterio(flask_app, monkeypatch, caplog, mensaje, nivel):
    """analyze_single_keyword_ai_impact convierte el error de SerpAPI en excepción y lo registra."""
    import app as modulo_app
    monkeypatch.setenv("SERPAPI_KEY", "clave-de-prueba")
    monkeypatch.setattr(modulo_app.ai_cache, "get_cached_analysis", lambda *a: None)
    monkeypatch.setattr(modulo_app.ai_cache, "cache_analysis", lambda *a, **k: None)
    monkeypatch.setattr(modulo_app, "get_serp_json", lambda params: {"error": mensaje})
    with caplog.at_level(logging.WARNING), pytest.raises(Exception) as excinfo:
        modulo_app.analyze_single_keyword_ai_impact("kw", "https://example.com/", "esp")
    assert _niveles(caplog, "Error analizando keyword") == [nivel]
    # El lote de AI Overview vuelve a registrar esa excepción con el mismo criterio
    assert modulo_app.nivel_error_serpapi(excinfo.value) == nivel
    fuente = open(modulo_app.__file__, encoding="utf-8").read()
    assert "logger.log(nivel_error_serpapi(e), error_msg)" in fuente


@pytest.mark.parametrize("fallos, nivel_final", [(1, None), (3, logging.ERROR)])
def test_middleware_reintento_es_warning_y_fallo_definitivo_error(flask_app, monkeypatch, caplog, fallos, nivel_final):
    """Una excepción que se reintenta es WARNING; si se agotan los intentos, ERROR."""
    import quota_middleware
    llamadas = {"n": 0}

    class Busqueda:
        def __init__(self, params): pass

        def get_dict(self):
            llamadas["n"] += 1
            if llamadas["n"] <= fallos:
                raise RuntimeError("Read timeout from SerpAPI")
            return {"organic_results": []}

    monkeypatch.setattr(quota_middleware, "GoogleSearch", Busqueda)
    monkeypatch.setattr(quota_middleware.time, "sleep", lambda s: None)
    with caplog.at_level(logging.WARNING, logger="quota_middleware"):
        quota_middleware._execute_serp_call({"q": "kw"}, "json")
    niveles = _niveles(caplog, "Error en llamada SerpAPI")
    assert niveles[:-1] == [logging.WARNING] * (len(niveles) - 1)
    if nivel_final is None:
        assert niveles == [logging.WARNING]
    else:
        assert niveles[-1] == logging.ERROR
