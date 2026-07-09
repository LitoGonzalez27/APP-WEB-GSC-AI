"""
Rutas del panel AI Visibility Summary
"""

import logging
from flask import render_template, request, jsonify

from auth import auth_required, get_current_user
from ai_summary import ai_summary_bp
from ai_summary.models.brand_link_repository import BrandLinkRepository
from ai_summary.services.summary_service import SummaryService
from services.utils import normalize_search_console_url

logger = logging.getLogger(__name__)

ALLOWED_PERIODS = ('7', '14', '28', '30', 'last_month', '90', '180')
MAX_BRANDS_PER_USER = 25
MAX_NAME_LENGTH = 255

MODULE_LINK_FIELDS = {
    'manual_ai': 'manual_ai_project_id',
    'ai_mode': 'ai_mode_project_id',
    'llm': 'llm_project_id',
}


def _check_access(user):
    """
    El panel agrega proyectos PROPIOS de los tres módulos de IA, así que el
    criterio de acceso es el mismo que para crearlos: cualquier plan de pago
    (o admin). El acceso compartido por proyecto no aplica aquí: la capa de
    datos es owner-only y un colaborador sin proyectos propios solo vería un
    panel vacío.
    """
    return user.get('role') == 'admin' or user.get('plan', 'free') != 'free'


def _payment_required_response():
    return jsonify({
        'success': False,
        'error': 'Your plan does not include AI visibility modules',
        'paywall': True,
    }), 402


def _validated_links(user, data):
    """
    Extraer y validar los *_project_id del body: tipo entero estricto y
    ownership verificado (anti-IDOR). Devuelve (links, error_response).
    """
    links = {}
    for module, field in MODULE_LINK_FIELDS.items():
        project_id = data.get(field)
        if project_id is None:
            links[field] = None
            continue
        if not isinstance(project_id, int) or isinstance(project_id, bool):
            return None, (jsonify({'success': False, 'error': f'{field} must be an integer'}), 400)
        if not BrandLinkRepository.verify_project_ownership(user['id'], module, project_id):
            return None, (jsonify({'success': False, 'error': f'Invalid {field}'}), 403)
        links[field] = project_id
    return links, None


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
    projects = BrandLinkRepository.get_user_module_projects(user['id'])
    suggestions = BrandLinkRepository.suggest_links(user['id'], brands, projects)

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
    brand_name = str(data.get('brand_name') or '').strip()
    brand_domain = normalize_search_console_url(str(data.get('brand_domain') or '').strip())

    if not brand_name or len(brand_name) > MAX_NAME_LENGTH:
        return jsonify({'success': False, 'error': 'brand_name is required (max 255 chars)'}), 400
    if len(brand_domain) < 3 or len(brand_domain) > MAX_NAME_LENGTH:
        return jsonify({'success': False, 'error': 'brand_domain must be a valid domain'}), 400

    if len(BrandLinkRepository.get_user_brands(user['id'])) >= MAX_BRANDS_PER_USER:
        return jsonify({'success': False, 'error': f'Brand limit reached ({MAX_BRANDS_PER_USER})'}), 400

    links, error = _validated_links(user, data)
    if error:
        return error
    if not any(links.values()):
        return jsonify({'success': False, 'error': 'Link at least one project'}), 400

    result = BrandLinkRepository.create_brand(
        user_id=user['id'],
        brand_name=brand_name,
        brand_domain=brand_domain,
        **links,
    )
    return (jsonify(result), 201) if result.get('success') else (jsonify(result), 400)


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
        - period: 7 | 14 | 28 | 30 | last_month | 90 | 180 (default 30)
    """
    user = get_current_user()
    if not _check_access(user):
        return _payment_required_response()

    brand = BrandLinkRepository.get_brand(brand_id, user['id'])
    if not brand:
        return jsonify({'success': False, 'error': 'Brand not found'}), 404

    period = request.args.get('period', '30')
    if period not in ALLOWED_PERIODS:
        period = '30'

    try:
        summary = SummaryService.get_brand_summary(brand, period)
        return jsonify({'success': True, **summary})
    except Exception as e:
        logger.error(f"Error building AI summary for brand {brand_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Failed to build summary'}), 500
