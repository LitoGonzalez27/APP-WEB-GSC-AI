# manual_ai_system.py - Sistema Manual AI Analysis independiente
# SEGURO: No toca ningún archivo existente, usa servicios establecidos

from flask import Blueprint, render_template, request, jsonify
from datetime import datetime, date, timedelta
import logging
import json
from typing import List, Dict, Any, Optional

# Reutilizar servicios existentes (sin modificarlos)
from database import get_db_connection
from auth import auth_required, get_current_user
from services.serp_service import get_serp_json
from services.ai_analysis import detect_ai_overview_elements
from services.utils import extract_domain, normalize_search_console_url

logger = logging.getLogger(__name__)

# Blueprint independiente - no interfiere con rutas existentes
manual_ai_bp = Blueprint('manual_ai', __name__, url_prefix='/manual-ai')

# ================================
# ROUTES - API y PÁGINAS
# ================================

@manual_ai_bp.route('/')
@auth_required
def manual_ai_dashboard():
    """Dashboard principal del sistema Manual AI Analysis"""
    user = get_current_user()
    return render_template('manual_ai_dashboard.html', user=user)

@manual_ai_bp.route('/api/projects', methods=['GET'])
@auth_required
def get_projects():
    """Obtener todos los proyectos del usuario actual"""
    user = get_current_user()
    projects = get_user_projects(user['id'])
    
    return jsonify({
        'success': True,
        'projects': projects
    })

