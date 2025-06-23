# services/utils.py
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

def extract_domain(url_str):
    """
    Versión mejorada y más robusta para extraer dominios
    """
    if not url_str:
        return ''
    try:
        clean_url = url_str.strip().lower()
        if not clean_url.startswith(('http://', 'https://')):
            clean_url = 'https://' + clean_url
        parsed = urlparse(clean_url)
        domain = parsed.netloc
        if ':' in domain:
            domain = domain.split(':')[0]
        if domain.startswith('www.'):
            domain = domain[4:]
        common_subdomains = ['m', 'mobile', 'es', 'en', 'blog', 'shop', 'store']
        parts = domain.split('.')
        if len(parts) > 2 and parts[0] in common_subdomains:
            domain = '.'.join(parts[1:])
        return domain
    except Exception as e:
        logger.error(f"Error extrayendo dominio de '{url_str}': {e}")
        try:
            fallback = url_str.lower().strip()
            fallback = fallback.replace('https://', '').replace('http://', '')
            if fallback.startswith('www.'):
                fallback = fallback[4:]
            if '/' in fallback:
                fallback = fallback.split('/')[0]
            if ':' in fallback:
                fallback = fallback.split(':')[0]
            return fallback
        except:
            return ''

def normalize_search_console_url(sc_url_str):
    """
    Versión mejorada para normalizar URLs de Search Console
    """
    if not sc_url_str:
        return ''
    sc_url_str = sc_url_str.strip().lower()
    if sc_url_str.startswith('sc-domain:'):
        domain = sc_url_str.split(':', 1)[1]
        return domain.strip()
    return extract_domain(sc_url_str)

def urls_match(serp_url_str, sc_prop_url_str):
    """
    Versión mejorada con logging detallado para debugging.
    """
    if not serp_url_str or not sc_prop_url_str:
        logger.debug(f"URLs vacías: serp='{serp_url_str}', sc='{sc_prop_url_str}'")
        return False
    try:
        serp_domain = extract_domain(serp_url_str)
        sc_domain = normalize_search_console_url(sc_prop_url_str)
        logger.info(f"[MATCH DEBUG] Comparando: SERP='{serp_domain}' vs SC='{sc_domain}' (originales: '{serp_url_str}' vs '{sc_prop_url_str}')")
        if not serp_domain or not sc_domain:
            logger.debug(f"Dominios vacíos después de normalización")
            return False
        if serp_domain == sc_domain:
            logger.info(f"✅ MATCH EXACTO: {serp_domain}")
            return True
        if 'hmfertilitycenter.com' in serp_domain.lower() and 'hmfertilitycenter.com' in sc_domain.lower():
            logger.info(f"✅ MATCH ESPECIAL hmfertilitycenter.com")
            return True
        if 'hmfertilitycenter.com' in serp_domain and normalize_search_console_url(sc_prop_url_str) == 'hmfertilitycenter.com':
            logger.info(f"✅ MATCH ESPECIAL BLOG hmfertilitycenter.com")
            return True
        serp_no_www = serp_domain.replace('www.', '')
        sc_no_www = sc_domain.replace('www.', '')
        if serp_no_www == sc_no_www:
            logger.info(f"✅ MATCH SIN WWW: {serp_no_www}")
            return True
        if serp_domain.endswith('.' + sc_domain):
            logger.info(f"✅ MATCH SUBDOMINIO: {serp_domain} ends with .{sc_domain}")
            return True
        if sc_domain.endswith('.' + serp_domain):
            logger.info(f"✅ MATCH SUBDOMINIO INVERSO: {sc_domain} ends with .{serp_domain}")
            return True
        def get_main_domain(domain_val): # Renombrado 'domain' para evitar conflicto de nombre
            parts = domain_val.split('.')
            if len(parts) >= 2:
                if len(parts) >= 3 and parts[-2] in ['co', 'com', 'org', 'net', 'gov']:
                    return '.'.join(parts[-3:])
                return '.'.join(parts[-2:])
            return domain_val
        serp_main = get_main_domain(serp_domain)
        sc_main = get_main_domain(sc_domain)
        if serp_main == sc_main:
            logger.info(f"✅ MATCH DOMINIO PRINCIPAL: {serp_main}")
            return True
        if serp_domain in sc_domain:
            diff = sc_domain.replace(serp_domain, '').strip('.')
            if diff in ['www', ''] or len(diff) <= 3:
                logger.info(f"✅ MATCH CONTENIDO: {serp_domain} en {sc_domain}")
                return True
        if sc_domain in serp_domain:
            diff = serp_domain.replace(sc_domain, '').strip('.')
            if diff in ['www', ''] or len(diff) <= 3:
                logger.info(f"✅ MATCH CONTENIDO INVERSO: {sc_domain} en {serp_domain}")
                return True
        logger.warning(f"❌ NO MATCH: '{serp_domain}' vs '{sc_domain}' - Ningún algoritmo coincidió")
        return False
    except Exception as e:
        logger.error(f"Error en urls_match: {e}", exc_info=True)
        return False