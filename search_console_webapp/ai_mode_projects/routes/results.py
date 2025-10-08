"""
Rutas para obtener resultados y estadísticas
"""

import logging
from flask import request, jsonify
from auth import auth_required, get_current_user
from ai_mode_projects import ai_mode_bp
from ai_mode_projects.services.project_service import ProjectService
from ai_mode_projects.services.statistics_service import StatisticsService
from ai_mode_projects.utils.validators import check_ai_mode_access
from ai_mode_projects.config import DEFAULT_DAYS_RANGE

logger = logging.getLogger(__name__)

# Instancias de servicios
project_service = ProjectService()
stats_service = StatisticsService()


@ai_mode_bp.route('/api/projects/<int:project_id>/results', methods=['GET'])
@auth_required
def get_project_results(project_id):
    """
    Obtener resultados de análisis de un proyecto
    
    Args:
        project_id: ID del proyecto
    
    Query params:
        days: Número de días hacia atrás (default: 30)
    
    Returns:
        JSON con resultados de análisis
    """
    user = get_current_user()
    
    # Control por plan
    has_access, error_response = check_ai_mode_access(user)
    if not has_access:
        return jsonify(error_response), 402
    
    if not project_service.user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    days = int(request.args.get('days', DEFAULT_DAYS_RANGE))
    
    from ai_mode_projects.models.result_repository import ResultRepository
    result_repo = ResultRepository()
    results = result_repo.get_project_results(project_id, days)
    
    return jsonify({
        'success': True,
        'results': results
    })


@ai_mode_bp.route('/api/projects/<int:project_id>/stats', methods=['GET'])
@auth_required
def get_project_stats(project_id):
    """
    Obtener estadísticas y gráficos de un proyecto
    
    Args:
        project_id: ID del proyecto
    
    Query params:
        days: Número de días hacia atrás (default: 30)
    
    Returns:
        JSON con estadísticas completas
    """
    user = get_current_user()
    
    # Control por plan
    has_access, error_response = check_ai_mode_access(user)
    if not has_access:
        return jsonify(error_response), 402
    
    if not project_service.user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    days = int(request.args.get('days', DEFAULT_DAYS_RANGE))
    
    stats = stats_service.get_project_statistics(project_id, days)
    
    return jsonify({
        'success': True,
        'stats': stats
    })


@ai_mode_bp.route('/api/projects/<int:project_id>/stats-latest', methods=['GET'])
@auth_required
def get_project_stats_latest(project_id):
    """
    Devuelve métricas de Overview basadas en el último análisis disponible
    
    Args:
        project_id: ID del proyecto
    
    Returns:
        JSON con estadísticas del último análisis
    """
    user = get_current_user()
    
    if not project_service.user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    stats = stats_service.get_latest_overview_stats(project_id)
    
    return jsonify({
        'success': True,
        'main_stats': stats
    })


@ai_mode_bp.route('/api/projects/<int:project_id>/ai-overview-table', methods=['GET'])
@auth_required
def get_ai_overview_table_data(project_id):
    """
    Obtener datos detallados de keywords con AI Overview para la tabla Grid.js
    
    Args:
        project_id: ID del proyecto
    
    Query params:
        days: Número de días hacia atrás (default: 30)
    
    Returns:
        JSON con datos de tabla
    """
    user = get_current_user()
    
    if not project_service.user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        days = int(request.args.get('days', DEFAULT_DAYS_RANGE))
        ai_overview_data = stats_service.get_project_ai_overview_keywords(project_id, days)
        
        return jsonify({
            'success': True,
            'data': ai_overview_data
        })
    except Exception as e:
        logger.error(f"Error getting AI Overview table data for project {project_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@ai_mode_bp.route('/api/projects/<int:project_id>/ai-overview-table-latest', methods=['GET'])
@auth_required
def get_ai_overview_table_latest(project_id):
    """
    Tabla de AI Overview basada en el último análisis disponible por keyword
    
    Args:
        project_id: ID del proyecto
    
    Returns:
        JSON con datos de tabla del último análisis
    """
    user = get_current_user()
    
    if not project_service.user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        data = stats_service.get_project_ai_overview_keywords_latest(project_id)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        logger.error(f"Error getting latest AI Overview table for project {project_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@ai_mode_bp.route('/api/projects/<int:project_id>/top-domains', methods=['GET'])
@auth_required
def get_top_domains(project_id):
    """
    Obtener dominios más visibles para un proyecto
    
    Args:
        project_id: ID del proyecto
    
    Returns:
        JSON con top dominios
    """
    user = get_current_user()
    
    if not project_service.user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        from ai_mode_projects.config import DEFAULT_TOP_DOMAINS_LIMIT
        domains = stats_service.get_project_top_domains(project_id, DEFAULT_TOP_DOMAINS_LIMIT)
        return jsonify({
            'success': True,
            'domains': domains
        })
    except Exception as e:
        logger.error(f"Error getting top domains for project {project_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@ai_mode_bp.route('/api/projects/<int:project_id>/global-domains-ranking', methods=['GET'])
@auth_required
def get_global_domains_ranking(project_id):
    """
    Obtener ranking global de TODOS los dominios detectados en AI Overview
    
    Args:
        project_id: ID del proyecto
    
    Query params:
        days: Número de días hacia atrás (default: 30)
    
    Returns:
        JSON con ranking completo
    """
    user = get_current_user()
    
    if not project_service.user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        days = int(request.args.get('days', DEFAULT_DAYS_RANGE))
        ranking = stats_service.get_project_global_domains_ranking(project_id, days)
        
        return jsonify({
            'success': True,
            'domains': ranking,
            'total_domains': len(ranking)
        })
    except Exception as e:
        logger.error(f"Error getting global domains ranking for project {project_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

