"""
Rutas del panel AI Visibility Summary
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from flask import render_template, request, jsonify

from auth import auth_required, cron_or_auth_required, get_current_user
from ai_summary import ai_summary_bp
from ai_summary.models.brand_link_repository import BrandLinkRepository
from ai_summary.models.score_snapshot_repository import ScoreSnapshotRepository
from ai_summary.services.summary_service import SummaryService
from services.utils import normalize_search_console_url

logger = logging.getLogger(__name__)

ALLOWED_PERIODS = ('7', '14', '28', '30', 'last_month', '90', '180')
SNAPSHOT_PERIOD = '30'  # definición canónica del score histórico
MAX_BRANDS_PER_USER = 25
MAX_NAME_LENGTH = 255
SCORE_BACKFILL_WORKERS = 4

MODULE_LINK_FIELDS = {
    'manual_ai': 'manual_ai_project_id',
    'ai_mode': 'ai_mode_project_id',
    'llm': 'llm_project_id',
}

WEIGHTS_SUM_TOLERANCE = 0.5


def _validated_score_weights(raw):
    """
    Validar las ponderaciones personalizadas: dict plano con claves de
    WEIGHT_COMPONENTS, valores numéricos 0-100 que suman 100 (±0.5).
    Devuelve (weights|None, error_response|None). None = usar defaults.
    """
    from ai_summary.services.summary_service import WEIGHT_COMPONENTS

    if raw is None:
        return None, None
    if not isinstance(raw, dict) or not raw:
        return None, (jsonify({'success': False, 'error': 'score_weights must be an object or null'}), 400)

    weights = {}
    for key, value in raw.items():
        if key not in WEIGHT_COMPONENTS:
            return None, (jsonify({'success': False, 'error': f'Unknown weight component: {key}'}), 400)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0 or value > 100:
            return None, (jsonify({'success': False, 'error': f'Weight for {key} must be between 0 and 100'}), 400)
        weights[key] = round(float(value), 1)

    total = sum(weights.values())
    if abs(total - 100) > WEIGHTS_SUM_TOLERANCE:
        return None, (jsonify({'success': False, 'error': f'Weights must sum 100 (got {total:g})'}), 400)
    if not any(weights.values()):
        return None, (jsonify({'success': False, 'error': 'At least one weight must be greater than 0'}), 400)
    return weights, None


def _check_access(user):
    """
    Acceso: cualquier plan de pago (o admin) — el mismo criterio que para
    crear proyectos en los módulos — o bien usuarios con alguna marca
    compartida (colaboradores de solo lectura, p.ej. el cliente de una
    agencia con cuenta free).
    """
    if user.get('role') == 'admin' or user.get('plan', 'free') != 'free':
        return True
    try:
        from services.project_access_service import user_has_any_module_access
        return user_has_any_module_access(user['id'], 'ai_summary')
    except Exception:
        return False


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


@ai_summary_bp.route('/api/brands/<int:brand_id>', methods=['PUT'])
@auth_required
def update_brand(brand_id):
    """
    Editar una marca (solo el dueño): nombre identificativo y/o proyectos
    vinculados. Campos ausentes del body no se tocan; un campo de vínculo
    a null lo desvincula. Siempre debe quedar al menos un vínculo.
    """
    user = get_current_user()
    if not _check_access(user):
        return _payment_required_response()

    brand = BrandLinkRepository.get_brand(brand_id, user['id'])
    if not brand:
        return jsonify({'success': False, 'error': 'Brand not found'}), 404
    if not brand['is_owner']:
        return jsonify({'success': False, 'error': 'Only the owner can edit a brand'}), 403

    data = request.get_json() or {}
    updates = {}

    if 'brand_name' in data:
        brand_name = str(data.get('brand_name') or '').strip()
        if not brand_name or len(brand_name) > MAX_NAME_LENGTH:
            return jsonify({'success': False, 'error': 'brand_name is required (max 255 chars)'}), 400
        updates['brand_name'] = brand_name

    for module, field in MODULE_LINK_FIELDS.items():
        if field not in data:
            continue
        project_id = data[field]
        if project_id is not None:
            if not isinstance(project_id, int) or isinstance(project_id, bool):
                return jsonify({'success': False, 'error': f'{field} must be an integer'}), 400
            if not BrandLinkRepository.verify_project_ownership(user['id'], module, project_id):
                return jsonify({'success': False, 'error': f'Invalid {field}'}), 403
        updates[field] = project_id

    if 'score_weights' in data:
        weights, error = _validated_score_weights(data['score_weights'])
        if error:
            return error
        updates['score_weights'] = weights

    if not updates:
        return jsonify({'success': False, 'error': 'Nothing to update'}), 400

    # La marca resultante debe conservar al menos un proyecto vinculado
    merged = {field: updates.get(field, brand[field]) for field in MODULE_LINK_FIELDS.values()}
    if not any(merged.values()):
        return jsonify({'success': False, 'error': 'Link at least one project'}), 400

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
    except Exception as e:
        logger.error(f"Error building AI summary for brand {brand_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Failed to build summary'}), 500

    # Registro oportunista del histórico: el periodo 30d es la definición
    # canónica del score diario. Nunca bloquea la respuesta.
    if period == SNAPSHOT_PERIOD:
        try:
            ScoreSnapshotRepository.upsert_today(brand['id'], summary)
        except Exception as e:
            logger.warning(f"Score snapshot upsert failed for brand {brand_id}: {e}")

    return jsonify({'success': True, **summary})


@ai_summary_bp.route('/api/brands/scores', methods=['GET'])
@auth_required
def get_brand_scores():
    """
    Último score + delta por marca para las tarjetas del listado. Lee del
    histórico; las marcas sin snapshot de hoy se calculan ahora (acotado)
    y quedan registradas para la próxima vez.
    """
    user = get_current_user()
    if not _check_access(user):
        return _payment_required_response()

    brands = BrandLinkRepository.get_user_brands(user['id'])
    brand_ids = [b['id'] for b in brands]
    scores = ScoreSnapshotRepository.get_latest_scores(brand_ids)

    from datetime import date
    today = date.today().isoformat()
    stale = [b for b in brands if scores.get(b['id'], {}).get('date') != today]

    if stale:
        def compute_and_store(brand):
            try:
                summary = SummaryService.get_brand_summary(brand, SNAPSHOT_PERIOD)
                ScoreSnapshotRepository.upsert_today(brand['id'], summary)
            except Exception as e:
                logger.warning(f"Score backfill failed for brand {brand['id']}: {e}")

        with ThreadPoolExecutor(max_workers=SCORE_BACKFILL_WORKERS) as pool:
            list(pool.map(compute_and_store, stale))
        scores = ScoreSnapshotRepository.get_latest_scores(brand_ids)

    return jsonify({'success': True, 'scores': scores})


@ai_summary_bp.route('/api/brands/<int:brand_id>/score-history', methods=['GET'])
@auth_required
def get_brand_score_history(brand_id):
    """Serie diaria del AI Visibility Score. Query param: months = 3|6|12."""
    user = get_current_user()
    if not _check_access(user):
        return _payment_required_response()

    brand = BrandLinkRepository.get_brand(brand_id, user['id'])
    if not brand:
        return jsonify({'success': False, 'error': 'Brand not found'}), 404

    try:
        months = int(request.args.get('months', 6))
    except (TypeError, ValueError):
        months = 6

    history = ScoreSnapshotRepository.get_history(brand_id, months)
    return jsonify({'success': True, 'history': history})


@ai_summary_bp.route('/api/brands/<int:brand_id>/export/pdf', methods=['GET'])
@auth_required
def export_brand_pdf(brand_id):
    """Informe ejecutivo en PDF (one-pager) del resumen de la marca."""
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
        from flask import send_file
        from ai_summary.services.pdf_export_service import AiSummaryPdfExportService

        summary = SummaryService.get_brand_summary(brand, period)
        history = ScoreSnapshotRepository.get_history(brand_id, 6)
        pdf_buffer = AiSummaryPdfExportService().build(brand, summary, history)

        safe_name = ''.join(c if c.isalnum() or c in '-_' else '-' for c in brand['brand_name'])[:60]
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"ai-visibility-report-{safe_name.lower()}.pdf",
        )
    except ImportError as e:
        logger.error(f"PDF export dependencies missing: {e}")
        return jsonify({'success': False, 'error': 'PDF generation not available'}), 500
    except Exception as e:
        logger.error(f"Error exporting PDF for brand {brand_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Failed to generate PDF'}), 500


@ai_summary_bp.route('/api/cron/daily-snapshots', methods=['POST'])
@cron_or_auth_required
def cron_daily_snapshots():
    """
    Registrar el score diario de TODAS las marcas (cron). Autenticación:
    Bearer CRON_TOKEN o sesión de admin.
    """
    user = get_current_user()
    if user is not None and user.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Admin only'}), 403

    from ai_summary.services.summary_service import snapshot_all_brands
    result = snapshot_all_brands()
    return jsonify({'success': True, **result})
