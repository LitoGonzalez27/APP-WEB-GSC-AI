"""
Tests del manejo de enlaces de redirección google.com/goto en SERPs.

Cubre:
    - Detección de enlaces intermedios de Google (goto / url / interstitial)
    - Resolución del destino real cuando el parámetro es descifrable
    - Comportamiento seguro cuando el token es opaco (nunca "google.com")
    - Integración con los extractores de dominio compartidos
      (services.utils, manual_ai, ai_mode_projects)
    - urls_match: sin falsos positivos hacia google.com y sin perder
      matches cuando el redirect es resoluble
    - Escaneo/telemetría de respuestas completas de SerpAPI

No requiere red ni base de datos.
"""

import logging
import os

import pytest

# Igual que el resto de tests del repo: BD dummy para poder importar database.py
os.environ.setdefault("DATABASE_URL", "postgresql://dummy:dummy@localhost:5432/dummy")

from services.google_redirects import (
    clean_serp_link,
    domain_from_serp_link,
    is_google_redirect_link,
    log_redirect_stats,
    resolve_google_redirect,
    scan_serp_payload,
)
from services.utils import extract_domain, urls_match


# URLs de ejemplo reutilizadas en varios tests
GOTO_OPAQUE = "https://www.google.com/goto?url=AbC123xYz"
GOTO_RESOLVABLE = "https://www.google.com/goto?url=https%3A%2F%2Fwww.clinica.com%2Ftratamientos"
URL_CLASSIC = "https://www.google.com/url?q=https://ejemplo.com/pagina"
NORMAL = "https://www.ejemplo.com/pagina"


class TestIsGoogleRedirectLink:

    @pytest.mark.parametrize("url", [
        GOTO_OPAQUE,
        GOTO_RESOLVABLE,
        URL_CLASSIC,
        "https://google.com/goto?url=x",
        "https://google.es/goto?url=x",
        "https://www.google.co.uk/goto?url=x",
        "https://www.google.com.mx/goto/extra?url=x",
        "https://www.google.com/interstitial?url=x",
        "www.google.com/goto?url=x",  # sin esquema
    ])
    def test_detecta_redirects_de_google(self, url):
        assert is_google_redirect_link(url) is True

    @pytest.mark.parametrize("url", [
        NORMAL,
        "https://www.google.com/search?q=hola",
        "https://www.google.com/maps/place/x",
        "https://ejemplo.com/goto?url=x",       # /goto pero no es Google
        "https://gotogate.com/ofertas",          # 'goto' en el dominio
        "https://migoogle.com/goto?url=x",       # host que contiene 'google'
        "",
        None,
        123,
    ])
    def test_no_detecta_urls_normales(self, url):
        assert is_google_redirect_link(url) is False


class TestResolveGoogleRedirect:

    def test_resuelve_parametro_url_codificado(self):
        assert resolve_google_redirect(GOTO_RESOLVABLE) == "https://www.clinica.com/tratamientos"

    def test_resuelve_parametro_q_clasico(self):
        assert resolve_google_redirect(URL_CLASSIC) == "https://ejemplo.com/pagina"

    def test_resuelve_destino_sin_esquema(self):
        url = "https://www.google.com/goto?url=ejemplo.com/pagina"
        assert resolve_google_redirect(url) == "https://ejemplo.com/pagina"

    def test_resuelve_doble_encoding(self):
        url = "https://www.google.com/goto?url=https%253A%252F%252Fejemplo.com%252Fx"
        # parse_qs decodifica una vez -> queda https%3A%2F%2F... -> se decodifica otra vez
        assert resolve_google_redirect(url) == "https://ejemplo.com/x"

    def test_token_opaco_devuelve_none(self):
        assert resolve_google_redirect(GOTO_OPAQUE) is None

    def test_sin_query_devuelve_none(self):
        assert resolve_google_redirect("https://www.google.com/goto") is None

    def test_destino_google_devuelve_none(self):
        # Un redirect cuyo "destino" es el propio Google no aporta dominio útil
        url = "https://www.google.com/goto?url=https%3A%2F%2Fwww.google.com%2Fx"
        assert resolve_google_redirect(url) is None

    def test_url_normal_devuelve_none(self):
        assert resolve_google_redirect(NORMAL) is None

    def test_token_opaco_con_punto_no_fabrica_dominio(self):
        # Un token con un punto casual no debe convertirse en un "dominio"
        assert resolve_google_redirect("https://www.google.com/goto?url=AbC12.xYz") is None

    def test_destino_sin_codificar_con_parametros_no_se_trunca(self):
        # parse_qs partiría el destino en el primer '&'; debe conservarse entero
        url = "https://www.google.com/url?q=https://ejemplo.com/pag?a=1&b=2&sa=U"
        assert resolve_google_redirect(url) == "https://ejemplo.com/pag?a=1&b=2"

    def test_destino_sin_codificar_corta_tracking_de_google(self):
        url = "https://www.google.com/url?q=https://ejemplo.com/p?x=1&ved=abc&usg=z"
        assert resolve_google_redirect(url) == "https://ejemplo.com/p?x=1"


