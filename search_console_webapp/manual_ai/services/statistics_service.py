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
        ACTUALIZADO: Ahora lee del JSON (coherente con ranking de URLs) en lugar de tabla global_domains
        
        Args:
            project_id: ID del proyecto
            days: Número de días hacia atrás
            
        Returns:
            Lista de dominios con ranking completo y formateado para el frontend
        """
        from urllib.parse import urlparse
        from collections import defaultdict
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        # Obtener proyecto para domain y competidores
        cur.execute("""
            SELECT domain, selected_competitors
            FROM manual_ai_projects
            WHERE id = %s
        """, (project_id,))
        
        project_row = cur.fetchone()
        if not project_row:
            cur.close()
            conn.close()
            return []
        
        project_domain = project_row['domain']
        competitor_domains = project_row['selected_competitors'] or []
        
        # Obtener todos los resultados con AI Overview del periodo
        cur.execute("""
            SELECT 
                r.id,
                r.keyword_id,
                r.keyword,
                r.ai_analysis_data,
                r.analysis_date
            FROM manual_ai_results r
            WHERE r.project_id = %s 
                AND r.analysis_date >= %s 
                AND r.analysis_date <= %s
                AND r.has_ai_overview = true
                AND r.ai_analysis_data IS NOT NULL
        """, (project_id, start_date, end_date))
        
        results = cur.fetchall()
        
        cur.close()
        conn.close()
        
        # Contador de dominios: {domain: {mentions: int, positions: [], dates: set, keywords: set}}
        domain_stats = defaultdict(lambda: {
            'mentions': 0,
            'positions': [],
            'dates': set(),
            'keywords': set()
        })
        
        total_keywords_with_aio = 0
        keywords_seen = set()
        
        # Procesar cada resultado
        for row in results:
            try:
                ai_analysis = row['ai_analysis_data'] or {}
                debug_info = ai_analysis.get('debug_info', {})
                references_found = debug_info.get('references_found', [])
                
                keyword_id = row['keyword_id']
                analysis_date = str(row['analysis_date'])
                
                # Marcar keyword como analizado
                if keyword_id not in keywords_seen:
                    keywords_seen.add(keyword_id)
                    total_keywords_with_aio += 1
                
                # Procesar cada referencia (COHERENTE con ranking de URLs)
                for ref in references_found:
                    url = ref.get('link', '').strip()
                    position = ref.get('index')
                    
                    if url:
                        try:
                            # Extraer dominio limpio
                            parsed = urlparse(url)
                            domain = parsed.netloc.lower()
                            if domain.startswith('www.'):
                                domain = domain[4:]
                            
                            if domain:
                                # Contar CADA mención (coherente con ranking de URLs)
                                domain_stats[domain]['mentions'] += 1
                                domain_stats[domain]['positions'].append(position + 1 if position is not None else 1)
                                domain_stats[domain]['dates'].add(analysis_date)
                                domain_stats[domain]['keywords'].add(keyword_id)
                        except:
                            continue
                            
            except Exception as e:
                logger.warning(f"Error parsing ai_analysis_data: {e}")
                continue
        
        if not domain_stats:
            return []
        
        # Transformar a lista y calcular métricas
        domains_list = []
        for domain, stats in domain_stats.items():
            avg_position = sum(stats['positions']) / len(stats['positions']) if stats['positions'] else None
            
            # Porcentaje basado en keywords únicos que mencionan este dominio
            keywords_count = len(stats['keywords'])
            visibility_pct = (keywords_count / total_keywords_with_aio * 100) if total_keywords_with_aio > 0 else 0
            
            # Determinar tipo de dominio
            domain_type = 'other'
            is_project_domain = False
            is_selected_competitor = False
            
            if project_domain and project_domain.lower() in domain:
                domain_type = 'project'
                is_project_domain = True
            elif any(comp and comp.lower() in domain for comp in competitor_domains):
                domain_type = 'competitor'
                is_selected_competitor = True
            
            domains_list.append({
                'rank': 0,  # Se asignará después de ordenar
                'detected_domain': domain,
                'domain_type': domain_type,
                'appearances': stats['mentions'],  # TOTAL DE MENCIONES (coherente con URLs)
                'days_appeared': len(stats['dates']),
                'avg_position': float(avg_position) if avg_position else None,
                'best_position': min(stats['positions']) if stats['positions'] else None,
                'worst_position': max(stats['positions']) if stats['positions'] else None,
                'total_mentions': stats['mentions'],
                'visibility_percentage': float(round(visibility_pct, 2)),
                'keywords_mentioned': keywords_count  # Añadido para referencia
            })
        
        # Ordenar por número de menciones totales (descendente)
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
    
    @staticmethod
    def get_project_urls_ranking(project_id: int, days: int = 30, limit: int = 20) -> List[Dict]:
        """
        Obtener ranking de URLs más mencionadas en AI Overview
        
        Este método extrae y agrupa todas las URLs que aparecen en las referencias de AI Overview,
        contando cuántas veces cada URL ha sido mencionada.
        
        Args:
            project_id: ID del proyecto
            days: Número de días hacia atrás
            limit: Número máximo de URLs a retornar
            
        Returns:
            Lista de URLs con sus métricas (menciones, %, posición promedio)
        """
        conn = get_db_connection()
        cur = conn.cursor()
        
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        # Obtener todos los resultados con AI Overview del periodo
        cur.execute("""
            SELECT 
                r.id,
                r.keyword,
                r.ai_analysis_data
            FROM manual_ai_results r
            WHERE r.project_id = %s 
                AND r.analysis_date >= %s 
                AND r.analysis_date <= %s
                AND r.has_ai_overview = true
                AND r.ai_analysis_data IS NOT NULL
        """, (project_id, start_date, end_date))
        
        results = cur.fetchall()
        
        cur.close()
        conn.close()
        
        # Procesar referencias y agrupar URLs
        url_mentions = {}
        url_positions = {}
        total_mentions = 0
        
        for row in results:
            ai_analysis = row['ai_analysis_data'] or {}
            debug_info = ai_analysis.get('debug_info', {})
            references_found = debug_info.get('references_found', [])
            
            for ref in references_found:
                url = ref.get('link', '').strip()
                position = ref.get('index')
                
                if url:
                    # Contar menciones
                    if url not in url_mentions:
                        url_mentions[url] = 0
                        url_positions[url] = []
                    
                    url_mentions[url] += 1
                    total_mentions += 1
                    
                    # Guardar posiciones (index + 1 para posición visual)
                    if position is not None:
                        url_positions[url].append(position + 1)
        
        # Convertir a lista y calcular métricas
        urls_data = []
        for url, mentions in url_mentions.items():
            # Calcular posición promedio
            positions_list = url_positions.get(url, [])
            avg_position = sum(positions_list) / len(positions_list) if positions_list else None
            
            # Calcular porcentaje sobre total de menciones
            percentage = (mentions / total_mentions * 100) if total_mentions > 0 else 0
            
            urls_data.append({
                'url': url,
                'mentions': mentions,
                'percentage': round(percentage, 2),
                'avg_position': round(avg_position, 1) if avg_position else None
            })
        
        # Ordenar por número de menciones (descendente)
        urls_data.sort(key=lambda x: x['mentions'], reverse=True)
        
        # Limitar resultados y añadir ranking
        top_urls = urls_data[:limit]
        for index, url_data in enumerate(top_urls, start=1):
            url_data['rank'] = index

        return top_urls

    @staticmethod
    def get_aio_vs_organic_comparison(project_id: int, days: int = 30) -> Dict:
        """
        Compara las URLs que rankean orgánicamente (top 10) con las URLs
        citadas como referencias en el AI Overview, para todas las keywords
        del proyecto en el rango de días indicado.

        Utiliza EXCLUSIVAMENTE datos ya almacenados en `manual_ai_results.raw_serp_data`:
          - `raw_serp_data->'organic_results'`   → top 10 orgánico
          - `raw_serp_data->'ai_overview'->'references'` → páginas citadas por AIO

        Cero coste SerpAPI extra. Cero cambios de schema.

        Produce tres bloques de insight:
          1. overall:        estadísticas globales de overlap (URL-exacto y dominio)
          2. my_domain_stats: los 4 cuadrantes para el dominio del proyecto
                              (Rank & Cited / Rank-only / Cited-only / Neither)
          3. per_keyword:     desglose por keyword con el cuadrante asignado

        Args:
            project_id: ID del proyecto
            days: Número de días hacia atrás (default 30)

        Returns:
            Dict con overall, my_domain_stats, per_keyword
        """
        from urllib.parse import urlparse

        def _normalize_url(u):
            """Normaliza una URL para comparación: lowercase host, strip www,
            strip trailing slash. Devuelve None si la URL está vacía."""
            if not u:
                return None
            try:
                p = urlparse(u)
                host = (p.netloc or '').lower()
                if host.startswith('www.'):
                    host = host[4:]
                path = (p.path or '').rstrip('/')
                return (f'{host}{path}').lower() or None
            except Exception:
                return u.lower() if u else None

        def _domain_of(u):
            """Extrae el dominio canónico (sin www) de una URL."""
            if not u:
                return None
            try:
                host = (urlparse(u).netloc or '').lower()
                if host.startswith('www.'):
                    host = host[4:]
                return host or None
            except Exception:
                return None

        conn = get_db_connection()
        cur = conn.cursor()
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)

            # Dominio del proyecto (para cálculos "my_domain_stats")
            cur.execute(
                "SELECT domain FROM manual_ai_projects WHERE id = %s",
                (project_id,)
            )
            project_row = cur.fetchone()
            project_domain = (project_row['domain'] if project_row else '') or ''
            # Normalizamos el dominio del proyecto para compararlo con los
            # dominios extraídos de las URLs (que vienen con/sin www).
            project_domain_norm = _domain_of(f'https://{project_domain}')

            cur.execute("""
                SELECT r.keyword,
                       r.raw_serp_data->'organic_results' AS organic,
                       r.raw_serp_data->'ai_overview'->'references' AS refs
                FROM manual_ai_results r
                WHERE r.project_id = %s
                  AND r.analysis_date BETWEEN %s AND %s
                  AND r.has_ai_overview = TRUE
                  AND jsonb_array_length(COALESCE(r.raw_serp_data->'organic_results', '[]'::jsonb)) > 0
                  AND jsonb_array_length(COALESCE(r.raw_serp_data->'ai_overview'->'references', '[]'::jsonb)) > 0
                ORDER BY r.analysis_date DESC, r.id DESC
            """, (project_id, start_date, end_date))
            rows = cur.fetchall()
        finally:
            cur.close()
            conn.close()

        # Acumuladores globales
        total_aio_refs = 0
        total_organic = 0
        overlap_url_total = 0
        overlap_domain_total = 0

        # Cuadrantes del dominio del proyecto (por keyword única)
        kw_in_organic = 0
        kw_in_aio = 0
        kw_in_both = 0
        kw_organic_only = 0
        kw_aio_only = 0
        kw_neither = 0

        per_keyword: List[Dict] = []

        # Para evitar duplicados por keyword (si la misma kw tiene N filas
        # en los últimos 30 días, nos quedamos con la más reciente que es
        # la primera por el ORDER BY)
        seen_keywords = set()

        for r in rows:
            kw_text = r['keyword']
            if kw_text in seen_keywords:
                continue
            seen_keywords.add(kw_text)

            organic = r['organic'] or []
            refs = r['refs'] or []

            org_url_set = set(filter(
                None, (_normalize_url(o.get('link')) for o in organic if isinstance(o, dict))
            ))
            org_dom_set = set(filter(
                None, (_domain_of(o.get('link')) for o in organic if isinstance(o, dict))
            ))
            ref_url_set = set(filter(
                None, (_normalize_url(o.get('link')) for o in refs if isinstance(o, dict))
            ))
            ref_dom_set = set(filter(
                None, (_domain_of(o.get('link')) for o in refs if isinstance(o, dict))
            ))

            n_url_overlap = len(ref_url_set & org_url_set)
            n_dom_overlap = len(ref_dom_set & org_dom_set)

            total_aio_refs += len(ref_url_set)
            total_organic += len(org_url_set)
            overlap_url_total += n_url_overlap
            overlap_domain_total += n_dom_overlap

            # Cuadrantes del dominio del proyecto (comparación por dominio,
            # NO por URL exacta: si mi dominio aparece en /pagina-A como
            # orgánico y en /pagina-B como ref de AIO, para el análisis
            # SEO/GEO cuenta como "presente en ambos").
            my_in_org = (
                project_domain_norm in org_dom_set
                if project_domain_norm else False
            )
            my_in_aio = (
                project_domain_norm in ref_dom_set
                if project_domain_norm else False
            )

            if my_in_org and my_in_aio:
                kw_in_both += 1
                quadrant = 'both'
            elif my_in_org and not my_in_aio:
                kw_organic_only += 1
                quadrant = 'organic_only'
            elif not my_in_org and my_in_aio:
                kw_aio_only += 1
                quadrant = 'aio_only'
            else:
                kw_neither += 1
                quadrant = 'neither'

            if my_in_org:
                kw_in_organic += 1
            if my_in_aio:
                kw_in_aio += 1

            per_keyword.append({
                'keyword': kw_text,
                'organic_count': len(org_url_set),
                'aio_refs_count': len(ref_url_set),
                'overlap_url_count': n_url_overlap,
                'overlap_domain_count': n_dom_overlap,
                'my_domain_in_organic': my_in_org,
                'my_domain_in_aio': my_in_aio,
                'quadrant': quadrant,
            })

        # Ordenar per_keyword: primero `both` (éxito), luego oportunidades
        # (organic_only, aio_only), luego `neither`. Dentro de cada grupo,
        # orden descendente por overlap.
        quadrant_order = {
            'both': 0,
            'organic_only': 1,
            'aio_only': 2,
            'neither': 3,
        }
        per_keyword.sort(
            key=lambda k: (quadrant_order[k['quadrant']], -k['overlap_url_count'])
        )

        overlap_rate_url = (
            round(overlap_url_total / total_aio_refs * 100, 1)
            if total_aio_refs else 0.0
        )
        overlap_rate_dom = (
            round(overlap_domain_total / total_aio_refs * 100, 1)
            if total_aio_refs else 0.0
        )

        return {
            'overall': {
                'total_keywords_analyzed': len(per_keyword),
                'keywords_with_aio_and_organic': len(per_keyword),
                'total_aio_refs': total_aio_refs,
                'total_organic_top10': total_organic,
                'aio_refs_also_in_organic_url': overlap_url_total,
                'aio_refs_also_in_organic_domain': overlap_domain_total,
                'overlap_rate_url': overlap_rate_url,
                'overlap_rate_domain': overlap_rate_dom,
            },
            'my_domain_stats': {
                'project_domain': project_domain,
                'keywords_in_organic_top10': kw_in_organic,
                'keywords_in_aio_refs': kw_in_aio,
                'keywords_in_both': kw_in_both,
                'keywords_organic_only': kw_organic_only,
                'keywords_aio_only': kw_aio_only,
                'keywords_neither': kw_neither,
            },
            'per_keyword': per_keyword,
        }

