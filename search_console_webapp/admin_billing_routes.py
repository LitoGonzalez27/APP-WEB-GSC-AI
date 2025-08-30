#!/usr/bin/env python3
"""
Admin Billing Routes - Rutas Flask para el panel de administración de billing
============================================================================

Estas rutas extienden app.py para añadir funcionalidades de gestión de billing.
Añadir estas rutas a app.py después de la migración.
"""

from flask import render_template, request, jsonify
from auth import admin_required, get_current_user
from admin_billing_panel import (
    get_billing_stats, get_users_with_billing, get_user_billing_details,
    update_user_plan_manual, reset_user_quota_manual,
    get_plan_display_info, get_billing_status_display_info
)
import logging

logger = logging.getLogger(__name__)

# ========================================
# RUTAS PARA AÑADIR A app.py
# ========================================

"""
# Añadir estas rutas a app.py después de las rutas admin existentes:

@app.route('/admin/billing')
@admin_required
def admin_billing_panel():
    \"\"\"Panel de administración de billing\"\"\"
    try:
        # Obtener estadísticas de billing
        billing_stats = get_billing_stats()
        
        # Obtener usuarios con información de billing
        users = get_users_with_billing()
        
        # Funciones helper para el template
        def plan_display_info(plan):
            return get_plan_display_info(plan)
        
        def billing_status_display_info(status):
            return get_billing_status_display_info(status)
        
        return render_template('admin_billing.html', 
                             billing_stats=billing_stats,
                             users=users,
                             get_plan_display_info=plan_display_info,
                             get_billing_status_display_info=billing_status_display_info)
                             
    except Exception as e:
        logger.error(f"Error en panel billing: {e}")
        return jsonify({'error': 'Error interno del servidor'}), 500

@app.route('/admin/users/<int:user_id>/billing-details')
@admin_required
def user_billing_details(user_id):
    \"\"\"Obtener detalles completos de billing de un usuario\"\"\"
    try:
        user_details = get_user_billing_details(user_id)
        
        if not user_details:
            return jsonify({'success': False, 'error': 'Usuario no encontrado'}), 404
        
        return jsonify({'success': True, 'user': user_details})
        
    except Exception as e:
        logger.error(f"Error obteniendo detalles billing usuario {user_id}: {e}")
        return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500

@app.route('/admin/users/<int:user_id>/update-plan', methods=['POST'])
@admin_required
def admin_update_user_plan(user_id):
    \"\"\"Actualizar plan de un usuario manualmente (para testing/soporte)\"\"\"
    try:
        data = request.get_json()
        new_plan = data.get('plan')
        
        if not new_plan:
            return jsonify({'success': False, 'error': 'Plan requerido'}), 400
        
        current_admin = get_current_user()
        result = update_user_plan_manual(user_id, new_plan, current_admin['id'])
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error actualizando plan usuario {user_id}: {e}")
        return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500

@app.route('/admin/users/<int:user_id>/reset-quota', methods=['POST'])
@admin_required  
def admin_reset_user_quota(user_id):
    \"\"\"Resetear cuota de un usuario manualmente\"\"\"
    try:
        current_admin = get_current_user()
        result = reset_user_quota_manual(user_id, current_admin['id'])
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error reseteando cuota usuario {user_id}: {e}")
        return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500

@app.route('/admin/billing-stats')
@admin_required
def admin_billing_stats_api():
    \"\"\"API para obtener estadísticas de billing (para gráficos dinámicos)\"\"\"
    try:
        stats = get_billing_stats()
        return jsonify({'success': True, 'stats': stats})
        
    except Exception as e:
        logger.error(f"Error obteniendo stats billing: {e}")
        return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500
"""

# ========================================
# FUNCIONES HELPER PARA DESARROLLO
# ========================================

def test_billing_routes():
    """Función para probar las rutas de billing en desarrollo"""
    print("🧪 TESTING BILLING ROUTES")
    print("=" * 40)
    
    # Test estadísticas
    stats = get_billing_stats()
    print(f"📊 Stats: {stats}")
    
    # Test usuarios
    users = get_users_with_billing()
    print(f"👥 Usuarios: {len(users)} encontrados")
    
    if users:
        # Test primer usuario
        user_sample = users[0]
        print(f"👤 Usuario ejemplo: {user_sample['email']}")
        
        details = get_user_billing_details(user_sample['id'])
        if details:
            print(f"💳 Plan: {details.get('plan')}, Cuota: {details.get('quota_used')}/{details.get('quota_limit')}")

def generate_admin_billing_integration_code():
    """Genera el código para integrar en app.py"""
    integration_code = '''
# ========================================
# ADMIN BILLING ROUTES - AÑADIR A app.py
# ========================================

from admin_billing_panel import (
    get_billing_stats, get_users_with_billing, get_user_billing_details,
    update_user_plan_manual, reset_user_quota_manual,
    get_plan_display_info, get_billing_status_display_info
)

@app.route('/admin/billing')
@admin_required
def admin_billing_panel():
    """Panel de administración de billing"""
    try:
        billing_stats = get_billing_stats()
        users = get_users_with_billing()
        
        def plan_display_info(plan):
            return get_plan_display_info(plan)
        
        def billing_status_display_info(status):
            return get_billing_status_display_info(status)
        
        return render_template('admin_billing.html', 
                             billing_stats=billing_stats,
                             users=users,
                             get_plan_display_info=plan_display_info,
                             get_billing_status_display_info=billing_status_display_info)
                             
    except Exception as e:
        logger.error(f"Error en panel billing: {e}")
        return jsonify({'error': 'Error interno del servidor'}), 500

@app.route('/admin/users/<int:user_id>/billing-details')
@admin_required
def user_billing_details(user_id):
    """Obtener detalles completos de billing de un usuario"""
    try:
        user_details = get_user_billing_details(user_id)
        
        if not user_details:
            return jsonify({'success': False, 'error': 'Usuario no encontrado'}), 404
        
        return jsonify({'success': True, 'user': user_details})
        
    except Exception as e:
        logger.error(f"Error obteniendo detalles billing usuario {user_id}: {e}")
        return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500

@app.route('/admin/users/<int:user_id>/update-plan', methods=['POST'])
@admin_required
def admin_update_user_plan(user_id):
    """Actualizar plan de un usuario manualmente"""
    try:
        data = request.get_json()
        new_plan = data.get('plan')
        
        if not new_plan:
            return jsonify({'success': False, 'error': 'Plan requerido'}), 400
        
        current_admin = get_current_user()
        result = update_user_plan_manual(user_id, new_plan, current_admin['id'])
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error actualizando plan usuario {user_id}: {e}")
        return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500

@app.route('/admin/users/<int:user_id>/reset-quota', methods=['POST'])
@admin_required  
def admin_reset_user_quota(user_id):
    """Resetear cuota de un usuario manualmente"""
    try:
        current_admin = get_current_user()
        result = reset_user_quota_manual(user_id, current_admin['id'])
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error reseteando cuota usuario {user_id}: {e}")
        return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500
'''
    
    print("📋 CÓDIGO DE INTEGRACIÓN PARA app.py:")
    print("=" * 50)
    print(integration_code)
    
    return integration_code

if __name__ == "__main__":
    test_billing_routes()
    print("\n" + "="*50)
    generate_admin_billing_integration_code()
