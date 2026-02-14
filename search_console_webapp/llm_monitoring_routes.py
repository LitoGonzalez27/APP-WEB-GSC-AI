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
    GET    /api/llm-monitoring/projects/:id/metrics   - Métricas detalladas
    GET    /api/llm-monitoring/projects/:id/comparison - Comparativa LLMs
    GET    /api/llm-monitoring/models                 - Listar modelos LLM disponibles
    PUT    /api/llm-monitoring/models/:id             - Actualizar modelo (admin)
    GET    /api/llm-monitoring/health                 - Health check del sistema
    
    NOTA: El endpoint POST /projects/:id/analyze fue ELIMINADO.
          El análisis ahora se ejecuta AUTOMÁTICAMENTE vía cron diario a las 4:00 AM.
"""

import logging
import os
import json
import threading
import secrets
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from functools import wraps

# Importar sistema de autenticación
from auth import login_required, admin_required, get_current_user, cron_or_auth_required
from llm_monitoring_limits import (
    can_access_llm_monitoring,
    get_llm_plan_limits,
    count_user_active_projects,
    count_project_active_queries,
    get_llm_limits_summary,
    get_upgrade_options,
)

# Importar servicios
from database import get_db_connection
from services.llm_monitoring_service import MultiLLMMonitoringService, analyze_all_active_projects
from services.llm_monitoring_stats import LLMMonitoringStatsService

# Configurar logging
logger = logging.getLogger(__name__)

# Crear Blueprint
llm_monitoring_bp = Blueprint('llm_monitoring', __name__, url_prefix='/api/llm-monitoring')


# ============================================================================
# DECORADORES AUXILIARES
# ============================================================================

@llm_monitoring_bp.before_request
def enforce_llm_access():
    """
    Bloquea acceso si el usuario no tiene plan válido/billing activo.
    Excepciones: endpoints de cron y health.
    """
    try:
        path = request.path or ""
        if "/api/llm-monitoring/cron/" in path or path.endswith("/health"):
            return None
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Usuario no autenticado'}), 401
        if not can_access_llm_monitoring(user):
            return jsonify({
                'error': 'paywall',
                'message': 'LLM Monitoring requires a paid plan',
                'upgrade_options': get_upgrade_options(user.get('plan', 'free')),
                'current_plan': user.get('plan', 'free')
            }), 402
    except Exception as e:
        logger.error(f"Error en enforce_llm_access: {e}", exc_info=True)
        return jsonify({'error': 'Error validando acceso'}), 500

def validate_project_ownership(f):
    """
    Decorador para verificar que el usuario es dueño del proyecto
    """
    @wraps(f)
    def decorated_function(project_id, *args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Usuario no autenticado'}), 401
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Error de conexión a BD'}), 500
        
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT user_id FROM llm_monitoring_projects
                WHERE id = %s
            """, (project_id,))
            
            project = cur.fetchone()
            
            if not project:
                return jsonify({'error': 'Proyecto no encontrado'}), 404
            
            if project['user_id'] != user['id']:
                return jsonify({'error': 'No tienes permiso para acceder a este proyecto'}), 403
            
            return f(project_id, *args, **kwargs)
            
        except Exception as e:
            logger.error(f"Error validando ownership: {e}", exc_info=True)
            return jsonify({'error': f'Error validando permisos: {str(e)}'}), 500
        finally:
            cur.close()
            conn.close()
    
    return decorated_function


def _ensure_cron_token_or_admin():
    """
    Endurece endpoints sensibles de cron:
    - Permite CRON token válido
    - O usuario autenticado con rol admin
    - Bloquea usuarios autenticados no-admin
    """
    try:
        auth_header = request.headers.get('Authorization', '') or ''
        token = auth_header[7:].strip() if auth_header.lower().startswith('bearer ') else ''
        cron_secret = os.environ.get('CRON_TOKEN') or os.environ.get('CRON_SECRET')

        if cron_secret and token and secrets.compare_digest(token, cron_secret):
            return None

        user = get_current_user()
        if user and user.get('role') == 'admin':
            return None

        return jsonify({
            'success': False,
            'error': 'forbidden',
            'message': 'Se requiere token de cron o rol admin'
        }), 403
    except Exception as e:
        logger.error(f"Error validando acceso cron/admin: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Error validando permisos'}), 500


def _normalize_days_param(raw_days, default: int = 30, min_days: int = 1, max_days: int = 365) -> int:
    """
    Normaliza el parámetro days para evitar rangos no válidos o excesivos.
    """
    try:
        if raw_days is None or raw_days == '':
            return default
        days = int(raw_days)
    except (TypeError, ValueError):
        return default

    if days < min_days:
        return min_days
    if days > max_days:
        return max_days
    return days


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
        return jsonify({'error': 'Usuario no autenticado'}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a BD'}), 500
    
    try:
        cur = conn.cursor()
        
        # Obtener proyectos del usuario con última fecha de análisis
        cur.execute("""
            SELECT 
                p.id,
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
                'is_active': project['is_active'],
                'is_paused_by_quota': project.get('is_paused_by_quota', False),
                'paused_until': project['paused_until'].isoformat() if project.get('paused_until') else None,
                'paused_at': project['paused_at'].isoformat() if project.get('paused_at') else None,
                'paused_reason': project.get('paused_reason'),
                'last_analysis_date': project['last_analysis_date'].isoformat() if project['last_analysis_date'] else None,
                'created_at': project['created_at'].isoformat() if project['created_at'] else None,
                'updated_at': project['updated_at'].isoformat() if project['updated_at'] else None,
                'total_snapshots': project['total_snapshots'],
                'last_snapshot_date': project['last_snapshot_date'].isoformat() if project['last_snapshot_date'] else None
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
        return jsonify({'error': f'Error obteniendo proyectos: {str(e)}'}), 500
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
        return jsonify({'error': 'Usuario no autenticado'}), 401

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
        "enabled_llms": ["openai", "anthropic", "google", "perplexity"],
        "queries_per_llm": 15
    }
    
    Returns:
        JSON con el proyecto creado
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Usuario no autenticado'}), 401
    
    plan_limits = get_llm_plan_limits(user.get('plan', 'free'))
    max_projects = plan_limits.get('max_projects')

    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({'error': 'Body JSON inválido'}), 400
    
    # Validar campos requeridos
    required_fields = ['name', 'industry', 'brand_keywords']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Campo requerido: {field}'}), 400
    
    # Valores por defecto y extracción de datos
    brand_domain = data.get('brand_domain')
    brand_keywords = data.get('brand_keywords', [])
    selected_competitors = data.get('selected_competitors', [])  # ✨ NEW
    language = str(data.get('language', 'es') or 'es').strip().lower() or 'es'
    country_code = str(data.get('country_code', 'ES') or 'ES').strip().upper()
    enabled_llms = data.get('enabled_llms', ['openai', 'anthropic', 'google', 'perplexity'])
    queries_per_llm = data.get('queries_per_llm', 15)
    
    # Validaciones
    if not isinstance(brand_keywords, list) or len(brand_keywords) == 0:
        return jsonify({'error': 'brand_keywords debe ser un array con al menos 1 palabra clave'}), 400
    
    if queries_per_llm < 5 or queries_per_llm > 60:
        return jsonify({'error': 'queries_per_llm debe estar entre 5 y 60'}), 400

    max_prompts = plan_limits.get('max_prompts_per_project')
    if max_prompts is not None and queries_per_llm > max_prompts:
        return jsonify({
            'error': 'prompt_limit_exceeded',
            'message': 'Tu plan no permite tantos prompts por proyecto',
            'current_plan': user.get('plan', 'free'),
            'upgrade_options': get_upgrade_options(user.get('plan', 'free')),
            'limit': max_prompts,
            'requested': queries_per_llm
        }), 402
    
    if not isinstance(enabled_llms, list) or len(enabled_llms) == 0:
        return jsonify({'error': 'enabled_llms debe ser un array con al menos 1 LLM'}), 400
    
    valid_llms = ['openai', 'anthropic', 'google', 'perplexity']
    if not all(llm in valid_llms for llm in enabled_llms):
        return jsonify({'error': f'LLMs válidos: {valid_llms}'}), 400

    if not country_code or len(country_code) != 2 or not country_code.isalpha():
        return jsonify({'error': 'country_code debe ser un código ISO de 2 letras'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a BD'}), 500
    
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
                    'message': 'Has alcanzado el máximo de proyectos permitidos para tu plan',
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
            return jsonify({'error': 'Ya tienes un proyecto con ese nombre'}), 409
        
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
            queries_per_llm,
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
            'message': 'Proyecto creado exitosamente. Ahora añade tus prompts manualmente.',
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
                'queries_per_llm': queries_per_llm,
                'is_active': True,
                'created_at': created_at.isoformat(),
                'total_queries': 0
            }
        }), 201
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creando proyecto: {e}", exc_info=True)
        return jsonify({'error': f'Error creando proyecto: {str(e)}'}), 500
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
    
    conn = get_db_connection()
    if not conn:
        logger.error("❌ Error de conexión a BD")
        return jsonify({'error': 'Error de conexión a BD'}), 500
    
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
                COUNT(DISTINCT q.id) as total_queries,
                COUNT(DISTINCT s.id) as total_snapshots,
                MAX(s.snapshot_date) as last_snapshot_date
            FROM llm_monitoring_projects p
            LEFT JOIN llm_monitoring_queries q ON p.id = q.project_id
            LEFT JOIN llm_monitoring_snapshots s ON p.id = s.project_id
            WHERE p.id = %s
            GROUP BY p.id, p.user_id, p.name, p.brand_name, p.brand_domain, p.brand_keywords,
                     p.industry, p.enabled_llms, p.competitors, p.competitor_domains, 
                     p.competitor_keywords, p.selected_competitors, p.language, p.country_code, p.queries_per_llm,
                     p.is_active, p.last_analysis_date, p.created_at, p.updated_at
        """, (project_id,))
        
        project = cur.fetchone()
        logger.info(f"✅ Proyecto obtenido: {project['name'] if project else 'None'}")
        
        if not project:
            logger.warning(f"⚠️ Proyecto {project_id} no encontrado")
            return jsonify({'error': 'Proyecto no encontrado'}), 404
        
        # 📊 CALCULAR SOV AGREGADO DE TODOS LOS DÍAS DISPONIBLES (últimos 30 días)
        # Método 2: SoV Agregado - Suma TODAS las menciones de TODOS los LLMs
        # Esto refleja el volumen REAL de menciones en el mercado
        # ✨ NUEVO: Soporte para rango de fechas global
        days = _normalize_days_param(request.args.get('days'), default=30)
        metric_type = request.args.get('metric', 'normal')
        if metric_type not in ['normal', 'weighted']:
            metric_type = 'normal'
        enabled_llms_filter = project.get('enabled_llms') or []
        logger.info(f"📈 Consultando métricas para proyecto {project_id} (últimos {days} días)...")
        
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
        
        # ✨ NUEVO: Calcular TENDENCIAS (cambio vs período anterior)
        def calculate_trend(current, previous):
            """Calcula tendencia: direction (up/down/stable) y change (%)"""
            if previous == 0:
                if current > 0:
                    return {'direction': 'up', 'change': 100, 'previous': 0}
                return {'direction': 'stable', 'change': 0, 'previous': 0}
            
            change = ((current - previous) / previous) * 100
            
            # Considerar "stable" si el cambio es menor al 2%
            if abs(change) < 2:
                direction = 'stable'
            else:
                direction = 'up' if change > 0 else 'down'
            
            return {
                'direction': direction,
                'change': round(abs(change), 1),
                'previous': round(previous, 1)
            }
        
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
        if current_sentiment_value > prev_sentiment_value:
            sentiment_trend = {'direction': 'better', 'previous': prev_sentiment}
        elif current_sentiment_value < prev_sentiment_value:
            sentiment_trend = {'direction': 'worse', 'previous': prev_sentiment}
        else:
            sentiment_trend = {'direction': 'same', 'previous': prev_sentiment}
        
        trends = {
            'mention_rate': calculate_trend(aggregated_mention_rate, prev_mention_rate),
            'share_of_voice': calculate_trend(aggregated_sov, prev_sov),
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
        enabled_llms = project['enabled_llms'] or []
        llms_expected = len(enabled_llms)
        
        # Completeness (0-100): promedio de completitud por LLM (queries analizadas / esperadas)
        expected_queries = project.get('total_queries') or project.get('queries_per_llm') or 0
        llm_completeness = {}
        
        total_analyzed_queries = 0
        total_expected_queries = expected_queries * llms_expected if expected_queries else 0
        
        for llm_name in enabled_llms:
            snapshots = snapshots_by_llm.get(llm_name, [])
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
        llms_with_data = sum(1 for llm in enabled_llms if llm in snapshots_by_llm)
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
                'total_snapshots_in_period': len(all_snapshots)
            }
        }
        
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
                'last_snapshot_date': project['last_snapshot_date'].isoformat() if project['last_snapshot_date'] else None
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
            'quality_score': quality_data
        }), 200
        
    except Exception as e:
        logger.error(f"Error obteniendo proyecto: {e}", exc_info=True)
        return jsonify({'error': f'Error obteniendo proyecto: {str(e)}'}), 500
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
        "enabled_llms": ["openai", "google"],
        "queries_per_llm": 20
    }
    
    Returns:
        JSON con el proyecto actualizado
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Body vacío'}), 400

    user = get_current_user()
    if not user:
        return jsonify({'error': 'Usuario no autenticado'}), 401
    plan_limits = get_llm_plan_limits(user.get('plan', 'free'))
    max_prompts = plan_limits.get('max_prompts_per_project')
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a BD'}), 500
    
    try:
        cur = conn.cursor()
        
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
                return jsonify({'error': 'language no puede estar vacío'}), 400
            updates.append("language = %s")
            params.append(language)
        
        if 'brand_domain' in data:
            updates.append("brand_domain = %s")
            params.append(data['brand_domain'])
        
        if 'brand_keywords' in data:
            if not isinstance(data['brand_keywords'], list) or len(data['brand_keywords']) == 0:
                return jsonify({'error': 'brand_keywords debe ser un array con al menos 1 palabra clave'}), 400
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
                return jsonify({'error': 'enabled_llms debe ser un array con al menos 1 LLM'}), 400
            if not all(llm in valid_llms for llm in data['enabled_llms']):
                return jsonify({'error': f'LLMs válidos: {valid_llms}'}), 400
            updates.append("enabled_llms = %s")
            params.append(data['enabled_llms'])
        
        if 'queries_per_llm' in data:
            if data['queries_per_llm'] < 5 or data['queries_per_llm'] > 60:
                return jsonify({'error': 'queries_per_llm debe estar entre 5 y 60'}), 400
            if max_prompts is not None and data['queries_per_llm'] > max_prompts:
                return jsonify({
                    'error': 'prompt_limit_exceeded',
                    'message': 'Tu plan no permite tantos prompts por proyecto',
                    'current_plan': user.get('plan', 'free'),
                    'upgrade_options': get_upgrade_options(user.get('plan', 'free')),
                    'limit': max_prompts,
                    'requested': data['queries_per_llm']
                }), 402
            updates.append("queries_per_llm = %s")
            params.append(data['queries_per_llm'])
        
        if 'country_code' in data:
            country_code = str(data.get('country_code') or '').strip().upper()
            if not country_code or len(country_code) != 2 or not country_code.isalpha():
                return jsonify({'error': 'country_code debe ser un código ISO de 2 letras'}), 400
            updates.append("country_code = %s")
            params.append(country_code)
        
        if not updates:
            return jsonify({'error': 'No hay campos para actualizar'}), 400
        
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
        
        return jsonify({
            'success': True,
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
        return jsonify({'error': f'Error actualizando proyecto: {str(e)}'}), 500
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
        return jsonify({'error': 'Error de conexión a BD'}), 500
    
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
            return jsonify({'error': 'Proyecto no encontrado o ya está inactivo'}), 404
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'Proyecto "{project["name"]}" desactivado. Ya no se ejecutará en análisis automáticos.',
            'project_id': project['id']
        }), 200
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error desactivando proyecto: {e}", exc_info=True)
        return jsonify({'error': f'Error desactivando proyecto: {str(e)}'}), 500
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
        return jsonify({'error': 'Usuario no autenticado'}), 401
    plan_limits = get_llm_plan_limits(user.get('plan', 'free'))
    max_projects = plan_limits.get('max_projects')
    active_projects = count_user_active_projects(user['id'])
    if max_projects is not None and active_projects >= max_projects:
        return jsonify({
            'error': 'project_limit_reached',
            'message': 'Has alcanzado el máximo de proyectos permitidos para tu plan',
            'current_plan': user.get('plan', 'free'),
            'upgrade_options': get_upgrade_options(user.get('plan', 'free')),
            'limit': max_projects,
            'current': active_projects
        }), 402

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a BD'}), 500
    
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
            return jsonify({'error': 'Proyecto no encontrado o ya está activo'}), 404
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'Proyecto "{project["name"]}" reactivado. Se incluirá en próximos análisis automáticos.',
            'project_id': project['id']
        }), 200
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error reactivando proyecto: {e}", exc_info=True)
        return jsonify({'error': f'Error reactivando proyecto: {str(e)}'}), 500
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
        return jsonify({'error': 'Error de conexión a BD'}), 500
    
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
            return jsonify({'error': 'Proyecto no encontrado'}), 404
        
        if project['is_active']:
            return jsonify({
                'error': 'No se puede eliminar un proyecto activo. Desactívalo primero.',
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
        return jsonify({'error': f'Error eliminando proyecto: {str(e)}'}), 500
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
    
    if not queries_list:
        return jsonify({'error': 'No se proporcionaron queries'}), 400
    
    if not isinstance(queries_list, list):
        return jsonify({'error': 'queries debe ser una lista'}), 400
    
    # Validar límites por plan (prompts por proyecto)
    plan_limits = get_llm_plan_limits(user.get('plan', 'free'))
    max_prompts = plan_limits.get('max_prompts_per_project')

    # Obtener configuración del proyecto si no se especificó idioma
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a BD'}), 500
    
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
                    'message': 'Has alcanzado el máximo de prompts permitidos para este proyecto',
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
        
        added_count = 0
        duplicate_count = 0
        error_count = 0
        
        for query_text in queries_list:
            query_text = query_text.strip()
            if not query_text:
                error_count += 1
                continue
            
            try:
                cur.execute("""
                    INSERT INTO llm_monitoring_queries (
                        project_id, query_text, language, query_type, is_active, added_at
                    ) VALUES (%s, %s, %s, %s, TRUE, NOW())
                    ON CONFLICT (project_id, query_text) DO NOTHING
                """, (project_id, query_text, language, query_type))
                
                if cur.rowcount > 0:
                    added_count += 1
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
            'duplicate_count': duplicate_count,
            'error_count': error_count,
            'message': f'{added_count} queries añadidas exitosamente'
        }), 200
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error añadiendo queries: {e}", exc_info=True)
        return jsonify({'error': f'Error añadiendo queries: {str(e)}'}), 500
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
        return jsonify({'error': 'Error de conexión a BD'}), 500
    
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
            return jsonify({'error': 'Query no encontrada'}), 404
        
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
        return jsonify({'error': f'Error eliminando query: {str(e)}'}), 500
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
    # ✨ Obtener parámetro days del time range global
    days = request.args.get('days', 30, type=int)
    if days not in [7, 14, 30, 60, 90]:
        days = 30
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a BD'}), 500
    
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
            return jsonify({'error': 'Query no encontrada', 'success': False}), 404
        
        logger.info(f"📊 Fetching history for query {query_id} ('{query['query_text'][:30]}...') - last {days} days")
        
        # Obtener historial de resultados para esta query
        enabled_llms_filter = query.get('enabled_llms') or []
        history_query = f"""
            SELECT 
                analysis_date,
                llm_provider,
                brand_mentioned,
                position_in_list,
                sentiment
            FROM llm_monitoring_results
            WHERE query_id = %s AND project_id = %s
                AND analysis_date >= CURRENT_DATE - INTERVAL '{days} days'
        """
        history_params = [query_id, project_id]
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
        return jsonify({'error': f'Error obteniendo historial: {str(e)}', 'success': False}), 500
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
        return jsonify({'error': 'Error de conexión a BD'}), 500
    
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
            return jsonify({'error': 'Proyecto no encontrado'}), 404
        
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
        
        cur.close()
        conn.close()
        
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
                    'error': 'GOOGLE_API_KEY no está configurada en el servidor',
                    'hint': 'Contacta al administrador para configurar las API keys'
                }), 500
            else:
                return jsonify({
                    'success': False,
                    'error': 'No se pudieron generar sugerencias. Es posible que Gemini API esté teniendo problemas.',
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
            'error': f'Error generando sugerencias: {str(e)}',
            'hint': 'Verifica que GOOGLE_API_KEY esté configurada'
        }), 500


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
        return jsonify({'error': 'Error de conexión a BD'}), 500
    
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
            return jsonify({'error': 'Proyecto no encontrado'}), 404
        
        cur.close()
        conn.close()
        
        brand_name = project['brand_name']
        industry = project['industry'] or 'general'
        competitors = project['competitors'] or []
        
        # Intentar generar con Gemini
        try:
            import google.generativeai as genai
            import os
            
            api_key = os.getenv('GOOGLE_API_KEY')
            if api_key:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                import random
                import time
                
                language = (project['language'] or 'en').lower()
                language_map = {
                    'es': 'Spanish',
                    'en': 'English',
                    'it': 'Italian',
                    'fr': 'French',
                    'de': 'German',
                    'pt': 'Portuguese',
                }
                lang_instruction = language_map.get(language, language.upper())
                
                # Add randomness to get different results each time
                random_seed = random.randint(1, 1000)
                timestamp = int(time.time())
                
                prompt = f"""Generate {count} unique and CREATIVE prompt variations for LLM brand monitoring.

Brand: {brand_name}
Industry: {industry}
Competitors: {', '.join(competitors[:3]) if competitors else 'N/A'}
Existing prompts to avoid repeating: {', '.join(existing_prompts[:5]) if existing_prompts else 'None yet'}

CRITICAL: Generate ALL prompts in {lang_instruction} language.
IMPORTANT: Be creative and generate DIFFERENT prompts than typical suggestions. Seed: {random_seed}-{timestamp}

Requirements:
- Each prompt should be a question users might ask an AI about this industry/brand
- Mix different types: comparisons, recommendations, reviews, how-to, alternatives, opinions, experiences
- Keep prompts concise (under 80 characters)
- Return ONLY the prompts, one per line, no numbering or explanations
- ALL prompts MUST be in {lang_instruction}
- Generate UNIQUE prompts different from the examples above"""

                response = model.generate_content(prompt)
                suggestions = [
                    line.strip() 
                    for line in response.text.strip().split('\n') 
                    if line.strip() and len(line.strip()) > 5
                ][:count]
                
                return jsonify({
                    'success': True,
                    'suggestions': suggestions,
                    'source': 'ai'
                }), 200
        
        except Exception as ai_error:
            logger.warning(f"AI generation failed, using fallback: {ai_error}")
        
        # Fallback: Generate simple variations locally with randomization
        import random
        
        language = project['language'] or 'en'
        comp_name = competitors[0] if competitors else ('competidores' if language == 'es' else 'competitors')
        
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
        return jsonify({'error': str(e), 'success': False}), 500
    finally:
        pass  # Connection already closed


