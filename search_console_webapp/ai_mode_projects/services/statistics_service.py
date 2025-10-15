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
                    r.brand_mentioned,
                    r.mention_position,
                    r.analysis_date
                FROM ai_mode_keywords k
                LEFT JOIN ai_mode_results r ON k.id = r.keyword_id 
                    AND r.analysis_date >= %s AND r.analysis_date <= %s
                WHERE k.project_id = %s
                ORDER BY k.id, r.analysis_date DESC
            )
            SELECT 
                COUNT(*) as total_keywords,
                COUNT(CASE WHEN is_active = true THEN 1 END) as active_keywords,
                COUNT(CASE WHEN brand_mentioned = true THEN 1 END) as total_mentions,
                AVG(CASE WHEN mention_position IS NOT NULL THEN mention_position END) as avg_position,
                (COUNT(CASE WHEN brand_mentioned = true THEN 1 END)::float / 
                 NULLIF(COUNT(CASE WHEN analysis_date IS NOT NULL THEN 1 END), 0)::float * 100) as visibility_percentage
            FROM latest_results
        """, (start_date, end_date, project_id))
        
        main_stats = dict(cur.fetchone() or {})
        
        # Datos para gráfico de visibilidad por día
        cur.execute("""
            SELECT 
                r.analysis_date,
                COUNT(DISTINCT r.keyword_id) as total_keywords,
                COUNT(DISTINCT CASE WHEN r.brand_mentioned = true THEN r.keyword_id END) as mentions,
                (COUNT(DISTINCT CASE WHEN r.brand_mentioned = true THEN r.keyword_id END)::float / 
                 NULLIF(COUNT(DISTINCT r.keyword_id), 0)::float * 100) as visibility_pct
            FROM ai_mode_results r
            WHERE r.project_id = %s AND r.analysis_date >= %s AND r.analysis_date <= %s
            GROUP BY r.analysis_date
            ORDER BY r.analysis_date
        """, (project_id, start_date, end_date))
        
        visibility_data = [dict(row) for row in cur.fetchall()]
        
        # Datos para gráfico de posiciones
        cur.execute("""
            SELECT 
                r.analysis_date,
                COUNT(DISTINCT CASE WHEN r.mention_position BETWEEN 1 AND 3 THEN r.keyword_id END) as pos_1_3,
                COUNT(DISTINCT CASE WHEN r.mention_position BETWEEN 4 AND 10 THEN r.keyword_id END) as pos_4_10,
                COUNT(DISTINCT CASE WHEN r.mention_position BETWEEN 11 AND 20 THEN r.keyword_id END) as pos_11_20,
                COUNT(DISTINCT CASE WHEN r.mention_position > 20 THEN r.keyword_id END) as pos_21_plus
            FROM ai_mode_results r
            WHERE r.project_id = %s AND r.analysis_date >= %s AND r.analysis_date <= %s
                AND r.brand_mentioned = true
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
                FROM ai_mode_events
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
        
        # Obtener keywords con brand mentions y sus estadísticas
        cur.execute("""
            WITH keyword_stats AS (
                SELECT 
                    k.id,
                    k.keyword,
                    COUNT(DISTINCT r.analysis_date) as analysis_count,
                    COUNT(DISTINCT CASE WHEN r.brand_mentioned = true THEN r.analysis_date END) as mentions_count,
                    AVG(CASE WHEN r.brand_mentioned = true THEN r.mention_position END) as avg_position,
                    MAX(r.analysis_date) as last_analysis
                FROM ai_mode_keywords k
                LEFT JOIN ai_mode_results r ON k.id = r.keyword_id
                    AND r.analysis_date >= %s AND r.analysis_date <= %s
                WHERE k.project_id = %s AND k.is_active = true
                GROUP BY k.id, k.keyword
            )
            SELECT 
                id,
                keyword,
                analysis_count,
                mentions_count,
                avg_position,
                CASE 
                    WHEN analysis_count > 0 
                    THEN ROUND((mentions_count::float / analysis_count::float * 100)::numeric, 1)
                    ELSE 0 
                END as visibility,
                last_analysis
            FROM keyword_stats
            WHERE mentions_count > 0
            ORDER BY mentions_count DESC
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
            FROM ai_mode_projects
            WHERE id = %s
        """, (project_id,))
        
        project_row = cur.fetchone()
        competitor_domains = []
        if project_row and project_row['selected_competitors']:
            competitor_domains = project_row['selected_competitors']
        
        # Obtener últimos resultados de keywords con brand mentions
        cur.execute("""
            WITH latest_results AS (
                SELECT DISTINCT ON (k.id)
                    k.id,
                    k.keyword,
                    r.brand_mentioned,
                    r.mention_position,
                    r.analysis_date
                FROM ai_mode_keywords k
                LEFT JOIN ai_mode_results r ON k.id = r.keyword_id
                WHERE k.project_id = %s AND k.is_active = true
                ORDER BY k.id, r.analysis_date DESC
            )
            SELECT 
                id,
                keyword,
                brand_mentioned,
                mention_position,
                analysis_date as last_analysis
            FROM latest_results
            WHERE analysis_date IS NOT NULL
            ORDER BY 
                CASE WHEN brand_mentioned = true THEN 0 ELSE 1 END,
                mention_position NULLS LAST,
                keyword
        """, (project_id,))
        
        keywords = [dict(row) for row in cur.fetchall()]
        
        # Para cada keyword, obtener información de competidores desde raw_ai_mode_data
        result_keywords = []
        for kw in keywords:
            keyword_data = {
                'keyword': kw['keyword'],
                'user_domain_in_aio': kw['brand_mentioned'] or False,
                'user_domain_position': kw['mention_position'] if kw['mention_position'] else None,
                'last_analysis': kw['last_analysis'],
                'competitors': []
            }
            
            # Extraer competidores de raw_ai_mode_data si hay análisis
            if competitor_domains and kw['last_analysis']:
                cur.execute("""
                    SELECT raw_ai_mode_data
                    FROM ai_mode_results
                    WHERE project_id = %s
                        AND keyword_id = %s
                        AND analysis_date = %s
                        AND raw_ai_mode_data IS NOT NULL
                """, (project_id, kw['id'], kw['last_analysis']))
                
                result_row = cur.fetchone()
                if result_row and result_row['raw_ai_mode_data']:
                    try:
                        from urllib.parse import urlparse
                        serp_data = result_row['raw_ai_mode_data']
                        references = serp_data.get('references', [])
                        
                        # Buscar cada competidor en las references
                        for comp_domain in competitor_domains:
                            comp_lower = comp_domain.lower()
                            for ref in references:
                                link = ref.get('link', '')
                                if link:
                                    try:
                                        parsed = urlparse(link)
                                        domain = parsed.netloc.lower()
                                        if domain.startswith('www.'):
                                            domain = domain[4:]
                                        
                                        # Si el dominio coincide con el competidor
                                        if comp_lower in domain or domain in comp_lower:
                                            keyword_data['competitors'].append({
                                                'domain': comp_domain,
                                                'position': ref.get('position', 0)
                                            })
                                            break  # Solo la primera aparición de este competidor
                                    except:
                                        continue
                    except Exception as e:
                        logger.warning(f"Error extracting competitors from raw_ai_mode_data: {e}")
            
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
        from database import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT detected_domain,
                       COUNT(*) AS appearances,
                       AVG(domain_position)::float AS avg_position
                FROM ai_mode_global_domains
                WHERE project_id = %s
                GROUP BY detected_domain
                ORDER BY appearances DESC
                LIMIT %s
            """, (project_id, limit))
            rows = cur.fetchall()
            domains = []
            for idx, row in enumerate(rows, 1):
                domains.append({
                    'detected_domain': row['detected_domain'],
                    'domain_type': 'other',
                    'appearances': row['appearances'],
                    'days_appeared': None,
                    'avg_position': row['avg_position'],
                    'visibility_percentage': None,
                    'is_project_domain': False,
                    'is_selected_competitor': False,
                    'rank': idx
                })
            return domains
        except Exception as e:
            logger.warning(f"Top domains not available: {e}")
            return []
        finally:
            try:
                cur.close(); conn.close()
            except Exception:
                pass
    
    @staticmethod
    def get_project_global_domains_ranking(project_id: int, days: int = 30) -> List[Dict]:
        """
        Obtener ranking global de TODOS los dominios detectados en AI Mode
        Extrae dominios desde raw_ai_mode_data (Google AI Mode sources)
        
        Args:
            project_id: ID del proyecto
            days: Número de días hacia atrás
            
        Returns:
            Lista de dominios con ranking completo y formateado para el frontend
        """
        from urllib.parse import urlparse
        from collections import defaultdict
        from datetime import timedelta
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        # Obtener proyecto para brand_name y competidores
        cur.execute("""
            SELECT brand_name, selected_competitors
            FROM ai_mode_projects
            WHERE id = %s
        """, (project_id,))
        
        project_row = cur.fetchone()
        if not project_row:
            cur.close()
            conn.close()
            return []
        
        brand_name = project_row['brand_name']
        competitor_domains = project_row['selected_competitors'] or []
        
        # Obtener todos los resultados con raw_ai_mode_data
        cur.execute("""
            SELECT 
                raw_ai_mode_data,
                analysis_date,
                keyword_id
            FROM ai_mode_results
            WHERE project_id = %s 
                AND analysis_date >= %s 
                AND analysis_date <= %s
                AND raw_ai_mode_data IS NOT NULL
        """, (project_id, start_date, end_date))
        
        results = cur.fetchall()
        
        # Contador de dominios: {domain: {mentions: int, positions: [], dates: set}}
        domain_stats = defaultdict(lambda: {
            'mentions': 0,
            'positions': [],
            'dates': set()
        })
        
        total_keywords_analyzed = 0
        keywords_seen = set()
        
        # Procesar cada resultado
        for row in results:
            try:
                # raw_ai_mode_data ya está parseado por psycopg2 (JSONB)
                serp_data = row['raw_ai_mode_data']
                keyword_id = row['keyword_id']
                analysis_date = str(row['analysis_date'])
                
                # Marcar este keyword como analizado
                if keyword_id not in keywords_seen:
                    keywords_seen.add(keyword_id)
                    total_keywords_analyzed += 1
                
                # Google AI Mode estructura real: {text_blocks, references, inline_images}
                # Extraer dominios de references (fuentes citadas)
                references = serp_data.get('references', [])
                
                for ref in references:
                    link = ref.get('link', '')
                    position = ref.get('position', 0)
                    if link:
                        try:
                            # Extraer dominio limpio
                            parsed = urlparse(link)
                            domain = parsed.netloc.lower()
                            if domain.startswith('www.'):
                                domain = domain[4:]
                            
                            if domain:
                                domain_stats[domain]['mentions'] += 1
                                domain_stats[domain]['positions'].append(position if position else 1)
                                domain_stats[domain]['dates'].add(analysis_date)
                        except:
                            continue
                            
            except Exception as e:
                logger.warning(f"Error parsing raw_ai_mode_data: {e}")
                continue
        
        cur.close()
        conn.close()
        
        if not domain_stats:
            return []
        
        # Transformar a lista y calcular métricas
        domains_list = []
        for domain, stats in domain_stats.items():
            avg_position = sum(stats['positions']) / len(stats['positions']) if stats['positions'] else None
            visibility_pct = (stats['mentions'] / total_keywords_analyzed * 100) if total_keywords_analyzed > 0 else 0
            
            # Determinar tipo de dominio
            domain_type = 'other'
            if brand_name and brand_name.lower() in domain:
                domain_type = 'project'
            elif any(comp and comp.lower() in domain for comp in competitor_domains):
                domain_type = 'competitor'
            
            domains_list.append({
                'detected_domain': domain,
                'domain_type': domain_type,
                'appearances': stats['mentions'],
                'days_appeared': len(stats['dates']),
                'avg_position': avg_position,
                'visibility_percentage': visibility_pct,
                'is_project_domain': domain_type == 'project',
                'is_selected_competitor': domain_type == 'competitor',
                'rank': 0  # Se asignará después de ordenar
            })
        
        # Ordenar por número de menciones (descendente)
        domains_list.sort(key=lambda x: x['appearances'], reverse=True)
        
        # Agregar rank
        for idx, domain in enumerate(domains_list, 1):
            domain['rank'] = idx
        
        return domains_list
    
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
                    r.brand_mentioned,
                    r.mention_position,
                    r.analysis_date
                FROM ai_mode_keywords k
                LEFT JOIN ai_mode_results r ON k.id = r.keyword_id
                WHERE k.project_id = %s
                AND k.is_active = true
                ORDER BY k.id, r.analysis_date DESC
            )
            SELECT 
                COUNT(*) as total_keywords,
                COUNT(CASE WHEN brand_mentioned = true THEN 1 END) as total_mentions,
                AVG(CASE WHEN brand_mentioned = true AND mention_position IS NOT NULL 
                    THEN mention_position END)::float as avg_position,
                (COUNT(CASE WHEN brand_mentioned = true THEN 1 END)::float / 
                 NULLIF(COUNT(*), 0)::float * 100)::float as visibility_percentage,
                MAX(analysis_date) as last_analysis_date
            FROM latest_results
        """, (project_id,))
        
        stats = dict(cur.fetchone() or {})
        
        cur.close()
        conn.close()
        
        return stats

