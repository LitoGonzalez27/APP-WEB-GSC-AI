#!/usr/bin/env python3
"""
Admin Billing Panel - Funciones backend para el panel admin con información de billing
===================================================================================

Nuevas funciones para mostrar información de planes, cuotas y billing en el panel admin.
Estas funciones extienden las existentes para incluir datos de Stripe y facturación.
"""

import os
import json
import logging
from datetime import datetime, date, timedelta
from database import get_db_connection, resume_quota_pauses_for_user

logger = logging.getLogger(__name__)


def log_admin_action(admin_id, action, target_user_id=None, details=None):
    """Registra una acción administrativa en el audit log."""
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return
        cur = conn.cursor()
        # Verificar si la tabla existe antes de insertar
        cur.execute("SELECT to_regclass('public.admin_audit_log') AS reg")
        reg = cur.fetchone()
        if not (reg['reg'] if isinstance(reg, dict) else reg[0]):
            return
        cur.execute('''
            INSERT INTO admin_audit_log (admin_user_id, action, target_user_id, details)
            VALUES (%s, %s, %s, %s)
        ''', (admin_id, action, target_user_id, json.dumps(details) if details else None))
        conn.commit()
    except Exception as e:
        logger.warning(f"Error registrando admin action: {e}")
    finally:
        if conn:
            conn.close()