# ============================================================================
# ENDPOINTS: ANÁLISIS
# ============================================================================

# REMOVED: Manual analysis endpoint
#
# Razón: El sistema ahora funciona EXCLUSIVAMENTE con cron diario (4:00 AM).
# 
# El análisis manual fue eliminado porque:
# - Toma 15-30 minutos (timeout en navegador)
# - Prioriza completitud sobre velocidad
# - Requiere sistema robusto de reintentos
# - El cron diario garantiza 100% de completitud
#
# El endpoint /projects/<int:project_id>/analyze ya NO está disponible.
# Los usuarios ven los resultados del último análisis automático en el dashboard.
#
# Para ejecutar análisis manual (admin/debugging):
# - Usar: python3 fix_openai_incomplete_analysis.py
# - O ejecutar manualmente: python3 daily_llm_monitoring_cron.py


@llm_monitoring_bp.route('/projects/<int:project_id>/metrics', methods=['GET'])
@login_required
@validate_project_ownership
def get_project_metrics(project_id):
    """
    Obtiene métricas detalladas de un proyecto
    
    Query params opcionales:
        start_date: Fecha inicio (YYYY-MM-DD, default: último mes)
        end_date: Fecha fin (YYYY-MM-DD, default: hoy)
        llm_provider: Filtrar por LLM (openai, anthropic, google, perplexity)
    
    Returns:
        JSON con snapshots y métricas agregadas
    """
    # Parámetros de fecha
    raw_days = request.args.get('days')
    days = _normalize_days_param(raw_days, default=30)
    
    if raw_days is not None and raw_days != '':
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    else:
        end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
        start_date = request.args.get('start_date', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        
    llm_provider = request.args.get('llm_provider')
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a BD'}), 500
    
    try:
        cur = conn.cursor()

        cur.execute("""
            SELECT enabled_llms
            FROM llm_monitoring_projects
            WHERE id = %s
        """, (project_id,))
        project_row = cur.fetchone()
        if not project_row:
            return jsonify({'error': 'Proyecto no encontrado'}), 404
        enabled_llms_filter = project_row.get('enabled_llms') or []
        
        # Query base
        query = """
            SELECT 
                s.*,
                p.brand_name,
                p.competitors
            FROM llm_monitoring_snapshots s
            JOIN llm_monitoring_projects p ON s.project_id = p.id
            WHERE s.project_id = %s
            AND s.snapshot_date >= %s
            AND s.snapshot_date <= %s
        """
        
        params = [project_id, start_date, end_date]
        
        # Filtro opcional por LLM
        if llm_provider:
            query += " AND s.llm_provider = %s"
            params.append(llm_provider)
        elif enabled_llms_filter:
            query += " AND s.llm_provider = ANY(%s)"
            params.append(enabled_llms_filter)
        
        query += " ORDER BY s.snapshot_date DESC, s.llm_provider"
        
        cur.execute(query, params)
        snapshots = cur.fetchall()
        
        # Formatear snapshots
        snapshots_list = []
        for s in snapshots:
            total_mentions = (s.get('total_mentions') or 0)
            pos_mentions = (s.get('positive_mentions') or 0)
            neu_mentions = (s.get('neutral_mentions') or 0)
            neg_mentions = (s.get('negative_mentions') or 0)

            positive_pct = (pos_mentions / total_mentions * 100) if total_mentions else 0
            neutral_pct = (neu_mentions / total_mentions * 100) if total_mentions else 0
            negative_pct = (neg_mentions / total_mentions * 100) if total_mentions else 0

            snapshots_list.append({
                'id': s['id'],
                'llm_provider': s['llm_provider'],
                'snapshot_date': s['snapshot_date'].isoformat() if s['snapshot_date'] else None,
                'mention_rate': float(s['mention_rate']) if s['mention_rate'] is not None else 0,
                'avg_position': float(s['avg_position']) if s['avg_position'] is not None else None,
                'top3_count': s.get('appeared_in_top3'),
                'top5_count': s.get('appeared_in_top5'),
                'top10_count': s.get('appeared_in_top10'),
                'share_of_voice': float(s['share_of_voice']) if s['share_of_voice'] is not None else 0,
                # ✨ NUEVO: Share of Voice ponderado por posición
                'weighted_share_of_voice': float(s.get('weighted_share_of_voice') or s.get('share_of_voice') or 0),
                # ➕ Exponer datos de competidores para el frontend (gráfico SOV)
                'total_competitor_mentions': int(s.get('total_competitor_mentions') or 0),
                'competitor_breakdown': s.get('competitor_breakdown') or {},
                'weighted_competitor_breakdown': s.get('weighted_competitor_breakdown') or {},
                'sentiment': {
                    'positive': float(positive_pct),
                    'neutral': float(neutral_pct),
                    'negative': float(negative_pct)
                },
                'total_queries': s.get('total_queries') or 0,
                'total_cost': float(s['total_cost_usd']) if s['total_cost_usd'] is not None else 0
            })
        
        # Calcular métricas agregadas
        total_cost = sum(s['total_cost'] for s in snapshots_list)
        total_queries = sum(s['total_queries'] for s in snapshots_list)
        
        # Promedio de mention_rate por LLM
        metrics_by_llm = {}
        for llm in ['openai', 'anthropic', 'google', 'perplexity']:
            llm_snapshots = [s for s in snapshots_list if s['llm_provider'] == llm]
            if llm_snapshots:
                metrics_by_llm[llm] = {
                    'avg_mention_rate': sum(s['mention_rate'] for s in llm_snapshots) / len(llm_snapshots),
                    'avg_position': sum(s['avg_position'] for s in llm_snapshots if s['avg_position']) / len([s for s in llm_snapshots if s['avg_position']]) if any(s['avg_position'] for s in llm_snapshots) else None,
                    'avg_share_of_voice': sum(s['share_of_voice'] for s in llm_snapshots) / len(llm_snapshots),
                    'total_snapshots': len(llm_snapshots)
                }
        
        return jsonify({
            'success': True,
            'project_id': project_id,
            'period': {
                'start_date': start_date,
                'end_date': end_date
            },
            'snapshots': snapshots_list,
            'aggregated': {
                'total_snapshots': len(snapshots_list),
                'total_cost_usd': total_cost,
                'total_queries_analyzed': total_queries,
                'metrics_by_llm': metrics_by_llm
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error obteniendo métricas: {e}", exc_info=True)
        return jsonify({'error': f'Error obteniendo métricas: {str(e)}'}), 500
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/projects/<int:project_id>/urls-ranking', methods=['GET'])
@login_required
@validate_project_ownership
def get_urls_ranking(project_id):
    """
    Obtiene el ranking de URLs más mencionadas por los LLMs
    
    Query params opcionales:
        days: Número de días (default: 30)
        llm_provider: Filtrar por LLM específico ('openai', 'anthropic', 'google', 'perplexity')
        limit: Número máximo de URLs (default: 50)
    
    Returns:
        JSON con ranking de URLs citadas por los LLMs
    """
    days = _normalize_days_param(request.args.get('days'), default=30)
    llm_provider = request.args.get('llm_provider')
    limit = request.args.get('limit', 50, type=int)
    
    try:
        enabled_llms_filter = None
        if not llm_provider:
            conn = get_db_connection()
            if conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT enabled_llms
                    FROM llm_monitoring_projects
                    WHERE id = %s
                """, (project_id,))
                project = cur.fetchone()
                if project:
                    enabled_llms_filter = project.get('enabled_llms') or None
                cur.close()
                conn.close()

        urls_ranking = LLMMonitoringStatsService.get_project_urls_ranking(
            project_id=project_id,
            days=days,
            llm_provider=llm_provider,
            enabled_llms=enabled_llms_filter,
            limit=limit
        )
        
        return jsonify({
            'success': True,
            'project_id': project_id,
            'filters': {
                'days': days,
                'llm_provider': llm_provider or 'all',
                'limit': limit
            },
            'urls': urls_ranking,
            'total_urls': len(urls_ranking)
        }), 200
        
    except Exception as e:
        logger.error(f"Error obteniendo ranking de URLs: {e}", exc_info=True)
        return jsonify({'error': f'Error obteniendo ranking de URLs: {str(e)}'}), 500


@llm_monitoring_bp.route('/projects/<int:project_id>/comparison', methods=['GET'])
@login_required
@validate_project_ownership
def get_llm_comparison(project_id):
    """
    Comparativa entre LLMs para un proyecto (usa vista llm_visibility_comparison)
    
    Query params opcionales:
        metric: 'weighted' o 'normal' (default: 'weighted')
    
    Returns:
        JSON con comparativa de métricas entre LLMs
    """
    # ✨ NUEVO: Parámetro de métrica para Share of Voice
    metric_type = request.args.get('metric', 'weighted')
    
    # ✨ NUEVO: Parámetro de días
    days = _normalize_days_param(request.args.get('days'), default=30)
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a BD'}), 500
    
    try:
        cur = conn.cursor()

        cur.execute("""
            SELECT enabled_llms
            FROM llm_monitoring_projects
            WHERE id = %s
        """, (project_id,))
        project_row = cur.fetchone()
        if not project_row:
            return jsonify({'error': 'Proyecto no encontrado'}), 404
        enabled_llms_filter = project_row.get('enabled_llms') or []
        
        # Traer filas por LLM directamente desde snapshots
        # ✨ NUEVO: Incluir weighted_share_of_voice
        comparison_query = """
            SELECT 
                llm_provider,
                snapshot_date,
                mention_rate,
                total_mentions,
                avg_position,
                share_of_voice,
                weighted_share_of_voice,
                avg_sentiment_score,
                positive_mentions,
                neutral_mentions,
                negative_mentions,
                total_queries
            FROM llm_monitoring_snapshots
            WHERE project_id = %s
            AND snapshot_date >= %s
        """
        comparison_params = [project_id, start_date]
        if enabled_llms_filter:
            comparison_query += " AND llm_provider = ANY(%s)"
            comparison_params.append(enabled_llms_filter)
        comparison_query += " ORDER BY snapshot_date DESC, llm_provider"
        cur.execute(comparison_query, comparison_params)
        
        rows = cur.fetchall()
        
        # ✨ NUEVO: Obtener distribución de position_source para cada snapshot
        # Esto nos permite mostrar badges 📝/🔗/📝🔗 en UI
        position_source_query = """
            SELECT 
                s.llm_provider,
                s.snapshot_date,
                COUNT(*) FILTER (WHERE r.position_source = 'text') as text_count,
                COUNT(*) FILTER (WHERE r.position_source = 'link') as link_count,
                COUNT(*) FILTER (WHERE r.position_source = 'both') as both_count,
                COUNT(*) as total_with_position
            FROM llm_monitoring_snapshots s
            LEFT JOIN llm_monitoring_results r ON 
                s.project_id = r.project_id 
                AND s.llm_provider = r.llm_provider 
                AND s.snapshot_date = r.analysis_date
                AND r.position_source IS NOT NULL
            WHERE s.project_id = %s
            AND s.snapshot_date >= %s
        """
        position_source_params = [project_id, start_date]
        if enabled_llms_filter:
            position_source_query += " AND s.llm_provider = ANY(%s)"
            position_source_params.append(enabled_llms_filter)
        position_source_query += """
            GROUP BY s.llm_provider, s.snapshot_date
            ORDER BY s.snapshot_date DESC, s.llm_provider
        """
        cur.execute(position_source_query, position_source_params)
        
        position_sources = cur.fetchall()
        
        # Crear lookup dict para position_source por (llm_provider, date)
        position_source_map = {}
        for ps in position_sources:
            key = (ps['llm_provider'], ps['snapshot_date'].isoformat() if ps['snapshot_date'] else None)
            text_count = ps['text_count'] or 0
            link_count = ps['link_count'] or 0
            both_count = ps['both_count'] or 0
            
            # Determinar badge predominante
            if both_count > 0 or (text_count > 0 and link_count > 0):
                dominant_source = 'both'
            elif text_count >= link_count:
                dominant_source = 'text'
            else:
                dominant_source = 'link'
            
            position_source_map[key] = {
                'dominant': dominant_source,
                'text_count': text_count,
                'link_count': link_count,
                'both_count': both_count
            }
        
        # Formatear datos
        comparison_list = []
        for c in rows:
            # 🔧 FIX: Calcular sentiment basándose en los contadores, igual que en el KPI
            positive_mentions = c.get('positive_mentions') or 0
            neutral_mentions = c.get('neutral_mentions') or 0
            negative_mentions = c.get('negative_mentions') or 0
            total_queries_row = c.get('total_queries') or 0
            
            positive_pct = (positive_mentions / total_queries_row * 100) if total_queries_row else 0
            neutral_pct = (neutral_mentions / total_queries_row * 100) if total_queries_row else 0
            negative_pct = (negative_mentions / total_queries_row * 100) if total_queries_row else 0
            
            # ✨ NUEVO: Seleccionar Share of Voice según métrica
            if metric_type == 'weighted':
                sov = c.get('weighted_share_of_voice') or c.get('share_of_voice') or 0
            else:
                sov = c.get('share_of_voice') or 0
            
            # ✨ NUEVO: Obtener position_source info para este snapshot
            snapshot_key = (c['llm_provider'], c['snapshot_date'].isoformat() if c['snapshot_date'] else None)
            position_source_info = position_source_map.get(snapshot_key, {
                'dominant': None,
                'text_count': 0,
                'link_count': 0,
                'both_count': 0
            })
            
            comparison_list.append({
                'llm_provider': c['llm_provider'],
                'snapshot_date': c['snapshot_date'].isoformat() if c['snapshot_date'] else None,
                'mention_rate': float(c['mention_rate']) if c['mention_rate'] is not None else 0,
                'total_mentions': c.get('total_mentions') or 0,  # 🔧 FIX: Campo faltante para Grid.js
                'avg_position': float(c['avg_position']) if c['avg_position'] is not None else None,
                'position_source': position_source_info['dominant'],  # ✨ NUEVO: 'text', 'link', 'both'
                'position_source_details': position_source_info,  # ✨ NUEVO: Detalles para tooltip
                'share_of_voice': float(sov) if sov is not None else 0,  # ✨ MODIFICADO: Usar métrica seleccionada
                'sentiment_score': float(c['avg_sentiment_score']) if c['avg_sentiment_score'] is not None else 0,
                'sentiment': {
                    'positive': float(positive_pct),
                    'neutral': float(neutral_pct),
                    'negative': float(negative_pct)
                },
                'total_queries': total_queries_row
            })
        
        # Agrupar por fecha para comparación lado a lado
        by_date = {}
        for c in comparison_list:
            date = c['snapshot_date']
            if date not in by_date:
                by_date[date] = {}
            by_date[date][c['llm_provider']] = c
        
        return jsonify({
            'success': True,
            'project_id': project_id,
            'comparison': comparison_list,
            'by_date': by_date
        }), 200
        
    except Exception as e:
        logger.error(f"Error obteniendo comparativa: {e}", exc_info=True)
        return jsonify({'error': f'Error obteniendo comparativa: {str(e)}'}), 500
    finally:
        cur.close()
        conn.close()


# ============================================================================
# ENDPOINTS: CONFIGURACIÓN
# ============================================================================
# 
# NOTA: Los endpoints de configuración de API keys y presupuesto por usuario
# han sido ELIMINADOS porque en este modelo de negocio, los usuarios NO 
# configuran sus propias API keys. El servicio usa API keys globales
# gestionadas por el dueño del servicio en variables de entorno.
#
# Si en el futuro se necesita un modelo "Enterprise" donde clientes grandes
# usen sus propias APIs, se pueden restaurar estos endpoints.
# ============================================================================


# ============================================================================
# ENDPOINTS: QUERIES DETALLADAS
# ============================================================================

@llm_monitoring_bp.route('/projects/<int:project_id>/queries', methods=['GET'])
@login_required
@validate_project_ownership
def get_project_queries(project_id):
    """
    Obtener tabla detallada de queries/prompts con métricas agregadas
    
    Devuelve información similar a la tabla de LLM Pulse:
    - Query text
    - Country & Language
    - Total responses (cuántos LLMs respondieron)
    - Total mentions
    - Visibility % (promedio)
    - Average position
    - Last update
    - Creation date
    
    Query params:
        days: Días hacia atrás para filtrar resultados (default: 30)
    
    Returns:
        JSON con lista de queries y sus métricas
    """
    user = get_current_user()
    days = _normalize_days_param(request.args.get('days'), default=30)
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a BD'}), 500
    
    try:
        cur = conn.cursor()
        
        # Obtener información del proyecto (para country)
        cur.execute("""
            SELECT name, language, country_code, enabled_llms
            FROM llm_monitoring_projects
            WHERE id = %s
        """, (project_id,))
        
        project = cur.fetchone()
        if not project:
            return jsonify({'error': 'Proyecto no encontrado'}), 404
        enabled_llms_filter = project.get('enabled_llms') or []
        
        # Calcular rango de fechas
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Obtener información del proyecto para filtrar URLs de marca
        cur.execute("""
            SELECT brand_domain FROM llm_monitoring_projects WHERE id = %s
        """, (project_id,))
        
        project_info = cur.fetchone()
        brand_domain = project_info['brand_domain'] if project_info else None
        
        # Obtener queries con métricas agregadas
        # ✨ MEJORADO: Contar menciones en texto + menciones en URLs
        query_metrics_sql = """
            WITH query_metrics AS (
                SELECT 
                    q.id,
                    q.query_text,
                    q.language,
                    q.query_type,
                    q.added_at as created_at,
                    COUNT(DISTINCT r.llm_provider) as total_responses,
                    COUNT(DISTINCT r.id) as total_results,
                    -- ✨ NUEVO: Contar menciones en texto (brand_mentioned)
                    SUM(CASE WHEN r.brand_mentioned THEN 1 ELSE 0 END) as text_mentions,
                    -- ✨ NUEVO: Contar URLs de marca en sources (requiere jsonb_array_elements)
                    SUM(
                        CASE 
                            WHEN r.sources IS NOT NULL AND r.sources::text != '[]' 
                            THEN (
                                SELECT COUNT(*) 
                                FROM jsonb_array_elements(r.sources::jsonb) AS source
                                WHERE source->>'url' ILIKE %s
                            )
                            ELSE 0
                        END
                    ) as url_citations,
                    AVG(CASE WHEN r.brand_mentioned THEN 100 ELSE 0 END) as visibility_pct,
                    AVG(r.position_in_list) FILTER (WHERE r.position_in_list IS NOT NULL) as avg_position,
                    MAX(r.analysis_date) as last_analysis_date,
                    MAX(r.created_at) as last_update
                FROM llm_monitoring_queries q
                LEFT JOIN llm_monitoring_results r ON q.id = r.query_id 
                    AND r.analysis_date >= %s 
                    AND r.analysis_date <= %s
                    {llm_filter}
                WHERE q.project_id = %s AND q.is_active = TRUE
                GROUP BY q.id, q.query_text, q.language, q.query_type, q.added_at
            )
            SELECT 
                id,
                query_text,
                language,
                query_type,
                created_at,
                total_responses,
                total_results,
                -- ✨ NUEVO: Total de menciones = menciones en texto + citaciones en URLs
                (COALESCE(text_mentions, 0) + COALESCE(url_citations, 0)) as total_mentions,
                text_mentions,
                url_citations,
                ROUND(visibility_pct::numeric, 1) as visibility_pct,
                ROUND(avg_position::numeric, 1) as avg_position,
                last_analysis_date,
                last_update
            FROM query_metrics
            ORDER BY last_update DESC NULLS LAST, created_at DESC
        """.format(
            llm_filter="AND r.llm_provider = ANY(%s)" if enabled_llms_filter else ""
        )
        query_metrics_params = [f'%{brand_domain}%' if brand_domain else '%', start_date, end_date]
        if enabled_llms_filter:
            query_metrics_params.append(enabled_llms_filter)
        query_metrics_params.append(project_id)
        cur.execute(query_metrics_sql, query_metrics_params)
        
        queries_raw = cur.fetchall()
        
        # ✨ NUEVO: Obtener menciones detalladas por LLM para cada query (para acordeón expandible)
        # Esto nos permite mostrar qué LLMs mencionaron la marca y los competidores
        # Usamos DISTINCT ON para obtener solo el resultado más reciente por (query_id, llm_provider)
        # 🔧 FIX: Incluir información sobre menciones en URLs también
        mentions_query_sql = """
            SELECT DISTINCT ON (r.query_id, r.llm_provider)
                r.query_id,
                r.llm_provider,
                r.brand_mentioned,
                r.position_in_list,
                r.competitors_mentioned,
                r.sources,
                r.analysis_date
            FROM llm_monitoring_results r
            WHERE r.query_id = ANY(%s)
                AND r.analysis_date >= %s
                AND r.analysis_date <= %s
                {llm_filter}
            ORDER BY r.query_id, r.llm_provider, r.analysis_date DESC
        """.format(
            llm_filter="AND r.llm_provider = ANY(%s)" if enabled_llms_filter else ""
        )
        mentions_query_params = [[q['id'] for q in queries_raw], start_date, end_date]
        if enabled_llms_filter:
            mentions_query_params.append(enabled_llms_filter)
        cur.execute(mentions_query_sql, mentions_query_params)
        
        mentions_by_query = {}
        for row in cur.fetchall():
            query_id = row['query_id']
            llm = row['llm_provider']
            
            if query_id not in mentions_by_query:
                mentions_by_query[query_id] = {}
            
            # 🔧 FIX: Detectar menciones en URLs también
            brand_in_text = row['brand_mentioned'] or False
            brand_in_urls = False
            
            # Verificar si la marca aparece en las URLs citadas
            if brand_domain and row['sources']:
                sources = row['sources']
                # sources puede ser una string JSON o ya un dict/list
                if isinstance(sources, str):
                    import json
                    try:
                        sources = json.loads(sources)
                    except:
                        sources = []
                
                if isinstance(sources, list):
                    for source in sources:
                        if isinstance(source, dict):
                            url = source.get('url', '').lower()
                            if brand_domain.lower() in url:
                                brand_in_urls = True
                                break
            
            # La marca fue mencionada si apareció en texto O en URLs
            brand_mentioned_total = brand_in_text or brand_in_urls
            
            # Ahora cada fila es única por (query_id, llm_provider) - el más reciente
            mentions_by_query[query_id][llm] = {
                'brand_mentioned': brand_mentioned_total,  # 🔧 FIX: Total incluyendo URLs
                'brand_mentioned_in_text': brand_in_text,  # ✨ NUEVO: Desglose
                'brand_mentioned_in_urls': brand_in_urls,  # ✨ NUEVO: Desglose
                'position': row['position_in_list'],
                'competitors': row['competitors_mentioned'] or {}
            }
        
        cur.close()
        conn.close()
        
        # Formatear datos para el frontend
        queries_list = []
        for q in queries_raw:
            query_id = q['id']
            
            # ✨ NUEVO: Añadir información de menciones por LLM
            mentions_detail = mentions_by_query.get(query_id, {})
            
            queries_list.append({
                'id': query_id,
                'prompt': q['query_text'],
                'country': 'Global',  # Por ahora global, se puede añadir por query
                'language': q['language'] or project['language'] or 'en',
                'query_type': q['query_type'],
                'total_responses': q['total_responses'] or 0,
                'total_mentions': q['total_mentions'] or 0,
                'visibility_pct': float(q['visibility_pct']) if q['visibility_pct'] else 0,
                'avg_position': float(q['avg_position']) if q['avg_position'] else None,
                'last_update': q['last_update'].isoformat() if q['last_update'] else None,
                'last_analysis_date': q['last_analysis_date'].isoformat() if q['last_analysis_date'] else None,
                'created_at': q['created_at'].isoformat() if q['created_at'] else None,
                'mentions_by_llm': mentions_detail  # ✨ NUEVO: Detalles para acordeón
            })
        
        return jsonify({
            'success': True,
            'queries': queries_list,
            'total': len(queries_list),
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': days
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error obteniendo queries: {e}", exc_info=True)
        return jsonify({'error': f'Error obteniendo queries: {str(e)}'}), 500


# ============================================================================
# ENDPOINTS: SHARE OF VOICE HISTÓRICO
# ============================================================================

@llm_monitoring_bp.route('/projects/<int:project_id>/share-of-voice-history', methods=['GET'])
@login_required
@validate_project_ownership
def get_share_of_voice_history(project_id):
    """
    Obtener datos históricos de Share of Voice para gráfico de líneas temporal
    
    Similar a los gráficos comparativos de Manual AI, muestra la evolución
    del Share of Voice de la marca vs competidores a lo largo del tiempo.
    
    Query params:
        days: Número de días hacia atrás (default: 30)
        metric: 'normal' o 'weighted' (default: 'weighted') - tipo de Share of Voice
    
    Returns:
        JSON con datos para gráfico de líneas:
        {
            'dates': ['2025-01-01', '2025-01-02', ...],
            'datasets': [
                {
                    'label': 'Tu Marca',
                    'data': [45.2, 48.1, ...],
                    'borderColor': '#3b82f6',
                    ...
                },
                {
                    'label': 'Competidor 1',
                    'data': [30.5, 28.3, ...],
                    'borderColor': '#ef4444',
                    ...
                }
            ]
        }
    """
    user = get_current_user()
    days = _normalize_days_param(request.args.get('days'), default=30)
    metric_type = request.args.get('metric', 'weighted')  # 'normal' o 'weighted'
    
    # Validar metric_type
    if metric_type not in ['normal', 'weighted']:
        metric_type = 'weighted'
    
    logger.info(f"📊 Share of Voice history requested - Type: {metric_type}, Days: {days}")
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a BD'}), 500
    
    try:
        cur = conn.cursor()
        
        # Obtener proyecto
        cur.execute("""
            SELECT 
                id, user_id, name, brand_name, industry, 
                brand_domain, brand_keywords,
                competitors, selected_competitors,
                language, country_code,
                queries_per_llm, enabled_llms,
                is_active, created_at, last_analysis_date
            FROM llm_monitoring_projects
            WHERE id = %s
        """, (project_id,))
        
        project = cur.fetchone()
        
        if not project:
            return jsonify({'error': 'Proyecto no encontrado'}), 404
            
        # Calcular fechas de inicio y fin
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        enabled_llms_filter = project.get('enabled_llms') or []
        
        # Obtener todos los snapshots del período agrupados por fecha (incluir métricas ponderadas)
        sov_history_query = """
            SELECT 
                snapshot_date,
                llm_provider,
                share_of_voice,
                weighted_share_of_voice,
                total_mentions,
                total_competitor_mentions,
                competitor_breakdown,
                weighted_competitor_breakdown
            FROM llm_monitoring_snapshots
            WHERE project_id = %s 
                AND snapshot_date >= %s 
        """
        sov_history_params = [project_id, start_date]
        if enabled_llms_filter:
            sov_history_query += " AND llm_provider = ANY(%s)"
            sov_history_params.append(enabled_llms_filter)
        sov_history_query += " ORDER BY snapshot_date, llm_provider"
        cur.execute(sov_history_query, sov_history_params)
        
        snapshots = cur.fetchall()
        
        cur.close()
        conn.close()
        
        # Si no hay datos, devolver estructura vacía
        if not snapshots:
            return jsonify({
                'success': True,
                'dates': [],
                'datasets': []
            }), 200
        
        # ✨ NEW: Use selected_competitors structure for clear attribution
        # =======================================================================
        # MAPEO DIRECTO: Cada dominio tiene sus keywords asociadas
        # =======================================================================
        
        selected_competitors = project.get('selected_competitors') or []
        
        # Crear mapeo: variante_detectada -> dominio_competidor
        competitor_mapping = {}
        competitor_display_names = {}  # dominio -> nombre_display
        
        def normalize_variant(variant):
            """Normaliza una variante para matching"""
            v = variant.lower().strip()
            # Quitar extensiones de dominio comunes
            v = v.replace('.com', '').replace('.es', '').replace('.net', '').replace('.org', '')
            v = v.replace('.mx', '').replace('.ar', '').replace('.cl', '').replace('.pe', '')
            v = v.replace('www.', '')
            return v
        
        def get_display_name(domain):
            """Obtiene nombre display limpio del dominio"""
            if not domain:
                return 'Unknown Competitor'
            # Quitar www. y extensión
            name = domain.replace('www.', '')
            # Tomar solo el nombre antes del TLD
            name_parts = name.split('.')
            if len(name_parts) > 0:
                return name_parts[0].upper()
            return domain.upper()
        
        # ✨ NEW: Mapear directamente desde selected_competitors
        for comp in selected_competitors:
            domain = comp.get('domain', '').strip()
            keywords = comp.get('keywords', [])
            
            if not domain:
                continue
            
            # Usar el dominio como identificador único
            domain_lower = domain.lower()
            display_name = get_display_name(domain)
            competitor_display_names[domain_lower] = display_name
            
            # Mapear el dominio a sí mismo
            competitor_mapping[domain_lower] = domain_lower
            
            # Mapear todas las keywords asociadas a este dominio
            for keyword in keywords:
                keyword_lower = keyword.lower().strip()
                competitor_mapping[keyword_lower] = domain_lower
                
                # También mapear variante normalizada
                keyword_normalized = normalize_variant(keyword)
                if keyword_normalized != keyword_lower:
                    competitor_mapping[keyword_normalized] = domain_lower
        
        # Agrupar datos por fecha Y agrupar menciones por dominio de competidor
        from collections import defaultdict
        data_by_date = defaultdict(lambda: {
            'brand_mentions': 0,
            'competitor_mentions': defaultdict(int),  # Agrupado por dominio
            'llm_count': 0
        })
        
        # ✨ NUEVO: Elegir la métrica correcta según el parámetro
        for snapshot in snapshots:
            date_str = snapshot['snapshot_date'].isoformat()
            
            # ✨ MEJORADO: Usar menciones ponderadas o normales según el parámetro
            if metric_type == 'weighted':
                # Si hay weighted_share_of_voice, usarlo para inferir menciones ponderadas
                try:
                    weighted_sov_raw = snapshot.get('weighted_share_of_voice')
                    # Convertir a float de forma segura
                    try:
                        weighted_sov = float(weighted_sov_raw) if weighted_sov_raw is not None else None
                    except Exception:
                        weighted_sov = None
                    
                    weighted_breakdown_raw = snapshot.get('weighted_competitor_breakdown')
                    # Asegurar que sea un dict; si viene en string JSON, parsear
                    if isinstance(weighted_breakdown_raw, dict):
                        weighted_breakdown = weighted_breakdown_raw
                    elif isinstance(weighted_breakdown_raw, str):
                        try:
                            parsed = json.loads(weighted_breakdown_raw)
                            weighted_breakdown = parsed if isinstance(parsed, dict) else {}
                        except Exception:
                            weighted_breakdown = {}
                    else:
                        weighted_breakdown = {}
                    
                    # Si tenemos datos ponderados, usarlos
                    if weighted_sov is not None and weighted_breakdown:
                        # Calcular menciones ponderadas de competidores
                        try:
                            total_weighted_comp = sum(float(v) for v in weighted_breakdown.values() if v is not None)
                        except Exception:
                            total_weighted_comp = 0.0
                        
                        if weighted_sov and weighted_sov > 0:
                            # SoV = brand / (brand + comp) * 100
                            # brand = (SoV / (100 - SoV)) * comp
                            if weighted_sov >= 100:
                                # Si SoV es 100%, la marca tiene todas las menciones
                                weighted_brand = total_weighted_comp if total_weighted_comp > 0 else 1.0
                            else:
                                weighted_brand = (weighted_sov / (100 - weighted_sov)) * total_weighted_comp
                        else:
                            weighted_brand = 0.0
                        
                        data_by_date[date_str]['brand_mentions'] += weighted_brand
                        breakdown = weighted_breakdown
                    else:
                        # Fallback a métricas normales si no hay datos ponderados
                        logger.warning(f"⚠️ No weighted data for {date_str}, falling back to normal metrics")
                        data_by_date[date_str]['brand_mentions'] += (snapshot['total_mentions'] or 0)
                        breakdown = snapshot.get('competitor_breakdown') or {}
                except Exception as e_weighted:
                    # Cualquier error en la ruta ponderada no debe romper el endpoint
                    logger.warning(f"⚠️ Weighted calc error on {date_str}: {e_weighted}. Using normal metrics as fallback.")
                    data_by_date[date_str]['brand_mentions'] += (snapshot['total_mentions'] or 0)
                    breakdown = snapshot.get('competitor_breakdown') or {}
            else:
                # Modo normal: usar métricas estándar
                data_by_date[date_str]['brand_mentions'] += (snapshot['total_mentions'] or 0)
                breakdown = snapshot.get('competitor_breakdown') or {}
            
            data_by_date[date_str]['llm_count'] += 1
            
            # 🔧 FIX: Asegurar que breakdown es un dict antes de iterar
            if isinstance(breakdown, str):
                try:
                    breakdown = json.loads(breakdown)
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"⚠️ Could not parse breakdown JSON for {date_str}, skipping")
                    breakdown = {}
            
            if not isinstance(breakdown, dict):
                logger.warning(f"⚠️ Breakdown is not a dict for {date_str}, skipping")
                breakdown = {}
            
            for detected_variant, mentions in breakdown.items():
                variant_lower = detected_variant.lower().strip()
                variant_normalized = normalize_variant(detected_variant)
                
                # Buscar en el mapeo directo
                competitor_domain = None
                if variant_lower in competitor_mapping:
                    competitor_domain = competitor_mapping[variant_lower]
                elif variant_normalized in competitor_mapping:
                    competitor_domain = competitor_mapping[variant_normalized]
                else:
                    # Buscar por coincidencia parcial (más robustez)
                    for mapped_variant, domain in competitor_mapping.items():
                        if (mapped_variant in variant_lower or 
                            variant_lower in mapped_variant or
                            normalize_variant(mapped_variant) == variant_normalized):
                            competitor_domain = domain
                            break
                
                # Si encontramos el dominio, acumular menciones
                if competitor_domain:
                    data_by_date[date_str]['competitor_mentions'][competitor_domain] += mentions
                # Si no, ignorar (no es un competidor configurado)
        
        # Ordenar fechas
        dates = sorted(data_by_date.keys())
        
        # Preparar datasets
        datasets = []
        
        # Dataset para la marca principal (TODAS las variantes ya están sumadas en total_mentions)
        brand_name = project['brand_name'] or 'Your Brand'
        brand_data = []
        
        for date_str in dates:
            day_data = data_by_date[date_str]
            brand_mentions = day_data['brand_mentions']
            total_comp_mentions = sum(day_data['competitor_mentions'].values())
            total_mentions = brand_mentions + total_comp_mentions
            
            # Calcular Share of Voice de la marca
            sov = (brand_mentions / total_mentions * 100) if total_mentions > 0 else 0
            brand_data.append(round(sov, 2))
        
        datasets.append({
            'label': brand_name,
            'data': brand_data,
            'borderColor': '#3b82f6',  # Blue para la marca
            'backgroundColor': 'rgba(59, 130, 246, 0.1)',
            'borderWidth': 3,
            'tension': 0.4,
            'fill': True,
            'pointRadius': 4,
            'pointHoverRadius': 6
        })
        
        # Datasets para competidores (ahora agrupados)
        competitor_colors = [
            '#ef4444',  # Red
            '#f97316',  # Orange
            '#22c55e',  # Green
            '#a855f7',  # Purple
            '#ec4899'   # Pink
        ]
        
        # ✨ NEW: Obtener lista única de dominios de competidores
        all_competitor_domains = set()
        for day_data in data_by_date.values():
            all_competitor_domains.update(day_data['competitor_mentions'].keys())
        
        for idx, competitor_domain in enumerate(sorted(all_competitor_domains)):
            comp_data = []
            
            # ✨ NEW: Obtener nombre display del dominio
            display_name = competitor_display_names.get(competitor_domain, get_display_name(competitor_domain))
            
            for date_str in dates:
                day_data = data_by_date[date_str]
                brand_mentions = day_data['brand_mentions']
                comp_mentions = day_data['competitor_mentions'].get(competitor_domain, 0)
                total_comp_mentions = sum(day_data['competitor_mentions'].values())
                total_mentions = brand_mentions + total_comp_mentions
                
                # Calcular Share of Voice del competidor
                sov = (comp_mentions / total_mentions * 100) if total_mentions > 0 else 0
                comp_data.append(round(sov, 2))
            
            color = competitor_colors[idx % len(competitor_colors)]
            datasets.append({
                'label': display_name,
                'data': comp_data,
                'borderColor': color,
                'backgroundColor': color.replace('rgb', 'rgba').replace(')', ', 0.1)') if 'rgb' in color else f'{color}20',
                'borderWidth': 2,
                'tension': 0.4,
                'fill': False,
                'pointRadius': 3,
                'pointHoverRadius': 5
            })
        
        # =======================================================================
        # DATOS ADICIONALES: Menciones absolutas + Donut data
        # =======================================================================
        
        # 1. Datasets para gráfico de menciones (números absolutos)
        mentions_datasets = []
        
        # Dataset de menciones de marca
        brand_mentions_data = []
        for date_str in dates:
            day_data = data_by_date[date_str]
            brand_mentions_data.append(day_data['brand_mentions'])
        
        mentions_datasets.append({
            'label': brand_name,
            'data': brand_mentions_data,
            'borderColor': '#3b82f6',
            'backgroundColor': 'rgba(59, 130, 246, 0.1)',
            'borderWidth': 3,
            'tension': 0.4,
            'fill': True,
            'pointRadius': 4,
            'pointHoverRadius': 6
        })
        
        # Datasets de menciones de competidores
        for idx, competitor_domain in enumerate(sorted(all_competitor_domains)):
            comp_mentions_data = []
            display_name = competitor_display_names.get(competitor_domain, get_display_name(competitor_domain))
            
            for date_str in dates:
                day_data = data_by_date[date_str]
                comp_mentions_data.append(day_data['competitor_mentions'].get(competitor_domain, 0))
            
            color = competitor_colors[idx % len(competitor_colors)]
            mentions_datasets.append({
                'label': display_name,
                'data': comp_mentions_data,
                'borderColor': color,
                'backgroundColor': color.replace('rgb', 'rgba').replace(')', ', 0.1)') if 'rgb' in color else f'{color}20',
                'borderWidth': 2,
                'tension': 0.4,
                'fill': False,
                'pointRadius': 3,
                'pointHoverRadius': 5
            })
        
        # 2. Datos para gráfico de rosco (promedio del período)
        total_brand_mentions_period = sum(data_by_date[date_str]['brand_mentions'] for date_str in dates)
        total_competitor_mentions_period = defaultdict(int)
        
        for date_str in dates:
            for comp_domain, mentions in data_by_date[date_str]['competitor_mentions'].items():
                total_competitor_mentions_period[comp_domain] += mentions
        
        # Calcular totales
        grand_total = total_brand_mentions_period + sum(total_competitor_mentions_period.values())
        
        # Preparar datos del donut
        donut_labels = [brand_name]
        donut_values = [round(total_brand_mentions_period / grand_total * 100, 2) if grand_total > 0 else 0]
        donut_colors = ['#3b82f6']
        
        for idx, competitor_domain in enumerate(sorted(all_competitor_domains)):
            display_name = competitor_display_names.get(competitor_domain, get_display_name(competitor_domain))
            comp_total = total_competitor_mentions_period.get(competitor_domain, 0)
            comp_percentage = round(comp_total / grand_total * 100, 2) if grand_total > 0 else 0
            
            if comp_percentage > 0:  # Solo incluir si tiene menciones
                donut_labels.append(display_name)
                donut_values.append(comp_percentage)
                donut_colors.append(competitor_colors[idx % len(competitor_colors)])
        
        return jsonify({
            'success': True,
            'metric_type': metric_type,  # ✨ NUEVO: Indicar qué métrica se está usando
            'dates': dates,
            'datasets': datasets,  # Share of Voice (%)
            'mentions_datasets': mentions_datasets,  # Menciones absolutas
            'donut_data': {
                'labels': donut_labels,
                'values': donut_values,
                'colors': donut_colors
            },
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': days
            }
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo histórico de Share of Voice: {e}", exc_info=True)
        logger.error(f"   Project ID: {project_id}, Days: {days}, Metric: {metric_type}")
        return jsonify({
            'error': f'Error obteniendo datos: {str(e)}',
            'details': 'Check server logs for more information'
        }), 500


# ============================================================================
# ENDPOINTS: MODELOS
# ============================================================================

@llm_monitoring_bp.route('/models', methods=['GET'])
@login_required
def get_models():
    """
    Lista todos los modelos LLM disponibles
    
    Query params opcionales:
        provider: Filtrar por proveedor (openai, anthropic, google, perplexity)
        is_current: Filtrar solo modelos actuales (true/false)
    
    Returns:
        JSON con lista de modelos y sus precios
    """
    provider = request.args.get('provider')
    is_current = request.args.get('is_current')
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a BD'}), 500
    
    try:
        cur = conn.cursor()
        
        query = "SELECT * FROM llm_model_registry WHERE 1=1"
        params = []
        
        if provider:
            query += " AND llm_provider = %s"
            params.append(provider)
        
        if is_current is not None:
            query += " AND is_current = %s"
            params.append(is_current.lower() == 'true')
        
        query += " ORDER BY llm_provider, is_current DESC, model_display_name"
        
        cur.execute(query, params)
        models = cur.fetchall()
        
        # Formatear modelos
        models_list = []
        for m in models:
            models_list.append({
                'id': m['id'],
                'llm_provider': m['llm_provider'],
                'model_id': m['model_id'],
                'model_display_name': m['model_display_name'],
                'cost_per_1m_input_tokens': float(m['cost_per_1m_input_tokens']) if m['cost_per_1m_input_tokens'] else 0,
                'cost_per_1m_output_tokens': float(m['cost_per_1m_output_tokens']) if m['cost_per_1m_output_tokens'] else 0,
                'max_tokens': m['max_tokens'],
                'is_current': m['is_current'],
                'is_available': m['is_available'],
                'created_at': m['created_at'].isoformat() if m['created_at'] else None,
                'updated_at': m['updated_at'].isoformat() if m['updated_at'] else None
            })
        
        return jsonify({
            'success': True,
            'models': models_list,
            'total': len(models_list)
        }), 200
        
    except Exception as e:
        logger.error(f"Error obteniendo modelos: {e}", exc_info=True)
        return jsonify({'error': f'Error obteniendo modelos: {str(e)}'}), 500
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/models/current', methods=['GET'])
@login_required
def get_current_models():
    """
    Obtiene los modelos actuales (is_current=TRUE) de cada proveedor
    
    Returns:
        JSON con los modelos actuales por proveedor
        
    Example response:
        {
            "success": true,
            "models": {
                "openai": {"model_id": "gpt-5.2", "display_name": "GPT-5.2"},
                "anthropic": {"model_id": "claude-sonnet-4-5", "display_name": "Claude Sonnet 4.5"},
                "google": {"model_id": "gemini-3", "display_name": "Gemini 3"},
                "perplexity": {"model_id": "sonar", "display_name": "Perplexity Sonar"}
            }
        }
    """
    # Fallbacks por defecto (Model IDs correctos según docs oficiales)
    fallbacks = {
        'openai': {'model_id': 'gpt-5.1', 'display_name': 'GPT-5.1'},
        'anthropic': {'model_id': 'claude-sonnet-4-5-20250929', 'display_name': 'Claude Sonnet 4.5'},
        'google': {'model_id': 'gemini-3-pro-preview', 'display_name': 'Gemini 3 Pro'},
        'perplexity': {'model_id': 'sonar', 'display_name': 'Perplexity Sonar'}
    }
    
    conn = get_db_connection()
    if not conn:
        # Si no hay BD, devolver fallbacks
        return jsonify({
            'success': True,
            'models': fallbacks,
            'source': 'fallback'
        }), 200
    
    try:
        cur = conn.cursor()
        
        # Query con columnas que SÍ existen en la tabla
        cur.execute("""
            SELECT llm_provider, model_id, model_display_name
            FROM llm_model_registry
            WHERE is_current = TRUE AND is_available = TRUE
            ORDER BY llm_provider
        """)
        
        models = cur.fetchall()
        
        models_dict = {}
        for m in models:
            models_dict[m['llm_provider']] = {
                'model_id': m['model_id'],
                'display_name': m['model_display_name'] or m['model_id']
            }
        
        # Aplicar fallbacks para providers que no tienen modelo en BD
        for provider, fallback in fallbacks.items():
            if provider not in models_dict:
                models_dict[provider] = fallback
        
        return jsonify({
            'success': True,
            'models': models_dict,
            'source': 'database' if models else 'fallback'
        }), 200
        
    except Exception as e:
        logger.error(f"Error obteniendo modelos actuales: {e}", exc_info=True)
        # En caso de error, devolver fallbacks
        return jsonify({
            'success': True,
            'models': fallbacks,
            'source': 'fallback_error'
        }), 200
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/models/<int:model_id>', methods=['PUT'])
@admin_required
def update_model(model_id):
    """
    Actualiza un modelo LLM (solo admin)
    
    Body:
    {
        "cost_per_1m_input_tokens": 15.0,
        "cost_per_1m_output_tokens": 45.0,
        "is_current": true,
        "is_available": true
    }
    
    Returns:
        JSON con el modelo actualizado
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Body vacío'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a BD'}), 500
    
    try:
        cur = conn.cursor()
        
        updates = []
        params = []
        
        if 'cost_per_1m_input_tokens' in data:
            updates.append("cost_per_1m_input_tokens = %s")
            params.append(data['cost_per_1m_input_tokens'])
        
        if 'cost_per_1m_output_tokens' in data:
            updates.append("cost_per_1m_output_tokens = %s")
            params.append(data['cost_per_1m_output_tokens'])
        
        if 'is_current' in data:
            updates.append("is_current = %s")
            params.append(data['is_current'])
        
        if 'is_available' in data:
            updates.append("is_available = %s")
            params.append(data['is_available'])
        
        if not updates:
            return jsonify({'error': 'No hay campos para actualizar'}), 400
        
        updates.append("updated_at = NOW()")
        params.append(model_id)
        
        query = f"""
            UPDATE llm_model_registry
            SET {', '.join(updates)}
            WHERE id = %s
            RETURNING *
        """
        
        cur.execute(query, params)
        model = cur.fetchone()
        
        if not model:
            return jsonify({'error': 'Modelo no encontrado'}), 404
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'model': {
                'id': model['id'],
                'llm_provider': model['llm_provider'],
                'model_id': model['model_id'],
                'model_display_name': model['model_display_name'],
                'cost_per_1m_input_tokens': float(model['cost_per_1m_input_tokens']),
                'cost_per_1m_output_tokens': float(model['cost_per_1m_output_tokens']),
                'is_current': model['is_current'],
                'is_available': model['is_available'],
                'updated_at': model['updated_at'].isoformat() if model['updated_at'] else None
            }
        }), 200
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error actualizando modelo: {e}", exc_info=True)
        return jsonify({'error': f'Error actualizando modelo: {str(e)}'}), 500
    finally:
        cur.close()
        conn.close()


