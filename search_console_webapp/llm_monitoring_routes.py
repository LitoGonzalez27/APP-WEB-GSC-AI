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
import json
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
            logger.error(f"Error validando ownership: {e}", exc_info=True)
            return jsonify({'error': f'Error validando permisos: {str(e)}'}), 500
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
                %s, %s::jsonb, %s, %s,
                TRUE, NOW(), NOW()
            )
            RETURNING id, created_at
        """, (
            user['id'],
            data['name'],
            data['brand_name'],
            data['industry'],
            enabled_llms,
            json.dumps(competitors),  # Convertir a JSON string
            language,
            queries_per_llm
        ))
        
        result = cur.fetchone()
        project_id = result['id']
        created_at = result['created_at']
        
        # ✅ NUEVO: Ya NO generamos queries automáticamente
        # El usuario deberá añadirlas manualmente después de crear el proyecto
        # Esto es consistente con Manual AI y AI Mode
        queries = []
        logger.info(f"✅ Proyecto {project_id} creado. El usuario deberá añadir prompts manualmente.")
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Proyecto creado exitosamente. Ahora añade tus prompts manualmente.',
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
                'total_queries': 0  # Sin queries todavía
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
                p.industry,
                p.enabled_llms,
                p.competitors,
                p.language,
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
            GROUP BY p.id, p.user_id, p.name, p.brand_name, p.industry, 
                     p.enabled_llms, p.competitors, p.language, p.queries_per_llm,
                     p.is_active, p.last_analysis_date, p.created_at, p.updated_at
        """, (project_id,))
        
        project = cur.fetchone()
        logger.info(f"✅ Proyecto obtenido: {project['name'] if project else 'None'}")
        
        if not project:
            logger.warning(f"⚠️ Proyecto {project_id} no encontrado")
            return jsonify({'error': 'Proyecto no encontrado'}), 404
        
        # Obtener últimas métricas de cada LLM
        logger.info(f"📈 Consultando métricas para proyecto {project_id}...")
        cur.execute("""
            SELECT 
                llm_provider,
                mention_rate,
                avg_position,
                share_of_voice,
                positive_mentions,
                neutral_mentions,
                negative_mentions,
                total_mentions,
                total_queries,
                snapshot_date
            FROM llm_monitoring_snapshots
            WHERE project_id = %s
            ORDER BY snapshot_date DESC, llm_provider
            LIMIT 4
        """, (project_id,))
        
        latest_metrics = cur.fetchall()
        logger.info(f"📊 Métricas encontradas: {len(latest_metrics)} registros")
        
        # Formatear métricas
        metrics_by_llm = {}
        for metric in latest_metrics:
            positive_mentions = metric.get('positive_mentions') or 0
            neutral_mentions = metric.get('neutral_mentions') or 0
            negative_mentions = metric.get('negative_mentions') or 0
            total_mentions = metric.get('total_mentions') or (positive_mentions + neutral_mentions + negative_mentions)

            positive_pct = (positive_mentions / total_mentions * 100) if total_mentions else 0
            neutral_pct = (neutral_mentions / total_mentions * 100) if total_mentions else 0
            negative_pct = (negative_mentions / total_mentions * 100) if total_mentions else 0

            metrics_by_llm[metric['llm_provider']] = {
                'mention_rate': float(metric['mention_rate']) if metric['mention_rate'] is not None else 0,
                'avg_position': float(metric['avg_position']) if metric['avg_position'] is not None else None,
                'share_of_voice': float(metric['share_of_voice']) if metric['share_of_voice'] is not None else 0,
                'sentiment': {
                    'positive': float(positive_pct),
                    'neutral': float(neutral_pct),
                    'negative': float(negative_pct)
                },
                'total_queries': metric.get('total_queries'),
                'date': metric['snapshot_date'].isoformat() if metric['snapshot_date'] else None
            }
        
        logger.info(f"✅ Preparando respuesta para proyecto {project_id}")
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
            updates.append("competitors = %s::jsonb")
            params.append(json.dumps(data['competitors']))
        
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
# ENDPOINTS: PROMPTS/QUERIES (Manual Management)
# ============================================================================

@llm_monitoring_bp.route('/projects/<int:project_id>/queries', methods=['GET'])
@login_required
@validate_project_ownership
def get_project_queries(project_id):
    """
    Obtiene todas las queries/prompts de un proyecto
    
    Returns:
        JSON con lista de queries
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a BD'}), 500
    
    try:
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                id,
                query_text,
                language,
                query_type,
                is_active,
                added_at
            FROM llm_monitoring_queries
            WHERE project_id = %s AND is_active = TRUE
            ORDER BY added_at DESC
        """, (project_id,))
        
        queries = cur.fetchall()
        
        # Formatear respuesta
        queries_list = []
        for query in queries:
            queries_list.append({
                'id': query['id'],
                'query_text': query['query_text'],
                'language': query['language'],
                'query_type': query['query_type'],
                'is_active': query['is_active'],
                'added_at': query['added_at'].isoformat() if query['added_at'] else None
            })
        
        return jsonify({
            'success': True,
            'queries': queries_list,
            'total': len(queries_list)
        }), 200
        
    except Exception as e:
        logger.error(f"Error obteniendo queries: {e}", exc_info=True)
        return jsonify({'error': f'Error obteniendo queries: {str(e)}'}), 500
    finally:
        cur.close()
        conn.close()


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
    
    # Obtener configuración del proyecto si no se especificó idioma
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión a BD'}), 500
    
    try:
        cur = conn.cursor()
        
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
            if not query_text or len(query_text) < 10:
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
                # ➕ Exponer datos de competidores para el frontend (gráfico SOV)
                'total_competitor_mentions': int(s.get('total_competitor_mentions') or 0),
                'competitor_breakdown': s.get('competitor_breakdown') or {},
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
        
        # Traer filas por LLM directamente desde snapshots
        cur.execute("""
            SELECT 
                llm_provider,
                snapshot_date,
                mention_rate,
                avg_position,
                share_of_voice,
                avg_sentiment_score,
                total_queries
            FROM llm_monitoring_snapshots
            WHERE project_id = %s
            ORDER BY snapshot_date DESC, llm_provider
            LIMIT 100
        """, (project_id,))
        
        rows = cur.fetchall()
        
        # Formatear datos
        comparison_list = []
        for c in rows:
            comparison_list.append({
                'llm_provider': c['llm_provider'],
                'snapshot_date': c['snapshot_date'].isoformat() if c['snapshot_date'] else None,
                'mention_rate': float(c['mention_rate']) if c['mention_rate'] is not None else 0,
                'avg_position': float(c['avg_position']) if c['avg_position'] is not None else None,
                'share_of_voice': float(c['share_of_voice']) if c['share_of_voice'] is not None else 0,
                'sentiment_score': float(c['avg_sentiment_score']) if c['avg_sentiment_score'] is not None else 0,
                'total_queries': c['total_queries']
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