def _get_table_columns(cur, table_name):
    """Devuelve set de columnas de una tabla (si existe)."""
    try:
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = %s
        """, (table_name,))
        return {row[0] if isinstance(row, tuple) else row['column_name'] for row in cur.fetchall()}
    except Exception:
        return set()


def _get_month_bounds(now=None):
    now = now or datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if month_start.month == 12:
        next_month = month_start.replace(year=month_start.year + 1, month=1)
    else:
        next_month = month_start.replace(month=month_start.month + 1)
    return month_start, next_month


def _get_today_bounds(now=None):
    now = now or datetime.utcnow()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    next_day = day_start + timedelta(days=1)
    return day_start, next_day


_ALLOWED_TIME_COLS = frozenset({'timestamp', 'created_at'})
_ALLOWED_SOURCE_FILTERS = frozenset({"source = 'serp_api'", "operation_type LIKE 'serp_%'"})


def _get_serp_usage_by_user(cur):
    """Mapa user_id -> ru SERP consumidas este mes."""
    columns = _get_table_columns(cur, 'quota_usage_events')
    if not columns:
        return {}

    time_col = 'timestamp' if 'timestamp' in columns else ('created_at' if 'created_at' in columns else None)
    if not time_col or time_col not in _ALLOWED_TIME_COLS:
        return {}

    if 'source' in columns:
        source_filter = "source = 'serp_api'"
    elif 'operation_type' in columns:
        source_filter = "operation_type LIKE 'serp_%'"
    else:
        return {}

    # ✅ Validación explícita de valores dinámicos en SQL
    if source_filter not in _ALLOWED_SOURCE_FILTERS:
        return {}

    month_start, next_month = _get_month_bounds()
    cur.execute(f'''
        SELECT user_id, COALESCE(SUM(ru_consumed), 0) AS serp_ru_month
        FROM quota_usage_events
        WHERE {time_col} >= %s
          AND {time_col} < %s
          AND {source_filter}
        GROUP BY user_id
    ''', (month_start, next_month))
    rows = cur.fetchall()
    return {row['user_id']: row for row in rows}


def _get_ru_usage_by_user(cur):
    """Mapa user_id -> RU totales consumidas este mes (todas las fuentes)."""
    columns = _get_table_columns(cur, 'quota_usage_events')
    if not columns:
        return {}
    time_col = 'timestamp' if 'timestamp' in columns else ('created_at' if 'created_at' in columns else None)
    if not time_col:
        return {}

    month_start, next_month = _get_month_bounds()
    cur.execute(f'''
        SELECT user_id, COALESCE(SUM(ru_consumed), 0) AS ru_month
        FROM quota_usage_events
        WHERE {time_col} >= %s
          AND {time_col} < %s
        GROUP BY user_id
    ''', (month_start, next_month))
    rows = cur.fetchall()
    return {row['user_id']: row for row in rows}


def _get_llm_usage_by_user(cur):
    """Mapa user_id -> unidades y coste LLM del mes."""
    try:
        cur.execute("SELECT to_regclass('public.llm_monitoring_results') AS reg")
        reg = cur.fetchone()
        if not (reg['reg'] if isinstance(reg, dict) else reg[0]):
            return {}
    except Exception:
        return {}

    cur.execute('''
        SELECT 
            p.user_id,
            COUNT(*) AS llm_units_month,
            COALESCE(SUM(r.cost_usd), 0) AS llm_cost_month
        FROM llm_monitoring_results r
        JOIN llm_monitoring_projects p ON p.id = r.project_id
        WHERE r.analysis_date >= DATE_TRUNC('month', CURRENT_DATE)
          AND r.analysis_date < DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month'
        GROUP BY p.user_id
    ''')
    rows = cur.fetchall()
    return {row['user_id']: row for row in rows}


def _get_llm_active_projects_by_user(cur):
    """Mapa user_id -> proyectos LLM activos."""
    try:
        cur.execute("SELECT to_regclass('public.llm_monitoring_projects') AS reg")
        reg = cur.fetchone()
        if not (reg['reg'] if isinstance(reg, dict) else reg[0]):
            return {}
    except Exception:
        return {}

    cur.execute('''
        SELECT user_id, COUNT(*) AS active_projects
        FROM llm_monitoring_projects
        WHERE is_active = TRUE
        GROUP BY user_id
    ''')
    rows = cur.fetchall()
    return {row['user_id']: row for row in rows}


def _get_ai_mode_paused_projects_by_user(cur):
    """Mapa user_id -> proyectos AI Mode pausados por cuota."""
    try:
        cur.execute("SELECT to_regclass('public.ai_mode_projects') AS reg")
        reg = cur.fetchone()
        if not (reg['reg'] if isinstance(reg, dict) else reg[0]):
            return {}
    except Exception:
        return {}

    cur.execute('''
        SELECT user_id, COUNT(*) AS paused_projects
        FROM ai_mode_projects
        WHERE COALESCE(is_paused_by_quota, FALSE) = TRUE
        GROUP BY user_id
    ''')
    rows = cur.fetchall()
    return {row['user_id']: row for row in rows}


def _get_llm_paused_projects_by_user(cur):
    """Mapa user_id -> proyectos LLM pausados por cuota."""
    try:
        cur.execute("SELECT to_regclass('public.llm_monitoring_projects') AS reg")
        reg = cur.fetchone()
        if not (reg['reg'] if isinstance(reg, dict) else reg[0]):
            return {}
    except Exception:
        return {}

    cur.execute('''
        SELECT user_id, COUNT(*) AS paused_projects
        FROM llm_monitoring_projects
        WHERE COALESCE(is_paused_by_quota, FALSE) = TRUE
        GROUP BY user_id
    ''')
    rows = cur.fetchall()
    return {row['user_id']: row for row in rows}

def _get_invitations_by_user(cur):
    """Mapa user_id -> {total_sent, accepted, pending} invitaciones."""
    try:
        cur.execute("SELECT to_regclass('public.project_invitations') AS reg")
        reg = cur.fetchone()
        if not (reg['reg'] if isinstance(reg, dict) else reg[0]):
            return {}
    except Exception:
        return {}

    try:
        cur.execute('''
            SELECT owner_user_id,
                COUNT(*) AS total_sent,
                COUNT(CASE WHEN status = 'accepted' THEN 1 END) AS accepted,
                COUNT(CASE WHEN status = 'pending' THEN 1 END) AS pending
            FROM project_invitations
            GROUP BY owner_user_id
        ''')
        return {row['owner_user_id']: row for row in cur.fetchall()}
    except Exception:
        return {}


def _get_project_counts_by_user(cur):
    """Mapa user_id -> {aio_total, aio_active, aim_total, aim_active, llm_total, llm_active}."""
    counts = {}
    for table, key in [('manual_ai_projects', 'aio'), ('ai_mode_projects', 'aim'), ('llm_monitoring_projects', 'llm')]:
        try:
            cur.execute("SELECT to_regclass(%s) AS reg", (f'public.{table}',))
            reg = cur.fetchone()
            if not (reg['reg'] if isinstance(reg, dict) else reg[0]):
                continue
        except Exception:
            continue

        try:
            cur.execute(f'''
                SELECT user_id,
                    COUNT(*) AS total,
                    COUNT(CASE WHEN is_active THEN 1 END) AS active
                FROM {table} GROUP BY user_id
            ''')
            for row in cur.fetchall():
                uid = row['user_id']
                counts.setdefault(uid, {})[f'{key}_total'] = int(row['total'] or 0)
                counts.setdefault(uid, {})[f'{key}_active'] = int(row['active'] or 0)
        except Exception:
            pass
    return counts


def get_billing_stats():
    """Obtiene estadísticas de billing para el dashboard admin"""
    try:
        conn = get_db_connection()
        if not conn:
            return {
                'total_users': 0,
                'users_by_plan': {},
                'users_by_billing_status': {},
                'total_ru_consumed_today': 0,
                'total_ru_consumed_month': 0,
                'revenue_estimate_month': 0
            }
        
        cur = conn.cursor()
        
        # Total de usuarios
        cur.execute('SELECT COUNT(*) AS count FROM users')
        row = cur.fetchone()
        total_users = row['count'] if isinstance(row, dict) else (row[0] if row else 0)
        
        # Usuarios por plan
        cur.execute('''
            SELECT plan, COUNT(*) as count 
            FROM users 
            GROUP BY plan 
            ORDER BY plan
        ''')
        users_by_plan = {}
        for row in cur.fetchall():
            if isinstance(row, dict):
                users_by_plan[row.get('plan')] = row.get('count', 0)
            elif row:
                users_by_plan[row[0]] = row[1]
        
        # Usuarios por estado de billing
        cur.execute('''
            SELECT billing_status, COUNT(*) as count 
            FROM users 
            GROUP BY billing_status 
            ORDER BY billing_status
        ''')
        users_by_billing_status = {}
        for row in cur.fetchall():
            if isinstance(row, dict):
                users_by_billing_status[row.get('billing_status')] = row.get('count', 0)
            elif row:
                users_by_billing_status[row[0]] = row[1]
        
        # RU consumidas hoy/mes (si existe la tabla)
        total_ru_today = 0
        total_ru_month = 0
        total_serp_ru_month = 0
        try:
            columns = _get_table_columns(cur, 'quota_usage_events')
            time_col = 'timestamp' if 'timestamp' in columns else ('created_at' if 'created_at' in columns else None)
            if time_col:
                day_start, next_day = _get_today_bounds()
                month_start, next_month = _get_month_bounds()
                cur.execute(f'''
                    SELECT COALESCE(SUM(ru_consumed), 0) AS total_ru
                    FROM quota_usage_events 
                    WHERE {time_col} >= %s AND {time_col} < %s
                ''', (day_start, next_day))
                row = cur.fetchone()
                total_ru_today = row['total_ru'] if isinstance(row, dict) else (row[0] if row else 0)
                
                cur.execute(f'''
                    SELECT COALESCE(SUM(ru_consumed), 0) AS total_ru
                    FROM quota_usage_events 
                    WHERE {time_col} >= %s AND {time_col} < %s
                ''', (month_start, next_month))
                row = cur.fetchone()
                total_ru_month = row['total_ru'] if isinstance(row, dict) else (row[0] if row else 0)

                if 'source' in columns:
                    serp_filter = "source = 'serp_api'"
                elif 'operation_type' in columns:
                    serp_filter = "operation_type LIKE 'serp_%'"
                else:
                    serp_filter = None
                if serp_filter:
                    cur.execute(f'''
                        SELECT COALESCE(SUM(ru_consumed), 0) AS total_ru
                        FROM quota_usage_events
                        WHERE {time_col} >= %s
                          AND {time_col} < %s
                          AND {serp_filter}
                    ''', (month_start, next_month))
                    row = cur.fetchone()
                    total_serp_ru_month = row['total_ru'] if isinstance(row, dict) else (row[0] if row else 0)
        except:
            # Tabla quota_usage_events no existe aún
            pass

        # LLM usage (si existen tablas)
        total_llm_units_month = 0
        total_llm_cost_month = 0
        try:
            cur.execute("SELECT to_regclass('public.llm_monitoring_results') AS reg")
            reg = cur.fetchone()
            if reg and (reg['reg'] if isinstance(reg, dict) else reg[0]):
                month_start, next_month = _get_month_bounds()
                cur.execute('''
                    SELECT 
                        COUNT(*) AS total_units,
                        COALESCE(SUM(cost_usd), 0) AS total_cost
                    FROM llm_monitoring_results
                    WHERE analysis_date >= %s
                      AND analysis_date < %s
                ''', (month_start.date(), next_month.date()))
                row = cur.fetchone()
                if row:
                    if isinstance(row, dict):
                        total_llm_units_month = row.get('total_units', 0)
                        total_llm_cost_month = row.get('total_cost', 0)
                    else:
                        total_llm_units_month = row[0] if len(row) > 0 else 0
                        total_llm_cost_month = row[1] if len(row) > 1 else 0
        except Exception:
            pass
        
        # Estimación de ingresos mensuales (básico: €29.99, premium: pricing por configurar)
        revenue_estimate = 0
        for plan, count in users_by_plan.items():
            try:
                count_val = int(count or 0)
            except Exception:
                count_val = 0
            if plan == 'basic':
                revenue_estimate += count_val * 29.99
            elif plan == 'premium':
                revenue_estimate += count_val * 49.99  # Estimación, ajustar según tu pricing
            elif plan == 'business':
                revenue_estimate += count_val * 139.99
        
        return {
            'total_users': total_users,
            'users_by_plan': users_by_plan,
            'users_by_billing_status': users_by_billing_status,
            'total_ru_consumed_today': total_ru_today,
            'total_ru_consumed_month': total_ru_month,
            'total_serp_ru_month': total_serp_ru_month,
            'total_llm_units_month': total_llm_units_month,
            'total_llm_cost_month': total_llm_cost_month,
            'revenue_estimate_month': revenue_estimate
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo stats de billing: {e}")
        return {
            'total_users': 0,
            'users_by_plan': {},
            'users_by_billing_status': {},
            'total_ru_consumed_today': 0,
            'total_ru_consumed_month': 0,
            'total_serp_ru_month': 0,
            'total_llm_units_month': 0,
            'total_llm_cost_month': 0,
            'revenue_estimate_month': 0
        }
    finally:
        if conn:
            conn.close()

def get_users_with_billing(limit=200, offset=0):
    """Obtiene usuarios con información de billing para el panel admin (paginado)"""
    try:
        conn = get_db_connection()
        if not conn:
            return []
        
        cur = conn.cursor()
        
        # Query que incluye todos los campos de billing + custom quotas
        cur.execute('''
            SELECT 
                id, email, name, picture, role,
                COALESCE(is_active, TRUE) as is_active,
                created_at, updated_at, last_login_at, google_id,
                -- Campos de billing (con fallbacks seguros)
                COALESCE(plan, 'free') as plan,
                COALESCE(current_plan, plan, 'free') as current_plan,
                COALESCE(billing_status, 'active') as billing_status,
                COALESCE(quota_limit, 0) as quota_limit,
                COALESCE(quota_used, 0) as quota_used,
                quota_reset_date,
                stripe_customer_id,
                subscription_id,
                current_period_start,
                current_period_end,
                pending_plan,
                pending_plan_date,
                ai_overview_paused_until,
                ai_overview_paused_at,
                ai_overview_paused_reason,
                -- Custom quota fields
                custom_quota_limit,
                custom_quota_notes,
                custom_quota_assigned_by,
                custom_quota_assigned_date
            FROM users 
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        ''', (limit, offset))
        
        users = cur.fetchall()
        users_list = [dict(user) for user in users]

        # Enriquecer con métricas SERP/LLM
        serp_usage = _get_serp_usage_by_user(cur)
        ru_usage = _get_ru_usage_by_user(cur)
        llm_usage = _get_llm_usage_by_user(cur)
        llm_projects = _get_llm_active_projects_by_user(cur)
        ai_mode_paused = _get_ai_mode_paused_projects_by_user(cur)
        llm_paused = _get_llm_paused_projects_by_user(cur)
        invitations = _get_invitations_by_user(cur)
        project_counts = _get_project_counts_by_user(cur)

        for user in users_list:
            user_id = user['id']
            serp_row = serp_usage.get(user_id, {})
            ru_row = ru_usage.get(user_id, {})
            llm_row = llm_usage.get(user_id, {})
            proj_row = llm_projects.get(user_id, {})
            ai_mode_row = ai_mode_paused.get(user_id, {})
            llm_paused_row = llm_paused.get(user_id, {})
            inv_row = invitations.get(user_id, {})
            pc_row = project_counts.get(user_id, {})

            user['serp_ru_month'] = int(serp_row.get('serp_ru_month', 0) or 0)
            user['ru_month'] = int(ru_row.get('ru_month', 0) or 0)
            user['llm_units_month'] = int(llm_row.get('llm_units_month', 0) or 0)
            user['llm_cost_month'] = float(llm_row.get('llm_cost_month', 0) or 0)
            user['llm_active_projects'] = int(proj_row.get('active_projects', 0) or 0)
            user['ai_mode_paused_projects'] = int(ai_mode_row.get('paused_projects', 0) or 0)
            user['llm_paused_projects'] = int(llm_paused_row.get('paused_projects', 0) or 0)
            # Invitaciones
            user['invitations_sent'] = int(inv_row.get('total_sent', 0) or 0)
            user['invitations_accepted'] = int(inv_row.get('accepted', 0) or 0)
            user['invitations_pending'] = int(inv_row.get('pending', 0) or 0)
            # Proyectos por módulo
            user['aio_total'] = pc_row.get('aio_total', 0)
            user['aio_active'] = pc_row.get('aio_active', 0)
            user['aim_total'] = pc_row.get('aim_total', 0)
            user['aim_active'] = pc_row.get('aim_active', 0)
            user['llm_total'] = pc_row.get('llm_total', 0)
            user['llm_active'] = pc_row.get('llm_active', 0)

        return users_list
        
    except Exception as e:
        logger.error(f"Error obteniendo usuarios con billing: {e}")
        # Fallback a función original si falla
        try:
            cur = conn.cursor()
            cur.execute('''
                SELECT id, email, name, picture, role, is_active, created_at, google_id
                FROM users 
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            ''', (limit, offset))
            users = cur.fetchall()
            # Añadir campos de billing como None para compatibilidad
            enhanced_users = []
            for user in users:
                user_dict = dict(user)
                user_dict.update({
                    'plan': 'unknown',
                    'current_plan': 'unknown', 
                    'billing_status': 'unknown',
                    'quota_limit': 0,
                    'quota_used': 0,
                    'quota_reset_date': None,
                    'stripe_customer_id': None,
                    'subscription_id': None,
                    'current_period_start': None,
                    'current_period_end': None,
                    'pending_plan': None,
                    'pending_plan_date': None
                })
                enhanced_users.append(user_dict)
            return enhanced_users
        except:
            return []
    finally:
        if conn:
            conn.close()

def get_user_billing_details(user_id):
    """Obtiene detalles completos de billing para un usuario específico"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
        
        cur = conn.cursor()
        
        # Información del usuario con billing + custom quotas
        cur.execute('''
            SELECT 
                id, email, name, picture, role, is_active, created_at,
                plan, current_plan, billing_status, quota_limit, quota_used,
                quota_reset_date, stripe_customer_id, subscription_id,
                current_period_start, current_period_end, pending_plan, pending_plan_date,
                ai_overview_paused_until, ai_overview_paused_at, ai_overview_paused_reason,
                custom_quota_limit, custom_quota_notes, custom_quota_assigned_by, custom_quota_assigned_date
            FROM users 
            WHERE id = %s
        ''', (user_id,))
        
        user = cur.fetchone()
        if not user:
            return None
        
        user_dict = dict(user)
        
        # Obtener histórico de uso reciente (si existe la tabla)
        try:
            cur.execute('''
                SELECT 
                    DATE(timestamp) as day,
                    SUM(ru_consumed) as ru_consumed,
                    COUNT(*) as operations
                FROM quota_usage_events 
                WHERE user_id = %s 
                AND timestamp >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY DATE(timestamp)
                ORDER BY day DESC
                LIMIT 10
            ''', (user_id,))
            
            usage_history = [dict(row) for row in cur.fetchall()]
            user_dict['usage_history'] = usage_history
        except:
            user_dict['usage_history'] = []
        
        # Calcular estadísticas
        if user_dict['quota_limit'] > 0:
            user_dict['quota_percentage'] = round((user_dict['quota_used'] / user_dict['quota_limit']) * 100, 1)
        else:
            user_dict['quota_percentage'] = 0

        # Enriquecer con métricas SERP/LLM para el modal
        serp_usage = _get_serp_usage_by_user(cur)
        ru_usage = _get_ru_usage_by_user(cur)
        llm_usage = _get_llm_usage_by_user(cur)
        llm_projects = _get_llm_active_projects_by_user(cur)
        ai_mode_paused = _get_ai_mode_paused_projects_by_user(cur)
        llm_paused = _get_llm_paused_projects_by_user(cur)
        invitations = _get_invitations_by_user(cur)
        project_counts = _get_project_counts_by_user(cur)

        serp_row = serp_usage.get(user_id, {})
        ru_row = ru_usage.get(user_id, {})
        llm_row = llm_usage.get(user_id, {})
        proj_row = llm_projects.get(user_id, {})
        ai_mode_row = ai_mode_paused.get(user_id, {})
        llm_paused_row = llm_paused.get(user_id, {})
        inv_row = invitations.get(user_id, {})
        pc_row = project_counts.get(user_id, {})

        user_dict['serp_ru_month'] = int(serp_row.get('serp_ru_month', 0) or 0)
        user_dict['ru_month'] = int(ru_row.get('ru_month', 0) or 0)
        user_dict['llm_units_month'] = int(llm_row.get('llm_units_month', 0) or 0)
        user_dict['llm_cost_month'] = float(llm_row.get('llm_cost_month', 0) or 0)
        user_dict['llm_active_projects'] = int(proj_row.get('active_projects', 0) or 0)
        user_dict['ai_mode_paused_projects'] = int(ai_mode_row.get('paused_projects', 0) or 0)
        user_dict['llm_paused_projects'] = int(llm_paused_row.get('paused_projects', 0) or 0)
        # Invitaciones
        user_dict['invitations_sent'] = int(inv_row.get('total_sent', 0) or 0)
        user_dict['invitations_accepted'] = int(inv_row.get('accepted', 0) or 0)
        user_dict['invitations_pending'] = int(inv_row.get('pending', 0) or 0)
        # Proyectos por módulo
        user_dict['aio_total'] = pc_row.get('aio_total', 0)
        user_dict['aio_active'] = pc_row.get('aio_active', 0)
        user_dict['aim_total'] = pc_row.get('aim_total', 0)
        user_dict['aim_active'] = pc_row.get('aim_active', 0)
        user_dict['llm_total'] = pc_row.get('llm_total', 0)
        user_dict['llm_active'] = pc_row.get('llm_active', 0)

        return user_dict
        
    except Exception as e:
        logger.error(f"Error obteniendo detalles de billing para usuario {user_id}: {e}")
        return None
    finally:
        if conn:
            conn.close()

