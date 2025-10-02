"""
Repositorio para operaciones de base de datos relacionadas con keywords
"""

import logging
from typing import List, Dict
from database import get_db_connection

logger = logging.getLogger(__name__)


class KeywordRepository:
    """Repositorio para gestión de keywords en base de datos"""
    
    @staticmethod
    def get_keywords_for_project(project_id: int) -> List[Dict]:
        """
        Obtener todas las keywords activas de un proyecto
        
        Args:
            project_id: ID del proyecto
            
        Returns:
            Lista de keywords con estadísticas
        """
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                SELECT 
                    k.*,
                    COUNT(r.id) as analysis_count,
                    MAX(r.analysis_date) as last_analysis_date,
                    AVG(CASE WHEN r.has_ai_overview THEN 1.0 ELSE 0.0 END) as ai_overview_frequency
                FROM manual_ai_keywords k
                LEFT JOIN manual_ai_results r ON k.id = r.keyword_id
                WHERE k.project_id = %s AND k.is_active = true
                GROUP BY k.id, k.keyword, k.is_active, k.added_at
                ORDER BY k.added_at DESC
            """, (project_id,))
            
            keywords = cur.fetchall()
            return [dict(keyword) for keyword in keywords]
            
        except Exception as e:
            logger.error(f"Error fetching keywords for project {project_id}: {e}")
            return []
        finally:
            cur.close()
            conn.close()
    
    @staticmethod
    def get_project_keyword_count(project_id: int) -> int:
        """
        Obtener el conteo actual de keywords activas de un proyecto
        
        Args:
            project_id: ID del proyecto
            
        Returns:
            Número de keywords activas
        """
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                SELECT COUNT(*) as count
                FROM manual_ai_keywords
                WHERE project_id = %s AND is_active = true
            """, (project_id,))
            
            result = cur.fetchone()
            return result['count'] if result else 0
            
        except Exception as e:
            logger.error(f"Error counting keywords for project {project_id}: {e}")
            return 0
        finally:
            cur.close()
            conn.close()
    
    @staticmethod
    def add_keywords_to_project(project_id: int, keywords_list: List[str]) -> int:
        """
        Agregar keywords a un proyecto (evitando duplicados)
        
        Args:
            project_id: ID del proyecto
            keywords_list: Lista de keywords a agregar
            
        Returns:
            Número de keywords agregadas exitosamente
        """
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
        
        logger.info(f"Added {added_count} keywords to project {project_id}")
        return added_count
    
    @staticmethod
    def delete_keyword(project_id: int, keyword_id: int) -> Dict:
        """
        Eliminar una keyword (soft delete) y sus resultados
        
        Args:
            project_id: ID del proyecto
            keyword_id: ID de la keyword
            
        Returns:
            Dict con información del keyword eliminada
        """
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # Buscar la keyword
            cur.execute("""
                SELECT id, keyword FROM manual_ai_keywords 
                WHERE id = %s AND project_id = %s AND is_active = true
            """, (keyword_id, project_id))
            
            keyword_data = cur.fetchone()
            if not keyword_data:
                return {'success': False, 'error': 'Keyword not found'}
            
            # Marcar como inactiva (soft delete)
            cur.execute("""
                UPDATE manual_ai_keywords 
                SET is_active = false
                WHERE id = %s AND project_id = %s
            """, (keyword_id, project_id))
            
            # Eliminar resultados asociados
            cur.execute("""
                DELETE FROM manual_ai_results 
                WHERE keyword_id = %s AND project_id = %s
            """, (keyword_id, project_id))
            
            conn.commit()
            
            return {
                'success': True,
                'keyword': keyword_data['keyword']
            }
            
        except Exception as e:
            logger.error(f"Error deleting keyword {keyword_id}: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            cur.close()
            conn.close()
    
    @staticmethod
    def update_keyword(project_id: int, keyword_id: int, new_keyword: str) -> bool:
        """
        Actualizar el texto de una keyword
        
        Args:
            project_id: ID del proyecto
            keyword_id: ID de la keyword
            new_keyword: Nuevo texto de la keyword
            
        Returns:
            True si se actualizó correctamente
        """
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # Verificar que la keyword existe
            cur.execute("""
                SELECT keyword FROM manual_ai_keywords 
                WHERE id = %s AND project_id = %s AND is_active = true
            """, (keyword_id, project_id))
            
            if not cur.fetchone():
                logger.warning(f"Keyword {keyword_id} not found in project {project_id}")
                return False
            
            # Verificar que no existe otra keyword con el mismo texto
            cur.execute("""
                SELECT id FROM manual_ai_keywords 
                WHERE project_id = %s AND keyword = %s AND is_active = true AND id != %s
            """, (project_id, new_keyword, keyword_id))
            
            if cur.fetchone():
                logger.warning(f"Keyword '{new_keyword}' already exists in project {project_id}")
                return False
            
            # Actualizar la keyword
            cur.execute("""
                UPDATE manual_ai_keywords 
                SET keyword = %s
                WHERE id = %s AND project_id = %s
            """, (new_keyword, keyword_id, project_id))
            
            conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error updating keyword {keyword_id}: {e}")
            return False
        finally:
            cur.close()
            conn.close()

