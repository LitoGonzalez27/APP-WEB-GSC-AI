#!/usr/bin/env python3
"""
LLM Monitoring - Límites y políticas por plan
=============================================
Centraliza límites de proyectos, prompts y consumo mensual.
"""

import json
import logging
import os
from datetime import date, timedelta
from typing import Dict, Optional
from database import get_db_connection
from services.llm_monitoring.schema_check import SchemaFeature, column_exists_sql
from services.llm_providers.web_search import is_search_enabled

logger = logging.getLogger(__name__)


LLM_ALLOWED_PLANS = ['basic', 'premium', 'business', 'enterprise']
LLM_ALLOWED_STATUSES = ['active', 'trialing', 'beta']
LLM_PROVIDERS = ['openai', 'anthropic', 'google', 'perplexity']

LLM_PLAN_LIMITS: Dict[str, Dict[str, Optional[int]]] = {
    'basic': {
        'max_projects': 1,
        'max_prompts_per_project': 20,
        'max_monthly_units': 640,
    },
    'premium': {
        'max_projects': 3,
        'max_prompts_per_project': 30,
        'max_monthly_units': 2880,
    },
    'business': {
        'max_projects': 5,
        'max_prompts_per_project': 60,
        'max_monthly_units': 9600,
    },
    'enterprise': {
        'max_projects': None,  # Control manual / acuerdos
        'max_prompts_per_project': None,
        'max_monthly_units': None,
    },
}


def get_llm_plan_limits(plan: str) -> Dict[str, Optional[int]]:
    return LLM_PLAN_LIMITS.get(plan, {
        'max_projects': 0,
        'max_prompts_per_project': 0,
        'max_monthly_units': 0,
    })


def can_access_llm_monitoring(user: dict) -> bool:
    if not user:
        return False
    if user.get('role') == 'admin':
        return True
    plan = user.get('plan', 'free')
    status = user.get('billing_status', '')
    return plan in LLM_ALLOWED_PLANS and status in LLM_ALLOWED_STATUSES


# ---------------------------------------------------------------------------
# Unidades de consumo
# ---------------------------------------------------------------------------
# 1 unidad = 1 prompt × 1 LLM sin búsqueda web. En proyectos con search_mode='auto'
# cada respuesta consume el peso de su proveedor (decisión de Carlos 2026-09-13: por
# modo del proyecto, no por si el modelo buscó, para que el consumo sea previsible).
# Pesos iniciales = coste con búsqueda / sin búsqueda medido en P1, redondeado arriba
# (CLAUDE-query-fanout.md §1b). Se pueden ajustar sin deploy con la variable
# LLM_SEARCH_UNIT_WEIGHTS='{"openai": 7, ...}'. Las filas con error cuentan 1.
DEFAULT_SEARCH_UNIT_WEIGHTS: Dict[str, int] = {
    'openai': 7,
    'anthropic': 10,
    'google': 3,
    'perplexity': 3,
}

UNITS_SCHEMA = SchemaFeature(
    name='unidades ponderadas',
    sql=column_exists_sql('llm_monitoring_results', 'units_consumed'),
    migration='migrate_llm_search_p3.py',
)


def _load_search_unit_weights() -> Dict[str, int]:
    weights = dict(DEFAULT_SEARCH_UNIT_WEIGHTS)
    raw = os.getenv('LLM_SEARCH_UNIT_WEIGHTS')
    if not raw:
        return weights
    try:
        overrides = json.loads(raw)
        for provider, weight in overrides.items():
            if provider not in LLM_PROVIDERS or int(weight) < 1:
                raise ValueError(f'{provider}={weight}')
            weights[provider] = int(weight)
    except (ValueError, TypeError, AttributeError) as exc:
        logger.error(f"LLM_SEARCH_UNIT_WEIGHTS inválida ({exc}); se usan los pesos por defecto")
        return dict(DEFAULT_SEARCH_UNIT_WEIGHTS)
    return weights


SEARCH_UNIT_WEIGHTS: Dict[str, int] = _load_search_unit_weights()


def units_per_task(llm_provider: str, search_mode: Optional[str]) -> int:
    """Unidades que consume una respuesta correcta de `llm_provider` en un proyecto con ese modo."""
    if not is_search_enabled(search_mode):
        return 1
    return SEARCH_UNIT_WEIGHTS.get(llm_provider, 1)


def units_by_provider(provider_names, search_mode: Optional[str]) -> Dict[str, int]:
    return {name: units_per_task(name, search_mode) for name in provider_names}


