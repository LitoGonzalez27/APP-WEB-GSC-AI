"""
Rutas para gestión de proyectos AI Mode
"""

import logging
from flask import render_template, request, jsonify
from auth import auth_required, get_current_user
from ai_mode_projects import ai_mode_bp
from ai_mode_projects.services.project_service import ProjectService
from ai_mode_projects.utils.validators import check_ai_mode_access

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
    return render_template('ai_mode_dashboard.html', user=user)


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
    has_access, error_response = check_ai_mode_access(user)
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
    has_access, error_response = check_ai_mode_access(user)
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
    """
    Eliminar completamente un proyecto AI Mode y todos sus datos
    
    Args:
        project_id: ID del proyecto
    
    Returns:
        JSON con resultado de la eliminación y estadísticas
    """
    user = get_current_user()
    
    result = project_service.delete_project(project_id, user['id'])
    
    if result['success']:
        return jsonify({
            'success': True,
            'message': f'AI Mode project "{result.get("project_name", "")}" deleted successfully',
            'stats': result.get('stats', {})
        })
    else:
        status_code = 404 if 'not found' in result.get('error', '').lower() else 500
        return jsonify(result), status_code

