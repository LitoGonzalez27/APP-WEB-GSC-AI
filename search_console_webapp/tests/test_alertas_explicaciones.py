"""
Explicación en lenguaje llano de los avisos de errores por email (oct-2026).

El email llevaba solo logger, fichero, línea y mensaje técnico. Ahora empieza por
qué ha pasado, si afecta a los clientes, qué hacer y la gravedad; lo técnico va al final.

Ejecutar:  scripts/run_tests_docker.sh -q tests/test_alertas_explicaciones.py
"""

from datetime import datetime, timezone

import pytest

from services.alertas_errores import AvisoErrores
from services.alertas_explicaciones import REPETICIONES_PARA_REVISAR, explicar


def _pendiente(mensaje, veces=1, traza=''):
    ahora = datetime(2026, 10, 8, 6, 9, tzinfo=timezone.utc)
    return {'veces': veces, 'primera': ahora, 'ultima': ahora, 'nivel': 'ERROR', 'mensaje': mensaje, 'traza': traza}


@pytest.mark.parametrize("logger_name, fichero, mensaje, clave, gravedad", [
    ("quota_middleware", "quota_middleware.py",
     "Error en llamada SerpAPI (json): SerpAPI devolvió una respuesta vacía o que no es JSON "
     "(Expecting value: line 1 column 1 (char 0))", "serpapi_no_json", "sin_accion"),
    # el texto de antes del arreglo también se reconoce
    ("services.serp_service", "serp_service.py",
     "❌ Error en SerpAPI: {'error': 'Expecting value: line 1 column 1 (char 0)'}", "serpapi_no_json", "sin_accion"),
    ("services.serp_service", "serp_service.py",
     "❌ Error en SerpAPI: {'error': 'Your account has run out of searches.'}", "serpapi_sin_saldo", "urgente"),
    ("quota_middleware", "quota_middleware.py",
     "SerpAPI error: Invalid API key. Your API key should be here", "serpapi_clave", "urgente"),
    ("services.llm_providers.openai_provider", "openai_provider.py",
     "Error code: 429 - {'error': {'type': 'insufficient_quota'}}", "ia_sin_credito", "urgente"),
    ("stripe_webhooks", "stripe_webhooks.py",
     "❌ Invalid signature with provided secrets: No signatures found", "stripe_firma", "urgente"),
    ("manual_ai.services.analysis_service", "analysis_service.py",
     "Failed to get database connection for project 12", "bd_conexion", "revisar"),
    ("services.llm_providers.anthropic_provider", "anthropic_provider.py",
     "Error code: 529 - overloaded_error", "servicio_saturado", "sin_accion"),
    ("auth", "auth.py", "Error refrescando token: invalid_grant: Token has been expired or revoked.",
     "google_acceso", "sin_accion"),
])
def test_errores_conocidos(logger_name, fichero, mensaje, clave, gravedad):
    x = explicar(logger_name, fichero, '', mensaje)
    assert (x.clave, x.gravedad) == (clave, gravedad)
    assert x.titulo and x.que_paso and x.impacto and x.que_hacer


def test_el_proveedor_sin_credito_sale_en_el_titulo():
    x = explicar("services.llm_providers.anthropic_provider", "anthropic_provider.py", '',
                 "anthropic: Your credit balance is too low to access the Anthropic API")
    assert x.titulo == "Anthropic (Claude) se ha quedado sin crédito"


def test_un_numero_cualquiera_no_es_un_429():
    x = explicar("manual_ai.services.analysis_service", "analysis_service.py", '', "Error analyzing project 429: KeyError")
    assert x.clave.startswith("sin_catalogar")


def test_lo_desconocido_lo_dice_y_nombra_la_zona():
    x = explicar("manual_ai.services.analysis_service", "analysis_service.py", 'KeyError', "algo raro")
    assert x.titulo == "Fallo no catalogado en Manual AI" and x.gravedad == "revisar"
    assert "no está catalogado" in x.que_paso and "Claude" in x.que_hacer


def test_lo_que_no_importa_pero_se_repite_mucho_sube_a_revisar():
    x = explicar("services.llm_providers.anthropic_provider", "anthropic_provider.py", '', "Request timed out",
                 veces=REPETICIONES_PARA_REVISAR)
    assert x.gravedad == "revisar" and str(REPETICIONES_PARA_REVISAR) in x.que_hacer


def test_explicar_nunca_lanza():
    assert explicar(None, None, None, None).gravedad == "revisar"


def test_email_del_8_oct_explicado_primero_y_lo_tecnico_al_final():
    """Las dos líneas del email real (middleware + servicio) son una sola incidencia."""
    h = AvisoErrores(lambda a, b: None, "production")
    pendientes = {
        ("quota_middleware", "quota_middleware.py", 452, ''): _pendiente(
            "Error en llamada SerpAPI (json): Expecting value: line 1 column 1 (char 0)"),
        ("services.serp_service", "serp_service.py", 91, ''): _pendiente(
            "❌ Error en SerpAPI: {'error': 'Expecting value: line 1 column 1 (char 0)'}"),
    }
    asunto, html = h._componer(pendientes)
    assert asunto == "[PRODUCTION] Clicandseo · Sin acción: SerpAPI respondió mal a una búsqueda"
    assert html.count("Qué ha pasado") == 1 and "Ha pasado una vez" in html
    assert "no hace falta hacer nada" in html
    # la explicación va antes que el detalle técnico, y el detalle sigue completo
    assert html.index("Qué ha pasado") < html.index("Detalle técnico") < html.index("quota_middleware.py:452")
    assert "2 error(es) de 2 tipo(s)" in html and "serp_service.py:91" in html


def test_lo_urgente_va_primero_y_en_el_asunto():
    h = AvisoErrores(lambda a, b: None, "production")
    pendientes = {
        ("auth", "auth.py", 10, ''): _pendiente("invalid_grant", veces=3),
        ("stripe_webhooks", "stripe_webhooks.py", 49, ''): _pendiente(
            "❌ Invalid signature with provided secrets: x"),
    }
    asunto, html = h._componer(pendientes)
    assert asunto == ("[PRODUCTION] Clicandseo · Urgente: No se pudo verificar un aviso de pago de Stripe "
                      "(y 1 aviso más)")
    assert "hay algo urgente" in html
    assert html.index("aviso de pago de Stripe") < html.index("Google rechazó el acceso")


def test_las_explicaciones_se_escapan():
    h = AvisoErrores(lambda a, b: None, "staging")
    _asunto, html = h._componer({("app", "app.py", 1, ''): _pendiente("<script>x</script>")})
    assert "<script>" not in html and "(staging)" in html
