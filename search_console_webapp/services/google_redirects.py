# services/google_redirects.py
"""
Manejo centralizado de los enlaces de redirección de Google en SERPs.

Desde julio de 2026 Google reescribe enlaces de resultados como
``google.com/goto?url=<token>`` (y mantiene el formato clásico
``google.com/url?q=<url>``). Si un proveedor SERP (SerpAPI) no resuelve
la redirección, el campo ``link`` llega apuntando a google.com y toda la
detección de dominios produce falsos negativos, además de contaminar las
estadísticas de competidores con "google.com".

Este módulo es la única pieza del código que debe saber de estos enlaces:

- ``is_google_redirect_link``: ¿es un enlace intermedio de Google?
- ``resolve_google_redirect``: intenta recuperar la URL real de destino.
- ``clean_serp_link``: URL lista para usar, o ``None`` si es un redirect
  irresoluble (token opaco). Nunca devuelve un enlace goto.
- ``domain_from_serp_link``: dominio (sin www) del destino real, o ``''``.
- ``scan_serp_payload`` / ``log_redirect_stats``: telemetría sobre una
  respuesta completa de SerpAPI, para detectar regresiones del proveedor.

No depende de Flask ni de la base de datos: es importable desde cualquier
paquete (services, manual_ai, ai_mode_projects, scripts).
"""

import logging
import re
import threading
from typing import Optional
from urllib.parse import parse_qs, unquote, urlparse

logger = logging.getLogger(__name__)

# Hosts tipo google.com, www.google.es, google.co.uk, google.com.mx...
_GOOGLE_HOST_RE = re.compile(r'^(www\.)?google\.[a-z]{2,3}(\.[a-z]{2})?$')

# Paths de redirección conocidos. '/goto' es el nuevo (2026); '/url' e
# '/interstitial' son formatos intermedios que Google ya usaba.
_REDIRECT_PATH_PREFIXES = ('/goto', '/url', '/interstitial')

# Parámetros de query donde Google transporta el destino, por orden de
# preferencia observado ('url' en /goto, 'q'/'url' en /url).
_DESTINATION_PARAMS = ('url', 'q', 'target', 'dest', 'u')

# Algo con pinta de dominio real: "ejemplo.com/pagina", "sub.ejemplo.co.uk"
_DOMAIN_LIKE_RE = re.compile(r'^[a-z0-9][a-z0-9.-]*\.[a-z]{2,}([/?#].*)?$', re.IGNORECASE)

# Throttling de warnings: los crons diarios procesan miles de referencias y
# un proveedor roto inundaría los logs. Avisamos con detalle las primeras
# veces y después solo una de cada _WARN_EVERY.
_WARN_FIRST = 20
_WARN_EVERY = 100
_unresolved_count = 0
_count_lock = threading.Lock()


def is_google_redirect_link(url: str) -> bool:
    """True si la URL es un enlace intermedio de Google (goto/url)."""
    if not url or not isinstance(url, str):
        return False
    candidate = url.strip()
    if not candidate.lower().startswith(('http://', 'https://')):
        candidate = 'https://' + candidate
    try:
        parsed = urlparse(candidate)
    except Exception:
        return False
    host = (parsed.netloc or '').split(':')[0].lower()
    if not _GOOGLE_HOST_RE.match(host):
        return False
    path = (parsed.path or '').rstrip('/').lower()
    return any(path == p or path.startswith(p + '/') for p in _REDIRECT_PATH_PREFIXES)


def _looks_like_destination(value: str) -> bool:
    """¿El valor de un parámetro es una URL/dominio real y no un token opaco?"""
    if not value:
        return False
    lowered = value.lower()
    if lowered.startswith(('http://', 'https://')):
        try:
            host = urlparse(value).netloc.split(':')[0]
        except Exception:
            return False
        return bool(host) and '.' in host and not _GOOGLE_HOST_RE.match(host.lower())
    return bool(_DOMAIN_LIKE_RE.match(value)) and not _GOOGLE_HOST_RE.match(lowered.split('/')[0])


def resolve_google_redirect(url: str) -> Optional[str]:
    """
    Intenta extraer la URL de destino de un enlace de redirección de Google.

    Devuelve la URL absoluta del destino, o ``None`` si el parámetro es un
    token opaco/cifrado que solo Google puede resolver (el caso habitual de
    /goto?url=<hash>).
    """
    if not is_google_redirect_link(url):
        return None
    candidate = url.strip()
    if not candidate.lower().startswith(('http://', 'https://')):
        candidate = 'https://' + candidate
    try:
        query = parse_qs(urlparse(candidate).query)
    except Exception:
        return None

    for param in _DESTINATION_PARAMS:
        for raw_value in query.get(param, []):
            value = raw_value.strip()
            # Doble encoding ocasional: url=https%3A%2F%2F...
            if value.lower().startswith(('http%3a', 'https%3a')):
                value = unquote(value)
            if not _looks_like_destination(value):
                continue
            if not value.lower().startswith(('http://', 'https://')):
                value = 'https://' + value
            return value
    return None