def llm_units_sql(alias: str = '') -> str:
    """
    Agregado SQL de unidades consumidas sobre llm_monitoring_results.

    Con la columna `units_consumed` migrada suma los pesos; sin ella (entorno sin
    migrar) cuenta filas, que es exactamente lo mismo que antes de la ponderación.
    Admite FILTER detrás: f"COALESCE({llm_units_sql()} FILTER (WHERE ...), 0)".
    """
    if UNITS_SCHEMA.available(get_db_connection):
        return f"SUM({alias + '.' if alias else ''}units_consumed)"
    return "COUNT(*)"


def get_upgrade_options(plan: str) -> list:
    order = ['basic', 'premium', 'business', 'enterprise']
    if plan not in order:
        return ['basic', 'premium', 'business']
    idx = order.index(plan)
    return order[min(idx + 1, len(order) - 1):]


def count_user_active_projects(user_id: int) -> int:
    conn = get_db_connection()
    if not conn:
        return 0
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*) AS count
            FROM llm_monitoring_projects
            WHERE user_id = %s AND is_active = TRUE
        """, (user_id,))
        row = cur.fetchone()
        return int(row['count']) if row else 0
    finally:
        cur.close()
        conn.close()


def count_project_active_queries(project_id: int) -> int:
    conn = get_db_connection()
    if not conn:
        return 0
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*) AS count
            FROM llm_monitoring_queries
            WHERE project_id = %s AND is_active = TRUE
        """, (project_id,))
        row = cur.fetchone()
        return int(row['count']) if row else 0
    finally:
        cur.close()
        conn.close()


def get_user_monthly_llm_usage(user_id: int, month_date: Optional[date] = None) -> int:
    """
    Devuelve unidades consumidas en el período de quota (1 prompt x 1 LLM = 1 unidad;
    con búsqueda web, el peso del proveedor: ver units_per_task).
    Se calcula desde llm_monitoring_results.
    """
    conn = get_db_connection()
    if not conn:
        return 0
    cur = None
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT quota_reset_date, current_period_start, current_period_end
            FROM users
            WHERE id = %s
        """, (user_id,))
        user = cur.fetchone() or {}

        # Ventana compartida con la cuota por proyecto (project_quota.py)
        from project_quota import compute_quota_window
        window_start, window_end = compute_quota_window(user, today=month_date)

        cur.execute(f"""
            SELECT COALESCE({llm_units_sql('r')}, 0) AS count
            FROM llm_monitoring_results r
            JOIN llm_monitoring_projects p ON p.id = r.project_id
            WHERE p.user_id = %s
              AND r.analysis_date >= %s
              AND r.analysis_date < %s
        """, (user_id, window_start, window_end))
        row = cur.fetchone()
        return int(row['count']) if row else 0
    finally:
        if cur:
            cur.close()
        conn.close()


def get_llm_limits_summary(user: dict) -> dict:
    if not user:
        return {
            'plan': 'free',
            'is_admin': False,
            'max_projects': 0,
            'max_prompts_per_project': 0,
            'max_monthly_units': 0,
            'monthly_units_used': 0,
            'monthly_units_remaining': 0,
            'active_projects': 0,
            'allowed_llms': LLM_PROVIDERS,
        }

    plan = user.get('plan', 'free')
    is_admin = user.get('role') == 'admin'

    # Los admin deben poder operar sin límites de plan para pruebas/soporte.
    if is_admin:
        used_units = get_user_monthly_llm_usage(user['id'])
        projects_count = count_user_active_projects(user['id'])
        return {
            'plan': plan,
            'is_admin': True,
            'max_projects': None,
            'max_prompts_per_project': None,
            'max_monthly_units': None,
            'monthly_units_used': used_units,
            'monthly_units_remaining': None,
            'active_projects': projects_count,
            'allowed_llms': LLM_PROVIDERS,
        }

    limits = get_llm_plan_limits(plan)
    used_units = get_user_monthly_llm_usage(user['id'])
    max_units = limits.get('max_monthly_units')

    # Enterprise: respetar custom limits si el admin los ha configurado
    max_prompts = limits.get('max_prompts_per_project')
    max_projects = limits.get('max_projects')
    if plan == 'enterprise':
        custom_prompts = user.get('custom_llm_prompts_limit')
        custom_units = user.get('custom_llm_monthly_units_limit')
        custom_projects = user.get('custom_llm_max_projects')
        if custom_prompts is not None:
            max_prompts = int(custom_prompts)
        if custom_units is not None:
            max_units = int(custom_units)
        if custom_projects is not None:
            max_projects = int(custom_projects)

    remaining_units = None if max_units is None else max(0, max_units - used_units)
    projects_count = count_user_active_projects(user['id'])

    return {
        'plan': plan,
        'is_admin': False,
        'max_projects': max_projects,
        'max_prompts_per_project': max_prompts,
        'max_monthly_units': max_units,
        'monthly_units_used': used_units,
        'monthly_units_remaining': remaining_units,
        'active_projects': projects_count,
        'allowed_llms': LLM_PROVIDERS,
    }
