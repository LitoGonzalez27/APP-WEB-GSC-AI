"""
Rutas para exportación de datos
"""

import logging
from flask import request, jsonify
from auth import auth_required, get_current_user
from manual_ai import manual_ai_bp
from manual_ai.services.project_service import ProjectService
from manual_ai.utils.validators import check_manual_ai_access

logger = logging.getLogger(__name__)

# Instancia del servicio
project_service = ProjectService()


@manual_ai_bp.route('/api/projects/<int:project_id>/download-excel', methods=['POST'])
@auth_required
def download_manual_ai_excel(project_id):
    """
    Generar y descargar Excel con datos de Manual AI
    
    NOTA: Esta ruta aún usa el sistema original para generación de Excel
    Se puede refactorizar más adelante si es necesario
    
    Args:
        project_id: ID del proyecto
    
    Request JSON:
        - days: Número de días hacia atrás (optional, default: 30)
    
    Returns:
        Archivo Excel para descarga
    """
    user = get_current_user()
    
    # Control por plan
    has_access, error_response = check_manual_ai_access(user)
    if not has_access:
        return jsonify(error_response), 402
    
    if not project_service.user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        # Importar del sistema original (por ahora)
        from manual_ai_system import generate_manual_ai_excel, get_project_info
        from flask import send_file
        import pytz
        from datetime import datetime
        
        # Obtener filtros del request
        data = request.get_json() or {}
        days = int(data.get('days', 30))
        
        # Obtener información del proyecto
        project_info = get_project_info(project_id)
        if not project_info:
            logger.error(f"Project {project_id} not found for user {user['id']}")
            return jsonify({'success': False, 'error': 'Project not found'}), 404
        
        logger.info(f"Project info retrieved: {project_info['name']} ({project_info['domain']})")
        
        # Verificar que hay datos para exportar
        from manual_ai.models.result_repository import ResultRepository
        result_repo = ResultRepository()
        results = result_repo.get_project_results(project_id, days)
        
        if not results:
            return jsonify({'success': False, 'error': 'No data available for export'}), 400
        
        # Generar Excel
        logger.info(f"Generating Manual AI Excel for project {project_id}, user {user['id']}, days {days}")
        xlsx_file = generate_manual_ai_excel(
            project_id=project_id,
            project_info=project_info,
            days=days,
            user_id=user['id']
        )
        logger.info(f"Manual AI Excel generated successfully for project {project_id}")
        
        # Crear nombre de archivo
        madrid_tz = pytz.timezone('Europe/Madrid')
        now_madrid = datetime.now(madrid_tz)
        timestamp = now_madrid.strftime('%Y%m%d-%H%M')
        
        project_slug = project_info['name'].lower().replace(' ', '').replace('-', '').replace('_', '')[:20]
        filename = f'manual-ai_export__{project_slug}__{timestamp}__Europe-Madrid.xlsx'
        
        # Registrar telemetría
        logger.info(f"Manual AI Excel export: project_id={project_id}, days={days}, filename={filename}")
        
        return send_file(
            xlsx_file,
            download_name=filename,
            as_attachment=True,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except ImportError as e:
        logger.error(f"Import error in manual AI Excel generation: {e}")
        return jsonify({'success': False, 'error': 'Missing required dependencies for Excel generation'}), 500
    except Exception as e:
        logger.error(f"Error generating manual AI Excel for project {project_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Failed to generate Excel file: {str(e)}'}), 500


@manual_ai_bp.route('/api/projects/<int:project_id>/export', methods=['GET'])
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
    has_access, error_response = check_manual_ai_access(user)
    if not has_access:
        return jsonify(error_response), 402
    
    if not project_service.user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    return jsonify({
        'success': True,
        'message': 'Export functionality coming soon'
    })

