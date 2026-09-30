"""
LLM Monitoring Routes Blueprint

Este módulo contiene todos los endpoints REST para el sistema Multi-LLM Brand Monitoring.
Se registra como Blueprint en app.py para mantener el código modular.

MODELO DE NEGOCIO:
    Los usuarios pagan una suscripción y el servicio incluye acceso a los LLMs.
    Las API keys son gestionadas globalmente por el dueño del servicio (variables de entorno).
    Los usuarios NO necesitan configurar sus propias API keys.

Endpoints:
    GET    /api/llm-monitoring/projects               - Listar proyectos
    POST   /api/llm-monitoring/projects               - Crear proyecto
    GET    /api/llm-monitoring/projects/:id           - Obtener proyecto
    PUT    /api/llm-monitoring/projects/:id           - Actualizar proyecto
    DELETE /api/llm-monitoring/projects/:id           - Eliminar proyecto (soft delete)
    Métricas, comparación, ranking de URLs, fan-out, contenido, queries, share of voice,
    respuestas y el primer análisis viven en llm_monitoring_rutas_analisis.py (sep-2026).
    /models, /models/current, /models/:id, /models/approve|reject|changelog y
    /cron/model-discovery viven en llm_monitoring_rutas_modelos.py (sep-2026).
    /health y los crons (/cron/daily-analysis, /cron/watchdog, /cron/alert) viven en
    llm_monitoring_rutas_cron.py (sep-2026).
    
    NOTA: El endpoint POST /projects/:id/analyze fue ELIMINADO.
          El análisis ahora se ejecuta AUTOMÁTICAMENTE vía cron diario a las 4:00 AM.
"""

import logging
import os
import json
from datetime import datetime, timedelta


from flask import request, jsonify

# Importar sistema de autenticación
from auth import login_required, get_current_user
from llm_monitoring_limits import (
    get_llm_plan_limits,
    count_user_active_projects,
    count_project_active_queries,
    get_llm_limits_summary,
    get_upgrade_options,
    SEARCH_UNIT_WEIGHTS,
)
from services.project_access_service import (
    get_project_permissions,
)

# Importar servicios
from database import get_db_connection
from services.llm_providers.web_search import is_search_enabled, normalize_search_mode
from services.llm_monitoring import prompt_sets as prompt_sets_lib
from services.llm_monitoring import pseudo_snapshots as pseudo_snapshots_lib
from services.country_config import get_default_language_for_country

# Helpers de informes (filtros, métricas por prompt, branded, modelos, fan-out y
# contenido): viven en llm_monitoring_informes.py desde sep-2026 y se exponen aquí
# con los mismos nombres para las rutas y para quien los importe de este módulo.
import llm_monitoring_export_excel  # exportaciones: el código vive en su módulo (sep-2026)
import llm_monitoring_export_pdf
from llm_monitoring_informes import (  # noqa: F401
    _VALID_HOST_RE,
    _normalize_days_param,
    _remove_accents,
    classify_query_branded,
    _compute_branded_metrics,
    _calculate_trend,
    _weight_for_position,
    _extract_source_host,
    _PROMPT_METRICS_SQL,
    collect_prompt_metrics,
    empty_prompt_metrics,
    _summarize_prompt_bucket,
    _OPPORTUNITY_LABELS,
    MODEL_FALLBACKS,
    fetch_current_models,
    _safe_fanout_metrics,
    _safe_content_overview,
    round_half_up,
    _as_json,
    _normalize_cluster_name,
    _REPORT_VALID_LLMS,
    ReportFilters,
    _parse_report_filters,
    _report_filter_conditions,
    _narrow_llms,
    _resolve_filtered_query_ids,
    _report_view_label,
)

# Configurar logging
logger = logging.getLogger(__name__)

# Blueprint, control de acceso, decoradores y estado del primer análisis: viven en
# llm_monitoring_base.py desde sep-2026 y se exponen aquí con los mismos nombres.
from llm_monitoring_base import (  # noqa: F401
    llm_monitoring_bp,
    _INITIAL_ANALYSIS_RUNNING,
    _INITIAL_ANALYSIS_RUNNING_LOCK,
    _safe_notify_email,
    _is_initial_analysis_running,
    _mark_initial_analysis_running,
    _clear_initial_analysis_running,
    enforce_llm_access,
    validate_project_ownership,
    _ensure_cron_token_or_admin,
)

# Rutas de análisis: viven en llm_monitoring_rutas_analisis.py desde sep-2026. Importarlo registra
# sus rutas en el blueprint; los nombres se exponen aquí como antes.
from llm_monitoring_rutas_analisis import (  # noqa: F401
    run_initial_analysis,
    get_project_metrics,
    get_urls_ranking,
    get_project_fanout,
    start_url_content_analysis,
    get_url_content_analysis,
    get_llm_comparison,
    get_project_queries,
    get_share_of_voice_history,
    get_project_responses,
)

# Rutas de cron: viven en llm_monitoring_rutas_cron.py desde sep-2026. Importarlo registra
# sus rutas en el blueprint; los nombres se exponen aquí como antes.
from llm_monitoring_rutas_cron import (  # noqa: F401
    trigger_daily_analysis,
    cron_watchdog,
    health_check,
    cron_alert,
)

# Rutas de modelos: viven en llm_monitoring_rutas_modelos.py desde sep-2026. Importarlo registra
# sus rutas en el blueprint; los nombres se exponen aquí como antes.
from llm_monitoring_rutas_modelos import (  # noqa: F401
    get_models,
    get_current_models,
    update_model,
    CHAT_MODEL_FILTERS,
    DEFAULT_PRICING_BY_TIER,
    is_chat_model,
    estimate_pricing_for_model,
    validate_model_before_switch,
    _log_model_change,
    get_model_version_score,
    is_model_newer,
    cron_model_discovery,
    approve_model_by_token,
    reject_model_by_token,
    _render_approval_result,
    get_model_changelog,
)


def _get_effective_plan_limits(user: dict) -> dict:
    """
    Devuelve límites efectivos por usuario.
    Admin opera sin límites para soporte y validación interna.
    Enterprise: respeta custom_llm_prompts_limit, custom_llm_monthly_units_limit
    y custom_llm_max_projects si están configurados por el admin; si no,
    opera sin límites (None).
    """
    limits = get_llm_plan_limits((user or {}).get('plan', 'free'))
    if user and user.get('role') == 'admin':
        limits = dict(limits)
        limits['max_projects'] = None
        limits['max_prompts_per_project'] = None
        limits['max_monthly_units'] = None
    elif user and (user or {}).get('plan') == 'enterprise':
        limits = dict(limits)
        # Aplicar custom limits si el admin los ha configurado para este usuario
        custom_prompts = user.get('custom_llm_prompts_limit')
        custom_units = user.get('custom_llm_monthly_units_limit')
        custom_projects = user.get('custom_llm_max_projects')
        if custom_prompts is not None:
            limits['max_prompts_per_project'] = int(custom_prompts)
        if custom_units is not None:
            limits['max_monthly_units'] = int(custom_units)
        if custom_projects is not None:
            limits['max_projects'] = int(custom_projects)
    return limits


# ============================================================================
# ENDPOINTS: PROYECTOS
# ============================================================================

@llm_monitoring_bp.route('/projects', methods=['GET'])
@login_required
def get_projects():
    """
    Lista todos los proyectos de monitorización del usuario actual
    
    Returns:
        JSON con lista de proyectos y métricas básicas
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required. Please sign in.'}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500
    
    try:
        cur = conn.cursor()

        try:
            # Owner projects + shared projects (viewer) when collaboration tables exist.
            cur.execute("""
                SELECT 
                    p.id,
                    p.user_id,
                    p.name,
                    p.brand_name,
                    p.brand_domain,
                    p.brand_keywords,
                    p.industry,
                    p.enabled_llms,
                    p.competitors,
                    p.competitor_domains,
                    p.competitor_keywords,
                    p.selected_competitors,
                    p.language,
                    p.country_code,
                    p.queries_per_llm,
                    p.is_active,
                    p.is_paused_by_quota,
                    p.paused_until,
                    p.paused_at,
                    p.paused_reason,
                    p.last_analysis_date,
                    p.created_at,
                    p.updated_at,
                    CASE WHEN p.user_id = %s THEN 'owner' ELSE 'viewer' END AS access_role,
                    (p.user_id = %s) AS is_owner,
                    (p.user_id = %s) AS can_edit,
                    (p.user_id = %s) AS can_manage_access,
                    (
                        SELECT COUNT(*)
                        FROM llm_monitoring_queries q
                        WHERE q.project_id = p.id AND q.is_active = TRUE
                    ) as total_queries,
                    COUNT(DISTINCT s.id) as total_snapshots,
                    MAX(s.snapshot_date) as last_snapshot_date
                FROM llm_monitoring_projects p
                LEFT JOIN llm_monitoring_snapshots s ON p.id = s.project_id
                WHERE (
                    p.user_id = %s
                    OR EXISTS (
                        SELECT 1
                        FROM project_collaborators c
                        WHERE c.module_name = 'llm_monitoring'
                          AND c.project_id = p.id
                          AND c.user_id = %s
                    )
                )
                GROUP BY p.id
                ORDER BY p.created_at DESC
            """, (
                user['id'],
                user['id'],
                user['id'],
                user['id'],
                user['id'],
                user['id'],
            ))
        except Exception as query_error:
            if "project_collaborators" not in str(query_error).lower():
                raise
            logger.warning(
                "project_collaborators table not available yet. Falling back to owner-only projects list."
            )
            conn.rollback()
            cur.execute("""
                SELECT 
                    p.id,
                    p.user_id,
                    p.name,
                    p.brand_name,
                    p.brand_domain,
                    p.brand_keywords,
                    p.industry,
                    p.enabled_llms,
                    p.competitors,
                    p.competitor_domains,
                    p.competitor_keywords,
                    p.selected_competitors,
                    p.language,
                    p.country_code,
                    p.queries_per_llm,
                    p.is_active,
                    p.is_paused_by_quota,
                    p.paused_until,
                    p.paused_at,
                    p.paused_reason,
                    p.last_analysis_date,
                    p.created_at,
                    p.updated_at,
                    'owner' AS access_role,
                    TRUE AS is_owner,
                    TRUE AS can_edit,
                    TRUE AS can_manage_access,
                    (
                        SELECT COUNT(*)
                        FROM llm_monitoring_queries q
                        WHERE q.project_id = p.id AND q.is_active = TRUE
                    ) as total_queries,
                    COUNT(DISTINCT s.id) as total_snapshots,
                    MAX(s.snapshot_date) as last_snapshot_date
                FROM llm_monitoring_projects p
                LEFT JOIN llm_monitoring_snapshots s ON p.id = s.project_id
                WHERE p.user_id = %s
                GROUP BY p.id
                ORDER BY p.created_at DESC
            """, (user['id'],))

        projects = cur.fetchall()
        
        # Formatear respuesta
        projects_list = []
        for project in projects:
            is_owner = bool(project.get('is_owner')) if project.get('is_owner') is not None else project.get('user_id') == user['id']
            can_edit = bool(project.get('can_edit')) if project.get('can_edit') is not None else is_owner
            can_manage_access = bool(project.get('can_manage_access')) if project.get('can_manage_access') is not None else is_owner
            projects_list.append({
                'id': project['id'],
                'name': project['name'],
                'brand_name': project['brand_name'],
                'brand_domain': project.get('brand_domain'),
                'brand_keywords': project.get('brand_keywords') or [],
                'industry': project['industry'],
                'enabled_llms': project['enabled_llms'],
                'competitors': project['competitors'],
                'competitor_domains': project.get('competitor_domains') or [],
                'competitor_keywords': project.get('competitor_keywords') or [],
                'selected_competitors': project.get('selected_competitors') or [],
                'language': project['language'],
                'country_code': project.get('country_code'),
                'queries_per_llm': project['queries_per_llm'],
                'total_queries': project.get('total_queries') or 0,
                'is_active': project['is_active'],
                'initial_analysis_in_progress': _is_initial_analysis_running(project['id']),
                'is_paused_by_quota': project.get('is_paused_by_quota', False),
                'paused_until': project['paused_until'].isoformat() if project.get('paused_until') else None,
                'paused_at': project['paused_at'].isoformat() if project.get('paused_at') else None,
                'paused_reason': project.get('paused_reason'),
                'last_analysis_date': project['last_analysis_date'].isoformat() if project['last_analysis_date'] else None,
                'created_at': project['created_at'].isoformat() if project['created_at'] else None,
                'updated_at': project['updated_at'].isoformat() if project['updated_at'] else None,
                'total_snapshots': project['total_snapshots'],
                'last_snapshot_date': project['last_snapshot_date'].isoformat() if project['last_snapshot_date'] else None,
                'access_role': project.get('access_role') or ('owner' if is_owner else 'viewer'),
                'is_owner': is_owner,
                'can_edit': can_edit,
                'can_manage_access': can_manage_access
            })
        
        limits_summary = get_llm_limits_summary(user)

        return jsonify({
            'success': True,
            'projects': projects_list,
            'total': len(projects_list),
            'limits': limits_summary
        }), 200
        
    except Exception as e:
        logger.error(f"Error obteniendo proyectos: {e}", exc_info=True)
        return jsonify({'error': 'Failed to load data. Please try again.'}), 500
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/usage', methods=['GET'])
@login_required
def get_usage():
    """
    Devuelve límites y consumo del usuario para LLM Monitoring
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required. Please sign in.'}), 401

    limits_summary = get_llm_limits_summary(user)
    return jsonify({'success': True, 'limits': limits_summary}), 200


