# services/ai_analysis.py
import logging
from .utils import urls_match, normalize_search_console_url

logger = logging.getLogger(__name__)

def check_domain_in_references(element_data, normalized_site_url):
    """
    Recorre arrays de referencias (references, sources, links, citations)
    y comprueba si aparece normalized_site_url.
    Devuelve (bool, posición, enlace) o (False, None, None).
    """
    references = (
        element_data.get('references')
        or element_data.get('sources')
        or element_data.get('links')
        or element_data.get('citations')
        or []
    )
    for idx, ref in enumerate(references, start=1):
        if not isinstance(ref, dict):
            continue
        link = (
            ref.get('url')
            or ref.get('link')
            or ref.get('source')
            or ref.get('href')
            or ref.get('source_link')
        )
        if link and urls_match(link, normalized_site_url):
            return True, idx, link
    return False, None, None


def detect_ai_overview_elements(serp_data, site_url_to_check=None):
    """
    Detecta únicamente bloques de AI Overview (ignora featured_snippet)
    y comprueba si nuestro dominio aparece como fuente.
    """
    ai_elements = {
        'has_ai_overview': False,
        'ai_overview_detected': [],
        'total_elements': 0,
        'elements_before_organic': 0,
        'impact_score': 0,
        'domain_is_ai_source': False,
        'domain_ai_source_position': None,
        'domain_ai_source_link': None,
        'debug_info': {}
    }

    if not serp_data:
        logger.warning("serp_data vacío en detect_ai_overview_elements")
        return ai_elements

    # Registro de claves disponibles
    keys = list(serp_data.keys())
    ai_elements['debug_info']['available_keys'] = keys
    logger.info(f"Claves SERP recibidas: {keys}")

    # Solo estos bloques consideramos AI Overview
    ai_overview_keys = [
        'ai_overview', 'ai_overview_first_person_singular',
        'ai_overview_complete', 'ai_overview_inline',
        'generative_ai', 'bard_answer', 'answer_box'
    ]

    normalized_site = None
    if site_url_to_check:
        normalized_site = normalize_search_console_url(site_url_to_check)

    position_counter = 0

    for ai_key in ai_overview_keys:
        element_data = serp_data.get(ai_key)
        if not element_data:
            continue

        logger.info(f"Procesando bloque AI: {ai_key}")

        # ✅ NUEVO: Verificar que el AI Overview tenga contenido real
        current_content_length = 0
        sources_count = 0
        references = []

        if isinstance(element_data, dict):
            # Text blocks
            text_blocks = element_data.get('text_blocks') or []
            for block in text_blocks:
                current_content_length += len(str(block.get('snippet', '')))
            # Campos sueltos
            if current_content_length == 0:
                for field in ['text', 'answer', 'snippet', 'description']:
                    val = element_data.get(field)
                    if isinstance(val, str):
                        current_content_length += len(val)
            # Referencias/fuentes
            references = (
                element_data.get('references')
                or element_data.get('sources')
                or element_data.get('links')
                or element_data.get('citations')
                or []
            )
            sources_count = len(references)

        elif isinstance(element_data, list):
            for item in element_data:
                if isinstance(item, dict):
                    snippet = item.get('text') or item.get('snippet') or ''
                    current_content_length += len(str(snippet))
            sources_count = 0 # Asumiendo que las listas de elementos no tienen un conteo directo de fuentes aquí, o se maneja por elemento si fuera necesario.

        else:
            current_content_length = len(str(element_data))

        # ✅ NUEVO: Solo marcar como AI Overview si tiene contenido O fuentes
        if current_content_length == 0 and sources_count == 0:
            logger.warning(f"AI Overview detectado pero vacío para clave: {ai_key}")
            continue  # Skip este bloque vacío

        # ✅ Solo si llegamos aquí, es un AI Overview válido
        ai_elements['has_ai_overview'] = True

        # Comprobar dominio en referencias
        if normalized_site and isinstance(references, list) and references:
            is_src, pos, link = check_domain_in_references(element_data, normalized_site)
            if is_src:
                ai_elements['domain_is_ai_source'] = True
                ai_elements['domain_ai_source_position'] = pos
                ai_elements['domain_ai_source_link'] = link

        # Añadir al listado de bloques detectados
        ai_elements['ai_overview_detected'].append({
            'type': f'AI Overview ({ai_key})',
            'position': position_counter,
            'content_length': current_content_length,
            'sources_count': sources_count
        })
        ai_elements['impact_score'] += 40
        position_counter += 1

    # Resultado final
    ai_elements['total_elements'] = len(ai_elements['ai_overview_detected'])
    ai_elements['elements_before_organic'] = position_counter
    ai_elements['impact_score'] = min(ai_elements['impact_score'], 100)

    logger.info(f"AI Overview completo: {ai_elements}")
    return ai_elements