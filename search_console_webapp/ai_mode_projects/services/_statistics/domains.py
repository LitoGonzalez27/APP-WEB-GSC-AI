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
        # Refactor 2026-05-25: null-check + cursor inside try.
        from database import get_db_connection
        conn = get_db_connection()
        if not conn:
            logger.error(f"get_project_top_domains({project_id}): no DB connection")
            return []
        try:
            cur = conn.cursor()
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
                conn.close()
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

        # Refactor 2026-05-25: null-check + try/finally. Only the SQL phase
        # needs the conn — the in-memory aggregation below runs after release.
        conn = get_db_connection()
        if not conn:
            logger.error(f"get_project_global_domains_ranking({project_id}): no DB connection")
            return []
        try:
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
        finally:
            try:
                conn.close()
            except Exception:
                pass

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
    def get_project_urls_ranking(project_id: int, days: int = 30, limit: int = 20) -> List[Dict]:
        """
        Obtener ranking de URLs más mencionadas en AI Mode
        
        Este método extrae y agrupa todas las URLs que aparecen en las referencias de AI Mode,
        contando cuántas veces cada URL ha sido mencionada.
        
        Args:
            project_id: ID del proyecto
            days: Número de días hacia atrás
            limit: Número máximo de URLs a retornar
            
        Returns:
            Lista de URLs con sus métricas (menciones, %, posición promedio)
        """
        # Refactor 2026-05-25: null-check + try/finally for SQL phase.
        conn = get_db_connection()
        if not conn:
            logger.error(f"get_project_urls_ranking({project_id}): no DB connection")
            return []
        try:
            cur = conn.cursor()

            end_date = date.today()
            start_date = end_date - timedelta(days=days)

            # Obtener todos los resultados con AI Mode del periodo
            cur.execute("""
                SELECT
                    r.id,
                    r.keyword,
                    r.raw_ai_mode_data
                FROM ai_mode_results r
                WHERE r.project_id = %s
                    AND r.analysis_date >= %s
                    AND r.analysis_date <= %s
                    AND r.raw_ai_mode_data IS NOT NULL
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
        
        # Debug: contador de referencias sin posición
        refs_without_position = 0
        refs_with_position = 0
        
        for row in results:
            raw_data = row['raw_ai_mode_data'] or {}
            
            # En AI Mode, las referencias están directamente en 'references'
            references = raw_data.get('references', [])
            
            for ref in references:
                url = ref.get('link', '').strip()
                # AI Mode usa 'index' (0-based) en lugar de 'position'
                index = ref.get('index')
                position = None
                
                # Convertir index (0-based) a position (1-based)
                if index is not None:
                    if isinstance(index, (int, float)):
                        position = float(index) + 1
                    elif isinstance(index, str):
                        try:
                            position = float(index.strip()) + 1
                        except Exception:
                            position = None
                
                # Debug: log de primeras referencias
                if total_mentions < 5:
                    logger.info(f"📍 URL #{total_mentions + 1}: {url[:50]}... | index={index} | position={position}")
                
                if url:
                    # Contar menciones
                    if url not in url_mentions:
                        url_mentions[url] = 0
                        url_positions[url] = []
                    
                    url_mentions[url] += 1
                    total_mentions += 1
                    
                    # Guardar posiciones válidas (>= 1 después de la conversión)
                    if position is not None and position >= 1:
                        url_positions[url].append(position)
                        refs_with_position += 1
                    else:
                        refs_without_position += 1
        
        logger.info(f"📊 URLs Stats: {len(url_mentions)} unique URLs, {total_mentions} total mentions")
        logger.info(f"📍 Position Stats: {refs_with_position} with valid position, {refs_without_position} without position")
        
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
                'avg_position': round(avg_position, 1) if avg_position is not None else None
            })
        
        # Ordenar por número de menciones (descendente)
        urls_data.sort(key=lambda x: x['mentions'], reverse=True)
        
        # Limitar resultados y añadir ranking
        top_urls = urls_data[:limit]
        for index, url_data in enumerate(top_urls, start=1):
            url_data['rank'] = index
        
        return top_urls