def update_user_plan_manual(user_id, new_plan, admin_id):
    """Permite al admin cambiar el plan de un usuario manualmente (para testing o soporte)"""
    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Database connection failed'}
        
        cur = conn.cursor()
        
        # Validar plan
        valid_plans = ['free', 'basic', 'premium', 'business', 'enterprise']
        if new_plan not in valid_plans:
            return {'success': False, 'error': f'Plan inválido. Debe ser: {", ".join(valid_plans)}'}
        
        # Obtener límites de cuota según plan
        quota_limits = {
            'free': 0,
            'basic': 1225,
            'premium': 2950,
            'business': 8000,
            'enterprise': 0  # Enterprise usa custom_quota_limit
        }
        
        new_quota_limit = quota_limits[new_plan]
        
        # Actualizar usuario
        # ✅ FIX: Preservar billing_status si ya es 'active' o 'trialing' (suscripción Stripe válida)
        cur.execute('''
            UPDATE users
            SET
                plan = %s,
                current_plan = %s,
                quota_limit = %s,
                billing_status = CASE
                    WHEN billing_status IN ('active', 'trialing') THEN billing_status
                    WHEN %s = 'free' THEN 'active'
                    ELSE 'beta'
                END,
                updated_at = NOW()
            WHERE id = %s
        ''', (new_plan, new_plan, new_quota_limit, new_plan, user_id))
        
        if cur.rowcount == 0:
            return {'success': False, 'error': 'Usuario no encontrado'}
        
        # Log de la acción
        logger.info(f"Admin {admin_id} cambió plan de usuario {user_id} a {new_plan}")

        conn.commit()

        # ✅ Audit log
        log_admin_action(admin_id, 'plan_change', user_id, {
            'new_plan': new_plan, 'new_quota_limit': new_quota_limit
        })

        return {
            'success': True,
            'message': f'Plan actualizado a {new_plan} ({new_quota_limit} RU/mes)',
            'new_plan': new_plan,
            'new_quota_limit': new_quota_limit
        }
        
    except Exception as e:
        logger.error(f"Error actualizando plan manual: {e}")
        return {'success': False, 'error': 'Error interno del servidor'}
    finally:
        if conn:
            conn.close()

