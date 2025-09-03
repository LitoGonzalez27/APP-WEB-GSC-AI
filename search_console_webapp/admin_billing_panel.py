#!/usr/bin/env python3
"""
Admin Billing Panel - Funciones backend para el panel admin con información de billing
===================================================================================

Nuevas funciones para mostrar información de planes, cuotas y billing en el panel admin.
Estas funciones extienden las existentes para incluir datos de Stripe y facturación.
"""

import os
import logging
from datetime import datetime, date
from database import get_db_connection

logger = logging.getLogger(__name__)

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
        cur.execute('SELECT COUNT(*) FROM users')
        total_users = cur.fetchone()[0]
        
        # Usuarios por plan
        cur.execute('''
            SELECT plan, COUNT(*) as count 
            FROM users 
            GROUP BY plan 
            ORDER BY plan
        ''')
        users_by_plan = dict(cur.fetchall())
        
        # Usuarios por estado de billing
        cur.execute('''
            SELECT billing_status, COUNT(*) as count 
            FROM users 
            GROUP BY billing_status 
            ORDER BY billing_status
        ''')
        users_by_billing_status = dict(cur.fetchall())
        
        # RU consumidas hoy (si existe la tabla)
        total_ru_today = 0
        total_ru_month = 0
        try:
            cur.execute('''
                SELECT COALESCE(SUM(ru_consumed), 0) 
                FROM quota_usage_events 
                WHERE timestamp::date = CURRENT_DATE
            ''')
            total_ru_today = cur.fetchone()[0]
            
            cur.execute('''
                SELECT COALESCE(SUM(ru_consumed), 0) 
                FROM quota_usage_events 
                WHERE timestamp >= DATE_TRUNC('month', CURRENT_DATE)
            ''')
            total_ru_month = cur.fetchone()[0]
        except:
            # Tabla quota_usage_events no existe aún
            pass
        
        # Estimación de ingresos mensuales (básico: €29.99, premium: pricing por configurar)
        revenue_estimate = 0
        for plan, count in users_by_plan.items():
            if plan == 'basic':
                revenue_estimate += count * 29.99
            elif plan == 'premium':
                revenue_estimate += count * 49.99  # Estimación, ajustar según tu pricing
        
        return {
            'total_users': total_users,
            'users_by_plan': users_by_plan,
            'users_by_billing_status': users_by_billing_status,
            'total_ru_consumed_today': total_ru_today,
            'total_ru_consumed_month': total_ru_month,
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
            'revenue_estimate_month': 0
        }
    finally:
        if conn:
            conn.close()

def get_users_with_billing():
    """Obtiene todos los usuarios con información de billing para el panel admin"""
    try:
        conn = get_db_connection()
        if not conn:
            return []
        
        cur = conn.cursor()
        
        # Query que incluye todos los campos de billing + custom quotas
        cur.execute('''
            SELECT 
                id, email, name, picture, role, is_active, 
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
                -- Custom quota fields
                custom_quota_limit,
                custom_quota_notes,
                custom_quota_assigned_by,
                custom_quota_assigned_date
            FROM users 
            ORDER BY created_at DESC
        ''')
        
        users = cur.fetchall()
        return [dict(user) for user in users]
        
    except Exception as e:
        logger.error(f"Error obteniendo usuarios con billing: {e}")
        # Fallback a función original si falla
        try:
            cur = conn.cursor()
            cur.execute('''
                SELECT id, email, name, picture, role, is_active, created_at, google_id
                FROM users 
                ORDER BY created_at DESC
            ''')
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
        valid_plans = ['free', 'basic', 'premium', 'enterprise']
        if new_plan not in valid_plans:
            return {'success': False, 'error': f'Plan inválido. Debe ser: {", ".join(valid_plans)}'}
        
        # Obtener límites de cuota según plan
        quota_limits = {
            'free': 0,
            'basic': 1225,
            'premium': 2950,
            'enterprise': 0  # Enterprise usa custom_quota_limit
        }
        
        new_quota_limit = quota_limits[new_plan]
        
        # Actualizar usuario
        cur.execute('''
            UPDATE users 
            SET 
                plan = %s,
                current_plan = %s,
                quota_limit = %s,
                billing_status = CASE 
                    WHEN %s = 'free' THEN 'active'
                    ELSE 'beta'  -- Planes de pago manuales marcados como beta
                END,
                updated_at = NOW()
            WHERE id = %s
        ''', (new_plan, new_plan, new_quota_limit, new_plan, user_id))
        
        if cur.rowcount == 0:
            return {'success': False, 'error': 'Usuario no encontrado'}
        
        # Log de la acción
        logger.info(f"Admin {admin_id} cambió plan de usuario {user_id} a {new_plan}")
        
        conn.commit()
        
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

def reset_user_quota_manual(user_id, admin_id):
    """Permite al admin resetear la cuota de un usuario manualmente"""
    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Database connection failed'}
        
        cur = conn.cursor()
        
        # Resetear cuota
        cur.execute('''
            UPDATE users 
            SET 
                quota_used = 0,
                quota_reset_date = NOW() + INTERVAL '30 days',
                updated_at = NOW()
            WHERE id = %s
        ''', (user_id,))
        
        if cur.rowcount == 0:
            return {'success': False, 'error': 'Usuario no encontrado'}
        
        # Log de la acción
        logger.info(f"Admin {admin_id} reseteo cuota de usuario {user_id}")
        
        conn.commit()
        
        return {'success': True, 'message': 'Cuota reseteada exitosamente'}
        
    except Exception as e:
        logger.error(f"Error reseteando cuota: {e}")
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
            'price': '€59.99',
            'color': '#28a745'
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
        cur.execute('SELECT email, quota_used, plan FROM users WHERE id = %s', (user_id,))
        user_info = cur.fetchone()
        
        if not user_info:
            return {'success': False, 'error': 'User not found'}
        
        previous_quota_used = user_info['quota_used'] or 0
        
        # Resetear quota_used a 0
        cur.execute('''
            UPDATE users 
            SET quota_used = 0, 
                updated_at = NOW()
            WHERE id = %s
        ''', (user_id,))
        
        # Registrar evento de reset en quota_usage_events (si la tabla existe)
        try:
            cur.execute('''
                INSERT INTO quota_usage_events 
                (user_id, ru_consumed, operation_type, metadata, created_at) 
                VALUES (%s, %s, %s, %s, NOW())
            ''', (
                user_id, 
                0,  # No consume RU, es un reset
                'admin_quota_reset',
                json.dumps({
                    'reset_by_admin_id': admin_id,
                    'reset_by_admin_email': admin_info['email'],
                    'previous_quota_used': previous_quota_used,
                    'reason': 'Manual admin reset'
                })
            ))
        except Exception as event_error:
            # Si falla el registro de evento, continuar (no crítico)
            logger.warning(f"Could not log quota reset event: {event_error}")
        
        conn.commit()
        
        logger.info(f"✅ Quota reset: user {user_id} ({user_info['email']}) by admin {admin_info['email']}")
        logger.info(f"   Previous usage: {previous_quota_used} RU -> Reset to: 0 RU")
        
        return {
            'success': True,
            'message': f'Quota reset successfully. Previous usage: {previous_quota_used} RU',
            'previous_usage': previous_quota_used,
            'new_usage': 0
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
