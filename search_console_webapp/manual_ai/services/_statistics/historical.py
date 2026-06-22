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


def _keep_best(bucket: Dict[int, Dict], keyword_id: int, position, url) -> None:
    """Guarda en bucket[keyword_id] la MEJOR (menor) posición vista para esa
    keyword en una fecha, junto a su URL. Una keyword puede aparecer varias
    veces en global_domains; nos quedamos con la cita mejor posicionada."""
    existing = bucket.get(keyword_id)
    if existing is None or (
        position is not None and (existing['position'] is None or position < existing['position'])
    ):
        bucket[keyword_id] = {'position': position, 'url': url}


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

        # Competidores normalizados (preservando el original para mostrar)
        comp_list = []
        seen_norm = set()
        for c in competitors:
            cn = _normalize_domain(c)
            if cn and cn not in seen_norm:
                seen_norm.add(cn)
                comp_list.append((cn, c))

        # Todas las entidades usan la misma forma: {fecha: {kw_id: {position, url}}}.
        # Dominio propio (URLs) y competidores salen de global_domains.
        proj_url = {fd: {}, ld: {}}
        comp_data = {cn: {fd: {}, ld: {}} for cn, _ in comp_list}

        for g in gd_rows:
            dstr = str(g['analysis_date'])
            if dstr not in (fd, ld):
                continue
            det = _normalize_domain(g['detected_domain'])
            kid, pos, url = g['keyword_id'], g['domain_position'], g['domain_source_url']

            if g['is_project_domain']:
                _keep_best(proj_url[dstr], kid, pos, url)

            for cn, _orig in comp_list:
                if _domains_match(det, cn):
                    _keep_best(comp_data[cn][dstr], kid, pos, url)

        # Dominio propio: pertenencia y posición AUTORITATIVAS desde results
        # (domain_mentioned); la URL se toma de global_domains (is_project_domain).
        proj_data = {fd: {}, ld: {}}
        for r in results_rows:
            dstr = str(r['analysis_date'])
            if r['domain_mentioned'] and dstr in proj_data:
                kid = r['keyword_id']
                proj_data[dstr][kid] = {
                    'position': r['domain_position'],
                    'url': (proj_url[dstr].get(kid) or {}).get('url'),
                }

        def _build_entity(label, domain, dtype, prev_map, curr_map) -> Dict:
            """prev_map / curr_map: {kw_id: {'position', 'url'}} en cada fecha."""
            prev_ids = set(prev_map)
            curr_ids = set(curr_map)
            gained_ids = curr_ids - prev_ids
            lost_ids = prev_ids - curr_ids
            kept_ids = prev_ids & curr_ids

            gained = [{
                'keyword': kw_text.get(kid, ''),
                'position': curr_map[kid]['position'],
                'url': curr_map[kid]['url'],
            } for kid in gained_ids]

            lost = [{
                'keyword': kw_text.get(kid, ''),
                'previous_position': prev_map[kid]['position'],
                'previous_url': prev_map[kid]['url'],
            } for kid in lost_ids]

            maintained = []
            for kid in kept_ids:
                pp, cp = prev_map[kid]['position'], curr_map[kid]['position']
                delta = (cp - pp) if (pp is not None and cp is not None) else None
                maintained.append({
                    'keyword': kw_text.get(kid, ''),
                    'previous_position': pp,
                    'current_position': cp,
                    'position_delta': delta,  # negativo = mejora (sube en el ranking)
                    'url': curr_map[kid]['url'],
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

        entities: List[Dict] = [
            _build_entity('Your domain', project_domain, 'project', proj_data[fd], proj_data[ld])
        ]
        for cn, orig in comp_list:
            entities.append(
                _build_entity(orig, orig, 'competitor', comp_data[cn][fd], comp_data[cn][ld])
            )

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
