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
    POST   /api/llm-monitoring/projects/:id/analyze   - Análisis manual
    GET    /api/llm-monitoring/projects/:id/metrics   - Métricas detalladas
    GET    /api/llm-monitoring/projects/:id/comparison - Comparativa LLMs
    GET    /api/llm-monitoring/models                 - Listar modelos LLM disponibles
    PUT    /api/llm-monitoring/models/:id             - Actualizar modelo (admin)
    GET    /api/llm-monitoring/health                 - Health check del sistema
"""

import logging
import os
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from functools import wraps

# Importar sistema de autenticación
from auth import login_required, get_current_user

# Importar servicios
from database import get_db_connection
from services.llm_monitoring_service import MultiLLMMonitoringService, analyze_all_active_projects

# Configurar logging
logger = logging.getLogger(__name__)

# Crear Blueprint
llm_monitoring_bp = Blueprint('llm_monitoring', __name__, url_prefix='/api/llm-monitoring')


# ============================================================================
# DECORADORES AUXILIARES
# ============================================================================

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
            logger.error(f"Error validando ownership: {e}")
            return jsonify({'error': 'Error validando permisos'}), 500
        finally:
            cur.close()
            conn.close()
    
    return decorated_function


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
                p.industry,
                p.enabled_llms,
                p.competitors,
                p.language,
                p.queries_per_llm,
                p.is_active,
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
                'industry': project['industry'],
                'enabled_llms': project['enabled_llms'],
                'competitors': project['competitors'],
                'language': project['language'],
                'queries_per_llm': project['queries_per_llm'],
                'is_active': project['is_active'],
                'last_analysis_date': project['last_analysis_date'].isoformat() if project['last_analysis_date'] else None,
                'created_at': project['created_at'].isoformat() if project['created_at'] else None,
                'updated_at': project['updated_at'].isoformat() if project['updated_at'] else None,
                'total_snapshots': project['total_snapshots'],
                'last_snapshot_date': project['last_snapshot_date'].isoformat() if project['last_snapshot_date'] else None
            })
        
        return jsonify({
            'success': True,
            'projects': projects_list,
            'total': len(projects_list)
        }), 200
        
    except Exception as e:
        logger.error(f"Error obteniendo proyectos: {e}", exc_info=True)
        return jsonify({'error': f'Error obteniendo proyectos: {str(e)}'}), 500
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/projects', methods=['POST'])
@login_required
def create_project():
    """
    Crea un nuevo proyecto de monitorización
    
    Body esperado:
    {
        "name": "Mi Marca SEO",
        "brand_name": "MiMarca",
        "industry": "SEO tools",
        "competitors": ["Semrush", "Ahrefs"],
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
    
    data = request.get_json()
    
    # Validar campos requeridos
    required_fields = ['name', 'brand_name', 'industry']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Campo requerido: {field}'}), 400
    
    # Valores por defecto
    competitors = data.get('competitors', [])
    language = data.get('language', 'es')
    enabled_llms = data.get('enabled_llms', ['openai', 'anthropic', 'google', 'perplexity'])
    queries_per_llm = data.get('queries_per_llm', 15)
    
    # Validaciones
    if len(data['brand_name']) < 2:
        return jsonify({'error': 'brand_name debe tener al menos 2 caracteres'}), 400
    
    if queries_per_llm < 5 or queries_per_llm > 50:
        return jsonify({'error': 'queries_per_llm debe estar entre 5 y 50'}), 400
    
    if not isinstance(enabled_llms, list) or len(enabled_llms) == 0:
        return jsonify({'error': 'enabled_llms debe ser un array con al menos 1 LLM'}), 400
    
    valid_llms = ['openai', 'anthropic', 'google', 'perplexity']
    if not all(llm in valid_llms for llm in enabled_llms):
        return jsonify({'error': f'LLMs válidos: {valid_llms}'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a BD'}), 500
    
    try:
        cur = conn.cursor()
        
        # Verificar que no exista proyecto con ese nombre para el usuario
        cur.execute("""
            SELECT id FROM llm_monitoring_projects
            WHERE user_id = %s AND name = %s
        """, (user['id'], data['name']))
        
        if cur.fetchone():
            return jsonify({'error': 'Ya tienes un proyecto con ese nombre'}), 409
        
        # Insertar proyecto
        cur.execute("""
            INSERT INTO llm_monitoring_projects (
                user_id, name, brand_name, industry,
                enabled_llms, competitors, language, queries_per_llm,
                is_active, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                TRUE, NOW(), NOW()
            )
            RETURNING id, created_at
        """, (
            user['id'],
            data['name'],
            data['brand_name'],
            data['industry'],
            enabled_llms,
            competitors,
            language,
            queries_per_llm
        ))
        
        result = cur.fetchone()
        project_id = result['id']
        created_at = result['created_at']
        
        # Generar queries iniciales
        from services.llm_monitoring_service import MultiLLMMonitoringService
        
        # Crear servicio (sin API keys, solo para generar queries)
        queries = []
        try:
            # Generar queries sin necesidad de inicializar proveedores
            service_queries = MultiLLMMonitoringService({}).generate_queries_for_project(
                brand_name=data['brand_name'],
                industry=data['industry'],
                language=language,
                competitors=competitors,
                count=queries_per_llm
            )
            
            # Insertar queries en BD
            for query_data in service_queries:
                cur.execute("""
                    INSERT INTO llm_monitoring_queries (
                        project_id, query_text, language, query_type, created_at
                    ) VALUES (%s, %s, %s, %s, NOW())
                    RETURNING id
                """, (
                    project_id,
                    query_data['query_text'],
                    query_data['language'],
                    query_data['query_type']
                ))
                
                query_id = cur.fetchone()['id']
                queries.append({
                    'id': query_id,
                    'query_text': query_data['query_text'],
                    'query_type': query_data['query_type']
                })
        
        except Exception as e:
            logger.warning(f"No se pudieron generar queries automáticas: {e}")
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'project': {
                'id': project_id,
                'name': data['name'],
                'brand_name': data['brand_name'],
                'industry': data['industry'],
                'enabled_llms': enabled_llms,
                'competitors': competitors,
                'language': language,
                'queries_per_llm': queries_per_llm,
                'is_active': True,
                'created_at': created_at.isoformat(),
                'total_queries_generated': len(queries)
            },
            'queries': queries[:5]  # Retornar solo las primeras 5 como ejemplo
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
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a BD'}), 500
    
    try:
        cur = conn.cursor()
        
        # Obtener proyecto
        cur.execute("""
            SELECT 
                p.*,
                COUNT(DISTINCT q.id) as total_queries,
                COUNT(DISTINCT s.id) as total_snapshots,
                MAX(s.snapshot_date) as last_snapshot_date
            FROM llm_monitoring_projects p
            LEFT JOIN llm_monitoring_queries q ON p.id = q.project_id
            LEFT JOIN llm_monitoring_snapshots s ON p.id = s.project_id
            WHERE p.id = %s
            GROUP BY p.id
        """, (project_id,))
        
        project = cur.fetchone()
        
        if not project:
            return jsonify({'error': 'Proyecto no encontrado'}), 404
        
        # Obtener últimas métricas de cada LLM
        cur.execute("""
            SELECT 
                llm_provider,
                mention_rate,
                avg_position,
                share_of_voice,
                sentiment_positive_pct,
                sentiment_neutral_pct,
                sentiment_negative_pct,
                total_queries_analyzed,
                snapshot_date
            FROM llm_monitoring_snapshots
            WHERE project_id = %s
            ORDER BY snapshot_date DESC, llm_provider
            LIMIT 4
        """, (project_id,))
        
        latest_metrics = cur.fetchall()
        
        # Formatear métricas
        metrics_by_llm = {}
        for metric in latest_metrics:
            metrics_by_llm[metric['llm_provider']] = {
                'mention_rate': float(metric['mention_rate']) if metric['mention_rate'] else 0,
                'avg_position': float(metric['avg_position']) if metric['avg_position'] else None,
                'share_of_voice': float(metric['share_of_voice']) if metric['share_of_voice'] else 0,
                'sentiment': {
                    'positive': float(metric['sentiment_positive_pct']) if metric['sentiment_positive_pct'] else 0,
                    'neutral': float(metric['sentiment_neutral_pct']) if metric['sentiment_neutral_pct'] else 0,
                    'negative': float(metric['sentiment_negative_pct']) if metric['sentiment_negative_pct'] else 0
                },
                'total_queries': metric['total_queries_analyzed'],
                'date': metric['snapshot_date'].isoformat() if metric['snapshot_date'] else None
            }
        
        return jsonify({
            'success': True,
            'project': {
                'id': project['id'],
                'name': project['name'],
                'brand_name': project['brand_name'],
                'industry': project['industry'],
                'enabled_llms': project['enabled_llms'],
                'competitors': project['competitors'],
                'language': project['language'],
                'queries_per_llm': project['queries_per_llm'],
                'is_active': project['is_active'],
                'last_analysis_date': project['last_analysis_date'].isoformat() if project['last_analysis_date'] else None,
                'created_at': project['created_at'].isoformat() if project['created_at'] else None,
                'updated_at': project['updated_at'].isoformat() if project['updated_at'] else None,
                'total_queries': project['total_queries'],
                'total_snapshots': project['total_snapshots'],
                'last_snapshot_date': project['last_snapshot_date'].isoformat() if project['last_snapshot_date'] else None
            },
            'latest_metrics': metrics_by_llm
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
        "is_active": false,
        "enabled_llms": ["openai", "google"],
        "competitors": ["Nuevo Competidor"],
        "queries_per_llm": 20
    }
    
    Returns:
        JSON con el proyecto actualizado
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Body vacío'}), 400
    
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
        
        if 'is_active' in data:
            updates.append("is_active = %s")
            params.append(data['is_active'])
        
        if 'enabled_llms' in data:
            # Validar LLMs
            valid_llms = ['openai', 'anthropic', 'google', 'perplexity']
            if not all(llm in valid_llms for llm in data['enabled_llms']):
                return jsonify({'error': f'LLMs válidos: {valid_llms}'}), 400
            updates.append("enabled_llms = %s")
            params.append(data['enabled_llms'])
        
        if 'competitors' in data:
            updates.append("competitors = %s")
            params.append(data['competitors'])
        
        if 'queries_per_llm' in data:
            if data['queries_per_llm'] < 5 or data['queries_per_llm'] > 50:
                return jsonify({'error': 'queries_per_llm debe estar entre 5 y 50'}), 400
            updates.append("queries_per_llm = %s")
            params.append(data['queries_per_llm'])
        
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
                'industry': project['industry'],
                'enabled_llms': project['enabled_llms'],
                'competitors': project['competitors'],
                'language': project['language'],
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


@llm_monitoring_bp.route('/projects/<int:project_id>', methods=['DELETE'])
@login_required
@validate_project_ownership
def delete_project(project_id):
    """
    Elimina un proyecto (soft delete: marca is_active = false)
    
    Returns:
        JSON con confirmación
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a BD'}), 500
    
    try:
        cur = conn.cursor()
        
        # Soft delete: marcar como inactivo
        cur.execute("""
            UPDATE llm_monitoring_projects
            SET is_active = FALSE, updated_at = NOW()
            WHERE id = %s
            RETURNING id, name
        """, (project_id,))
        
        project = cur.fetchone()
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'Proyecto "{project["name"]}" marcado como inactivo',
            'project_id': project['id']
        }), 200
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error eliminando proyecto: {e}", exc_info=True)
        return jsonify({'error': f'Error eliminando proyecto: {str(e)}'}), 500
    finally:
        cur.close()
        conn.close()


# ============================================================================
# ENDPOINTS: ANÁLISIS
# ============================================================================

@llm_monitoring_bp.route('/projects/<int:project_id>/analyze', methods=['POST'])
@login_required
@validate_project_ownership
def analyze_project(project_id):
    """
    Lanza análisis manual inmediato de un proyecto
    
    Query params opcionales:
        max_workers: Número de workers paralelos (default: 10)
    
    Returns:
        JSON con resultados del análisis
    """
    user = get_current_user()
    
    # Obtener API keys (primero de variables de entorno)
    api_keys = {}
    
    if os.getenv('OPENAI_API_KEY'):
        api_keys['openai'] = os.getenv('OPENAI_API_KEY')
    if os.getenv('ANTHROPIC_API_KEY'):
        api_keys['anthropic'] = os.getenv('ANTHROPIC_API_KEY')
    if os.getenv('GOOGLE_API_KEY'):
        api_keys['google'] = os.getenv('GOOGLE_API_KEY')
    if os.getenv('PERPLEXITY_API_KEY'):
        api_keys['perplexity'] = os.getenv('PERPLEXITY_API_KEY')
    
    if not api_keys:
        return jsonify({
            'error': 'No hay API keys configuradas',
            'hint': 'Configura OPENAI_API_KEY, GOOGLE_API_KEY, etc. en variables de entorno'
        }), 503
    
    max_workers = request.args.get('max_workers', 10, type=int)
    
    try:
        # Crear servicio
        service = MultiLLMMonitoringService(api_keys)
        
        # Ejecutar análisis
        logger.info(f"Iniciando análisis manual del proyecto {project_id} por usuario {user['id']}")
        
        result = service.analyze_project(
            project_id=project_id,
            max_workers=max_workers
        )
        
        return jsonify({
            'success': True,
            'message': 'Análisis completado',
            'results': result
        }), 200
        
    except Exception as e:
        logger.error(f"Error en análisis manual: {e}", exc_info=True)
        return jsonify({'error': f'Error en análisis: {str(e)}'}), 500


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
    end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    start_date = request.args.get('start_date', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    llm_provider = request.args.get('llm_provider')
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a BD'}), 500
    
    try:
        cur = conn.cursor()
        
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
        
        query += " ORDER BY s.snapshot_date DESC, s.llm_provider"
        
        cur.execute(query, params)
        snapshots = cur.fetchall()
        
        # Formatear snapshots
        snapshots_list = []
        for s in snapshots:
            snapshots_list.append({
                'id': s['id'],
                'llm_provider': s['llm_provider'],
                'snapshot_date': s['snapshot_date'].isoformat() if s['snapshot_date'] else None,
                'mention_rate': float(s['mention_rate']) if s['mention_rate'] else 0,
                'avg_position': float(s['avg_position']) if s['avg_position'] else None,
                'top3_count': s['top3_count'],
                'top5_count': s['top5_count'],
                'top10_count': s['top10_count'],
                'share_of_voice': float(s['share_of_voice']) if s['share_of_voice'] else 0,
                'sentiment': {
                    'positive': float(s['sentiment_positive_pct']) if s['sentiment_positive_pct'] else 0,
                    'neutral': float(s['sentiment_neutral_pct']) if s['sentiment_neutral_pct'] else 0,
                    'negative': float(s['sentiment_negative_pct']) if s['sentiment_negative_pct'] else 0
                },
                'total_queries': s['total_queries_analyzed'],
                'total_cost': float(s['total_cost_usd']) if s['total_cost_usd'] else 0
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


@llm_monitoring_bp.route('/projects/<int:project_id>/comparison', methods=['GET'])
@login_required
@validate_project_ownership
def get_llm_comparison(project_id):
    """
    Comparativa entre LLMs para un proyecto (usa vista llm_visibility_comparison)
    
    Returns:
        JSON con comparativa de métricas entre LLMs
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a BD'}), 500
    
    try:
        cur = conn.cursor()
        
        # Usar vista de comparación
        cur.execute("""
            SELECT *
            FROM llm_visibility_comparison
            WHERE project_id = %s
            ORDER BY snapshot_date DESC, llm_provider
            LIMIT 100
        """, (project_id,))
        
        comparisons = cur.fetchall()
        
        # Formatear datos
        comparison_list = []
        for c in comparisons:
            comparison_list.append({
                'llm_provider': c['llm_provider'],
                'snapshot_date': c['snapshot_date'].isoformat() if c['snapshot_date'] else None,
                'mention_rate': float(c['mention_rate']) if c['mention_rate'] else 0,
                'avg_position': float(c['avg_position']) if c['avg_position'] else None,
                'share_of_voice': float(c['share_of_voice']) if c['share_of_voice'] else 0,
                'sentiment_score': float(c['sentiment_score']) if c['sentiment_score'] else 0,
                'total_queries': c['total_queries_analyzed']
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


@llm_monitoring_bp.route('/models/<int:model_id>', methods=['PUT'])
@login_required
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
    # TODO: Agregar decorador @admin_required
    
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


logger.info("✅ LLM Monitoring Blueprint loaded successfully")

