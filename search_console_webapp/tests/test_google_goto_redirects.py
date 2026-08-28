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


# ---------------------------------------------------------------------------
# Resolución activa (HTTP + metadata): capa que recupera las URLs reales en
# vez de descartar las referencias con token opaco. Sin red: sesión falseada.
# ---------------------------------------------------------------------------

import services.google_redirects as gr
from services.google_redirects import (
    _domain_from_reference_metadata,
    resolve_payload_redirects,
    resolve_redirect_via_http,
    sanitize_serp_response,
)

GOTO_OPAQUE_2 = "https://www.google.es/goto?url=CAESotroTokenOpaco123"
REAL_DEST = "https://www.esic.edu/rethink/canales-de-distribucion"


class _FakeResponse:
    def __init__(self, status_code, location=None):
        self.status_code = status_code
        self.headers = {"Location": location} if location else {}


class _FakeSession:
    """Devuelve respuestas por URL (dict) o en secuencia (list)."""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, url, allow_redirects=False, timeout=None, proxies=None):
        self.calls.append({"url": url, "proxies": proxies})
        if isinstance(self.responses, dict):
            resp = self.responses[url]
        else:
            resp = self.responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp


@pytest.fixture()
def fake_http(monkeypatch):
    """Instala una sesión falsa y limpia la caché HTTP antes y después."""

    def _install(responses):
        session = _FakeSession(responses)
        monkeypatch.setattr(gr, "_http_session", session)
        return session

    gr._clear_http_cache()
    yield _install
    gr._clear_http_cache()


class TestResolveRedirectViaHttp:

    def test_302_devuelve_location(self, fake_http):
        fake_http({GOTO_OPAQUE: _FakeResponse(302, REAL_DEST)})
        assert resolve_redirect_via_http(GOTO_OPAQUE) == REAL_DEST

    def test_location_relativo_se_absolutiza(self, fake_http):
        session = fake_http([
            _FakeResponse(302, "/url?q=https://ejemplo.com/pagina"),
        ])
        # /url?q=... es a su vez un redirect de Google descifrable
        assert resolve_redirect_via_http(GOTO_OPAQUE) == "https://ejemplo.com/pagina"
        assert len(session.calls) == 1

    def test_multi_hop_goto_a_goto(self, fake_http):
        fake_http({
            GOTO_OPAQUE: _FakeResponse(302, GOTO_OPAQUE_2),
            GOTO_OPAQUE_2: _FakeResponse(302, REAL_DEST),
        })
        assert resolve_redirect_via_http(GOTO_OPAQUE) == REAL_DEST

    def test_200_sin_redirect_es_none(self, fake_http):
        fake_http({GOTO_OPAQUE: _FakeResponse(200)})
        assert resolve_redirect_via_http(GOTO_OPAQUE) is None

    def test_error_de_red_es_none(self, fake_http):
        fake_http({GOTO_OPAQUE: ConnectionError("boom")})
        assert resolve_redirect_via_http(GOTO_OPAQUE) is None

    def test_consent_google_es_bloqueo(self, fake_http):
        fake_http({GOTO_OPAQUE: _FakeResponse(302, "https://consent.google.com/m?continue=x")})
        assert resolve_redirect_via_http(GOTO_OPAQUE) is None

    def test_cachea_aciertos(self, fake_http):
        session = fake_http({GOTO_OPAQUE: _FakeResponse(302, REAL_DEST)})
        assert resolve_redirect_via_http(GOTO_OPAQUE) == REAL_DEST
        assert resolve_redirect_via_http(GOTO_OPAQUE) == REAL_DEST
        assert len(session.calls) == 1

    def test_cachea_fallos(self, fake_http):
        session = fake_http({GOTO_OPAQUE: _FakeResponse(200)})
        assert resolve_redirect_via_http(GOTO_OPAQUE) is None
        assert resolve_redirect_via_http(GOTO_OPAQUE) is None
        assert len(session.calls) == 1

    def test_desactivable_por_env(self, fake_http, monkeypatch):
        session = fake_http({GOTO_OPAQUE: _FakeResponse(302, REAL_DEST)})
        monkeypatch.setenv("GOTO_HTTP_RESOLUTION_ENABLED", "false")
        assert resolve_redirect_via_http(GOTO_OPAQUE) is None
        assert session.calls == []

    def test_url_normal_no_se_toca(self, fake_http):
        session = fake_http({})
        assert resolve_redirect_via_http(NORMAL) is None
        assert session.calls == []

    def test_429_reintenta_por_proxy(self, fake_http, monkeypatch):
        monkeypatch.setenv("SCANNER_PROXY_URL", "http://proxy.interno:3128")
        session = fake_http([
            _FakeResponse(429),
            _FakeResponse(302, REAL_DEST),
        ])
        assert resolve_redirect_via_http(GOTO_OPAQUE) == REAL_DEST
        assert session.calls[0]["proxies"] is None
        assert session.calls[1]["proxies"] == {
            "http": "http://proxy.interno:3128",
            "https": "http://proxy.interno:3128",
        }


