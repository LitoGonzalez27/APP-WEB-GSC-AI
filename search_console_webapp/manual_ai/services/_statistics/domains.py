"""
Servicio para cálculo de estadísticas y métricas del sistema Manual AI
"""

import logging
from datetime import date, timedelta
from typing import List, Dict
from database import get_db_connection

logger = logging.getLogger(__name__)


class _DomainsMixin:

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
        # Refactor 2026-05-25: try/finally to GUARANTEE conn release.
        conn = get_db_connection()
        if not conn:
            logger.error(f"get_project_top_domains({project_id}): no DB connection")
            return []
        try:
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

            return domains
        finally:
            try:
                conn.close()
            except Exception:
                pass

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

        # Refactor 2026-05-25: try/finally GUARANTEES conn release back to the
        # pool even if SQL fails or we early-return. We isolate DB work into
        # an inner block; in-memory aggregation runs after the conn is freed
        # to minimise time the pool slot is held.
        conn = get_db_connection()
        if not conn:
            logger.error(f"get_project_global_domains_ranking({project_id}): no DB connection")
            return []
        try:
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
        finally:
            try:
                conn.close()
            except Exception:
                pass
        
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
        # Refactor 2026-05-25: try/finally to GUARANTEE conn release.
        conn = get_db_connection()
        if not conn:
            logger.error(f"get_project_urls_ranking({project_id}): no DB connection")
            return []
        try:
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
        finally:
            try:
                conn.close()
            except Exception:
                pass

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