@llm_monitoring_bp.route('/projects', methods=['POST'])
@login_required
def create_project():
    """
    Crea un nuevo proyecto de monitorización
    
    Body esperado:
    {
        "name": "Mi Marca SEO",
        "industry": "SEO tools",
        "brand_domain": "hmfertility.com",
        "brand_keywords": ["hmfertility", "hm", "fertility clinic"],
        "competitor_domains": ["competitor1.com"],
        "competitor_keywords": ["semrush", "ahrefs"],
        "language": "es",
        "enabled_llms": ["openai", "anthropic", "google", "perplexity"]
    }
    
    Returns:
        JSON con el proyecto creado
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required. Please sign in.'}), 401
    
    plan_limits = _get_effective_plan_limits(user)
    max_projects = plan_limits.get('max_projects')

    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({'error': 'Invalid request format'}), 400
    
    # Validar campos requeridos
    required_fields = ['name', 'industry', 'brand_keywords']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Required field: {field}'}), 400
    
    # Valores por defecto y extracción de datos
    brand_domain = data.get('brand_domain')
    brand_keywords = data.get('brand_keywords', [])
    selected_competitors = data.get('selected_competitors', [])  # ✨ NEW
    country_code = str(data.get('country_code', 'ES') or 'ES').strip().upper()
    # Idioma de contenido: si el cliente NO lo envía, derivarlo del país
    # (FR->fr, IT->it, PT->pt...) en vez de asumir 'es'. Si lo envía
    # explícitamente, se respeta tal cual (sin cambio de comportamiento).
    _language_in = str(data.get('language') or '').strip().lower()
    language = _language_in or get_default_language_for_country(country_code)
    enabled_llms = data.get('enabled_llms', ['openai', 'anthropic', 'google', 'perplexity'])
    
    # Validaciones
    if not isinstance(brand_keywords, list) or len(brand_keywords) == 0:
        return jsonify({'error': 'Please add at least one brand keyword'}), 400
    
    max_prompts = plan_limits.get('max_prompts_per_project')
    # queries_per_llm deja de ser configurable por usuario.
    # Se guarda internamente una capacidad derivada del plan para compatibilidad.
    # Enterprise (max_prompts=None) permite hasta 5000 prompts por proyecto.
    if max_prompts is None:
        configured_prompt_capacity = 5000  # Enterprise / Admin: sin límite efectivo
    elif isinstance(max_prompts, int):
        configured_prompt_capacity = max(5, min(5000, max_prompts))
    else:
        configured_prompt_capacity = 60
    
    if not isinstance(enabled_llms, list) or len(enabled_llms) == 0:
        return jsonify({'error': 'Please select at least one LLM'}), 400
    
    valid_llms = ['openai', 'anthropic', 'google', 'perplexity']
    if not all(llm in valid_llms for llm in enabled_llms):
        return jsonify({'error': f'Valid LLMs: {valid_llms}'}), 400

    if not country_code or len(country_code) != 2 or not country_code.isalpha():
        return jsonify({'error': 'Country code must be a 2-letter ISO code'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500
    
    try:
        cur = conn.cursor()

        # Lock del usuario para evitar carreras en creación de proyectos
        cur.execute("SELECT id FROM users WHERE id = %s FOR UPDATE", (user['id'],))

        if max_projects is not None:
            cur.execute("""
                SELECT COUNT(*) AS count
                FROM llm_monitoring_projects
                WHERE user_id = %s AND is_active = TRUE
            """, (user['id'],))
            row = cur.fetchone()
            active_projects = int(row['count']) if row else 0
            if active_projects >= max_projects:
                return jsonify({
                    'error': 'project_limit_reached',
                    'message': 'You have reached the maximum number of projects allowed for your plan',
                    'current_plan': user.get('plan', 'free'),
                    'upgrade_options': get_upgrade_options(user.get('plan', 'free')),
                    'limit': max_projects,
                    'current': active_projects
                }), 402
        
        # Verificar que no exista proyecto con ese nombre para el usuario
        cur.execute("""
            SELECT id FROM llm_monitoring_projects
            WHERE user_id = %s AND name = %s
        """, (user['id'], data['name']))
        
        if cur.fetchone():
            return jsonify({'error': 'A project with this name already exists'}), 409
        
        # ✨ NEW: Extract legacy fields from selected_competitors for backward compatibility
        competitor_domains = []
        competitor_keywords = []
        if selected_competitors:
            for comp in selected_competitors:
                if comp.get('domain'):
                    competitor_domains.append(comp['domain'])
                if comp.get('keywords'):
                    competitor_keywords.extend(comp['keywords'])
        
        # Insertar proyecto con nuevos campos
        cur.execute("""
            INSERT INTO llm_monitoring_projects (
                user_id, name, industry,
                brand_domain, brand_keywords,
                selected_competitors,
                competitor_domains, competitor_keywords,
                enabled_llms, language, country_code, queries_per_llm,
                is_active, created_at, updated_at,
                brand_name, competitors
            ) VALUES (
                %s, %s, %s,
                %s, %s::jsonb,
                %s::jsonb,
                %s::jsonb, %s::jsonb,
                %s, %s, %s, %s,
                TRUE, NOW(), NOW(),
                %s, %s::jsonb
            )
            RETURNING id, created_at
        """, (
            user['id'],
            data['name'],
            data['industry'],
            brand_domain,
            json.dumps(brand_keywords),
            json.dumps(selected_competitors),  # ✨ NEW
            json.dumps(competitor_domains),  # Legacy
            json.dumps(competitor_keywords),  # Legacy
            enabled_llms,
            language,
            country_code,
            configured_prompt_capacity,
            # Campos legacy por compatibilidad
            brand_keywords[0] if brand_keywords else 'Brand',
            json.dumps(competitor_keywords)  # Usar keywords como legacy competitors
        ))
        
        result = cur.fetchone()
        project_id = result['id']
        created_at = result['created_at']
        
        logger.info(f"✅ Proyecto {project_id} creado. El usuario deberá añadir prompts manualmente.")
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Project created successfully. Now add your prompts manually.',
            'project': {
                'id': project_id,
                'name': data['name'],
                'industry': data['industry'],
                'brand_domain': brand_domain,
                'brand_keywords': brand_keywords,
                'competitor_domains': competitor_domains,
                'competitor_keywords': competitor_keywords,
                'enabled_llms': enabled_llms,
                'language': language,
                'country_code': country_code,
                'queries_per_llm': configured_prompt_capacity,
                'is_active': True,
                'created_at': created_at.isoformat(),
                'total_queries': 0
            }
        }), 201
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creando proyecto: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/projects/<int:project_id>', methods=['GET'])
@login_required
@validate_project_ownership
def get_project(project_id):
    """
    Obtiene detalles de un proyecto específico
    
    Returns:
        JSON con detalles del proyecto y estadísticas
    """
    logger.info(f"📊 GET /projects/{project_id} - Iniciando...")

    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required. Please sign in.'}), 401
    
    conn = get_db_connection()
    if not conn:
        logger.error("❌ Error de conexión a BD")
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500
    
    try:
        cur = conn.cursor()
        logger.info(f"🔍 Consultando proyecto {project_id}...")
        
        # Obtener proyecto
        cur.execute("""
            SELECT 
                p.id,
                p.user_id,
                p.name,
                p.brand_name,
                p.brand_domain,
                p.brand_keywords,
                p.industry,
                p.enabled_llms,
                p.competitors,
                p.competitor_domains,
                p.competitor_keywords,
                p.selected_competitors,
                p.language,
                p.country_code,
                p.queries_per_llm,
                p.is_active,
                p.last_analysis_date,
                p.created_at,
                p.updated_at,
                p.search_mode,
                p.search_enabled_at,
                COUNT(DISTINCT q.id) FILTER (WHERE q.is_active = TRUE) as total_queries,
                COUNT(DISTINCT s.id) as total_snapshots,
                MAX(s.snapshot_date) as last_snapshot_date
            FROM llm_monitoring_projects p
            LEFT JOIN llm_monitoring_queries q ON p.id = q.project_id
            LEFT JOIN llm_monitoring_snapshots s ON p.id = s.project_id
            WHERE p.id = %s
            GROUP BY p.id, p.user_id, p.name, p.brand_name, p.brand_domain, p.brand_keywords,
                     p.industry, p.enabled_llms, p.competitors, p.competitor_domains, 
                     p.competitor_keywords, p.selected_competitors, p.language, p.country_code, p.queries_per_llm,
                     p.is_active, p.last_analysis_date, p.created_at, p.updated_at,
                     p.search_mode, p.search_enabled_at
        """, (project_id,))
        
        project = cur.fetchone()
        logger.info(f"✅ Proyecto obtenido: {project['name'] if project else 'None'}")
        
        if not project:
            logger.warning(f"⚠️ Proyecto {project_id} no encontrado")
            return jsonify({'error': 'Project not found'}), 404
        
        # 📊 CALCULAR SOV AGREGADO DE TODOS LOS DÍAS DISPONIBLES (últimos 30 días)
        # Método 2: SoV Agregado - Suma TODAS las menciones de TODOS los LLMs
        # Esto refleja el volumen REAL de menciones en el mercado
        # ✨ NUEVO: Soporte para rango de fechas global
        days = _normalize_days_param(request.args.get('days'), default=30)
        metric_type = request.args.get('metric', 'normal')
        if metric_type not in ['normal', 'weighted']:
            metric_type = 'normal'
        report_filters = _parse_report_filters(request.args)
        enabled_llms_filter = _narrow_llms(project.get('enabled_llms') or [], report_filters)
        filtered_query_ids = _resolve_filtered_query_ids(cur, project_id, report_filters, start_date=datetime.now().date() - timedelta(days=days), end_date=datetime.now().date())
        logger.info(f"📈 Consultando métricas para proyecto {project_id} (últimos {days} días)...")

        # Banner UX: mostrar aviso solo cuando hay histórico en el rango
        # de LLMs actualmente desactivados.
        cur.execute("""
            SELECT DISTINCT llm_provider
            FROM llm_monitoring_snapshots
            WHERE project_id = %s
              AND snapshot_date >= CURRENT_DATE - (%s * INTERVAL '1 day')
        """, (project_id, days))
        historical_llms_in_range = sorted([
            row['llm_provider']
            for row in cur.fetchall()
            if row.get('llm_provider')
        ])
        active_llms_set = set(enabled_llms_filter)
        historical_llms_set = set(historical_llms_in_range)
        excluded_llms_with_data = sorted(list(historical_llms_set - active_llms_set))
        model_scope_notice = {
            'show': len(excluded_llms_with_data) > 0,
            'range_days': days,
            'active_llms': enabled_llms_filter,
            'excluded_llms_with_data': excluded_llms_with_data,
            'historical_llms_in_range': historical_llms_in_range
        }
        
        if filtered_query_ids is not None:
            # Filtro global activo → pseudo-snapshots desde results
            today = datetime.now().date()
            all_snapshots = pseudo_snapshots_lib.build_pseudo_snapshots(
                cur, project_id, filtered_query_ids,
                today - timedelta(days=days), None,
                enabled_llms=enabled_llms_filter,
            )
            previous_snapshots = pseudo_snapshots_lib.build_pseudo_snapshots(
                cur, project_id, filtered_query_ids,
                today - timedelta(days=days * 2),
                today - timedelta(days=days + 1),
                enabled_llms=enabled_llms_filter,
            )
            # Mismo orden que el camino legacy (fecha DESC, provider ASC)
            for _pseudo_rows in (all_snapshots, previous_snapshots):
                _pseudo_rows.sort(key=lambda s: s['llm_provider'])
                _pseudo_rows.sort(key=lambda s: s['snapshot_date'], reverse=True)
        else:
            # Obtener todos los snapshots del rango seleccionado
            # ✨ NUEVO: Incluir campos Top3/5/10 para métricas de posición granulares
            snapshots_query = """
                SELECT
                    llm_provider,
                    mention_rate,
                    avg_position,
                    share_of_voice,
                    weighted_share_of_voice,
                    positive_mentions,
                    neutral_mentions,
                    negative_mentions,
                    total_mentions,
                    total_queries,
                    total_competitor_mentions,
                    weighted_competitor_breakdown,
                    appeared_in_top3,
                    appeared_in_top5,
                    appeared_in_top10,
                    snapshot_date
                FROM llm_monitoring_snapshots
                WHERE project_id = %s
                    AND snapshot_date >= CURRENT_DATE - (%s * INTERVAL '1 day')
            """
            snapshots_params = [project_id, days]
            if enabled_llms_filter:
                snapshots_query += " AND llm_provider = ANY(%s)"
                snapshots_params.append(enabled_llms_filter)
            snapshots_query += " ORDER BY snapshot_date DESC, llm_provider"
            cur.execute(snapshots_query, snapshots_params)

            all_snapshots = cur.fetchall()
            logger.info(f"📊 Métricas encontradas: {len(all_snapshots)} snapshots (últimos {days} días)")

            # ✨ NUEVO: Obtener snapshots del período ANTERIOR para calcular tendencias
            # Si el período actual es "últimos 30 días", el anterior es "hace 60-31 días"
            previous_snapshots_query = """
                SELECT
                    llm_provider,
                    mention_rate,
                    avg_position,
                    share_of_voice,
                    weighted_share_of_voice,
                    positive_mentions,
                    neutral_mentions,
                    negative_mentions,
                    total_mentions,
                    total_queries,
                    total_competitor_mentions,
                    weighted_competitor_breakdown,
                    appeared_in_top3,
                    appeared_in_top5,
                    appeared_in_top10,
                    snapshot_date
                FROM llm_monitoring_snapshots
                WHERE project_id = %s
                    AND snapshot_date >= CURRENT_DATE - (%s * INTERVAL '1 day')
                    AND snapshot_date < CURRENT_DATE - (%s * INTERVAL '1 day')
            """
            previous_snapshots_params = [project_id, days * 2, days]
            if enabled_llms_filter:
                previous_snapshots_query += " AND llm_provider = ANY(%s)"
                previous_snapshots_params.append(enabled_llms_filter)
            previous_snapshots_query += " ORDER BY snapshot_date DESC, llm_provider"
            cur.execute(previous_snapshots_query, previous_snapshots_params)

            previous_snapshots = cur.fetchall()
        logger.info(f"📊 Snapshots período anterior: {len(previous_snapshots)} (para calcular tendencias)")
        
        # 🧮 Calcular MÉTRICAS AGREGADAS (volumen real)
        # En lugar de promediar SoV por LLM, sumamos TODAS las menciones
        
        # Totales agregados - PERÍODO ACTUAL
        total_brand_mentions = 0
        total_competitor_mentions = 0
        total_queries_all = 0
        total_positive = 0
        total_neutral = 0
        total_negative = 0
        all_positions = []
        
        # ✨ NUEVO: Totales ponderados para Share of Voice
        total_brand_mentions_weighted = 0.0
        total_competitor_mentions_weighted = 0.0
        
        # ✨ NUEVO: Métricas de posición granulares
        total_top3 = 0
        total_top5 = 0
        total_top10 = 0
        
        # Agrupar por LLM para cálculos individuales
        snapshots_by_llm = {}
        def _parse_weighted_breakdown(raw_value):
            if isinstance(raw_value, dict):
                return raw_value
            if isinstance(raw_value, str):
                try:
                    parsed = json.loads(raw_value)
                    return parsed if isinstance(parsed, dict) else {}
                except Exception:
                    return {}
            return {}
        
        def _accumulate_weighted_totals(snapshot):
            nonlocal total_brand_mentions_weighted, total_competitor_mentions_weighted
            
            weighted_sov_raw = snapshot.get('weighted_share_of_voice')
            try:
                weighted_sov = float(weighted_sov_raw) if weighted_sov_raw is not None else None
            except Exception:
                weighted_sov = None
            
            weighted_breakdown = _parse_weighted_breakdown(snapshot.get('weighted_competitor_breakdown'))
            
            if weighted_sov is not None and weighted_breakdown:
                try:
                    total_weighted_comp = sum(float(v) for v in weighted_breakdown.values() if v is not None)
                except Exception:
                    total_weighted_comp = 0.0
                
                if weighted_sov >= 100:
                    weighted_brand = total_weighted_comp if total_weighted_comp > 0 else 1.0
                elif weighted_sov > 0:
                    weighted_brand = (weighted_sov / (100 - weighted_sov)) * total_weighted_comp
                else:
                    weighted_brand = 0.0
                
                total_brand_mentions_weighted += weighted_brand
                total_competitor_mentions_weighted += total_weighted_comp
            else:
                # Fallback a métricas normales si no hay datos ponderados
                total_brand_mentions_weighted += (snapshot.get('total_mentions') or 0)
                total_competitor_mentions_weighted += (snapshot.get('total_competitor_mentions') or 0)
        
        for snapshot in all_snapshots:
            llm = snapshot['llm_provider']
            if llm not in snapshots_by_llm:
                snapshots_by_llm[llm] = []
            snapshots_by_llm[llm].append(snapshot)
            
            # Acumular totales agregados
            total_brand_mentions += (snapshot.get('total_mentions') or 0)
            total_competitor_mentions += (snapshot.get('total_competitor_mentions') or 0)
            total_queries_all += (snapshot.get('total_queries') or 0)
            total_positive += (snapshot.get('positive_mentions') or 0)
            total_neutral += (snapshot.get('neutral_mentions') or 0)
            total_negative += (snapshot.get('negative_mentions') or 0)
            
            # ✨ NUEVO: Acumular Top3/5/10
            total_top3 += (snapshot.get('appeared_in_top3') or 0)
            total_top5 += (snapshot.get('appeared_in_top5') or 0)
            total_top10 += (snapshot.get('appeared_in_top10') or 0)
            
            # Acumular posiciones
            if snapshot.get('avg_position') is not None:
                all_positions.append(float(snapshot['avg_position']))
            
            # ✨ NUEVO: Acumular métricas ponderadas para SoV
            _accumulate_weighted_totals(snapshot)
        
        # ✨ NUEVO: Calcular métricas del PERÍODO ANTERIOR para tendencias
        prev_brand_mentions = 0
        prev_competitor_mentions = 0
        prev_queries_all = 0
        prev_positive = 0
        prev_neutral = 0
        prev_negative = 0
        prev_positions = []
        
        # ✨ NUEVO: Totales ponderados del período anterior
        prev_brand_mentions_weighted = 0.0
        prev_competitor_mentions_weighted = 0.0
        
        def _accumulate_prev_weighted_totals(snapshot):
            nonlocal prev_brand_mentions_weighted, prev_competitor_mentions_weighted
            
            weighted_sov_raw = snapshot.get('weighted_share_of_voice')
            try:
                weighted_sov = float(weighted_sov_raw) if weighted_sov_raw is not None else None
            except Exception:
                weighted_sov = None
            
            weighted_breakdown = _parse_weighted_breakdown(snapshot.get('weighted_competitor_breakdown'))
            
            if weighted_sov is not None and weighted_breakdown:
                try:
                    total_weighted_comp = sum(float(v) for v in weighted_breakdown.values() if v is not None)
                except Exception:
                    total_weighted_comp = 0.0
                
                if weighted_sov >= 100:
                    weighted_brand = total_weighted_comp if total_weighted_comp > 0 else 1.0
                elif weighted_sov > 0:
                    weighted_brand = (weighted_sov / (100 - weighted_sov)) * total_weighted_comp
                else:
                    weighted_brand = 0.0
                
                prev_brand_mentions_weighted += weighted_brand
                prev_competitor_mentions_weighted += total_weighted_comp
            else:
                # Fallback a métricas normales si no hay datos ponderados
                prev_brand_mentions_weighted += (snapshot.get('total_mentions') or 0)
                prev_competitor_mentions_weighted += (snapshot.get('total_competitor_mentions') or 0)
        
        for snapshot in previous_snapshots:
            prev_brand_mentions += (snapshot.get('total_mentions') or 0)
            prev_competitor_mentions += (snapshot.get('total_competitor_mentions') or 0)
            prev_queries_all += (snapshot.get('total_queries') or 0)
            prev_positive += (snapshot.get('positive_mentions') or 0)
            prev_neutral += (snapshot.get('neutral_mentions') or 0)
            prev_negative += (snapshot.get('negative_mentions') or 0)
            if snapshot.get('avg_position') is not None:
                prev_positions.append(float(snapshot['avg_position']))
            
            # ✨ NUEVO: Acumular métricas ponderadas para SoV (periodo anterior)
            _accumulate_prev_weighted_totals(snapshot)
        
        # Métricas del período anterior
        prev_mention_rate = (prev_brand_mentions / prev_queries_all * 100) if prev_queries_all > 0 else 0
        if metric_type == 'weighted':
            prev_sov = (
                (prev_brand_mentions_weighted / (prev_brand_mentions_weighted + prev_competitor_mentions_weighted) * 100)
                if (prev_brand_mentions_weighted + prev_competitor_mentions_weighted) > 0 else 0
            )
        else:
            prev_sov = (
                (prev_brand_mentions / (prev_brand_mentions + prev_competitor_mentions) * 100)
                if (prev_brand_mentions + prev_competitor_mentions) > 0 else 0
            )
        prev_positive_pct = (prev_positive / prev_queries_all * 100) if prev_queries_all > 0 else 0
        
        # 📊 Calcular métricas agregadas globales
        aggregated_mention_rate = (total_brand_mentions / total_queries_all * 100) if total_queries_all > 0 else 0
        if metric_type == 'weighted':
            aggregated_sov = (
                (total_brand_mentions_weighted / (total_brand_mentions_weighted + total_competitor_mentions_weighted) * 100)
                if (total_brand_mentions_weighted + total_competitor_mentions_weighted) > 0 else 0
            )
        else:
            aggregated_sov = (
                (total_brand_mentions / (total_brand_mentions + total_competitor_mentions) * 100)
                if (total_brand_mentions + total_competitor_mentions) > 0 else 0
            )
        aggregated_avg_position = sum(all_positions) / len(all_positions) if all_positions else None
        
        # ✨ NUEVO: Métricas de posición desde resultados (consistencia con Responses Inspector)
        results_total_appearances = None
        results_avg_position = None
        results_top3 = 0
        results_top5 = 0
        results_top10 = 0
        
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        position_query = """
            SELECT 
                COUNT(*) FILTER (WHERE brand_mentioned) as total_mentions,
                AVG(position_in_list) FILTER (
                    WHERE brand_mentioned 
                      AND position_in_list IS NOT NULL 
                      AND position_in_list <= 30
                ) as avg_position,
                COUNT(*) FILTER (
                    WHERE brand_mentioned 
                      AND position_in_list IS NOT NULL 
                      AND position_in_list <= 3
                ) as top3,
                COUNT(*) FILTER (
                    WHERE brand_mentioned 
                      AND position_in_list IS NOT NULL 
                      AND position_in_list <= 5
                ) as top5,
                COUNT(*) FILTER (
                    WHERE brand_mentioned 
                      AND position_in_list IS NOT NULL 
                      AND position_in_list <= 10
                ) as top10
            FROM llm_monitoring_results
            WHERE project_id = %s
              AND analysis_date >= %s
              AND analysis_date <= %s
        """
        position_params = [project_id, start_date, end_date]
        if filtered_query_ids is not None:
            position_query += " AND query_id = ANY(%s)"
            position_params.append(filtered_query_ids)
        if enabled_llms_filter:
            position_query += " AND llm_provider = ANY(%s)"
            position_params.append(enabled_llms_filter)
        cur.execute(position_query, position_params)

        position_row = cur.fetchone()
        if position_row:
            results_total_appearances = position_row.get('total_mentions') or 0
            results_avg_position = position_row.get('avg_position')
            results_top3 = position_row.get('top3') or 0
            results_top5 = position_row.get('top5') or 0
            results_top10 = position_row.get('top10') or 0
        
        # ✨ NUEVO: Calcular tasas de posición (% sobre total de menciones donde aparecimos)
        # Nota: Top3 incluye Top1, Top5 incluye Top3, etc.
        if results_total_appearances is not None:
            total_appearances = results_total_appearances
            total_top3 = results_top3
            total_top5 = results_top5
            total_top10 = results_top10
            if results_avg_position is not None:
                aggregated_avg_position = float(results_avg_position)
        else:
            total_appearances = total_brand_mentions  # Usar menciones como base
        top3_rate = (total_top3 / total_appearances * 100) if total_appearances > 0 else 0
        top5_rate = (total_top5 / total_appearances * 100) if total_appearances > 0 else 0
        top10_rate = (total_top10 / total_appearances * 100) if total_appearances > 0 else 0
        
        # Sentiment agregado
        aggregated_positive_pct = (total_positive / total_queries_all * 100) if total_queries_all > 0 else 0
        aggregated_neutral_pct = (total_neutral / total_queries_all * 100) if total_queries_all > 0 else 0
        aggregated_negative_pct = (total_negative / total_queries_all * 100) if total_queries_all > 0 else 0
        
        has_previous_period_data = len(previous_snapshots) > 0 and prev_queries_all > 0

        # ✨ NUEVO: Calcular TENDENCIAS (cambio vs período anterior)
        # Alias local → función de módulo (extraída para reusar en /metrics, /comparison, exports)
        calculate_trend = _calculate_trend
        
        # ✨ Calcular tendencia del SENTIMIENTO de forma categórica
        def get_dominant_sentiment(positive, neutral, negative):
            """Determina el sentimiento dominante y devuelve un valor numérico para comparación"""
            if positive >= neutral and positive >= negative:
                return ('positive', 3)  # 3 = mejor
            elif neutral >= positive and neutral >= negative:
                return ('neutral', 2)   # 2 = medio
            else:
                return ('negative', 1)  # 1 = peor
        
        current_sentiment, current_sentiment_value = get_dominant_sentiment(
            aggregated_positive_pct, aggregated_neutral_pct, aggregated_negative_pct
        )
        
        # Sentimiento del período anterior
        prev_positive_pct_calc = (prev_positive / prev_queries_all * 100) if prev_queries_all > 0 else 0
        prev_neutral_pct_calc = (prev_neutral / prev_queries_all * 100) if prev_queries_all > 0 else 0
        prev_negative_pct_calc = (prev_negative / prev_queries_all * 100) if prev_queries_all > 0 else 0
        
        prev_sentiment, prev_sentiment_value = get_dominant_sentiment(
            prev_positive_pct_calc, prev_neutral_pct_calc, prev_negative_pct_calc
        )
        
        # Determinar la tendencia categórica del sentimiento
        if not has_previous_period_data:
            sentiment_trend = None
        elif current_sentiment_value > prev_sentiment_value:
            sentiment_trend = {'direction': 'better', 'previous': prev_sentiment}
        elif current_sentiment_value < prev_sentiment_value:
            sentiment_trend = {'direction': 'worse', 'previous': prev_sentiment}
        else:
            sentiment_trend = {'direction': 'same', 'previous': prev_sentiment}

        trends = {
            'mention_rate': calculate_trend(aggregated_mention_rate, prev_mention_rate, has_previous_period_data),
            'share_of_voice': calculate_trend(aggregated_sov, prev_sov, has_previous_period_data),
            'sentiment': sentiment_trend  # ✨ Ahora es categórico: better/worse/same
        }
        
        # 🎯 Calcular métricas individuales por LLM (para compatibilidad con frontend)
        # El frontend espera datos por LLM, pero ahora usamos los valores agregados
        metrics_by_llm = {}
        
        for llm, llm_snapshots in snapshots_by_llm.items():
            if not llm_snapshots:
                continue
            
            # Último snapshot para fecha de referencia
            latest_snapshot = llm_snapshots[0]
            
            # ✨ IMPORTANTE: Usar métricas AGREGADAS para TODO (consistencia total)
            # Método 2: SoV Agregado aplicado a TODAS las métricas
            metrics_by_llm[llm] = {
                'mention_rate': round(aggregated_mention_rate, 2),  # ✨ AGREGADO (consistente)
                'avg_position': round(aggregated_avg_position, 2) if aggregated_avg_position else None,  # ✨ AGREGADO
                'share_of_voice': round(aggregated_sov, 2),  # ✨ AGREGADO
                'sentiment': {
                    'positive': round(aggregated_positive_pct, 2),  # ✨ AGREGADO
                    'neutral': round(aggregated_neutral_pct, 2),    # ✨ AGREGADO
                    'negative': round(aggregated_negative_pct, 2)   # ✨ AGREGADO
                },
                'total_queries': latest_snapshot.get('total_queries'),
                'date': latest_snapshot['snapshot_date'].isoformat() if latest_snapshot['snapshot_date'] else None,
                'snapshots_count': len(llm_snapshots)
            }
        
        logger.info(
            f"✅ Métricas agregadas calculadas ({metric_type}): "
            f"SoV={aggregated_sov:.2f}%, Mention Rate={aggregated_mention_rate:.2f}%"
        )
        
        # ✨ NUEVO: Calcular Quality Score
        # Componentes del Quality Score:
        # 1. Completeness: ¿Cada LLM analizó todas las queries esperadas?
        # 2. Freshness: ¿Cuánto hace del último análisis?
        # 3. Coverage: ¿Qué % de LLMs tienen datos?
        #
        # IMPORTANTE: la calidad del dato es una propiedad del PROYECTO, no de
        # la vista. Con la barra de filtros activa (p.ej. 2 de 4 LLMs), los
        # snapshots de arriba están filtrados y la calidad saldría degradada
        # (cobertura 2/4, completeness a la mitad) sin serlo. Se calcula
        # SIEMPRE sobre los snapshots reales sin filtrar.
        enabled_llms = project['enabled_llms'] or []
        llms_expected = len(enabled_llms)

        view_is_filtered = (filtered_query_ids is not None) or bool(report_filters.llms)
        if view_is_filtered:
            quality_sql = """
                SELECT llm_provider, total_queries, snapshot_date
                FROM llm_monitoring_snapshots
                WHERE project_id = %s
                    AND snapshot_date >= CURRENT_DATE - (%s * INTERVAL '1 day')
            """
            quality_params = [project_id, days]
            if enabled_llms:
                quality_sql += " AND llm_provider = ANY(%s)"
                quality_params.append(enabled_llms)
            cur.execute(quality_sql, quality_params)
            quality_rows = cur.fetchall()
        else:
            quality_rows = all_snapshots

        quality_snapshots_by_llm = {}
        for _q_snap in quality_rows:
            quality_snapshots_by_llm.setdefault(_q_snap['llm_provider'], []).append(_q_snap)
        
        # Completeness (0-100): promedio de completitud por LLM (queries analizadas / esperadas)
        # La completitud se calcula contra prompts realmente configurados en el proyecto.
        expected_queries = project.get('total_queries') or 0
        llm_completeness = {}
        
        total_analyzed_queries = 0
        total_expected_queries = expected_queries * llms_expected if expected_queries else 0
        
        for llm_name in enabled_llms:
            snapshots = quality_snapshots_by_llm.get(llm_name, [])
            latest_snapshot = None
            if snapshots:
                latest_snapshot = max(
                    snapshots,
                    key=lambda s: s.get('snapshot_date') or datetime.min
                )
            analyzed = (latest_snapshot or {}).get('total_queries') or 0
            total_analyzed_queries += analyzed
            if expected_queries and expected_queries > 0:
                pct = min(100.0, (analyzed / expected_queries) * 100)
            else:
                pct = 0.0
            llm_completeness[llm_name] = {
                'analyzed': analyzed,
                'expected': expected_queries,
                'completeness_pct': round(pct, 1)
            }
        if total_expected_queries > 0:
            completeness = min(100.0, (total_analyzed_queries / total_expected_queries) * 100)
        else:
            completeness = 0
        
        # Coverage (0-100): % de LLMs con al menos un snapshot
        llms_with_data = sum(1 for llm in enabled_llms if llm in quality_snapshots_by_llm)
        coverage = (llms_with_data / llms_expected * 100) if llms_expected > 0 else 0
        
        # Freshness (0-100): 100 si datos de hoy, decrece con el tiempo
        from datetime import date as date_type
        last_snapshot = project['last_snapshot_date']
        if last_snapshot:
            days_since_update = (date_type.today() - last_snapshot).days
            freshness = max(0, 100 - (days_since_update * 10))  # -10% por día
        else:
            freshness = 0
        
        # Quality Score final (promedio ponderado)
        quality_score = round((completeness * 0.5 + freshness * 0.3 + coverage * 0.2), 1)
        
        quality_data = {
            'score': quality_score,
            'components': {
                'completeness': round(completeness, 1),
                'freshness': round(freshness, 1),
                'coverage': round(coverage, 1)
            },
            'details': {
                'llms_with_data': llms_with_data,
                'llms_expected': llms_expected,
                'total_analyzed_queries': total_analyzed_queries,
                'total_expected_queries': total_expected_queries,
                'queries_by_llm': llm_completeness,
                'days_since_update': (date_type.today() - last_snapshot).days if last_snapshot else None,
                'total_snapshots_in_period': len(quality_rows)
            }
        }
        
        permissions = get_project_permissions(user['id'], 'llm_monitoring', project_id)
        logger.info(f"✅ Preparando respuesta para proyecto {project_id}")
        return jsonify({
            'success': True,
            'project': {
                'id': project['id'],
                'name': project['name'],
                'brand_name': project['brand_name'],
                'brand_domain': project.get('brand_domain'),
                'brand_keywords': project.get('brand_keywords', []),
                'industry': project['industry'],
                'enabled_llms': project['enabled_llms'],
                'competitors': project['competitors'],  # Legacy
                'competitor_domains': project.get('competitor_domains', []),  # Legacy
                'competitor_keywords': project.get('competitor_keywords', []),  # Legacy
                'selected_competitors': project.get('selected_competitors', []),  # ✨ NUEVO
                'language': project['language'],
                'country_code': project.get('country_code'),
                'queries_per_llm': project['queries_per_llm'],
                'is_active': project['is_active'],
                'last_analysis_date': project['last_analysis_date'].isoformat() if project['last_analysis_date'] else None,
                'created_at': project['created_at'].isoformat() if project['created_at'] else None,
                'updated_at': project['updated_at'].isoformat() if project['updated_at'] else None,
                'total_queries': project['total_queries'],
                'total_snapshots': project['total_snapshots'],
                'last_snapshot_date': project['last_snapshot_date'].isoformat() if project['last_snapshot_date'] else None,
                # Búsqueda web (P7): la UI de fan-out solo se pinta con search_mode='auto'
                'search_mode': normalize_search_mode(project.get('search_mode')),
                'search_enabled_at': project['search_enabled_at'].isoformat() if project.get('search_enabled_at') else None,
                **({'search_unit_weights': SEARCH_UNIT_WEIGHTS} if is_search_enabled(project.get('search_mode')) else {}),
                'access_role': permissions.get('access_role'),
                'is_owner': permissions.get('is_owner', False),
                'can_edit': permissions.get('can_edit', False),
                'can_manage_access': permissions.get('can_manage_access', False),
            },
            'latest_metrics': metrics_by_llm,
            # ✨ NUEVO: Tendencias (comparación con período anterior)
            'trends': trends,
            # ✨ NUEVO: Métricas de posición granulares
            'position_metrics': {
                'avg_position': round(aggregated_avg_position, 1) if aggregated_avg_position else None,
                'top3_rate': round(top3_rate, 1),
                'top5_rate': round(top5_rate, 1),
                'top10_rate': round(top10_rate, 1),
                'total_top3': total_top3,
                'total_top5': total_top5,
                'total_top10': total_top10,
                'total_appearances': total_appearances
            },
            # ✨ NUEVO: Quality Score del análisis
            'quality_score': quality_data,
            'model_scope_notice': model_scope_notice
        }), 200
        
    except Exception as e:
        logger.error(f"Error obteniendo proyecto: {e}", exc_info=True)
        return jsonify({'error': 'Failed to load data. Please try again.'}), 500
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/projects/<int:project_id>', methods=['PUT'])
@login_required
@validate_project_ownership
def update_project(project_id):
    """
    Actualiza un proyecto existente
    
    Body (todos opcionales):
    {
        "name": "Nuevo Nombre",
        "industry": "Nueva Industria",
        "brand_domain": "newdomain.com",
        "brand_keywords": ["keyword1", "keyword2"],
        "competitor_domains": ["comp1.com"],
        "competitor_keywords": ["comp_kw1", "comp_kw2"],
        "is_active": false,
        "enabled_llms": ["openai", "google"]
    }
    
    Returns:
        JSON con el proyecto actualizado
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body is empty'}), 400

    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required. Please sign in.'}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500
    
    try:
        cur = conn.cursor()

        cur.execute("""
            SELECT enabled_llms
            FROM llm_monitoring_projects
            WHERE id = %s
        """, (project_id,))
        current_project_row = cur.fetchone()
        if not current_project_row:
            return jsonify({'error': 'Project not found'}), 404
        previous_enabled_llms = current_project_row.get('enabled_llms') or []
        
        # Campos actualizables
        updates = []
        params = []
        
        if 'name' in data:
            updates.append("name = %s")
            params.append(data['name'])
        
        if 'industry' in data:
            updates.append("industry = %s")
            params.append(data['industry'])

        if 'language' in data:
            language = str(data.get('language') or '').strip().lower()
            if not language:
                return jsonify({'error': 'Language cannot be empty'}), 400
            updates.append("language = %s")
            params.append(language)
        
        if 'brand_domain' in data:
            updates.append("brand_domain = %s")
            params.append(data['brand_domain'])
        
        if 'brand_keywords' in data:
            if not isinstance(data['brand_keywords'], list) or len(data['brand_keywords']) == 0:
                return jsonify({'error': 'Please add at least one brand keyword'}), 400
            updates.append("brand_keywords = %s::jsonb")
            params.append(json.dumps(data['brand_keywords']))
            # Actualizar también brand_name legacy
            updates.append("brand_name = %s")
            params.append(data['brand_keywords'][0])
        
        # ✨ NEW: Handle selected_competitors (and extract legacy fields)
        if 'selected_competitors' in data:
            selected_competitors = data['selected_competitors']
            updates.append("selected_competitors = %s::jsonb")
            params.append(json.dumps(selected_competitors))
            
            # Extract legacy fields for backward compatibility
            competitor_domains = []
            competitor_keywords = []
            if selected_competitors:
                for comp in selected_competitors:
                    if comp.get('domain'):
                        competitor_domains.append(comp['domain'])
                    if comp.get('keywords'):
                        competitor_keywords.extend(comp['keywords'])
            
            # Update legacy fields
            updates.append("competitor_domains = %s::jsonb")
            params.append(json.dumps(competitor_domains))
            updates.append("competitor_keywords = %s::jsonb")
            params.append(json.dumps(competitor_keywords))
            updates.append("competitors = %s::jsonb")
            params.append(json.dumps(competitor_keywords))
        
        if 'is_active' in data:
            updates.append("is_active = %s")
            params.append(data['is_active'])
        
        if 'enabled_llms' in data:
            # Validar LLMs
            valid_llms = ['openai', 'anthropic', 'google', 'perplexity']
            if not isinstance(data['enabled_llms'], list) or len(data['enabled_llms']) == 0:
                return jsonify({'error': 'Please select at least one LLM'}), 400
            if not all(llm in valid_llms for llm in data['enabled_llms']):
                return jsonify({'error': f'Valid LLMs: {valid_llms}'}), 400
            updates.append("enabled_llms = %s")
            params.append(data['enabled_llms'])
        
        if 'country_code' in data:
            country_code = str(data.get('country_code') or '').strip().upper()
            if not country_code or len(country_code) != 2 or not country_code.isalpha():
                return jsonify({'error': 'Country code must be a 2-letter ISO code'}), 400
            updates.append("country_code = %s")
            params.append(country_code)
        
        if not updates:
            return jsonify({'error': 'No fields to update'}), 400
        
        # Actualizar proyecto
        updates.append("updated_at = NOW()")
        params.append(project_id)
        
        query = f"""
            UPDATE llm_monitoring_projects
            SET {', '.join(updates)}
            WHERE id = %s
            RETURNING *
        """
        
        cur.execute(query, params)
        project = cur.fetchone()
        
        conn.commit()

        updated_enabled_llms = project.get('enabled_llms') or []
        llm_changes = {
            'previous_enabled_llms': previous_enabled_llms,
            'current_enabled_llms': updated_enabled_llms,
            'added_llms': sorted(list(set(updated_enabled_llms) - set(previous_enabled_llms))),
            'removed_llms': sorted(list(set(previous_enabled_llms) - set(updated_enabled_llms)))
        }
        model_selection_changed = (
            'enabled_llms' in data and
            (len(llm_changes['added_llms']) > 0 or len(llm_changes['removed_llms']) > 0)
        )
        
        return jsonify({
            'success': True,
            'model_selection_changed': model_selection_changed,
            'llm_changes': llm_changes if model_selection_changed else None,
            'project': {
                'id': project['id'],
                'name': project['name'],
                'brand_name': project['brand_name'],
                'brand_domain': project['brand_domain'],
                'brand_keywords': project['brand_keywords'],
                'industry': project['industry'],
                'enabled_llms': project['enabled_llms'],
                'competitors': project['competitors'],
                'competitor_domains': project['competitor_domains'],
                'competitor_keywords': project['competitor_keywords'],
                'language': project['language'],
                'country_code': project['country_code'],
                'queries_per_llm': project['queries_per_llm'],
                'is_active': project['is_active'],
                'updated_at': project['updated_at'].isoformat() if project['updated_at'] else None
            }
        }), 200
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error actualizando proyecto: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/projects/<int:project_id>/deactivate', methods=['PUT'])
@login_required
@validate_project_ownership
def deactivate_project(project_id):
    """
    Desactiva un proyecto (marca is_active = false)
    El proyecto deja de ejecutarse en el CRON diario pero mantiene sus datos
    
    Returns:
        JSON con confirmación
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500
    
    try:
        cur = conn.cursor()
        
        # Marcar como inactivo
        cur.execute("""
            UPDATE llm_monitoring_projects
            SET is_active = FALSE, updated_at = NOW()
            WHERE id = %s AND is_active = TRUE
            RETURNING id, name
        """, (project_id,))
        
        project = cur.fetchone()
        
        if not project:
            return jsonify({'error': 'Project not found or already inactive'}), 404
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'Project "{project["name"]}" deactivated. It will no longer run in automatic analyses.',
            'project_id': project['id']
        }), 200
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error desactivando proyecto: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/projects/<int:project_id>/activate', methods=['PUT'])
@login_required
@validate_project_ownership
def activate_project(project_id):
    """
    Reactiva un proyecto inactivo (marca is_active = true)
    
    Returns:
        JSON con confirmación
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required. Please sign in.'}), 401
    plan_limits = _get_effective_plan_limits(user)
    max_projects = plan_limits.get('max_projects')
    active_projects = count_user_active_projects(user['id'])
    if max_projects is not None and active_projects >= max_projects:
        return jsonify({
            'error': 'project_limit_reached',
            'message': 'You have reached the maximum number of projects allowed for your plan',
            'current_plan': user.get('plan', 'free'),
            'upgrade_options': get_upgrade_options(user.get('plan', 'free')),
            'limit': max_projects,
            'current': active_projects
        }), 402

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500
    
    try:
        cur = conn.cursor()
        
        # Marcar como activo
        cur.execute("""
            UPDATE llm_monitoring_projects
            SET is_active = TRUE, updated_at = NOW()
            WHERE id = %s AND is_active = FALSE
            RETURNING id, name
        """, (project_id,))
        
        project = cur.fetchone()
        
        if not project:
            return jsonify({'error': 'Project not found or already active'}), 404
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'Project "{project["name"]}" reactivated. It will be included in upcoming automatic analyses.',
            'project_id': project['id']
        }), 200
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error reactivando proyecto: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/projects/<int:project_id>', methods=['DELETE'])
@login_required
@validate_project_ownership
def delete_project(project_id):
    """
    Elimina DEFINITIVAMENTE un proyecto (hard delete)
    SOLO funciona si el proyecto está INACTIVO
    
    Elimina:
    - El proyecto
    - Todas sus queries
    - Todos los resultados de análisis
    - Todos los snapshots
    
    Returns:
        JSON con confirmación
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500
    
    try:
        cur = conn.cursor()
        
        # Verificar que el proyecto esté inactivo
        cur.execute("""
            SELECT id, name, is_active 
            FROM llm_monitoring_projects
            WHERE id = %s
        """, (project_id,))
        
        project = cur.fetchone()
        
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        if project['is_active']:
            return jsonify({
                'error': 'Cannot delete an active project. Please deactivate it first.',
                'action_required': 'deactivate_first'
            }), 400
        
        project_name = project['name']
        
        # Eliminar en cascada (orden importante para foreign keys)
        # 1. Snapshots
        cur.execute("DELETE FROM llm_monitoring_snapshots WHERE project_id = %s", (project_id,))
        snapshots_deleted = cur.rowcount
        
        # 2. Resultados
        cur.execute("DELETE FROM llm_monitoring_results WHERE project_id = %s", (project_id,))
        results_deleted = cur.rowcount
        
        # 3. Queries
        cur.execute("DELETE FROM llm_monitoring_queries WHERE project_id = %s", (project_id,))
        queries_deleted = cur.rowcount
        
        # 4. Proyecto
        cur.execute("DELETE FROM llm_monitoring_projects WHERE id = %s", (project_id,))
        
        conn.commit()
        
        logger.info(f"🗑️ Proyecto '{project_name}' eliminado definitivamente:")
        logger.info(f"   - Queries: {queries_deleted}")
        logger.info(f"   - Resultados: {results_deleted}")
        logger.info(f"   - Snapshots: {snapshots_deleted}")
        
        return jsonify({
            'success': True,
            'message': f'Proyecto "{project_name}" eliminado definitivamente',
            'project_id': project_id,
            'stats': {
                'queries_deleted': queries_deleted,
                'results_deleted': results_deleted,
                'snapshots_deleted': snapshots_deleted
            }
        }), 200
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error eliminando proyecto: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        cur.close()
        conn.close()


# ============================================================================
# ENDPOINTS: PROMPTS/QUERIES (Manual Management)
# ============================================================================
@llm_monitoring_bp.route('/projects/<int:project_id>/queries', methods=['POST'])
@login_required
@validate_project_ownership
def add_queries_to_project(project_id):
    """
    Añade queries/prompts manualmente a un proyecto
    
    Body esperado:
    {
        "queries": ["¿Qué es X?", "¿Cómo funciona Y?", ...],
        "language": "es" (opcional, default del proyecto),
        "query_type": "manual" (opcional, default: "manual")
    }
    
    Returns:
        JSON con resultado de la operación
    """
    user = get_current_user()
    
    data = request.get_json()
    queries_list = data.get('queries', [])
    language = data.get('language')
    query_type = data.get('query_type', 'manual')
    # ✨ NEW: optional cluster to assign to all prompts in this batch
    cluster_assignment_raw = data.get('cluster', None)
    target_cluster = None
    if cluster_assignment_raw is not None and cluster_assignment_raw != '':
        target_cluster = _normalize_cluster_name(cluster_assignment_raw)
        if not target_cluster:
            target_cluster = None
    # Prompt set opcional para todo el lote ('core'/null → núcleo)
    set_assignment_raw = data.get('set', None)

    if not queries_list:
        return jsonify({'error': 'No se proporcionaron queries'}), 400

    if not isinstance(queries_list, list):
        return jsonify({'error': 'queries debe ser una lista'}), 400
    
    # Validar límites por plan (prompts por proyecto)
    plan_limits = _get_effective_plan_limits(user)
    max_prompts = plan_limits.get('max_prompts_per_project')

    # Obtener configuración del proyecto si no se especificó idioma
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500
    
    try:
        cur = conn.cursor()

        # Lock del proyecto para evitar carreras al añadir prompts
        cur.execute("SELECT id FROM llm_monitoring_projects WHERE id = %s FOR UPDATE", (project_id,))

        if max_prompts is not None:
            cur.execute("""
                SELECT COUNT(*) AS count
                FROM llm_monitoring_queries
                WHERE project_id = %s AND is_active = TRUE
            """, (project_id,))
            row = cur.fetchone()
            current_count = int(row['count']) if row else 0
            incoming_count = len([q for q in queries_list if isinstance(q, str) and q.strip()])
            if current_count + incoming_count > max_prompts:
                return jsonify({
                    'error': 'prompt_limit_exceeded',
                    'message': 'You have reached the maximum number of prompts allowed for this project',
                    'current_plan': user.get('plan', 'free'),
                    'upgrade_options': get_upgrade_options(user.get('plan', 'free')),
                    'limit': max_prompts,
                    'current': current_count,
                    'requested': incoming_count
                }), 402
        
        # Si no se especificó idioma, usar el del proyecto
        if not language:
            cur.execute("SELECT language FROM llm_monitoring_projects WHERE id = %s", (project_id,))
            project = cur.fetchone()
            if project:
                language = project['language']
            else:
                language = 'es'

        # ✨ NEW: Validate that target_cluster (if any) is defined in the project config
        if target_cluster:
            cur.execute(
                "SELECT prompt_clusters FROM llm_monitoring_projects WHERE id = %s",
                (project_id,)
            )
            project_cfg = cur.fetchone() or {}
            raw_clusters_cfg = project_cfg.get('prompt_clusters') or {}
            if isinstance(raw_clusters_cfg, str):
                try:
                    raw_clusters_cfg = json.loads(raw_clusters_cfg)
                except (json.JSONDecodeError, TypeError):
                    raw_clusters_cfg = {}
            defined_clusters = {
                (c.get('name') or '').lower()
                for c in (raw_clusters_cfg.get('clusters') or [])
                if isinstance(c, dict)
            }
            if target_cluster.lower() not in defined_clusters:
                # Silently ignore unknown cluster rather than failing the whole batch
                logger.warning(
                    f"Cluster '{target_cluster}' not defined for project {project_id} — ignoring"
                )
                target_cluster = None

        # Resolver set del lote (mismo criterio tolerante que el cluster:
        # un set desconocido se ignora, no rompe el lote entero)
        target_set = None
        if set_assignment_raw is not None and set_assignment_raw != '':
            sets_cfg = _load_sets_config(cur, project_id)
            ok, resolved = _resolve_set_assignment(set_assignment_raw, sets_cfg or {})
            if ok:
                target_set = resolved
            else:
                logger.warning(
                    f"Set '{set_assignment_raw}' not defined for project {project_id} — ignoring"
                )

        added_count = 0
        reactivated_count = 0
        duplicate_count = 0
        error_count = 0

        for query_text in queries_list:
            query_text = query_text.strip()
            if not query_text:
                error_count += 1
                continue

            try:
                # El borrado de prompts es "soft" (is_active = FALSE) y la fila
                # sigue ocupando el UNIQUE (project_id, query_text). Un prompt
                # borrado y vuelto a añadir se REACTIVA con los valores del lote
                # (idioma, tipo, cluster, set) conservando su id y, por tanto, su
                # histórico. Solo cuenta como duplicado si ya está activo:
                # con DO UPDATE ... WHERE, rowcount es 0 cuando la guarda falla.
                cur.execute("""
                    INSERT INTO llm_monitoring_queries (
                        project_id, query_text, language, query_type, topic_cluster, prompt_set, is_active, added_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, TRUE, NOW())
                    ON CONFLICT (project_id, query_text) DO UPDATE SET
                        is_active = TRUE,
                        language = EXCLUDED.language,
                        query_type = EXCLUDED.query_type,
                        topic_cluster = EXCLUDED.topic_cluster,
                        prompt_set = EXCLUDED.prompt_set,
                        added_at = NOW()
                    WHERE llm_monitoring_queries.is_active = FALSE
                    RETURNING (xmax = 0) AS inserted
                """, (project_id, query_text, language, query_type, target_cluster, target_set))

                if cur.rowcount > 0:
                    added_count += 1
                    row = cur.fetchone()
                    if row is not None and not row['inserted']:
                        reactivated_count += 1
                else:
                    duplicate_count += 1

            except Exception as e:
                logger.warning(f"Error añadiendo query '{query_text}': {e}")
                error_count += 1
                continue
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'added_count': added_count,
            'reactivated_count': reactivated_count,
            'duplicate_count': duplicate_count,
            'error_count': error_count,
            'message': f'{added_count} prompts added successfully'
        }), 200
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error añadiendo queries: {e}", exc_info=True)
        return jsonify({'error': 'Failed to add prompts. Please try again.'}), 500
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/projects/<int:project_id>/queries/<int:query_id>', methods=['DELETE'])
@login_required
@validate_project_ownership
def delete_query(project_id, query_id):
    """
    Elimina una query de un proyecto (soft delete: marca is_active = false)
    
    Returns:
        JSON con confirmación
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500
    
    try:
        cur = conn.cursor()
        
        # Verificar que la query pertenece al proyecto
        cur.execute("""
            SELECT id, query_text
            FROM llm_monitoring_queries
            WHERE id = %s AND project_id = %s
        """, (query_id, project_id))
        
        query = cur.fetchone()
        
        if not query:
            return jsonify({'error': 'Prompt not found'}), 404
        
        # Soft delete
        cur.execute("""
            UPDATE llm_monitoring_queries
            SET is_active = FALSE
            WHERE id = %s AND project_id = %s
            RETURNING id
        """, (query_id, project_id))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Query eliminada exitosamente',
            'query_id': query_id
        }), 200
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error eliminando query: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        cur.close()
        conn.close()


