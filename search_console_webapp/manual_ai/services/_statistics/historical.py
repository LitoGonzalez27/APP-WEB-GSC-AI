"""
Comparación histórica de AI Overview para Manual AI.

Responde a la pregunta de negocio: "Hace N días estas keywords me mencionaban
en AI Overview, hoy estas otras. ¿En cuáles he ganado/perdido visibilidad y qué
URLs están afectadas?" — tanto para el dominio del proyecto como para cada
competidor seleccionado.

No requiere cambios de esquema: reutiliza `manual_ai_results`
(estado autoritativo del dominio del proyecto) y `manual_ai_global_domains`
(URLs y presencia de competidores) ya almacenados por el análisis diario.

Estrategia de fechas: como los análisis no corren a diario (p.ej. Lun/Jue/Sáb),
una fecha exacta "hace 30 días" puede no tener snapshot. Por eso comparamos el
PRIMER análisis disponible dentro de la ventana contra el ÚLTIMO, y devolvemos
las fechas reales usadas para que el frontend las muestre con transparencia.
"""

import logging
import re
from datetime import date, timedelta
from typing import Dict, List, Optional
from database import get_db_connection

logger = logging.getLogger(__name__)


def _normalize_domain(value: Optional[str]) -> str:
    """Normaliza un dominio a comparable: minúsculas, sin esquema, sin www, sin path."""
    if not value:
        return ''
    d = value.strip().lower()
    d = re.sub(r'^https?://', '', d)
    d = re.sub(r'^www\.', '', d)
    d = d.split('/')[0]
    return d


def _domains_match(detected: str, competitor: str) -> bool:
    """True si `detected` (ya normalizado) corresponde al `competitor` (normalizado).

    Acepta igualdad exacta o relación de subdominio en cualquier dirección, de
    forma coherente con cómo el resto del sistema empareja competidores.
    """
    if not detected or not competitor:
        return False
    return (
        detected == competitor
        or detected.endswith('.' + competitor)
        or competitor.endswith('.' + detected)
    )