class TestCleanSerpLink:

    def test_url_normal_pasa_sin_cambios(self):
        assert clean_serp_link(NORMAL) == NORMAL

    def test_redirect_resoluble_devuelve_destino(self):
        assert clean_serp_link(GOTO_RESOLVABLE) == "https://www.clinica.com/tratamientos"

    def test_redirect_opaco_devuelve_none(self):
        assert clean_serp_link(GOTO_OPAQUE) is None

    def test_entrada_vacia(self):
        assert clean_serp_link("") is None
        assert clean_serp_link(None) is None


class TestDomainFromSerpLink:

    def test_dominio_normal(self):
        assert domain_from_serp_link(NORMAL) == "ejemplo.com"

    def test_redirect_resoluble(self):
        assert domain_from_serp_link(GOTO_RESOLVABLE) == "clinica.com"

    def test_redirect_opaco_nunca_google(self):
        assert domain_from_serp_link(GOTO_OPAQUE) == ""

    def test_quita_puerto(self):
        assert domain_from_serp_link("https://ejemplo.com:8080/x") == "ejemplo.com"


class TestExtractDomainIntegracion:
    """extract_domain (services.utils) protege urls_match y toda la app."""

    def test_url_normal_sin_cambios(self):
        assert extract_domain("https://www.ejemplo.com/pagina") == "ejemplo.com"

    def test_goto_opaco_devuelve_vacio(self):
        # Antes devolvía 'google.com' y contaminaba competidores
        assert extract_domain(GOTO_OPAQUE) == ""

    def test_goto_resoluble_devuelve_destino(self):
        assert extract_domain(GOTO_RESOLVABLE) == "clinica.com"

    def test_google_normal_sigue_funcionando(self):
        # Solo los paths de redirección se tratan como especiales
        assert extract_domain("https://www.google.com/maps") == "google.com"


class TestUrlsMatchIntegracion:

    def test_goto_opaco_no_matchea_nada(self):
        assert urls_match(GOTO_OPAQUE, "sc-domain:clinica.com") is False

    def test_goto_opaco_no_matchea_propiedad_google(self):
        # Regresión clave: el goto no debe contar como google.com
        assert urls_match(GOTO_OPAQUE, "sc-domain:google.com") is False

    def test_goto_resoluble_matchea_dominio(self):
        assert urls_match(GOTO_RESOLVABLE, "sc-domain:clinica.com") is True

    def test_goto_resoluble_matchea_propiedad_url(self):
        assert urls_match(GOTO_RESOLVABLE, "https://www.clinica.com/") is True

    def test_matching_normal_intacto(self):
        assert urls_match("https://www.ejemplo.com/p", "sc-domain:ejemplo.com") is True
        assert urls_match("https://blog.ejemplo.com/p", "sc-domain:ejemplo.com") is True
        assert urls_match("https://otro.com/p", "sc-domain:ejemplo.com") is False


