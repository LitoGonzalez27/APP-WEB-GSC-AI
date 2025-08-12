# manual_ai_system.py - Sistema Manual AI Analysis independiente
# SEGURO: No toca ningún archivo existente, usa servicios establecidos

from flask import Blueprint, render_template, request, jsonify
from datetime import datetime, date, timedelta
import logging
import json
import time
from typing import List, Dict, Any, Optional
import threading

# Reutilizar servicios existentes (sin modificarlos)
from database import get_db_connection
from auth import auth_required, cron_or_auth_required, get_current_user
from services.serp_service import get_serp_json
from services.ai_analysis import detect_ai_overview_elements
from services.utils import extract_domain, normalize_search_console_url
from services.ai_cache import ai_cache
import os

logger = logging.getLogger(__name__)

# Blueprint independiente - no interfiere con rutas existentes
manual_ai_bp = Blueprint('manual_ai', __name__, url_prefix='/manual-ai')

# ================================
# UTILIDADES DE OBSERVABILIDAD
# ================================

def now_utc_iso() -> str:
    return datetime.utcnow().isoformat() + 'Z'

def with_backoff(max_attempts: int = 3, base_delay_sec: float = 1.0):
    """Decorador sencillo de reintentos con backoff exponencial y jitter pequeño.
    Reintenta solo para errores transitorios; el callable debe lanzar Exception para reintentar.
    """
    def _decorator(func):
        def _wrapper(*args, **kwargs):
            attempt = 0
            last_err = None
            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as err:  # noqa: BLE001
                    last_err = err
                    attempt += 1
                    if attempt >= max_attempts:
                        break
                    delay = base_delay_sec * (2 ** (attempt - 1))
                    # Pequeño jitter para evitar thundering herd
                    time.sleep(delay + 0.05 * attempt)
            raise last_err
        return _wrapper
    return _decorator


# ================================
# HEALTH-CHECK
# ================================

@manual_ai_bp.route('/api/health', methods=['GET'])
def manual_ai_health():
    """Health-check: confirma app viva, DB accesible, última ejecución y resultados del día."""
    try:
        # DB check
        conn = get_db_connection()
        if not conn:
            return jsonify({"status": "error", "db": "down"}), 500
        cur = conn.cursor()
        today = date.today()
        # Últimos eventos de cron (si existen)
        try:
            cur.execute(
                """
                SELECT event_date, event_type, event_title
                FROM manual_ai_events
                WHERE event_type IN ('daily_analysis')
                ORDER BY event_date DESC
                LIMIT 1
                """
            )
            last = cur.fetchone()
        except Exception:
            last = None
        # Conteos de hoy (agregados a nivel global)
        cur.execute("SELECT COUNT(*) AS c FROM manual_ai_results WHERE analysis_date = %s", (today,))
        results_today = cur.fetchone()['c']
        try:
            cur.execute("SELECT COUNT(*) AS c FROM manual_ai_global_domains WHERE analysis_date = %s", (today,))
            global_today = cur.fetchone()['c']
        except Exception:
            global_today = 0
        cur.close(); conn.close()
        return jsonify({
            "status": "ok",
            "ts": now_utc_iso(),
            "db": "ok",
            "last_cron": (last['event_date'] if last and isinstance(last, dict) else (last[0] if last else None)),
            "results_today": int(results_today),
            "global_domains_today": int(global_today)
        }), 200
    except Exception as e:
        logger.error(json.dumps({"event": "health_error", "error": str(e)}))
        return jsonify({"status": "error", "message": str(e)}), 500


## (Eliminado) Migraciones runtime: se gestionan ahora con script dedicado

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
            country_code=data.get('country_code', 'US'),
            competitors=data.get('competitors', [])
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

