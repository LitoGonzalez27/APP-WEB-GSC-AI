#!/usr/bin/env python3
"""
Enterprise Limits - Topes por módulo para usuarios Enterprise
=============================================================

Centraliza la resolución de los límites "custom" que el admin puede asignar
a un usuario con plan `enterprise` (columnas `users.custom_*`, ver
`migrate_enterprise_module_limits.py`):

    Módulo          Máx. proyectos                  Máx. keywords/prompts por proyecto
    ------          --------------                  ----------------------------------
    manual_ai       custom_manual_ai_max_projects   custom_manual_ai_keywords_limit
    ai_mode         custom_ai_mode_max_projects     custom_ai_mode_keywords_limit
    llm_monitoring  custom_llm_max_projects         custom_llm_prompts_limit (ya existía)

Reglas:
- Solo se aplican cuando `plan == 'enterprise'`. Para el resto de planes se
  devuelven los topes globales del módulo (200 / 300 keywords, proyectos sin
  límite en Manual AI / AI Mode; LLM tiene su propia tabla por plan en
  `llm_monitoring_limits.py`).
- Los admins (`role == 'admin'`) operan sin límite, igual que en LLM Monitoring.
- Un tope custom de keywords nunca supera el tope global del módulo
  (`min(custom, global)`), porque el global protege al backend.
- `None` significa "sin límite".

Este módulo NO toca la base de datos: recibe el dict de usuario ya cargado
(`get_current_user()` hace `SELECT * FROM users`, así que las columnas custom
vienen incluidas).
"""

from typing import Dict, Optional

MODULE_MANUAL_AI = 'manual_ai'
MODULE_AI_MODE = 'ai_mode'
MODULE_LLM = 'llm_monitoring'

# Columnas de `users` por módulo
_PROJECT_COLUMNS = {
    MODULE_MANUAL_AI: 'custom_manual_ai_max_projects',
    MODULE_AI_MODE: 'custom_ai_mode_max_projects',
    MODULE_LLM: 'custom_llm_max_projects',
}

_KEYWORD_COLUMNS = {
    MODULE_MANUAL_AI: 'custom_manual_ai_keywords_limit',
    MODULE_AI_MODE: 'custom_ai_mode_keywords_limit',
    MODULE_LLM: 'custom_llm_prompts_limit',
}

ENTERPRISE_LIMIT_COLUMNS = sorted(set(_PROJECT_COLUMNS.values()) | set(_KEYWORD_COLUMNS.values()))


def _as_positive_int(value) -> Optional[int]:
    """Convierte un valor de BD a int >= 1, o None si no hay override."""
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 1 else None


def is_enterprise_user(user: Optional[dict]) -> bool:
    return bool(user) and user.get('plan') == 'enterprise'


def get_custom_max_projects(user: Optional[dict], module: str) -> Optional[int]:
    """Máx. proyectos custom para el módulo. None = sin override / no aplica."""
    if not is_enterprise_user(user) or user.get('role') == 'admin':
        return None
    column = _PROJECT_COLUMNS.get(module)
    if not column:
        return None
    return _as_positive_int(user.get(column))


def get_effective_keywords_limit(user: Optional[dict], module: str, global_limit: int) -> int:
    """
    Tope efectivo de keywords/prompts por proyecto para el módulo.

    - No enterprise / admin → `global_limit`.
    - Enterprise con override → min(override, global_limit).
    """
    if not is_enterprise_user(user) or user.get('role') == 'admin':
        return int(global_limit)
    column = _KEYWORD_COLUMNS.get(module)
    custom = _as_positive_int(user.get(column)) if column else None
    if custom is None:
        return int(global_limit)
    return min(custom, int(global_limit))


def check_project_cap(user: Optional[dict], module: str, active_projects: int) -> Optional[Dict]:
    """
    Devuelve None si el usuario puede crear/reactivar un proyecto más en el
    módulo, o el payload de error (HTTP 402) si ha alcanzado su tope custom.

    Se usa tanto al crear como al reanudar (un proyecto pausado manualmente
    no cuenta como activo; al reanudarlo vuelve a contar).
    """
    max_projects = get_custom_max_projects(user, module)
    if max_projects is None or int(active_projects) < max_projects:
        return None
    return {
        'success': False,
        'error': 'project_limit_reached',
        'message': (
            f'You have reached the maximum number of active projects for your plan '
            f'({active_projects}/{max_projects}). Pause or delete a project to add another, '
            f'or contact support to extend your limit.'
        ),
        'current_plan': user.get('plan', 'free') if user else 'free',
        'limit': max_projects,
        'current': int(active_projects),
        'action_required': 'contact_support',
    }


def get_module_limits_summary(user: Optional[dict], module: str,
                              active_projects: int, global_keywords_limit: int) -> Dict:
    """Resumen de límites para el frontend (`limits` en GET /api/projects)."""
    return {
        'max_projects': get_custom_max_projects(user, module),
        'active_projects': int(active_projects),
        'max_keywords_per_project': get_effective_keywords_limit(user, module, global_keywords_limit),
        'is_enterprise': is_enterprise_user(user),
    }
