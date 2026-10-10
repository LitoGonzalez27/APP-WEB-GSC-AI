"""
Notas manuales de AI Overview y AI Mode (POST /api/projects/<id>/notes).

El botón «Add Note» del modal de configuración estuvo un año sin hacer nada:
al modularizar (sep-2025) se perdieron su JS y esta ruta. La nota se guarda
como evento 'manual_note_added' (las gráficas ya lo pintan en azul).
Lo crítico: solo el dueño escribe, y el texto se valida antes de guardar.
"""

import os

import pytest
from flask import Flask

os.environ.setdefault("DATABASE_URL", "postgresql://dummy:dummy@localhost:5432/dummy")

import manual_ai.routes.projects as aio  # noqa: E402
import ai_mode_projects.routes.projects as aim  # noqa: E402

MODULOS = [pytest.param(aio, id="ai_overview"), pytest.param(aim, id="ai_mode")]


def _post(mod, monkeypatch, body, owner=True, saved=True):
    monkeypatch.setattr(mod, "get_current_user", lambda: {"id": 7, "plan": "business"})
    monkeypatch.setattr(mod.project_service, "user_owns_project", lambda uid, pid: owner)
    eventos = []

    def create_event(**kw):
        eventos.append(kw)
        return saved
    monkeypatch.setattr(mod.EventRepository, "create_event", staticmethod(create_event))

    with Flask(__name__).test_request_context("/api/projects/12/notes", method="POST", json=body):
        resp, code = mod.add_project_note.__wrapped__(12)
    return code, resp.get_json(), eventos


@pytest.mark.parametrize("mod", MODULOS)
def test_el_dueno_guarda_la_nota_como_evento(mod, monkeypatch):
    code, data, eventos = _post(mod, monkeypatch, {"note": "  Cambié los títulos de la home  "})
    assert code == 201 and data["success"] is True and data["note_date"]
    assert eventos == [{
        "project_id": 12, "event_type": "manual_note_added",
        "event_title": "User note: Cambié los títulos de la home",
        "event_description": "Cambié los títulos de la home",
        "keywords_affected": 0, "user_id": 7,
    }]


@pytest.mark.parametrize("mod", MODULOS)
def test_quien_no_es_dueno_no_escribe(mod, monkeypatch):
    code, _, eventos = _post(mod, monkeypatch, {"note": "hola"}, owner=False)
    assert code == 403 and eventos == []


@pytest.mark.parametrize("mod", MODULOS)
@pytest.mark.parametrize("body", [{"note": "   "}, {}, {"note": 5}, None, {"note": "x" * 501}])
def test_texto_invalido_no_se_guarda(mod, monkeypatch, body):
    code, data, eventos = _post(mod, monkeypatch, body)
    assert code == 400 and data["success"] is False and eventos == []


@pytest.mark.parametrize("mod", MODULOS)
def test_titulo_recortado_y_fallo_de_bd(mod, monkeypatch):
    _, _, eventos = _post(mod, monkeypatch, {"note": "a" * 80})
    assert eventos[0]["event_title"] == "User note: " + "a" * 50 + "..."
    assert eventos[0]["event_description"] == "a" * 80
    code, data, _ = _post(mod, monkeypatch, {"note": "hola"}, saved=False)
    assert code == 500 and data["success"] is False
