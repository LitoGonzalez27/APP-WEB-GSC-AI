"""
Tests de caracterización de la LÓGICA de LLM Monitoring.

Congela el comportamiento de las funciones puras críticas de detección, que han
tenido bugs reales en el pasado (posición a partir de referencias [19], años "2025."
confundidos con posiciones):
  - `MultiLLMMonitoringService._detect_position_in_list`
  - `MultiLLMMonitoringService._analyze_sentiment_keywords`

Son funciones puras (solo usan `self` para logging), así que se invocan sobre una
instancia creada sin __init__ (object.__new__) — evita instanciar providers / API keys.

Ejecutar:  python3 -m pytest tests/test_llm_monitoring_logic.py -q
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://dummy:dummy@localhost:5432/dummy")

from services.llm_monitoring_service import MultiLLMMonitoringService  # noqa: E402


def _svc():
    return object.__new__(MultiLLMMonitoringService)


# ---------------------------------------------------------------------------
# _detect_position_in_list
# ---------------------------------------------------------------------------

def test_lista_numerada():
    r = _svc()._detect_position_in_list("1. Foo\n2. MyBrand\n3. Bar", ["mybrand"])
    assert r["appears_in_list"] is True
    assert r["position"] == 2
    assert r["total_items"] == 3
    assert r["detection_method"] == "numbered_list"


def test_ano_no_es_posicion():
    """'2025. MyBrand' NO debe detectarse como posición 2025 (MAX_VALID_POSITION=30)."""
    r = _svc()._detect_position_in_list("2025. MyBrand es una empresa.", ["mybrand"])
    assert r["position"] != 2025
    assert r["detection_method"] != "numbered_list"


def test_referencia_bibliografica_no_es_posicion():
    """'MyBrand[19]' NO debe dar posición 19 (patrón de referencias eliminado)."""
    r = _svc()._detect_position_in_list("MyBrand[19] is a great option here.", ["mybrand"])
    assert r["position"] != 19
    assert r["detection_method"] != "numbered_list"
    # cae a inferencia contextual (mención al inicio → posición 1)
    assert r["detection_method"] == "context_inference"


def test_marca_no_presente():
    r = _svc()._detect_position_in_list("This text talks about other companies.", ["mybrand"])
    assert r["appears_in_list"] is False
    assert r["position"] is None
    assert r["detection_method"] is None


def test_inferencia_contextual_temprana():
    text = "MyBrand " + ("x " * 200)  # mención al principio de un texto largo
    r = _svc()._detect_position_in_list(text, ["mybrand"])
    assert r["detection_method"] == "context_inference"
    assert r["position"] == 1


# ---------------------------------------------------------------------------
# _analyze_sentiment_keywords
# ---------------------------------------------------------------------------

def test_sentimiento_positivo():
    r = _svc()._analyze_sentiment_keywords(["MyBrand is excellent and the best option"])
    assert r["sentiment"] == "positive"
    assert r["score"] > 0.5


def test_sentimiento_negativo():
    r = _svc()._analyze_sentiment_keywords(["MyBrand is terrible, avoid it"])
    assert r["sentiment"] == "negative"
    assert r["score"] < 0.5


def test_sentimiento_neutral():
    r = _svc()._analyze_sentiment_keywords(["MyBrand is a company based in Madrid"])
    assert r["sentiment"] == "neutral"
    assert r["score"] == 0.5
