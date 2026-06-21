"""
Tests del servicio de comparación histórica de AI Overview (Manual AI).

Cubre la lógica de agregación de
`StatisticsService.get_ai_overview_historical_comparison` con una BD simulada
(sin conexión real): clasificación gained / lost / maintained, deltas de
posición y URLs afectadas, tanto para el dominio del proyecto como para
competidores. También cubre los casos borde (sin proyecto, una sola fecha).

Ejecutar:  python3 -m pytest tests/test_manual_ai_historical.py -q
"""

import os
import importlib
from datetime import date

os.environ.setdefault("DATABASE_URL", "postgresql://dummy:dummy@localhost:5432/dummy")

import pytest  # noqa: E402

FIRST = date(2026, 5, 22)
LAST = date(2026, 6, 21)


class _Row(dict):
    """Fila tipo RealDictRow: None para claves ausentes (no KeyError)."""
    def __getitem__(self, k):
        return super().get(k)


def _r(**kw):
    return _Row(**kw)


class _FakeCursor:
    """Cursor que decide qué devolver según la SQL ejecutada."""

    def __init__(self, scenario):
        self.scenario = scenario
        self._mode = None

    def execute(self, sql, params=None):
        s = sql or ""
        if "MIN(analysis_date)" in s:
            self._mode = "dates"
        elif "manual_ai_global_domains" in s:
            self._mode = "global_domains"
        elif "manual_ai_projects" in s:
            self._mode = "project"
        elif "manual_ai_results" in s:
            self._mode = "results"
        else:
            self._mode = None

    def fetchone(self):
        if self._mode == "project":
            return self.scenario["project"]
        if self._mode == "dates":
            return self.scenario["dates"]
        return None

    def fetchall(self):
        if self._mode == "results":
            return self.scenario["results"]
        if self._mode == "global_domains":
            return self.scenario["global_domains"]
        return []

    def close(self):
        pass


class _FakeConn:
    def __init__(self, scenario):
        self.scenario = scenario

    def cursor(self, *a, **k):
        return _FakeCursor(self.scenario)

    def close(self):
        pass


def _patch_db(monkeypatch, scenario):
    mod = importlib.import_module("manual_ai.services._statistics.historical")
    monkeypatch.setattr(mod, "get_db_connection", lambda: _FakeConn(scenario))


def _full_scenario():
    """Escenario rico: ganadas, perdidas y mantenidas para dominio y competidor."""
    return {
        "project": _r(domain="example.com", selected_competitors=["comp.com"]),
        "dates": _r(first_date=FIRST, last_date=LAST, date_count=4),
        "results": [
            # first_date — dominio propio menciona kw1 (pos3) y kw2 (pos5)
            _r(keyword_id=1, keyword="seo tips", analysis_date=FIRST, domain_mentioned=True, domain_position=3),
            _r(keyword_id=2, keyword="ai search", analysis_date=FIRST, domain_mentioned=True, domain_position=5),
            _r(keyword_id=3, keyword="serp", analysis_date=FIRST, domain_mentioned=False, domain_position=None),
            # last_date — kw1 mejora (pos2), kw3 nueva (pos4), kw2 ya no aparece
            _r(keyword_id=1, keyword="seo tips", analysis_date=LAST, domain_mentioned=True, domain_position=2),
            _r(keyword_id=3, keyword="serp", analysis_date=LAST, domain_mentioned=True, domain_position=4),
            _r(keyword_id=2, keyword="ai search", analysis_date=LAST, domain_mentioned=False, domain_position=None),
        ],
        "global_domains": [
            # Dominio propio (is_project_domain=True) con URLs
            _r(keyword_id=1, analysis_date=FIRST, detected_domain="example.com", domain_position=3,
               domain_source_url="https://example.com/seo", is_project_domain=True),
            _r(keyword_id=2, analysis_date=FIRST, detected_domain="example.com", domain_position=5,
               domain_source_url="https://example.com/ai", is_project_domain=True),
            _r(keyword_id=1, analysis_date=LAST, detected_domain="example.com", domain_position=2,
               domain_source_url="https://example.com/seo", is_project_domain=True),
            _r(keyword_id=3, analysis_date=LAST, detected_domain="example.com", domain_position=4,
               domain_source_url="https://example.com/serp", is_project_domain=True),
            # Competidor comp.com: mantiene kw1, gana kw2
            _r(keyword_id=1, analysis_date=FIRST, detected_domain="comp.com", domain_position=1,
               domain_source_url="https://comp.com/a", is_project_domain=False),
            _r(keyword_id=1, analysis_date=LAST, detected_domain="comp.com", domain_position=1,
               domain_source_url="https://comp.com/a", is_project_domain=False),
            _r(keyword_id=2, analysis_date=LAST, detected_domain="comp.com", domain_position=2,
               domain_source_url="https://comp.com/b", is_project_domain=False),
        ],
    }


