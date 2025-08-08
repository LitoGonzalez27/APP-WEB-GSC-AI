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
    
    if not user_owns_project(user['id'], project_id):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Obtener nombre del proyecto antes de eliminarlo
        cur.execute("SELECT name FROM manual_ai_projects WHERE id = %s", (project_id,))
        project_data = cur.fetchone()
        if not project_data:
            return jsonify({'success': False, 'error': 'Project not found'}), 404
            
        project_name = project_data[0]
        
        # Eliminar en orden inverso de dependencias
        # 1. Eliminar eventos
        cur.execute("DELETE FROM manual_ai_events WHERE project_id = %s", (project_id,))
        events_deleted = cur.rowcount
        
        # 2. Eliminar snapshots
        cur.execute("DELETE FROM manual_ai_snapshots WHERE project_id = %s", (project_id,))
        snapshots_deleted = cur.rowcount
        
        # 3. Eliminar resultados de análisis
        cur.execute("""
            DELETE FROM manual_ai_results 
            WHERE keyword_id IN (
                SELECT id FROM manual_ai_keywords WHERE project_id = %s
            )
        """, (project_id,))
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
        
    except Exception as e:
        logger.error(f"Error analyzing project {project_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

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
    """Obtener dominios más visibles para un proyecto"""
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
                    # 2. Obtener SERP usando función existente (igual que sistema automático)
                    api_key = os.getenv('SERPAPI_KEY')
                    if not api_key:
                        logger.error(f"❌ SERPAPI_KEY not configured for keyword '{keyword}' in project {project_id}")
                        logger.error(f"❌ Available env vars: {', '.join([k for k in os.environ.keys() if 'API' in k or 'KEY' in k])}")
                        failed_keywords += 1
                        continue
                    
                    # 3. Construir parámetros SERP para sistema manual (sin detección dinámica)
                    # En sistema manual: país fijo del proyecto, sin GSC data
                    from services.country_config import get_country_config
                    
                    serp_params = {
                        'engine': 'google',
                        'q': keyword,
                        'api_key': api_key,
                        'num': 20
                    }
                    
                    # Aplicar configuración del país seleccionado en el proyecto
                    country_config = get_country_config(internal_country)
                    if country_config:
                        serp_params.update({
                            'location': country_config['serp_location'],
                            'gl': country_config['serp_gl'],
                            'hl': country_config['serp_hl'],
                            'google_domain': country_config['google_domain']
                        })
                        logger.debug(f"Using {country_config['name']} config for '{keyword}'")
                    
                    serp_data = get_serp_json(serp_params)
                    
                    if not serp_data or serp_data.get('error'):
                        logger.warning(f"No SERP data for keyword '{keyword}': {serp_data.get('error', 'Unknown error')}")
                        failed_keywords += 1
                        continue
                    
                    # 4. Analizar AI Overview usando servicio existente
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
    logger.info("🕒 === INICIANDO ANÁLISIS DIARIO AUTOMÁTICO ===")

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
        lock_cur.execute("SELECT pg_try_advisory_lock(%s, %s)", (lock_class_id, lock_object_id))
        lock_acquired = bool(lock_cur.fetchone()[0])

        if not lock_acquired:
            logger.info("🔒 Otro análisis diario ya está en ejecución. Saliendo sin hacer nada")
            lock_cur.close(); lock_conn.close()
            return {"success": True, "message": "Another daily run in progress (skipped)", "skipped": 0, "failed": 0, "successful": 0, "total_projects": 0}
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
            LEFT JOIN manual_ai_keywords k ON p.id = k.project_id
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
        
        logger.info(f"📊 Found {len(projects)} active projects for daily analysis")
        
        successful_analyses = 0
        failed_analyses = 0
        skipped_analyses = 0
        
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
                    logger.info(f"⏭️ Project {project_dict['id']} ({project_dict['name']}) already analyzed today, skipping")
                    skipped_analyses += 1
                    continue
                
                logger.info(f"🚀 Starting daily analysis for project {project_dict['id']} ({project_dict['name']}) - {project_dict['keyword_count']} keywords")
                
                # Ejecutar análisis automático (sin sobreescritura)
                results = run_project_analysis(project_dict['id'], force_overwrite=False)
                
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
        
        return {
            "success": True,
            "message": "Daily analysis completed",
            "total_projects": total_projects,
            "successful": successful_analyses,
            "failed": failed_analyses,
            "skipped": skipped_analyses
        }
        
    except Exception as e:
        logger.error(f"❌ Critical error in daily analysis: {e}")
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
                    run_daily_analysis_for_all_projects()
                    logger.info("✅ Async daily analysis finished")
                except Exception as e:
                    logger.error(f"❌ Error in async daily analysis: {e}")

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
    
    # Estadísticas principales
    cur.execute("""
        SELECT 
            COUNT(DISTINCT k.id) as total_keywords,
            COUNT(DISTINCT CASE WHEN k.is_active = true THEN k.id END) as active_keywords,
            COUNT(DISTINCT CASE WHEN r.has_ai_overview = true THEN r.id END) as total_ai_keywords,
            COUNT(DISTINCT CASE WHEN r.domain_mentioned = true THEN r.id END) as total_mentions,
            AVG(CASE WHEN r.domain_position IS NOT NULL THEN r.domain_position END) as avg_position,
            (COUNT(DISTINCT CASE WHEN r.domain_mentioned = true THEN r.id END)::float / 
             NULLIF(COUNT(DISTINCT CASE WHEN r.has_ai_overview = true THEN r.id END), 0)::float * 100) as visibility_percentage,
            (COUNT(DISTINCT CASE WHEN r.has_ai_overview = true THEN r.id END)::float / 
             NULLIF(COUNT(DISTINCT r.id), 0)::float * 100) as aio_weight_percentage
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
        
        # Obtener análisis de dominios en AI Overview (excluyendo el dominio del proyecto)
        cur.execute("""
            SELECT 
                LOWER(TRIM(BOTH '/' FROM 
                    CASE 
                        WHEN r.ai_overview_data->'sources' IS NOT NULL THEN
                            unnested_source->>'url'
                        ELSE NULL
                    END
                )) as clean_url,
                r.domain_position,
                r.analysis_date
            FROM manual_ai_results r
            JOIN manual_ai_keywords k ON r.keyword_id = k.id
            LEFT JOIN LATERAL jsonb_array_elements(r.ai_overview_data->'sources') AS unnested_source ON true
            WHERE k.project_id = %s 
                AND r.has_ai_overview = true
                AND r.ai_overview_data IS NOT NULL
                AND r.ai_overview_data->'sources' IS NOT NULL
                AND unnested_source->>'url' IS NOT NULL
                AND unnested_source->>'url' != ''
                AND r.analysis_date >= NOW() - INTERVAL '30 days'
        """, (project_id,))
        
        results = cur.fetchall()
        
        # Procesar URLs para extraer dominios
        domain_stats = {}
        
        for url, position, analysis_date in results:
            if not url:
                continue
                
            # Extraer dominio de la URL
            domain = extract_domain_from_url(url)
            
            # Filtrar el dominio del proyecto y dominios inválidos
            if not domain or domain == project_domain or domain in ['', 'localhost', 'example.com']:
                continue
            
            # Acumular estadísticas por dominio
            if domain not in domain_stats:
                domain_stats[domain] = {
                    'domain': domain,
                    'appearances': 0,
                    'positions': [],
                    'dates': set()
                }
            
            domain_stats[domain]['appearances'] += 1
            if position:
                domain_stats[domain]['positions'].append(position)
            domain_stats[domain]['dates'].add(str(analysis_date.date()) if analysis_date else None)
        
        # Calcular promedios y scores
        domain_list = []
        for domain, stats in domain_stats.items():
            avg_position = sum(stats['positions']) / len(stats['positions']) if stats['positions'] else None
            
            # Solo incluir dominios con datos válidos
            if stats['appearances'] > 0:
                domain_list.append({
                    'domain': domain,
                    'appearances': stats['appearances'],
                    'avg_position': round(avg_position, 1) if avg_position else None,
                    'unique_dates': len([d for d in stats['dates'] if d])
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

# Manual AI System ready for registration