# ============================================================================
# PROMPT CLUSTERS (topic clustering manual)
# ============================================================================


def _sanitize_prompt_clusters_config(raw):
    """
    Sanitize incoming clusters config. Expected shape:
        {"enabled": bool, "clusters": [{"name": "..."}]}
    Returns (config_dict, list_of_names_in_order).
    Raises ValueError on invalid input.
    """
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError('clusters_config must be an object')

    enabled = bool(raw.get('enabled'))
    clusters_in = raw.get('clusters') or []
    if not isinstance(clusters_in, list):
        raise ValueError('clusters must be a list')

    seen = set()
    cleaned = []
    names_in_order = []
    for entry in clusters_in:
        if isinstance(entry, str):
            name = _normalize_cluster_name(entry)
        elif isinstance(entry, dict):
            name = _normalize_cluster_name(entry.get('name'))
        else:
            continue
        if not name:
            continue
        # case-insensitive uniqueness
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append({'name': name})
        names_in_order.append(name)

    return (
        {'enabled': enabled and len(cleaned) > 0, 'clusters': cleaned},
        names_in_order,
    )


@llm_monitoring_bp.route('/projects/<int:project_id>/clusters', methods=['GET'])
@login_required
@validate_project_ownership
def get_project_clusters(project_id):
    """
    Devuelve la configuración de clusters del proyecto + conteo de prompts por cluster.

    Returns:
        {
            "success": true,
            "clusters_config": {"enabled": bool, "clusters": [{"name": "..."}]},
            "counts": {"ClusterA": 5, "Unassigned": 2, ...}
        }
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500

    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT prompt_clusters
            FROM llm_monitoring_projects
            WHERE id = %s
        """, (project_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'Project not found'}), 404

        raw_config = row.get('prompt_clusters') or {'enabled': False, 'clusters': []}
        if isinstance(raw_config, str):
            try:
                raw_config = json.loads(raw_config)
            except (json.JSONDecodeError, TypeError):
                raw_config = {'enabled': False, 'clusters': []}

        # Conteo de prompts activos por cluster
        cur.execute("""
            SELECT COALESCE(topic_cluster, '') AS cluster, COUNT(*) AS cnt
            FROM llm_monitoring_queries
            WHERE project_id = %s AND is_active = TRUE
            GROUP BY COALESCE(topic_cluster, '')
        """, (project_id,))
        counts = {}
        for r in cur.fetchall():
            key = r['cluster'] if r['cluster'] else 'Unassigned'
            counts[key] = int(r['cnt'])

        return jsonify({
            'success': True,
            'clusters_config': raw_config,
            'counts': counts
        }), 200

    except Exception as e:
        logger.error(f"Error obteniendo clusters: {e}", exc_info=True)
        return jsonify({'error': 'Failed to load clusters. Please try again.'}), 500
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/projects/<int:project_id>/clusters', methods=['PUT'])
@login_required
@validate_project_ownership
def update_project_clusters(project_id):
    """
    Actualiza la configuración de clusters del proyecto.

    Body:
        {"clusters_config": {"enabled": bool, "clusters": [{"name": "..."}]}}

    Comportamiento:
    - Guarda el nuevo array canónico en llm_monitoring_projects.prompt_clusters.
    - Si un cluster ha sido ELIMINADO (o si se deshabilita la feature),
      todos los queries con ese topic_cluster se ponen a NULL (desasignados).
    - No renombra clusters automáticamente: usa el endpoint /clusters/rename para eso.
    """
    data = request.get_json() or {}
    raw_config = data.get('clusters_config')
    if raw_config is None:
        return jsonify({'error': 'clusters_config is required'}), 400

    try:
        sanitized, names_in_order = _sanitize_prompt_clusters_config(raw_config)
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500

    try:
        cur = conn.cursor()

        # Lock del proyecto para evitar carreras
        cur.execute(
            "SELECT prompt_clusters FROM llm_monitoring_projects WHERE id = %s FOR UPDATE",
            (project_id,)
        )
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'Project not found'}), 404

        # Guardar nueva config
        cur.execute("""
            UPDATE llm_monitoring_projects
            SET prompt_clusters = %s::jsonb, updated_at = NOW()
            WHERE id = %s
        """, (json.dumps(sanitized), project_id))

        # Desasignar cluster de queries cuyo cluster ya no exista (o si se desactiva)
        if not sanitized['enabled'] or not names_in_order:
            cur.execute("""
                UPDATE llm_monitoring_queries
                SET topic_cluster = NULL
                WHERE project_id = %s AND topic_cluster IS NOT NULL
            """, (project_id,))
            orphaned = cur.rowcount
        else:
            cur.execute("""
                UPDATE llm_monitoring_queries
                SET topic_cluster = NULL
                WHERE project_id = %s
                  AND topic_cluster IS NOT NULL
                  AND NOT (topic_cluster = ANY(%s))
            """, (project_id, names_in_order))
            orphaned = cur.rowcount

        conn.commit()

        return jsonify({
            'success': True,
            'clusters_config': sanitized,
            'orphaned_prompts': orphaned
        }), 200

    except Exception as e:
        conn.rollback()
        logger.error(f"Error actualizando clusters: {e}", exc_info=True)
        return jsonify({'error': 'Failed to save clusters. Please try again.'}), 500
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/projects/<int:project_id>/clusters/rename', methods=['POST'])
@login_required
@validate_project_ownership
def rename_project_cluster(project_id):
    """
    Renombra un cluster: actualiza la config del proyecto y todos los prompts asignados.

    Body: {"old_name": "...", "new_name": "..."}
    """
    data = request.get_json() or {}
    old_name = _normalize_cluster_name(data.get('old_name'))
    new_name = _normalize_cluster_name(data.get('new_name'))

    if not old_name or not new_name:
        return jsonify({'error': 'old_name and new_name are required'}), 400
    if old_name == new_name:
        return jsonify({'success': True, 'updated_prompts': 0}), 200

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500

    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT prompt_clusters FROM llm_monitoring_projects WHERE id = %s FOR UPDATE",
            (project_id,)
        )
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'Project not found'}), 404

        raw_config = row.get('prompt_clusters') or {'enabled': False, 'clusters': []}
        if isinstance(raw_config, str):
            try:
                raw_config = json.loads(raw_config)
            except (json.JSONDecodeError, TypeError):
                raw_config = {'enabled': False, 'clusters': []}

        clusters_list = raw_config.get('clusters') or []
        existing_names_lower = {c.get('name', '').lower() for c in clusters_list if isinstance(c, dict)}

        if old_name.lower() not in existing_names_lower:
            return jsonify({'error': f"Cluster '{old_name}' not found"}), 404
        if new_name.lower() in existing_names_lower and new_name.lower() != old_name.lower():
            return jsonify({'error': f"A cluster named '{new_name}' already exists"}), 409

        # Actualizar config
        renamed_list = []
        for c in clusters_list:
            if not isinstance(c, dict):
                continue
            if c.get('name', '').lower() == old_name.lower():
                renamed_list.append({'name': new_name})
            else:
                renamed_list.append({'name': c.get('name')})
        raw_config['clusters'] = renamed_list
        raw_config['enabled'] = bool(raw_config.get('enabled')) and len(renamed_list) > 0

        cur.execute("""
            UPDATE llm_monitoring_projects
            SET prompt_clusters = %s::jsonb, updated_at = NOW()
            WHERE id = %s
        """, (json.dumps(raw_config), project_id))

        # Actualizar queries asignados
        cur.execute("""
            UPDATE llm_monitoring_queries
            SET topic_cluster = %s
            WHERE project_id = %s AND topic_cluster = %s
        """, (new_name, project_id, old_name))
        updated = cur.rowcount

        conn.commit()
        return jsonify({
            'success': True,
            'clusters_config': raw_config,
            'updated_prompts': updated
        }), 200

    except Exception as e:
        conn.rollback()
        logger.error(f"Error renombrando cluster: {e}", exc_info=True)
        return jsonify({'error': 'Failed to rename cluster. Please try again.'}), 500
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/projects/<int:project_id>/queries/<int:query_id>/cluster', methods=['PUT'])
@login_required
@validate_project_ownership
def assign_query_cluster(project_id, query_id):
    """
    Asigna (o desasigna) un cluster a un prompt concreto.

    Body: {"cluster": "NombreCluster"}  o  {"cluster": null}  para desasignar.

    Validaciones:
    - El cluster debe existir en prompt_clusters del proyecto (o ser null).
    """
    data = request.get_json() or {}
    requested = data.get('cluster', None)
    # Permitir null/"" para desasignar
    if requested is None or requested == '':
        target_cluster = None
    else:
        target_cluster = _normalize_cluster_name(requested)
        if not target_cluster:
            return jsonify({'error': 'Invalid cluster name'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500

    try:
        cur = conn.cursor()

        cur.execute(
            "SELECT prompt_clusters FROM llm_monitoring_projects WHERE id = %s",
            (project_id,)
        )
        project_row = cur.fetchone()
        if not project_row:
            return jsonify({'error': 'Project not found'}), 404

        # Validar que el cluster exista en la config (si se está asignando)
        if target_cluster is not None:
            raw_config = project_row.get('prompt_clusters') or {}
            if isinstance(raw_config, str):
                try:
                    raw_config = json.loads(raw_config)
                except (json.JSONDecodeError, TypeError):
                    raw_config = {}
            cluster_names = {
                (c.get('name') or '').lower()
                for c in (raw_config.get('clusters') or [])
                if isinstance(c, dict)
            }
            if target_cluster.lower() not in cluster_names:
                return jsonify({
                    'error': f"Cluster '{target_cluster}' is not defined for this project"
                }), 400

        cur.execute("""
            UPDATE llm_monitoring_queries
            SET topic_cluster = %s
            WHERE id = %s AND project_id = %s
            RETURNING id, topic_cluster
        """, (target_cluster, query_id, project_id))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'Prompt not found'}), 404

        conn.commit()
        return jsonify({
            'success': True,
            'query_id': row['id'],
            'topic_cluster': row['topic_cluster']
        }), 200

    except Exception as e:
        conn.rollback()
        logger.error(f"Error asignando cluster a query: {e}", exc_info=True)
        return jsonify({'error': 'Failed to assign cluster. Please try again.'}), 500
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/projects/<int:project_id>/queries/bulk-cluster', methods=['POST'])
@login_required
@validate_project_ownership
def bulk_assign_cluster(project_id):
    """
    Asigna (o desasigna) un mismo cluster a varios prompts en una sola llamada.

    Body: {"query_ids": [1,2,3], "cluster": "NombreCluster" | null}
    """
    data = request.get_json() or {}
    query_ids = data.get('query_ids') or []
    if not isinstance(query_ids, list) or not query_ids:
        return jsonify({'error': 'query_ids must be a non-empty list'}), 400
    # Sanity cap
    query_ids = [int(q) for q in query_ids if isinstance(q, (int, str)) and str(q).isdigit()][:500]
    if not query_ids:
        return jsonify({'error': 'query_ids must contain integer IDs'}), 400

    requested = data.get('cluster', None)
    if requested is None or requested == '':
        target_cluster = None
    else:
        target_cluster = _normalize_cluster_name(requested)
        if not target_cluster:
            return jsonify({'error': 'Invalid cluster name'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500

    try:
        cur = conn.cursor()

        cur.execute(
            "SELECT prompt_clusters FROM llm_monitoring_projects WHERE id = %s",
            (project_id,)
        )
        project_row = cur.fetchone()
        if not project_row:
            return jsonify({'error': 'Project not found'}), 404

        if target_cluster is not None:
            raw_config = project_row.get('prompt_clusters') or {}
            if isinstance(raw_config, str):
                try:
                    raw_config = json.loads(raw_config)
                except (json.JSONDecodeError, TypeError):
                    raw_config = {}
            cluster_names = {
                (c.get('name') or '').lower()
                for c in (raw_config.get('clusters') or [])
                if isinstance(c, dict)
            }
            if target_cluster.lower() not in cluster_names:
                return jsonify({
                    'error': f"Cluster '{target_cluster}' is not defined for this project"
                }), 400

        cur.execute("""
            UPDATE llm_monitoring_queries
            SET topic_cluster = %s
            WHERE project_id = %s AND id = ANY(%s)
        """, (target_cluster, project_id, query_ids))
        updated = cur.rowcount

        conn.commit()
        return jsonify({
            'success': True,
            'updated': updated,
            'topic_cluster': target_cluster
        }), 200

    except Exception as e:
        conn.rollback()
        logger.error(f"Error en bulk-cluster: {e}", exc_info=True)
        return jsonify({'error': 'Failed to update clusters. Please try again.'}), 500
    finally:
        cur.close()
        conn.close()


# ═══════════════════════════════════════════════════════════════════
# PROMPT SETS (núcleo / tendencia / estacionales)
# El set "núcleo" es implícito (prompt_set = NULL): siempre existe,
# siempre activo. Los sets adicionales viven en projects.prompt_sets
# y pueden llevar ventana estacional UTC (ver services/llm_monitoring/
# prompt_sets.py). Espejo del patrón de clusters de arriba.
# ═══════════════════════════════════════════════════════════════════

CORE_SET_KEY = 'core'


def _load_sets_config(cur, project_id, for_update=False):
    """Lee y parsea prompt_sets del proyecto. Devuelve None si el proyecto no existe."""
    lock = ' FOR UPDATE' if for_update else ''
    cur.execute(
        f"SELECT prompt_sets FROM llm_monitoring_projects WHERE id = %s{lock}",
        (project_id,)
    )
    row = cur.fetchone()
    if not row:
        return None
    return prompt_sets_lib.parse_sets_config(row.get('prompt_sets'))


def _resolve_set_assignment(requested, sets_config):
    """
    Resuelve el valor entrante de un assignment de set a valor de columna.

    'core'/None/'' → None (núcleo). Otro nombre → debe existir en la config.
    Returns (ok, value_or_error): si ok, value es None o el nombre canónico.
    """
    if requested is None or requested == '' or \
            str(requested).strip().lower() in prompt_sets_lib.RESERVED_CORE_NAMES:
        return True, None
    name = prompt_sets_lib.normalize_set_name(requested)
    if not name:
        return False, 'Invalid set name'
    defined = {n.lower(): n for n in prompt_sets_lib.get_defined_set_names(sets_config)}
    canonical = defined.get(name.lower())
    if not canonical:
        return False, f"Set '{name}' is not defined for this project"
    return True, canonical


@llm_monitoring_bp.route('/projects/<int:project_id>/sets', methods=['GET'])
@login_required
@validate_project_ownership
def get_project_sets(project_id):
    """
    Devuelve la configuración de sets del proyecto + conteo de prompts por set
    + si cada ventana está activa hoy (día UTC).

    Returns:
        {
            "success": true,
            "sets_config": {"enabled": bool, "sets": [{"name", "window"?}]},
            "counts": {"core": 59, "Black Friday": 12},
            "active_today": {"core": true, "Black Friday": false}
        }
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500

    try:
        cur = conn.cursor()
        cfg = _load_sets_config(cur, project_id)
        if cfg is None:
            return jsonify({'error': 'Project not found'}), 404

        cur.execute("""
            SELECT COALESCE(prompt_set, %s) AS set_name, COUNT(*) AS cnt
            FROM llm_monitoring_queries
            WHERE project_id = %s AND is_active = TRUE
            GROUP BY COALESCE(prompt_set, %s)
        """, (CORE_SET_KEY, project_id, CORE_SET_KEY))
        counts = {r['set_name']: int(r['cnt']) for r in cur.fetchall()}

        active_today = {CORE_SET_KEY: True}
        for entry in (cfg.get('sets') or []):
            if isinstance(entry, dict) and entry.get('name'):
                active_today[entry['name']] = prompt_sets_lib.is_window_active(
                    entry.get('window')
                )

        # enabled_llms viaja aquí porque la barra de filtros global se pinta
        # ANTES de que el detalle del proyecto esté cargado.
        cur.execute(
            "SELECT enabled_llms FROM llm_monitoring_projects WHERE id = %s",
            (project_id,)
        )
        llms_row = cur.fetchone() or {}

        return jsonify({
            'success': True,
            'sets_config': cfg,
            'counts': counts,
            'active_today': active_today,
            'enabled_llms': llms_row.get('enabled_llms') or []
        }), 200

    except Exception as e:
        logger.error(f"Error obteniendo sets: {e}", exc_info=True)
        return jsonify({'error': 'Failed to load sets. Please try again.'}), 500
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/projects/<int:project_id>/sets', methods=['PUT'])
@login_required
@validate_project_ownership
def update_project_sets(project_id):
    """
    Actualiza la configuración de sets del proyecto.

    Body:
        {"sets_config": {"enabled": bool,
                         "sets": [{"name": "...", "window": {"start": "MM-DD", "end": "MM-DD"}|null}]}}

    Comportamiento (espejo de clusters):
    - Guarda el array canónico en llm_monitoring_projects.prompt_sets.
    - Si un set ha sido ELIMINADO (o se deshabilita la feature), los prompts
      con ese prompt_set vuelven a NULL (núcleo) — nunca se borran prompts.
    """
    data = request.get_json() or {}
    raw_config = data.get('sets_config')
    if raw_config is None:
        return jsonify({'error': 'sets_config is required'}), 400

    try:
        sanitized, names_in_order = prompt_sets_lib.sanitize_prompt_sets_config(raw_config)
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500

    try:
        cur = conn.cursor()

        if _load_sets_config(cur, project_id, for_update=True) is None:
            return jsonify({'error': 'Project not found'}), 404

        cur.execute("""
            UPDATE llm_monitoring_projects
            SET prompt_sets = %s::jsonb, updated_at = NOW()
            WHERE id = %s
        """, (json.dumps(sanitized), project_id))

        # Prompts de sets eliminados (o feature deshabilitada) → núcleo
        if not sanitized['enabled'] or not names_in_order:
            cur.execute("""
                UPDATE llm_monitoring_queries
                SET prompt_set = NULL
                WHERE project_id = %s AND prompt_set IS NOT NULL
            """, (project_id,))
            reassigned = cur.rowcount
        else:
            cur.execute("""
                UPDATE llm_monitoring_queries
                SET prompt_set = NULL
                WHERE project_id = %s
                  AND prompt_set IS NOT NULL
                  AND NOT (prompt_set = ANY(%s))
            """, (project_id, names_in_order))
            reassigned = cur.rowcount

        conn.commit()

        return jsonify({
            'success': True,
            'sets_config': sanitized,
            'reassigned_to_core': reassigned
        }), 200

    except Exception as e:
        conn.rollback()
        logger.error(f"Error actualizando sets: {e}", exc_info=True)
        return jsonify({'error': 'Failed to save sets. Please try again.'}), 500
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/projects/<int:project_id>/sets/rename', methods=['POST'])
@login_required
@validate_project_ownership
def rename_project_set(project_id):
    """
    Renombra un set: actualiza la config del proyecto y todos los prompts asignados.

    Body: {"old_name": "...", "new_name": "..."}
    """
    data = request.get_json() or {}
    old_name = prompt_sets_lib.normalize_set_name(data.get('old_name'))
    new_name = prompt_sets_lib.normalize_set_name(data.get('new_name'))

    if not old_name or not new_name:
        return jsonify({'error': 'old_name and new_name are required'}), 400
    if new_name.lower() in prompt_sets_lib.RESERVED_CORE_NAMES:
        return jsonify({'error': f'"{new_name}" is reserved for the core set'}), 400
    if old_name == new_name:
        return jsonify({'success': True, 'updated_prompts': 0}), 200

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500

    try:
        cur = conn.cursor()
        cfg = _load_sets_config(cur, project_id, for_update=True)
        if cfg is None:
            return jsonify({'error': 'Project not found'}), 404

        sets_list = [s for s in (cfg.get('sets') or []) if isinstance(s, dict)]
        existing_lower = {s.get('name', '').lower() for s in sets_list}

        if old_name.lower() not in existing_lower:
            return jsonify({'error': f"Set '{old_name}' not found"}), 404
        if new_name.lower() in existing_lower and new_name.lower() != old_name.lower():
            return jsonify({'error': f"A set named '{new_name}' already exists"}), 409

        for s in sets_list:
            if s.get('name', '').lower() == old_name.lower():
                s['name'] = new_name
        cfg['sets'] = sets_list

        cur.execute("""
            UPDATE llm_monitoring_projects
            SET prompt_sets = %s::jsonb, updated_at = NOW()
            WHERE id = %s
        """, (json.dumps(cfg), project_id))

        cur.execute("""
            UPDATE llm_monitoring_queries
            SET prompt_set = %s
            WHERE project_id = %s AND prompt_set = %s
        """, (new_name, project_id, old_name))
        updated = cur.rowcount

        conn.commit()
        return jsonify({
            'success': True,
            'sets_config': cfg,
            'updated_prompts': updated
        }), 200

    except Exception as e:
        conn.rollback()
        logger.error(f"Error renombrando set: {e}", exc_info=True)
        return jsonify({'error': 'Failed to rename set. Please try again.'}), 500
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/projects/<int:project_id>/queries/<int:query_id>/set', methods=['PUT'])
@login_required
@validate_project_ownership
def assign_query_set(project_id, query_id):
    """
    Asigna un set a un prompt concreto.

    Body: {"set": "Black Friday"}  o  {"set": null|"core"}  para volver a núcleo.
    """
    data = request.get_json() or {}

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500

    try:
        cur = conn.cursor()
        cfg = _load_sets_config(cur, project_id)
        if cfg is None:
            return jsonify({'error': 'Project not found'}), 404

        ok, target = _resolve_set_assignment(data.get('set', None), cfg)
        if not ok:
            return jsonify({'error': target}), 400

        cur.execute("""
            UPDATE llm_monitoring_queries
            SET prompt_set = %s
            WHERE id = %s AND project_id = %s
            RETURNING id, prompt_set
        """, (target, query_id, project_id))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'Prompt not found'}), 404

        conn.commit()
        return jsonify({
            'success': True,
            'query_id': row['id'],
            'prompt_set': row['prompt_set']
        }), 200

    except Exception as e:
        conn.rollback()
        logger.error(f"Error asignando set a query: {e}", exc_info=True)
        return jsonify({'error': 'Failed to assign set. Please try again.'}), 500
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/projects/<int:project_id>/queries/bulk-set', methods=['POST'])
@login_required
@validate_project_ownership
def bulk_assign_set(project_id):
    """
    Asigna un mismo set a varios prompts en una sola llamada.

    Body: {"query_ids": [1,2,3], "set": "Black Friday" | null | "core"}
    """
    data = request.get_json() or {}
    query_ids = data.get('query_ids') or []
    if not isinstance(query_ids, list) or not query_ids:
        return jsonify({'error': 'query_ids must be a non-empty list'}), 400
    query_ids = [int(q) for q in query_ids if isinstance(q, (int, str)) and str(q).isdigit()][:500]
    if not query_ids:
        return jsonify({'error': 'query_ids must contain integer IDs'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500

    try:
        cur = conn.cursor()
        cfg = _load_sets_config(cur, project_id)
        if cfg is None:
            return jsonify({'error': 'Project not found'}), 404

        ok, target = _resolve_set_assignment(data.get('set', None), cfg)
        if not ok:
            return jsonify({'error': target}), 400

        cur.execute("""
            UPDATE llm_monitoring_queries
            SET prompt_set = %s
            WHERE project_id = %s AND id = ANY(%s)
        """, (target, project_id, query_ids))
        updated = cur.rowcount

        conn.commit()
        return jsonify({
            'success': True,
            'updated': updated,
            'prompt_set': target
        }), 200

    except Exception as e:
        conn.rollback()
        logger.error(f"Error en bulk-set: {e}", exc_info=True)
        return jsonify({'error': 'Failed to update sets. Please try again.'}), 500
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/projects/<int:project_id>/clusters/metrics', methods=['GET'])
@login_required
@validate_project_ownership
def get_clusters_metrics(project_id):
    """
    Devuelve métricas agregadas por cluster (Share of Voice + Avg Position)
    para el gráfico de barras que sustituye a "LLM Comparison".

    Query params:
        - days: ventana temporal (default 30)
        - metric: "weighted" | "classic"  (default "weighted")

    Excluye prompts sin cluster (topic_cluster IS NULL).
    Los cálculos se hacen on-the-fly a partir de llm_monitoring_results.
    """
    days = _normalize_days_param(request.args.get('days'), default=30)
    metric = (request.args.get('metric') or 'weighted').lower()
    if metric not in ('weighted', 'classic'):
        metric = 'weighted'
    # Aplica set/branded/llms; el filtro de clusters se ignora aquí a propósito
    # (este endpoint ya desglosa por cluster)
    report_filters = _parse_report_filters(request.args)

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500

    try:
        cur = conn.cursor()

        cur.execute("""
            SELECT prompt_clusters, enabled_llms
            FROM llm_monitoring_projects
            WHERE id = %s
        """, (project_id,))
        project = cur.fetchone()
        if not project:
            return jsonify({'error': 'Project not found'}), 404

        raw_config = project.get('prompt_clusters') or {}
        if isinstance(raw_config, str):
            try:
                raw_config = json.loads(raw_config)
            except (json.JSONDecodeError, TypeError):
                raw_config = {}
        enabled = bool(raw_config.get('enabled'))
        defined_clusters = [
            c.get('name') for c in (raw_config.get('clusters') or [])
            if isinstance(c, dict) and c.get('name')
        ]
        enabled_llms = _narrow_llms(project.get('enabled_llms') or [], report_filters)

        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)

        # Pull per-result rows (only for prompts with cluster assigned)
        filtered_query_ids = _resolve_filtered_query_ids(
            cur, project_id, report_filters, include_clusters=False,
            start_date=start_date, end_date=end_date
        )
        params = [project_id, start_date, end_date]
        ids_filter = ''
        if filtered_query_ids is not None:
            ids_filter = 'AND r.query_id = ANY(%s)'
            params.append(filtered_query_ids)
        llm_filter = ''
        if enabled_llms:
            llm_filter = 'AND r.llm_provider = ANY(%s)'
            params.append(enabled_llms)

        cur.execute(f"""
            SELECT
                q.topic_cluster AS cluster,
                r.brand_mentioned,
                r.position_in_list,
                r.competitors_mentioned
            FROM llm_monitoring_results r
            JOIN llm_monitoring_queries q ON q.id = r.query_id
            WHERE r.project_id = %s
              AND r.analysis_date >= %s
              AND r.analysis_date <= %s
              AND q.topic_cluster IS NOT NULL
              {ids_filter}
              {llm_filter}
        """, params)
        rows = cur.fetchall() or []

        MAX_POSITION = 30

        # Init buckets for every defined cluster so the chart still shows them
        # as empty bars (0) instead of being missing.
        buckets = {
            name: {
                'total_results': 0,
                'brand_mentions': 0,
                'competitor_mentions': 0,
                'weighted_brand': 0.0,
                'weighted_competitors': 0.0,
                'positions': []
            }
            for name in defined_clusters
        }

        for r in rows:
            cluster = r.get('cluster')
            if not cluster or cluster not in buckets:
                continue
            b = buckets[cluster]
            b['total_results'] += 1
            position = r.get('position_in_list')

            # Brand contribution
            if r.get('brand_mentioned'):
                b['brand_mentions'] += 1
                b['weighted_brand'] += _weight_for_position(position)

            # Competitor contribution
            cm = r.get('competitors_mentioned') or {}
            if isinstance(cm, str):
                try:
                    cm = json.loads(cm)
                except (json.JSONDecodeError, TypeError):
                    cm = {}
            if isinstance(cm, dict):
                for _comp, count in cm.items():
                    try:
                        count_int = int(count)
                    except (TypeError, ValueError):
                        continue
                    if count_int > 0:
                        b['competitor_mentions'] += 1
                        b['weighted_competitors'] += _weight_for_position(position)

            # Positions (filtered)
            if position is not None and position <= MAX_POSITION:
                b['positions'].append(position)

        clusters_out = []
        for name in defined_clusters:
            b = buckets[name]
            if metric == 'weighted':
                denom = b['weighted_brand'] + b['weighted_competitors']
                sov = round((b['weighted_brand'] / denom) * 100, 1) if denom > 0 else 0.0
            else:
                denom = b['brand_mentions'] + b['competitor_mentions']
                sov = round((b['brand_mentions'] / denom) * 100, 1) if denom > 0 else 0.0

            avg_pos = None
            if b['positions']:
                avg_pos = round(sum(b['positions']) / len(b['positions']), 1)

            clusters_out.append({
                'cluster': name,
                'total_results': b['total_results'],
                'brand_mentions': b['brand_mentions'],
                'competitor_mentions': b['competitor_mentions'],
                'share_of_voice': sov,
                'avg_position': avg_pos,
                'has_data': b['total_results'] > 0
            })

        # Sort: clusters with data first (by SoV desc), then empty clusters
        clusters_out.sort(
            key=lambda c: (
                -1 if c['has_data'] else 1,
                -(c['share_of_voice'] or 0),
                c['cluster']
            )
        )

        return jsonify({
            'success': True,
            'enabled': enabled,
            'metric': metric,
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': days
            },
            'clusters': clusters_out,
            'total_clusters_defined': len(defined_clusters)
        }), 200

    except Exception as e:
        logger.error(f"Error calculando métricas de clusters: {e}", exc_info=True)
        return jsonify({'error': 'Failed to compute cluster metrics. Please try again.'}), 500
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/projects/<int:project_id>/queries/<int:query_id>/history', methods=['GET'])
@login_required
@validate_project_ownership
def get_query_history(project_id, query_id):
    """
    ✨ NUEVO: Obtiene el historial de visibilidad de un prompt/query específico
    para mostrar la evolución temporal en una gráfica.
    
    Query params:
        - days: Número de días de historial (default: 30, usa el time range global)
    
    Returns:
        JSON con historial de menciones por fecha y LLM
    """
    # ✨ Obtener parámetro days del time range global (normalizado como el resto)
    days = _normalize_days_param(request.args.get('days'), default=30)
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500
    
    cur = None
    try:
        cur = conn.cursor()
        
        # Verificar que la query pertenece al proyecto
        cur.execute("""
            SELECT q.id, q.query_text, p.enabled_llms
            FROM llm_monitoring_queries q
            JOIN llm_monitoring_projects p ON q.project_id = p.id
            WHERE q.id = %s AND q.project_id = %s
        """, (query_id, project_id))
        
        query = cur.fetchone()
        
        if not query:
            return jsonify({'error': 'Prompt not found', 'success': False}), 404
        
        logger.info(f"📊 Fetching history for query {query_id} ('{query['query_text'][:30]}...') - last {days} days")
        
        # Obtener historial de resultados para esta query
        enabled_llms_filter = query.get('enabled_llms') or []
        history_query = """
            SELECT
                analysis_date,
                llm_provider,
                brand_mentioned,
                position_in_list,
                sentiment
            FROM llm_monitoring_results
            WHERE query_id = %s AND project_id = %s
                AND analysis_date >= CURRENT_DATE - (%s * INTERVAL '1 day')
        """
        history_params = [query_id, project_id, days]
        if enabled_llms_filter:
            history_query += " AND llm_provider = ANY(%s)"
            history_params.append(enabled_llms_filter)
        history_query += " ORDER BY analysis_date ASC, llm_provider"
        cur.execute(history_query, history_params)
        
        results = cur.fetchall()
        
        logger.info(f"   → Found {len(results)} result records")
        
        # Si no hay resultados, retornar lista vacía con éxito
        if not results:
            return jsonify({
                'success': True,
                'query_id': query_id,
                'query_text': query['query_text'],
                'history': [],
                'llm_providers': [],
                'total_data_points': 0,
                'days': days,
                'message': 'No historical data found for this query in the selected period'
            }), 200
        
        # Agrupar resultados por fecha
        history_by_date = {}
        llm_providers_set = set()
        
        for row in results:
            date_str = row['analysis_date'].isoformat() if row['analysis_date'] else None
            if not date_str:
                continue
                
            llm = row['llm_provider']
            llm_providers_set.add(llm)
            
            if date_str not in history_by_date:
                history_by_date[date_str] = {
                    'date': date_str,
                    'total_llms': 0,
                    'llms_mentioned': 0,
                    'visibility_rate': 0,
                    'by_llm': {}
                }
            
            history_by_date[date_str]['total_llms'] += 1
            if row['brand_mentioned']:
                history_by_date[date_str]['llms_mentioned'] += 1
            
            history_by_date[date_str]['by_llm'][llm] = {
                'mentioned': row['brand_mentioned'] or False,
                'position': row['position_in_list'],
                'sentiment': row['sentiment']
            }
        
        # Calcular visibility_rate por fecha
        for date_str, data in history_by_date.items():
            if data['total_llms'] > 0:
                data['visibility_rate'] = round(
                    (data['llms_mentioned'] / data['total_llms']) * 100, 1
                )
        
        # Convertir a lista ordenada por fecha
        history_list = sorted(
            list(history_by_date.values()),
            key=lambda x: x['date']
        )
        
        # Obtener lista de LLMs únicos para la leyenda del gráfico
        llm_providers = sorted(list(llm_providers_set))
        
        logger.info(f"   ✅ Returning {len(history_list)} data points for {len(llm_providers)} LLMs")
        
        return jsonify({
            'success': True,
            'query_id': query_id,
            'query_text': query['query_text'],
            'history': history_list,
            'llm_providers': llm_providers,
            'total_data_points': len(history_list),
            'days': days
        }), 200
        
    except Exception as e:
        logger.error(f"Error obteniendo historial de query: {e}", exc_info=True)
        return jsonify({'error': 'Failed to load data. Please try again.', 'success': False}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@llm_monitoring_bp.route('/projects/<int:project_id>/queries/suggest', methods=['POST'])
@login_required
@validate_project_ownership
def suggest_queries(project_id):
    """
    Genera sugerencias de queries usando IA (Gemini Flash)
    
    Analiza los prompts existentes del proyecto y el contexto (marca, industria)
    para sugerir prompts adicionales relevantes usando Gemini Flash.
    
    Body opcional:
    {
        "count": 10  (número de sugerencias, default: 10, max: 20)
    }
    
    Returns:
        JSON con lista de sugerencias generadas por IA
    """
    user = get_current_user()
    
    data = request.get_json() or {}
    count = min(data.get('count', 10), 20)  # Máximo 20 sugerencias
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500
    cur = None
    try:
        cur = conn.cursor()

        # Obtener datos del proyecto
        cur.execute("""
            SELECT name, brand_name, industry, language, competitors
            FROM llm_monitoring_projects
            WHERE id = %s
        """, (project_id,))
        
        project = cur.fetchone()
        
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        # Obtener queries existentes
        cur.execute("""
            SELECT query_text
            FROM llm_monitoring_queries
            WHERE project_id = %s AND is_active = TRUE
            ORDER BY added_at DESC
            LIMIT 20
        """, (project_id,))
        
        existing_queries = cur.fetchall()
        existing_queries_list = [q['query_text'] for q in existing_queries]

        # Generar sugerencias usando IA
        from services.llm_monitoring_service import generate_query_suggestions_with_ai
        
        logger.info(f"🤖 Generando sugerencias para proyecto {project_id}: {project['brand_name']}")
        logger.info(f"   - Industria: {project['industry']}")
        logger.info(f"   - Queries existentes: {len(existing_queries_list)}")
        logger.info(f"   - Competidores: {project['competitors']}")
        
        suggestions = generate_query_suggestions_with_ai(
            brand_name=project['brand_name'],
            industry=project['industry'],
            language=project['language'],
            existing_queries=existing_queries_list,
            competitors=project['competitors'] or [],
            count=count
        )
        
        if not suggestions:
            logger.warning(f"⚠️ No se generaron sugerencias para proyecto {project_id}")
            # Verificar si es por falta de API key
            import os
            if not os.getenv('GOOGLE_API_KEY'):
                return jsonify({
                    'success': False,
                    'error': 'GOOGLE_API_KEY is not configured on the server',
                    'hint': 'Contacta al administrador para configurar las API keys'
                }), 500
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to generate suggestions. The Gemini API may be experiencing issues.',
                    'hint': 'Intenta de nuevo en unos momentos'
                }), 500
        
        return jsonify({
            'success': True,
            'suggestions': suggestions,
            'count': len(suggestions),
            'message': f'{len(suggestions)} sugerencias generadas por IA'
        }), 200
        
    except Exception as e:
        logger.error(f"Error generando sugerencias: {e}", exc_info=True)
        return jsonify({
            'error': 'Internal server error',
            'hint': 'Verifica que GOOGLE_API_KEY esté configurada'
        }), 500
    finally:
        try:
            cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


@llm_monitoring_bp.route('/projects/<int:project_id>/queries/suggest-variations', methods=['POST'])
@login_required
@validate_project_ownership
def suggest_query_variations(project_id):
    """
    ✨ NUEVO: Genera variaciones rápidas de prompts existentes usando IA
    
    Body:
    {
        "existing_prompts": ["prompt1", "prompt2"],
        "count": 6
    }
    
    Returns:
        JSON con lista de variaciones sugeridas
    """
    data = request.get_json() or {}
    existing_prompts = data.get('existing_prompts', [])
    count = min(data.get('count', 6), 10)
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500
    
    try:
        cur = conn.cursor()
        
        # Obtener datos del proyecto
        cur.execute("""
            SELECT brand_name, industry, language, competitors
            FROM llm_monitoring_projects
            WHERE id = %s
        """, (project_id,))
        
        project = cur.fetchone()
        
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        cur.close()
        conn.close()
        
        brand_name = project['brand_name']
        industry = project['industry'] or 'general'
        competitors = project['competitors'] or []
        
        language = (project['language'] or 'en').lower()

        # Intentar generar con IA usando el provider configurado en BD (sin modelo hardcodeado)
        try:
            from services.llm_monitoring_service import generate_query_suggestions_with_ai

            suggestions = generate_query_suggestions_with_ai(
                brand_name=brand_name,
                industry=industry,
                language=language,
                existing_queries=existing_prompts,
                competitors=competitors,
                count=count
            )
            if suggestions:
                return jsonify({
                    'success': True,
                    'suggestions': suggestions,
                    'source': 'ai'
                }), 200

        except Exception as ai_error:
            logger.warning(f"AI generation failed, using fallback: {ai_error}")
        
        # Fallback: Generate simple variations locally with randomization
        import random
        
        competitor_fallback = {
            'es': 'competidores',
            'it': 'concorrenti',
            'fr': 'concurrents',
            'de': 'Wettbewerber',
            'pt': 'concorrentes',
        }
        comp_name = competitors[0] if competitors else competitor_fallback.get(language, 'competitors')
        
        if language == 'es':
            all_variations = [
                f"¿Qué es {brand_name} y cómo funciona?",
                f"Mejores herramientas de {industry}",
                f"{brand_name} vs {comp_name} comparativa",
                f"¿Vale la pena {brand_name}? Opiniones",
                f"Alternativas a {brand_name}",
                f"Cómo empezar con {brand_name}",
                f"Precios y planes de {brand_name}",
                f"Las mejores soluciones de {industry}",
                f"Opiniones sobre {brand_name}",
                f"¿Qué opinan de {brand_name}?",
                f"Ventajas y desventajas de {brand_name}",
                f"¿Recomiendan {brand_name}?",
                f"Tutorial de {brand_name}",
                f"Características de {brand_name}",
                f"¿Es bueno {brand_name}?",
                f"Empresas que usan {brand_name}",
                f"Comparativa de {industry}",
                f"Top {industry} en 2024",
                f"¿Cuál es mejor {brand_name} o {comp_name}?",
                f"Experiencias con {brand_name}"
            ]
        elif language == 'it':
            all_variations = [
                f"Cos'è {brand_name} e come funziona?",
                f"Migliori strumenti di {industry}",
                f"Confronto {brand_name} vs {comp_name}",
                f"{brand_name} vale la pena? Recensioni",
                f"Alternative a {brand_name}",
                f"Come iniziare con {brand_name}",
                f"Prezzi e piani di {brand_name}",
                f"Opinioni su {brand_name}",
                f"Pro e contro di {brand_name}",
                f"{brand_name} per principianti"
            ]
        elif language == 'fr':
            all_variations = [
                f"Qu'est-ce que {brand_name} et comment ça marche ?",
                f"Meilleurs outils de {industry}",
                f"Comparatif {brand_name} vs {comp_name}",
                f"{brand_name} vaut-il le coup ? Avis",
                f"Alternatives à {brand_name}",
                f"Comment démarrer avec {brand_name}",
                f"Tarifs et offres de {brand_name}",
                f"Avis sur {brand_name}",
                f"Avantages et inconvénients de {brand_name}",
                f"{brand_name} pour débutants"
            ]
        elif language == 'de':
            all_variations = [
                f"Was ist {brand_name} und wie funktioniert es?",
                f"Beste {industry}-Tools",
                f"{brand_name} vs {comp_name} Vergleich",
                f"Lohnt sich {brand_name}? Erfahrungen",
                f"Alternativen zu {brand_name}",
                f"Wie startet man mit {brand_name}?",
                f"Preise und Pakete von {brand_name}",
                f"Bewertungen zu {brand_name}",
                f"Vor- und Nachteile von {brand_name}",
                f"{brand_name} für Einsteiger"
            ]
        elif language == 'pt':
            all_variations = [
                f"O que é {brand_name} e como funciona?",
                f"Melhores ferramentas de {industry}",
                f"Comparativo {brand_name} vs {comp_name}",
                f"{brand_name} vale a pena? Avaliações",
                f"Alternativas ao {brand_name}",
                f"Como começar com {brand_name}",
                f"Preços e planos do {brand_name}",
                f"Opiniões sobre {brand_name}",
                f"Prós e contras do {brand_name}",
                f"{brand_name} para iniciantes"
            ]
        else:
            all_variations = [
                f"What is {brand_name} and how does it work?",
                f"Best {industry} tools and platforms",
                f"{brand_name} vs {comp_name} comparison",
                f"Is {brand_name} worth it? Reviews",
                f"Alternatives to {brand_name}",
                f"How to get started with {brand_name}",
                f"{brand_name} pricing and plans",
                f"Top rated {industry} solutions",
                f"{brand_name} reviews and opinions",
                f"Pros and cons of {brand_name}",
                f"Would you recommend {brand_name}?",
                f"{brand_name} tutorial",
                f"{brand_name} features",
                f"Is {brand_name} good?",
                f"Companies using {brand_name}",
                f"Best {industry} comparison",
                f"Top {industry} in 2024",
                f"Which is better {brand_name} or {comp_name}?",
                f"User experiences with {brand_name}",
                f"{brand_name} for beginners"
            ]
        
        # Shuffle and pick random variations
        random.shuffle(all_variations)
        variations = all_variations
        
        # Filter out existing prompts
        existing_lower = [p.lower() for p in existing_prompts]
        suggestions = [v for v in variations if v.lower() not in existing_lower][:count]
        
        return jsonify({
            'success': True,
            'suggestions': suggestions,
            'source': 'fallback'
        }), 200
        
    except Exception as e:
        logger.error(f"Error generating variations: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error', 'success': False}), 500
    finally:
        pass  # Connection already closed


# ============================================================================
# EXPORTACIÓN DE DATOS - Excel y PDF
# ============================================================================

@llm_monitoring_bp.route('/projects/<int:project_id>/export/excel', methods=['GET'])
@login_required
@validate_project_ownership
def export_project_excel(project_id):
    """Exportar datos COMPLETOS del proyecto a Excel (todas las métricas visibles en UI)

    El código vive en llm_monitoring_export_excel.py."""
    return llm_monitoring_export_excel.exportar_excel(project_id)


@llm_monitoring_bp.route('/projects/<int:project_id>/export/pdf', methods=['GET'])
@login_required
@validate_project_ownership
def export_project_pdf(project_id):
    """Exportar datos del proyecto a PDF - Multi-page professional report

    El código vive en llm_monitoring_export_pdf.py."""
    return llm_monitoring_export_pdf.exportar_pdf(project_id)


logger.info("✅ LLM Monitoring Blueprint loaded successfully")