class TestDomainFromReferenceMetadata:

    def test_source_es_dominio(self):
        assert _domain_from_reference_metadata({"source": "esic.edu"}) == "esic.edu"
        assert _domain_from_reference_metadata(
            {"source": "www.plangeneralcontable.com"}
        ) == "plangeneralcontable.com"
        assert _domain_from_reference_metadata(
            {"source": "sede.agenciatributaria.gob.es"}
        ) == "sede.agenciatributaria.gob.es"

    def test_source_marca_cae_a_source_icon(self):
        ref = {
            "source": "ESIC University",
            "source_icon": (
                "https://encrypted-tbn0.gstatic.com/faviconV2"
                "?url=https://www.esic.edu&client=AIM&size=128&type=FAVICON"
            ),
        }
        assert _domain_from_reference_metadata(ref) == "esic.edu"

    def test_thumbnail_gstatic_sin_url_no_sirve(self):
        ref = {
            "source": "Una Marca",
            "thumbnail": "https://encrypted-tbn1.gstatic.com/images?q=tbn:abc123",
        }
        assert _domain_from_reference_metadata(ref) == ""

    def test_source_google_se_descarta(self):
        assert _domain_from_reference_metadata({"source": "google.com"}) == ""

    def test_sin_metadata(self):
        assert _domain_from_reference_metadata({}) == ""
        assert _domain_from_reference_metadata(None) == ""


class TestResolvePayloadRedirects:

    def test_cadena_completa_de_recuperacion(self, fake_http):
        fake_http({
            GOTO_OPAQUE: _FakeResponse(302, REAL_DEST),   # capa HTTP
            GOTO_OPAQUE_2: _FakeResponse(200),            # HTTP falla → metadata
        })
        goto_sin_nada = "https://www.google.com/goto?url=CAESduplicadoSinMetadata"
        payload = {
            "ai_overview": {
                "references": [
                    {"link": GOTO_RESOLVABLE},                      # capa token
                    {"link": GOTO_OPAQUE, "source": "ESIC"},        # capa HTTP
                    {"link": GOTO_OPAQUE_2, "source": "bbva.es"},   # capa metadata
                    {"link": NORMAL},                               # intacto
                ],
            },
            "organic_results": [{"link": goto_sin_nada}],           # irresoluble
        }
        # el goto irresoluble también pasa por HTTP y falla
        gr._http_session.responses[goto_sin_nada] = _FakeResponse(200)

        stats = resolve_payload_redirects(payload, context="kw")

        refs = payload["ai_overview"]["references"]
        assert refs[0]["link"] == "https://www.clinica.com/tratamientos"
        assert refs[0]["google_goto_original"] == GOTO_RESOLVABLE
        assert refs[1]["link"] == REAL_DEST
        assert refs[2]["link"] == "https://bbva.es/"
        assert refs[2]["google_goto_domain_only"] is True
        assert refs[3]["link"] == NORMAL
        assert "google_goto_original" not in refs[3]
        assert payload["organic_results"][0]["link"] == goto_sin_nada  # intacto
        assert stats == {
            "redirects": 4, "via_token": 1, "via_http": 1,
            "via_metadata": 1, "unresolved": 1,
        }

    def test_walk_generico_alcanza_dicts_anidados(self, fake_http):
        fake_http({GOTO_OPAQUE: _FakeResponse(302, REAL_DEST)})
        payload = {
            "text_blocks": [
                {"type": "list", "list": [{"reference": {"link": GOTO_OPAQUE}}]},
            ],
        }
        stats = resolve_payload_redirects(payload)
        assert payload["text_blocks"][0]["list"][0]["reference"]["link"] == REAL_DEST
        assert stats["via_http"] == 1

    def test_payload_sin_redirects_no_llama_http(self, fake_http):
        session = fake_http({})
        payload = {"organic_results": [{"link": NORMAL}]}
        stats = resolve_payload_redirects(payload)
        assert stats["redirects"] == 0
        assert session.calls == []
        assert payload["organic_results"][0]["link"] == NORMAL

    def test_payload_malformado_no_rompe(self, fake_http):
        fake_http({})
        assert resolve_payload_redirects(None)["redirects"] == 0
        assert resolve_payload_redirects({})["redirects"] == 0
        assert resolve_payload_redirects({"organic_results": "x"})["redirects"] == 0


class TestSanitizeSerpResponse:

    def test_alarma_y_resolucion(self, fake_http, caplog):
        fake_http({GOTO_OPAQUE: _FakeResponse(302, REAL_DEST)})
        payload = {"ai_overview": {"references": [{"link": GOTO_OPAQUE}]}}
        with caplog.at_level(logging.WARNING, logger="services.google_redirects"):
            stats = sanitize_serp_response(payload, context="kw")
        # la alarma de regresión del proveedor sigue saltando…
        assert any("GOOGLE GOTO" in rec.message for rec in caplog.records)
        # …y el payload queda saneado con la URL real
        assert payload["ai_overview"]["references"][0]["link"] == REAL_DEST
        assert stats["via_http"] == 1