# ============================================================================
# CRON JOBS
# ============================================================================

@llm_monitoring_bp.route('/cron/daily-analysis', methods=['POST'])
@cron_or_auth_required
def trigger_daily_analysis():
    """
    Trigger para análisis diario automático (cron job)
    
    Query params:
        async (int): Si es 1, ejecuta en background y responde inmediatamente con 202
    
    Returns:
        JSON con resultado de la ejecución del cron
    """
    auth_error = _ensure_cron_token_or_admin()
    if auth_error:
        return auth_error

    try:
        # Verificar si se solicita ejecución asíncrona
        is_async = request.args.get('async', '0') == '1'
        
        if is_async:
            # Ejecutar en background y responder inmediatamente
            def run_analysis_in_background():
                try:
                    logger.info("🚀 LLM Monitoring: Starting daily analysis in background")
                    results = analyze_all_active_projects(
                        api_keys=None,  # Usar variables de entorno
                        max_workers=10
                    )
                    
                    # Procesar resultados
                    successful = sum(1 for r in results if 'error' not in r)
                    failed = sum(1 for r in results if 'error' in r)
                    total_queries = sum(r.get('total_queries_executed', 0) for r in results if 'error' not in r)
                    
                    logger.info(f"✅ LLM Monitoring: Daily analysis completed - {len(results)} projects processed")
                    logger.info(f"   Successful: {successful}, Failed: {failed}, Total queries: {total_queries}")
                except Exception as e:
                    logger.error(f"💥 LLM Monitoring: Background analysis error: {e}")
            
            # Iniciar thread en background
            thread = threading.Thread(target=run_analysis_in_background, daemon=True)
            thread.start()
            
            logger.info("📤 LLM Monitoring: Daily analysis triggered (async mode)")
            return jsonify({
                'success': True,
                'message': 'Daily analysis triggered in background',
                'async': True
            }), 202
        
        # Modo síncrono (comportamiento original)
        results = analyze_all_active_projects(
            api_keys=None,  # Usar variables de entorno
            max_workers=10
        )
        
        # Procesar resultados
        successful = sum(1 for r in results if 'error' not in r)
        failed = sum(1 for r in results if 'error' in r)
        total_queries = sum(r.get('total_queries_executed', 0) for r in results if 'error' not in r)
        
        return jsonify({
            'success': True,
            'total_projects': len(results),
            'successful': successful,
            'failed': failed,
            'total_queries': total_queries,
            'results': results
        }), 200
            
    except Exception as e:
        logger.error(f"Error in daily analysis cron trigger: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# HEALTH CHECK
# ============================================================================

@llm_monitoring_bp.route('/health', methods=['GET'])
def health_check():
    """
    Health check del sistema LLM Monitoring
    
    Returns:
        JSON con estado del sistema
    """
    try:
        # Verificar conexión a BD
        conn = get_db_connection()
        if not conn:
            return jsonify({
                'status': 'error',
                'database': 'disconnected'
            }), 503
        
        cur = conn.cursor()
        
        # Contar proyectos activos
        cur.execute("SELECT COUNT(*) as count FROM llm_monitoring_projects WHERE is_active = TRUE")
        active_projects = cur.fetchone()['count']
        
        # Verificar API keys disponibles
        api_keys_available = {
            'openai': bool(os.getenv('OPENAI_API_KEY')),
            'anthropic': bool(os.getenv('ANTHROPIC_API_KEY')),
            'google': bool(os.getenv('GOOGLE_API_KEY')),
            'perplexity': bool(os.getenv('PERPLEXITY_API_KEY'))
        }
        
        cur.close()
        conn.close()
        
        return jsonify({
            'status': 'ok',
            'database': 'connected',
            'active_projects': active_projects,
            'api_keys_configured': sum(api_keys_available.values()),
            'api_keys': api_keys_available
        }), 200
        
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@llm_monitoring_bp.route('/projects/<int:project_id>/responses', methods=['GET'])
@login_required
@validate_project_ownership
def get_project_responses(project_id):
    """
    Obtener respuestas detalladas de LLMs para inspección manual
    
    Query params:
        query_id: ID de query específica (opcional)
        llm_provider: Filtrar por proveedor (opcional)
        days: Días hacia atrás (default: 7)
    
    Returns:
        JSON con respuestas completas de cada LLM
    """
    query_id = request.args.get('query_id', type=int)
    llm_provider = request.args.get('llm_provider')
    days = _normalize_days_param(request.args.get('days'), default=7)
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a BD'}), 500
    
    try:
        cur = conn.cursor()

        cur.execute("""
            SELECT enabled_llms
            FROM llm_monitoring_projects
            WHERE id = %s
        """, (project_id,))
        project_row = cur.fetchone()
        if not project_row:
            return jsonify({'error': 'Proyecto no encontrado'}), 404
        enabled_llms_filter = project_row.get('enabled_llms') or []
        
        # Calcular rango de fechas
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Query base
        query = """
            SELECT 
                r.id,
                r.query_id,
                q.query_text,
                r.llm_provider,
                r.model_used,
                r.brand_mentioned,
                r.position_in_list,
                r.sentiment,
                r.mention_contexts,
                r.competitors_mentioned,
                r.full_response,
                r.response_length,
                r.sources,
                r.analysis_date,
                r.created_at
            FROM llm_monitoring_results r
            JOIN llm_monitoring_queries q ON r.query_id = q.id
            WHERE r.project_id = %s
                AND r.analysis_date >= %s
                AND r.analysis_date <= %s
        """
        
        params = [project_id, start_date, end_date]
        
        # Filtros opcionales
        if query_id:
            query += " AND r.query_id = %s"
            params.append(query_id)
        
        if llm_provider:
            query += " AND r.llm_provider = %s"
            params.append(llm_provider)
        elif enabled_llms_filter:
            query += " AND r.llm_provider = ANY(%s)"
            params.append(enabled_llms_filter)
        
        query += " ORDER BY r.analysis_date DESC, q.query_text, r.llm_provider"
        
        cur.execute(query, params)
        results = cur.fetchall()
        
        # Formatear resultados
        responses = []
        for r in results:
            responses.append({
                'id': r['id'],
                'query_id': r['query_id'],
                'query_text': r['query_text'],
                'llm_provider': r['llm_provider'],
                'model_used': r['model_used'],
                'brand_mentioned': r['brand_mentioned'],
                'position_in_list': r['position_in_list'],
                'sentiment': r['sentiment'],
                'mention_contexts': r['mention_contexts'] or [],
                'competitors_mentioned': r['competitors_mentioned'] or {},
                'full_response': r['full_response'],
                'response_length': r['response_length'],
                'sources': r['sources'] or [],  # ✨ NUEVO
                'analysis_date': r['analysis_date'].isoformat() if r['analysis_date'] else None,
                'created_at': r['created_at'].isoformat() if r['created_at'] else None
            })
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'responses': responses,
            'total': len(responses),
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': days
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error obteniendo respuestas: {e}", exc_info=True)
        return jsonify({'error': f'Error obteniendo respuestas: {str(e)}'}), 500


# ============================================================================
# EXPORTACIÓN DE DATOS - Excel y PDF
# ============================================================================

@llm_monitoring_bp.route('/projects/<int:project_id>/export/excel', methods=['GET'])
@login_required
@validate_project_ownership
def export_project_excel(project_id):
    """
    Exportar datos del proyecto a Excel
    
    Query params:
        days: int - Período de días (default: 30)
    """
    from io import BytesIO
    from flask import send_file
    
    logger.info(f"📥 Starting Excel export for project {project_id}")
    
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
        logger.info("✅ openpyxl imported successfully")
    except ImportError as e:
        logger.error(f"openpyxl no está instalado: {e}")
        return jsonify({'error': 'Excel export not available. Missing openpyxl library.'}), 500
    
    days = _normalize_days_param(request.args.get('days'), default=30)
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a BD'}), 500
    
    try:
        cur = conn.cursor()
        
        # Obtener datos del proyecto
        cur.execute("""
            SELECT name, industry, brand_domain, brand_keywords, language, country_code, enabled_llms
            FROM llm_monitoring_projects
            WHERE id = %s
        """, (project_id,))
        project = cur.fetchone()
        
        if not project:
            return jsonify({'error': 'Proyecto no encontrado'}), 404
        
        # Obtener métricas por LLM
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        enabled_llms_filter = project.get('enabled_llms') or []
        
        metrics_query = """
            SELECT 
                llm_provider,
                COUNT(DISTINCT query_id) as total_queries,
                SUM(CASE WHEN brand_mentioned THEN 1 ELSE 0 END) as total_mentions,
                ROUND(AVG(CASE WHEN brand_mentioned THEN 100.0 ELSE 0 END), 1) as mention_rate_pct,
                AVG(CASE WHEN sentiment = 'positive' THEN 1 WHEN sentiment = 'negative' THEN -1 ELSE 0 END) as avg_sentiment
            FROM llm_monitoring_results
            WHERE project_id = %s AND analysis_date >= %s AND analysis_date <= %s
        """
        metrics_params = [project_id, start_date, end_date]
        if enabled_llms_filter:
            metrics_query += " AND llm_provider = ANY(%s)"
            metrics_params.append(enabled_llms_filter)
        metrics_query += """
            GROUP BY llm_provider
            ORDER BY llm_provider
        """
        cur.execute(metrics_query, metrics_params)
        metrics = cur.fetchall()
        
        # Obtener queries con resultados
        export_country = project['country_code'] or 'Global'
        queries_export_query = """
            SELECT 
                q.query_text AS prompt,
                %s::text AS country,
                q.language,
                COUNT(DISTINCT r.llm_provider) as llms_analyzed,
                SUM(CASE WHEN r.brand_mentioned THEN 1 ELSE 0 END) as times_mentioned,
                AVG(r.position_in_list) as avg_position
            FROM llm_monitoring_queries q
            LEFT JOIN llm_monitoring_results r ON q.id = r.query_id AND r.analysis_date >= %s AND r.analysis_date <= %s
                {llm_filter}
            WHERE q.project_id = %s AND q.is_active = TRUE
            GROUP BY q.id, q.query_text, q.language
            ORDER BY times_mentioned DESC
        """.format(
            llm_filter="AND r.llm_provider = ANY(%s)" if enabled_llms_filter else ""
        )
        queries_export_params = [export_country, start_date, end_date]
        if enabled_llms_filter:
            queries_export_params.append(enabled_llms_filter)
        queries_export_params.append(project_id)
        cur.execute(queries_export_query, queries_export_params)
        queries = cur.fetchall()
        
        cur.close()
        conn.close()
        
        # Crear Excel
        wb = openpyxl.Workbook()
        
        # Estilos
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="161616", end_color="161616", fill_type="solid")
        accent_fill = PatternFill(start_color="D8F9B8", end_color="D8F9B8", fill_type="solid")
        border = Border(
            left=Side(style='thin', color='E5E7EB'),
            right=Side(style='thin', color='E5E7EB'),
            top=Side(style='thin', color='E5E7EB'),
            bottom=Side(style='thin', color='E5E7EB')
        )
        
        # === Hoja 1: Resumen del Proyecto ===
        ws_summary = wb.active
        ws_summary.title = "Project Summary"
        
        ws_summary['A1'] = "LLM Monitoring Report"
        ws_summary['A1'].font = Font(bold=True, size=16)
        ws_summary['A2'] = f"Project: {project['name']}"
        ws_summary['A3'] = f"Period: Last {days} days"
        ws_summary['A4'] = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        ws_summary['A6'] = "Project Details"
        ws_summary['A6'].font = Font(bold=True, size=12)
        ws_summary['A7'] = "Industry:"
        ws_summary['B7'] = project['industry'] or 'N/A'
        ws_summary['A8'] = "Brand Domain:"
        ws_summary['B8'] = project['brand_domain'] or 'N/A'
        ws_summary['A9'] = "Brand Keywords:"
        ws_summary['B9'] = ', '.join(project['brand_keywords']) if project['brand_keywords'] else 'N/A'
        ws_summary['A10'] = "Language:"
        ws_summary['B10'] = project['language'] or 'N/A'
        ws_summary['A11'] = "Country:"
        ws_summary['B11'] = project['country_code'] or 'N/A'
        
        # === Hoja 2: Métricas por LLM ===
        ws_metrics = wb.create_sheet("LLM Metrics")
        
        headers = ["LLM Provider", "Total Queries", "Total Mentions", "Mention Rate (%)", "Avg Sentiment"]
        for col, header in enumerate(headers, 1):
            cell = ws_metrics.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center')
            cell.border = border
        
        for row_idx, m in enumerate(metrics, 2):
            ws_metrics.cell(row=row_idx, column=1, value=m['llm_provider'].upper()).border = border
            ws_metrics.cell(row=row_idx, column=2, value=m['total_queries'] or 0).border = border
            ws_metrics.cell(row=row_idx, column=3, value=m['total_mentions'] or 0).border = border
            ws_metrics.cell(row=row_idx, column=4, value=round(float(m['mention_rate_pct'] or 0), 1)).border = border
            ws_metrics.cell(row=row_idx, column=5, value=round(float(m['avg_sentiment'] or 0), 2)).border = border
        
        # Ajustar anchos
        for col in range(1, 6):
            ws_metrics.column_dimensions[get_column_letter(col)].width = 20
        
        # === Hoja 3: Queries/Prompts ===
        ws_queries = wb.create_sheet("Prompts & Queries")
        
        headers = ["Prompt", "Country", "Language", "LLMs Analyzed", "Times Mentioned", "Avg Position"]
        for col, header in enumerate(headers, 1):
            cell = ws_queries.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center')
            cell.border = border
        
        for row_idx, q in enumerate(queries, 2):
            ws_queries.cell(row=row_idx, column=1, value=q['prompt']).border = border
            ws_queries.cell(row=row_idx, column=2, value=q['country']).border = border
            ws_queries.cell(row=row_idx, column=3, value=q['language']).border = border
            ws_queries.cell(row=row_idx, column=4, value=q['llms_analyzed']).border = border
            ws_queries.cell(row=row_idx, column=5, value=q['times_mentioned']).border = border
            ws_queries.cell(row=row_idx, column=6, value=round(float(q['avg_position'] or 0), 1) if q['avg_position'] else 'N/A').border = border
        
        # Ajustar anchos
        ws_queries.column_dimensions['A'].width = 60
        for col in range(2, 7):
            ws_queries.column_dimensions[get_column_letter(col)].width = 15
        
        # Guardar en memoria
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        
        filename = f"llm-monitoring-{project['name'].replace(' ', '-')}-{datetime.now().strftime('%Y%m%d')}.xlsx"
        
        logger.info(f"✅ Excel exportado para proyecto {project_id}")
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        logger.error(f"❌ Error exportando Excel para proyecto {project_id}: {e}", exc_info=True)
        return jsonify({'error': f'Error exportando Excel: {str(e)}'}), 500


