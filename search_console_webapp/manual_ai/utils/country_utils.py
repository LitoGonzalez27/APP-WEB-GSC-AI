"""
Utilidades para conversión de códigos de país
"""

import logging

logger = logging.getLogger(__name__)


def convert_iso_to_internal_country(country_code: str) -> str:
    """
    Convertir códigos ISO-2 o internos a código interno (keys de COUNTRY_MAPPING).

    Acepta:
    - Códigos internos ya válidos como 'esp', 'usa', 'gbr' (retorna tal cual)
    - Códigos ISO-2 como 'ES', 'US', 'GB' (mapea a interno)
    Si no es posible mapear, retorna 'esp' como fallback seguro (con warning).
    
    Args:
        country_code: Código de país ISO-2 o interno
        
    Returns:
        Código interno de país
    """
    try:
        if not country_code:
            return 'esp'

        code_str = str(country_code).strip()
        if not code_str:
            return 'esp'

        code_upper = code_str.upper()
        code_lower = code_str.lower()

        # Si ya es un código interno conocido, devolverlo
        try:
            from services.country_config import get_country_config
            if get_country_config(code_lower):
                return code_lower
        except Exception:
            # Si por algún motivo falla la importación, seguimos con el mapeo ISO2
            pass

        iso2_to_internal = {
            # Europa occidental y principales
            'ES': 'esp', 'US': 'usa', 'GB': 'gbr', 'FR': 'fra', 'DE': 'deu', 'IT': 'ita',
            'PT': 'prt', 'NL': 'nld', 'BE': 'bel', 'CH': 'che', 'AT': 'aut', 'SE': 'swe',
            'NO': 'nor', 'DK': 'dnk', 'FI': 'fin', 'IE': 'irl', 'LU': 'lux', 'LT': 'ltu',
            'LV': 'lva', 'EE': 'est', 'PL': 'pol', 'CZ': 'cze', 'HU': 'hun', 'RO': 'rou',
            'BG': 'bgr', 'GR': 'grc', 'HR': 'hrv', 'SI': 'svn', 'SK': 'svk',
            'CY': 'cyp', 'AL': 'alb', 'AD': 'and', 'AM': 'arm', 'AZ': 'aze', 'BY': 'blr',
            'BA': 'bih', 'GE': 'geo', 'IS': 'isl', 'KZ': 'kaz', 'XK': 'xkx', 'LI': 'lie',
            'MK': 'mkd', 'MT': 'mlt', 'MD': 'mda',
            'MC': 'mco', 'ME': 'mne', 'SM': 'smr', 'RS': 'srb', 'UA': 'ukr', 'VA': 'vat',

            # América
            'CA': 'can', 'MX': 'mex', 'AR': 'arg', 'CO': 'col', 'CL': 'chl', 'PE': 'per',
            'VE': 'ven', 'EC': 'ecu', 'UY': 'ury', 'PY': 'pry', 'SV': 'slv', 'PA': 'pan',
            'NI': 'nic', 'PR': 'pri', 'BR': 'bra', 'BZ': 'blz', 'GY': 'guy', 'SR': 'sur',
            'DO': 'dom', 'BO': 'bol', 'GT': 'gtm', 'CR': 'cri', 'CU': 'cub', 'HN': 'hnd',

            # Oriente Medio / Asia / Oceanía
            'TR': 'tur', 'IL': 'isr', 'AE': 'are', 'SA': 'sau', 'IN': 'ind', 'CN': 'chn',
            'JP': 'jpn', 'AU': 'aus', 'ID': 'idn', 'KR': 'kor', 'SG': 'sgp',

            # África
            'ZA': 'zaf',
        }

        mapped = iso2_to_internal.get(code_upper)
        if mapped:
            try:
                from services.country_config import get_country_config as _gcc
                if _gcc(mapped):
                    return mapped
            except Exception:
                return mapped

        # Fallback seguro
        logger.warning(f"[Manual AI] Country code '{country_code}' no mapeado; usando 'esp' por defecto")
        return 'esp'

    except Exception:
        return 'esp'

