"""
Rutas para gestión de proyectos
"""

import logging
from flask import render_template, request, jsonify
from auth import auth_required, get_current_user
from manual_ai import manual_ai_bp
from manual_ai.services.project_service import ProjectService
from manual_ai.utils.validators import check_manual_ai_access

logger = logging.getLogger(__name__)

# Instancia del servicio
project_service = ProjectService()


@manual_ai_bp.route('/')
@auth_required
def manual_ai_dashboard():
    """
    Dashboard principal del sistema Manual AI Analysis
    Acceso libre con paywalls en acciones específicas
    
    Returns:
        Renderizado del template manual_ai_dashboard.html
    """
    user = get_current_user()
    logger.info(f"Usuario accediendo Manual AI dashboard: {user.get('email')} (plan: {user.get('plan')})")
    return render_template('manual_ai_dashboard.html', user=user)


@manual_ai_bp.route('/api/projects', methods=['GET'])
@auth_required
def get_projects():
    """
    Obtener todos los proyectos del usuario actual
    
    Returns:
        JSON con lista de proyectos
    """
    user = get_current_user()
    
    # Control por plan
    has_access, error_response = check_manual_ai_access(user)
    if not has_access:
        return jsonify(error_response), 402
    
    projects = project_service.get_user_projects(user['id'])
    
    return jsonify({
        'success': True,
        'projects': projects
    })


@manual_ai_bp.route('/api/projects', methods=['POST'])
@auth_required
def create_project():
    """
    Crear un nuevo proyecto
    
    Request JSON:
        - name: Nombre del proyecto
        - domain: Dominio del proyecto
        - description: Descripción (opcional)
        - country_code: Código de país (opcional, default: US)
        - competitors: Lista de competidores (opcional)
    
    Returns:
        JSON con resultado de la creación
    """
    user = get_current_user()
    
    # Control por plan
    has_access, error_response = check_manual_ai_access(user)
    if not has_access:
        return jsonify(error_response), 402
    
    data = request.get_json()
    
    # Validaciones básicas
    if not data.get('name') or not data.get('domain'):
        return jsonify({'success': False, 'error': 'Name and domain are required'}), 400
    
    result = project_service.create_project(
        user_id=user['id'],
        name=data['name'],
        description=data.get('description', ''),
        domain=data['domain'],
        country_code=data.get('country_code', 'US'),
        competitors=data.get('competitors', [])
    )
    
    if result['success']:
        return jsonify(result), 201
    else:
        return jsonify(result), 500


@manual_ai_bp.route('/api/projects/<int:project_id>', methods=['GET'])
@auth_required
def get_project_details(project_id):
    """
    Obtener detalles completos de un proyecto
    
    Args:
        project_id: ID del proyecto
    
    Returns:
        JSON con detalles del proyecto
    """
    user = get_current_user()
    
    # Control por plan
    has_access, error_response = check_manual_ai_access(user)
    if not has_access:
        return jsonify(error_response), 402
    
    project = project_service.get_project_details(project_id, user['id'])
    
    if not project:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    return jsonify({
        'success': True,
        'project': project
    })


@manual_ai_bp.route('/api/projects/<int:project_id>', methods=['PUT'])
@auth_required
def update_project(project_id):
    """
    Actualizar un proyecto (nombre, descripción)
    
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


@manual_ai_bp.route('/api/projects/<int:project_id>', methods=['DELETE'])
@auth_required
def delete_project(project_id):
    """
    Eliminar completamente un proyecto y todos sus datos
    
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
            'message': f'Project "{result.get("project_name", "")}" deleted successfully',
            'stats': result.get('stats', {})
        })
    else:
        status_code = 404 if 'not found' in result.get('error', '').lower() else 500
        return jsonify(result), status_code

