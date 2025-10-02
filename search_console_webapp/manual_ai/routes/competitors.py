"""
Rutas para gestión de competidores
"""

import logging
import json
from flask import request, jsonify
from auth import auth_required, get_current_user
from manual_ai import manual_ai_bp
from manual_ai.services.project_service import ProjectService
from manual_ai.services.competitor_service import CompetitorService
from manual_ai.models.project_repository import ProjectRepository
from manual_ai.models.event_repository import EventRepository
from services.utils import normalize_search_console_url

logger = logging.getLogger(__name__)

# Instancias de servicios
project_service = ProjectService()
competitor_service = CompetitorService()
project_repo = ProjectRepository()
event_repo = EventRepository()


@manual_ai_bp.route('/api/projects/<int:project_id>/competitors', methods=['GET'])
@auth_required
def get_project_competitors(project_id):
    """
    Obtener competidores seleccionados de un proyecto
    
    Args:
        project_id: ID del proyecto
    
    Returns:
        JSON con lista de competidores
    """
    user = get_current_user()
    
    if not project_service.user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        competitors = project_repo.get_project_competitors(project_id)
        
        logger.info(f"Retrieved {len(competitors)} competitors for project {project_id}")
        
        return jsonify({
            'success': True,
            'competitors': competitors
        })
        
    except Exception as e:
        logger.error(f"Error getting competitors for project {project_id}: {e}")
        return jsonify({'success': False, 'error': f'Database error: {str(e)}'}), 500


@manual_ai_bp.route('/api/projects/<int:project_id>/competitors', methods=['PUT'])
@auth_required
def update_project_competitors(project_id):
    """
    Actualizar competidores seleccionados de un proyecto
    
    Args:
        project_id: ID del proyecto
    
    Request JSON:
        - competitors: Lista de dominios competidores
    
    Returns:
        JSON con resultado de la actualización
    """
    user = get_current_user()
    
    if not project_service.user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        data = request.get_json()
        if not data or 'competitors' not in data:
            return jsonify({'success': False, 'error': 'Missing competitors data'}), 400
        
        competitors = data['competitors']
        
        # Obtener datos del proyecto
        project = project_repo.get_project_info(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404
        
        # Validar competidores
        validation = competitor_service.validate_competitors(competitors, project['domain'])
        
        if not validation['success']:
            return jsonify(validation), 400
        
        validated_competitors = validation['validated']
        
        # Obtener competidores anteriores para detectar cambios
        previous_competitors = project_repo.get_project_competitors(project_id)
        
        # Detectar cambios
        removed_competitors = [c for c in previous_competitors if c not in validated_competitors]
        added_competitors = [c for c in validated_competitors if c not in previous_competitors]
        has_changes = len(removed_competitors) > 0 or len(added_competitors) > 0
        
        # Actualizar competidores
        success = project_repo.update_project_competitors(project_id, validated_competitors)
        
        if not success:
            return jsonify({'success': False, 'error': 'Failed to update competitors'}), 500
        
        # Crear evento detallado
        if has_changes:
            from datetime import datetime
            event_description_data = {
                'previous_competitors': previous_competitors,
                'new_competitors': validated_competitors,
                'changes': {
                    'removed': removed_competitors,
                    'added': added_competitors,
                    'total_before': len(previous_competitors),
                    'total_after': len(validated_competitors)
                },
                'timestamp': datetime.now().isoformat(),
                'change_summary': f"Added: {len(added_competitors)}, Removed: {len(removed_competitors)}"
            }
            
            event_repo.create_event(
                project_id=project_id,
                event_type='competitors_changed',
                event_title='Competitor configuration changed',
                event_description=json.dumps(event_description_data),
                user_id=user['id']
            )
        else:
            event_repo.create_event(
                project_id=project_id,
                event_type='competitors_updated',
                event_title='Competitors list updated (no changes)',
                event_description=f'Confirmed {len(validated_competitors)} competitors: {", ".join(validated_competitors)}',
                user_id=user['id']
            )
        
        # Sincronizar flags históricos
        competitor_service.sync_historical_competitor_flags(project_id, validated_competitors)
        
        return jsonify({
            'success': True,
            'competitors': validated_competitors,
            'message': f'Successfully updated {len(validated_competitors)} competitors'
        })
        
    except Exception as e:
        logger.error(f"Error updating competitors for project {project_id}: {e}")
        return jsonify({'success': False, 'error': f'Database error: {str(e)}'}), 500


@manual_ai_bp.route('/api/projects/<int:project_id>/competitors-charts', methods=['GET'])
@auth_required
def get_competitors_charts_data(project_id):
    """
    Obtener datos para gráficas de competidores
    
    Args:
        project_id: ID del proyecto
    
    Query params:
        days: Número de días hacia atrás (default: 30)
    
    Returns:
        JSON con datos para gráficas
    """
    user = get_current_user()
    
    if not project_service.user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        from manual_ai.config import DEFAULT_DAYS_RANGE
        days = int(request.args.get('days', DEFAULT_DAYS_RANGE))
        charts_data = competitor_service.get_competitors_charts_data(project_id, days)

        return jsonify({
            'success': True,
            'data': charts_data
        })
    except Exception as e:
        logger.error(f"Error getting competitors charts data for project {project_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

