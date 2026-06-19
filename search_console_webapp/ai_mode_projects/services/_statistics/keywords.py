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
        # Refactor 2026-05-25: null-check + try/finally.
        conn = get_db_connection()
        if not conn:
            logger.error(f"get_project_ai_overview_keywords({project_id}): no DB connection")
            return {'keywords': [], 'total_keywords': 0, 'date_range': {'start': '', 'end': ''}}
        try:
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
        # Refactor 2026-05-25: null-check + try/finally.
        conn = get_db_connection()
        if not conn:
            logger.error(f"get_project_ai_overview_keywords_latest({project_id}): no DB connection")
            return {'keywordResults': [], 'competitorDomains': [], 'total_keywords': 0}
        try:
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

                            # Ordenar referencias por el campo 'index' (0-based) para mantener consistencia
                            # con analysis_service.py
                            enriched_refs = []
                            for i, ref in enumerate(references):
                                if not isinstance(ref, dict):
                                    continue
                                idx = ref.get('index')
                                idx_num = idx if isinstance(idx, int) and idx >= 0 else None
                                enriched_refs.append((idx_num, i, ref))
                            enriched_refs.sort(key=lambda t: (t[0] is None, t[0] if t[0] is not None else 10**9, t[1]))

                            # Buscar cada competidor en las references ordenadas
                            for comp_domain in competitor_domains:
                                comp_lower = comp_domain.lower()
                                found = False
                                for loop_idx, (index_value, original_idx, ref) in enumerate(enriched_refs):
                                    link = ref.get('link', '')
                                    if link:
                                        try:
                                            parsed = urlparse(link)
                                            domain = parsed.netloc.lower()
                                            if domain.startswith('www.'):
                                                domain = domain[4:]

                                            # Si el dominio coincide con el competidor
                                            if comp_lower in domain or domain in comp_lower:
                                                # Calcular posición: usar index (0-based) + 1, igual que en analysis_service.py
                                                actual_index = ref.get('index')
                                                position = (actual_index + 1) if isinstance(actual_index, int) and actual_index >= 0 else (loop_idx + 1)

                                                keyword_data['competitors'].append({
                                                    'domain': comp_domain,
                                                    'position': position
                                                })
                                                found = True
                                                break  # Solo la primera aparición de este competidor
                                        except:
                                            continue
                                    if found:
                                        break
                        except Exception as e:
                            logger.warning(f"Error extracting competitors from raw_ai_mode_data: {e}")

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