def _note_unresolved(url: str, context: str = '') -> None:
    """Registra un redirect irresoluble con throttling de logs."""
    global _unresolved_count
    with _count_lock:
        _unresolved_count += 1
        count = _unresolved_count
    if count <= _WARN_FIRST or count % _WARN_EVERY == 0:
        suffix = f" (contexto: {context})" if context else ""
        logger.warning(
            f"[GOOGLE GOTO] Enlace de redirección irresoluble #{count}: '{url[:120]}'{suffix}. "
            f"El proveedor SERP está devolviendo enlaces goto sin resolver."
        )
    else:
        logger.debug(f"[GOOGLE GOTO] Enlace irresoluble (#{count}): {url[:120]}")


def clean_serp_link(url: str, context: str = '') -> Optional[str]:
    """
    Devuelve una URL segura para extraer dominios/compararla.

    - URL normal → se devuelve tal cual.
    - Redirect de Google resoluble → URL de destino real.
    - Redirect irresoluble (token opaco) → ``None`` + warning throttled.
      Los llamadores deben tratar ``None`` como "destino desconocido",
      nunca como google.com.
    """
    if not url or not isinstance(url, str):
        return url or None
    if not is_google_redirect_link(url):
        return url
    resolved = resolve_google_redirect(url)
    if resolved:
        logger.debug(f"[GOOGLE GOTO] Redirect resuelto: {url[:80]} -> {resolved[:80]}")
        return resolved
    _note_unresolved(url, context)
    return None


def domain_from_serp_link(url: str, context: str = '') -> str:
    """
    Dominio (lowercase, sin www ni puerto) del destino real de un enlace SERP.
    Devuelve ``''`` si la URL está vacía o es un redirect irresoluble.
    """
    clean = clean_serp_link(url, context)
    if not clean:
        return ''
    candidate = clean.strip()
    if not candidate.lower().startswith(('http://', 'https://')):
        candidate = 'https://' + candidate
    try:
        host = (urlparse(candidate).netloc or '').split(':')[0].lower()
    except Exception:
        return ''
    if host.startswith('www.'):
        host = host[4:]
    return host


def _iter_payload_links(serp_data: dict):
    """Itera (sección, url) sobre los campos de enlace de una respuesta SerpAPI."""
    if not isinstance(serp_data, dict):
        return

    for item in serp_data.get('organic_results') or []:
        if isinstance(item, dict) and item.get('link'):
            yield 'organic_results', item['link']

    ai_overview = serp_data.get('ai_overview') or {}
    if isinstance(ai_overview, dict):
        for key in ('references', 'sources'):
            for ref in ai_overview.get(key) or []:
                if isinstance(ref, dict) and ref.get('link'):
                    yield f'ai_overview.{key}', ref['link']

    for key in ('featured_snippet', 'answer_box'):
        block = serp_data.get(key) or {}
        if isinstance(block, dict) and block.get('link'):
            yield key, block['link']

    for item in serp_data.get('local_results') or []:
        if isinstance(item, dict) and item.get('link'):
            yield 'local_results', item['link']


def scan_serp_payload(serp_data: dict) -> dict:
    """
    Cuenta enlaces de redirección de Google en una respuesta de SerpAPI.

    Returns:
        dict con total de enlaces, redirects detectados, cuántos se pudieron
        resolver y desglose por sección. ``clean=True`` si no hay redirects.
    """
    stats = {'total_links': 0, 'redirects': 0, 'resolved': 0, 'unresolved': 0, 'sections': {}}
    for section, url in _iter_payload_links(serp_data):
        stats['total_links'] += 1
        if not is_google_redirect_link(url):
            continue
        stats['redirects'] += 1
        section_stats = stats['sections'].setdefault(section, {'resolved': 0, 'unresolved': 0})
        if resolve_google_redirect(url):
            stats['resolved'] += 1
            section_stats['resolved'] += 1
        else:
            stats['unresolved'] += 1
            section_stats['unresolved'] += 1
    stats['clean'] = stats['redirects'] == 0
    return stats


def log_redirect_stats(serp_data: dict, context: str = '') -> dict:
    """
    Escanea una respuesta de SerpAPI y deja una alarma en logs si contiene
    enlaces goto (la señal de que el proveedor tiene una regresión).
    Pensado para llamarse en el punto de entrada de cada respuesta SERP.
    """
    stats = scan_serp_payload(serp_data)
    if not stats['clean']:
        suffix = f" | keyword: '{context}'" if context else ''
        logger.warning(
            f"[GOOGLE GOTO] ⚠️ Respuesta SERP con {stats['redirects']} enlace(s) de redirección "
            f"({stats['unresolved']} irresolubles) sobre {stats['total_links']} enlaces. "
            f"Secciones: {stats['sections']}{suffix}"
        )
    return stats
