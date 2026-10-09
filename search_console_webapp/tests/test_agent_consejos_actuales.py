"""Los informes guardados antes de pasar Agent Readiness a inglés traían los
consejos en español; al abrirlos se regeneran con el texto actual."""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://dummy:dummy@localhost:5432/dummy")

from agent_scanner import storage  # noqa: E402
from agent_scanner.knowledge import advice_for  # noqa: E402


def test_consejos_antiguos_se_regeneran_y_las_evidencias_no():
    viejo = {"por_que": "texto antiguo en español", "como": "x", "esfuerzo": "Bajo", "impacto": "Alto"}
    data = {
        "client": {"checks": [
            {"id": "1.1", "score": 0, "evidence": "evidencia medida", "advice": dict(viejo)},
            {"id": "1.2", "score": 1, "evidence": "ok"},                       # sin consejo: no se añade
        ]},
        "competitors": [{"checks": [{"id": "1.1", "score": 0, "advice": dict(viejo)}]}, None],
    }
    storage.refrescar_consejos(data)
    nuevo = advice_for("1.1")
    assert nuevo and data["client"]["checks"][0]["advice"] == nuevo
    assert data["competitors"][0]["checks"][0]["advice"] == nuevo
    assert data["client"]["checks"][0]["evidence"] == "evidencia medida"
    assert "advice" not in data["client"]["checks"][1]


def test_tolera_datos_raros():
    assert storage.refrescar_consejos(None) is None
    assert storage.refrescar_consejos({"client": None}) == {"client": None}


def test_veredicto_y_penalizaciones_antiguos_pasan_a_ingles():
    from agent_scanner import scoring
    data = {"client": {"checks": [],
                       "level": {"emoji": "🔴", "name": "Invisible para agentes", "msg": "Ni te leen ni te usan. Riesgo alto."},
                       "penalties": [["Sin politica de bots documentada", -5]]},
            "competitors": [{"checks": [], "level": {"emoji": "🚫", "name": "Puerta cerrada a agentes", "msg": "x"}}]}
    storage.refrescar_consejos(data)
    assert data["client"]["level"] == {"emoji": "🔴", "name": scoring.LEVELS[0][3], "msg": scoring.LEVELS[0][4]}
    assert data["client"]["penalties"] == [["No documented bot policy", -5]]
    assert data["competitors"][0]["level"]["name"] == scoring.NIVEL_PUERTA_CERRADA["name"]
