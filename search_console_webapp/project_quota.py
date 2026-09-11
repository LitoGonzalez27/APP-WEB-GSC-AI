#!/usr/bin/env python3
"""
Project Quota - Cuota y ciclo por PROYECTO
==========================================

Complementa a la cuota por usuario (`quota_manager.py`, RU globales) y a la
cuota LLM por usuario (`llm_monitoring_limits.py`, units) con un **tope
propio por proyecto** y una **frecuencia de análisis por proyecto**, pensado
para clientes tipo agencia que gestionan varios clientes finales dentro de
una sola cuenta (ver `CLAUDE-enterprise-agencias.md`).

Columnas (todas NULL = sin tope propio, se aplica solo la cuota del usuario):

    manual_ai_projects.monthly_ru_limit          INTEGER  -- RU por ventana
    manual_ai_projects.analysis_frequency_days   INTEGER  -- ya existía (1 = cada tick)
    ai_mode_projects.monthly_ru_limit            INTEGER
    ai_mode_projects.analysis_frequency_days     INTEGER  -- ya existía
    llm_monitoring_projects.monthly_units_limit  INTEGER  -- units (prompt x LLM) por ventana
    llm_monitoring_projects.analysis_frequency_days INTEGER -- nuevo

Reglas:
- La **ventana** es la misma que la de la cuota del usuario: 30 días que
  terminan en `users.quota_reset_date` (fallback: periodo Stripe, y si no,
  mes natural). Al resetear la cuota del usuario, la ventana avanza y el
  consumo por proyecto vuelve a cero de forma natural.
- **Consumo Manual AI / AI Mode**: suma de `quota_usage_events.ru_consumed`
  con `metadata->>'project_id'` del proyecto dentro de la ventana (incluye
  re-análisis manuales). **Consumo LLM**: filas de `llm_monitoring_results`
  del proyecto dentro de la ventana (1 prompt x 1 LLM = 1 unit), igual que
  el contador por usuario.
- Al agotar el tope, se pausa **solo ese proyecto** (`is_paused_by_quota`,
  `paused_until = reset_date`, `paused_reason = 'project_quota_exceeded'`).
  La auto-reanudación existente por `paused_until` y el
  `resume_quota_pauses_for_user` del reset lo despausan sin código extra.
- Subir o quitar el tope desde el admin despausa el proyecto si ya cabe.
- La cuota del usuario sigue siendo el techo global: un proyecto nunca
  consume más allá de lo que le queda al usuario.
"""

import logging
import os
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def get_db_connection():
    """Import perezoso: `database` exige DATABASE_URL al importarse y las
    funciones puras de este módulo (ventana) deben poder testearse sin BD."""
    from database import get_db_connection as _get
    return _get()

PROJECT_QUOTA_PAUSE_REASON = 'project_quota_exceeded'

MODULES: Dict[str, Dict] = {
    'manual_ai': {
        'label': 'Manual AI (AI Overview)',
        'table': 'manual_ai_projects',
        'keywords_table': 'manual_ai_keywords',
        'source': 'manual_ai',
        'limit_col': 'monthly_ru_limit',
        'unit': 'RU',
    },
    'ai_mode': {
        'label': 'AI Mode',
        'table': 'ai_mode_projects',
        'keywords_table': 'ai_mode_keywords',
        'source': 'ai_mode',
        'limit_col': 'monthly_ru_limit',
        'unit': 'RU',
    },
    'llm_monitoring': {
        'label': 'LLM Monitoring',
        'table': 'llm_monitoring_projects',
        'keywords_table': 'llm_monitoring_queries',
        'source': None,  # se mide en llm_monitoring_results
        'limit_col': 'monthly_units_limit',
        'unit': 'units',
    },
}

_UNSET = object()


# ---------------------------------------------------------------------------
# Ventana de cuota (pura, sin DB)
# ---------------------------------------------------------------------------

