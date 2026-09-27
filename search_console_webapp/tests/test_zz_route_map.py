"""
Foto del mapa de rutas de la app (regla, endpoint y métodos).

Por qué existe: casi todos los blueprints se registran dentro de try/except
(app.py). Si una refactorización rompe un import, la app arranca igual pero
sin esas rutas y los crons de Railway reciben 404 sin que nada avise. Este test
falla en cuanto desaparece, aparece o cambia cualquier ruta.

Regenerar la foto (solo tras un cambio de rutas intencionado y revisado):
    UPDATE_SNAPSHOTS=1 scripts/run_tests_docker.sh tests/test_zz_route_map.py
"""

import json
import os
from pathlib import Path

import pytest

SNAPSHOT = Path(__file__).resolve().parent / "snapshots" / "route_map.json"


def build_route_map(flask_app_module):
    rows = []
    for rule in flask_app_module.app.url_map.iter_rules():
        rows.append({
            "rule": rule.rule,
            "endpoint": rule.endpoint,
            "methods": sorted(m for m in rule.methods if m not in ("HEAD", "OPTIONS")),
        })
    return sorted(rows, key=lambda r: (r["rule"], r["endpoint"]))


def test_route_map_matches_snapshot(flask_app):
    current = build_route_map(flask_app)

    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(json.dumps(current, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        pytest.skip(f"Foto regenerada: {len(current)} rutas")

    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    key = lambda r: (r["rule"], r["endpoint"], tuple(r["methods"]))
    missing = sorted(set(map(key, expected)) - set(map(key, current)))
    added = sorted(set(map(key, current)) - set(map(key, expected)))
    assert not missing and not added, (
        f"El mapa de rutas ha cambiado.\n  Desaparecen: {missing}\n  Aparecen: {added}"
    )
