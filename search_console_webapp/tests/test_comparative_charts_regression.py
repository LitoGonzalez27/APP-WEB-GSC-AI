"""
Test de REGRESIÓN para los gráficos comparativos (Manual AI y AI Mode).

Contexto: al dividir competitor_service.py en mixins, el método
`get_project_comparative_charts_data` (movido a un módulo nuevo) seguía llamando a
`CompetitorService.get_competitors_for_date_range(...)` por nombre de clase. Ese
nombre ya NO estaba en el scope del módulo del mixin → `NameError`, que el `except`
del método tragaba devolviendo `{'visibility_chart': {}, ...}`. Resultado: los
gráficos comparativos salían vacíos ("No data") aunque hubiera datos.

Este test ejercita el método con una BD simulada (sin conexión real) y verifica que
NO cae en el `except` (es decir, que `visibility_chart` trae la estructura con
`datasets`, no el dict vacío). Habría cazado el NameError.

Ejecutar:  python3 -m pytest tests/test_comparative_charts_regression.py -q
"""

import os
import importlib

os.environ.setdefault("DATABASE_URL", "postgresql://dummy:dummy@localhost:5432/dummy")

import pytest  # noqa: E402


class _Row(dict):
    """Fila tipo RealDictRow que devuelve None para claves ausentes (no KeyError)."""
    def __getitem__(self, k):
        return super().get(k)


class _FakeCursor:
    def execute(self, sql, params=None):
        self._sql = sql or ""

    def fetchone(self):
        # La query de proyecto necesita domain + selected_competitors.
        return _Row(domain="example.com", selected_competitors=[])

    def fetchall(self):
        return []

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeConn:
    def cursor(self, *a, **k):
        return _FakeCursor()

    def close(self):
        pass

    def commit(self):
        pass

    def rollback(self):
        pass


def _fake_get_db_connection():
    return _FakeConn()


# (módulo del servicio público, módulos de mixins a parchear)
CASES = [
    (
        "manual_ai.services.competitor_service",
        ["manual_ai.services._competitor.charts", "manual_ai.services._competitor.historical"],
    ),
    (
        "ai_mode_projects.services.competitor_service",
        ["ai_mode_projects.services._competitor.charts", "ai_mode_projects.services._competitor.historical"],
    ),
]


@pytest.mark.parametrize("svc_mod_name,patch_mods", CASES)
def test_comparative_charts_no_nameerror(svc_mod_name, patch_mods, monkeypatch):
    svc_mod = importlib.import_module(svc_mod_name)
    Service = svc_mod.CompetitorService

    # Parchear get_db_connection en cada submódulo que lo use (mixins).
    for mod_name in patch_mods:
        try:
            mod = importlib.import_module(mod_name)
        except ModuleNotFoundError:
            # En main, ai_mode aún no está dividido en mixins: el método vive en el
            # propio competitor_service (monolito) → parcheamos ahí.
            mod = svc_mod
        if hasattr(mod, "get_db_connection"):
            monkeypatch.setattr(mod, "get_db_connection", _fake_get_db_connection)
    # Por si el monolito tiene el método directamente:
    if hasattr(svc_mod, "get_db_connection"):
        monkeypatch.setattr(svc_mod, "get_db_connection", _fake_get_db_connection)

    result = Service.get_project_comparative_charts_data(1, days=30)

    # Si hubiera NameError (u otra excepción), el método devuelve {'visibility_chart': {}}.
    assert result.get("visibility_chart") != {}, (
        f"{svc_mod_name}: get_project_comparative_charts_data cayó en el except "
        f"(probable NameError / regresión). Resultado: {result}"
    )
    assert "datasets" in result["visibility_chart"]
    assert "datasets" in result["position_chart"]
