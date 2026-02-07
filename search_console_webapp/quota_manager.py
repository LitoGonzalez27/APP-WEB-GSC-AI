#!/usr/bin/env python3
"""
QUOTA MANAGER - Lógica Central de Gestión de Quotas
=================================================

Maneja toda la lógica de quotas incluyendo:
- Límites por plan (Free, Basic, Premium)
- Custom quotas para Enterprise
- Validación de acceso antes de consumir RU
- Tracking de uso de quotas
"""

import os
import logging
from datetime import datetime, timedelta
from database import get_db_connection

logger = logging.getLogger(__name__)

# Configuración de límites por plan
PLAN_LIMITS = {
    'free': 0,
    'basic': 1225,
    'premium': 2950,
    'business': 8000,
    'enterprise': 0  # Enterprise usa custom_quota_limit
}

# Precios para estadísticas
PLAN_PRICES = {
    'free': 0,
    'basic': 29.99,
    'premium': 49.99,
    'business': 139.99,
    'enterprise': 0  # Custom pricing
}

def compute_next_quota_reset_date(period_start=None, period_end=None, last_reset=None, now=None):
    """
    Calcula la próxima fecha de reset de quota.
    Usa intervalo mensual fijo (30 días) para respetar cuotas "por mes",
    incluso en planes anuales.
    """
    interval_days = int(os.getenv('QUOTA_RESET_INTERVAL_DAYS', '30'))
    now = now or datetime.utcnow()
    base = last_reset or period_start or now
    if isinstance(base, str):
        try:
            base = datetime.fromisoformat(base)
        except Exception:
            base = now
    next_reset = base + timedelta(days=interval_days)

    # Si hay periodo Stripe, no pasar el fin del periodo actual
    if period_end and next_reset > period_end:
        next_reset = period_end

    # Si quedó en el pasado, avanzar hasta futuro (sin pasar el periodo)
    while next_reset <= now:
        candidate = next_reset + timedelta(days=interval_days)
        if period_end and candidate > period_end:
            next_reset = period_end
            break
        next_reset = candidate

    return next_reset

def get_user_effective_quota_limit(user_id):
    """
    Obtiene el límite de quota efectivo para un usuario
    Prioriza custom_quota_limit sobre plan estándar
    """
    try:
        conn = get_db_connection()
        if not conn:
            return 0
        
        cur = conn.cursor()
        
        cur.execute('''
            SELECT 
                plan,
                custom_quota_limit,
                quota_limit
            FROM users 
            WHERE id = %s
        ''', (user_id,))
        
        user = cur.fetchone()
        if not user:
            return 0
        
        # user es un RealDictRow, usar como diccionario
        plan = user['plan']
        custom_quota_limit = user['custom_quota_limit']
        quota_limit = user['quota_limit']
        
        # Prioridad: custom_quota_limit > quota_limit > plan default (asegurar int)
        if custom_quota_limit is not None:
            return int(custom_quota_limit)
        elif quota_limit is not None and quota_limit > 0:
            return int(quota_limit)
        else:
            return PLAN_LIMITS.get(plan, 0)
            
    except Exception as e:
        logger.error(f"Error obteniendo límite de quota para usuario {user_id}: {e}")
        return 0
    finally:
        if conn:
            conn.close()

