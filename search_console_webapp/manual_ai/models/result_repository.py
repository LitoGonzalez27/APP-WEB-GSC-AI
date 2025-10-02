"""
Repositorio para operaciones de base de datos relacionadas con resultados de análisis
"""

import logging
import json
from datetime import date, timedelta
from typing import List, Dict
from database import get_db_connection

logger = logging.getLogger(__name__)


class ResultRepository:
    """Repositorio para gestión de resultados de análisis"""
    
    @staticmethod
    def create_result(project_id: int, keyword_id: int, analysis_date: date, 
                     keyword: str, domain: str, ai_result: Dict, serp_data: Dict, 
                     country_code: str):
        """
        Crear un nuevo resultado de análisis
        
        Args:
            project_id: ID del proyecto
            keyword_id: ID de la keyword
            analysis_date: Fecha del análisis
            keyword: Texto de la keyword
            domain: Dominio analizado
            ai_result: Resultado del análisis AI
            serp_data: Datos SERP raw
            country_code: Código de país
        """
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                INSERT INTO manual_ai_results (
                    project_id, keyword_id, analysis_date, keyword, domain,
                    has_ai_overview, domain_mentioned, domain_position, 
                    ai_elements_count, impact_score, raw_serp_data, 
                    ai_analysis_data, country_code
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                project_id, keyword_id, analysis_date, keyword, domain,
                ai_result.get('has_ai_overview', False),
                ai_result.get('domain_is_ai_source', False),
                ai_result.get('domain_ai_source_position'),
                ai_result.get('total_elements', 0),
                ai_result.get('impact_score', 0),
                json.dumps(serp_data),
                json.dumps(ai_result),
                country_code
            ))
            
            conn.commit()
            
        except Exception as e:
            logger.error(f"Error creating result: {e}")
            raise
        finally:
            cur.close()
            conn.close()
    
    @staticmethod
    def result_exists_for_date(project_id: int, keyword_id: int, analysis_date: date) -> bool:
        """
        Verificar si ya existe un análisis para una keyword en una fecha
        
        Args:
            project_id: ID del proyecto
            keyword_id: ID de la keyword
            analysis_date: Fecha a verificar
            
        Returns:
            True si existe, False en caso contrario
        """
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                SELECT 1 FROM manual_ai_results 
                WHERE project_id = %s AND keyword_id = %s AND analysis_date = %s
            """, (project_id, keyword_id, analysis_date))
            
            return cur.fetchone() is not None
            
        except Exception as e:
            logger.error(f"Error checking result existence: {e}")
            return False
        finally:
            cur.close()
            conn.close()
    
    @staticmethod
    def delete_result_for_date(project_id: int, keyword_id: int, analysis_date: date):
        """
        Eliminar un resultado existente (para permitir sobreescritura)
        
        Args:
            project_id: ID del proyecto
            keyword_id: ID de la keyword
            analysis_date: Fecha del análisis a eliminar
        """
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                DELETE FROM manual_ai_results 
                WHERE project_id = %s AND keyword_id = %s AND analysis_date = %s
            """, (project_id, keyword_id, analysis_date))
            
            conn.commit()
            logger.debug(f"Deleted existing result for keyword {keyword_id} on {analysis_date}")
            
        except Exception as e:
            logger.error(f"Error deleting result: {e}")
            raise
        finally:
            cur.close()
            conn.close()
    
    @staticmethod
    def get_project_results(project_id: int, days: int = 30) -> List[Dict]:
        """
        Obtener resultados de análisis de un proyecto
        
        Args:
            project_id: ID del proyecto
            days: Número de días hacia atrás
            
        Returns:
            Lista de resultados
        """
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            start_date = date.today() - timedelta(days=days)
            
            cur.execute("""
                SELECT 
                    r.*,
                    k.keyword
                FROM manual_ai_results r
                JOIN manual_ai_keywords k ON r.keyword_id = k.id
                WHERE r.project_id = %s 
                    AND r.analysis_date >= %s
                    AND k.is_active = true
                ORDER BY r.analysis_date DESC, r.keyword
            """, (project_id, start_date))
            
            results = cur.fetchall()
            return [dict(result) for result in results]
            
        except Exception as e:
            logger.error(f"Error fetching project results for project {project_id}: {e}")
            return []
        finally:
            cur.close()
            conn.close()
    
    @staticmethod
    def create_snapshot(project_id: int, snapshot_date: date, metrics: Dict):
        """
        Crear un snapshot diario de métricas
        
        Args:
            project_id: ID del proyecto
            snapshot_date: Fecha del snapshot
            metrics: Dict con métricas a guardar
        """
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                INSERT INTO manual_ai_snapshots (
                    project_id, snapshot_date,
                    total_keywords, active_keywords, keywords_with_ai,
                    domain_mentions, avg_position, visibility_percentage
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (project_id, snapshot_date) 
                DO UPDATE SET
                    total_keywords = EXCLUDED.total_keywords,
                    active_keywords = EXCLUDED.active_keywords,
                    keywords_with_ai = EXCLUDED.keywords_with_ai,
                    domain_mentions = EXCLUDED.domain_mentions,
                    avg_position = EXCLUDED.avg_position,
                    visibility_percentage = EXCLUDED.visibility_percentage
            """, (
                project_id, snapshot_date,
                metrics.get('total_keywords', 0),
                metrics.get('active_keywords', 0),
                metrics.get('keywords_with_ai', 0),
                metrics.get('domain_mentions', 0),
                metrics.get('avg_position'),
                metrics.get('visibility_percentage')
            ))
            
            conn.commit()
            logger.info(f"Snapshot created for project {project_id} on {snapshot_date}")
            
        except Exception as e:
            logger.error(f"Error creating snapshot: {e}")
        finally:
            cur.close()
            conn.close()

