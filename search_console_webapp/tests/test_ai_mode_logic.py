"""
Tests de caracterización de la LÓGICA DE NEGOCIO de AI Mode.

Congela el comportamiento observable de las funciones puras críticas:
  - `AnalysisService._parse_ai_mode_response`: detección de marca en la respuesta
    de Google AI Mode (references + text_blocks), con word-boundaries (fix crítico
    contra falsos positivos tipo "quipu" ⊂ "quipus") y variación get<brand>→<brand>.
  - `ai_mode_projects.utils.helpers.extract_domain_from_url`.
  - `ai_mode_projects.utils.country_utils.convert_iso_to_internal_country`.

Funciones puras → no tocan BD. `_parse_ai_mode_response` no usa `self`, así que se
invoca sobre una instancia creada sin __init__ (object.__new__).

Ejecutar:  python3 -m pytest tests/test_ai_mode_logic.py -q
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://dummy:dummy@localhost:5432/dummy")

from ai_mode_projects.services.analysis_service import AnalysisService  # noqa: E402
from ai_mode_projects.utils.helpers import extract_domain_from_url  # noqa: E402
from ai_mode_projects.utils.country_utils import convert_iso_to_internal_country  # noqa: E402


def _parse(serp, brand):
    svc = object.__new__(AnalysisService)  # sin __init__ (el método no usa self)
    return svc._parse_ai_mode_response(serp, brand)


# ---------------------------------------------------------------------------
# _parse_ai_mode_response
# ---------------------------------------------------------------------------

def test_serp_invalido():
    r = _parse(None, "quipu")
    assert r["brand_mentioned"] is False
    assert r["total_sources"] == 0
    assert r["sentiment"] == "neutral"
    assert r.get("error") == "Invalid serp_data"


def test_brand_vacio():
    r = _parse({"references": []}, "")
    assert r["brand_mentioned"] is False
    assert r.get("error") == "No brand name configured"


def test_marca_en_dominio_de_referencia():
    serp = {"references": [
        {"index": 0, "link": "https://www.competidor.com/x", "title": "Comp", "source": "comp", "snippet": ""},
        {"index": 1, "link": "https://www.quipu.com/page", "title": "Quipu", "source": "Quipu", "snippet": ""},
    ]}
    r = _parse(serp, "quipu")
    assert r["brand_mentioned"] is True
    assert r["mention_position"] == 2          # index 1 → posición 1-based 2
    assert r["total_sources"] == 2


def test_marca_no_presente():
    serp = {"references": [
        {"index": 0, "link": "https://otra.com", "title": "Otra cosa", "source": "otra", "snippet": "nada"},
    ]}
    r = _parse(serp, "quipu")
    assert r["brand_mentioned"] is False
    assert r["total_sources"] == 1


def test_word_boundary_evita_falso_positivo():
    """'quipu' NO debe matchear dentro de 'quipus' (fix crítico de word boundaries)."""
    serp = {"references": [
        {"index": 0, "link": "https://example.com", "title": "los quipus andinos", "source": "example", "snippet": "quipus incas"},
    ]}
    r = _parse(serp, "quipu")
    assert r["brand_mentioned"] is False


def test_variacion_get_prefijo():
    """brand 'getquipu' debe detectar 'quipu' como palabra completa en el título."""
    serp = {"references": [
        {"index": 0, "link": "https://site.com", "title": "Quipu is the best tool", "source": "site", "snippet": ""},
    ]}
    r = _parse(serp, "getquipu")
    assert r["brand_mentioned"] is True
    assert r["mention_position"] == 1
    assert r["sentiment"] == "positive"        # 'best' ∈ positive_words


def test_marca_solo_en_text_blocks():
    """Mención solo en texto generado por IA → mention_position = 0."""
    serp = {
        "references": [],
        "text_blocks": [{"text": "I recommend Quipu, it is the best invoicing tool"}],
    }
    r = _parse(serp, "quipu")
    assert r["brand_mentioned"] is True
    assert r["mention_position"] == 0
    assert r["total_sources"] == 0


# ---------------------------------------------------------------------------
# utils
# ---------------------------------------------------------------------------

def test_extract_domain():
    assert extract_domain_from_url("https://www.example.com/page") == "example.com"
    assert extract_domain_from_url("") == ""
    assert extract_domain_from_url(None) == ""


def test_country_mapping():
    assert convert_iso_to_internal_country("ES") == "esp"
    assert convert_iso_to_internal_country("US") == "usa"
    assert convert_iso_to_internal_country("") == "esp"
    assert convert_iso_to_internal_country("ZZ") == "esp"
