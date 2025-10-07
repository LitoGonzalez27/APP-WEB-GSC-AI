"""
Rutas para gestión de topic clusters en Manual AI
"""

import logging
import json
from flask import request, jsonify
from auth import auth_required, get_current_user
from manual_ai import manual_ai_bp
from manual_ai.services.cluster_service import ClusterService
from manual_ai.services.project_service import ProjectService

logger = logging.getLogger(__name__)

# Instancias de servicios
cluster_service = ClusterService()
project_service = ProjectService()


@manual_ai_bp.route('/api/projects/<int:project_id>/clusters', methods=['GET'])
@auth_required
def get_project_clusters(project_id):
    """
    Obtener configuración de clusters de un proyecto
    
    Args:
        project_id: ID del proyecto
    
    Returns:
        JSON con configuración de clusters
    """
    user = get_current_user()
    
    if not project_service.user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        clusters_config = cluster_service.get_project_clusters(project_id)
        
        logger.info(f"Retrieved clusters config for project {project_id}: {len(clusters_config.get('clusters', []))} clusters")
        
        return jsonify({
            'success': True,
            'clusters_config': clusters_config
        })
        
    except Exception as e:
        logger.error(f"Error getting clusters for project {project_id}: {e}")
        return jsonify({'success': False, 'error': f'Database error: {str(e)}'}), 500


@manual_ai_bp.route('/api/projects/<int:project_id>/clusters', methods=['PUT'])
@auth_required
def update_project_clusters(project_id):
    """
    Actualizar configuración de clusters de un proyecto
    
    Args:
        project_id: ID del proyecto
    
    Request JSON:
        - enabled: Boolean indicando si los clusters están habilitados
        - clusters: Lista de clusters con sus términos
    
    Returns:
        JSON con resultado de la actualización
    """
    user = get_current_user()
    
    if not project_service.user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Missing clusters data'}), 400
        
        clusters_config = data.get('clusters_config', {})
        
        # Validar configuración
        validation = cluster_service.validate_clusters_config(clusters_config)
        
        if not validation['valid']:
            return jsonify({
                'success': False,
                'error': 'Invalid clusters configuration',
                'errors': validation['errors'],
                'warnings': validation.get('warnings', [])
            }), 400
        
        # Actualizar clusters
        success = cluster_service.update_project_clusters(project_id, clusters_config)
        
        if not success:
            return jsonify({'success': False, 'error': 'Failed to update clusters'}), 500
        
        # Log de éxito
        num_clusters = len(clusters_config.get('clusters', []))
        enabled = clusters_config.get('enabled', False)
        
        logger.info(f"✅ Clusters updated for project {project_id}: {num_clusters} clusters, enabled={enabled}")
        
        return jsonify({
            'success': True,
            'clusters_config': clusters_config,
            'message': f'Successfully updated clusters configuration',
            'warnings': validation.get('warnings', [])
        })
        
    except Exception as e:
        logger.error(f"Error updating clusters for project {project_id}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': f'Database error: {str(e)}'}), 500


@manual_ai_bp.route('/api/projects/<int:project_id>/clusters/statistics', methods=['GET'])
@auth_required
def get_clusters_statistics(project_id):
    """
    Obtener estadísticas de clusters para gráficas y tablas
    
    Args:
        project_id: ID del proyecto
    
    Query params:
        days: Número de días hacia atrás (default: 30)
    
    Returns:
        JSON con estadísticas de clusters
    """
    user = get_current_user()
    
    if not project_service.user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        from manual_ai.config import DEFAULT_DAYS_RANGE
        days = int(request.args.get('days', DEFAULT_DAYS_RANGE))
        
        logger.info(f"📊 Getting cluster statistics for project {project_id} with {days} days")
        
        statistics = cluster_service.get_cluster_statistics(project_id, days)
        
        logger.info(f"📈 Cluster statistics retrieved: {statistics.get('total_clusters', 0)} clusters with data")
        
        return jsonify({
            'success': True,
            'data': statistics
        })
        
    except Exception as e:
        logger.error(f"❌ Error getting cluster statistics for project {project_id}: {e}")
        import traceback
        logger.error(f"🔍 Traceback: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500


@manual_ai_bp.route('/api/projects/<int:project_id>/clusters/validate', methods=['POST'])
@auth_required
def validate_clusters_config(project_id):
    """
    Validar configuración de clusters sin guardarla
    
    Args:
        project_id: ID del proyecto
    
    Request JSON:
        - clusters_config: Configuración de clusters a validar
    
    Returns:
        JSON con resultado de la validación
    """
    user = get_current_user()
    
    if not project_service.user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Missing clusters data'}), 400
        
        clusters_config = data.get('clusters_config', {})
        
        # Validar configuración
        validation = cluster_service.validate_clusters_config(clusters_config)
        
        return jsonify({
            'success': True,
            'validation': validation
        })
        
    except Exception as e:
        logger.error(f"Error validating clusters config for project {project_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@manual_ai_bp.route('/api/projects/<int:project_id>/clusters/test', methods=['POST'])
@auth_required
def test_cluster_classification(project_id):
    """
    Probar clasificación de una keyword en clusters
    
    Args:
        project_id: ID del proyecto
    
    Request JSON:
        - keyword: Keyword a probar
    
    Returns:
        JSON con clusters donde clasifica la keyword
    """
    user = get_current_user()
    
    if not project_service.user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        data = request.get_json()
        if not data or 'keyword' not in data:
            return jsonify({'success': False, 'error': 'Missing keyword'}), 400
        
        keyword = data['keyword']
        
        # Obtener configuración de clusters del proyecto
        clusters_config = cluster_service.get_project_clusters(project_id)
        
        # Clasificar keyword
        matching_clusters = cluster_service.classify_keyword(keyword, clusters_config)
        
        return jsonify({
            'success': True,
            'keyword': keyword,
            'matching_clusters': matching_clusters,
            'is_classified': len(matching_clusters) > 0
        })
        
    except Exception as e:
        logger.error(f"Error testing cluster classification for project {project_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

