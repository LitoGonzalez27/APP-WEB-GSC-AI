"""
Repositorio para operaciones de base de datos relacionadas con proyectos
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
        Obtener todos los proyectos de un usuario con estadísticas basadas en último análisis
        
        Args:
            user_id: ID del usuario
            
        Returns:
            Lista de proyectos con sus estadísticas
        """
        conn = get_db_connection()
        if not conn:
            logger.error("Failed to get database connection for user projects")
            return []
            
        cur = conn.cursor()
        
        try:
            # Usar la misma lógica que get_project_statistics (último análisis por keyword)
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
                    COALESCE(project_stats.total_keywords, 0) as total_keywords,
                    COALESCE(project_stats.total_ai_keywords, 0) as total_ai_keywords,
                    COALESCE(project_stats.total_mentions, 0) as total_mentions,
                    COALESCE(project_stats.visibility_percentage, 0) as visibility_percentage,
                    project_stats.avg_position,
                    COALESCE(project_stats.aio_weight_percentage, 0) as aio_weight_percentage,
                    project_stats.last_analysis_date
                FROM manual_ai_projects p
                LEFT JOIN LATERAL (
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
                        WHERE k.project_id = p.id
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
                         NULLIF(COUNT(CASE WHEN analysis_date IS NOT NULL THEN 1 END), 0)::float * 100) as aio_weight_percentage,
                        MAX(analysis_date) as last_analysis_date
                    FROM latest_results
                ) project_stats ON true
                WHERE p.user_id = %s AND p.is_active = true
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
    
    @staticmethod
    def create_project(user_id: int, name: str, description: str, domain: str, 
                      country_code: str, competitors: List[str] = None) -> int:
        """
        Crear un nuevo proyecto
        
        Args:
            user_id: ID del usuario propietario
            name: Nombre del proyecto
            description: Descripción del proyecto
            domain: Dominio del proyecto
            country_code: Código de país
            competitors: Lista de competidores
            
        Returns:
            ID del proyecto creado
        """
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
    
    @staticmethod
    def user_owns_project(user_id: int, project_id: int) -> bool:
        """
        Verificar si un usuario es propietario de un proyecto
        
        Args:
            user_id: ID del usuario
            project_id: ID del proyecto
            
        Returns:
            True si el usuario es propietario, False en caso contrario
        """
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
    
    @staticmethod
    def get_project_with_details(project_id: int) -> Optional[Dict]:
        """
        Obtener proyecto con todos sus detalles
        
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
            FROM manual_ai_projects p
            LEFT JOIN manual_ai_keywords k ON p.id = k.project_id
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
        Obtener información básica de un proyecto
        
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
                SELECT id, name, description, domain, country_code, created_at, updated_at, selected_competitors
                FROM manual_ai_projects
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
        Actualizar nombre y descripción de un proyecto
        
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
                SELECT id FROM manual_ai_projects 
                WHERE user_id = %s AND name = %s AND id != %s
            """, (user_id, name, project_id))
            
            if cur.fetchone():
                logger.warning(f"Project name '{name}' already exists for user {user_id}")
                return False
            
            # Actualizar proyecto
            cur.execute("""
                UPDATE manual_ai_projects 
                SET name = %s, description = %s, updated_at = NOW()
                WHERE id = %s AND user_id = %s
            """, (name, description, project_id, user_id))
            
            success = cur.rowcount > 0
            conn.commit()
            
            if success:
                logger.info(f"Project {project_id} updated successfully")
            
            return success
            
        except Exception as e:
            logger.error(f"Error updating project {project_id}: {e}")
            return False
        finally:
            cur.close()
            conn.close()
    
    @staticmethod
    def delete_project(project_id: int, user_id: int) -> Dict:
        """
        Eliminar completamente un proyecto y todos sus datos
        
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
            cur.execute("SELECT name FROM manual_ai_projects WHERE id = %s", (project_id,))
            project_data = cur.fetchone()
            
            if not project_data:
                return {'success': False, 'error': 'Project not found'}
            
            project_name = project_data['name'] if isinstance(project_data, dict) else project_data[0]
            
            # Eliminar en orden inverso de dependencias
            # 1. Eventos
            try:
                cur.execute("DELETE FROM manual_ai_events WHERE project_id = %s", (project_id,))
                events_deleted = cur.rowcount
            except Exception as e:
                logger.warning(f"No events deleted for project {project_id}: {e}")
                events_deleted = 0
            
            # 2. Snapshots
            try:
                cur.execute("DELETE FROM manual_ai_snapshots WHERE project_id = %s", (project_id,))
                snapshots_deleted = cur.rowcount
            except Exception as e:
                logger.warning(f"No snapshots deleted for project {project_id}: {e}")
                snapshots_deleted = 0
            
            # 3. Resultados
            cur.execute("DELETE FROM manual_ai_results WHERE project_id = %s", (project_id,))
            results_deleted = cur.rowcount
            
            # 4. Keywords
            cur.execute("DELETE FROM manual_ai_keywords WHERE project_id = %s", (project_id,))
            keywords_deleted = cur.rowcount
            
            # 5. Proyecto
            cur.execute("DELETE FROM manual_ai_projects WHERE id = %s AND user_id = %s", 
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
        Obtener competidores seleccionados de un proyecto
        
        Args:
            project_id: ID del proyecto
            
        Returns:
            Lista de competidores
        """
        conn = get_db_connection()
        if not conn:
            logger.error(f"Failed to get database connection for project {project_id} competitors")
            return []
            
        cur = conn.cursor()
        
        try:
            cur.execute("""
                SELECT selected_competitors
                FROM manual_ai_projects 
                WHERE id = %s AND is_active = true
            """, (project_id,))
            
            result = cur.fetchone()
            
            if not result:
                logger.warning(f"Project {project_id} not found or inactive")
                return []
            
            competitors = result['selected_competitors'] if result['selected_competitors'] else []
            
            # Validar que competitors sea una lista
            if not isinstance(competitors, list):
                logger.warning(f"Invalid competitors data type for project {project_id}: {type(competitors)}")
                return []
            
            return competitors
            
        except Exception as e:
            logger.error(f"Error getting competitors for project {project_id}: {e}")
            return []
        finally:
            cur.close()
            conn.close()
    
    @staticmethod
    def update_project_competitors(project_id: int, competitors: List[str]) -> bool:
        """
        Actualizar competidores de un proyecto
        
        Args:
            project_id: ID del proyecto
            competitors: Lista de competidores (ya validados y normalizados)
            
        Returns:
            True si se actualizó correctamente
        """
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                UPDATE manual_ai_projects 
                SET selected_competitors = %s, updated_at = NOW()
                WHERE id = %s
            """, (json.dumps(competitors), project_id))
            
            success = cur.rowcount > 0
            conn.commit()
            
            return success
            
        except Exception as e:
            logger.error(f"Error updating competitors for project {project_id}: {e}")
            return False
        finally:
            cur.close()
            conn.close()

