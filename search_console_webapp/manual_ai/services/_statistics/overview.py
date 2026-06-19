"""
Servicio para cálculo de estadísticas y métricas del sistema Manual AI
"""

import logging
from datetime import date, timedelta
from typing import List, Dict
from database import get_db_connection

logger = logging.getLogger(__name__)


class _OverviewMixin:

    @staticmethod
    def get_project_statistics(project_id: int, days: int = 30) -> Dict:
        """
        Obtener estadísticas completas de un proyecto para gráficos

        Args:
            project_id: ID del proyecto
            days: Número de días hacia atrás

        Returns:
            Dict con estadísticas principales, datos de gráficos y eventos
        """
        # Refactor 2026-05-25: wrap in try/finally to GUARANTEE conn release
        # back to the pool even if any cur.execute() raises. Previous code
        # leaked pool slots on every DB hiccup.
        conn = get_db_connection()
        if not conn:
            logger.error(f"get_project_statistics({project_id}): no DB connection")
            return {
                'main_stats': {}, 'visibility_chart': [], 'positions_chart': [],
                'events': [], 'date_range': {'start': '', 'end': ''}
            }
        try:
            cur = conn.cursor()

            end_date = date.today()
            start_date = end_date - timedelta(days=days)

            # Estadísticas principales - Solo cuenta resultados más recientes por keyword
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
            active_keywords = int(main_stats.get('active_keywords') or 0)

            # Datos para gráfico de visibilidad por día
            cur.execute("""
                SELECT
                    r.analysis_date,
                    COUNT(DISTINCT r.keyword_id) as total_keywords_analyzed,
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
            # Filtrar días incompletos (evitar caídas por análisis parcial)
            if active_keywords > 0:
                visibility_data = [
                    row for row in visibility_data
                    if int(row.get('total_keywords_analyzed') or 0) >= active_keywords
                ]
            allowed_dates = {row['analysis_date'] for row in visibility_data if row.get('analysis_date')}

            # Datos para gráfico de posiciones
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
            if allowed_dates:
                positions_data = [row for row in positions_data if row.get('analysis_date') in allowed_dates]

            # Eventos para anotaciones
            cur.execute("""
                WITH ranked_events AS (
                    SELECT
                        event_date,
                        event_type,
                        event_title,
                        event_description,
                        keywords_affected,
                        ROW_NUMBER() OVER (
                            PARTITION BY event_date, event_type
                            ORDER BY
                                CASE WHEN event_description IS NOT NULL AND event_description != ''
                                     AND event_description != 'No additional notes provided'
                                     THEN 1 ELSE 2 END,
                                id DESC
                        ) as rn
                    FROM manual_ai_events
                    WHERE project_id = %s AND event_date >= %s AND event_date <= %s
                )
                SELECT event_date, event_type, event_title, event_description, keywords_affected
                FROM ranked_events
                WHERE rn = 1
                ORDER BY event_date
            """, (project_id, start_date, end_date))

            events_data = [dict(row) for row in cur.fetchall()]

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
        finally:
            try:
                conn.close()
            except Exception:
                pass

    @staticmethod
    def get_latest_overview_stats(project_id: int) -> Dict:
        """
        Devuelve métricas de Overview basadas en el último análisis disponible
        
        Args:
            project_id: ID del proyecto
            
        Returns:
            Dict con estadísticas del último análisis
        """
        # Refactor 2026-05-25: try/finally to GUARANTEE conn release.
        conn = get_db_connection()
        if not conn:
            logger.error(f"get_latest_overview_stats({project_id}): no DB connection")
            return {}
        try:
            cur = conn.cursor()

            cur.execute("""
                WITH latest_results AS (
                    SELECT DISTINCT ON (k.id)
                        k.id AS keyword_id,
                        r.has_ai_overview,
                        r.domain_mentioned,
                        r.domain_position,
                        r.analysis_date
                    FROM manual_ai_keywords k
                    LEFT JOIN manual_ai_results r ON k.id = r.keyword_id
                    WHERE k.project_id = %s
                    AND k.is_active = true
                    ORDER BY k.id, r.analysis_date DESC
                )
                SELECT
                    COUNT(*) as total_keywords,
                    COUNT(CASE WHEN has_ai_overview = true THEN 1 END) as total_ai_keywords,
                    COUNT(CASE WHEN domain_mentioned = true THEN 1 END) as total_mentions,
                    AVG(CASE WHEN domain_mentioned = true AND domain_position IS NOT NULL
                        THEN domain_position END)::float as avg_position,
                    (COUNT(CASE WHEN has_ai_overview = true THEN 1 END)::float /
                     NULLIF(COUNT(*), 0)::float * 100)::float as aio_weight_percentage,
                    (COUNT(CASE WHEN domain_mentioned = true THEN 1 END)::float /
                     NULLIF(COUNT(CASE WHEN has_ai_overview = true THEN 1 END), 0)::float * 100)::float as visibility_percentage,
                    MAX(analysis_date) as last_analysis_date
                FROM latest_results
            """, (project_id,))

            stats = dict(cur.fetchone() or {})

            return stats
        finally:
            try:
                conn.close()
            except Exception:
                pass
