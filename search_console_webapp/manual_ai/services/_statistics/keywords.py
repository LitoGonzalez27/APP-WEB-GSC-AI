"""
Servicio para cálculo de estadísticas y métricas del sistema Manual AI
"""

import logging
from datetime import date, timedelta
from typing import List, Dict
from database import get_db_connection

logger = logging.getLogger(__name__)


class _KeywordsMixin:

    @staticmethod
    def get_project_ai_overview_keywords(project_id: int, days: int = 30) -> Dict:
        """
        Obtener datos detallados de keywords con AI Overview para tabla Grid.js
        
        Args:
            project_id: ID del proyecto
            days: Número de días hacia atrás
            
        Returns:
            Dict con datos de keywords y estadísticas
        """
        # Refactor 2026-05-25: try/finally to GUARANTEE conn release.
        conn = get_db_connection()
        if not conn:
            logger.error(f"get_project_ai_overview_keywords({project_id}): no DB connection")
            return {'keywords': [], 'total_keywords': 0,
                    'date_range': {'start': '', 'end': ''}}
        try:
            cur = conn.cursor()

            end_date = date.today()
            start_date = end_date - timedelta(days=days)

            # Obtener keywords con AI Overview y sus estadísticas
            cur.execute("""
                WITH keyword_stats AS (
                    SELECT
                        k.id,
                        k.keyword,
                        COUNT(DISTINCT r.analysis_date) as analysis_count,
                        COUNT(DISTINCT CASE WHEN r.has_ai_overview = true THEN r.analysis_date END) as ai_overview_count,
                        COUNT(DISTINCT CASE WHEN r.domain_mentioned = true THEN r.analysis_date END) as mentions_count,
                        AVG(CASE WHEN r.domain_mentioned = true THEN r.domain_position END) as avg_position,
                        MAX(r.analysis_date) as last_analysis
                    FROM manual_ai_keywords k
                    LEFT JOIN manual_ai_results r ON k.id = r.keyword_id
                        AND r.analysis_date >= %s AND r.analysis_date <= %s
                    WHERE k.project_id = %s AND k.is_active = true
                    GROUP BY k.id, k.keyword
                )
                SELECT
                    id,
                    keyword,
                    analysis_count,
                    ai_overview_count,
                    mentions_count,
                    avg_position,
                    CASE
                        WHEN analysis_count > 0
                        THEN ROUND((ai_overview_count::float / analysis_count::float * 100)::numeric, 1)
                        ELSE 0
                    END as ai_frequency,
                    CASE
                        WHEN ai_overview_count > 0
                        THEN ROUND((mentions_count::float / ai_overview_count::float * 100)::numeric, 1)
                        ELSE 0
                    END as visibility,
                    last_analysis
                FROM keyword_stats
                WHERE ai_overview_count > 0
                ORDER BY ai_overview_count DESC, mentions_count DESC
            """, (start_date, end_date, project_id))

            keywords = [dict(row) for row in cur.fetchall()]

            return {
                'keywords': keywords,
                'total_keywords': len(keywords),
                'date_range': {
                    'start': str(start_date),
                    'end': str(end_date)
                }
            }
        finally:
            try:
                conn.close()
            except Exception:
                pass

    @staticmethod
    def get_project_ai_overview_keywords_latest(project_id: int) -> Dict:
        """
        Tabla de AI Overview basada en el último análisis disponible por keyword
        
        Args:
            project_id: ID del proyecto
            
        Returns:
            Dict con datos de keywords del último análisis y competidores
        """
        # Refactor 2026-05-25: try/finally to GUARANTEE conn release.
        conn = get_db_connection()
        if not conn:
            logger.error(f"get_project_ai_overview_keywords_latest({project_id}): no DB connection")
            return {'keywordResults': [], 'competitorDomains': [], 'total_keywords': 0}
        try:
            cur = conn.cursor()

            # Obtener competidores del proyecto
            cur.execute("""
                SELECT selected_competitors
                FROM manual_ai_projects
                WHERE id = %s
            """, (project_id,))

            project_row = cur.fetchone()
            competitor_domains = []
            if project_row and project_row['selected_competitors']:
                competitor_domains = project_row['selected_competitors']

            # Obtener últimos resultados de keywords con AI Overview
            cur.execute("""
                WITH latest_results AS (
                    SELECT DISTINCT ON (k.id)
                        k.id,
                        k.keyword,
                        r.has_ai_overview,
                        r.domain_mentioned,
                        r.domain_position,
                        r.analysis_date
                    FROM manual_ai_keywords k
                    LEFT JOIN manual_ai_results r ON k.id = r.keyword_id
                    WHERE k.project_id = %s AND k.is_active = true
                    ORDER BY k.id, r.analysis_date DESC
                )
                SELECT
                    id,
                    keyword,
                    has_ai_overview,
                    domain_mentioned,
                    domain_position,
                    analysis_date as last_analysis
                FROM latest_results
                WHERE has_ai_overview = true
                ORDER BY
                    CASE WHEN domain_mentioned = true THEN 0 ELSE 1 END,
                    domain_position NULLS LAST,
                    keyword
            """, (project_id,))

            keywords = [dict(row) for row in cur.fetchall()]

            # Para cada keyword, obtener información de competidores
            result_keywords = []
            for kw in keywords:
                keyword_data = {
                    'keyword': kw['keyword'],
                    'user_domain_in_aio': kw['domain_mentioned'] or False,
                    'user_domain_position': kw['domain_position'] if kw['domain_position'] else None,
                    'last_analysis': kw['last_analysis'],
                    'competitors': []
                }

                # Obtener datos de competidores de global_domains para esta keyword en su última fecha
                if competitor_domains and kw['last_analysis']:
                    cur.execute("""
                        SELECT
                            detected_domain,
                            domain_position
                        FROM manual_ai_global_domains
                        WHERE project_id = %s
                            AND keyword_id = %s
                            AND analysis_date = %s
                            AND detected_domain = ANY(%s)
                    """, (project_id, kw['id'], kw['last_analysis'], competitor_domains))

                    comp_data = cur.fetchall()
                    for comp in comp_data:
                        keyword_data['competitors'].append({
                            'domain': comp['detected_domain'],
                            'position': comp['domain_position']
                        })

                result_keywords.append(keyword_data)

            return {
                'keywordResults': result_keywords,
                'competitorDomains': competitor_domains,
                'total_keywords': len(result_keywords)
            }
        finally:
            try:
                conn.close()
            except Exception:
                pass
