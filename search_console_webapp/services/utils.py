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
    Versión mejorada y más robusta para matching de URLs, especialmente importante
    para detectar el dominio del usuario en fuentes de AI Overview.
    """
    if not serp_url_str or not sc_prop_url_str:
        logger.debug(f"[URL MATCH] URLs vacías: serp='{serp_url_str}', sc='{sc_prop_url_str}'")
        return False
    
    try:
        # Extraer dominios de ambas URLs
        serp_domain = extract_domain(serp_url_str)
        sc_domain = normalize_search_console_url(sc_prop_url_str)
        
        logger.debug(f"[URL MATCH] Comparando: SERP='{serp_domain}' vs SC='{sc_domain}' (originales: '{serp_url_str}' vs '{sc_prop_url_str}')")
        
        if not serp_domain or not sc_domain:
            logger.debug(f"[URL MATCH] Dominios vacíos después de normalización")
            return False

        # ✅ MEJORADO: Múltiples estrategias de matching para AI Overview
        
        # 1. Match exacto (más común)
        if serp_domain == sc_domain:
            logger.info(f"[URL MATCH] ✅ MATCH EXACTO: {serp_domain}")
            return True

        # 2. Match sin www (muy común en AI Overview sources)
        serp_no_www = serp_domain.replace('www.', '')
        sc_no_www = sc_domain.replace('www.', '')
        if serp_no_www == sc_no_www:
            logger.info(f"[URL MATCH] ✅ MATCH SIN WWW: {serp_no_www}")
            return True

        # 3. Match de subdominios (importante para blogs, tiendas, etc.)
        if serp_domain.endswith('.' + sc_domain):
            logger.info(f"[URL MATCH] ✅ MATCH SUBDOMINIO: {serp_domain} ends with .{sc_domain}")
            return True
        if sc_domain.endswith('.' + serp_domain):
            logger.info(f"[URL MATCH] ✅ MATCH SUBDOMINIO INVERSO: {sc_domain} ends with .{serp_domain}")
            return True

        # 4. ✅ NUEVO: Match de dominio principal (muy importante para AI Overview)
        def get_main_domain(domain_val):
            """Extraer el dominio principal (ej: blog.example.com -> example.com)"""
            parts = domain_val.split('.')
            if len(parts) >= 2:
                # Manejar casos como example.co.uk, example.com.mx, etc.
                if len(parts) >= 3 and parts[-2] in ['co', 'com', 'org', 'net', 'gov']:
                    return '.'.join(parts[-3:])
                return '.'.join(parts[-2:])
            return domain_val

        serp_main = get_main_domain(serp_domain)
        sc_main = get_main_domain(sc_domain)
        
        if serp_main == sc_main:
            logger.info(f"[URL MATCH] ✅ MATCH DOMINIO PRINCIPAL: {serp_main}")
            return True

        # 5. ✅ NUEVO: Match parcial para casos especiales
        if serp_domain in sc_domain:
            diff = sc_domain.replace(serp_domain, '').strip('.')
            if diff in ['www', ''] or len(diff) <= 3:
                logger.info(f"[URL MATCH] ✅ MATCH CONTENIDO: {serp_domain} en {sc_domain}")
                return True

        if sc_domain in serp_domain:
            diff = serp_domain.replace(sc_domain, '').strip('.')
            if diff in ['www', ''] or len(diff) <= 3:
                logger.info(f"[URL MATCH] ✅ MATCH CONTENIDO INVERSO: {sc_domain} en {serp_domain}")
                return True

        # 6. ✅ NUEVO: Casos especiales para dominios conocidos problemáticos
        # Agregar lógica específica para dominios que sabemos pueden tener problemas
        special_cases = {
            'hmfertilitycenter.com': ['hmfertilitycenter.com', 'blog.hmfertilitycenter.com', 'www.hmfertilitycenter.com']
        }
        
        for main_domain, variants in special_cases.items():
            if any(variant in serp_domain for variant in variants) and any(variant in sc_domain for variant in variants):
                logger.info(f"[URL MATCH] ✅ MATCH ESPECIAL: {main_domain}")
                return True

        # 7. ✅ NUEVO: Match para dominios de AI Overview que pueden venir con tracking params
        # AI Overview a veces incluye parámetros de tracking que debemos ignorar
        if '?' in serp_url_str:
            clean_serp_url = serp_url_str.split('?')[0]
            clean_serp_domain = extract_domain(clean_serp_url)
            if clean_serp_domain and clean_serp_domain == sc_domain:
                logger.info(f"[URL MATCH] ✅ MATCH SIN TRACKING: {clean_serp_domain}")
                return True

        # Si llegamos aquí, no hay match
        logger.debug(f"[URL MATCH] ❌ NO MATCH: '{serp_domain}' vs '{sc_domain}' - Ningún algoritmo coincidió")
        return False
        
    except Exception as e:
        logger.error(f"[URL MATCH] Error en urls_match: {e}", exc_info=True)
        return False