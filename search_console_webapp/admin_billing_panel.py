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
        
        # Query que incluye todos los campos de billing
        cur.execute('''
            SELECT 
                id, email, name, picture, role, is_active, 
                created_at, updated_at, google_id,
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
                pending_plan_date
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
        
        # Información del usuario con billing
        cur.execute('''
            SELECT 
                id, email, name, picture, role, is_active, created_at,
                plan, current_plan, billing_status, quota_limit, quota_used,
                quota_reset_date, stripe_customer_id, subscription_id,
                current_period_start, current_period_end, pending_plan, pending_plan_date
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
        valid_plans = ['free', 'basic', 'premium']
        if new_plan not in valid_plans:
            return {'success': False, 'error': f'Plan inválido. Debe ser: {", ".join(valid_plans)}'}
        
        # Obtener límites de cuota según plan
        quota_limits = {
            'free': 0,
            'basic': 1225,
            'premium': 2950
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
            'price': '€49.99',  # Ajustar según tu pricing real
            'color': '#28a745'
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

if __name__ == "__main__":
    test_billing_functions()