def _service():
    svc_mod = importlib.import_module("manual_ai.services.statistics_service")
    return svc_mod.StatisticsService()


def test_full_comparison_project_entity(monkeypatch):
    _patch_db(monkeypatch, _full_scenario())
    data = _service().get_ai_overview_historical_comparison(1, days=30)

    assert data["comparison_available"] is True
    assert data["compared_dates"] == {"previous": str(FIRST), "current": str(LAST)}
    assert data["date_count"] == 4
    assert data["project_domain"] == "example.com"

    # Entidad 0 = tu dominio
    proj = data["entities"][0]
    assert proj["type"] == "project"
    assert proj["summary"] == {
        "previous_count": 2,
        "current_count": 2,
        "gained_count": 1,
        "lost_count": 1,
        "maintained_count": 1,
    }

    gained = proj["gained"][0]
    assert gained["keyword"] == "serp"
    assert gained["position"] == 4
    assert gained["url"] == "https://example.com/serp"

    lost = proj["lost"][0]
    assert lost["keyword"] == "ai search"
    assert lost["previous_position"] == 5
    assert lost["previous_url"] == "https://example.com/ai"

    kept = proj["maintained"][0]
    assert kept["keyword"] == "seo tips"
    assert kept["previous_position"] == 3
    assert kept["current_position"] == 2
    assert kept["position_delta"] == -1  # negativo = mejora (sube en ranking)
    assert kept["url"] == "https://example.com/seo"


def test_full_comparison_competitor_entity(monkeypatch):
    _patch_db(monkeypatch, _full_scenario())
    data = _service().get_ai_overview_historical_comparison(1, days=30)

    comp = data["entities"][1]
    assert comp["type"] == "competitor"
    assert comp["domain"] == "comp.com"
    assert comp["summary"]["previous_count"] == 1
    assert comp["summary"]["current_count"] == 2
    assert comp["summary"]["gained_count"] == 1
    assert comp["summary"]["lost_count"] == 0
    assert comp["summary"]["maintained_count"] == 1

    assert comp["gained"][0]["keyword"] == "ai search"
    assert comp["gained"][0]["url"] == "https://comp.com/b"
    assert comp["maintained"][0]["keyword"] == "seo tips"


def test_single_date_not_enough_history(monkeypatch):
    scenario = _full_scenario()
    scenario["dates"] = _r(first_date=LAST, last_date=LAST, date_count=1)
    _patch_db(monkeypatch, scenario)

    data = _service().get_ai_overview_historical_comparison(1, days=7)
    assert data["comparison_available"] is False
    assert data["date_count"] == 1
    assert data["entities"] == []


def test_missing_project_returns_empty(monkeypatch):
    scenario = _full_scenario()
    scenario["project"] = None
    _patch_db(monkeypatch, scenario)

    data = _service().get_ai_overview_historical_comparison(999, days=30)
    assert data["comparison_available"] is False
    assert data["entities"] == []


def test_normalize_and_match_helpers():
    mod = importlib.import_module("manual_ai.services._statistics.historical")
    assert mod._normalize_domain("https://www.Example.com/path") == "example.com"
    assert mod._normalize_domain(None) == ""
    assert mod._domains_match("comp.com", "comp.com") is True
    assert mod._domains_match("blog.comp.com", "comp.com") is True
    assert mod._domains_match("comp.com", "other.com") is False
