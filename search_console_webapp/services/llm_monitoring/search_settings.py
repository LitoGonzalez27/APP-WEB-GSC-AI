"""
Interruptor de búsqueda web por proyecto de LLM Monitoring (solo admin).

Decisión de Carlos (2026-09-13): la búsqueda queda desactivada en todos los proyectos
y se activa proyecto a proyecto para el cliente que la pague. Activarla cambia la
metodología (el modelo puede buscar en la web), el coste (~×6) y las unidades que
consume cada prompt (llm_monitoring_limits.units_per_task).

`search_enabled_at` guarda cuándo se activó por última vez, para marcar el cambio de
metodología en los gráficos. Al desactivar se conserva como histórico.
"""

import logging
from typing import Dict

from services.llm_providers.web_search import SEARCH_MODE_AUTO, SEARCH_MODES

logger = logging.getLogger(__name__)


def get_db_connection():
    """Import perezoso: `database` exige DATABASE_URL al importarse."""
    from database import get_db_connection as _get
    return _get()


def set_project_search_mode(project_id: int, search_mode: str) -> Dict:
    """
    Fija `search_mode` ('off' | 'auto') de un proyecto. Valida estrictamente (un valor
    desconocido es un error, no se interpreta). Si el modo no cambia no toca nada.
    """
    if search_mode not in SEARCH_MODES:
        raise ValueError(f"search_mode must be one of {', '.join(SEARCH_MODES)}")

    conn = get_db_connection()
    if not conn:
        return {'success': False, 'error': 'Database connection failed'}
    cur = None
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, user_id, name, search_mode, search_enabled_at
            FROM llm_monitoring_projects
            WHERE id = %s
            FOR UPDATE
        """, (project_id,))
        project = cur.fetchone()
        if not project:
            conn.rollback()
            return {'success': False, 'error': 'Project not found'}

        previous = project['search_mode']
        enabled_at = project['search_enabled_at']
        changed = previous != search_mode
        if changed:
            cur.execute("""
                UPDATE llm_monitoring_projects
                SET search_mode = %s,
                    search_enabled_at = CASE WHEN %s THEN NOW() ELSE search_enabled_at END,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING search_enabled_at
            """, (search_mode, search_mode == SEARCH_MODE_AUTO, project_id))
            enabled_at = cur.fetchone()['search_enabled_at']
        conn.commit()

        if changed:
            logger.info(f"[search_settings] Proyecto LLM #{project_id} ({project['name']}): "
                        f"search_mode {previous} → {search_mode}")
        return {
            'success': True,
            'project_id': project_id,
            'user_id': project['user_id'],
            'name': project['name'],
            'previous_search_mode': previous,
            'search_mode': search_mode,
            'search_enabled_at': enabled_at.isoformat() if enabled_at else None,
            'changed': changed,
        }
    except Exception as exc:
        logger.error(f"[search_settings] Error cambiando search_mode del proyecto #{project_id}: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        return {'success': False, 'error': 'Database error'}
    finally:
        if cur:
            cur.close()
        conn.close()
