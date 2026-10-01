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
    "Your account has been suspended.",
    "Unsupported `xx` gl parameter.",
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
