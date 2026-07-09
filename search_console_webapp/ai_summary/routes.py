"""
Rutas del panel AI Visibility Summary
"""

import logging
from flask import render_template, request, jsonify

from auth import auth_required, get_current_user
from ai_summary import ai_summary_bp
from ai_summary.models.brand_link_repository import BrandLinkRepository
from ai_summary.services.summary_service import SummaryService

logger = logging.getLogger(__name__)

ALLOWED_DAYS = (7, 30, 90)

MODULE_LINK_FIELDS = {
    'manual_ai': 'manual_ai_project_id',
    'ai_mode': 'ai_mode_project_id',
    'llm': 'llm_project_id',
}


def _check_access(user):
    """
    El panel es transversal: se permite si el usuario puede usar al menos uno
    de los módulos de IA (mismo criterio que Manual AI: cualquier plan de pago,
    o acceso compartido a algún módulo).
    """
    if user.get('role') == 'admin':
        return True
    if user.get('plan', 'free') != 'free':
        return True
    try:
        from services.project_access_service import user_has_any_module_access
        return any(
            user_has_any_module_access(user['id'], module)
            for module in ('manual_ai', 'ai_mode', 'llm_monitoring')
        )
    except Exception:
        return False


def _payment_required_response():
    return jsonify({
        'success': False,
        'error': 'Your plan does not include AI visibility modules',
        'paywall': True,
    }), 402


@ai_summary_bp.route('/')
@auth_required
def ai_summary_dashboard():
    """Dashboard del panel de resumen de visibilidad IA"""
    user = get_current_user()
    logger.info(f"Usuario accediendo AI Summary dashboard: {user.get('email')} (plan: {user.get('plan')})")

    access_blocked = not _check_access(user)
    try:
        from llm_monitoring_limits import get_upgrade_options
        upgrade_options = get_upgrade_options(user.get('plan', 'free'))
    except Exception:
        upgrade_options = ['basic', 'premium', 'business']

    return render_template(
        'ai_summary.html',
        user=user,
        access_blocked=access_blocked,
        upgrade_options=upgrade_options
    )


@ai_summary_bp.route('/api/brands', methods=['GET'])
@auth_required
def get_brands():
    """Marcas del usuario + sugerencias de vinculación + proyectos por módulo"""
    user = get_current_user()
    if not _check_access(user):
        return _payment_required_response()

    brands = BrandLinkRepository.get_user_brands(user['id'])
    suggestions = BrandLinkRepository.suggest_links(user['id'], brands)
    projects = BrandLinkRepository.get_user_module_projects(user['id'])

    return jsonify({
        'success': True,
        'brands': brands,
        'suggestions': suggestions,
        'projects': projects,
    })


@ai_summary_bp.route('/api/brands', methods=['POST'])
@auth_required
def create_brand():
    """
    Crear una marca vinculando proyectos existentes.

    Request JSON:
        - brand_name: Nombre visible de la marca
        - brand_domain: Dominio principal (se normaliza)
        - manual_ai_project_id / ai_mode_project_id / llm_project_id (opcionales,
          al menos uno requerido)
    """
    user = get_current_user()
    if not _check_access(user):
        return _payment_required_response()

    data = request.get_json() or {}
    brand_name = (data.get('brand_name') or '').strip()
    brand_domain = (data.get('brand_domain') or '').strip()
    if not brand_name or not brand_domain:
        return jsonify({'success': False, 'error': 'brand_name and brand_domain are required'}), 400

    links = {}
    for module, field in MODULE_LINK_FIELDS.items():
        project_id = data.get(field)
        if project_id is None:
            links[field] = None
            continue
        if not BrandLinkRepository.verify_project_ownership(user['id'], module, project_id):
            return jsonify({'success': False, 'error': f'Invalid {field}'}), 403
        links[field] = project_id

    if not any(links.values()):
        return jsonify({'success': False, 'error': 'Link at least one project'}), 400

    result = BrandLinkRepository.create_brand(
        user_id=user['id'],
        brand_name=brand_name,
        brand_domain=brand_domain,
        **links,
    )
    return (jsonify(result), 201) if result.get('success') else (jsonify(result), 400)


@ai_summary_bp.route('/api/brands/<int:brand_id>', methods=['PUT'])
@auth_required
def update_brand(brand_id):
    """Actualizar nombre o vínculos de una marca"""
    user = get_current_user()
    if not _check_access(user):
        return _payment_required_response()

    data = request.get_json() or {}
    updates = {}
    if data.get('brand_name'):
        updates['brand_name'] = data['brand_name'].strip()

    for module, field in MODULE_LINK_FIELDS.items():
        if field not in data:
            continue
        project_id = data[field]
        if project_id is not None and not BrandLinkRepository.verify_project_ownership(
                user['id'], module, project_id):
            return jsonify({'success': False, 'error': f'Invalid {field}'}), 403
        updates[field] = project_id

    result = BrandLinkRepository.update_brand(brand_id, user['id'], updates)
    return jsonify(result), (200 if result.get('success') else 400)


@ai_summary_bp.route('/api/brands/<int:brand_id>', methods=['DELETE'])
@auth_required
def delete_brand(brand_id):
    """Eliminar una marca (no toca los proyectos vinculados)"""
    user = get_current_user()
    if not _check_access(user):
        return _payment_required_response()

    deleted = BrandLinkRepository.delete_brand(brand_id, user['id'])
    if not deleted:
        return jsonify({'success': False, 'error': 'Brand not found'}), 404
    return jsonify({'success': True})


@ai_summary_bp.route('/api/brands/<int:brand_id>/summary', methods=['GET'])
@auth_required
def get_brand_summary(brand_id):
    """
    Resumen unificado de visibilidad IA de una marca.

    Query params:
        - days: 7 | 30 | 90 (default 30)
    """
    user = get_current_user()
    if not _check_access(user):
        return _payment_required_response()

    brand = BrandLinkRepository.get_brand(brand_id, user['id'])
    if not brand:
        return jsonify({'success': False, 'error': 'Brand not found'}), 404

    try:
        days = int(request.args.get('days', 30))
    except (TypeError, ValueError):
        days = 30
    if days not in ALLOWED_DAYS:
        days = 30

    try:
        summary = SummaryService.get_brand_summary(brand, days)
        return jsonify({'success': True, **summary})
    except Exception as e:
        logger.error(f"Error building AI summary for brand {brand_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Failed to build summary'}), 500