@manual_ai_bp.route('/api/projects', methods=['POST'])
@auth_required
def create_project():
    """Crear un nuevo proyecto"""
    user = get_current_user()
    data = request.get_json()
    
    # Validaciones básicas
    if not data.get('name') or not data.get('domain'):
        return jsonify({'success': False, 'error': 'Name and domain are required'}), 400
    
    try:
        project_id = create_new_project(
            user_id=user['id'],
            name=data['name'],
            description=data.get('description', ''),
            domain=data['domain'],
            country_code=data.get('country_code', 'US')
        )
        
        # Crear evento de creación
        create_project_event(
            project_id=project_id,
            event_type='project_created',
            event_title=f'Project "{data["name"]}" created',
            user_id=user['id']
        )
        
        return jsonify({
            'success': True,
            'project_id': project_id,
            'message': 'Project created successfully'
        })
        
    except Exception as e:
        logger.error(f"Error creating project: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@manual_ai_bp.route('/api/projects/<int:project_id>', methods=['GET'])
@auth_required
def get_project_details(project_id):
    """Obtener detalles completos de un proyecto"""
    user = get_current_user()
    
    if not user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    project = get_project_with_details(project_id)
    return jsonify({
        'success': True,
        'project': project
    })

@manual_ai_bp.route('/api/projects/<int:project_id>/keywords', methods=['GET'])
@auth_required
def get_project_keywords(project_id):
    """Obtener keywords de un proyecto"""
    user = get_current_user()
    
    if not user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    keywords = get_keywords_for_project(project_id)
    return jsonify({
        'success': True,
        'keywords': keywords
    })

@manual_ai_bp.route('/api/projects/<int:project_id>/keywords', methods=['POST'])
@auth_required
def add_keywords_to_project(project_id):
    """Agregar keywords a un proyecto"""
    user = get_current_user()
    
    if not user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    keywords_list = data.get('keywords', [])
    
    if not keywords_list:
        return jsonify({'success': False, 'error': 'No keywords provided'}), 400
    
    # Verificar límite de 200 keywords
    current_count = get_project_keyword_count(project_id)
    if current_count + len(keywords_list) > 200:
        return jsonify({
            'success': False, 
            'error': f'Project would exceed 200 keywords limit. Current: {current_count}, Adding: {len(keywords_list)}'
        }), 400
    
    try:
        added_count = add_keywords_to_project_db(project_id, keywords_list)
        
        # Crear evento
        create_project_event(
            project_id=project_id,
            event_type='keywords_added',
            event_title=f'{added_count} keywords added',
            keywords_affected=added_count,
            user_id=user['id']
        )
        
        return jsonify({
            'success': True,
            'added_count': added_count,
            'message': f'{added_count} keywords added successfully'
        })
        
    except Exception as e:
        logger.error(f"Error adding keywords: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@manual_ai_bp.route('/api/projects/<int:project_id>/analyze', methods=['POST'])
@auth_required
def analyze_project(project_id):
    """Ejecutar análisis completo de un proyecto"""
    user = get_current_user()
    
    if not user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        # Ejecutar análisis
        results = run_project_analysis(project_id)
        
        # Crear snapshot del día
        create_daily_snapshot(project_id)
        
        # Crear evento
        create_project_event(
            project_id=project_id,
            event_type='analysis_completed',
            event_title='Daily analysis completed',
            keywords_affected=len(results),
            user_id=user['id']
        )
        
        return jsonify({
            'success': True,
            'results_count': len(results),
            'analysis_date': str(date.today()),
            'message': 'Analysis completed successfully'
        })
        
    except Exception as e:
        logger.error(f"Error analyzing project {project_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@manual_ai_bp.route('/api/projects/<int:project_id>/stats', methods=['GET'])
@auth_required
def get_project_stats(project_id):
    """Obtener estadísticas y gráficos de un proyecto"""
    user = get_current_user()
    
    if not user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    days_param = request.args.get('days', '30')
    try:
        days = int(days_param)
    except ValueError:
        days = 30
    
    stats = get_project_statistics(project_id, days)
    return jsonify({
        'success': True,
        'stats': stats
    })

@manual_ai_bp.route('/api/projects/<int:project_id>/export', methods=['GET'])
@auth_required
def export_project_data(project_id):
    """Exportar datos del proyecto a CSV"""
    user = get_current_user()
    
    if not user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    # TODO: Implementar exportación usando excel_generator.py existente
    return jsonify({
        'success': True,
        'message': 'Export functionality coming soon'
    })

# ================================
# FUNCIONES DE BASE DE DATOS
# ================================

def get_user_projects(user_id: int) -> List[Dict]:
    """Obtener todos los proyectos de un usuario con estadísticas básicas"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            p.id,
            p.name,
            p.description,
            p.domain,
            p.country_code,
            p.created_at,
            p.updated_at,
            COUNT(DISTINCT k.id) as keyword_count,
            COUNT(DISTINCT CASE WHEN r.has_ai_overview = true THEN r.id END) as ai_overview_count,
            COUNT(DISTINCT CASE WHEN r.domain_mentioned = true THEN r.id END) as mentions_count,
            MAX(r.analysis_date) as last_analysis_date
        FROM manual_ai_projects p
        LEFT JOIN manual_ai_keywords k ON p.id = k.project_id AND k.is_active = true
        LEFT JOIN manual_ai_results r ON p.id = r.project_id AND r.analysis_date >= CURRENT_DATE - INTERVAL '30 days'
        WHERE p.user_id = %s AND p.is_active = true
        GROUP BY p.id, p.name, p.description, p.domain, p.country_code, p.created_at, p.updated_at
        ORDER BY p.created_at DESC
    """, (user_id,))
    
    projects = cur.fetchall()
    cur.close()
    conn.close()
    
    return [dict(project) for project in projects]

def create_new_project(user_id: int, name: str, description: str, domain: str, country_code: str) -> int:
    """Crear un nuevo proyecto"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Normalizar dominio
    normalized_domain = normalize_search_console_url(domain) or domain
    
    cur.execute("""
        INSERT INTO manual_ai_projects (user_id, name, description, domain, country_code)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    """, (user_id, name, description, normalized_domain, country_code))
    
    project_id = cur.fetchone()['id']
    conn.commit()
    cur.close()
    conn.close()
    
    logger.info(f"Created new project {project_id} for user {user_id}")
    return project_id

def user_owns_project(user_id: int, project_id: int) -> bool:
    """Verificar si un usuario es propietario de un proyecto"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 1 FROM manual_ai_projects 
        WHERE id = %s AND user_id = %s AND is_active = true
    """, (project_id, user_id))
    
    result = cur.fetchone()
    cur.close()
    conn.close()
    
    return result is not None

def get_project_with_details(project_id: int) -> Dict:
    """Obtener proyecto con todos sus detalles"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            p.*,
            COUNT(DISTINCT k.id) as keyword_count,
            COUNT(DISTINCT CASE WHEN k.is_active = true THEN k.id END) as active_keyword_count
        FROM manual_ai_projects p
        LEFT JOIN manual_ai_keywords k ON p.id = k.project_id
        WHERE p.id = %s
        GROUP BY p.id
    """, (project_id,))
    
    project = cur.fetchone()
    cur.close()
    conn.close()
    
    return dict(project) if project else None

def get_keywords_for_project(project_id: int) -> List[Dict]:
    """Obtener todas las keywords de un proyecto"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            k.*,
            COUNT(r.id) as analysis_count,
            MAX(r.analysis_date) as last_analysis_date,
            AVG(CASE WHEN r.has_ai_overview THEN 1.0 ELSE 0.0 END) as ai_overview_frequency
        FROM manual_ai_keywords k
        LEFT JOIN manual_ai_results r ON k.id = r.keyword_id
        WHERE k.project_id = %s
        GROUP BY k.id, k.keyword, k.is_active, k.added_at
        ORDER BY k.added_at DESC
    """, (project_id,))
    
    keywords = cur.fetchall()
    cur.close()
    conn.close()
    
    return [dict(keyword) for keyword in keywords]

def get_project_keyword_count(project_id: int) -> int:
    """Obtener el conteo actual de keywords activas de un proyecto"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT COUNT(*) as count
        FROM manual_ai_keywords
        WHERE project_id = %s AND is_active = true
    """, (project_id,))
    
    result = cur.fetchone()
    cur.close()
    conn.close()
    
    return result['count'] if result else 0

def add_keywords_to_project_db(project_id: int, keywords_list: List[str]) -> int:
    """Agregar keywords a un proyecto (evitando duplicados)"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    added_count = 0
    
    for keyword in keywords_list:
        keyword = keyword.strip()
        if not keyword:
            continue
            
        try:
            cur.execute("""
                INSERT INTO manual_ai_keywords (project_id, keyword)
                VALUES (%s, %s)
                ON CONFLICT (project_id, keyword) DO NOTHING
            """, (project_id, keyword))
            
            if cur.rowcount > 0:
                added_count += 1
                
        except Exception as e:
            logger.warning(f"Error adding keyword '{keyword}': {e}")
            continue
    
    conn.commit()
    cur.close()
    conn.close()
    
    return added_count

def run_project_analysis(project_id: int) -> List[Dict]:
    """Ejecutar análisis completo de todas las keywords activas de un proyecto"""
    # Obtener proyecto y keywords
    project = get_project_with_details(project_id)
    keywords = [k for k in get_keywords_for_project(project_id) if k['is_active']]
    
    if not project or not keywords:
        return []
    
    results = []
    today = date.today()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    logger.info(f"Starting analysis for project {project_id} with {len(keywords)} keywords")
    
    for keyword_data in keywords:
        keyword = keyword_data['keyword']
        keyword_id = keyword_data['id']
        
        try:
            # Verificar si ya existe análisis para hoy
            cur.execute("""
                SELECT 1 FROM manual_ai_results 
                WHERE project_id = %s AND keyword_id = %s AND analysis_date = %s
            """, (project_id, keyword_id, today))
            
            if cur.fetchone():
                logger.debug(f"Analysis already exists for keyword '{keyword}' on {today}")
                continue
            
            # Usar servicios existentes para obtener datos SERP
            serp_data = get_serp_json(keyword, project['country_code'])
            
            if not serp_data:
                logger.warning(f"No SERP data for keyword '{keyword}'")
                continue
            
            # Usar servicio existente para análisis AI Overview
            ai_result = detect_ai_overview_elements(serp_data, project['domain'])
            
            # Guardar resultado
            cur.execute("""
                INSERT INTO manual_ai_results (
                    project_id, keyword_id, analysis_date, keyword, domain,
                    has_ai_overview, domain_mentioned, domain_position, 
                    ai_elements_count, impact_score, raw_serp_data, 
                    ai_analysis_data, country_code
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                project_id, keyword_id, today, keyword, project['domain'],
                ai_result.get('has_ai_overview', False),
                ai_result.get('domain_is_ai_source', False),
                ai_result.get('domain_ai_source_position'),
                ai_result.get('total_elements', 0),
                ai_result.get('impact_score', 0),
                json.dumps(serp_data),
                json.dumps(ai_result),
                project['country_code']
            ))
            
            results.append({
                'keyword': keyword,
                'has_ai_overview': ai_result.get('has_ai_overview', False),
                'domain_mentioned': ai_result.get('domain_is_ai_source', False),
                'position': ai_result.get('domain_ai_source_position'),
                'impact_score': ai_result.get('impact_score', 0)
            })
            
            logger.debug(f"Analyzed keyword '{keyword}': AI={ai_result.get('has_ai_overview')}, Mentioned={ai_result.get('domain_is_ai_source')}")
            
        except Exception as e:
            logger.error(f"Error analyzing keyword '{keyword}': {e}")
            continue
    
    conn.commit()
    cur.close()
    conn.close()
    
    logger.info(f"Completed analysis for project {project_id}: {len(results)} keywords processed")
    return results

def create_daily_snapshot(project_id: int) -> None:
    """Crear snapshot diario con métricas del proyecto"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    today = date.today()
    
    # Calcular métricas del día
    cur.execute("""
        WITH project_stats AS (
            SELECT 
                COUNT(DISTINCT k.id) as total_keywords,
                COUNT(DISTINCT CASE WHEN k.is_active THEN k.id END) as active_keywords,
                COUNT(DISTINCT CASE WHEN r.has_ai_overview = true AND r.analysis_date = %s THEN r.id END) as keywords_with_ai,
                COUNT(DISTINCT CASE WHEN r.domain_mentioned = true AND r.analysis_date = %s THEN r.id END) as domain_mentions,
                AVG(CASE WHEN r.domain_position IS NOT NULL AND r.analysis_date = %s THEN r.domain_position END) as avg_position,
                (COUNT(DISTINCT CASE WHEN r.domain_mentioned = true AND r.analysis_date = %s THEN r.id END)::float / 
                 NULLIF(COUNT(DISTINCT CASE WHEN r.has_ai_overview = true AND r.analysis_date = %s THEN r.id END), 0)::float * 100) as visibility_percentage
            FROM manual_ai_keywords k
            LEFT JOIN manual_ai_results r ON k.id = r.keyword_id
            WHERE k.project_id = %s
        )
        INSERT INTO manual_ai_snapshots (
            project_id, snapshot_date, total_keywords, active_keywords,
            keywords_with_ai, domain_mentions, avg_position, visibility_percentage,
            change_type, change_description
        ) 
        SELECT 
            %s, %s, total_keywords, active_keywords,
            keywords_with_ai, domain_mentions, avg_position, visibility_percentage,
            'daily_analysis', 'Daily automated analysis'
        FROM project_stats
        ON CONFLICT (project_id, snapshot_date) 
        DO UPDATE SET
            keywords_with_ai = EXCLUDED.keywords_with_ai,
            domain_mentions = EXCLUDED.domain_mentions,
            avg_position = EXCLUDED.avg_position,
            visibility_percentage = EXCLUDED.visibility_percentage
    """, (today, today, today, today, today, project_id, project_id, today))
    
    conn.commit()
    cur.close()
    conn.close()

def create_project_event(project_id: int, event_type: str, event_title: str, 
                        event_description: str = None, keywords_affected: int = 0, 
                        user_id: int = None) -> None:
    """Crear un evento para tracking de cambios"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    today = date.today()
    
    cur.execute("""
        INSERT INTO manual_ai_events (
            project_id, event_date, event_type, event_title, 
            event_description, keywords_affected, user_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (project_id, today, event_type, event_title, event_description, keywords_affected, user_id))
    
    conn.commit()
    cur.close()
    conn.close()

def get_project_statistics(project_id: int, days: int = 30) -> Dict:
    """Obtener estadísticas completas de un proyecto para gráficos"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    # Estadísticas principales
    cur.execute("""
        SELECT 
            COUNT(DISTINCT k.id) as total_keywords,
            COUNT(DISTINCT CASE WHEN k.is_active = true THEN k.id END) as active_keywords,
            COUNT(DISTINCT CASE WHEN r.has_ai_overview = true THEN r.id END) as total_ai_keywords,
            COUNT(DISTINCT CASE WHEN r.domain_mentioned = true THEN r.id END) as total_mentions,
            AVG(CASE WHEN r.domain_position IS NOT NULL THEN r.domain_position END) as avg_position,
            (COUNT(DISTINCT CASE WHEN r.domain_mentioned = true THEN r.id END)::float / 
             NULLIF(COUNT(DISTINCT CASE WHEN r.has_ai_overview = true THEN r.id END), 0)::float * 100) as visibility_percentage
        FROM manual_ai_keywords k
        LEFT JOIN manual_ai_results r ON k.id = r.keyword_id 
            AND r.analysis_date >= %s AND r.analysis_date <= %s
        WHERE k.project_id = %s
    """, (start_date, end_date, project_id))
    
    main_stats = dict(cur.fetchone() or {})
    
    # Datos para gráfico de visibilidad por día
    cur.execute("""
        SELECT 
            r.analysis_date,
            COUNT(DISTINCT CASE WHEN r.has_ai_overview = true THEN r.id END) as ai_keywords,
            COUNT(DISTINCT CASE WHEN r.domain_mentioned = true THEN r.id END) as mentions,
            (COUNT(DISTINCT CASE WHEN r.domain_mentioned = true THEN r.id END)::float / 
             NULLIF(COUNT(DISTINCT CASE WHEN r.has_ai_overview = true THEN r.id END), 0)::float * 100) as visibility_pct
        FROM manual_ai_results r
        WHERE r.project_id = %s AND r.analysis_date >= %s AND r.analysis_date <= %s
        GROUP BY r.analysis_date
        ORDER BY r.analysis_date
    """, (project_id, start_date, end_date))
    
    visibility_data = [dict(row) for row in cur.fetchall()]
    
    # Datos para gráfico de posiciones
    cur.execute("""
        SELECT 
            r.analysis_date,
            COUNT(CASE WHEN r.domain_position BETWEEN 1 AND 3 THEN 1 END) as pos_1_3,
            COUNT(CASE WHEN r.domain_position BETWEEN 4 AND 10 THEN 1 END) as pos_4_10,
            COUNT(CASE WHEN r.domain_position BETWEEN 11 AND 20 THEN 1 END) as pos_11_20,
            COUNT(CASE WHEN r.domain_position > 20 THEN 1 END) as pos_21_plus
        FROM manual_ai_results r
        WHERE r.project_id = %s AND r.analysis_date >= %s AND r.analysis_date <= %s
            AND r.domain_mentioned = true
        GROUP BY r.analysis_date
        ORDER BY r.analysis_date
    """, (project_id, start_date, end_date))
    
    positions_data = [dict(row) for row in cur.fetchall()]
    
    # Eventos para anotaciones
    cur.execute("""
        SELECT event_date, event_type, event_title, keywords_affected
        FROM manual_ai_events
        WHERE project_id = %s AND event_date >= %s AND event_date <= %s
        ORDER BY event_date
    """, (project_id, start_date, end_date))
    
    events_data = [dict(row) for row in cur.fetchall()]
    
    cur.close()
    conn.close()
    
    return {
        'main_stats': main_stats,
        'visibility_chart': visibility_data,
        'positions_chart': positions_data,
        'events': events_data,
        'date_range': {
            'start': str(start_date),
            'end': str(end_date)
        }
    }

# ================================
# FUNCIONES DE UTILIDAD
# ================================

def init_manual_ai_system():
    """Inicializar el sistema (crear tablas si no existen)"""
    try:
        # Importar y ejecutar el script de creación de tablas
        from create_manual_ai_tables import create_manual_ai_tables
        return create_manual_ai_tables()
    except ImportError:
        logger.error("create_manual_ai_tables.py not found")
        return False
    except Exception as e:
        logger.error(f"Error initializing manual AI system: {e}")
        return False

# Registrar rutas de error handling
@manual_ai_bp.errorhandler(404)
def handle_404(e):
    return jsonify({'success': False, 'error': 'Endpoint not found'}), 404

@manual_ai_bp.errorhandler(500)
def handle_500(e):
    return jsonify({'success': False, 'error': 'Internal server error'}), 500

# Logging para debugging
logger.info("Manual AI System loaded successfully")