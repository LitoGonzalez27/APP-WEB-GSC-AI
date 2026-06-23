"""
Servicio para cálculo de estadísticas y métricas del sistema Manual AI
"""

import logging
from datetime import date, timedelta
from typing import List, Dict
from database import get_db_connection

logger = logging.getLogger(__name__)


class _AioOrganicMixin:

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

        Produce cuatro bloques de insight:
          1. overall:             estadísticas globales de overlap (URL-exacto y dominio)
          2. my_domain_stats:     los 4 cuadrantes para el dominio del proyecto
                                  (Rank & Cited / Rank-only / Cited-only / Neither)
          3. position_correlation: correlación entre posición orgánica del dominio
                                   del proyecto y probabilidad de ser citado en AIO.
                                   Agrupa por buckets: Top 3 / 4-10 / 11+ / Not ranking.
                                   Responde: "¿Rankear más alto orgánicamente
                                   aumenta la probabilidad de ser citado en AIO?"
          4. per_keyword:         desglose por keyword con cuadrante + posición

        Args:
            project_id: ID del proyecto
            days: Número de días hacia atrás (default 30)

        Returns:
            Dict con overall, my_domain_stats, position_correlation, per_keyword
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

            # Selección de fila ALINEADA con el Overview: una sola fila por
            # keyword (la MÁS RECIENTE del rango), idéntico a
            # get_project_statistics() en overview.py. Así el panel mira el
            # mismo día que el contador de "menciones" del Overview y no
            # diverge por elegir un día distinto de la misma keyword.
            #
            # "Citado en AIO" pasa a usar r.domain_mentioned (la MISMA señal
            # que el Overview: detecta el dominio en referencias oficiales,
            # en el texto del AI Overview y en listados). Antes este panel
            # solo miraba el array `references`, perdiendo las menciones en
            # texto/listado que no llevan link.
            #
            # Denominador ("keywords analizadas") = keywords cuya última fila
            # tiene AI Overview + resultados orgánicos. Ya NO se exige que el
            # array `references` esté poblado (una mención en texto puede
            # existir sin referencias formales).
            cur.execute("""
                WITH latest AS (
                    SELECT DISTINCT ON (k.id)
                        k.id AS keyword_id,
                        k.keyword,
                        r.has_ai_overview,
                        r.domain_mentioned,
                        r.raw_serp_data->'organic_results' AS organic,
                        r.raw_serp_data->'ai_overview'->'references' AS refs
                    FROM manual_ai_keywords k
                    LEFT JOIN manual_ai_results r ON k.id = r.keyword_id
                        AND r.analysis_date >= %s AND r.analysis_date <= %s
                    WHERE k.project_id = %s
                    ORDER BY k.id, r.analysis_date DESC
                )
                SELECT keyword, domain_mentioned, organic, refs
                FROM latest
                WHERE has_ai_overview = TRUE
                  AND jsonb_array_length(COALESCE(organic, '[]'::jsonb)) > 0
            """, (start_date, end_date, project_id))
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

        # Position correlation: para cada bucket de posición orgánica del
        # dominio del proyecto, contar cuántas keywords caen en ese bucket
        # y cuántas de esas están también citadas en AIO. El objetivo es
        # responder "¿rankear más alto correlaciona con más AIO mentions?".
        #
        # Buckets:
        #   - top_3:         organic position in [1, 3]
        #   - positions_4_10: organic position in [4, 10]
        #   - beyond_top_10: organic position >= 11 (rare con num=10,
        #                    pero posible con num=20)
        #   - not_ranking:   domain NOT found in organic_results
        position_buckets = {
            'top_3':          {'total_keywords': 0, 'cited_in_aio': 0},
            'positions_4_10': {'total_keywords': 0, 'cited_in_aio': 0},
            'beyond_top_10':  {'total_keywords': 0, 'cited_in_aio': 0},
            'not_ranking':    {'total_keywords': 0, 'cited_in_aio': 0},
        }

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

            # Extraer la posición orgánica del dominio del proyecto (si
            # aparece en el top N del organic). Si aparece varias veces
            # (raro pero posible con distintas URLs del mismo dominio),
            # nos quedamos con la mejor posición (más alta en el SERP).
            my_organic_position = None
            if project_domain_norm:
                for o in organic:
                    if not isinstance(o, dict):
                        continue
                    o_domain = _domain_of(o.get('link'))
                    if o_domain == project_domain_norm:
                        pos = o.get('position')
                        # `position` en SerpAPI es 1-indexed.
                        if isinstance(pos, int) and pos > 0:
                            if my_organic_position is None or pos < my_organic_position:
                                my_organic_position = pos

            n_url_overlap = len(ref_url_set & org_url_set)
            n_dom_overlap = len(ref_dom_set & org_dom_set)

            total_aio_refs += len(ref_url_set)
            total_organic += len(org_url_set)
            overlap_url_total += n_url_overlap
            overlap_domain_total += n_dom_overlap

            # Cuadrantes del dominio del proyecto:
            #   - Orgánico: comparación por dominio (no URL exacta): si mi
            #     dominio aparece en cualquier resultado orgánico, cuenta.
            #   - AIO: usa domain_mentioned (referencias + texto + listados),
            #     la misma señal que el Overview.
            my_in_org = (
                project_domain_norm in org_dom_set
                if project_domain_norm else False
            )
            # "Citado en AIO" = MISMA señal que el Overview (domain_mentioned),
            # que cubre referencias oficiales + menciones en texto + listados.
            # `ref_dom_set` se sigue usando para las stats de overlap y para
            # aio_refs_count, pero ya NO decide si el dominio cuenta como
            # citado (eso perdía las menciones de texto sin link).
            my_in_aio = bool(r['domain_mentioned'])

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

            # Asignar la keyword a su bucket de posición orgánica y
            # contabilizar si además está citada en AIO.
            if my_organic_position is None:
                bucket_key = 'not_ranking'
            elif my_organic_position <= 3:
                bucket_key = 'top_3'
            elif my_organic_position <= 10:
                bucket_key = 'positions_4_10'
            else:
                bucket_key = 'beyond_top_10'

            position_buckets[bucket_key]['total_keywords'] += 1
            if my_in_aio:
                position_buckets[bucket_key]['cited_in_aio'] += 1

            per_keyword.append({
                'keyword': kw_text,
                'organic_count': len(org_url_set),
                'aio_refs_count': len(ref_url_set),
                'overlap_url_count': n_url_overlap,
                'overlap_domain_count': n_dom_overlap,
                'my_domain_in_organic': my_in_org,
                'my_domain_in_aio': my_in_aio,
                'my_organic_position': my_organic_position,
                'position_bucket': bucket_key,
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

        # Calcular el AIO rate (%) para cada bucket de posición.
        # Formula: cited_in_aio / total_keywords * 100.
        # Si el bucket está vacío, aio_rate es 0.
        position_correlation = {}
        for bucket_key, bucket_data in position_buckets.items():
            total = bucket_data['total_keywords']
            cited = bucket_data['cited_in_aio']
            aio_rate = round(cited / total * 100, 1) if total > 0 else 0.0
            position_correlation[bucket_key] = {
                'total_keywords': total,
                'cited_in_aio': cited,
                'aio_rate': aio_rate,
            }

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
            'position_correlation': position_correlation,
            'per_keyword': per_keyword,
        }
