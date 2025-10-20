"""
Rutas para ejecución de análisis
"""

import logging
import threading
from datetime import date
from flask import request, jsonify
from auth import auth_required, cron_or_auth_required, get_current_user
from manual_ai import manual_ai_bp
from manual_ai.services.project_service import ProjectService
from manual_ai.services.analysis_service import AnalysisService
from manual_ai.services.cron_service import CronService
from manual_ai.models.result_repository import ResultRepository
from manual_ai.models.event_repository import EventRepository
from manual_ai.utils.validators import check_manual_ai_access

logger = logging.getLogger(__name__)

# Instancias de servicios
project_service = ProjectService()
analysis_service = AnalysisService()
cron_service = CronService()
result_repo = ResultRepository()
event_repo = EventRepository()


@manual_ai_bp.route('/api/projects/<int:project_id>/analyze', methods=['POST'])
@auth_required
def analyze_project(project_id):
    """
    Ejecutar análisis completo de un proyecto
    
    Args:
        project_id: ID del proyecto
    
    Returns:
        JSON con resultado del análisis
    """
    user = get_current_user()
    
    # Control por plan
    has_access, error_response = check_manual_ai_access(user)
    if not has_access:
        return jsonify(error_response), 402
    
    if not project_service.user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        # Ejecutar análisis manual con sobreescritura forzada
        analysis_result = analysis_service.run_project_analysis(project_id, force_overwrite=True)
        
        # Manejar respuesta que puede incluir información de quota
        if isinstance(analysis_result, dict) and analysis_result.get('quota_exceeded'):
            # Análisis interrumpido por quota
            quota_info = analysis_result.get('quota_info', {})
            partial_results = analysis_result.get('results', [])
            
            logger.warning(f"Manual AI analysis for project {project_id} stopped due to quota limit")
            
            # Crear snapshot con resultados parciales si hay algunos
            if partial_results:
                _create_daily_snapshot(project_id)
            
            # Crear evento de análisis parcial
            event_repo.create_event(
                project_id=project_id,
                event_type='manual_analysis_quota_exceeded',
                event_title=f'Manual analysis stopped: quota exceeded ({len(partial_results)} keywords analyzed)',
                keywords_affected=len(partial_results),
                user_id=user['id']
            )
            
            return jsonify({
                'success': False,
                'error': 'quota_exceeded',
                'quota_exceeded': True,
                'quota_info': quota_info,
                'action_required': analysis_result.get('action_required', 'upgrade'),
                'results_count': len(partial_results),
                'keywords_analyzed': analysis_result.get('keywords_analyzed', 0),
                'keywords_remaining': analysis_result.get('keywords_remaining', 0),
                'analysis_date': str(date.today()),
                'message': f'Analysis stopped due to quota limit. {len(partial_results)} keywords analyzed successfully.'
            }), 429  # Too Many Requests
        
        # Análisis normal (lista de resultados)
        if isinstance(analysis_result, list):
            results = analysis_result
        else:
            results = analysis_result.get('results', []) if isinstance(analysis_result, dict) else []
        
        if not results:
            logger.warning(f"No results returned for project {project_id} analysis")
            return jsonify({
                'success': False,
                'error': 'No keywords available for analysis'
            }), 400
        
        # Crear snapshot del día
        _create_daily_snapshot(project_id)
        
        # Crear evento
        event_repo.create_event(
            project_id=project_id,
            event_type='manual_analysis_completed',
            event_title='Manual analysis completed (with overwrite)',
            keywords_affected=len(results),
            user_id=user['id']
        )
        
        return jsonify({
            'success': True,
            'results_count': len(results),
            'analysis_date': str(date.today()),
            'message': 'Analysis completed successfully'
        })
        
    except ValueError as e:
        logger.warning(f"Validation error analyzing project {project_id}: {e}")
        return jsonify({'success': False, 'error': 'Invalid project data'}), 400
    except ConnectionError as e:
        logger.error(f"Connection error analyzing project {project_id}: {e}")
        return jsonify({'success': False, 'error': 'Analysis service temporarily unavailable'}), 503
    except Exception as e:
        logger.error(f"Unexpected error analyzing project {project_id}: {e}")
        return jsonify({'success': False, 'error': 'Analysis failed due to internal error'}), 500


@manual_ai_bp.route('/api/cron/daily-analysis', methods=['POST'])
@cron_or_auth_required
def trigger_daily_analysis():
    """
    Trigger para análisis diario automático (cron job)
    
    Query params:
        async (int): Si es 1, ejecuta en background y responde inmediatamente con 202
    
    Returns:
        JSON con resultado de la ejecución del cron
    """
    try:
        # Verificar si se solicita ejecución asíncrona
        is_async = request.args.get('async', '0') == '1'
        
        if is_async:
            # Ejecutar en background y responder inmediatamente
            def run_analysis_in_background():
                try:
                    logger.info("🚀 Manual AI: Starting daily analysis in background")
                    result = cron_service.run_daily_analysis_for_all_projects()
                    if result.get('success'):
                        logger.info(f"✅ Manual AI: Daily analysis completed - {result.get('total_projects', 0)} projects processed")
                    else:
                        logger.error(f"❌ Manual AI: Daily analysis failed - {result.get('error', 'Unknown error')}")
                except Exception as e:
                    logger.error(f"💥 Manual AI: Background analysis error: {e}")
            
            # Iniciar thread en background
            thread = threading.Thread(target=run_analysis_in_background, daemon=True)
            thread.start()
            
            logger.info("📤 Manual AI: Daily analysis triggered (async mode)")
            return jsonify({
                'success': True,
                'message': 'Daily analysis triggered in background',
                'async': True
            }), 202
        
        # Modo síncrono (comportamiento original)
        result = cron_service.run_daily_analysis_for_all_projects()
        
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"Error in daily analysis cron trigger: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def _create_daily_snapshot(project_id: int):
    """Helper para crear snapshot diario"""
    try:
        today = date.today()
        metrics = _calculate_snapshot_metrics(project_id)
        result_repo.create_snapshot(project_id, today, metrics)
    except Exception as e:
        logger.error(f"Error creating snapshot for project {project_id}: {e}")


def _calculate_snapshot_metrics(project_id: int) -> dict:
    """Helper para calcular métricas de snapshot"""
    from database import get_db_connection
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        today = date.today()
        
        cur.execute("""
            SELECT 
                COUNT(DISTINCT k.id) as total_keywords,
                COUNT(DISTINCT CASE WHEN k.is_active = true THEN k.id END) as active_keywords,
                COUNT(DISTINCT CASE WHEN r.has_ai_overview = true THEN k.id END) as keywords_with_ai,
                COUNT(DISTINCT CASE WHEN r.domain_mentioned = true THEN k.id END) as domain_mentions,
                AVG(CASE WHEN r.domain_mentioned = true THEN r.domain_position END) as avg_position,
                (COUNT(DISTINCT CASE WHEN r.domain_mentioned = true THEN k.id END)::float /
                 NULLIF(COUNT(DISTINCT CASE WHEN r.has_ai_overview = true THEN k.id END), 0)::float * 100) as visibility_percentage
            FROM manual_ai_keywords k
            LEFT JOIN manual_ai_results r ON k.id = r.keyword_id AND r.analysis_date = %s
            WHERE k.project_id = %s
        """, (today, project_id))
        
        result = cur.fetchone()
        return dict(result) if result else {}
        
    finally:
        cur.close()
        conn.close()