def get_user_quota_status(user_id):
    """
    Obtiene el estado completo de quota de un usuario
    Retorna: limit, used, remaining, percentage, can_consume
    """
    try:
        conn = get_db_connection()
        if not conn:
            return {
                'quota_limit': 0, 'quota_used': 0, 'remaining': 0, 
                'percentage': 0, 'can_consume': False,
                'plan': 'unknown', 'is_custom': False
            }
        
        cur = conn.cursor()
        
        cur.execute('''
            SELECT 
                plan, quota_used, custom_quota_limit, quota_limit, quota_reset_date
            FROM users 
            WHERE id = %s
        ''', (user_id,))
        
        user = cur.fetchone()
        if not user:
            return {
                'quota_limit': 0, 'quota_used': 0, 'remaining': 0, 
                'percentage': 0, 'can_consume': False,
                'plan': 'unknown', 'is_custom': False
            }
        
        # user es un RealDictRow, usar como diccionario
        plan = user['plan']
        quota_used = user['quota_used']
        custom_quota_limit = user['custom_quota_limit']
        quota_limit = user['quota_limit']
        quota_reset_date = user['quota_reset_date']
        
        # Determinar límite efectivo (asegurar conversión a int)
        is_custom = custom_quota_limit is not None
        if is_custom:
            effective_limit = int(custom_quota_limit or 0)
        elif quota_limit is not None and quota_limit > 0:
            effective_limit = int(quota_limit)
        else:
            effective_limit = PLAN_LIMITS.get(plan, 0)
        
        # Calcular estadísticas (asegurar conversión a int)
        used = int(quota_used or 0)
        remaining = max(0, effective_limit - used)
        percentage = round((used / effective_limit * 100), 1) if effective_limit > 0 else 0
        can_consume = remaining > 0
        
        return {
            'quota_limit': effective_limit,
            'quota_used': used,
            'remaining': remaining,
            'percentage': percentage,
            'can_consume': can_consume,
            'plan': plan,
            'is_custom': is_custom,
            'reset_date': quota_reset_date
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo estado de quota para usuario {user_id}: {e}")
        return {
            'quota_limit': 0, 'quota_used': 0, 'remaining': 0, 
            'percentage': 0, 'can_consume': False,
            'plan': 'unknown', 'is_custom': False
        }
    finally:
        if conn:
            conn.close()

def can_user_consume_ru(user_id, ru_amount=1):
    """
    Verifica si un usuario puede consumir una cantidad específica de RU
    """
    quota_status = get_user_quota_status(user_id)
    return quota_status['remaining'] >= ru_amount

def consume_user_quota(user_id, ru_amount, operation_type="api_call", metadata=None):
    """
    Consume quota de un usuario y registra el uso
    Retorna: {'success': bool, 'message': str, 'remaining': int}
    """
    try:
        # Verificar si puede consumir
        if not can_user_consume_ru(user_id, ru_amount):
            quota_status = get_user_quota_status(user_id)
            return {
                'success': False,
                'message': f'Quota limit exceeded. Used: {quota_status["used"]}/{quota_status["limit"]} RU',
                'remaining': quota_status['remaining'],
                'error_code': 'QUOTA_EXCEEDED'
            }
        
        conn = get_db_connection()
        if not conn:
            return {
                'success': False,
                'message': 'Database connection failed',
                'remaining': 0,
                'error_code': 'DB_ERROR'
            }
        
        cur = conn.cursor()
        
        # Actualizar quota del usuario
        cur.execute('''
            UPDATE users 
            SET 
                quota_used = COALESCE(quota_used, 0) + %s,
                updated_at = NOW()
            WHERE id = %s
        ''', (ru_amount, user_id))
        
        if cur.rowcount == 0:
            return {
                'success': False,
                'message': 'User not found',
                'remaining': 0,
                'error_code': 'USER_NOT_FOUND'
            }
        
        # TODO: Registrar en quota_usage_events cuando la tabla exista
        # cur.execute('''
        #     INSERT INTO quota_usage_events 
        #     (user_id, ru_consumed, operation_type, metadata, timestamp)
        #     VALUES (%s, %s, %s, %s, NOW())
        # ''', (user_id, ru_amount, operation_type, metadata))
        
        conn.commit()
        
        # Obtener estado actualizado
        updated_status = get_user_quota_status(user_id)
        
        logger.info(f"Usuario {user_id} consumió {ru_amount} RU. Restante: {updated_status['remaining']}")
        
        return {
            'success': True,
            'message': f'Consumed {ru_amount} RU successfully',
            'remaining': updated_status['remaining'],
            'used': updated_status['used'],
            'limit': updated_status['limit']
        }
        
    except Exception as e:
        logger.error(f"Error consumiendo quota para usuario {user_id}: {e}")
        return {
            'success': False,
            'message': 'Internal server error',
            'remaining': 0,
            'error_code': 'INTERNAL_ERROR'
        }
    finally:
        if conn:
            conn.close()

def get_user_access_permissions(user_id):
    """
    Obtiene los permisos de acceso de un usuario basado en su plan y quota
    """
    quota_status = get_user_quota_status(user_id)
    plan = quota_status['plan']
    has_quota = quota_status['can_consume']
    
    permissions = {
        'can_use_ai_overview': False,
        'can_use_manual_ai': False,
        'can_use_serp_api': False,
        'quota_status': quota_status
    }
    
    # Free plan: Sin acceso a features de AI
    if plan == 'free':
        permissions.update({
            'can_use_ai_overview': False,
            'can_use_manual_ai': False,
            'can_use_serp_api': False
        })
    
    # Basic, Premium, Business, Enterprise: Acceso completo si tienen quota
    elif plan in ['basic', 'premium', 'business', 'enterprise']:
        permissions.update({
            'can_use_ai_overview': has_quota,
            'can_use_manual_ai': has_quota,
            'can_use_serp_api': has_quota
        })
    
    return permissions

def reset_user_quota(user_id, admin_id=None):
    """
    Resetea la quota usada de un usuario (para admins o billing cycle)
    """
    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Database connection failed'}
        
        cur = conn.cursor()
        
        # Obtener periodo actual para alinear reset
        cur.execute('''
            SELECT current_period_start, current_period_end, quota_reset_date
            FROM users WHERE id = %s
        ''', (user_id,))
        row = cur.fetchone() or {}
        next_reset = compute_next_quota_reset_date(
            period_start=row.get('current_period_start'),
            period_end=row.get('current_period_end'),
            last_reset=row.get('quota_reset_date')
        )

        # Resetear quota
        cur.execute('''
            UPDATE users 
            SET 
                quota_used = 0,
                quota_reset_date = %s,
                updated_at = NOW()
            WHERE id = %s
        ''', (next_reset, user_id))
        
        if cur.rowcount == 0:
            return {'success': False, 'error': 'Usuario no encontrado'}
        
        conn.commit()
        
        action_by = f"admin {admin_id}" if admin_id else "billing cycle"
        logger.info(f"Quota reset for user {user_id} by {action_by}")
        
        return {'success': True, 'message': 'Quota reset successfully'}
        
    except Exception as e:
        logger.error(f"Error resetting quota for user {user_id}: {e}")
        return {'success': False, 'error': 'Internal server error'}
    finally:
        if conn:
            conn.close()

def get_quota_statistics():
    """
    Obtiene estadísticas generales de uso de quotas
    """
    try:
        conn = get_db_connection()
        if not conn:
            return {}
        
        cur = conn.cursor()
        
        # Estadísticas por plan
        cur.execute('''
            SELECT 
                plan,
                COUNT(*) as users,
                SUM(COALESCE(quota_used, 0)) as total_used,
                SUM(CASE 
                    WHEN custom_quota_limit IS NOT NULL THEN custom_quota_limit
                    WHEN quota_limit IS NOT NULL THEN quota_limit
                    ELSE 0
                END) as total_limit
            FROM users 
            GROUP BY plan
            ORDER BY plan
        ''')
        
        plan_stats = [dict(row) for row in cur.fetchall()]
        
        # Usuarios con custom quotas
        cur.execute('''
            SELECT COUNT(*) as custom_quota_users
            FROM users 
            WHERE custom_quota_limit IS NOT NULL
        ''')
        
        custom_count = cur.fetchone()[0]
        
        return {
            'plan_statistics': plan_stats,
            'custom_quota_users': custom_count,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas de quota: {e}")
        return {}
    finally:
        if conn:
            conn.close()

# Funciones de testing
def test_quota_manager():
    """Función para probar el quota manager"""
    print("🧪 TESTING QUOTA MANAGER")
    print("=" * 40)
    
    # Obtener primer usuario para testing
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT id, email, plan FROM users LIMIT 1')
        result = cur.fetchone()
        
        if result:
            # result es un RealDictRow (diccionario)
            user_id = result['id']
            email = result['email'] 
            plan = result['plan']
            print(f"Testing con usuario: {email} (ID: {user_id}, Plan: {plan})")
            
            # Test estado de quota
            status = get_user_quota_status(user_id)
            print(f"Estado quota: Limit={status['limit']}, Used={status['used']}, Can_consume={status['can_consume']}")
            
            # Test permisos
            permissions = get_user_access_permissions(user_id)
            print(f"Permisos: AI Overview: {permissions['ai_overview_access']}, Manual AI: {permissions['manual_ai_access']}")
            
            # Test de consumo (simulado)
            print(f"¿Puede consumir 1 RU? {can_user_consume_ru(user_id, 1)}")
            
            # Test estadísticas
            stats = get_quota_statistics()
            print(f"Planes encontrados: {len(stats.get('plan_statistics', []))}")
            print(f"Usuarios con custom quota: {stats.get('custom_quota_users', 0)}")
            
        else:
            print("No users found for testing")
            
    except Exception as e:
        print(f"Error in testing: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            conn.close()

def record_quota_usage(user_id, ru_consumed, operation_type="unknown", metadata=None):
    """
    Registra el consumo de RU por parte de un usuario
    
    Args:
        user_id: ID del usuario
        ru_consumed: Cantidad de RU consumidos
        operation_type: Tipo de operación (serp_json, serp_html, serp_screenshot)
        metadata: Información adicional (dict)
    
    Returns:
        bool: True si se registró exitosamente
    """
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("No se pudo conectar a la base de datos para registrar quota usage")
            return False
        
        cur = conn.cursor()
        
        # Actualizar quota_used en tabla users
        cur.execute('''
            UPDATE users 
            SET quota_used = COALESCE(quota_used, 0) + %s,
                updated_at = NOW()
            WHERE id = %s
        ''', (ru_consumed, user_id))
        
        # Registrar evento en quota_usage_events si la tabla existe
        try:
            import json
            cur.execute('''
                INSERT INTO quota_usage_events 
                (user_id, ru_consumed, operation_type, metadata, created_at) 
                VALUES (%s, %s, %s, %s, NOW())
            ''', (
                user_id, 
                ru_consumed, 
                operation_type,
                json.dumps(metadata) if metadata else None
            ))
        except Exception as e:
            # Si la tabla no existe, continuar (no es crítico)
            logger.warning(f"Could not log to quota_usage_events: {e}")
        
        conn.commit()
        
        logger.info(f"📊 Recorded {ru_consumed} RU usage for user {user_id} ({operation_type})")
        return True
        
    except Exception as e:
        logger.error(f"Error recording quota usage for user {user_id}: {e}")
        return False
    finally:
        if conn:
            conn.close()

def reset_user_quota(user_id, admin_id=None):
    """
    Resetea la quota de un usuario a 0
    
    Args:
        user_id: ID del usuario
        admin_id: ID del admin que hace el reset (opcional)
    
    Returns:
        bool: True si se reseteó exitosamente
    """
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("No se pudo conectar a la base de datos para resetear quota")
            return False
        
        cur = conn.cursor()
        
        # Obtener usage actual antes del reset
        cur.execute('SELECT quota_used FROM users WHERE id = %s', (user_id,))
        result = cur.fetchone()
        previous_usage = result['quota_used'] if result else 0
        
        # Obtener periodo actual para alinear reset
        cur.execute('''
            SELECT current_period_start, current_period_end, quota_reset_date
            FROM users WHERE id = %s
        ''', (user_id,))
        row = cur.fetchone() or {}
        next_reset = compute_next_quota_reset_date(
            period_start=row.get('current_period_start'),
            period_end=row.get('current_period_end'),
            last_reset=row.get('quota_reset_date')
        )

        # Resetear quota_used a 0
        cur.execute('''
            UPDATE users 
            SET quota_used = 0,
                quota_reset_date = %s,
                updated_at = NOW()
            WHERE id = %s
        ''', (next_reset, user_id))
        
        # Registrar evento de reset
        try:
            import json
            cur.execute('''
                INSERT INTO quota_usage_events 
                (user_id, ru_consumed, operation_type, metadata, created_at) 
                VALUES (%s, %s, %s, %s, NOW())
            ''', (
                user_id, 
                0,  # No consume RU, es un reset
                'quota_reset',
                json.dumps({
                    'previous_usage': previous_usage,
                    'reset_by_admin': admin_id,
                    'reason': 'Manual quota reset'
                })
            ))
        except Exception as e:
            logger.warning(f"Could not log quota reset event: {e}")
        
        conn.commit()
        
        logger.info(f"🔄 Reset quota for user {user_id}: {previous_usage} RU -> 0 RU")
        return True
        
    except Exception as e:
        logger.error(f"Error resetting quota for user {user_id}: {e}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    test_quota_manager()
