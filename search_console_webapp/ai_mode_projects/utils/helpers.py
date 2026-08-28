"""
Funciones helper y utilidades generales
"""

from datetime import datetime
from urllib.parse import urlparse
import re

from services.google_redirects import clean_serp_link


def now_utc_iso() -> str:
    """
    Retorna timestamp UTC en formato ISO
    
    Returns:
        String con timestamp UTC ISO
    """
    return datetime.utcnow().isoformat() + 'Z'


def extract_domain_from_url(url: str) -> str:
    """
    Extraer el dominio de una URL completa, eliminando protocolo y path
    
    Args:
        url: URL completa o dominio
        
    Returns:
        Dominio limpio
        
    Examples:
        'https://www.example.com/page' -> 'example.com'
        'http://subdomain.example.com' -> 'subdomain.example.com'
    """
    if not url or not isinstance(url, str):
        return ''

    # Resolver redirects google.com/goto; si el destino es irrecuperable,
    # el dominio es desconocido (nunca debe contarse como google.com).
    url = clean_serp_link(url)
    if not url:
        return ''

    url = url.strip().lower()
    
    # Si no tiene protocolo, añadir temporalmente para parsing
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split('/')[0]
        
        # Remover www.
        domain = re.sub(r'^www\.', '', domain)
        
        # Remover puerto si existe
        domain = domain.split(':')[0]
        
        return domain
    except Exception:
        return url.replace('https://', '').replace('http://', '').split('/')[0]