@manual_ai_bp.route('/api/projects/<int:project_id>', methods=['PUT'])
@auth_required
def update_project(project_id):
    """Actualizar un proyecto (nombre, configuración, etc.)"""
    user = get_current_user()
    
    if not user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        data = request.get_json()
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Validar datos requeridos
        if 'name' not in data:
            return jsonify({'success': False, 'error': 'Project name is required'}), 400
            
        name = data['name'].strip()
        description = data.get('description', '').strip()
        
        if not name:
            return jsonify({'success': False, 'error': 'Project name cannot be empty'}), 400
            
        # Verificar que el nombre no esté siendo usado por otro proyecto del usuario
        cur.execute("""
            SELECT id FROM manual_ai_projects 
            WHERE user_id = %s AND name = %s AND id != %s
        """, (user['id'], name, project_id))
        
        if cur.fetchone():
            return jsonify({'success': False, 'error': 'Project name already exists'}), 400
        
        # Actualizar proyecto (nombre y descripción)
        cur.execute("""
            UPDATE manual_ai_projects 
            SET name = %s, description = %s, updated_at = NOW()
            WHERE id = %s AND user_id = %s
        """, (name, description, project_id, user['id']))
        
        if cur.rowcount == 0:
            return jsonify({'success': False, 'error': 'Project not found'}), 404
            
        # Registrar evento de cambio de nombre
        cur.execute("""
            INSERT INTO manual_ai_events (project_id, event_type, event_title, description, event_date)
            VALUES (%s, 'project_updated', 'Project Renamed', %s, NOW())
        """, (project_id, f'Project renamed to "{name}"'))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Project {project_id} updated successfully")
        return jsonify({'success': True, 'message': 'Project updated successfully'})
        
    except Exception as e:
        logger.error(f"Error updating project {project_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@manual_ai_bp.route('/api/projects/<int:project_id>', methods=['DELETE'])
@auth_required
def delete_project(project_id):
    """Eliminar completamente un proyecto y todos sus datos"""
    user = get_current_user()
    
    logger.info(f"🗑️ Delete request for project {project_id} by user {user.get('id')}")
    
    if not user_owns_project(user['id'], project_id):
        logger.warning(f"🚫 Unauthorized delete attempt for project {project_id} by user {user.get('id')}")
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Obtener nombre del proyecto antes de eliminarlo (compatible con RealDictRow o tuplas)
        cur.execute("SELECT name FROM manual_ai_projects WHERE id = %s", (project_id,))
        project_data = cur.fetchone()
        if not project_data:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        try:
            project_name = project_data['name'] if isinstance(project_data, dict) else project_data[0]
        except Exception:
            project_name = str(project_data)
        
        # Eliminar en orden inverso de dependencias
        # 1. Eliminar eventos (no críticos si no existen)
        try:
            cur.execute("DELETE FROM manual_ai_events WHERE project_id = %s", (project_id,))
        except Exception as e:
            logger.warning(f"No events deleted for project {project_id}: {e}")
        events_deleted = cur.rowcount
        
        # 2. Eliminar snapshots
        try:
            cur.execute("DELETE FROM manual_ai_snapshots WHERE project_id = %s", (project_id,))
        except Exception as e:
            logger.warning(f"No snapshots deleted for project {project_id}: {e}")
        snapshots_deleted = cur.rowcount
        
        # 3. Eliminar resultados de análisis (más robusto por project_id)
        cur.execute(
            "DELETE FROM manual_ai_results WHERE project_id = %s",
            (project_id,)
        )
        results_deleted = cur.rowcount
        
        # 4. Eliminar keywords
        cur.execute("DELETE FROM manual_ai_keywords WHERE project_id = %s", (project_id,))
        keywords_deleted = cur.rowcount
        
        # 5. Eliminar proyecto
        cur.execute("DELETE FROM manual_ai_projects WHERE id = %s AND user_id = %s", 
                   (project_id, user['id']))
        
        if cur.rowcount == 0:
            return jsonify({'success': False, 'error': 'Project not found or unauthorized'}), 404
        
        conn.commit()
        conn.close()
        
        logger.info(f"Project '{project_name}' (ID: {project_id}) deleted successfully. "
                   f"Removed: {keywords_deleted} keywords, {results_deleted} results, "
                   f"{snapshots_deleted} snapshots, {events_deleted} events")
        
        return jsonify({
            'success': True, 
            'message': f'Project "{project_name}" deleted successfully',
            'stats': {
                'keywords_deleted': keywords_deleted,
                'results_deleted': results_deleted,
                'snapshots_deleted': snapshots_deleted,
                'events_deleted': events_deleted
            }
        })
        
    except Exception as e:
        logger.error(f"Error deleting project {project_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

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

@manual_ai_bp.route('/api/projects/<int:project_id>/keywords/<int:keyword_id>', methods=['DELETE'])
@auth_required
def delete_project_keyword(project_id, keyword_id):
    """Eliminar una keyword específica de un proyecto"""
    user = get_current_user()
    
    if not user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        # Verificar que la keyword existe y pertenece al proyecto
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, keyword FROM manual_ai_keywords 
            WHERE id = %s AND project_id = %s AND is_active = true
        """, (keyword_id, project_id))
        
        keyword_data = cur.fetchone()
        if not keyword_data:
            return jsonify({'success': False, 'error': 'Keyword not found'}), 404
        
        # Marcar como inactiva (soft delete)
        cur.execute("""
            UPDATE manual_ai_keywords 
            SET is_active = false, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND project_id = %s
        """, (keyword_id, project_id))
        
        # Eliminar resultados asociados
        cur.execute("""
            DELETE FROM manual_ai_results 
            WHERE keyword_id = %s AND project_id = %s
        """, (keyword_id, project_id))
        
        conn.commit()
        conn.close()
        
        # Crear evento
        create_project_event(
            project_id=project_id,
            event_type='keyword_deleted',
            event_title=f'Keyword deleted: {keyword_data["keyword"]}',
            keywords_affected=1,
            user_id=user['id']
        )
        
        return jsonify({
            'success': True,
            'message': f'Keyword "{keyword_data["keyword"]}" deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Error deleting keyword: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@manual_ai_bp.route('/api/projects/<int:project_id>/keywords/<int:keyword_id>', methods=['PUT'])
@auth_required
def update_project_keyword(project_id, keyword_id):
    """Actualizar una keyword específica de un proyecto"""
    user = get_current_user()
    
    if not user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    new_keyword = data.get('keyword', '').strip()
    
    if not new_keyword:
        return jsonify({'success': False, 'error': 'Keyword cannot be empty'}), 400
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Verificar que la keyword existe
        cur.execute("""
            SELECT keyword FROM manual_ai_keywords 
            WHERE id = %s AND project_id = %s AND is_active = true
        """, (keyword_id, project_id))
        
        old_keyword_data = cur.fetchone()
        if not old_keyword_data:
            return jsonify({'success': False, 'error': 'Keyword not found'}), 404
        
        old_keyword = old_keyword_data['keyword']
        
        # Verificar que no existe otra keyword con el mismo texto en el proyecto
        cur.execute("""
            SELECT id FROM manual_ai_keywords 
            WHERE project_id = %s AND keyword = %s AND is_active = true AND id != %s
        """, (project_id, new_keyword, keyword_id))
        
        if cur.fetchone():
            return jsonify({'success': False, 'error': 'Keyword already exists in this project'}), 400
        
        # Actualizar la keyword
        cur.execute("""
            UPDATE manual_ai_keywords 
            SET keyword = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND project_id = %s
        """, (new_keyword, keyword_id, project_id))
        
        conn.commit()
        conn.close()
        
        # Crear evento
        create_project_event(
            project_id=project_id,
            event_type='keyword_updated',
            event_title=f'Keyword updated: "{old_keyword}" → "{new_keyword}"',
            keywords_affected=1,
            user_id=user['id']
        )
        
        return jsonify({
            'success': True,
            'message': f'Keyword updated successfully'
        })
        
    except Exception as e:
        logger.error(f"Error updating keyword: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ================================
# PROJECT ANALYSIS ENDPOINTS
# ================================

@manual_ai_bp.route('/api/projects/<int:project_id>/analyze', methods=['POST'])
@auth_required
def analyze_project(project_id):
    """Ejecutar análisis completo de un proyecto"""
    user = get_current_user()
    
    if not user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        # Ejecutar análisis manual con sobreescritura forzada
        results = run_project_analysis(project_id, force_overwrite=True)
        
        if not results:
            logger.warning(f"No results returned for project {project_id} analysis")
            return jsonify({
                'success': False, 
                'error': 'No keywords available for analysis'
            }), 400
        
        # Crear snapshot del día
        create_daily_snapshot(project_id)
        
        # Crear evento
        create_project_event(
            project_id=project_id,
            event_type='manual_analysis_completed',
            event_title='Manual analysis completed (with overwrite)',
            keywords_affected=len(results),
            user_id=user['id']
        )
        
        return jsonify({
            'success': True,
            'results_count': len(results),
            'analysis_date': str(date.today()),
            'message': 'Analysis completed successfully'
        })
        
    except ValueError as e:
        logger.warning(f"Validation error analyzing project {project_id}: {e}")
        return jsonify({'success': False, 'error': 'Invalid project data'}), 400
    except ConnectionError as e:
        logger.error(f"Connection error analyzing project {project_id}: {e}")
        return jsonify({'success': False, 'error': 'Analysis service temporarily unavailable'}), 503
    except Exception as e:
        logger.error(f"Unexpected error analyzing project {project_id}: {e}")
        return jsonify({'success': False, 'error': 'Analysis failed due to internal error'}), 500

@manual_ai_bp.route('/api/projects/<int:project_id>/results', methods=['GET'])
@auth_required
def get_project_results(project_id):
    """Obtener resultados de análisis de un proyecto"""
    user = get_current_user()
    
    if not user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    days_param = request.args.get('days', '30')
    try:
        days = int(days_param)
    except ValueError:
        days = 30
    
    results = get_project_analysis_results(project_id, days)
    return jsonify({
        'success': True,
        'results': results
    })

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

@manual_ai_bp.route('/api/projects/<int:project_id>/top-domains', methods=['GET'])
@auth_required
def get_top_domains(project_id):
    """Obtener dominios más visibles para un proyecto (versión anterior - mantenida por compatibilidad)"""
    user = get_current_user()
    
    if not user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        domains = get_project_top_domains(project_id)
        return jsonify({
            'success': True,
            'domains': domains
        })
    except Exception as e:
        logger.error(f"Error getting top domains for project {project_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@manual_ai_bp.route('/api/projects/<int:project_id>/global-domains-ranking', methods=['GET'])
@auth_required
def get_global_domains_ranking(project_id):
    """Obtener ranking global de TODOS los dominios detectados en AI Overview"""
    user = get_current_user()
    
    if not user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        days = int(request.args.get('days', 30))  # Parámetro opcional para rango de días
        ranking = get_project_global_domains_ranking(project_id, days)
        
        return jsonify({
            'success': True,
            'domains': ranking,
            'total_domains': len(ranking)
        })
    except Exception as e:
        logger.error(f"Error getting global domains ranking for project {project_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@manual_ai_bp.route('/api/projects/<int:project_id>/competitors-charts', methods=['GET'])
@auth_required
def get_competitors_charts_data(project_id):
    """Obtener datos para gráficas de competidores (Brand Visibility Index y Brand Position Over Time)"""
    user = get_current_user()
    
    if not user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        days = int(request.args.get('days', 30))  # Parámetro opcional para rango de días
        charts_data = get_project_competitors_charts_data(project_id, days)

        return jsonify({
            'success': True,
            'data': charts_data
        })
    except Exception as e:
        logger.error(f"Error getting competitors charts data for project {project_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@manual_ai_bp.route('/api/projects/<int:project_id>/comparative-charts', methods=['GET'])
@auth_required
def get_comparative_charts_data(project_id):
    """Obtener datos para gráficas comparativas: proyecto vs competidores seleccionados"""
    user = get_current_user()
    
    if not user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        days = int(request.args.get('days', 30))  # Parámetro opcional para rango de días
        charts_data = get_project_comparative_charts_data(project_id, days)

        return jsonify({
            'success': True,
            'data': charts_data
        })
    except Exception as e:
        logger.error(f"Error getting comparative charts data for project {project_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@manual_ai_bp.route('/api/projects/<int:project_id>/competitors', methods=['GET'])
@auth_required
def get_project_competitors(project_id):
    """Obtener competidores seleccionados de un proyecto"""
    user = get_current_user()
    
    if not user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        conn = get_db_connection()
        if not conn:
            logger.error(f"Failed to get database connection for project {project_id} competitors")
            return jsonify({'success': False, 'error': 'Database connection failed'}), 503
            
        cur = conn.cursor()
        
        cur.execute("""
            SELECT selected_competitors
            FROM manual_ai_projects 
            WHERE id = %s AND is_active = true
        """, (project_id,))
        
        result = cur.fetchone()
        
        if not result:
            logger.warning(f"Project {project_id} not found or inactive")
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Project not found'}), 404
        
        competitors = result['selected_competitors'] if result['selected_competitors'] else []
        
        # Validar que competitors sea una lista
        if not isinstance(competitors, list):
            logger.warning(f"Invalid competitors data type for project {project_id}: {type(competitors)}")
            competitors = []
        
        cur.close()
        conn.close()
        
        logger.info(f"Retrieved {len(competitors)} competitors for project {project_id}")
        
        return jsonify({
            'success': True,
            'competitors': competitors
        })
        
    except Exception as e:
        logger.error(f"Error getting competitors for project {project_id}: {type(e).__name__}: {e}")
        logger.error(f"Error details: {repr(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Close connections if they exist
        try:
            if 'cur' in locals():
                cur.close()
            if 'conn' in locals():
                conn.close()
        except:
            pass
            
        return jsonify({'success': False, 'error': f'Database error: {str(e)}'}), 500

@manual_ai_bp.route('/api/projects/<int:project_id>/competitors', methods=['PUT'])
@auth_required
def update_project_competitors(project_id):
    """Actualizar competidores seleccionados de un proyecto"""
    user = get_current_user()
    
    if not user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        data = request.get_json()
        if not data or 'competitors' not in data:
            return jsonify({'success': False, 'error': 'Missing competitors data'}), 400
        
        competitors = data['competitors']
        
        # Validaciones
        if not isinstance(competitors, list):
            return jsonify({'success': False, 'error': 'Competitors must be a list'}), 400
        
        if len(competitors) > 4:
            return jsonify({'success': False, 'error': 'Maximum 4 competitors allowed'}), 400
        
        # Validar y normalizar dominios
        validated_competitors = []
        for competitor in competitors:
            if not competitor or not isinstance(competitor, str):
                continue
                
            # Normalizar dominio (remover protocolo, www, trailing slash)
            normalized = normalize_search_console_url(competitor.strip())
            if not normalized:
                return jsonify({'success': False, 'error': f'Invalid domain: {competitor}'}), 400
            
            if normalized not in validated_competitors:
                validated_competitors.append(normalized)
        
        # Obtener dominio del proyecto para evitar auto-competencia
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT domain FROM manual_ai_projects WHERE id = %s", (project_id,))
        project_result = cur.fetchone()
        if not project_result:
            return jsonify({'success': False, 'error': 'Project not found'}), 404
        
        project_domain = normalize_search_console_url(project_result['domain'])
        
        # Filtrar el dominio del proyecto si está en competidores
        validated_competitors = [comp for comp in validated_competitors if comp != project_domain]
        
        # Actualizar competidores
        cur.execute("""
            UPDATE manual_ai_projects 
            SET selected_competitors = %s, updated_at = NOW()
            WHERE id = %s
        """, (json.dumps(validated_competitors), project_id))
        
        # Crear evento
        create_project_event(
            project_id=project_id,
            event_type='competitors_updated',
            event_title='Competitors list updated',
            event_description=f'Updated to {len(validated_competitors)} competitors: {", ".join(validated_competitors)}',
            user_id=user['id']
        )
        
        conn.commit()
        cur.close()
        conn.close()
        
        # Sincronizar flags de competidores en datos históricos para mantener consistencia
        sync_historical_competitor_flags(project_id, validated_competitors)
        
        return jsonify({
            'success': True,
            'competitors': validated_competitors,
            'message': f'Successfully updated {len(validated_competitors)} competitors'
        })
        
    except Exception as e:
        logger.error(f"Error updating competitors for project {project_id}: {type(e).__name__}: {e}")
        logger.error(f"Error details: {repr(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Close connections if they exist
        try:
            if 'cur' in locals():
                cur.close()
            if 'conn' in locals():
                conn.close()
        except:
            pass
            
        return jsonify({'success': False, 'error': f'Database error: {str(e)}'}), 500

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
# SERP UTILITY FUNCTIONS - USAR SISTEMA EXISTENTE
# ================================

def convert_iso_to_internal_country(country_code: str) -> str:
    """Convertir códigos ISO a códigos internos del sistema"""
    country_mapping = {
        'US': 'usa',
        'GB': 'gbr', 
        'ES': 'esp',
        'FR': 'fra',
        'DE': 'deu',
        'MX': 'mex',
        'AR': 'arg',
        'CO': 'col',
        'CL': 'chl'
    }
    return country_mapping.get(country_code, 'esp')  # Default a España

# ================================
# FUNCIONES DE BASE DE DATOS
# ================================

def get_user_projects(user_id: int) -> List[Dict]:
    """Obtener todos los proyectos de un usuario con estadísticas básicas"""
    conn = get_db_connection()
    if not conn:
        logger.error("Failed to get database connection for user projects")
        return []
        
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT 
                p.id,
                p.name,
                p.description,
                p.domain,
                p.country_code,
                p.created_at,
                p.updated_at,
                p.selected_competitors,
                COALESCE(jsonb_array_length(p.selected_competitors), 0) AS competitors_count,
                COUNT(DISTINCT k.id) as keyword_count,
                COUNT(DISTINCT CASE WHEN r.has_ai_overview = true THEN r.id END) as ai_overview_count,
                COUNT(DISTINCT CASE WHEN r.domain_mentioned = true THEN r.id END) as mentions_count,
                MAX(r.analysis_date) as last_analysis_date
            FROM manual_ai_projects p
            LEFT JOIN manual_ai_keywords k ON p.id = k.project_id AND k.is_active = true
            LEFT JOIN manual_ai_results r ON p.id = r.project_id
            WHERE p.user_id = %s AND p.is_active = true
            GROUP BY p.id, p.name, p.description, p.domain, p.country_code, p.created_at, p.updated_at, p.selected_competitors
            ORDER BY p.created_at DESC
        """, (user_id,))
        
        projects = cur.fetchall()
        return [dict(project) for project in projects]
        
    except Exception as e:
        logger.error(f"Error fetching user projects for user {user_id}: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def create_new_project(user_id: int, name: str, description: str, domain: str, country_code: str, competitors: List[str] = None) -> int:
    """Crear un nuevo proyecto"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Normalizar dominio del proyecto
    normalized_domain = normalize_search_console_url(domain) or domain
    
    # Procesar y validar competidores
    validated_competitors = []
    if competitors:
        for competitor in competitors[:4]:  # Máximo 4
            if competitor and isinstance(competitor, str):
                normalized_comp = normalize_search_console_url(competitor.strip())
                if normalized_comp and normalized_comp != normalized_domain:
                    if normalized_comp not in validated_competitors:
                        validated_competitors.append(normalized_comp)
    
    cur.execute("""
        INSERT INTO manual_ai_projects (user_id, name, description, domain, country_code, selected_competitors)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (user_id, name, description, normalized_domain, country_code, json.dumps(validated_competitors)))
    
    project_id = cur.fetchone()['id']
    conn.commit()
    cur.close()
    conn.close()
    
    logger.info(f"Created new project {project_id} for user {user_id} with {len(validated_competitors)} competitors")
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

def run_project_analysis(project_id: int, force_overwrite: bool = False) -> List[Dict]:
    """
    Ejecutar análisis completo de todas las keywords activas de un proyecto
    
    Args:
        project_id: ID del proyecto a analizar
        force_overwrite: Si True, sobreescribe resultados existentes del día (para análisis manual)
                        Si False, omite keywords ya analizadas hoy (para análisis automático)
    """
    # Obtener proyecto y keywords
    project = get_project_with_details(project_id)
    keywords = [k for k in get_keywords_for_project(project_id) if k['is_active']]
    
    if not project or not keywords:
        return []
    
    results = []
    failed_keywords = 0
    today = date.today()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    analysis_mode = "MANUAL (with overwrite)" if force_overwrite else "AUTOMATIC (skip existing)"
    logger.info(f"🚀 Starting {analysis_mode} analysis for project {project_id} with {len(keywords)} user-defined keywords")
    
    for keyword_data in keywords:
        keyword = keyword_data['keyword']
        keyword_id = keyword_data['id']
        
        try:
            # Verificar si ya existe análisis para hoy
            cur.execute("""
                SELECT 1 FROM manual_ai_results 
                WHERE project_id = %s AND keyword_id = %s AND analysis_date = %s
            """, (project_id, keyword_id, today))
            
            existing_analysis = cur.fetchone()
            
            if existing_analysis and not force_overwrite:
                # Análisis automático: omitir si ya existe
                logger.debug(f"Analysis already exists for keyword '{keyword}' on {today}, skipping (auto mode)")
                continue
            elif existing_analysis and force_overwrite:
                # Análisis manual: eliminar resultado existente para sobreescribir
                cur.execute("""
                    DELETE FROM manual_ai_results 
                    WHERE project_id = %s AND keyword_id = %s AND analysis_date = %s
                """, (project_id, keyword_id, today))
                logger.info(f"🔄 Overwriting existing analysis for keyword '{keyword}' (manual mode)")
            # Si no existe, continuar normalmente
            
            # ✅ USAR LÓGICA SIMILAR AL AUTOMÁTICO (ADAPTADA AL CONTEXTO MANUAL)
            # DIFERENCIAS vs Sistema Automático:
            # - País fijo del proyecto (no detección dinámica por GSC)
            # - Keywords definidas por usuario (no top keywords de GSC)
            # - Dominio fijo del proyecto (no múltiples sitios)
            try:
                # 1. Verificar caché primero (igual que sistema automático)
                internal_country = convert_iso_to_internal_country(project['country_code'])
                cached_result = ai_cache.get_cached_analysis(keyword, project['domain'], internal_country)
                
                if cached_result and cached_result.get('analysis'):
                    logger.info(f"💾 Using cached result for '{keyword}'")
                    ai_result = cached_result['analysis'].get('ai_analysis', {})
                else:
                    # 2. Obtener SERP con reintentos y backoff (tolerancia a 429/timeout)
                    api_key = os.getenv('SERPAPI_KEY')
                    if not api_key:
                        logger.error(f"❌ SERPAPI_KEY not configured for keyword '{keyword}' in project {project_id}")
                        logger.error(f"❌ Available env vars: {', '.join([k for k in os.environ.keys() if 'API' in k or 'KEY' in k])}")
                        failed_keywords += 1
                        continue

                    from services.country_config import get_country_config

                    serp_params_base = {
                        'engine': 'google',
                        'q': keyword,
                        'api_key': api_key,
                        'num': 20
                    }
                    country_config = get_country_config(internal_country)
                    if country_config:
                        serp_params_base.update({
                            'location': country_config['serp_location'],
                            'gl': country_config['serp_gl'],
                            'hl': country_config['serp_hl'],
                            'google_domain': country_config['google_domain']
                        })
                        logger.debug(f"Using {country_config['name']} config for '{keyword}'")

                    @with_backoff(max_attempts=3, base_delay_sec=1.0)
                    def fetch_serp():
                        data = get_serp_json(dict(serp_params_base))
                        if not data or data.get('error'):
                            raise RuntimeError(data.get('error', 'SERP fetch error'))
                        return data

                    serp_data = fetch_serp()

                    # 3. Analizar AI Overview usando servicio existente
                    ai_result = detect_ai_overview_elements(serp_data, project['domain'])
                    
                    # 5. Guardar en caché (igual que sistema automático)
                    ai_cache.cache_analysis(keyword, project['domain'], internal_country, {
                        'keyword': keyword,
                        'ai_analysis': ai_result,
                        'timestamp': time.time(),
                        'country_analyzed': internal_country
                    })
                    
            except Exception as serp_error:
                logger.error(f"Error analyzing keyword '{keyword}': {serp_error}")
                failed_keywords += 1
                continue
            
            # Guardar resultado en base de datos
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
            
            # NUEVA FUNCIONALIDAD: Detectar y almacenar TODOS los dominios en AI Overview
            if ai_result.get('has_ai_overview', False):
                store_global_domains_detected(
                    project_id=project_id,
                    keyword_id=keyword_id,
                    keyword=keyword,
                    project_domain=project['domain'],
                    ai_analysis_data=ai_result,
                    analysis_date=today,
                    country_code=project['country_code'],
                    selected_competitors=project.get('selected_competitors', [])
                )
            
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
            failed_keywords += 1
            continue
    
    conn.commit()
    cur.close()
    conn.close()
    
    overwrite_info = " (with overwrite)" if force_overwrite else " (skipping existing)"
    logger.info(f"✅ Completed {analysis_mode} analysis for project {project_id}: {len(results)}/{len(keywords)} keywords processed, {failed_keywords} failed{overwrite_info}")
    if failed_keywords > 0:
        logger.warning(f"⚠️ {failed_keywords} keywords failed analysis (check SERPAPI_KEY configuration)")
    return results

# ================================
# SISTEMA CRON DIARIO
# ================================

def run_daily_analysis_for_all_projects():
    """
    Ejecutar análisis diario para todos los proyectos activos.
    Esta función está destinada a ser ejecutada por cron job diario.
    """
    job_id = f"cron-{int(time.time())}"
    started_at = time.time()
    logger.info(json.dumps({
        "event": "cron_start",
        "job_id": job_id,
        "ts": now_utc_iso()
    }))

    # ---------- Lock de concurrencia por día (PostgreSQL advisory lock) ----------
    lock_conn = None
    lock_cur = None
    lock_acquired = False
    lock_class_id = 4242
    lock_object_id = int(date.today().strftime('%Y%m%d'))

    try:
        lock_conn = get_db_connection()
        if not lock_conn:
            logger.error("❌ No se pudo conectar a la base de datos para adquirir el lock")
            return {"success": False, "error": "DB connection failed for lock"}
        lock_cur = lock_conn.cursor()
        lock_cur.execute("SELECT pg_try_advisory_lock(%s, %s) as lock_acquired", (lock_class_id, lock_object_id))
        result = lock_cur.fetchone()
        lock_acquired = bool(result['lock_acquired']) if result else False
        
        logger.info(f"🔐 Advisory lock attempt: class_id={lock_class_id}, object_id={lock_object_id}, acquired={lock_acquired}")

        if not lock_acquired:
            logger.info(json.dumps({
                "event": "cron_skipped_lock",
                "job_id": job_id,
                "ts": now_utc_iso()
            }))
            lock_cur.close(); lock_conn.close()
            return {"success": True, "message": "Another daily run in progress (skipped)", "skipped": 0, "failed": 0, "successful": 0, "total_projects": 0}
        
        logger.info("✅ Advisory lock adquirido exitosamente. Continuando con análisis...")
        # Obtener todos los proyectos activos
        conn = get_db_connection()
        if not conn:
            error_msg = "No se pudo conectar a la base de datos"
            logger.error(f"❌ {error_msg}")
            return {"success": False, "error": error_msg}
            
        cur = conn.cursor()
        
        cur.execute("""
            SELECT p.id, p.name, p.domain, p.country_code, p.user_id,
                   COUNT(k.id) as keyword_count
            FROM manual_ai_projects p
            LEFT JOIN manual_ai_keywords k ON p.id = k.project_id AND k.is_active = true
            WHERE p.is_active = true
            GROUP BY p.id, p.name, p.domain, p.country_code, p.user_id
            HAVING COUNT(k.id) > 0
            ORDER BY p.id
        """)
        
        projects = cur.fetchall()
        cur.close()
        conn.close()
        
        if not projects:
            logger.info("⏭️ No active projects found for daily analysis")
            return {"success": True, "message": "No active projects", "processed": 0}
        
        logger.info(json.dumps({
            "event": "cron_projects_found",
            "job_id": job_id,
            "count": len(projects)
        }))
        for i, project in enumerate(projects):
            project_data = project if isinstance(project, dict) else {
                'id': project[0], 'name': project[1], 'domain': project[2], 
                'country_code': project[3], 'user_id': project[4], 'keyword_count': project[5]
            }
            logger.info(f"📋 Project {i+1}: ID={project_data['id']}, Name='{project_data['name']}', Domain='{project_data['domain']}', Keywords={project_data['keyword_count']}")
        
        successful_analyses = 0
        failed_analyses = 0
        skipped_analyses = 0
        total_keywords_processed = 0
        
        for project in projects:
            # Convertir el resultado del cursor a diccionario si es necesario
            if isinstance(project, (tuple, list)):
                project_dict = {
                    'id': project[0],
                    'name': project[1], 
                    'domain': project[2],
                    'country_code': project[3],
                    'user_id': project[4],
                    'keyword_count': project[5]
                }
            else:
                # Ya es un diccionario (RealDictRow)
                project_dict = dict(project)
            
            try:
                # Verificar si ya se ejecutó hoy
                today = date.today()
                conn = get_db_connection()
                cur = conn.cursor()
                
                cur.execute("""
                    SELECT COUNT(*) as count
                    FROM manual_ai_results 
                    WHERE project_id = %s AND analysis_date = %s
                """, (project_dict['id'], today))
                
                result_row = cur.fetchone()
                existing_results = result_row['count'] if result_row else 0
                cur.close()
                conn.close()
                
                if existing_results > 0:
                    logger.info(f"⏭️ Project {project_dict['id']} ({project_dict['name']}) already analyzed today with {existing_results} results, skipping")
                    skipped_analyses += 1
                    continue
                
                logger.info(f"🚀 Starting daily analysis for project {project_dict['id']} ({project_dict['name']}) - {project_dict['keyword_count']} keywords")
                
                # Ejecutar análisis automático (sin sobreescritura)
                results = run_project_analysis(project_dict['id'], force_overwrite=False)
                total_keywords_processed += len(results)
                
                # Crear snapshot diario
                create_daily_snapshot(project_dict['id'])
                
                # Crear evento
                create_project_event(
                    project_id=project_dict['id'],
                    event_type='daily_analysis',
                    event_title='Daily automated analysis completed',
                    keywords_affected=len(results),
                    user_id=project_dict['user_id']
                )
                
                logger.info(f"✅ Completed daily analysis for project {project_dict['id']}: {len(results)} keywords processed")
                successful_analyses += 1
                
            except Exception as e:
                logger.error(f"❌ Failed daily analysis for project {project_dict['id']} ({project_dict['name']}): {e}")
                logger.error(f"❌ Error type: {type(e)}")
                import traceback
                logger.error(f"❌ Traceback: {traceback.format_exc()}")
                failed_analyses += 1
                
                # Crear evento de error
                try:
                    create_project_event(
                        project_id=project_dict['id'],
                        event_type='analysis_failed',
                        event_title=f'Daily analysis failed: {str(e)[:100]}',
                        keywords_affected=0,
                        user_id=project_dict['user_id']
                    )
                except Exception as event_error:
                    logger.error(f"Failed to create error event: {event_error}")
        
        # Resumen final
        total_projects = len(projects)
        logger.info(f"🏁 === ANÁLISIS DIARIO COMPLETADO ===")
        logger.info(f"📊 Total proyectos: {total_projects}")
        logger.info(f"✅ Exitosos: {successful_analyses}")
        logger.info(f"❌ Fallidos: {failed_analyses}")
        logger.info(f"⏭️ Omitidos (ya analizados): {skipped_analyses}")
        duration_ms = int((time.time() - started_at) * 1000)
        logger.info(json.dumps({
            "event": "cron_finished",
            "job_id": job_id,
            "duration_ms": duration_ms,
            "projects": total_projects,
            "successful": successful_analyses,
            "failed": failed_analyses,
            "skipped": skipped_analyses,
            "keywords_processed": total_keywords_processed
        }))

        return {
            "success": True,
            "message": "Daily analysis completed",
            "total_projects": total_projects,
            "successful": successful_analyses,
            "failed": failed_analyses,
            "skipped": skipped_analyses,
            "keywords_processed": total_keywords_processed,
            "duration_ms": duration_ms,
            "job_id": job_id
        }
        
    except Exception as e:
        logger.error(json.dumps({
            "event": "cron_error",
            "job_id": job_id,
            "error": str(e)
        }))
        logger.error(f"❌ Error type: {type(e)}")
        import traceback
        logger.error(f"❌ Full traceback: {traceback.format_exc()}")
        return {"success": False, "error": str(e)}
    finally:
        # Liberar el lock
        try:
            if lock_acquired and lock_conn and lock_cur:
                lock_cur.execute("SELECT pg_advisory_unlock(%s, %s)", (lock_class_id, lock_object_id))
                lock_conn.commit()
        except Exception as unlock_err:
            logger.error(f"⚠️ Error liberando el lock de cron: {unlock_err}")
        finally:
            try:
                if lock_cur:
                    lock_cur.close()
            finally:
                if lock_conn:
                    lock_conn.close()

@manual_ai_bp.route('/api/cron/daily-analysis', methods=['POST'])
@cron_or_auth_required
def trigger_daily_analysis():
    """
    Endpoint para ejecutar manualmente el análisis diario.
    Útil para testing y ejecución manual del cron.
    """
    try:
        user = get_current_user()
        if user:
            logger.info(f"🔧 Manual cron trigger by user: {user.get('email', 'unknown')}")
        else:
            logger.info("🔧 Manual cron trigger by CRON TOKEN")
        
        # Verificar conexión a la base de datos primero
        conn = get_db_connection()
        if not conn:
            error_msg = "Database connection failed"
            logger.error(f"❌ {error_msg}")
            return jsonify({"success": False, "error": error_msg}), 500
        conn.close()

        # Modo asíncrono opcional para evitar timeouts
        async_flag = (
            str(request.args.get('async', '')).lower() in ('1', 'true', 'yes') or
            str(request.headers.get('X-Async', '')).lower() in ('1', 'true', 'yes')
        )

        if async_flag:
            logger.info("🚀 Async daily analysis requested. Launching background job...")

            def _run_job():
                try:
                    result = run_daily_analysis_for_all_projects()
                    logger.info(json.dumps({
                        "event": "cron_async_finished",
                        "result": {k: result.get(k) for k in ("success","total_projects","successful","failed","skipped","keywords_processed","duration_ms","job_id")}
                    }))
                except Exception as e:
                    logger.error(json.dumps({"event": "cron_async_error", "error": str(e)}))

            t = threading.Thread(target=_run_job, daemon=True)
            t.start()
            return jsonify({"success": True, "started": True, "mode": "async"}), 202

        # Modo síncrono (por defecto)
        result = run_daily_analysis_for_all_projects()

        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify(result), 400  # Cambiar a 400 para errores de negocio
            
    except Exception as e:
        logger.error(f"❌ Error in manual daily analysis trigger: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500

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

def get_project_analysis_results(project_id: int, days: int = 30) -> List[Dict]:
    """Obtener resultados de análisis de un proyecto"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    cur.execute("""
        SELECT 
            r.analysis_date,
            r.keyword,
            r.has_ai_overview,
            r.domain_mentioned,
            r.domain_position,
            r.ai_elements_count,
            r.impact_score,
            k.is_active
        FROM manual_ai_results r
        JOIN manual_ai_keywords k ON r.keyword_id = k.id
        WHERE r.project_id = %s 
        AND r.analysis_date >= %s 
        AND r.analysis_date <= %s
        ORDER BY r.analysis_date DESC, r.keyword
    """, (project_id, start_date, end_date))
    
    results = [dict(row) for row in cur.fetchall()]
    cur.close()
    conn.close()
    
    return results

def get_project_statistics(project_id: int, days: int = 30) -> Dict:
    """Obtener estadísticas completas de un proyecto para gráficos"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    # Estadísticas principales - CORREGIDO: Solo cuenta resultados más recientes por keyword
    cur.execute("""
        WITH latest_results AS (
            SELECT DISTINCT ON (k.id) 
                k.id as keyword_id,
                k.is_active,
                r.has_ai_overview,
                r.domain_mentioned,
                r.domain_position,
                r.analysis_date
            FROM manual_ai_keywords k
            LEFT JOIN manual_ai_results r ON k.id = r.keyword_id 
                AND r.analysis_date >= %s AND r.analysis_date <= %s
            WHERE k.project_id = %s
            ORDER BY k.id, r.analysis_date DESC
        )
        SELECT 
            COUNT(*) as total_keywords,
            COUNT(CASE WHEN is_active = true THEN 1 END) as active_keywords,
            COUNT(CASE WHEN has_ai_overview = true THEN 1 END) as total_ai_keywords,
            COUNT(CASE WHEN domain_mentioned = true THEN 1 END) as total_mentions,
            AVG(CASE WHEN domain_position IS NOT NULL THEN domain_position END) as avg_position,
            (COUNT(CASE WHEN domain_mentioned = true THEN 1 END)::float / 
             NULLIF(COUNT(CASE WHEN has_ai_overview = true THEN 1 END), 0)::float * 100) as visibility_percentage,
            (COUNT(CASE WHEN has_ai_overview = true THEN 1 END)::float / 
             NULLIF(COUNT(CASE WHEN analysis_date IS NOT NULL THEN 1 END), 0)::float * 100) as aio_weight_percentage
        FROM latest_results
    """, (start_date, end_date, project_id))
    
    main_stats = dict(cur.fetchone() or {})
    
    # Datos para gráfico de visibilidad por día - CORREGIDO: Solo cuenta keywords únicas
    cur.execute("""
        SELECT 
            r.analysis_date,
            COUNT(DISTINCT CASE WHEN r.has_ai_overview = true THEN r.keyword_id END) as ai_keywords,
            COUNT(DISTINCT CASE WHEN r.domain_mentioned = true THEN r.keyword_id END) as mentions,
            (COUNT(DISTINCT CASE WHEN r.domain_mentioned = true THEN r.keyword_id END)::float / 
             NULLIF(COUNT(DISTINCT CASE WHEN r.has_ai_overview = true THEN r.keyword_id END), 0)::float * 100) as visibility_pct
        FROM manual_ai_results r
        WHERE r.project_id = %s AND r.analysis_date >= %s AND r.analysis_date <= %s
        GROUP BY r.analysis_date
        ORDER BY r.analysis_date
    """, (project_id, start_date, end_date))
    
    visibility_data = [dict(row) for row in cur.fetchall()]
    
    # Datos para gráfico de posiciones - CORREGIDO: Cuenta keywords únicas por posición
    cur.execute("""
        SELECT 
            r.analysis_date,
            COUNT(DISTINCT CASE WHEN r.domain_position BETWEEN 1 AND 3 THEN r.keyword_id END) as pos_1_3,
            COUNT(DISTINCT CASE WHEN r.domain_position BETWEEN 4 AND 10 THEN r.keyword_id END) as pos_4_10,
            COUNT(DISTINCT CASE WHEN r.domain_position BETWEEN 11 AND 20 THEN r.keyword_id END) as pos_11_20,
            COUNT(DISTINCT CASE WHEN r.domain_position > 20 THEN r.keyword_id END) as pos_21_plus
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

def get_project_top_domains(project_id: int, limit: int = 10) -> List[Dict]:
    """
    Obtener los dominios más visibles para un proyecto específico.
    Calcula la visibilidad basada en frecuencia de aparición y posición promedio.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Obtener dominios de AI Overview que no sean el dominio del proyecto
        cur.execute("""
            SELECT 
                p.domain as project_domain
            FROM manual_ai_projects p
            WHERE p.id = %s
        """, (project_id,))
        
        project_data = cur.fetchone()
        if not project_data:
            return []
        
        project_domain = project_data[0]
        
        # Obtener análisis de dominios en AI Overview (excluyendo el dominio del proyecto) - CORREGIDO
        cur.execute("""
            SELECT 
                ref->>'link' as ref_link,
                (ref->>'index')::int as ref_index,
                ref->>'source' as ref_source,
                ref->>'title' as ref_title,
                r.analysis_date,
                r.keyword
            FROM manual_ai_results r
            JOIN manual_ai_keywords k ON r.keyword_id = k.id
            LEFT JOIN LATERAL jsonb_array_elements(r.ai_analysis_data->'debug_info'->'references_found') AS ref ON true
            WHERE k.project_id = %s 
                AND r.has_ai_overview = true
                AND r.ai_analysis_data IS NOT NULL
                AND r.ai_analysis_data->'debug_info'->'references_found' IS NOT NULL
                AND ref->>'link' IS NOT NULL
                AND ref->>'link' != ''
                AND r.analysis_date >= NOW() - INTERVAL '30 days'
        """, (project_id,))
        
        results = cur.fetchall()
        
        # Procesar referencias para extraer dominios - CORREGIDO
        domain_stats = {}
        
        for ref_link, ref_index, ref_source, ref_title, analysis_date, keyword in results:
            if not ref_link:
                continue
                
            # Extraer dominio de la URL
            domain = extract_domain_from_url(ref_link)
            
            # Filtrar el dominio del proyecto y dominios inválidos
            if not domain or domain == project_domain or domain in ['', 'localhost', 'example.com']:
                continue
            
            # Acumular estadísticas por dominio
            if domain not in domain_stats:
                domain_stats[domain] = {
                    'domain': domain,
                    'appearances': 0,
                    'positions': [],
                    'dates': set(),
                    'keywords': set()
                }
            
            domain_stats[domain]['appearances'] += 1
            if ref_index is not None:
                # Posición en AI Overview es index + 1 (SERPAPI usa índice 0-based)
                domain_stats[domain]['positions'].append(ref_index + 1)
            domain_stats[domain]['dates'].add(str(analysis_date.date()) if analysis_date else None)
            domain_stats[domain]['keywords'].add(keyword)
        
        # Calcular promedios y scores - MEJORADO
        domain_list = []
        for domain, stats in domain_stats.items():
            avg_position = sum(stats['positions']) / len(stats['positions']) if stats['positions'] else None
            
            # Solo incluir dominios con datos válidos
            if stats['appearances'] > 0:
                domain_list.append({
                    'domain': domain,
                    'appearances': stats['appearances'],
                    'avg_position': round(avg_position, 1) if avg_position else None,
                    'unique_dates': len([d for d in stats['dates'] if d]),
                    'unique_keywords': len(stats['keywords']),
                    'positions': stats['positions'],  # Para análisis detallado
                    'visibility_score': stats['appearances'] / len(stats['keywords']) if stats['keywords'] else 0
                })
        
        # Ordenar por número de apariciones (descendente) y luego por posición promedio (ascendente)
        domain_list.sort(key=lambda x: (-x['appearances'], x['avg_position'] or 999))
        
        # Retornar los top N dominios
        return domain_list[:limit]
        
    except Exception as e:
        logger.error(f"Error getting top domains for project {project_id}: {e}")
        return []
    finally:
        conn.close()

def get_project_competitors_charts_data(project_id: int, days: int = 30) -> Dict:
    """
    Obtener datos históricos de competidores para gráficas de visibilidad y evolución de posiciones.
    Retorna datos para Brand Visibility Index (scatter) y Brand Position Over Time (líneas).
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        # Obtener dominio del proyecto
        cur.execute("SELECT domain FROM manual_ai_projects WHERE id = %s", (project_id,))
        project_data = cur.fetchone()
        if not project_data:
            return {'visibility_scatter': [], 'position_evolution': [], 'domains': []}
        
        project_domain = project_data[0]
        
        # Obtener todos los datos de referencias históricas
        cur.execute("""
            SELECT 
                ref->>'link' as ref_link,
                (ref->>'index')::int as ref_index,
                ref->>'source' as ref_source,
                ref->>'title' as ref_title,
                r.analysis_date,
                r.keyword,
                k.id as keyword_id
            FROM manual_ai_results r
            JOIN manual_ai_keywords k ON r.keyword_id = k.id
            LEFT JOIN LATERAL jsonb_array_elements(r.ai_analysis_data->'debug_info'->'references_found') AS ref ON true
            WHERE k.project_id = %s 
                AND r.has_ai_overview = true
                AND r.ai_analysis_data IS NOT NULL
                AND r.ai_analysis_data->'debug_info'->'references_found' IS NOT NULL
                AND ref->>'link' IS NOT NULL
                AND ref->>'link' != ''
                AND r.analysis_date >= %s 
                AND r.analysis_date <= %s
            ORDER BY r.analysis_date ASC
        """, (project_id, start_date, end_date))
        
        results = cur.fetchall()
        
        # Procesar datos por dominio y fecha
        domain_daily_data = {}
        all_domains = set()
        
        for ref_link, ref_index, ref_source, ref_title, analysis_date, keyword, keyword_id in results:
            if not ref_link:
                continue
                
            domain = extract_domain_from_url(ref_link)
            if not domain or domain == project_domain:
                continue
                
            all_domains.add(domain)
            date_str = str(analysis_date.date())
            
            if domain not in domain_daily_data:
                domain_daily_data[domain] = {}
            
            if date_str not in domain_daily_data[domain]:
                domain_daily_data[domain][date_str] = {
                    'appearances': 0,
                    'positions': [],
                    'keywords': set(),
                    'total_keywords_analyzed': set()  # Para calcular brand likelihood
                }
            
            domain_daily_data[domain][date_str]['appearances'] += 1
            if ref_index is not None:
                domain_daily_data[domain][date_str]['positions'].append(ref_index + 1)
            domain_daily_data[domain][date_str]['keywords'].add(keyword)
        
        # Obtener total de keywords analizadas por día para calcular Brand Likelihood
        cur.execute("""
            SELECT 
                r.analysis_date,
                COUNT(DISTINCT r.keyword_id) as total_keywords_with_ai
            FROM manual_ai_results r
            JOIN manual_ai_keywords k ON r.keyword_id = k.id
            WHERE k.project_id = %s 
                AND r.has_ai_overview = true
                AND r.analysis_date >= %s 
                AND r.analysis_date <= %s
            GROUP BY r.analysis_date
            ORDER BY r.analysis_date
        """, (project_id, start_date, end_date))
        
        daily_totals = {str(row['analysis_date'].date()): row['total_keywords_with_ai'] for row in cur.fetchall()}
        
        # Calcular métricas finales para cada dominio
        visibility_scatter = []  # Para gráfica scatter de visibilidad
        position_evolution = []  # Para gráfica de líneas de evolución
        
        # Ordenar dominios por total de apariciones para seleccionar top competitors
        domain_totals = {}
        for domain, daily_data in domain_daily_data.items():
            total_appearances = sum(data['appearances'] for data in daily_data.values())
            domain_totals[domain] = total_appearances
        
        # Seleccionar top 6 dominios más visibles
        top_domains = sorted(domain_totals.items(), key=lambda x: x[1], reverse=True)[:6]
        selected_domains = [domain for domain, _ in top_domains]
        
        # Generar datos para scatter chart (Brand Visibility Index)
        for domain in selected_domains:
            daily_data = domain_daily_data.get(domain, {})
            
            total_appearances = sum(data['appearances'] for data in daily_data.values())
            all_positions = []
            total_keywords = set()
            
            for data in daily_data.values():
                all_positions.extend(data['positions'])
                total_keywords.update(data['keywords'])
            
            if total_appearances > 0 and all_positions:
                avg_position = sum(all_positions) / len(all_positions)
                
                # Brand Likelihood = apariciones / total keywords analizadas (%)
                total_analyzed = sum(daily_totals.values()) if daily_totals else 1
                brand_likelihood = (len(total_keywords) / total_analyzed) * 100 if total_analyzed > 0 else 0
                
                # Visibility Score = apariciones ponderadas por posición
                visibility_score = total_appearances * (11 - min(avg_position, 10)) / 10
                
                visibility_scatter.append({
                    'domain': domain,
                    'x': visibility_score,  # Eje X: Visibility Score (Brand Mentions)
                    'y': brand_likelihood,  # Eje Y: Likelihood to buy (%)
                    'appearances': total_appearances,
                    'avg_position': round(avg_position, 1),
                    'keywords_count': len(total_keywords)
                })
        
        # Generar datos para line chart (Brand Position Over Time)
        date_range = []
        current_date = start_date
        while current_date <= end_date:
            date_range.append(str(current_date))
            current_date += timedelta(days=1)
        
        position_evolution = {
            'dates': date_range,
            'datasets': []
        }
        
        # Colores para las líneas de competidores (usando paleta de AI Overview)
        colors = [
            '#D9FAB9',  # Verde claro (Your Domain)
            '#F2B9FA',  # Rosa/Magenta claro 
            '#FADBB9',  # Naranja/Beige claro
            '#B9E8FA',  # Azul claro
            '#D8F9B8',  # Verde adicional
            '#F0C8FA'   # Rosa adicional
        ]
        
        for i, domain in enumerate(selected_domains):
            daily_data = domain_daily_data.get(domain, {})
            positions_by_date = []
            
            for date_str in date_range:
                if date_str in daily_data and daily_data[date_str]['positions']:
                    avg_pos = sum(daily_data[date_str]['positions']) / len(daily_data[date_str]['positions'])
                    positions_by_date.append(round(avg_pos, 1))
                else:
                    positions_by_date.append(None)  # No data for this date
            
            position_evolution['datasets'].append({
                'label': domain,
                'data': positions_by_date,
                'borderColor': colors[i % len(colors)],
                'backgroundColor': colors[i % len(colors)] + '20',  # 20% opacity
                'tension': 0.4,
                'pointRadius': 3,
                'pointHoverRadius': 5
            })
        
        return {
            'visibility_scatter': visibility_scatter,
            'position_evolution': position_evolution,
            'domains': selected_domains,
            'date_range': {
                'start': str(start_date),
                'end': str(end_date)
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting competitors charts data for project {project_id}: {e}")
        return {'visibility_scatter': [], 'position_evolution': [], 'domains': []}
    finally:
        cur.close()
        conn.close()

def extract_domain_from_url(url: str) -> str:
    """Extraer dominio de una URL"""
    try:
        if not url:
            return None
            
        # Añadir https:// si no tiene esquema
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        # Usar urlparse para extraer el dominio
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Remover www. si existe
        if domain.startswith('www.'):
            domain = domain[4:]
            
        return domain if domain else None
        
    except Exception:
        return None

def get_project_comparative_charts_data(project_id: int, days: int = 30) -> Dict:
    """
    Obtener datos para gráficas comparativas: dominio del proyecto vs competidores seleccionados.
    
    Retorna datos para:
    1. Gráfica de % visibilidad en AI Overview (líneas por dominio)
    2. Gráfica de posición media en AI Overview (líneas por dominio)
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        # Obtener proyecto con competidores seleccionados
        cur.execute("""
            SELECT domain, selected_competitors 
            FROM manual_ai_projects 
            WHERE id = %s
        """, (project_id,))
        project_data = cur.fetchone()
        
        if not project_data:
            return {'visibility_chart': {}, 'position_chart': {}, 'domains': []}
        
        project_domain = project_data['domain']
        selected_competitors = project_data['selected_competitors'] or []
        
        # Lista de dominios a comparar: proyecto + competidores seleccionados
        domains_to_compare = [project_domain] + selected_competitors
        
        # Obtener datos de visibilidad y posición por fecha para cada dominio
        visibility_chart_data = {'dates': [], 'datasets': []}
        position_chart_data = {'dates': [], 'datasets': []}
        
        # Obtener fechas reales con datos (como get_project_statistics)
        cur.execute("""
            SELECT DISTINCT r.analysis_date
            FROM manual_ai_results r
            WHERE r.project_id = %s AND r.analysis_date >= %s AND r.analysis_date <= %s
            ORDER BY r.analysis_date
        """, (project_id, start_date, end_date))
        
        date_range = [str(row['analysis_date']) for row in cur.fetchall()]
        
        visibility_chart_data['dates'] = date_range
        position_chart_data['dates'] = date_range
        
        # Paleta de colores actualizada
        domain_colors = {
            project_domain: '#5BF0AF',  # Verde actualizado para dominio del usuario
        }
        
        competitor_colors = ['#F0715B', '#1851F1', '#A1A9FF', '#8EAA96']  # Nueva paleta: Naranja, Azul, Lila, Verde gris
        for i, competitor in enumerate(selected_competitors):
            if i < len(competitor_colors):
                domain_colors[competitor] = competitor_colors[i]
        
        # Para cada dominio, obtener sus métricas por fecha
        for domain in domains_to_compare:
            # Datos de visibilidad - CORREGIDO: Usar misma lógica que get_project_statistics
            if domain == project_domain:
                # Para dominio del proyecto, usar manual_ai_results (datos primarios)
                cur.execute("""
                    SELECT 
                        r.analysis_date,
                        (COUNT(DISTINCT CASE WHEN r.domain_mentioned = true THEN r.keyword_id END)::float / 
                         NULLIF(COUNT(DISTINCT CASE WHEN r.has_ai_overview = true THEN r.keyword_id END), 0)::float * 100) as visibility_percentage
                    FROM manual_ai_results r
                    WHERE r.project_id = %s AND r.analysis_date >= %s AND r.analysis_date <= %s
                    GROUP BY r.analysis_date
                    ORDER BY r.analysis_date
                """, (project_id, start_date, end_date))
            else:
                # Para competidores, usar manual_ai_global_domains
                cur.execute("""
                    WITH daily_metrics AS (
                        SELECT 
                            gd.analysis_date,
                            COUNT(DISTINCT gd.keyword_id) as domain_appearances,
                            (
                                SELECT COUNT(DISTINCT r.keyword_id)
                                FROM manual_ai_results r
                                WHERE r.project_id = %s 
                                AND r.analysis_date = gd.analysis_date
                                AND r.has_ai_overview = true
                            ) as total_ai_keywords
                        FROM manual_ai_global_domains gd
                        WHERE gd.project_id = %s 
                        AND gd.detected_domain = %s
                        AND gd.analysis_date >= %s 
                        AND gd.analysis_date <= %s
                        GROUP BY gd.analysis_date
                    )
                    SELECT 
                        analysis_date,
                        CASE 
                            WHEN total_ai_keywords > 0 
                            THEN (domain_appearances::float / total_ai_keywords::float * 100) 
                            ELSE 0 
                        END as visibility_percentage
                    FROM daily_metrics
                    ORDER BY analysis_date
                """, (project_id, project_id, domain, start_date, end_date))
            
            visibility_results = cur.fetchall()
            visibility_by_date = {str(row['analysis_date']): row['visibility_percentage'] for row in visibility_results}
            
            # Datos de posición media - CORREGIDO: Consistencia con get_project_statistics
            if domain == project_domain:
                # Para dominio del proyecto, usar manual_ai_results (datos primarios)
                cur.execute("""
                    SELECT 
                        r.analysis_date,
                        AVG(CASE WHEN r.domain_position IS NOT NULL THEN r.domain_position END) as avg_position
                    FROM manual_ai_results r
                    WHERE r.project_id = %s AND r.analysis_date >= %s AND r.analysis_date <= %s
                        AND r.domain_mentioned = true
                    GROUP BY r.analysis_date
                    ORDER BY r.analysis_date
                """, (project_id, start_date, end_date))
            else:
                # Para competidores, usar manual_ai_global_domains
                cur.execute("""
                    SELECT 
                        gd.analysis_date,
                        AVG(gd.domain_position) as avg_position
                    FROM manual_ai_global_domains gd
                    WHERE gd.project_id = %s 
                    AND gd.detected_domain = %s
                    AND gd.analysis_date >= %s 
                    AND gd.analysis_date <= %s
                    GROUP BY gd.analysis_date
                    ORDER BY gd.analysis_date
                """, (project_id, domain, start_date, end_date))
            
            position_results = cur.fetchall()
            position_by_date = {str(row['analysis_date']): row['avg_position'] for row in position_results}
            
            # Preparar datos para las gráficas
            visibility_data = []
            position_data = []
            
            for date_str in date_range:
                visibility_data.append(visibility_by_date.get(date_str, None))
                position_data.append(position_by_date.get(date_str, None))
            
            # Determinar el label del dominio
            domain_label = domain
            
            # Dataset para gráfica de visibilidad
            visibility_chart_data['datasets'].append({
                'label': domain_label,
                'data': visibility_data,
                'borderColor': domain_colors.get(domain, '#6B7280'),
                'backgroundColor': domain_colors.get(domain, '#6B7280') + '20',
                'tension': 0.4,
                'pointRadius': 3,
                'pointHoverRadius': 5,
                'borderWidth': domain == project_domain and 3 or 2  # Línea más gruesa para dominio del proyecto
            })
            
            # Dataset para gráfica de posición
            position_chart_data['datasets'].append({
                'label': domain_label,
                'data': position_data,
                'borderColor': domain_colors.get(domain, '#6B7280'),
                'backgroundColor': domain_colors.get(domain, '#6B7280') + '20',
                'tension': 0.4,
                'pointRadius': 3,
                'pointHoverRadius': 5,
                'borderWidth': domain == project_domain and 3 or 2
            })
        
        return {
            'visibility_chart': visibility_chart_data,
            'position_chart': position_chart_data,
            'domains': domains_to_compare,
            'date_range': {
                'start': str(start_date),
                'end': str(end_date)
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting comparative charts data for project {project_id}: {e}")
        return {'visibility_chart': {}, 'position_chart': {}, 'domains': []}
    finally:
        cur.close()
        conn.close()

def get_project_global_domains_ranking(project_id: int, days: int = 30) -> List[Dict]:
    """
    Obtener ranking global de TODOS los dominios detectados en AI Overview.
    
    Nueva lógica de agregación:
    - Total de Apariciones: Suma de apariciones diarias durante el período
    - Porcentaje de Visibilidad: Total apariciones / total keywords con AI Overview del período
    - Posición Media: Media ponderada sobre el total de búsquedas del período
    - Resaltado si es dominio del proyecto o competidor seleccionado
    - Ordenado por apariciones (desc) y posición media (asc)
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        # Obtener proyecto con competidores seleccionados
        cur.execute("""
            SELECT domain, selected_competitors 
            FROM manual_ai_projects 
            WHERE id = %s
        """, (project_id,))
        project_data = cur.fetchone()
        
        if not project_data:
            return []
        
        # Usar claves de diccionario por RealDictCursor
        project_domain = project_data['domain']
        selected_competitors = project_data['selected_competitors'] or []
        
        # Lógica corregida: total de AI Overviews generados durante el período
        # Ejemplo: Día 1 = 4 AI Overviews, Día 2 = 4 AI Overviews → Total = 8
        cur.execute("""
            SELECT SUM(daily_ai_overviews) as total_ai_overviews
            FROM (
                SELECT COUNT(*) as daily_ai_overviews
                FROM manual_ai_results r
                WHERE r.project_id = %s 
                AND r.analysis_date >= %s 
                AND r.analysis_date <= %s
                AND r.has_ai_overview = true
                GROUP BY r.analysis_date
            ) daily_counts
        """, (project_id, start_date, end_date))
        
        total_ai_overviews_result = cur.fetchone()
        total_ai_overviews = total_ai_overviews_result['total_ai_overviews'] if total_ai_overviews_result else 0
        
        if total_ai_overviews == 0:
            logger.warning(f"No AI Overview results found for project {project_id} in date range")
            return []
        
        # Obtener datos agregados por dominio 
        cur.execute("""
            WITH domain_daily_stats AS (
                -- Estadísticas diarias por dominio SOLO desde manual_ai_global_domains
                -- (excluyendo el dominio del proyecto para evitar duplicación)
                SELECT 
                    gd.detected_domain,
                    gd.analysis_date,
                    COUNT(*) as daily_appearances,
                    AVG(gd.domain_position) as avg_daily_position,
                    MAX(CASE WHEN gd.is_project_domain THEN 1 ELSE 0 END) as is_project_domain,
                    MAX(CASE WHEN gd.is_selected_competitor THEN 1 ELSE 0 END) as is_selected_competitor
                FROM manual_ai_global_domains gd
                WHERE gd.project_id = %s
                AND gd.analysis_date >= %s 
                AND gd.analysis_date <= %s
                AND gd.detected_domain != %s  -- Excluir dominio del proyecto para evitar duplicación
                GROUP BY gd.detected_domain, gd.analysis_date
                
                UNION ALL
                
                -- Estadísticas del dominio del proyecto SOLO desde manual_ai_results
                SELECT 
                    %s as detected_domain,
                    r.analysis_date,
                    COUNT(DISTINCT r.keyword_id) as daily_appearances,
                    AVG(r.domain_position) as avg_daily_position,
                    1 as is_project_domain,
                    0 as is_selected_competitor
                FROM manual_ai_results r
                WHERE r.project_id = %s
                AND r.analysis_date >= %s 
                AND r.analysis_date <= %s
                AND r.domain_mentioned = true
                GROUP BY r.analysis_date
            )
            SELECT 
                detected_domain,
                SUM(daily_appearances) as appearances,
                ROUND((SUM(daily_appearances * avg_daily_position) / NULLIF(SUM(daily_appearances), 0))::numeric, 1) as avg_position,
                ROUND((SUM(daily_appearances)::float / %s::float * 100)::numeric, 1) as visibility_percentage,
                COUNT(DISTINCT analysis_date) as days_present,
                MIN(analysis_date) as first_seen,
                MAX(analysis_date) as last_seen,
                MAX(is_project_domain)::boolean as is_project_domain,
                MAX(is_selected_competitor)::boolean as is_selected_competitor
            FROM domain_daily_stats
            GROUP BY detected_domain
            HAVING SUM(daily_appearances) > 0
            ORDER BY 
                SUM(daily_appearances) DESC,
                ROUND((SUM(daily_appearances * avg_daily_position) / NULLIF(SUM(daily_appearances), 0))::numeric, 1) ASC,
                detected_domain ASC
            LIMIT 20
        """, (
            project_id, start_date, end_date, project_domain,  # manual_ai_global_domains (excluyendo project_domain)
            project_domain, project_id, start_date, end_date,  # manual_ai_results para project domain
            total_ai_overviews  # para visibility_percentage
        ))
        
        results = cur.fetchall()
        
        # Formatear resultados
        ranking = []
        for i, row in enumerate(results):
            domain_data = dict(row)
            domain_data['rank'] = i + 1
            
            # Convertir decimales a float para JSON serialization
            if domain_data['avg_position'] is not None:
                domain_data['avg_position'] = float(domain_data['avg_position'])
            if domain_data['visibility_percentage'] is not None:
                domain_data['visibility_percentage'] = float(domain_data['visibility_percentage'])
            
            # Determinar tipo de dominio para resaltado
            if domain_data['is_project_domain']:
                domain_data['domain_type'] = 'project'
                domain_data['domain_label'] = f"{domain_data['detected_domain']} (Your Domain)"
            elif domain_data['is_selected_competitor']:
                domain_data['domain_type'] = 'competitor'
                domain_data['domain_label'] = f"{domain_data['detected_domain']} (Competitor)"
            else:
                domain_data['domain_type'] = 'other'
                domain_data['domain_label'] = domain_data['detected_domain']
            
            # Agregar datos para UI
            domain_data['logo_url'] = f"https://logo.clearbit.com/{domain_data['detected_domain']}"
            
            ranking.append(domain_data)
        
        logger.debug(f"✅ Generated global ranking with {len(ranking)} domains for project {project_id}")
        return ranking
        
    except Exception as e:
        logger.error(f"Error getting global domains ranking for project {project_id}: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def store_global_domains_detected(project_id: int, keyword_id: int, keyword: str, 
                                 project_domain: str, ai_analysis_data: Dict, 
                                 analysis_date: date, country_code: str, 
                                 selected_competitors: List[str]) -> None:
    """
    Almacenar TODOS los dominios detectados en AI Overview para detección global
    
    Esta función implementa el nuevo flujo solicitado:
    1. Detección global automática: guarda todos los dominios encontrados en AI Overview
    2. Marcado especial: identifica qué dominios son el del proyecto y cuáles son competidores seleccionados
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Limpiar datos existentes del día para evitar duplicados
        cur.execute("""
            DELETE FROM manual_ai_global_domains 
            WHERE project_id = %s AND keyword_id = %s AND analysis_date = %s
        """, (project_id, keyword_id, analysis_date))
        
        # Extraer todos los dominios de debug_info.references_found
        debug_info = ai_analysis_data.get('debug_info', {})
        references_found = debug_info.get('references_found', [])
        
        if not references_found:
            logger.debug(f"No references found in AI Overview for keyword '{keyword}' in project {project_id}")
            return
        
        # Normalizar dominio del proyecto y competidores para comparación
        normalized_project_domain = normalize_search_console_url(project_domain) or project_domain.lower()
        normalized_competitors = [
            normalize_search_console_url(comp) or comp.lower() 
            for comp in (selected_competitors or [])
        ]
        
        domains_stored = 0
        
        for ref in references_found:
            ref_link = ref.get('link', '')
            ref_index = ref.get('index', 0)
            ref_title = ref.get('title', '')
            ref_source = ref.get('source', '')
            
            if not ref_link:
                continue
            
            # Extraer dominio de la URL
            detected_domain = extract_domain_from_url(ref_link)
            if not detected_domain:
                continue
            
            # Determinar flags
            is_project_domain = (detected_domain == normalized_project_domain)
            is_selected_competitor = (detected_domain in normalized_competitors)
            
            # Posición en AI Overview (index + 1 porque SERPAPI usa índice 0-based)
            domain_position = ref_index + 1 if ref_index is not None else 1
            
            try:
                # Insertar dominio detectado
                cur.execute("""
                    INSERT INTO manual_ai_global_domains (
                        project_id, keyword_id, analysis_date, keyword, project_domain,
                        detected_domain, domain_position, domain_title, domain_source_url,
                        country_code, is_project_domain, is_selected_competitor
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (project_id, keyword_id, analysis_date, detected_domain) 
                    DO UPDATE SET
                        domain_position = EXCLUDED.domain_position,
                        domain_title = EXCLUDED.domain_title,
                        domain_source_url = EXCLUDED.domain_source_url,
                        is_project_domain = EXCLUDED.is_project_domain,
                        is_selected_competitor = EXCLUDED.is_selected_competitor
                """, (
                    project_id, keyword_id, analysis_date, keyword, project_domain,
                    detected_domain, domain_position, ref_title, ref_link,
                    country_code, is_project_domain, is_selected_competitor
                ))
                
                domains_stored += 1
                
            except Exception as insert_error:
                logger.warning(f"Error storing domain '{detected_domain}' for keyword '{keyword}': {insert_error}")
                continue
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.debug(f"✅ Stored {domains_stored} global domains for keyword '{keyword}' in project {project_id}")
        
    except Exception as e:
        logger.error(f"❌ Error storing global domains for keyword '{keyword}' in project {project_id}: {e}")
        # No re-raise para no afectar el análisis principal

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

def sync_historical_competitor_flags(project_id: int, current_competitors: List[str]) -> None:
    """
    Sincronizar flags de competidores en datos históricos para mantener consistencia.
    
    Esta función actualiza el campo is_selected_competitor en la tabla manual_ai_global_domains
    basándose en la lista actual de competidores del proyecto, asegurando que:
    
    1. Los dominios que YA NO son competidores se marquen como False
    2. Los dominios que AHORA son competidores se marquen como True
    3. Se mantenga sincronización total entre configuración actual y datos históricos
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Normalizar competidores actuales para comparación
        normalized_current = [
            normalize_search_console_url(comp) or comp.lower() 
            for comp in (current_competitors or [])
        ]
        
        logger.info(f"🔄 Syncing historical competitor flags for project {project_id}")
        logger.info(f"📋 Current competitors: {normalized_current}")
        
        # 1. Marcar como FALSE todos los dominios que YA NO son competidores
        cur.execute("""
            UPDATE manual_ai_global_domains 
            SET is_selected_competitor = FALSE
            WHERE project_id = %s 
            AND is_selected_competitor = TRUE
            AND detected_domain NOT IN %s
        """, (project_id, tuple(normalized_current) if normalized_current else ('',)))
        
        removed_count = cur.rowcount
        
        # 2. Marcar como TRUE todos los dominios que AHORA son competidores
        if normalized_current:
            cur.execute("""
                UPDATE manual_ai_global_domains 
                SET is_selected_competitor = TRUE
                WHERE project_id = %s 
                AND is_selected_competitor = FALSE
                AND detected_domain IN %s
                AND is_project_domain = FALSE
            """, (project_id, tuple(normalized_current)))
            
            added_count = cur.rowcount
        else:
            added_count = 0
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"✅ Historical sync completed for project {project_id}: {removed_count} removed, {added_count} added")
        
    except Exception as e:
        logger.error(f"Error syncing historical competitor flags for project {project_id}: {e}")
        try:
            if 'cur' in locals():
                cur.close()
            if 'conn' in locals():
                conn.close()
        except:
            pass

# Registrar rutas de error handling
@manual_ai_bp.errorhandler(404)
def handle_404(e):
    return jsonify({'success': False, 'error': 'Endpoint not found'}), 404

@manual_ai_bp.errorhandler(500)
def handle_500(e):
    return jsonify({'success': False, 'error': 'Internal server error'}), 500

# Manual AI System ready for registration