@llm_monitoring_bp.route('/projects/<int:project_id>/export/pdf', methods=['GET'])
@login_required
@validate_project_ownership
def export_project_pdf(project_id):
    """
    Exportar datos del proyecto a PDF
    
    Query params:
        days: int - Período de días (default: 30)
    """
    from io import BytesIO
    from flask import send_file
    
    logger.info(f"📥 Starting PDF export for project {project_id}")
    
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch, cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        logger.info("✅ reportlab imported successfully")
    except ImportError as e:
        logger.error(f"reportlab no está instalado: {e}")
        return jsonify({'error': 'PDF export not available. Missing reportlab library.'}), 500
    
    days = _normalize_days_param(request.args.get('days'), default=30)
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a BD'}), 500
    
    try:
        cur = conn.cursor()
        
        # Obtener datos del proyecto
        cur.execute("""
            SELECT name, industry, brand_domain, brand_keywords, language, country_code, enabled_llms
            FROM llm_monitoring_projects
            WHERE id = %s
        """, (project_id,))
        project = cur.fetchone()
        
        if not project:
            return jsonify({'error': 'Proyecto no encontrado'}), 404
        
        # Obtener métricas por LLM
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        enabled_llms_filter = project.get('enabled_llms') or []
        
        pdf_metrics_query = """
            SELECT 
                llm_provider,
                COUNT(DISTINCT query_id) as total_queries,
                SUM(CASE WHEN brand_mentioned THEN 1 ELSE 0 END) as total_mentions,
                ROUND(AVG(CASE WHEN brand_mentioned THEN 100.0 ELSE 0 END), 1) as mention_rate_pct
            FROM llm_monitoring_results
            WHERE project_id = %s AND analysis_date >= %s AND analysis_date <= %s
        """
        pdf_metrics_params = [project_id, start_date, end_date]
        if enabled_llms_filter:
            pdf_metrics_query += " AND llm_provider = ANY(%s)"
            pdf_metrics_params.append(enabled_llms_filter)
        pdf_metrics_query += """
            GROUP BY llm_provider
            ORDER BY mention_rate_pct DESC
        """
        cur.execute(pdf_metrics_query, pdf_metrics_params)
        metrics = cur.fetchall()
        
        cur.close()
        conn.close()
        
        # Crear PDF
        output = BytesIO()
        doc = SimpleDocTemplate(
            output,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        styles = getSampleStyleSheet()
        
        # Estilos personalizados
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#161616'),
            spaceAfter=20
        )
        
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#374151'),
            spaceAfter=10
        )
        
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#4b5563'),
            spaceAfter=8
        )
        
        elements = []
        
        # Título
        elements.append(Paragraph("LLM Visibility Monitor Report", title_style))
        elements.append(Paragraph(f"Project: {project['name']}", subtitle_style))
        elements.append(Paragraph(f"Period: Last {days} days | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", body_style))
        elements.append(Spacer(1, 20))
        
        # Información del proyecto
        elements.append(Paragraph("Project Details", subtitle_style))
        project_info = [
            f"<b>Industry:</b> {project['industry'] or 'N/A'}",
            f"<b>Brand Domain:</b> {project['brand_domain'] or 'N/A'}",
            f"<b>Brand Keywords:</b> {', '.join(project['brand_keywords']) if project['brand_keywords'] else 'N/A'}",
            f"<b>Language:</b> {project['language'] or 'N/A'} | <b>Country:</b> {project['country_code'] or 'N/A'}"
        ]
        for info in project_info:
            elements.append(Paragraph(info, body_style))
        elements.append(Spacer(1, 20))
        
        # Tabla de métricas por LLM
        elements.append(Paragraph("LLM Performance Metrics", subtitle_style))
        
        if metrics:
            table_data = [["LLM", "Queries", "Mentions", "Mention Rate"]]
            for m in metrics:
                table_data.append([
                    m['llm_provider'].upper(),
                    str(m['total_queries'] or 0),
                    str(m['total_mentions'] or 0),
                    f"{round(float(m['mention_rate_pct'] or 0), 1)}%"
                ])
            
            table = Table(table_data, colWidths=[3*cm, 3*cm, 3*cm, 3*cm])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#161616')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F9FAFB')),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#374151')),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ]))
            elements.append(table)
        else:
            elements.append(Paragraph("No metrics data available for this period.", body_style))
        
        elements.append(Spacer(1, 30))
        
        # Footer
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#9ca3af'),
            alignment=TA_CENTER
        )
        elements.append(Paragraph("Generated by ClicAndSEO LLM Visibility Monitor", footer_style))
        
        # Construir PDF
        doc.build(elements)
        output.seek(0)
        
        filename = f"llm-monitoring-{project['name'].replace(' ', '-')}-{datetime.now().strftime('%Y%m%d')}.pdf"
        
        logger.info(f"✅ PDF exportado para proyecto {project_id}")
        
        return send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        logger.error(f"❌ Error exportando PDF para proyecto {project_id}: {e}", exc_info=True)
        return jsonify({'error': f'Error exportando PDF: {str(e)}'}), 500


