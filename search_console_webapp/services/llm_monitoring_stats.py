"""
Servicio de Estadísticas para LLM Monitoring

Genera rankings y métricas agregadas de URLs mencionadas por LLMs
"""

import logging
from typing import List, Dict, Optional
from database import get_db_connection
from datetime import date, timedelta

logger = logging.getLogger(__name__)


class LLMMonitoringStatsService:
    """
    Servicio para calcular estadísticas de URLs mencionadas por LLMs
    """
    
    @staticmethod
    def get_project_urls_ranking(
        project_id: int,
        days: int = 30,
        llm_provider: Optional[str] = None,
        enabled_llms: Optional[List[str]] = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        Obtiene el ranking de URLs más mencionadas por los LLMs
        
        Analiza el campo `sources` de llm_monitoring_results que contiene
        las URLs citadas por cada LLM en sus respuestas.
        
        Args:
            project_id: ID del proyecto
            days: Número de días hacia atrás
            llm_provider: Filtrar por LLM específico ('openai', 'anthropic', 'google', 'perplexity')
                         Si es None, agrega de todos los LLMs
            limit: Número máximo de URLs a retornar
            
        Returns:
            Lista de dicts con:
                - rank: Posición en el ranking
                - url: URL mencionada
                - mentions: Número de menciones
                - percentage: % sobre total de menciones
                - llm_breakdown: Dict con menciones por LLM {'openai': 3, 'google': 2, ...}
                - providers: Lista de LLMs que mencionaron esta URL
                
        Example:
            >>> stats = LLMMonitoringStatsService.get_project_urls_ranking(1, days=7)
            >>> print(stats[0])
            {
                'rank': 1,
                'url': 'https://example.com/page',
                'mentions': 15,
                'percentage': 25.5,
                'llm_breakdown': {'openai': 8, 'google': 5, 'perplexity': 2},
                'providers': ['openai', 'google', 'perplexity']
            }
        """
        logger.info(f"🔍 Obteniendo ranking de URLs para proyecto {project_id}")
        logger.info(f"   Filtros: days={days}, llm_provider={llm_provider or 'all'}")
        
        conn = get_db_connection()
        if not conn:
            logger.error("❌ No se pudo conectar a BD")
            return []
        
        try:
            cur = conn.cursor()
            
            # Calcular fecha de inicio
            start_date = date.today() - timedelta(days=days)
            
            # Query base
            query = """
                SELECT 
                    llm_provider,
                    sources
                FROM llm_monitoring_results
                WHERE project_id = %s
                AND analysis_date >= %s
                AND sources IS NOT NULL
                AND sources != '[]'
            """
            
            params = [project_id, start_date]
            
            # Filtro opcional por LLM
            if llm_provider:
                query += " AND llm_provider = %s"
                params.append(llm_provider)
            elif enabled_llms:
                query += " AND llm_provider = ANY(%s)"
                params.append(enabled_llms)
            
            cur.execute(query, params)
            results = cur.fetchall()
            
            logger.info(f"📊 Encontrados {len(results)} resultados con sources")
            
            # Procesar URLs
            url_mentions = {}  # {url: count}
            url_llm_breakdown = {}  # {url: {llm: count}}
            total_mentions = 0
            
            for row in results:
                llm = row['llm_provider']
                sources = row['sources']
                
                # sources es un JSON array como: [{"url": "...", "provider": "..."}, ...]
                if isinstance(sources, str):
                    import json
                    try:
                        sources = json.loads(sources)
                    except:
                        continue
                
                if not isinstance(sources, list):
                    continue
                
                for source in sources:
                    if not isinstance(source, dict):
                        continue
                    
                    url = source.get('url', '').strip()
                    
                    if url:
                        # Contar mención general
                        if url not in url_mentions:
                            url_mentions[url] = 0
                            url_llm_breakdown[url] = {}
                        
                        url_mentions[url] += 1
                        total_mentions += 1
                        
                        # Contar por LLM
                        if llm not in url_llm_breakdown[url]:
                            url_llm_breakdown[url][llm] = 0
                        url_llm_breakdown[url][llm] += 1
            
            logger.info(f"📈 Procesadas {len(url_mentions)} URLs únicas, {total_mentions} menciones totales")
            
            # Convertir a lista y calcular métricas
            urls_data = []
            for url, mentions in url_mentions.items():
                # Calcular porcentaje
                percentage = (mentions / total_mentions * 100) if total_mentions > 0 else 0
                
                # Obtener LLMs que mencionaron esta URL
                llm_breakdown = url_llm_breakdown.get(url, {})
                providers = list(llm_breakdown.keys())
                
                urls_data.append({
                    'url': url,
                    'mentions': mentions,
                    'percentage': round(percentage, 2),
                    'llm_breakdown': llm_breakdown,
                    'providers': providers
                })
            
            # Ordenar por número de menciones (descendente)
            urls_data.sort(key=lambda x: x['mentions'], reverse=True)
            
            # Limitar resultados y añadir ranking
            top_urls = urls_data[:limit]
            for index, url_data in enumerate(top_urls, start=1):
                url_data['rank'] = index
            
            logger.info(f"✅ Top {len(top_urls)} URLs calculadas")
            
            cur.close()
            conn.close()
            
            return top_urls
            
        except Exception as e:
            logger.error(f"❌ Error calculando ranking de URLs: {e}", exc_info=True)
            return []
