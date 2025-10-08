"""
Rutas para gestión de keywords
"""

import logging
from flask import request, jsonify
from auth import auth_required, get_current_user
from ai_mode_projects import ai_mode_bp
from ai_mode_projects.services.project_service import ProjectService
from ai_mode_projects.models.keyword_repository import KeywordRepository
from ai_mode_projects.models.event_repository import EventRepository
from ai_mode_projects.config import MAX_KEYWORDS_PER_PROJECT, EVENT_TYPES
from ai_mode_projects.utils.validators import check_ai_mode_access

logger = logging.getLogger(__name__)

# Instancias de servicios y repositorios
project_service = ProjectService()
keyword_repo = KeywordRepository()
event_repo = EventRepository()


@ai_mode_bp.route('/api/projects/<int:project_id>/keywords', methods=['GET'])
@auth_required
def get_project_keywords(project_id):
    """
    Obtener keywords de un proyecto
    
    Args:
        project_id: ID del proyecto
    
    Returns:
        JSON con lista de keywords
    """
    user = get_current_user()
    
    # Control por plan
    has_access, error_response = check_ai_mode_access(user)
    if not has_access:
        return jsonify(error_response), 402
    
    if not project_service.user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    keywords = keyword_repo.get_keywords_for_project(project_id)
    
    return jsonify({
        'success': True,
        'keywords': keywords
    })


@ai_mode_bp.route('/api/projects/<int:project_id>/keywords', methods=['POST'])
@auth_required
def add_keywords_to_project(project_id):
    """
    Agregar keywords a un proyecto
    
    Args:
        project_id: ID del proyecto
    
    Request JSON:
        - keywords: Lista de keywords a agregar
    
    Returns:
        JSON con resultado de la operación
    """
    user = get_current_user()
    
    if not project_service.user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    keywords_list = data.get('keywords', [])
    
    if not keywords_list:
        return jsonify({'success': False, 'error': 'No keywords provided'}), 400
    
    # Verificar límite de keywords
    current_count = keyword_repo.get_project_keyword_count(project_id)
    if current_count + len(keywords_list) > MAX_KEYWORDS_PER_PROJECT:
        return jsonify({
            'success': False,
            'error': f'Project would exceed {MAX_KEYWORDS_PER_PROJECT} keywords limit. '
                    f'Current: {current_count}, Adding: {len(keywords_list)}'
        }), 400
    
    try:
        added_count = keyword_repo.add_keywords_to_project(project_id, keywords_list)
        
        # Crear evento
        event_repo.create_event(
            project_id=project_id,
            event_type=EVENT_TYPES['KEYWORDS_ADDED'],
            event_title=f'{added_count} keywords added',
            keywords_affected=added_count,
            user_id=user['id']
        )
        
        return jsonify({
            'success': True,
            'added_count': added_count,
            'message': f'{added_count} keywords added successfully'
        })
        
    except Exception as e:
        logger.error(f"Error adding keywords: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@ai_mode_bp.route('/api/projects/<int:project_id>/keywords/<int:keyword_id>', methods=['DELETE'])
@auth_required
def delete_project_keyword(project_id, keyword_id):
    """
    Eliminar una keyword específica de un proyecto
    
    Args:
        project_id: ID del proyecto
        keyword_id: ID de la keyword
    
    Returns:
        JSON con resultado de la eliminación
    """
    user = get_current_user()
    
    logger.info(f"Delete keyword request: project_id={project_id}, keyword_id={keyword_id}, user_id={user['id']}")
    
    if not project_service.user_owns_project(user['id'], project_id):
        logger.warning(f"Unauthorized access: User {user['id']} does not own project {project_id}")
        return jsonify({
            'success': False,
            'error': f'Project {project_id} not found or unauthorized access'
        }), 403
    
    try:
        result = keyword_repo.delete_keyword(project_id, keyword_id)
        
        if not result['success']:
            return jsonify(result), 404
        
        # Crear evento
        try:
            event_repo.create_event(
                project_id=project_id,
                event_type=EVENT_TYPES['KEYWORD_DELETED'],
                event_title=f'Keyword deleted: {result["keyword"]}',
                keywords_affected=1,
                user_id=user['id']
            )
        except Exception as event_error:
            logger.error(f"Failed to create deletion event (non-critical): {event_error}")
        
        logger.info(f"Keyword deleted successfully: {result['keyword']} from project {project_id}")
        return jsonify({
            'success': True,
            'message': f'Keyword "{result["keyword"]}" deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Error deleting keyword {keyword_id} from project {project_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@ai_mode_bp.route('/api/projects/<int:project_id>/keywords/<int:keyword_id>', methods=['PUT'])
@auth_required
def update_project_keyword(project_id, keyword_id):
    """
    Actualizar una keyword específica de un proyecto
    
    Args:
        project_id: ID del proyecto
        keyword_id: ID de la keyword
    
    Request JSON:
        - keyword: Nuevo texto de la keyword
    
    Returns:
        JSON con resultado de la actualización
    """
    user = get_current_user()
    
    if not project_service.user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    new_keyword = data.get('keyword', '').strip()
    
    if not new_keyword:
        return jsonify({'success': False, 'error': 'Keyword cannot be empty'}), 400
    
    try:
        success = keyword_repo.update_keyword(project_id, keyword_id, new_keyword)
        
        if not success:
            return jsonify({
                'success': False,
                'error': 'Keyword not found or already exists in this project'
            }), 400
        
        # Crear evento
        event_repo.create_event(
            project_id=project_id,
            event_type=EVENT_TYPES['KEYWORD_UPDATED'],
            event_title=f'Keyword updated to: "{new_keyword}"',
            keywords_affected=1,
            user_id=user['id']
        )
        
        return jsonify({
            'success': True,
            'message': 'Keyword updated successfully'
        })
        
    except Exception as e:
        logger.error(f"Error updating keyword: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

