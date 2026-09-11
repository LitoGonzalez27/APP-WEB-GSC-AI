"""Cuota y ciclo por PROYECTO (project_quota.py).

1. `compute_quota_window` (pura): misma regla que la cuota del usuario.
2. Catálogo de módulos y guardas de integración a nivel de fuente: los tres
   motores aplican el gate por proyecto y pausan SOLO el proyecto; el cron LLM
   lee la frecuencia; el admin expone las rutas; la migración y
   `init_database` crean las columnas.
"""
import re
from datetime import date, datetime
from pathlib import Path

import pytest

from project_quota import (
    MODULES,
    PROJECT_QUOTA_PAUSE_REASON,
    compute_quota_window,
)

ROOT = Path(__file__).resolve().parent.parent


def _read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Ventana
# ---------------------------------------------------------------------------

class TestComputeQuotaWindow:
    def test_reset_date_wins(self, monkeypatch):
        monkeypatch.setenv('QUOTA_RESET_INTERVAL_DAYS', '30')
        start, end = compute_quota_window({
            'quota_reset_date': datetime(2026, 10, 1, 3, 0),
            'current_period_start': datetime(2026, 1, 1),
            'current_period_end': datetime(2027, 1, 1),
        })
        assert (start, end) == (date(2026, 9, 1), date(2026, 10, 1))

    def test_stripe_period_fallback(self):
        start, end = compute_quota_window({
            'quota_reset_date': None,
            'current_period_start': datetime(2026, 9, 5),
            'current_period_end': datetime(2026, 10, 5),
        })
        assert (start, end) == (date(2026, 9, 5), date(2026, 10, 5))

    def test_calendar_month_fallback(self):
        assert compute_quota_window({}, today=date(2026, 12, 15)) == (date(2026, 12, 1), date(2027, 1, 1))
        assert compute_quota_window(None, today=date(2026, 2, 3)) == (date(2026, 2, 1), date(2026, 3, 1))

    def test_interval_env_respected(self, monkeypatch):
        monkeypatch.setenv('QUOTA_RESET_INTERVAL_DAYS', '7')
        start, end = compute_quota_window({'quota_reset_date': date(2026, 9, 20)})
        assert (start, end) == (date(2026, 9, 13), date(2026, 9, 20))


def test_llm_usage_uses_shared_window():
    """El contador LLM por usuario y el de proyecto deben compartir la ventana."""
    src = _read("llm_monitoring_limits.py")
    assert "from project_quota import compute_quota_window" in src


# ---------------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------------

def test_modules_catalog():
    assert set(MODULES) == {'manual_ai', 'ai_mode', 'llm_monitoring'}
    assert MODULES['manual_ai']['limit_col'] == 'monthly_ru_limit'
    assert MODULES['ai_mode']['limit_col'] == 'monthly_ru_limit'
    assert MODULES['llm_monitoring']['limit_col'] == 'monthly_units_limit'
    assert MODULES['manual_ai']['source'] == 'manual_ai'
    assert MODULES['ai_mode']['source'] == 'ai_mode'
    assert MODULES['llm_monitoring']['source'] is None
    assert PROJECT_QUOTA_PAUSE_REASON == 'project_quota_exceeded'


# ---------------------------------------------------------------------------
# Guardas de integración
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rel,module,cost", [
    ("manual_ai/services/analysis_service.py", "manual_ai", "MANUAL_AI_KEYWORD_ANALYSIS_COST"),
    ("ai_mode_projects/services/analysis_service.py", "ai_mode", "AI_MODE_KEYWORD_ANALYSIS_COST"),
])
def test_serp_engines_apply_project_gate(rel, module, cost):
    src = _read(rel)
    norm = re.sub(r"\s+", " ", src)
    # Pre-check antes del loop
    assert f"check_project_quota('{module}', project_id, current_user['id'], planned={cost})" in norm
    # Pausa SOLO el proyecto (dos veces: pre-check y dentro del loop)
    assert src.count(f"pause_project_for_quota('{module}', project_id, paused_until)") == 2
    # Contador local en el loop
    assert f"project_used_before + consumed_ru + {cost} > project_limit" in norm
    # Y sigue existiendo el gate por usuario (no lo hemos roto)
    assert "get_user_quota_status(current_user['id'])" in src


def test_llm_engine_applies_project_gate():
    src = _read("services/llm_monitoring/engine.py")
    norm = re.sub(r"\s+", " ", src)
    assert "prompt_sets, monthly_units_limit FROM llm_monitoring_projects" in norm
    assert "project.get('monthly_units_limit')" in src
    assert "get_project_usage('llm_monitoring', project_id, user_row['id'])" in src
    assert "pause_project_for_quota('llm_monitoring', project_id, paused_until)" in src
    assert "'llm_project_quota_exceeded'" in src
    # El gate por usuario sigue ahí
    assert "pause_llm_projects_for_quota(user_row['id'], paused_until, reason='quota_exceeded')" in src


def test_llm_cron_honors_frequency():
    src = _read("services/llm_monitoring_service.py")
    norm = re.sub(r"\s+", " ", src)
    assert "COALESCE(p.analysis_frequency_days, 1) AS analysis_frequency_days" in norm
    assert "AS last_analysis_date" in norm
    assert "(date.today() - last_analysis_date).days < frequency_days" in norm


def test_admin_routes_exist():
    src = _read("auth.py")
    assert "@app.route('/admin/users/<int:user_id>/project-limits')" in src
    assert "@app.route('/admin/projects/<module>/<int:project_id>/limits', methods=['POST'])" in src
    assert "set_project_limits(module, project_id, **kwargs)" in src


def test_admin_template_has_project_limits_table():
    src = _read("templates/admin_simple.html")
    assert 'id="detailProjectLimits"' in src
    assert "async function loadUserProjectLimits(userId)" in src
    assert "async function saveProjectLimits(moduleKey, projectId, userId)" in src
    assert "loadUserProjectLimits(id);" in src


def test_migration_and_init_database_cover_columns():
    mig = _read("migrate_project_quota_limits.py")
    init = _read("database.py")
    for table, col in [
        ("manual_ai_projects", "monthly_ru_limit"),
        ("ai_mode_projects", "monthly_ru_limit"),
        ("llm_monitoring_projects", "monthly_units_limit"),
        ("llm_monitoring_projects", "analysis_frequency_days"),
    ]:
        assert f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col}" in mig
        assert f"('{table}', '{col}" in init
    assert "idx_quota_events_project" in mig


def test_runbook_is_indexed():
    assert "CLAUDE-enterprise-agencias.md" in _read("CLAUDE-INDEX.md")
    assert (ROOT / "CLAUDE-enterprise-agencias.md").exists()
