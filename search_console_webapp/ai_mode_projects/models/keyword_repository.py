"""
Repositorio para operaciones de base de datos relacionadas con keywords AI Mode

Refactor 2026-05-25: every method now null-checks the connection and wraps
its body in try/finally, so a pool-exhausted state (get_db_connection()
returns None) no longer crashes mid-cursor and a query error no longer
leaks the pool slot.
"""

import logging
from typing import List, Dict
from database import get_db_connection

logger = logging.getLogger(__name__)


class KeywordRepository:
    """Repositorio para gestión de keywords AI Mode en base de datos"""

    @staticmethod
    def get_keywords_for_project(project_id: int) -> List[Dict]:
        """
        Obtener todas las keywords activas de un proyecto AI Mode
        """
        conn = get_db_connection()
        if not conn:
            logger.error(f"get_keywords_for_project[ai_mode]({project_id}): no DB connection")
            return []
        try:
            cur = conn.cursor()
            try:
                cur.execute("""
                    SELECT
                        k.*,
                        COUNT(r.id) as analysis_count,
                        MAX(r.analysis_date) as last_analysis_date,
                        AVG(CASE WHEN r.brand_mentioned THEN 1.0 ELSE 0.0 END) as brand_mention_frequency
                    FROM ai_mode_keywords k
                    LEFT JOIN ai_mode_results r ON k.id = r.keyword_id
                    WHERE k.project_id = %s AND k.is_active = true
                    GROUP BY k.id, k.keyword, k.is_active, k.added_at
                    ORDER BY k.added_at DESC
                """, (project_id,))

                keywords = cur.fetchall()
                return [dict(keyword) for keyword in keywords]

            except Exception as e:
                logger.error(f"Error fetching AI Mode keywords for project {project_id}: {e}")
                return []
        finally:
            try:
                conn.close()
            except Exception:
                pass

    @staticmethod
    def get_project_keyword_count(project_id: int) -> int:
        """
        Obtener el conteo actual de keywords activas de un proyecto AI Mode
        """
        conn = get_db_connection()
        if not conn:
            logger.error(f"get_project_keyword_count[ai_mode]({project_id}): no DB connection")
            return 0
        try:
            cur = conn.cursor()
            try:
                cur.execute("""
                    SELECT COUNT(*) as count
                    FROM ai_mode_keywords
                    WHERE project_id = %s AND is_active = true
                """, (project_id,))

                result = cur.fetchone()
                return result['count'] if result else 0

            except Exception as e:
                logger.error(f"Error counting AI Mode keywords for project {project_id}: {e}")
                return 0
        finally:
            try:
                conn.close()
            except Exception:
                pass

    @staticmethod
    def add_keywords_to_project(project_id: int, keywords_list: List[str]) -> int:
        """
        Agregar keywords a un proyecto AI Mode (evitando duplicados)
        """
        conn = get_db_connection()
        if not conn:
            logger.error(f"add_keywords_to_project[ai_mode]({project_id}): no DB connection")
            return 0
        try:
            cur = conn.cursor()
            added_count = 0

            for keyword in keywords_list:
                keyword = keyword.strip()
                if not keyword:
                    continue

                try:
                    cur.execute("""
                        INSERT INTO ai_mode_keywords (project_id, keyword)
                        VALUES (%s, %s)
                        ON CONFLICT (project_id, keyword) DO NOTHING
                    """, (project_id, keyword))

                    if cur.rowcount > 0:
                        added_count += 1

                except Exception as e:
                    logger.warning(f"Error adding AI Mode keyword '{keyword}': {e}")
                    continue

            conn.commit()

            logger.info(f"Added {added_count} AI Mode keywords to project {project_id}")
            return added_count
        finally:
            try:
                conn.close()
            except Exception:
                pass

    @staticmethod
    def delete_keyword(project_id: int, keyword_id: int) -> Dict:
        """
        Eliminar una keyword AI Mode (soft delete) y sus resultados
        """
        conn = get_db_connection()
        if not conn:
            logger.error(f"delete_keyword[ai_mode]({project_id},{keyword_id}): no DB connection")
            return {'success': False, 'error': 'Service temporarily unavailable'}
        try:
            cur = conn.cursor()
            try:
                # Buscar la keyword
                cur.execute("""
                    SELECT id, keyword FROM ai_mode_keywords
                    WHERE id = %s AND project_id = %s AND is_active = true
                """, (keyword_id, project_id))

                keyword_data = cur.fetchone()
                if not keyword_data:
                    return {'success': False, 'error': 'Keyword not found'}

                # Marcar como inactiva (soft delete)
                cur.execute("""
                    UPDATE ai_mode_keywords
                    SET is_active = false
                    WHERE id = %s AND project_id = %s
                """, (keyword_id, project_id))

                # Eliminar resultados asociados
                cur.execute("""
                    DELETE FROM ai_mode_results
                    WHERE keyword_id = %s AND project_id = %s
                """, (keyword_id, project_id))

                conn.commit()

                return {
                    'success': True,
                    'keyword': keyword_data['keyword']
                }

            except Exception as e:
                logger.error(f"Error deleting AI Mode keyword {keyword_id}: {e}")
                return {'success': False, 'error': str(e)}
        finally:
            try:
                conn.close()
            except Exception:
                pass

    @staticmethod
    def update_keyword(project_id: int, keyword_id: int, new_keyword: str) -> bool:
        """
        Actualizar el texto de una keyword AI Mode
        """
        conn = get_db_connection()
        if not conn:
            logger.error(f"update_keyword[ai_mode]({project_id},{keyword_id}): no DB connection")
            return False
        try:
            cur = conn.cursor()
            try:
                # Verificar que la keyword existe
                cur.execute("""
                    SELECT keyword FROM ai_mode_keywords
                    WHERE id = %s AND project_id = %s AND is_active = true
                """, (keyword_id, project_id))

                if not cur.fetchone():
                    logger.warning(f"AI Mode keyword {keyword_id} not found in project {project_id}")
                    return False

                # Verificar que no existe otra keyword con el mismo texto
                cur.execute("""
                    SELECT id FROM ai_mode_keywords
                    WHERE project_id = %s AND keyword = %s AND is_active = true AND id != %s
                """, (project_id, new_keyword, keyword_id))

                if cur.fetchone():
                    logger.warning(f"AI Mode keyword '{new_keyword}' already exists in project {project_id}")
                    return False

                # Actualizar la keyword
                cur.execute("""
                    UPDATE ai_mode_keywords
                    SET keyword = %s
                    WHERE id = %s AND project_id = %s
                """, (new_keyword, keyword_id, project_id))

                conn.commit()
                return True

            except Exception as e:
                logger.error(f"Error updating AI Mode keyword {keyword_id}: {e}")
                return False
        finally:
            try:
                conn.close()
            except Exception:
                pass