def compute_quota_window(user_row: Optional[dict], today: Optional[date] = None) -> Tuple[date, date]:
    """
    Ventana [start, end) del ciclo de cuota vigente del usuario. Misma regla
    que `llm_monitoring_limits.get_user_monthly_llm_usage`:

    1. `quota_reset_date` → [reset - QUOTA_RESET_INTERVAL_DAYS, reset)
    2. si no, periodo Stripe [current_period_start, current_period_end)
    3. si no, mes natural de `today`
    """
    user_row = user_row or {}
    interval_days = int(os.getenv('QUOTA_RESET_INTERVAL_DAYS', '30'))
    quota_reset_date = user_row.get('quota_reset_date')
    period_start = user_row.get('current_period_start')
    period_end = user_row.get('current_period_end')

    def _as_date(value):
        return value.date() if isinstance(value, datetime) else value

    if quota_reset_date:
        end = _as_date(quota_reset_date)
        return end - timedelta(days=interval_days), end
    if period_start and period_end:
        return _as_date(period_start), _as_date(period_end)

    today = today or date.today()
    start = today.replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def _validate_module(module: str) -> Dict:
    cfg = MODULES.get(module)
    if not cfg:
        raise ValueError(f"Módulo desconocido: {module}")
    return cfg


def _fetch_user_window(cur, user_id: int) -> Tuple[date, date]:
    cur.execute("""
        SELECT quota_reset_date, current_period_start, current_period_end
        FROM users WHERE id = %s
    """, (user_id,))
    return compute_quota_window(cur.fetchone() or {})


def _scalar(row, key):
    if row is None:
        return 0
    value = row[key] if isinstance(row, dict) else row[0]
    return int(value or 0)


# ---------------------------------------------------------------------------
# Consumo por proyecto
# ---------------------------------------------------------------------------

def _project_usage_with_cursor(cur, module: str, project_id: int, user_id: int,
                               window: Tuple[date, date]) -> int:
    cfg = _validate_module(module)
    start, end = window
    if cfg['source']:
        cur.execute("""
            SELECT COALESCE(SUM(ru_consumed), 0) AS used
            FROM quota_usage_events
            WHERE user_id = %s
              AND source = %s
              AND metadata->>'project_id' = %s
              AND timestamp >= %s
              AND timestamp < %s
        """, (user_id, cfg['source'], str(project_id), start, end))
    else:
        cur.execute("""
            SELECT COUNT(*) AS used
            FROM llm_monitoring_results
            WHERE project_id = %s
              AND analysis_date >= %s
              AND analysis_date < %s
        """, (project_id, start, end))
    return _scalar(cur.fetchone(), 'used')


