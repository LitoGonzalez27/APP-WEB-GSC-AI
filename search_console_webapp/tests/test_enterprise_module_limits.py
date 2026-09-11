"""Topes por módulo para usuarios Enterprise (enterprise_limits.py).

Cubre:
1. Resolución pura de límites (sin DB): plan, rol admin, overrides y min()
   contra el tope global del módulo.
2. Guardas a nivel de fuente: las rutas de creación/reanudación y de alta
   de keywords aplican el helper, el cron LLM lee la columna custom, y el
   panel admin persiste/limpia las 5 columnas nuevas.
"""
import re
from pathlib import Path

import pytest

from enterprise_limits import (
    MODULE_AI_MODE,
    MODULE_LLM,
    MODULE_MANUAL_AI,
    ENTERPRISE_LIMIT_COLUMNS,
    check_project_cap,
    get_custom_max_projects,
    get_effective_keywords_limit,
    get_module_limits_summary,
)

ROOT = Path(__file__).resolve().parent.parent


def _read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def _enterprise(**overrides):
    user = {'id': 1, 'plan': 'enterprise', 'role': 'user'}
    user.update(overrides)
    return user


# ---------------------------------------------------------------------------
# Resolución de límites
# ---------------------------------------------------------------------------

class TestMaxProjects:
    def test_non_enterprise_has_no_custom_cap(self):
        for plan in ('free', 'basic', 'premium', 'business'):
            user = {'plan': plan, 'custom_manual_ai_max_projects': 5}
            assert get_custom_max_projects(user, MODULE_MANUAL_AI) is None

    def test_enterprise_without_override_is_unlimited(self):
        assert get_custom_max_projects(_enterprise(), MODULE_MANUAL_AI) is None
        assert get_custom_max_projects(_enterprise(), MODULE_AI_MODE) is None
        assert get_custom_max_projects(_enterprise(), MODULE_LLM) is None

    def test_enterprise_override_per_module(self):
        user = _enterprise(
            custom_manual_ai_max_projects=5,
            custom_ai_mode_max_projects=3,
            custom_llm_max_projects=7,
        )
        assert get_custom_max_projects(user, MODULE_MANUAL_AI) == 5
        assert get_custom_max_projects(user, MODULE_AI_MODE) == 3
        assert get_custom_max_projects(user, MODULE_LLM) == 7

    def test_admin_is_never_capped(self):
        user = _enterprise(role='admin', custom_manual_ai_max_projects=1)
        assert get_custom_max_projects(user, MODULE_MANUAL_AI) is None

    def test_invalid_values_mean_no_override(self):
        assert get_custom_max_projects(_enterprise(custom_llm_max_projects=0), MODULE_LLM) is None
        assert get_custom_max_projects(_enterprise(custom_llm_max_projects='x'), MODULE_LLM) is None
        assert get_custom_max_projects(_enterprise(custom_llm_max_projects='4'), MODULE_LLM) == 4

    def test_none_user(self):
        assert get_custom_max_projects(None, MODULE_MANUAL_AI) is None


class TestKeywordsLimit:
    def test_non_enterprise_uses_global(self):
        user = {'plan': 'premium', 'custom_manual_ai_keywords_limit': 30}
        assert get_effective_keywords_limit(user, MODULE_MANUAL_AI, 200) == 200

    def test_enterprise_override_wins_when_lower(self):
        user = _enterprise(custom_manual_ai_keywords_limit=30, custom_ai_mode_keywords_limit=10)
        assert get_effective_keywords_limit(user, MODULE_MANUAL_AI, 200) == 30
        assert get_effective_keywords_limit(user, MODULE_AI_MODE, 300) == 10

    def test_override_never_exceeds_global(self):
        user = _enterprise(custom_manual_ai_keywords_limit=999)
        assert get_effective_keywords_limit(user, MODULE_MANUAL_AI, 200) == 200

    def test_enterprise_without_override_uses_global(self):
        assert get_effective_keywords_limit(_enterprise(), MODULE_AI_MODE, 300) == 300

    def test_admin_uses_global(self):
        user = _enterprise(role='admin', custom_ai_mode_keywords_limit=1)
        assert get_effective_keywords_limit(user, MODULE_AI_MODE, 300) == 300


