"""
Repositorio para operaciones de base de datos relacionadas con proyectos AI Mode
"""

import logging
import json
from typing import List, Dict, Optional
from database import get_db_connection
from services.utils import normalize_search_console_url

logger = logging.getLogger(__name__)


class ProjectRepository:
    """Repositorio para gestión de proyectos en base de datos"""
    
    @staticmethod
    def get_user_projects(user_id: int) -> List[Dict]:
        """
        Obtener todos los proyectos AI Mode de un usuario con estadísticas basadas en último análisis
        
        Args:
            user_id: ID del usuario
            
        Returns:
            Lista de proyectos con sus estadísticas
        """
        logger.info(f"🔍 [AI MODE REPOSITORY] Buscando proyectos para user_id: {user_id}")
        conn = get_db_connection()
        if not conn:
            logger.error("❌ [AI MODE REPOSITORY] Failed to get database connection for user projects")
            return []
            
        cur = conn.cursor()
        
        try:
            # Query adaptada para AI Mode: brand_name en lugar de domain
            cur.execute("""
                SELECT 
                    p.id,
                    p.name,
                    p.description,
                    p.brand_name,
                    p.country_code,
                    p.created_at,
                    p.updated_at,
                    p.selected_competitors,
                    p.topic_clusters_config,
                    COALESCE(project_stats.total_keywords, 0) as total_keywords,
                    COALESCE(project_stats.total_mentions, 0) as total_mentions,
                    COALESCE(project_stats.visibility_percentage, 0) as visibility_percentage,
                    project_stats.avg_position,
                    project_stats.last_analysis_date
                FROM ai_mode_projects p
                LEFT JOIN LATERAL (
                    WITH latest_results AS (
                        SELECT DISTINCT ON (k.id) 
                            k.id as keyword_id,
                            k.is_active,
                            r.brand_mentioned,
                            r.mention_position,
                            r.analysis_date
                        FROM ai_mode_keywords k
                        LEFT JOIN ai_mode_results r ON k.id = r.keyword_id 
                        WHERE k.project_id = p.id
                        ORDER BY k.id, r.analysis_date DESC
                    )
                    SELECT 
                        COUNT(*) as total_keywords,
                        COUNT(CASE WHEN is_active = true THEN 1 END) as active_keywords,
                        COUNT(CASE WHEN brand_mentioned = true THEN 1 END) as total_mentions,
                        AVG(CASE WHEN mention_position IS NOT NULL THEN mention_position END) as avg_position,
                        (COUNT(CASE WHEN brand_mentioned = true THEN 1 END)::float / 
                         NULLIF(COUNT(CASE WHEN analysis_date IS NOT NULL THEN 1 END), 0)::float * 100) as visibility_percentage,
                        MAX(analysis_date) as last_analysis_date
                    FROM latest_results
                ) project_stats ON true
                WHERE p.user_id = %s AND p.is_active = true
                ORDER BY p.created_at DESC
            """, (user_id,))
            
            projects = cur.fetchall()
            logger.info(f"✅ [AI MODE REPOSITORY] Query ejecutado. Proyectos encontrados: {len(projects)}")
            
            if len(projects) == 0:
                logger.warning(f"⚠️ [AI MODE REPOSITORY] ¡NO se encontraron proyectos para user_id {user_id}!")
                # Hacer una consulta simple para debug
                cur.execute("SELECT id, name, user_id, is_active FROM ai_mode_projects WHERE user_id = %s", (user_id,))
                debug_projects = cur.fetchall()
                logger.warning(f"🔍 [DEBUG] Consulta simple encontró: {len(debug_projects)} proyectos")
                for p in debug_projects:
                    logger.warning(f"  - ID: {p[0]}, Name: {p[1]}, UserID: {p[2]}, Active: {p[3]}")
            
            return [dict(project) for project in projects]
            
        except Exception as e:
            logger.error(f"❌ [AI MODE REPOSITORY] Error fetching user projects for user {user_id}: {e}")
            import traceback
            logger.error(f"🔍 [AI MODE REPOSITORY] Traceback: {traceback.format_exc()}")
            return []
        finally:
            cur.close()
            conn.close()
    
    @staticmethod
    def create_project(user_id: int, name: str, description: str, brand_name: str, 
                      country_code: str) -> int:
        """
        Crear un nuevo proyecto AI Mode
        
        Args:
            user_id: ID del usuario propietario
            name: Nombre del proyecto
            description: Descripción del proyecto
            brand_name: Nombre de la marca a monitorizar
            country_code: Código de país
            
        Returns:
            ID del proyecto creado
        """
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Limpiar y validar brand_name
        brand_name = brand_name.strip()
        
        cur.execute("""
            INSERT INTO ai_mode_projects (user_id, name, description, brand_name, country_code)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (user_id, name, description, brand_name, country_code))
        
        project_id = cur.fetchone()['id']
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"Created new AI Mode project {project_id} for user {user_id} with brand: {brand_name}")
        return project_id
    
    @staticmethod
    def user_owns_project(user_id: int, project_id: int) -> bool:
        """
        Verificar si un usuario es propietario de un proyecto AI Mode
        
        Args:
            user_id: ID del usuario
            project_id: ID del proyecto
            
        Returns:
            True si el usuario es propietario, False en caso contrario
        """
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 1 FROM ai_mode_projects 
            WHERE id = %s AND user_id = %s AND is_active = true
        """, (project_id, user_id))
        
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        return result is not None
    
    @staticmethod
    def get_project_with_details(project_id: int) -> Optional[Dict]:
        """
        Obtener proyecto AI Mode con todos sus detalles
        
        Args:
            project_id: ID del proyecto
            
        Returns:
            Dict con información del proyecto o None si no existe
        """
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                p.*,
                COUNT(DISTINCT k.id) as keyword_count,
                COUNT(DISTINCT CASE WHEN k.is_active = true THEN k.id END) as active_keyword_count
            FROM ai_mode_projects p
            LEFT JOIN ai_mode_keywords k ON p.id = k.project_id
            WHERE p.id = %s
            GROUP BY p.id
        """, (project_id,))
        
        project = cur.fetchone()
        cur.close()
        conn.close()
        
        return dict(project) if project else None
    
    @staticmethod
    def get_project_info(project_id: int) -> Optional[Dict]:
        """
        Obtener información básica de un proyecto AI Mode
        
        Args:
            project_id: ID del proyecto
            
        Returns:
            Dict con información básica del proyecto o None
        """
        conn = get_db_connection()
        if not conn:
            logger.error(f"Failed to get database connection for project {project_id}")
            return None
            
        cur = conn.cursor()
        
        try:
            cur.execute("""
                SELECT id, name, description, brand_name, country_code, selected_competitors, created_at, updated_at
                FROM ai_mode_projects
                WHERE id = %s AND is_active = true
            """, (project_id,))
            
            project = cur.fetchone()
            return dict(project) if project else None
            
        except Exception as e:
            logger.error(f"Error fetching project info for project {project_id}: {e}")
            return None
        finally:
            cur.close()
            conn.close()
    
    @staticmethod
    def update_project(project_id: int, user_id: int, name: str, description: str) -> bool:
        """
        Actualizar nombre y descripción de un proyecto AI Mode
        
        Args:
            project_id: ID del proyecto
            user_id: ID del usuario (para verificación)
            name: Nuevo nombre
            description: Nueva descripción
            
        Returns:
            True si se actualizó correctamente, False en caso contrario
        """
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # Verificar que el nombre no esté siendo usado por otro proyecto del usuario
            cur.execute("""
                SELECT id FROM ai_mode_projects 
                WHERE user_id = %s AND name = %s AND id != %s
            """, (user_id, name, project_id))
            
            if cur.fetchone():
                logger.warning(f"AI Mode project name '{name}' already exists for user {user_id}")
                return False
            
            # Actualizar proyecto
            cur.execute("""
                UPDATE ai_mode_projects 
                SET name = %s, description = %s, updated_at = NOW()
                WHERE id = %s AND user_id = %s
            """, (name, description, project_id, user_id))
            
            success = cur.rowcount > 0
            conn.commit()
            
            if success:
                logger.info(f"AI Mode project {project_id} updated successfully")
            
            return success
            
        except Exception as e:
            logger.error(f"Error updating AI Mode project {project_id}: {e}")
            return False
        finally:
            cur.close()
            conn.close()
    
    @staticmethod
    def delete_project(project_id: int, user_id: int) -> Dict:
        """
        Eliminar completamente un proyecto AI Mode y todos sus datos
        
        Args:
            project_id: ID del proyecto
            user_id: ID del usuario (para verificación)
            
        Returns:
            Dict con estadísticas de eliminación
        """
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # Obtener nombre del proyecto antes de eliminarlo
            cur.execute("SELECT name FROM ai_mode_projects WHERE id = %s", (project_id,))
            project_data = cur.fetchone()
            
            if not project_data:
                return {'success': False, 'error': 'Project not found'}
            
            project_name = project_data['name'] if isinstance(project_data, dict) else project_data[0]
            
            # Eliminar en orden inverso de dependencias
            # 1. Eventos
            try:
                cur.execute("DELETE FROM ai_mode_events WHERE project_id = %s", (project_id,))
                events_deleted = cur.rowcount
            except Exception as e:
                logger.warning(f"No events deleted for AI Mode project {project_id}: {e}")
                events_deleted = 0
            
            # 2. Snapshots
            try:
                cur.execute("DELETE FROM ai_mode_snapshots WHERE project_id = %s", (project_id,))
                snapshots_deleted = cur.rowcount
            except Exception as e:
                logger.warning(f"No snapshots deleted for AI Mode project {project_id}: {e}")
                snapshots_deleted = 0
            
            # 3. Resultados
            cur.execute("DELETE FROM ai_mode_results WHERE project_id = %s", (project_id,))
            results_deleted = cur.rowcount
            
            # 4. Keywords
            cur.execute("DELETE FROM ai_mode_keywords WHERE project_id = %s", (project_id,))
            keywords_deleted = cur.rowcount
            
            # 5. Proyecto
            cur.execute("DELETE FROM ai_mode_projects WHERE id = %s AND user_id = %s", 
                       (project_id, user_id))
            
            if cur.rowcount == 0:
                return {'success': False, 'error': 'Project not found or unauthorized'}
            
            conn.commit()
            
            logger.info(f"Project '{project_name}' (ID: {project_id}) deleted successfully. "
                       f"Removed: {keywords_deleted} keywords, {results_deleted} results, "
                       f"{snapshots_deleted} snapshots, {events_deleted} events")
            
            return {
                'success': True,
                'project_name': project_name,
                'stats': {
                    'keywords_deleted': keywords_deleted,
                    'results_deleted': results_deleted,
                    'snapshots_deleted': snapshots_deleted,
                    'events_deleted': events_deleted
                }
            }
            
        except Exception as e:
            logger.error(f"Error deleting project {project_id}: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            cur.close()
            conn.close()
    
    @staticmethod
    def get_project_competitors(project_id: int) -> List[str]:
        """
        Obtener lista de competidores (media sources) de un proyecto AI Mode
        
        Args:
            project_id: ID del proyecto
            
        Returns:
            Lista de dominios competidores
        """
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                SELECT selected_competitors
                FROM ai_mode_projects
                WHERE id = %s
            """, (project_id,))
            
            result = cur.fetchone()
            
            if result and result['selected_competitors']:
                return result['selected_competitors']
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting competitors for AI Mode project {project_id}: {e}")
            return []
        finally:
            cur.close()
            conn.close()
    
    @staticmethod
    def update_project_competitors(project_id: int, competitors: List[str]) -> bool:
        """
        Actualizar competidores (media sources) de un proyecto AI Mode
        
        Args:
            project_id: ID del proyecto
            competitors: Lista de dominios competidores
            
        Returns:
            True si se actualizó correctamente, False en caso contrario
        """
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # Convertir a JSON para PostgreSQL
            competitors_json = json.dumps(competitors) if competitors else '[]'
            
            cur.execute("""
                UPDATE ai_mode_projects
                SET selected_competitors = %s::jsonb, updated_at = NOW()
                WHERE id = %s
            """, (competitors_json, project_id))
            
            success = cur.rowcount > 0
            conn.commit()
            
            if success:
                logger.info(f"AI Mode project {project_id} competitors updated: {len(competitors)} sources")
            
            return success
            
        except Exception as e:
            logger.error(f"Error updating competitors for AI Mode project {project_id}: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()