def get_project_usage(module: str, project_id: int, user_id: int) -> int:
    """Consumo del proyecto en la ventana de cuota vigente del usuario."""
    conn = get_db_connection()
    if not conn:
        return 0
    cur = None
    try:
        cur = conn.cursor()
        window = _fetch_user_window(cur, user_id)
        return _project_usage_with_cursor(cur, module, project_id, user_id, window)
    except Exception as exc:
        # FAIL-OPEN (0 consumido) y rollback para no devolver al pool una conexión abortada
        logger.error(f"[project_quota] Error calculando consumo {module}#{project_id}: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        return 0
    finally:
        if cur:
            cur.close()
        conn.close()


def get_project_quota_state(module: str, project_id: int, user_id: int) -> Dict:
    """
    Estado de cuota del proyecto: {limit, used, remaining, window_start, window_end}.
    `limit` None = sin tope propio (solo aplica la cuota del usuario).
    """
    cfg = _validate_module(module)
    state = {'module': module, 'project_id': project_id, 'limit': None, 'used': 0,
             'remaining': None, 'window_start': None, 'window_end': None}
    conn = get_db_connection()
    if not conn:
        return state
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT {cfg['limit_col']} AS lim FROM {cfg['table']} WHERE id = %s", (project_id,))
        row = cur.fetchone()
        limit = None
        if row is not None:
            raw = row['lim'] if isinstance(row, dict) else row[0]
            limit = int(raw) if raw is not None else None
        window = _fetch_user_window(cur, user_id)
        used = _project_usage_with_cursor(cur, module, project_id, user_id, window)
        state.update({
            'limit': limit,
            'used': used,
            'remaining': None if limit is None else max(0, limit - used),
            'window_start': window[0].isoformat(),
            'window_end': window[1].isoformat(),
        })
        return state
    except Exception as exc:
        # FAIL-OPEN (limit None → sin tope) y rollback: un fallo aquí nunca debe pausar nada
        logger.error(f"[project_quota] Error obteniendo estado {module}#{project_id}: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        return state
    finally:
        if cur:
            cur.close()
        conn.close()


def check_project_quota(module: str, project_id: int, user_id: int, planned: int = 1) -> Dict:
    """
    ¿Puede el proyecto consumir `planned` unidades más? Devuelve el estado
    más `allowed`. FAIL-OPEN si no hay tope (limit None).
    """
    state = get_project_quota_state(module, project_id, user_id)
    limit = state.get('limit')
    state['planned'] = int(planned)
    state['allowed'] = limit is None or (state['used'] + int(planned)) <= limit
    return state


# ---------------------------------------------------------------------------
# Pausa de UN proyecto
# ---------------------------------------------------------------------------

def pause_project_for_quota(module: str, project_id: int, paused_until,
                            reason: str = PROJECT_QUOTA_PAUSE_REASON) -> bool:
    """Pausa solo este proyecto (mismas columnas que la pausa por usuario)."""
    cfg = _validate_module(module)
    if paused_until is None:
        # Nunca pausar indefinidamente (ver CLAUDE-quota-system.md §8)
        paused_until = datetime.utcnow() + timedelta(days=30)
    conn = get_db_connection()
    if not conn:
        return False
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(f"""
            UPDATE {cfg['table']}
            SET is_paused_by_quota = TRUE,
                paused_until = %s,
                paused_at = NOW(),
                paused_reason = %s,
                updated_at = NOW()
            WHERE id = %s
        """, (paused_until, reason, project_id))
        conn.commit()
        logger.warning(f"⏸️ [project_quota] Proyecto {module}#{project_id} pausado por tope propio hasta {paused_until}")
        return True
    except Exception as exc:
        logger.error(f"[project_quota] Error pausando {module}#{project_id}: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        if cur:
            cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# Administración (panel admin)
# ---------------------------------------------------------------------------

def _parse_optional_positive(value, label: str, minimum: int = 1) -> Optional[int]:
    if value is None or value == '':
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f'{label} must be a valid number')
    if parsed < minimum:
        raise ValueError(f'{label} must be >= {minimum}')
    return parsed


def set_project_limits(module: str, project_id: int,
                       monthly_limit=_UNSET, analysis_frequency_days=_UNSET) -> Dict:
    """
    Actualiza el tope propio y/o la frecuencia de análisis del proyecto.

    - `monthly_limit`: int >= 1, o None para quitar el tope. Omitido = no tocar.
    - `analysis_frequency_days`: int >= 1 (1 = cada tick del cron). None = 1. Omitido = no tocar.

    Si el proyecto estaba pausado por su tope propio y con el nuevo valor ya
    cabe (o se quita el tope), se despausa en la misma operación.
    """
    cfg = _validate_module(module)
    updates, params = [], []

    if monthly_limit is not _UNSET:
        parsed_limit = _parse_optional_positive(monthly_limit, 'Monthly limit')
        updates.append(f"{cfg['limit_col']} = %s")
        params.append(parsed_limit)
    if analysis_frequency_days is not _UNSET:
        parsed_freq = _parse_optional_positive(analysis_frequency_days, 'Analysis frequency') or 1
        updates.append("analysis_frequency_days = %s")
        params.append(parsed_freq)
    if not updates:
        return {'success': False, 'error': 'Nothing to update'}

    conn = get_db_connection()
    if not conn:
        return {'success': False, 'error': 'Database connection failed'}
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(f"""
            UPDATE {cfg['table']}
            SET {', '.join(updates)}, updated_at = NOW()
            WHERE id = %s
            RETURNING id, user_id, name, {cfg['limit_col']} AS monthly_limit,
                      COALESCE(analysis_frequency_days, 1) AS analysis_frequency_days,
                      is_paused_by_quota, paused_reason
        """, (*params, project_id))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            return {'success': False, 'error': 'Project not found'}
        row = dict(row)

        # Despausar si estaba parado por su tope y ahora cabe
        resumed = False
        if row.get('is_paused_by_quota') and row.get('paused_reason') == PROJECT_QUOTA_PAUSE_REASON:
            window = _fetch_user_window(cur, row['user_id'])
            used = _project_usage_with_cursor(cur, module, project_id, row['user_id'], window)
            new_limit = row.get('monthly_limit')
            if new_limit is None or used < int(new_limit):
                cur.execute(f"""
                    UPDATE {cfg['table']}
                    SET is_paused_by_quota = FALSE, paused_until = NULL,
                        paused_at = NULL, paused_reason = NULL, updated_at = NOW()
                    WHERE id = %s
                """, (project_id,))
                resumed = True
        conn.commit()
        logger.info(f"[project_quota] {module}#{project_id} límites actualizados: {row} (resumed={resumed})")
        return {
            'success': True,
            'module': module,
            'project_id': project_id,
            'user_id': row['user_id'],
            'name': row['name'],
            'monthly_limit': row.get('monthly_limit'),
            'analysis_frequency_days': row.get('analysis_frequency_days'),
            'resumed': resumed,
        }
    except Exception as exc:
        logger.error(f"[project_quota] Error actualizando {module}#{project_id}: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        return {'success': False, 'error': f'Database error: {exc}'}
    finally:
        if cur:
            cur.close()
        conn.close()


def list_user_projects_with_limits(user_id: int) -> Dict:
    """
    Proyectos del usuario en los 3 módulos con tope, consumo en ventana,
    frecuencia y estado de pausa. Para el panel admin.
    """
    out: Dict = {'user_id': user_id, 'window': None, 'modules': {}}
    conn = get_db_connection()
    if not conn:
        return out
    cur = None
    try:
        cur = conn.cursor()
        window = _fetch_user_window(cur, user_id)
        out['window'] = {'start': window[0].isoformat(), 'end': window[1].isoformat()}
        for module, cfg in MODULES.items():
            rows: List[Dict] = []
            try:
                cur.execute(f"""
                    SELECT p.id, p.name, p.is_active,
                           COALESCE(p.is_paused_by_quota, FALSE) AS is_paused_by_quota,
                           p.paused_until, p.paused_reason,
                           COALESCE(p.analysis_frequency_days, 1) AS analysis_frequency_days,
                           p.{cfg['limit_col']} AS monthly_limit,
                           (SELECT COUNT(*) FROM {cfg['keywords_table']} k
                             WHERE k.project_id = p.id AND COALESCE(k.is_active, TRUE)) AS keyword_count
                    FROM {cfg['table']} p
                    WHERE p.user_id = %s
                    ORDER BY p.id
                """, (user_id,))
                for r in cur.fetchall():
                    r = dict(r)
                    used = _project_usage_with_cursor(cur, module, r['id'], user_id, window)
                    limit = r.get('monthly_limit')
                    r['used'] = used
                    r['remaining'] = None if limit is None else max(0, int(limit) - used)
                    r['unit'] = cfg['unit']
                    if r.get('paused_until') is not None and hasattr(r['paused_until'], 'isoformat'):
                        r['paused_until'] = r['paused_until'].isoformat()
                    rows.append(r)
            except Exception as exc:
                # Tabla o columna ausente (migración pendiente): no rompe el panel
                logger.warning(f"[project_quota] No se pudieron listar proyectos {module} de user {user_id}: {exc}")
                conn.rollback()
            out['modules'][module] = {'label': cfg['label'], 'unit': cfg['unit'], 'projects': rows}
        return out
    finally:
        if cur:
            cur.close()
        conn.close()
