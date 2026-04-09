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
        from manual_ai.services.export_service import ExportService
        from manual_ai.models.project_repository import ProjectRepository
        from manual_ai.models.result_repository import ResultRepository
        from manual_ai.utils.export_filename import build_manual_ai_export_filename
        from flask import send_file

        # Obtener filtros del request
        data = request.get_json() or {}
        days = int(data.get('days', 30))
        
        # Obtener información del proyecto
        project_repo = ProjectRepository()
        project_info = project_repo.get_project_info(project_id)
        if not project_info:
            logger.error(f"Project {project_id} not found for user {user['id']}")
            return jsonify({'success': False, 'error': 'Project not found'}), 404
        
        logger.info(f"Project info retrieved: {project_info['name']} ({project_info['domain']})")
        
        # Verificar que hay datos para exportar
        result_repo = ResultRepository()
        results = result_repo.get_project_results(project_id, days)
        
        if not results:
            return jsonify({'success': False, 'error': 'No data available for export'}), 400
        
        # Generar Excel
        logger.info(f"Generating Manual AI Excel for project {project_id}, user {user['id']}, days {days}")
        export_service = ExportService()
        xlsx_file = export_service.generate_manual_ai_excel(
            project_id=project_id,
            project_info=project_info,
            days=days,
            user_id=user['id']
        )
        logger.info(f"Manual AI Excel generated successfully for project {project_id}")

        # Crear nombre de archivo con formato canónico:
        # "AI Overview export - {project name} - {YYYY-MM-DD} - Clicandseo.xlsx"
        # (misma función helper que usa el endpoint PDF para mantener consistencia)
        filename = build_manual_ai_export_filename(project_info.get('name'), 'xlsx')

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


@manual_ai_bp.route('/api/projects/<int:project_id>/export/pdf', methods=['GET'])
@auth_required
def download_manual_ai_pdf(project_id):
    """
    Generar y descargar un PDF profesional multi-página (AI Overview Visibility
    Report) con todos los datos del proyecto Manual AI.

    El PDF incluye 9 páginas (8 si clusters están deshabilitados):
      1. Cover / Project Details
      2. Executive Summary (6 KPIs)
      3. Trends Over Time (visibility chart + position distribution + events)
      4. Thematic Clusters Analysis (opcional)
      5. Competitive Analysis (multi-series line charts)
      6. AI Overview Keywords Details
      7. Top Mentioned URLs in AI Overview
      8. Global AI Overview Domains Ranking
      9. AI Overview vs Organic Comparison

    Args:
        project_id: ID del proyecto

    Query params:
        - days: Número de días hacia atrás (optional, default: 30, clamp 1-365)

    Returns:
        Archivo PDF para descarga. Filename canónico:
            "AI Overview export - {project_name} - YYYY-MM-DD - Clicandseo.pdf"
    """
    user = get_current_user()

    # Control por plan
    has_access, error_response = check_manual_ai_access(user)
    if not has_access:
        return jsonify(error_response), 402

    if not project_service.user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    try:
        from manual_ai.services.pdf_export_service import ManualAiPdfExportService
        from manual_ai.models.project_repository import ProjectRepository
        from manual_ai.utils.export_filename import build_manual_ai_export_filename
        from flask import send_file

        # Parse + clamp days
        try:
            days = int(request.args.get('days', 30))
        except (TypeError, ValueError):
            days = 30
        days = max(1, min(days, 365))

        # Verify project exists (the service also does this, but we want
        # to return a clean 404 before spinning up ReportLab)
        project_repo = ProjectRepository()
        project_info = project_repo.get_project_info(project_id)
        if not project_info:
            logger.error(f"Project {project_id} not found for user {user['id']}")
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        logger.info(
            f"Generating Manual AI PDF for project {project_id}, "
            f"user {user['id']}, days {days}"
        )

        pdf_file = ManualAiPdfExportService.generate_project_pdf(
            project_id=project_id,
            days=days,
        )

        logger.info(f"Manual AI PDF generated successfully for project {project_id}")

        # Canonical filename (same helper as Excel route)
        filename = build_manual_ai_export_filename(project_info.get('name'), 'pdf')

        # Telemetry
        logger.info(f"Manual AI PDF export: project_id={project_id}, days={days}, filename={filename}")

        return send_file(
            pdf_file,
            download_name=filename,
            as_attachment=True,
            mimetype='application/pdf',
        )

    except ImportError as e:
        logger.error(f"Import error in Manual AI PDF generation: {e}")
        return jsonify({
            'success': False,
            'error': 'Missing required dependencies for PDF generation (reportlab)'
        }), 500
    except ValueError as e:
        logger.warning(f"Value error in Manual AI PDF generation for project {project_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 404
    except Exception as e:
        logger.error(
            f"Error generating Manual AI PDF for project {project_id}: {e}",
            exc_info=True,
        )
        return jsonify({
            'success': False,
            'error': f'Failed to generate PDF file: {str(e)}'
        }), 500


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

