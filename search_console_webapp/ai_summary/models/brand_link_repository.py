"""
Repositorio para la tabla ai_brand_links (marcas que agrupan proyectos
de Manual AI, AI Mode y LLM Monitoring bajo una misma entidad).
"""

import logging
from typing import Dict, List, Optional

from database import db_conn
from services.utils import normalize_search_console_url

logger = logging.getLogger(__name__)

BRAND_LINK_FIELDS = """
    id, user_id, brand_name, brand_domain,
    manual_ai_project_id, ai_mode_project_id, llm_project_id,
    created_at, updated_at
"""

# Longitud mínima del slug para el matching difuso de AI Mode: por debajo,
# la contención por prefijo produce falsos positivos casi seguros
# (p.ej. brand_name "Sun" ⊂ "samsung").
MIN_FUZZY_SLUG_LEN = 4


def _row_to_brand(row) -> Dict:
    return {
        'id': row['id'],
        'user_id': row['user_id'],
        'brand_name': row['brand_name'],
        'brand_domain': row['brand_domain'],
        'manual_ai_project_id': row['manual_ai_project_id'],
        'ai_mode_project_id': row['ai_mode_project_id'],
        'llm_project_id': row['llm_project_id'],
        'created_at': row['created_at'].isoformat() if row['created_at'] else None,
        'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None,
    }


