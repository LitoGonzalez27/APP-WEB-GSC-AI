"""
Cifra principal de las tarjetas de proyecto (/api/project-cards/kpis).

Las tres listas de proyectos (AI Overview, AI Mode, LLM Visibility) piden su
cifra grande a este endpoint, que reutiliza los adapters de AI Visibility
Summary. Lo crítico: los adapters consultan por id sin comprobar permisos,
así que el endpoint SOLO puede devolver proyectos que el usuario puede ver.
"""

import os
import types

import pytest
from flask import Flask

os.environ.setdefault("DATABASE_URL", "postgresql://dummy:dummy@localhost:5432/dummy")

import project_cards_routes as pcr  # noqa: E402


@pytest.fixture
def app():
    app = Flask(__name__)
    app.register_blueprint(pcr.project_cards_bp)
    return app


def _call(app, query, monkeypatch, visibles, adapter_result=None, adapter_error=False):
    monkeypatch.setattr(pcr, "get_current_user", lambda: {"id": 7, "plan": "business"})
    import services.project_access_service as pas
    vistos = []

    def can_view(user_id, module, pid):
        vistos.append((user_id, module, pid))
        return pid in visibles
    monkeypatch.setattr(pas, "user_can_view_project", can_view)

    llamadas = []

    def summary(pid, period, include_competitors=True):
        llamadas.append((pid, period, include_competitors))
        if adapter_error:
            raise RuntimeError("boom")
        return adapter_result(pid) if adapter_result else {"available": True, "visibility_pct": 41.2,
                                                           "visibility_delta": -3.4, "last_date": "2026-10-08"}
    monkeypatch.setattr(pcr, "_adapter", lambda module: types.SimpleNamespace(get_channel_summary=summary))

    with app.test_request_context(f"/api/project-cards/kpis?{query}"):
        resp = pcr.get_kpis.__wrapped__()
    resp = resp if not isinstance(resp, tuple) else resp[0]
    return resp.get_json(), vistos, llamadas


def test_solo_devuelve_proyectos_visibles_y_sin_competidores(app, monkeypatch):
    data, vistos, llamadas = _call(app, "module=llm&ids=1,2,3", monkeypatch, visibles={1, 3})
    assert data["success"] is True
    assert set(data["kpis"]) == {"1", "3"}                     # el 2 no es suyo
    assert {m for _, m, _ in vistos} == {"llm_monitoring"}      # nombre del módulo de permisos
    assert all(inc is False for _, _, inc in llamadas)          # sin la parte cara
    assert all(p == "30" for _, p, _ in llamadas)
    assert data["kpis"]["1"] == {"available": True, "reason": None, "value": 41.2,
                                 "delta": -3.4, "last_date": "2026-10-08"}


def test_modulo_desconocido_y_ids_basura(app, monkeypatch):
    monkeypatch.setattr(pcr, "get_current_user", lambda: {"id": 7})
    with app.test_request_context("/api/project-cards/kpis?module=otro&ids=1"):
        resp, code = pcr.get_kpis.__wrapped__()
    assert code == 400
    data, _, llamadas = _call(app, "module=manual_ai&ids=abc,,1,1", monkeypatch, visibles={1})
    assert list(data["kpis"]) == ["1"] and len(llamadas) == 1   # deduplicado y limpio


def test_un_adapter_que_falla_no_rompe_la_lista(app, monkeypatch):
    data, _, _ = _call(app, "module=ai_mode&ids=5", monkeypatch, visibles={5}, adapter_error=True)
    assert data["kpis"]["5"] == {"available": False, "reason": "error"}


def test_tope_de_ids():
    assert len(pcr._parse_ids(",".join(str(i) for i in range(500)))) == pcr.MAX_IDS