class _HistoricalMixin:

    @staticmethod
    def get_ai_overview_historical_comparison(project_id: int, days: int = 30) -> Dict:
        """
        Compara la presencia en AI Overview entre el primer y el último análisis
        disponibles dentro de la ventana de `days` días.

        Args:
            project_id: ID del proyecto
            days: Tamaño de la ventana (7 / 30 / 90 ...)

        Returns:
            Dict con:
              - comparison_available: bool (False si no hay 2 fechas que comparar)
              - days, date_range, compared_dates, date_count, project_domain
              - entities: lista (tu dominio + cada competidor) con summary y
                listas gained / lost / maintained (cada item con keyword + URL).
        """
        empty: Dict = {
            'comparison_available': False,
            'days': days,
            'date_range': {'requested_start': '', 'requested_end': ''},
            'compared_dates': {'previous': None, 'current': None},
            'date_count': 0,
            'project_domain': None,
            'entities': [],
        }

        conn = get_db_connection()
        if not conn:
            logger.error(f"get_ai_overview_historical_comparison({project_id}): no DB connection")
            return empty

        try:
            cur = conn.cursor()

            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            empty['date_range'] = {
                'requested_start': str(start_date),
                'requested_end': str(end_date),
            }

            # Proyecto: dominio propio + competidores
            cur.execute("""
                SELECT domain, selected_competitors
                FROM manual_ai_projects
                WHERE id = %s
            """, (project_id,))
            project_row = cur.fetchone()
            if not project_row:
                return empty

            project_domain = project_row['domain']
            competitors = project_row['selected_competitors'] or []
            empty['project_domain'] = project_domain

            # Endpoints: primera y última fecha de análisis dentro de la ventana
            cur.execute("""
                SELECT MIN(analysis_date) AS first_date,
                       MAX(analysis_date) AS last_date,
                       COUNT(DISTINCT analysis_date) AS date_count
                FROM manual_ai_results
                WHERE project_id = %s
                    AND analysis_date >= %s AND analysis_date <= %s
            """, (project_id, start_date, end_date))
            dates_row = cur.fetchone()
            first_date = dates_row['first_date']
            last_date = dates_row['last_date']
            date_count = dates_row['date_count'] or 0

            # Necesitamos dos fechas distintas para comparar
            if not first_date or not last_date or first_date == last_date:
                empty['compared_dates'] = {
                    'previous': str(first_date) if first_date else None,
                    'current': str(last_date) if last_date else None,
                }
                empty['date_count'] = date_count
                return empty

            # Resultados de las dos fechas: estado autoritativo del dominio propio
            cur.execute("""
                SELECT keyword_id, keyword, analysis_date,
                       domain_mentioned, domain_position
                FROM manual_ai_results
                WHERE project_id = %s
                    AND analysis_date IN (%s, %s)
            """, (project_id, first_date, last_date))
            results_rows = cur.fetchall()

            # Dominios globales de las dos fechas: URLs + presencia de competidores
            cur.execute("""
                SELECT keyword_id, analysis_date, detected_domain,
                       domain_position, domain_source_url, is_project_domain
                FROM manual_ai_global_domains
                WHERE project_id = %s
                    AND analysis_date IN (%s, %s)
            """, (project_id, first_date, last_date))
            gd_rows = cur.fetchall()
        finally:
            try:
                conn.close()
            except Exception:
                pass

        fd, ld = str(first_date), str(last_date)

        # keyword_id -> texto de keyword
        kw_text: Dict[int, str] = {}
        for r in results_rows:
            kw_text[r['keyword_id']] = r['keyword']

        # Dominio propio: mención autoritativa (results) por fecha -> {kw_id: position}
        proj_mention: Dict[str, Dict[int, Optional[int]]] = {fd: {}, ld: {}}
        for r in results_rows:
            dstr = str(r['analysis_date'])
            if r['domain_mentioned'] and dstr in proj_mention:
                proj_mention[dstr][r['keyword_id']] = r['domain_position']

        # URL del dominio propio por (fecha, kw_id) desde global_domains (mejor posición)
        proj_url: Dict[tuple, Dict] = {}
        # Competidores normalizados (preservando el original para mostrar)
        comp_list = []
        seen_norm = set()
        for c in competitors:
            cn = _normalize_domain(c)
            if cn and cn not in seen_norm:
                seen_norm.add(cn)
                comp_list.append((cn, c))

        # comp_data[norm][fecha][kw_id] = {'position', 'url'}
        comp_data = {cn: {fd: {}, ld: {}} for cn, _ in comp_list}

        for g in gd_rows:
            dstr = str(g['analysis_date'])
            if dstr not in (fd, ld):
                continue
            det = _normalize_domain(g['detected_domain'])
            kid = g['keyword_id']
            pos = g['domain_position']
            url = g['domain_source_url']

            if g['is_project_domain']:
                key = (dstr, kid)
                existing = proj_url.get(key)
                if existing is None or (
                    pos is not None and (existing['position'] is None or pos < existing['position'])
                ):
                    proj_url[key] = {'url': url, 'position': pos}

            for cn, _orig in comp_list:
                if _domains_match(det, cn):
                    bucket = comp_data[cn][dstr]
                    existing = bucket.get(kid)
                    if existing is None or (
                        pos is not None and (existing['position'] is None or pos < existing['position'])
                    ):
                        bucket[kid] = {'position': pos, 'url': url}

        def _build_entity(label, domain, dtype, prev_map, curr_map, url_lookup) -> Dict:
            prev_ids = set(prev_map.keys())
            curr_ids = set(curr_map.keys())
            gained_ids = curr_ids - prev_ids
            lost_ids = prev_ids - curr_ids
            kept_ids = prev_ids & curr_ids

            gained = [{
                'keyword': kw_text.get(kid, ''),
                'position': curr_map[kid],
                'url': url_lookup(ld, kid),
            } for kid in gained_ids]

            lost = [{
                'keyword': kw_text.get(kid, ''),
                'previous_position': prev_map[kid],
                'previous_url': url_lookup(fd, kid),
            } for kid in lost_ids]

            maintained = []
            for kid in kept_ids:
                pp, cp = prev_map[kid], curr_map[kid]
                delta = (cp - pp) if (pp is not None and cp is not None) else None
                maintained.append({
                    'keyword': kw_text.get(kid, ''),
                    'previous_position': pp,
                    'current_position': cp,
                    'position_delta': delta,  # negativo = mejora (sube en el ranking)
                    'url': url_lookup(ld, kid),
                })

            gained.sort(key=lambda x: (x['position'] is None, x['position'] or 0, x['keyword']))
            lost.sort(key=lambda x: (x['previous_position'] is None, x['previous_position'] or 0, x['keyword']))
            maintained.sort(key=lambda x: (x['current_position'] is None, x['current_position'] or 0, x['keyword']))

            return {
                'type': dtype,
                'domain': domain,
                'label': label,
                'summary': {
                    'previous_count': len(prev_ids),
                    'current_count': len(curr_ids),
                    'gained_count': len(gained_ids),
                    'lost_count': len(lost_ids),
                    'maintained_count': len(kept_ids),
                },
                'gained': gained,
                'lost': lost,
                'maintained': maintained,
            }

        entities: List[Dict] = []

        # Entidad: tu dominio
        entities.append(_build_entity(
            'Your domain', project_domain, 'project',
            proj_mention[fd], proj_mention[ld],
            lambda dstr, kid: (proj_url.get((dstr, kid)) or {}).get('url'),
        ))

        # Entidades: cada competidor
        for cn, orig in comp_list:
            prev_map = {kid: v['position'] for kid, v in comp_data[cn][fd].items()}
            curr_map = {kid: v['position'] for kid, v in comp_data[cn][ld].items()}

            def _make_lookup(_cn):
                def _lookup(dstr, kid):
                    return (comp_data[_cn][dstr].get(kid) or {}).get('url')
                return _lookup

            entities.append(_build_entity(
                orig, orig, 'competitor', prev_map, curr_map, _make_lookup(cn),
            ))

        return {
            'comparison_available': True,
            'days': days,
            'date_range': {
                'requested_start': str(start_date),
                'requested_end': str(end_date),
            },
            'compared_dates': {'previous': fd, 'current': ld},
            'date_count': date_count,
            'project_domain': project_domain,
            'entities': entities,
        }