def get_plan_display_info(plan):
    """Retorna información visual para mostrar planes en el panel admin"""
    plan_info = {
        'free': {
            'name': 'Free',
            'badge_class': 'badge-free',
            'ru_limit': 0,
            'price': '€0',
            'color': '#6c757d'
        },
        'basic': {
            'name': 'Basic',
            'badge_class': 'badge-basic', 
            'ru_limit': 1225,
            'price': '€29.99',
            'color': '#007bff'
        },
        'premium': {
            'name': 'Premium',
            'badge_class': 'badge-premium',
            'ru_limit': 2950, 
            'price': '€49.99',
            'color': '#28a745'
        },
        'business': {
            'name': 'Business',
            'badge_class': 'badge-business',
            'ru_limit': 8000,
            'price': '€139.99',
            'color': '#17a2b8'
        },
        'enterprise': {
            'name': 'Enterprise',
            'badge_class': 'badge-enterprise',
            'ru_limit': 'Custom',
            'price': 'Custom',
            'color': '#6f42c1'
        }
    }
    
    return plan_info.get(plan, {
        'name': plan.title(),
        'badge_class': 'badge-unknown',
        'ru_limit': 0,
        'price': '€?',
        'color': '#ffc107'
    })

def get_billing_status_display_info(billing_status):
    """Retorna información visual para estados de billing"""
    status_info = {
        'active': {
            'name': 'Active',
            'badge_class': 'badge-active',
            'color': '#28a745',
            'icon': 'fas fa-check-circle'
        },
        'past_due': {
            'name': 'Past Due', 
            'badge_class': 'badge-past-due',
            'color': '#ffc107',
            'icon': 'fas fa-exclamation-triangle'
        },
        'canceled': {
            'name': 'Canceled',
            'badge_class': 'badge-canceled',
            'color': '#dc3545',
            'icon': 'fas fa-times-circle'
        },
        'beta': {
            'name': 'Beta',
            'badge_class': 'badge-beta',
            'color': '#6f42c1',
            'icon': 'fas fa-flask'
        }
    }
    
    return status_info.get(billing_status, {
        'name': billing_status.title(),
        'badge_class': 'badge-unknown',
        'color': '#6c757d',
        'icon': 'fas fa-question-circle'
    })