class BrandLinkRepository:
    """CRUD de vínculos de marca entre los tres módulos de IA"""

    @staticmethod
    def get_user_brands(user_id: int) -> List[Dict]:
        with db_conn() as conn:
            if not conn:
                return []
            cur = conn.cursor()
            cur.execute(f"""
                SELECT {BRAND_LINK_FIELDS}
                FROM ai_brand_links
                WHERE user_id = %s
                ORDER BY brand_name ASC
            """, (user_id,))
            return [_row_to_brand(r) for r in cur.fetchall()]

    @staticmethod
    def get_brand(brand_id: int, user_id: int) -> Optional[Dict]:
        with db_conn() as conn:
            if not conn:
                return None
            cur = conn.cursor()
            cur.execute(f"""
                SELECT {BRAND_LINK_FIELDS}
                FROM ai_brand_links
                WHERE id = %s AND user_id = %s
            """, (brand_id, user_id))
            row = cur.fetchone()
            return _row_to_brand(row) if row else None

    @staticmethod
    def create_brand(user_id: int, brand_name: str, brand_domain: str,
                     manual_ai_project_id: Optional[int] = None,
                     ai_mode_project_id: Optional[int] = None,
                     llm_project_id: Optional[int] = None) -> Dict:
        brand_domain = normalize_search_console_url(brand_domain)
        with db_conn() as conn:
            if not conn:
                return {'success': False, 'error': 'Database connection failed'}
            try:
                cur = conn.cursor()
                cur.execute(f"""
                    INSERT INTO ai_brand_links
                        (user_id, brand_name, brand_domain,
                         manual_ai_project_id, ai_mode_project_id, llm_project_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING {BRAND_LINK_FIELDS}
                """, (user_id, brand_name.strip(), brand_domain,
                      manual_ai_project_id, ai_mode_project_id, llm_project_id))
                row = cur.fetchone()
                conn.commit()
                return {'success': True, 'brand': _row_to_brand(row)}
            except Exception as e:
                conn.rollback()
                if 'unique' in str(e).lower():
                    return {'success': False, 'error': f'A brand for "{brand_domain}" already exists'}
                # No exponer detalles internos de BD al cliente (constraint
                # names, esquema): log completo aquí, mensaje genérico fuera.
                logger.error(f"Error creating brand link for user {user_id}: {e}")
                return {'success': False, 'error': 'Could not create the brand'}

    @staticmethod
    def delete_brand(brand_id: int, user_id: int) -> bool:
        with db_conn() as conn:
            if not conn:
                return False
            try:
                cur = conn.cursor()
                cur.execute("""
                    DELETE FROM ai_brand_links
                    WHERE id = %s AND user_id = %s
                """, (brand_id, user_id))
                deleted = cur.rowcount > 0
                conn.commit()
                return deleted
            except Exception as e:
                conn.rollback()
                logger.error(f"Error deleting brand link {brand_id}: {e}")
                return False

    # ------------------------------------------------------------------
    # Proyectos por módulo (para el formulario de vinculación y sugerencias)
    # ------------------------------------------------------------------

    @staticmethod
    def get_user_module_projects(user_id: int) -> Dict[str, List[Dict]]:
        """
        Proyectos del usuario en cada módulo de IA, con su identidad
        (dominio o marca) para poder sugerir vínculos.
        """
        projects = {'manual_ai': [], 'ai_mode': [], 'llm': []}
        with db_conn() as conn:
            if not conn:
                return projects
            try:
                cur = conn.cursor()

                cur.execute("""
                    SELECT id, name, domain AS identity, country_code
                    FROM manual_ai_projects
                    WHERE user_id = %s
                    ORDER BY name
                """, (user_id,))
                projects['manual_ai'] = [dict(r) for r in cur.fetchall()]

                cur.execute("""
                    SELECT id, name, brand_name AS identity, country_code
                    FROM ai_mode_projects
                    WHERE user_id = %s
                    ORDER BY name
                """, (user_id,))
                projects['ai_mode'] = [dict(r) for r in cur.fetchall()]

                cur.execute("""
                    SELECT id, name, brand_domain AS identity, country_code
                    FROM llm_monitoring_projects
                    WHERE user_id = %s AND is_active = TRUE
                    ORDER BY name
                """, (user_id,))
                projects['llm'] = [dict(r) for r in cur.fetchall()]

                return projects
            except Exception as e:
                logger.error(f"Error fetching module projects for user {user_id}: {e}")
                return projects

    @staticmethod
    def verify_project_ownership(user_id: int, module: str, project_id: int) -> bool:
        """Verificar que un proyecto pertenece al usuario antes de vincularlo (anti-IDOR)."""
        tables = {
            'manual_ai': 'manual_ai_projects',
            'ai_mode': 'ai_mode_projects',
            'llm': 'llm_monitoring_projects',
        }
        table = tables.get(module)
        if not table or not project_id:
            return False
        with db_conn() as conn:
            if not conn:
                return False
            cur = conn.cursor()
            cur.execute(f"SELECT 1 FROM {table} WHERE id = %s AND user_id = %s", (project_id, user_id))
            return cur.fetchone() is not None

    # ------------------------------------------------------------------
    # Sugerencias de vinculación automática
    # ------------------------------------------------------------------

    @staticmethod
    def suggest_links(user_id: int, existing_brands: List[Dict],
                      projects: Optional[Dict[str, List[Dict]]] = None) -> List[Dict]:
        """
        Sugerir marcas agrupando proyectos no vinculados de los tres módulos
        por dominio normalizado. AI Mode guarda un brand_name libre, así que
        su matching es difuso (slug del nombre contra la primera etiqueta del
        dominio, con longitud mínima) y siempre requiere confirmación.

        `projects` permite pasar el resultado de get_user_module_projects()
        ya cargado por el caller para no repetir las 3 queries.
        """
        if projects is None:
            projects = BrandLinkRepository.get_user_module_projects(user_id)

        linked = {
            'manual_ai': {b['manual_ai_project_id'] for b in existing_brands if b['manual_ai_project_id']},
            'ai_mode': {b['ai_mode_project_id'] for b in existing_brands if b['ai_mode_project_id']},
            'llm': {b['llm_project_id'] for b in existing_brands if b['llm_project_id']},
        }
        existing_domains = {b['brand_domain'] for b in existing_brands}

        def slug(value: str) -> str:
            return ''.join(c for c in (value or '').lower() if c.isalnum())

        # Agrupar por dominio normalizado (manual_ai y llm tienen dominio real)
        groups: Dict[str, Dict] = {}
        for module in ('manual_ai', 'llm'):
            for p in projects[module]:
                if p['id'] in linked[module]:
                    continue
                domain = normalize_search_console_url(p.get('identity') or '')
                if not domain or domain in existing_domains:
                    continue
                group = groups.setdefault(domain, {
                    'brand_domain': domain,
                    'brand_name': domain.split('.')[0].capitalize(),
                    'manual_ai_project_id': None,
                    'ai_mode_project_id': None,
                    'llm_project_id': None,
                    'matched_projects': [],
                })
                key = 'manual_ai_project_id' if module == 'manual_ai' else 'llm_project_id'
                if group[key] is None:
                    group[key] = p['id']
                    group['matched_projects'].append({'module': module, 'id': p['id'], 'name': p['name']})

        # AI Mode: matching difuso de brand_name contra la primera etiqueta del
        # dominio. Exigimos slug de longitud mínima e igualdad o prefijo (no
        # contención bidireccional) para evitar uniones absurdas tipo
        # "Sun" ⊂ "samsung".
        for p in projects['ai_mode']:
            if p['id'] in linked['ai_mode']:
                continue
            identity = p.get('identity') or ''
            name_slug = slug(identity.split('.')[0] if '.' in identity else identity)
            if len(name_slug) < MIN_FUZZY_SLUG_LEN:
                continue
            for domain, group in groups.items():
                if group['ai_mode_project_id'] is not None:
                    continue
                domain_slug = slug(domain.split('.')[0])
                if len(domain_slug) < MIN_FUZZY_SLUG_LEN:
                    continue
                if (name_slug == domain_slug
                        or domain_slug.startswith(name_slug)
                        or name_slug.startswith(domain_slug)):
                    group['ai_mode_project_id'] = p['id']
                    group['matched_projects'].append({'module': 'ai_mode', 'id': p['id'], 'name': p['name']})
                    break

        # Solo sugerimos grupos con al menos un módulo
        return sorted(groups.values(), key=lambda g: -len(g['matched_projects']))
