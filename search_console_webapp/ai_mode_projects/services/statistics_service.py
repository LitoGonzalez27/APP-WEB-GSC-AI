"""
Servicio para cálculo de estadísticas y métricas del sistema Manual AI
"""

import logging
from datetime import date, timedelta
from typing import List, Dict
from database import get_db_connection

logger = logging.getLogger(__name__)


class StatisticsService:
    """Servicio para generar estadísticas y métricas de proyectos"""
    
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
        conn = get_db_connection()
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
        
        # Datos para gráfico de visibilidad por día
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
        conn = get_db_connection()
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
        
        cur.close()
        conn.close()
        
        return {
            'keywords': keywords,
            'total_keywords': len(keywords),
            'date_range': {
                'start': str(start_date),
                'end': str(end_date)
            }
        }
    
    @staticmethod
    def get_project_ai_overview_keywords_latest(project_id: int) -> Dict:
        """
        Tabla de AI Overview basada en el último análisis disponible por keyword
        
        Args:
            project_id: ID del proyecto
            
        Returns:
            Dict con datos de keywords del último análisis y competidores
        """
        conn = get_db_connection()
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
        
        cur.close()
        conn.close()
        
        return {
            'keywordResults': result_keywords,
            'competitorDomains': competitor_domains,
            'total_keywords': len(result_keywords)
        }
    
    @staticmethod
    def get_project_top_domains(project_id: int, limit: int = 10) -> List[Dict]:
        """
        Obtener los dominios más visibles para un proyecto
        
        Args:
            project_id: ID del proyecto
            limit: Número máximo de dominios a retornar
            
        Returns:
            Lista de dominios con sus métricas
        """
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                detected_domain,
                COUNT(DISTINCT keyword_id) as keyword_count,
                AVG(domain_position) as avg_position,
                MIN(domain_position) as best_position,
                COUNT(*) as total_mentions
            FROM manual_ai_global_domains
            WHERE project_id = %s
            GROUP BY detected_domain
            ORDER BY keyword_count DESC, avg_position ASC
            LIMIT %s
        """, (project_id, limit))
        
        domains = [dict(row) for row in cur.fetchall()]
        
        cur.close()
        conn.close()
        
        return domains
    
    @staticmethod
    def get_project_global_domains_ranking(project_id: int, days: int = 30) -> List[Dict]:
        """
        Obtener ranking global de TODOS los dominios detectados en AI Overview
        
        Args:
            project_id: ID del proyecto
            days: Número de días hacia atrás
            
        Returns:
            Lista de dominios con ranking completo y formateado para el frontend
        """
        conn = get_db_connection()
        cur = conn.cursor()
        
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        cur.execute("""
            SELECT 
                gd.detected_domain,
                gd.is_project_domain,
                gd.is_selected_competitor,
                COUNT(DISTINCT gd.keyword_id) as keywords_mentioned,
                COUNT(DISTINCT gd.analysis_date) as days_appeared,
                AVG(gd.domain_position) as avg_position,
                MIN(gd.domain_position) as best_position,
                MAX(gd.domain_position) as worst_position,
                COUNT(*) as total_mentions,
                ROUND((COUNT(DISTINCT gd.keyword_id)::float / 
                       NULLIF((SELECT COUNT(DISTINCT keyword_id) 
                              FROM manual_ai_global_domains 
                              WHERE project_id = %s 
                              AND analysis_date >= %s 
                              AND analysis_date <= %s), 0)::float * 100)::numeric, 2) as coverage_pct
            FROM manual_ai_global_domains gd
            WHERE gd.project_id = %s 
                AND gd.analysis_date >= %s 
                AND gd.analysis_date <= %s
            GROUP BY gd.detected_domain, gd.is_project_domain, gd.is_selected_competitor
            ORDER BY keywords_mentioned DESC, avg_position ASC
        """, (project_id, start_date, end_date, project_id, start_date, end_date))
        
        raw_domains = [dict(row) for row in cur.fetchall()]
        
        cur.close()
        conn.close()
        
        # Transformar datos para el formato esperado por el frontend
        domains = []
        for index, domain in enumerate(raw_domains, start=1):
            # Determinar tipo de dominio
            if domain['is_project_domain']:
                domain_type = 'project'
            elif domain['is_selected_competitor']:
                domain_type = 'competitor'
            else:
                domain_type = 'other'
            
            domains.append({
                'rank': index,
                'detected_domain': domain['detected_domain'],
                'domain_type': domain_type,
                'appearances': domain['keywords_mentioned'],
                'days_appeared': domain['days_appeared'],
                'avg_position': float(domain['avg_position']) if domain['avg_position'] else None,
                'best_position': domain['best_position'],
                'worst_position': domain['worst_position'],
                'total_mentions': domain['total_mentions'],
                'visibility_percentage': float(domain['coverage_pct']) if domain['coverage_pct'] else 0.0
            })
        
        return domains
    
    @staticmethod
    def get_latest_overview_stats(project_id: int) -> Dict:
        """
        Devuelve métricas de Overview basadas en el último análisis disponible
        
        Args:
            project_id: ID del proyecto
            
        Returns:
            Dict con estadísticas del último análisis
        """
        conn = get_db_connection()
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
        
        cur.close()
        conn.close()
        
        return stats

