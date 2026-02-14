#!/usr/bin/env python3
"""
LLM Monitoring - Límites y políticas por plan
=============================================
Centraliza límites de proyectos, prompts y consumo mensual.
"""

import os
from datetime import date, timedelta
from typing import Dict, Optional
from database import get_db_connection


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
    Devuelve unidades consumidas en el período de quota (1 prompt x 1 LLM = 1 unidad).
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

        interval_days = int(os.getenv('QUOTA_RESET_INTERVAL_DAYS', '30'))
        quota_reset_date = user.get('quota_reset_date')
        current_period_start = user.get('current_period_start')
        current_period_end = user.get('current_period_end')

        if quota_reset_date:
            window_end = quota_reset_date.date()
            window_start = (quota_reset_date - timedelta(days=interval_days)).date()
        elif current_period_start and current_period_end:
            window_start = current_period_start.date()
            window_end = current_period_end.date()
        else:
            month_date = month_date or date.today()
            window_start = month_date.replace(day=1)
            if window_start.month == 12:
                window_end = window_start.replace(year=window_start.year + 1, month=1)
            else:
                window_end = window_start.replace(month=window_start.month + 1)

        cur.execute("""
            SELECT COUNT(*) AS count
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
    remaining_units = None if max_units is None else max(0, max_units - used_units)
    projects_count = count_user_active_projects(user['id'])

    return {
        'plan': plan,
        'is_admin': False,
        'max_projects': limits.get('max_projects'),
        'max_prompts_per_project': limits.get('max_prompts_per_project'),
        'max_monthly_units': max_units,
        'monthly_units_used': used_units,
        'monthly_units_remaining': remaining_units,
        'active_projects': projects_count,
        'allowed_llms': LLM_PROVIDERS,
    }