class TestProjectCap:
    def test_allows_below_cap(self):
        user = _enterprise(custom_manual_ai_max_projects=5)
        assert check_project_cap(user, MODULE_MANUAL_AI, 4) is None

    def test_blocks_at_cap_with_402_payload(self):
        user = _enterprise(custom_manual_ai_max_projects=5)
        err = check_project_cap(user, MODULE_MANUAL_AI, 5)
        assert err is not None
        assert err['error'] == 'project_limit_reached'
        assert err['limit'] == 5 and err['current'] == 5
        assert err['success'] is False
        assert 'message' in err

    def test_no_cap_means_always_allowed(self):
        assert check_project_cap(_enterprise(), MODULE_MANUAL_AI, 10_000) is None
        assert check_project_cap({'plan': 'basic'}, MODULE_AI_MODE, 10_000) is None

    def test_summary_shape(self):
        user = _enterprise(custom_ai_mode_max_projects=5, custom_ai_mode_keywords_limit=10)
        summary = get_module_limits_summary(user, MODULE_AI_MODE, 2, 300)
        assert summary == {
            'max_projects': 5,
            'active_projects': 2,
            'max_keywords_per_project': 10,
            'is_enterprise': True,
        }


# ---------------------------------------------------------------------------
# Guardas de integración a nivel de fuente
# ---------------------------------------------------------------------------

def test_columns_catalog_matches_migration():
    src = _read("migrate_enterprise_module_limits.py")
    for col in ENTERPRISE_LIMIT_COLUMNS:
        if col == 'custom_llm_prompts_limit':
            continue  # ya existía (migrate_llm_enterprise_support.py)
        assert col in src, f"{col} falta en la migración"


@pytest.mark.parametrize("rel,module_const", [
    ("manual_ai/routes/projects.py", "MODULE_MANUAL_AI"),
    ("ai_mode_projects/routes/projects.py", "MODULE_AI_MODE"),
])
def test_create_and_resume_apply_project_cap(rel, module_const):
    src = _read(rel)
    # Se aplica en creación y en reanudación (dos llamadas al helper)
    assert src.count("check_project_cap(") >= 2
    assert module_const in src
    assert "count_user_active_projects(user['id'])" in src
    # El tope devuelve 402 (mismo código que LLM Monitoring)
    assert "return jsonify(cap_error), 402" in src


@pytest.mark.parametrize("rel,module_const", [
    ("manual_ai/routes/keywords.py", "MODULE_MANUAL_AI"),
    ("ai_mode_projects/routes/keywords.py", "MODULE_AI_MODE"),
])
def test_keywords_route_uses_effective_limit(rel, module_const):
    src = _read(rel)
    assert f"get_effective_keywords_limit(user, {module_const}, MAX_KEYWORDS_PER_PROJECT)" in src
    # Ya no compara contra la constante global directamente
    assert "> MAX_KEYWORDS_PER_PROJECT" not in src


def test_llm_limits_honor_custom_max_projects():
    for rel in ("llm_monitoring_limits.py", "llm_monitoring_routes.py"):
        assert "custom_llm_max_projects" in _read(rel), rel


def test_llm_cron_reads_custom_max_projects():
    src = _read("services/llm_monitoring_service.py")
    norm = re.sub(r"\s+", " ", src)
    assert "u.custom_llm_max_projects" in norm
    assert "project.get('custom_llm_max_projects')" in norm


def test_admin_panel_persists_and_clears_all_columns():
    src = _read("admin_billing_panel.py")
    for col in ENTERPRISE_LIMIT_COLUMNS:
        assert f"{col} = %s" in src, f"assign_custom_quota no persiste {col}"
        assert f"{col} = NULL" in src, f"remove_custom_quota no limpia {col}"


def test_admin_route_forwards_module_limits():
    src = _read("auth.py")
    assert "module_limits=module_limits" in src
    assert "MODULE_LIMIT_FIELDS" in src