def assign_custom_quota(user_id, custom_limit, notes, admin_id):
    """Asigna una cuota personalizada a un usuario (para planes Enterprise)"""
    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Database connection failed'}
        
        cur = conn.cursor()
        
        # Validar que custom_limit sea un número positivo
        try:
            custom_limit = int(custom_limit)
            if custom_limit < 0:
                return {'success': False, 'error': 'Custom limit must be >= 0'}
        except (ValueError, TypeError):
            return {'success': False, 'error': 'Custom limit must be a valid number'}
        
        # Obtener información del admin que asigna
        cur.execute('SELECT name, email FROM users WHERE id = %s', (admin_id,))
        admin_info = cur.fetchone()
        admin_name = admin_info['email'] if admin_info else f'Admin ID {admin_id}'
        
        # Actualizar usuario con custom quota
        cur.execute('''
            UPDATE users 
            SET 
                custom_quota_limit = %s,
                custom_quota_notes = %s,
                custom_quota_assigned_by = %s,
                custom_quota_assigned_date = NOW(),
                -- También actualizar plan a enterprise si no lo es
                plan = CASE WHEN plan != 'enterprise' THEN 'enterprise' ELSE plan END,
                current_plan = CASE WHEN current_plan != 'enterprise' THEN 'enterprise' ELSE current_plan END,
                updated_at = NOW()
            WHERE id = %s
        ''', (custom_limit, notes, admin_name, user_id))
        
        if cur.rowcount == 0:
            return {'success': False, 'error': 'Usuario no encontrado'}
        
        # Log de la acción
        logger.info(f"Admin {admin_id} ({admin_name}) asignó custom quota {custom_limit} RU a usuario {user_id}")

        conn.commit()

        # ✅ Audit log
        log_admin_action(admin_id, 'assign_custom_quota', user_id, {
            'custom_limit': custom_limit, 'notes': notes
        })

        return {
            'success': True,
            'message': f'Custom quota assigned: {custom_limit} RU/month',
            'custom_limit': custom_limit,
            'assigned_by': admin_name,
            'assigned_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
    except Exception as e:
        logger.error(f"Error asignando custom quota: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {'success': False, 'error': f'Database error: {str(e)}'}
    finally:
        if conn:
            conn.close()

def remove_custom_quota(user_id, admin_id):
    """Remueve la cuota personalizada de un usuario (vuelve a plan estándar)"""
    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Database connection failed'}
        
        cur = conn.cursor()
        
        # Obtener información del admin
        cur.execute('SELECT name, email FROM users WHERE id = %s', (admin_id,))
        admin_info = cur.fetchone()
        admin_name = admin_info['email'] if admin_info else f'Admin ID {admin_id}'
        
        # Remover custom quota y volver a plan free por defecto
        cur.execute('''
            UPDATE users 
            SET 
                custom_quota_limit = NULL,
                custom_quota_notes = NULL,
                custom_quota_assigned_by = NULL,
                custom_quota_assigned_date = NULL,
                plan = 'free',
                current_plan = 'free',
                quota_limit = 0,
                updated_at = NOW()
            WHERE id = %s
        ''', (user_id,))
        
        if cur.rowcount == 0:
            return {'success': False, 'error': 'Usuario no encontrado'}
        
        # Log de la acción
        logger.info(f"Admin {admin_id} ({admin_name}) removió custom quota de usuario {user_id}")

        conn.commit()

        # ✅ Audit log
        log_admin_action(admin_id, 'remove_custom_quota', user_id, {})

        return {
            'success': True,
            'message': 'Custom quota removed. User reverted to Free plan.',
            'reverted_to': 'free'
        }
        
    except Exception as e:
        logger.error(f"Error removiendo custom quota: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {'success': False, 'error': f'Database error: {str(e)}'}
    finally:
        if conn:
            conn.close()

def get_effective_quota_limit(user_data):
    """Calcula el límite de cuota efectivo para un usuario (custom o plan estándar)"""
    if user_data.get('custom_quota_limit') is not None:
        return user_data['custom_quota_limit']
    
    # Usar límite del plan estándar
    plan_limits = {
        'free': 0,
        'basic': 1225,
        'premium': 2950,
        'business': 8000,
        'enterprise': 0  # Sin custom quota = sin acceso
    }
    
    return plan_limits.get(user_data.get('plan', 'free'), 0)

def get_custom_quota_users():
    """Obtiene todos los usuarios que tienen custom quotas asignadas"""
    try:
        conn = get_db_connection()
        if not conn:
            return []
        
        cur = conn.cursor()
        
        cur.execute('''
            SELECT 
                id, email, name, plan, current_plan, quota_used,
                custom_quota_limit, custom_quota_notes, 
                custom_quota_assigned_by, custom_quota_assigned_date
            FROM users 
            WHERE custom_quota_limit IS NOT NULL
            ORDER BY custom_quota_assigned_date DESC
        ''')
        
        users = cur.fetchall()
        return [dict(user) for user in users]
        
    except Exception as e:
        logger.error(f"Error obteniendo usuarios con custom quota: {e}")
        return []
    finally:
        if conn:
            conn.close()

# Función de prueba
def test_billing_functions():
    """Función para probar las nuevas funcionalidades de billing"""
    print("🧪 TESTING BILLING FUNCTIONS")
    print("=" * 40)
    
    # Test stats
    stats = get_billing_stats()
    print(f"Stats: {stats}")
    
    # Test usuarios
    users = get_users_with_billing()
    print(f"Usuarios encontrados: {len(users)}")
    
    if users:
        user_sample = users[0]
        print(f"Usuario ejemplo: {user_sample['email']} - Plan: {user_sample.get('plan', 'unknown')}")
        
        # Test detalles
        details = get_user_billing_details(user_sample['id'])
        if details:
            print(f"Detalles: Plan {details.get('plan')}, Cuota: {details.get('quota_used')}/{details.get('quota_limit')}")

def reset_user_quota_manual(user_id: int, admin_id: int) -> dict:
    """
    Resetea manualmente la quota de un usuario (admin override)
    
    Args:
        user_id: ID del usuario cuya quota resetear
        admin_id: ID del admin que hace el reset
        
    Returns:
        dict: {'success': bool, 'message': str, 'error': str}
    """
    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Database connection failed'}
        
        cur = conn.cursor()
        
        # Verificar que el admin existe
        cur.execute('SELECT email FROM users WHERE id = %s AND role = %s', (admin_id, 'admin'))
        admin_info = cur.fetchone()
        
        if not admin_info:
            return {'success': False, 'error': 'Admin not found or insufficient permissions'}
        
        # Verificar que el usuario existe y obtener quota actual
        cur.execute('''
            SELECT email, quota_used, plan, current_period_start, current_period_end, quota_reset_date
            FROM users
            WHERE id = %s
        ''', (user_id,))
        user_info = cur.fetchone()
        
        if not user_info:
            return {'success': False, 'error': 'User not found'}
        
        previous_quota_used = user_info['quota_used'] or 0

        from quota_manager import compute_next_quota_reset_date
        next_reset = compute_next_quota_reset_date(
            period_start=user_info.get('current_period_start'),
            period_end=user_info.get('current_period_end'),
            last_reset=user_info.get('quota_reset_date')
        )

        # Resetear quota_used a 0 y alinear próximo reset
        cur.execute('''
            UPDATE users 
            SET quota_used = 0,
                quota_reset_date = %s,
                updated_at = NOW()
            WHERE id = %s
        ''', (next_reset, user_id))
        
        # Registrar evento de reset en quota_usage_events (si la tabla existe)
        # ✅ FIX: Usar SAVEPOINT para que un fallo del INSERT (e.g. CHECK constraint)
        #    no aborte toda la transacción de PostgreSQL.
        try:
            cur.execute('SAVEPOINT quota_event_insert')
            cur.execute('''
                INSERT INTO quota_usage_events
                (user_id, ru_consumed, source, keyword, country_code, timestamp, metadata)
                VALUES (%s, %s, %s, %s, %s, NOW(), %s)
            ''', (
                user_id,
                0,  # No consume RU, es un reset
                'manual_ai',  # Usar valor permitido por CHECK constraint
                'admin_quota_reset',
                '',
                json.dumps({
                    'reset_by_admin_id': admin_id,
                    'reset_by_admin_email': admin_info['email'],
                    'previous_quota_used': previous_quota_used,
                    'reason': 'Manual admin reset'
                })
            ))
            cur.execute('RELEASE SAVEPOINT quota_event_insert')
        except Exception as event_error:
            # Rollback solo el SAVEPOINT, no toda la transacción
            try:
                cur.execute('ROLLBACK TO SAVEPOINT quota_event_insert')
            except Exception:
                pass
            logger.warning(f"Could not log quota reset event: {event_error}")

        try:
            resume_quota_pauses_for_user(user_id)
        except Exception as resume_error:
            logger.warning(f"Could not resume paused modules for user {user_id}: {resume_error}")
        
        conn.commit()
        
        logger.info(f"✅ Quota reset: user {user_id} ({user_info['email']}) by admin {admin_info['email']}")
        logger.info(f"   Previous usage: {previous_quota_used} RU -> Reset to: 0 RU")

        # ✅ Audit log
        log_admin_action(admin_id, 'quota_reset', user_id, {
            'previous_usage': previous_quota_used
        })

        return {
            'success': True,
            'message': f'Quota reset successfully. Previous usage: {previous_quota_used} RU',
            'previous_usage': previous_quota_used,
            'new_usage': 0,
            'next_reset': next_reset.isoformat() if next_reset else None
        }
        
    except Exception as e:
        logger.error(f"Error resetting quota for user {user_id}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {'success': False, 'error': f'Database error: {str(e)}'}
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    test_billing_functions()
