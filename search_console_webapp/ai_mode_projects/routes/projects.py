"""
Rutas para gestión de proyectos AI Mode
"""

import logging
from flask import render_template, request, jsonify
from auth import auth_required, get_current_user
from ai_mode_projects import ai_mode_bp
from ai_mode_projects.services.project_service import ProjectService
from ai_mode_projects.utils.validators import check_ai_mode_access
from services.project_access_service import user_has_any_module_access
from llm_monitoring_limits import get_upgrade_options

logger = logging.getLogger(__name__)

# Instancia del servicio
project_service = ProjectService()


@ai_mode_bp.route('/')
@auth_required
def ai_mode_dashboard():
    """
    Dashboard principal del sistema AI Mode Monitoring
    Acceso libre con paywalls en acciones específicas
    
    Returns:
        Renderizado del template ai_mode_dashboard.html
    """
    user = get_current_user()
    logger.info(f"Usuario accediendo AI Mode dashboard: {user.get('email')} (plan: {user.get('plan')})")
    has_shared_access = False
    try:
        has_shared_access = user_has_any_module_access(user.get('id'), 'ai_mode')
    except Exception:
        has_shared_access = False

    access_blocked = user.get('plan') == 'free' and not has_shared_access

    try:
        upgrade_options = get_upgrade_options(user.get('plan', 'free'))
    except Exception:
        upgrade_options = ['basic', 'premium', 'business']

    return render_template(
        'ai_mode_dashboard.html',
        user=user,
        has_shared_access=has_shared_access,
        access_blocked=access_blocked,
        upgrade_options=upgrade_options
    )


@ai_mode_bp.route('/api/projects', methods=['GET'])
@auth_required
def get_projects():
    """
    Obtener todos los proyectos AI Mode del usuario actual
    
    Returns:
        JSON con lista de proyectos
    """
    user = get_current_user()
    logger.info(f"🔍 [AI MODE] Usuario solicitando proyectos: ID={user.get('id')}, Email={user.get('email')}, Plan={user.get('plan')}")
    
    # Control por plan
    has_access, error_response = check_ai_mode_access(user, allow_shared=True)
    if not has_access:
        logger.warning(f"⚠️ [AI MODE] Usuario {user.get('id')} sin acceso: {error_response}")
        return jsonify(error_response), 402
    
    projects = project_service.get_user_projects(user['id'])
    logger.info(f"✅ [AI MODE] Proyectos encontrados para usuario {user.get('id')}: {len(projects)}")
    
    if len(projects) == 0:
        logger.warning(f"⚠️ [AI MODE] ¡NO SE ENCONTRARON PROYECTOS para usuario {user.get('id')}!")
    
    return jsonify({
        'success': True,
        'projects': projects
    })


@ai_mode_bp.route('/api/projects', methods=['POST'])
@auth_required
def create_project():
    """
    Crear un nuevo proyecto AI Mode
    
    Request JSON:
        - name: Nombre del proyecto
        - brand_name: Nombre de la marca a monitorizar
        - description: Descripción (opcional)
        - country_code: Código de país (opcional, default: US)
    
    Returns:
        JSON con resultado de la creación
    """
    user = get_current_user()
    
    # Control por plan
    has_access, error_response = check_ai_mode_access(user)
    if not has_access:
        return jsonify(error_response), 402
    
    data = request.get_json()
    
    # Validaciones básicas
    if not data.get('name') or not data.get('brand_name'):
        return jsonify({'success': False, 'error': 'Name and brand name are required'}), 400
    
    result = project_service.create_project(
        user_id=user['id'],
        name=data['name'],
        description=data.get('description', ''),
        brand_name=data['brand_name'],
        country_code=data.get('country_code', 'US')
    )
    
    if result['success']:
        return jsonify(result), 201
    else:
        return jsonify(result), 500


@ai_mode_bp.route('/api/projects/<int:project_id>', methods=['GET'])
@auth_required
def get_project_details(project_id):
    """
    Obtener detalles completos de un proyecto AI Mode
    
    Args:
        project_id: ID del proyecto
    
    Returns:
        JSON con detalles del proyecto
    """
    user = get_current_user()
    
    # Control por plan
    has_access, error_response = check_ai_mode_access(user, allow_shared=True)
    if not has_access:
        return jsonify(error_response), 402
    
    project = project_service.get_project_details(project_id, user['id'])
    
    if not project:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    return jsonify({
        'success': True,
        'project': project
    })


@ai_mode_bp.route('/api/projects/<int:project_id>', methods=['PUT'])
@auth_required
def update_project(project_id):
    """
    Actualizar un proyecto AI Mode (nombre, descripción)
    
    Args:
        project_id: ID del proyecto
    
    Request JSON:
        - name: Nuevo nombre
        - description: Nueva descripción
    
    Returns:
        JSON con resultado de la actualización
    """
    user = get_current_user()
    data = request.get_json()
    
    # Validar datos requeridos
    if 'name' not in data:
        return jsonify({'success': False, 'error': 'Project name is required'}), 400
    
    result = project_service.update_project(
        project_id=project_id,
        user_id=user['id'],
        name=data['name'],
        description=data.get('description', '')
    )
    
    if result['success']:
        return jsonify(result)
    else:
        status_code = 404 if 'not found' in result.get('error', '').lower() else 400
        return jsonify(result), status_code


@ai_mode_bp.route('/api/projects/<int:project_id>', methods=['DELETE'])
@auth_required
def delete_project(project_id):
    """Permanently delete an AI Mode project. Only allowed if it has been paused first."""
    user = get_current_user()

    result = project_service.delete_project(project_id, user['id'])

    if result['success']:
        return jsonify({
            'success': True,
            'message': f'AI Mode project "{result.get("project_name", "")}" deleted successfully',
            'stats': result.get('stats', {})
        })

    err_text = (result.get('error') or '').lower()
    if result.get('action_required') == 'deactivate_first':
        status_code = 400
    elif 'unauthorized' in err_text:
        status_code = 403
    elif 'not found' in err_text:
        status_code = 404
    else:
        status_code = 500
    return jsonify(result), status_code


@ai_mode_bp.route('/api/projects/<int:project_id>/pause', methods=['PUT'])
@auth_required
def pause_project(project_id):
    """Pause an AI Mode project: stops cron analyses, stops consuming quota,
    keeps all data. Only the owner can pause.
    """
    user = get_current_user()
    result = project_service.pause_project(project_id, user['id'])

    if result.get('success'):
        return jsonify(result), 200

    err_text = (result.get('error') or '').lower()
    if 'unauthorized' in err_text:
        status_code = 403
    elif 'not found' in err_text or 'already' in err_text:
        status_code = 404
    else:
        status_code = 400
    return jsonify(result), status_code


@ai_mode_bp.route('/api/projects/<int:project_id>/resume', methods=['PUT'])
@auth_required
def resume_project(project_id):
    """Resume a paused AI Mode project. Returns 402 with reset_date if quota is exhausted."""
    user = get_current_user()
    result = project_service.resume_project(project_id, user['id'])

    if result.get('success'):
        return jsonify(result), 200

    err_code = (result.get('error') or '').lower()
    if err_code == 'quota_exceeded':
        return jsonify(result), 402
    if 'unauthorized' in err_code:
        return jsonify(result), 403
    if 'not found' in err_code or 'already' in err_code:
        return jsonify(result), 404
    return jsonify(result), 400