# ============================================================================
# CRON: Model Discovery (cada 2 semanas)
# ============================================================================

def get_model_version_score(model_id: str) -> tuple:
    """
    Calcula un score de versión para comparar modelos.
    Retorna una tupla (major_version, date_score, model_id) para ordenar.
    
    Ejemplos:
        gpt-5.1 -> (5, 1, 99999999, 'gpt-5.1')
        gpt-5-2025-08-07 -> (5, 0, 20250807, 'gpt-5-2025-08-07')
        gpt-4o-2024-05-13 -> (4, 0, 20240513, 'gpt-4o-2024-05-13')
        gemini-3-pro-preview -> (3, 0, 99999999, 'gemini-3-pro-preview')
    """
    import re
    
    model_lower = model_id.lower()
    
    # Extraer versión principal (gpt-5, gpt-4, gemini-3, etc.)
    major = 0
    if 'gpt-5' in model_lower or 'gpt5' in model_lower:
        major = 5
    elif 'gpt-4.1' in model_lower:
        major = 4.1
    elif 'gpt-4' in model_lower or 'gpt4' in model_lower:
        major = 4
    elif 'o3' in model_lower:
        major = 6  # o3 es más nuevo que gpt-5
    elif 'o1' in model_lower:
        major = 5.5  # o1 está entre gpt-5 y o3
    elif 'gemini-3' in model_lower:
        major = 3
    elif 'gemini-2' in model_lower:
        major = 2
    elif 'gemini-1' in model_lower:
        major = 1
    elif 'claude-sonnet-4' in model_lower or 'claude-4' in model_lower:
        major = 4
    elif 'claude-3' in model_lower:
        major = 3
    elif 'sonar-pro' in model_lower:
        major = 2
    elif 'sonar-reasoning' in model_lower:
        major = 3
    elif 'sonar' in model_lower:
        major = 1
    
    # Extraer sub-versión (.1, .5, etc.)
    sub_version = 0
    sub_match = re.search(r'gpt-(\d+)\.(\d+)', model_lower)
    if sub_match:
        sub_version = int(sub_match.group(2))
    
    # Extraer fecha (YYYY-MM-DD o YYYYMMDD)
    date_score = 0
    date_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', model_id)
    if date_match:
        date_score = int(f"{date_match.group(1)}{date_match.group(2)}{date_match.group(3)}")
    else:
        # Si no tiene fecha, asumir que es el "latest" (muy reciente)
        if 'preview' in model_lower or 'latest' in model_lower:
            date_score = 99999998
        else:
            date_score = 99999999
    
    return (major, sub_version, date_score, model_id)


