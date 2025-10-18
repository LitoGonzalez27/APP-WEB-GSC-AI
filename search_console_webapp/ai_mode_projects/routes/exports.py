"""
Rutas para exportación de datos
"""

import logging
from flask import request, jsonify
from auth import auth_required, get_current_user
from ai_mode_projects import ai_mode_bp
from ai_mode_projects.services.project_service import ProjectService
from ai_mode_projects.utils.validators import check_ai_mode_access

logger = logging.getLogger(__name__)

# Instancia del servicio
project_service = ProjectService()


@ai_mode_bp.route('/api/projects/<int:project_id>/download-excel', methods=['POST'])
@auth_required
def download_manual_ai_excel(project_id):
    """
    Generar y descargar Excel con datos de Manual AI
    
    Args:
        project_id: ID del proyecto
    
    Request JSON:
        - days: Número de días hacia atrás (optional, default: 30)
    
    Returns:
        Archivo Excel para descarga
    """
    user = get_current_user()
    
    # Control por plan
    has_access, error_response = check_ai_mode_access(user)
    if not has_access:
        return jsonify(error_response), 402
    
    if not project_service.user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        from ai_mode_projects.services.export_service import ExportService
        from ai_mode_projects.models.project_repository import ProjectRepository
        from ai_mode_projects.models.result_repository import ResultRepository
        from flask import send_file
        import pytz
        from datetime import datetime
        
        # Obtener filtros del request
        data = request.get_json() or {}
        days = int(data.get('days', 30))
        
        # Obtener información del proyecto
        project_repo = ProjectRepository()
        project_info = project_repo.get_project_info(project_id)
        if not project_info:
            logger.error(f"Project {project_id} not found for user {user['id']}")
            return jsonify({'success': False, 'error': 'Project not found'}), 404
        
        logger.info(f"Project info retrieved: {project_info['name']} ({project_info.get('brand_name', 'N/A')})")
        
        # Verificar que hay datos para exportar
        result_repo = ResultRepository()
        results = result_repo.get_project_results(project_id, days)
        
        if not results:
            return jsonify({'success': False, 'error': 'No data available for export'}), 400
        
        # Generar Excel
        logger.info(f"Generating AI Mode Excel for project {project_id}, user {user['id']}, days {days}")
        export_service = ExportService()
        xlsx_file = export_service.generate_manual_ai_excel(
            project_id=project_id,
            project_info=project_info,
            days=days,
            user_id=user['id']
        )
        logger.info(f"AI Mode Excel generated successfully for project {project_id}")
        
        # Crear nombre de archivo
        madrid_tz = pytz.timezone('Europe/Madrid')
        now_madrid = datetime.now(madrid_tz)
        timestamp = now_madrid.strftime('%Y%m%d-%H%M')
        
        project_slug = project_info['name'].lower().replace(' ', '').replace('-', '').replace('_', '')[:20]
        filename = f'ai-mode_export__{project_slug}__{timestamp}__Europe-Madrid.xlsx'
        
        # Registrar telemetría
        logger.info(f"AI Mode Excel export: project_id={project_id}, days={days}, filename={filename}")
        
        return send_file(
            xlsx_file,
            download_name=filename,
            as_attachment=True,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except ImportError as e:
        logger.error(f"Import error in AI Mode Excel generation: {e}")
        return jsonify({'success': False, 'error': 'Missing required dependencies for Excel generation'}), 500
    except Exception as e:
        logger.error(f"Error generating AI Mode Excel for project {project_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Failed to generate Excel file: {str(e)}'}), 500


@ai_mode_bp.route('/api/projects/<int:project_id>/export', methods=['GET'])
@auth_required
def export_project_data(project_id):
    """
    Exportar datos del proyecto (placeholder para futuras funcionalidades)
    
    Args:
        project_id: ID del proyecto
    
    Returns:
        JSON con mensaje
    """
    user = get_current_user()
    
    # Control por plan
    has_access, error_response = check_ai_mode_access(user)
    if not has_access:
        return jsonify(error_response), 402
    
    if not project_service.user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    return jsonify({
        'success': True,
        'message': 'Export functionality coming soon'
    })