class TestHelpersDeModulos:
    """Los extractores locales de manual_ai y ai_mode_projects quedan protegidos."""

    def test_manual_ai_helper(self):
        from manual_ai.utils.helpers import extract_domain_from_url
        assert extract_domain_from_url(NORMAL) == "ejemplo.com"
        assert extract_domain_from_url(GOTO_OPAQUE) == ""
        assert extract_domain_from_url(GOTO_RESOLVABLE) == "clinica.com"

    def test_ai_mode_helper(self):
        from ai_mode_projects.utils.helpers import extract_domain_from_url
        assert extract_domain_from_url(NORMAL) == "ejemplo.com"
        assert extract_domain_from_url(GOTO_OPAQUE) == ""
        assert extract_domain_from_url(GOTO_RESOLVABLE) == "clinica.com"


class TestScanSerpPayload:

    def _payload_con_goto(self):
        return {
            "organic_results": [
                {"link": NORMAL},
                {"link": GOTO_OPAQUE},
            ],
            "ai_overview": {
                "references": [
                    {"link": GOTO_RESOLVABLE},
                    {"link": GOTO_OPAQUE},
                    {"link": "https://otra.com/x"},
                ],
                "sources": [{"link": GOTO_OPAQUE}],
            },
            "featured_snippet": {"link": NORMAL},
            "answer_box": {"link": GOTO_OPAQUE},
            "local_results": [{"link": NORMAL}],
        }

    def test_cuenta_redirects_por_seccion(self):
        stats = scan_serp_payload(self._payload_con_goto())
        assert stats["total_links"] == 9
        assert stats["redirects"] == 5
        assert stats["resolved"] == 1
        assert stats["unresolved"] == 4
        assert stats["clean"] is False
        assert stats["sections"]["organic_results"] == {"resolved": 0, "unresolved": 1}
        assert stats["sections"]["ai_overview.references"] == {"resolved": 1, "unresolved": 1}
        assert stats["sections"]["ai_overview.sources"] == {"resolved": 0, "unresolved": 1}
        assert stats["sections"]["answer_box"] == {"resolved": 0, "unresolved": 1}

    def test_payload_ai_mode_con_references_en_raiz(self):
        # Google AI Mode: {text_blocks, references, inline_images}
        stats = scan_serp_payload({
            "text_blocks": [{"type": "paragraph", "snippet": "x"}],
            "references": [
                {"link": GOTO_OPAQUE},
                {"link": NORMAL},
            ],
        })
        assert stats["redirects"] == 1
        assert stats["sections"]["references"] == {"resolved": 0, "unresolved": 1}

    def test_payload_limpio(self):
        stats = scan_serp_payload({
            "organic_results": [{"link": NORMAL}],
            "ai_overview": {"references": [{"link": "https://otra.com/x"}]},
        })
        assert stats["clean"] is True
        assert stats["redirects"] == 0

    def test_payload_malformado_no_rompe(self):
        assert scan_serp_payload({})["clean"] is True
        assert scan_serp_payload(None)["clean"] is True
        assert scan_serp_payload({"organic_results": "no-es-lista"})["clean"] is True
        assert scan_serp_payload({"organic_results": [None, "x", {}]})["clean"] is True


class TestLogRedirectStats:

    def test_avisa_en_logs_cuando_hay_goto(self, caplog):
        payload = {"organic_results": [{"link": GOTO_OPAQUE}]}
        with caplog.at_level(logging.WARNING, logger="services.google_redirects"):
            stats = log_redirect_stats(payload, context="mi keyword")
        assert stats["redirects"] == 1
        assert any("GOOGLE GOTO" in rec.message for rec in caplog.records)
        assert any("mi keyword" in rec.message for rec in caplog.records)

    def test_silencioso_con_payload_limpio(self, caplog):
        payload = {"organic_results": [{"link": NORMAL}]}
        with caplog.at_level(logging.WARNING, logger="services.google_redirects"):
            stats = log_redirect_stats(payload)
        assert stats["clean"] is True
        assert not caplog.records