def is_model_newer(new_model_id: str, current_model_id: str) -> bool:
    """Determina si new_model_id es más nuevo que current_model_id."""
    new_score = get_model_version_score(new_model_id)
    current_score = get_model_version_score(current_model_id)
    
    # Comparar: (major, sub_version, date_score)
    return (new_score[0], new_score[1], new_score[2]) > (current_score[0], current_score[1], current_score[2])


@llm_monitoring_bp.route('/cron/model-discovery', methods=['POST'])
@cron_or_auth_required
def cron_model_discovery():
    """
    Endpoint para CRON de descubrimiento de modelos LLM.
    
    Este endpoint:
    1. Consulta las APIs de cada proveedor para detectar nuevos modelos
    2. Compara versiones para identificar modelos MÁS NUEVOS vs MÁS ANTIGUOS
    3. Solo notifica sobre modelos realmente más nuevos
    4. Envía email de notificación con el resumen
    
    Llamar cada 2 semanas desde Railway Function-bun.
    
    Query params:
        - notify_email: Email para notificación (default: info@soycarlosgonzalez.com)
        - auto_update: true/false - Activar automáticamente nuevos modelos (default: false)
    
    Returns:
        JSON con resultados del descubrimiento
    """
    auth_error = _ensure_cron_token_or_admin()
    if auth_error:
        return auth_error

    import openai
    import google.generativeai as genai
    
    notify_email = request.args.get('notify_email', 'info@soycarlosgonzalez.com')
    auto_update = request.args.get('auto_update', 'false').lower() == 'true'
    
    logger.info("=" * 60)
    logger.info("🔍 CRON: Iniciando descubrimiento de modelos LLM...")
    logger.info(f"   Notify email: {notify_email}")
    logger.info(f"   Auto-update: {auto_update}")
    logger.info("=" * 60)
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a BD'}), 500
    
    try:
        cur = conn.cursor()
        
        # 1. Obtener modelos actuales de BD
        cur.execute("""
            SELECT llm_provider, model_id, model_display_name, is_current
            FROM llm_model_registry
            ORDER BY llm_provider, is_current DESC
        """)
        db_models = cur.fetchall()
        
        current_models = {}
        known_model_ids = set()
        for m in db_models:
            known_model_ids.add(m['model_id'])
            if m['is_current']:
                current_models[m['llm_provider']] = m['model_id']
        
        logger.info(f"📊 Modelos actuales en BD: {current_models}")
        
        # 2. Descubrir modelos de cada proveedor
        discovered_models = []
        newer_models = []      # Modelos MÁS NUEVOS que el actual
        older_models = []      # Modelos MÁS ANTIGUOS que el actual
        same_or_known = []     # Modelos ya conocidos
        errors = []
        
        # OpenAI - Solo buscar modelos de la familia GPT-5 y O-series (más recientes)
        try:
            openai_key = os.getenv('OPENAI_API_KEY')
            if openai_key:
                client = openai.OpenAI(api_key=openai_key)
                models = client.models.list()
                current_openai = current_models.get('openai', 'gpt-5.1')
                
                for m in models.data:
                    # Solo modelos GPT relevantes
                    if any(p in m.id.lower() for p in ['gpt-5', 'gpt-4', 'o1', 'o3']):
                        discovered_models.append({'provider': 'openai', 'model_id': m.id})
                        
                        if m.id not in known_model_ids:
                            model_info = {'provider': 'openai', 'model_id': m.id, 'display_name': m.id}
                            
                            if is_model_newer(m.id, current_openai):
                                model_info['status'] = 'NEWER'
                                newer_models.append(model_info)
                            else:
                                model_info['status'] = 'OLDER'
                                older_models.append(model_info)
                        else:
                            same_or_known.append({'provider': 'openai', 'model_id': m.id, 'status': 'KNOWN'})
                            
                logger.info(f"✅ OpenAI: Consultado correctamente")
        except Exception as e:
            errors.append(f"OpenAI: {str(e)[:100]}")
            logger.error(f"❌ OpenAI error: {e}")
        
        # Google
        try:
            google_key = os.getenv('GOOGLE_AI_API_KEY') or os.getenv('GOOGLE_API_KEY')
            if google_key:
                genai.configure(api_key=google_key)
                models = genai.list_models()
                current_google = current_models.get('google', 'gemini-3-pro-preview')
                
                for m in models:
                    if 'gemini' in m.name.lower():
                        model_id = m.name.split('/')[-1] if '/' in m.name else m.name
                        display = getattr(m, 'display_name', model_id)
                        discovered_models.append({'provider': 'google', 'model_id': model_id})
                        
                        if model_id not in known_model_ids:
                            model_info = {'provider': 'google', 'model_id': model_id, 'display_name': display}
                            
                            if is_model_newer(model_id, current_google):
                                model_info['status'] = 'NEWER'
                                newer_models.append(model_info)
                            else:
                                model_info['status'] = 'OLDER'
                                older_models.append(model_info)
                                
                logger.info(f"✅ Google: Consultado correctamente")
        except Exception as e:
            errors.append(f"Google: {str(e)[:100]}")
            logger.error(f"❌ Google error: {e}")
        
        # Perplexity (lista estática)
        perplexity_models = ['sonar', 'sonar-pro', 'sonar-reasoning']
        current_perplexity = current_models.get('perplexity', 'sonar')
        for model_id in perplexity_models:
            discovered_models.append({'provider': 'perplexity', 'model_id': model_id})
            if model_id not in known_model_ids:
                model_info = {'provider': 'perplexity', 'model_id': model_id, 'display_name': f'Perplexity {model_id.title()}'}
                if is_model_newer(model_id, current_perplexity):
                    model_info['status'] = 'NEWER'
                    newer_models.append(model_info)
                else:
                    model_info['status'] = 'OLDER'
                    older_models.append(model_info)
        
        # 3. Añadir SOLO modelos más nuevos a BD (los antiguos se ignoran)
        models_added = []
        for model in newer_models:
            try:
                cur.execute("""
                    INSERT INTO llm_model_registry (llm_provider, model_id, model_display_name, is_current, is_available)
                    VALUES (%s, %s, %s, %s, TRUE)
                    ON CONFLICT (llm_provider, model_id) DO NOTHING
                """, (model['provider'], model['model_id'], model['display_name'], auto_update))
                
                if cur.rowcount > 0:
                    models_added.append(model)
                    logger.info(f"   ✅ Añadido (NUEVO): {model['provider']} / {model['model_id']}")
                    
                    if auto_update:
                        cur.execute("""
                            UPDATE llm_model_registry SET is_current = FALSE
                            WHERE llm_provider = %s AND model_id != %s
                        """, (model['provider'], model['model_id']))
                        logger.info(f"   🔄 Activado como modelo actual")
                        
            except Exception as e:
                logger.error(f"   ❌ Error añadiendo {model['model_id']}: {e}")
        
        conn.commit()
        
        # 4. Obtener estado final
        cur.execute("""
            SELECT llm_provider, model_id, model_display_name
            FROM llm_model_registry
            WHERE is_current = TRUE
            ORDER BY llm_provider
        """)
        final_models = {row['llm_provider']: row['model_id'] for row in cur.fetchall()}
        
        # 5. Enviar email de notificación
        email_sent = False
        if notify_email:
            try:
                from email_service import send_email
                
                # Construir contenido del email
                subject = "🤖 LLM Model Discovery Report - Todo actualizado ✅"
                if newer_models:
                    subject = f"🆕 {len(newer_models)} modelos MÁS NUEVOS detectados - ¡Acción requerida!"
                
                html_body = f"""
                <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h1 style="color: #161616; border-bottom: 3px solid #D8F9B8; padding-bottom: 10px;">
                        🔍 LLM Model Discovery Report
                    </h1>
                    
                    <p style="color: #666;">Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC</p>
                    
                    <h2 style="color: #161616;">📊 Modelos Actuales en tu APP</h2>
                    <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                        <tr style="background: #161616; color: #D8F9B8;">
                            <th style="padding: 10px; text-align: left;">Proveedor</th>
                            <th style="padding: 10px; text-align: left;">Modelo Activo</th>
                        </tr>
                """
                
                for provider, model_id in final_models.items():
                    html_body += f"""
                        <tr style="border-bottom: 1px solid #eee;">
                            <td style="padding: 10px;">{provider.upper()}</td>
                            <td style="padding: 10px;"><code>{model_id}</code></td>
                        </tr>
                    """
                
                html_body += "</table>"
                
                # Modelos MÁS NUEVOS (importante!)
                if newer_models:
                    html_body += f"""
                    <h2 style="color: #22c55e;">🚀 Modelos MÁS NUEVOS Detectados ({len(newer_models)})</h2>
                    <p style="color: #666; font-size: 14px;">Estos modelos son más recientes que los que tienes activos:</p>
                    <ul style="background: #f0fdf4; padding: 15px 15px 15px 35px; border-radius: 8px; border-left: 4px solid #22c55e;">
                    """
                    for m in newer_models:
                        status = "✅ Activado automáticamente" if auto_update else "⏳ Pendiente de activar"
                        html_body += f"<li><strong>{m['provider'].upper()}</strong>: <code>{m['model_id']}</code> - {status}</li>"
                    html_body += "</ul>"
                    
                    if not auto_update:
                        html_body += """
                        <p style="background: #fef3c7; padding: 15px; border-radius: 8px; color: #92400e;">
                            ⚠️ <strong>Acción recomendada:</strong> Hay modelos más nuevos disponibles.
                            Considera actualizar ejecutando: <code>python update_models_now.py</code>
                        </p>
                        """
                else:
                    html_body += """
                    <div style="background: #f0fdf4; padding: 20px; border-radius: 8px; text-align: center; border-left: 4px solid #22c55e;">
                        <p style="color: #166534; margin: 0; font-weight: 600;">
                            ✅ ¡Tu APP está usando los modelos más recientes!
                        </p>
                        <p style="color: #666; margin: 10px 0 0 0; font-size: 14px;">
                            No se detectaron modelos más nuevos que los que tienes activos.
                        </p>
                    </div>
                    """
                
                # Modelos MÁS ANTIGUOS (solo informativo)
                if older_models:
                    html_body += f"""
                    <details style="margin-top: 20px;">
                        <summary style="cursor: pointer; color: #666; font-size: 14px;">
                            📁 {len(older_models)} modelos más antiguos detectados (no añadidos)
                        </summary>
                        <ul style="background: #f9fafb; padding: 15px 15px 15px 35px; border-radius: 8px; color: #666; font-size: 13px; margin-top: 10px;">
                    """
                    for m in older_models[:10]:  # Solo mostrar los primeros 10
                        html_body += f"<li>{m['provider']}: {m['model_id']}</li>"
                    if len(older_models) > 10:
                        html_body += f"<li>... y {len(older_models) - 10} más</li>"
                    html_body += "</ul></details>"
                
                if errors:
                    html_body += f"""
                    <h3 style="color: #dc2626; margin-top: 20px;">⚠️ Errores durante el descubrimiento</h3>
                    <ul style="color: #666; font-size: 14px;">
                    """
                    for err in errors:
                        html_body += f"<li>{err}</li>"
                    html_body += "</ul>"
                
                html_body += f"""
                    <hr style="margin: 30px 0; border: none; border-top: 1px solid #eee;">
                    <p style="color: #999; font-size: 12px; text-align: center;">
                        ClicAndSEO - LLM Visibility Monitor<br>
                        Este email se envía automáticamente cada 2 semanas.<br>
                        <small>Total modelos escaneados: {len(discovered_models)}</small>
                    </p>
                </div>
                """
                
                send_email(notify_email, subject, html_body)
                email_sent = True
                logger.info(f"📧 Email enviado a {notify_email}")
                
            except Exception as e:
                logger.error(f"❌ Error enviando email: {e}")
        
        logger.info("=" * 60)
        logger.info(f"✅ Descubrimiento completado")
        logger.info(f"   Modelos descubiertos: {len(discovered_models)}")
        logger.info(f"   Modelos MÁS NUEVOS: {len(newer_models)}")
        logger.info(f"   Modelos más antiguos (ignorados): {len(older_models)}")
        logger.info(f"   Modelos añadidos a BD: {len(models_added)}")
        logger.info("=" * 60)
        
        return jsonify({
            'success': True,
            'message': 'Model discovery completed',
            'discovered_count': len(discovered_models),
            'newer_models': newer_models,      # Solo modelos MÁS NUEVOS que los actuales
            'older_models_count': len(older_models),  # Cuántos modelos antiguos se ignoraron
            'models_added': models_added,
            'current_models': final_models,
            'email_sent': email_sent,
            'errors': errors,
            'summary': {
                'app_is_updated': len(newer_models) == 0,
                'action_required': len(newer_models) > 0 and not auto_update
            }
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error en model discovery: {e}", exc_info=True)
        return jsonify({'error': f'Error en model discovery: {str(e)}'}), 500
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/cron/alert', methods=['POST'])
@cron_or_auth_required
def cron_alert():
    """
    Endpoint para alertas de cron (fallos o warnings).
    Reutiliza el sistema de email existente.
    
    Payload JSON opcional:
        - notify_email
        - job_name
        - status (failed|warning|ok)
        - message
        - endpoint
        - response_status
        - response_body
        - run_at
    """
    auth_error = _ensure_cron_token_or_admin()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    
    notify_email = (
        data.get('notify_email')
        or request.args.get('notify_email')
        or os.getenv('CRON_ALERT_EMAIL')
        or os.getenv('MODEL_DISCOVERY_EMAIL')
        or 'info@soycarlosgonzalez.com'
    )
    
    job_name = data.get('job_name') or 'Cron'
    status = (data.get('status') or 'failed').lower()
    message = data.get('message') or 'Fallo no especificado'
    endpoint = data.get('endpoint') or ''
    response_status = data.get('response_status')
    response_body = data.get('response_body') or ''
    run_at = data.get('run_at') or datetime.utcnow().isoformat()
    
    def _truncate(value: str, max_len: int = 2000) -> str:
        if value is None:
            return ''
        text = str(value)
        if len(text) <= max_len:
            return text
        return text[:max_len] + "…"
    
    status_icon = "🚨" if status == "failed" else "⚠️" if status == "warning" else "✅"
    subject = f"{status_icon} Cron {status.upper()}: {job_name}"
    
    html_body = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto;">
        <h1 style="color: #161616; border-bottom: 3px solid #D8F9B8; padding-bottom: 10px;">
            {status_icon} Alerta de Cron
        </h1>
        <p style="color: #666;">Fecha: {run_at} UTC</p>
        <table style="width: 100%; border-collapse: collapse; margin-bottom: 16px;">
            <tr style="background: #161616; color: #D8F9B8;">
                <th style="padding: 10px; text-align: left;">Campo</th>
                <th style="padding: 10px; text-align: left;">Valor</th>
            </tr>
            <tr style="border-bottom: 1px solid #eee;">
                <td style="padding: 10px;">Job</td>
                <td style="padding: 10px;">{job_name}</td>
            </tr>
            <tr style="border-bottom: 1px solid #eee;">
                <td style="padding: 10px;">Estado</td>
                <td style="padding: 10px;">{status.upper()}</td>
            </tr>
            <tr style="border-bottom: 1px solid #eee;">
                <td style="padding: 10px;">Endpoint</td>
                <td style="padding: 10px;">{_truncate(endpoint, 300)}</td>
            </tr>
            <tr style="border-bottom: 1px solid #eee;">
                <td style="padding: 10px;">HTTP Status</td>
                <td style="padding: 10px;">{response_status}</td>
            </tr>
        </table>
        <h3 style="color: #161616;">Mensaje</h3>
        <pre style="background: #f9fafb; padding: 12px; border-radius: 8px; white-space: pre-wrap; word-break: break-word;">{_truncate(message)}</pre>
        <h3 style="color: #161616;">Respuesta</h3>
        <pre style="background: #f9fafb; padding: 12px; border-radius: 8px; white-space: pre-wrap; word-break: break-word;">{_truncate(response_body)}</pre>
        <hr style="margin: 24px 0; border: none; border-top: 1px solid #eee;">
        <p style="color: #999; font-size: 12px; text-align: center;">
            ClicAndSEO - Alerta automática de cron
        </p>
    </div>
    """
    
    email_sent = False
    if notify_email:
        try:
            from email_service import send_email
            email_sent = send_email(notify_email, subject, html_body)
            logger.info(f"📧 Alerta de cron enviada a {notify_email}")
        except Exception as e:
            logger.error(f"❌ Error enviando alerta de cron: {e}")
    
    return jsonify({
        'success': True,
        'email_sent': email_sent,
        'notify_email': notify_email,
        'job_name': job_name,
        'status': status
    }), 200


logger.info("✅ LLM Monitoring Blueprint loaded successfully")
