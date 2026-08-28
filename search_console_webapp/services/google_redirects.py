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
import os
import re
import threading
from collections import OrderedDict
from typing import Optional
from urllib.parse import parse_qs, unquote, urljoin, urlparse

logger = logging.getLogger(__name__)

# Hosts tipo google.com, www.google.es, google.co.uk, google.com.mx...
_GOOGLE_HOST_RE = re.compile(r'^(www\.)?google\.[a-z]{2,3}(\.[a-z]{2})?$')

# Paths de redirección conocidos. '/goto' es el nuevo (2026); '/url' e
# '/interstitial' son formatos intermedios que Google ya usaba.
_REDIRECT_PATH_PREFIXES = ('/goto', '/url', '/interstitial')

# Parámetros de query donde Google transporta el destino, por orden de
# preferencia observado ('url' en /goto, 'q'/'url' en /url).
_DESTINATION_PARAMS = ('url', 'q', 'target', 'dest', 'u')

# Algo con pinta de dominio real: "ejemplo.com/pagina", "sub.ejemplo.co.uk".
# Solo minúsculas en el host: los dominios reales que Google emite en el
# parámetro van en lowercase, mientras que un token opaco con un punto
# casual ("AbC12.xYz") suele mezclar mayúsculas — mejor descartarlo que
# fabricar un dominio inexistente en los rankings.
_DOMAIN_LIKE_RE = re.compile(r'^[a-z0-9][a-z0-9.-]*\.[a-z]{2,}([/?#].*)?$')

# Parámetros de tracking que Google añade DETRÁS del destino en /url
# (q=<destino>&sa=...&ved=...). Sirven para no truncar un destino sin
# codificar en su primer '&' real.
_GOOGLE_TRACKING_PARAM_RE = re.compile(r'&(sa|ved|usg|source|opi|rct|cd|cad|ei|sqi|bvm)=')

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
        raw_query = urlparse(candidate).query
        query = parse_qs(raw_query)
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
            # Un destino SIN codificar con sus propios parámetros
            # (q=https://x.com/p?a=1&b=2&sa=U) queda partido por parse_qs en
            # el primer '&'. Recuperar el valor completo del query crudo y
            # cortar solo ante los parámetros de tracking de Google.
            if value.lower().startswith(('http://', 'https://')) and '?' in value:
                start = raw_query.find(f'{param}={raw_value}')
                if start != -1:
                    full_value = raw_query[start + len(param) + 1:]
                    tracking = _GOOGLE_TRACKING_PARAM_RE.search(full_value)
                    value = (full_value[:tracking.start()] if tracking else full_value).strip()
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

    # Respuestas de Google AI Mode: {text_blocks, references, inline_images}
    # con las referencias directamente en la raíz del payload.
    for ref in serp_data.get('references') or []:
        if isinstance(ref, dict) and ref.get('link'):
            yield 'references', ref['link']

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


# ---------------------------------------------------------------------------
# Resolución activa: HTTP + metadata del payload
# ---------------------------------------------------------------------------
# El token de /goto?url=CAES... es opaco, pero el endpoint responde un 302
# con la URL real en el header Location sin cookies ni JS (verificado
# 2026-08-28 con enlaces reales de producción). Eso permite recuperar la URL
# completa en vez de descartar la referencia. Si la petición HTTP fallara,
# el propio payload de SerpAPI trae la fuente visible en la SERP
# (``source: 'esic.edu'`` o ``source_icon: '...faviconV2?url=https://...'``),
# suficiente para no perder el dominio en rankings y detección de marca.

_HTTP_RESOLVE_HOPS = 3
_HTTP_CACHE_MAX = 5000
_http_cache: 'OrderedDict[str, Optional[str]]' = OrderedDict()
_http_cache_lock = threading.Lock()

_BROWSER_UA = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36'
)

_http_session = None
_http_session_lock = threading.Lock()

# Hosts de Google que en un Location intermedio significan "bloqueado"
# (pantalla de consentimiento / sorry), no un destino real.
_GOOGLE_BLOCK_HOST_RE = re.compile(r'(^|\.)(consent|sorry)\.google\.[a-z.]+$')


def _get_http_session():
    """Sesión requests compartida (keep-alive) para resolver redirects."""
    global _http_session
    with _http_session_lock:
        if _http_session is None:
            import requests
            session = requests.Session()
            session.headers['User-Agent'] = _BROWSER_UA
            _http_session = session
        return _http_session


def _http_cache_get(url: str):
    with _http_cache_lock:
        if url in _http_cache:
            _http_cache.move_to_end(url)
            return True, _http_cache[url]
    return False, None


def _http_cache_set(url: str, resolved: Optional[str]) -> None:
    with _http_cache_lock:
        _http_cache[url] = resolved
        _http_cache.move_to_end(url)
        while len(_http_cache) > _HTTP_CACHE_MAX:
            _http_cache.popitem(last=False)


def _clear_http_cache() -> None:
    """Solo para tests."""
    with _http_cache_lock:
        _http_cache.clear()


def _is_acceptable_destination(url: str) -> bool:
    """El Location final debe ser una URL real fuera de google.*."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    host = (parsed.netloc or '').split(':')[0].lower()
    if not host or '.' not in host:
        return False
    return not _GOOGLE_HOST_RE.match(host)


def resolve_redirect_via_http(url: str, context: str = '') -> Optional[str]:
    """
    Sigue el redirect de Google por HTTP (sin descargar el destino) y
    devuelve la URL real del header Location, o ``None`` si no se pudo.

    - No sigue redirects automáticamente: lee ``Location`` hop a hop (máx.
      ``_HTTP_RESOLVE_HOPS``) para poder decodificar Locations que sean a su
      vez redirects de Google (goto → /url?q=...).
    - Cachea aciertos y fallos (LRU) para no repetir peticiones: los mismos
      tokens aparecen en muchas keywords del mismo cron.
    - Ante 429/403 reintenta una vez a través de ``SCANNER_PROXY_URL`` si
      está configurado (misma salida limpia que usa el Agent Scanner).
    - Desactivable con ``GOTO_HTTP_RESOLUTION_ENABLED=false``.
    """
    if os.getenv('GOTO_HTTP_RESOLUTION_ENABLED', 'true').strip().lower() == 'false':
        return None
    if not is_google_redirect_link(url):
        return None

    hit, cached = _http_cache_get(url)
    if hit:
        return cached

    timeout = (3.05, float(os.getenv('GOTO_HTTP_TIMEOUT_SECONDS', '6')))
    session = _get_http_session()
    proxy_url = os.getenv('SCANNER_PROXY_URL', '').strip()
    proxies_used = None

    resolved: Optional[str] = None
    current = url if url.lower().startswith(('http://', 'https://')) else 'https://' + url
    try:
        for _hop in range(_HTTP_RESOLVE_HOPS):
            response = session.get(
                current, allow_redirects=False, timeout=timeout, proxies=proxies_used
            )
            status = response.status_code
            if status in (429, 403) and proxy_url and proxies_used is None:
                # Reintento único por el proxy de salida limpia.
                proxies_used = {'http': proxy_url, 'https': proxy_url}
                continue
            if status not in (301, 302, 303, 307, 308):
                break
            location = (response.headers.get('Location') or '').strip()
            if not location:
                break
            location = urljoin(current, location)
            host = (urlparse(location).netloc or '').split(':')[0].lower()
            if _GOOGLE_BLOCK_HOST_RE.match(host):
                break  # consent/sorry: bloqueados, no hay destino real
            if is_google_redirect_link(location):
                decoded = resolve_google_redirect(location)
                if decoded:
                    resolved = decoded
                    break
                current = location  # otro redirect opaco: seguir el siguiente hop
                continue
            if _is_acceptable_destination(location):
                resolved = location
            break
    except Exception as e:
        logger.debug(f"[GOOGLE GOTO] Resolución HTTP fallida para '{url[:100]}': {e}")

    _http_cache_set(url, resolved)
    if resolved:
        logger.debug(f"[GOOGLE GOTO] Resuelto por HTTP: {url[:80]} -> {resolved[:80]}")
    return resolved


def _domain_from_reference_metadata(ref: dict) -> str:
    """
    Último recurso: dominio real de una referencia cuyo ``link`` es un goto
    irresoluble, a partir de la metadata que SerpAPI incluye en la propia
    referencia (la fuente visible en la SERP).

    - ``source``: a veces es directamente el dominio ('esic.edu'); otras es
      el nombre de la marca ('ESIC University') y no sirve.
    - ``source_icon`` / ``thumbnail``: URLs faviconV2 de gstatic con el
      dominio real embebido en el parámetro ``url=``.
    """
    if not isinstance(ref, dict):
        return ''

    source = ref.get('source')
    if isinstance(source, str):
        candidate = source.strip().lower()
        if _DOMAIN_LIKE_RE.match(candidate) and not _GOOGLE_HOST_RE.match(candidate.split('/')[0]):
            host = candidate.split('/')[0].split('?')[0]
            return host[4:] if host.startswith('www.') else host

    for key in ('source_icon', 'thumbnail'):
        value = ref.get(key)
        if not isinstance(value, str) or 'url=' not in value:
            continue
        try:
            embedded = parse_qs(urlparse(value).query).get('url', [])
        except Exception:
            continue
        for raw in embedded:
            candidate = raw.strip()
            if not candidate.lower().startswith(('http://', 'https://')):
                continue
            try:
                host = (urlparse(candidate).netloc or '').split(':')[0].lower()
            except Exception:
                continue
            if not host or '.' not in host:
                continue
            if _GOOGLE_HOST_RE.match(host) or host.endswith('.gstatic.com'):
                continue
            return host[4:] if host.startswith('www.') else host
    return ''


def _iter_link_dicts(node, depth: int = 0):
    """Itera todos los dicts (a cualquier profundidad) que tengan un 'link' str."""
    if depth > 15:
        return
    if isinstance(node, dict):
        if isinstance(node.get('link'), str):
            yield node
        for value in node.values():
            yield from _iter_link_dicts(value, depth + 1)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_link_dicts(item, depth + 1)


def resolve_payload_redirects(serp_data: dict, context: str = '') -> dict:
    """
    Sustituye IN PLACE los enlaces goto de una respuesta SerpAPI por sus
    destinos reales, para que todo lo que se almacene y procese después vea
    URLs fidedignas. Cadena de recuperación, de más a menos precisa:

    1. Token descifrable en el propio enlace (sin red).
    2. Redirect HTTP: Google responde 302 con la URL real en Location.
    3. Metadata de la referencia (source/source_icon): recupera el dominio;
       el link queda como ``https://<dominio>/`` y se marca
       ``google_goto_domain_only`` para que la UI pueda matizarlo.

    El enlace original se conserva en ``google_goto_original``. Solo si las
    tres capas fallan el link queda intacto (y los extractores de dominio lo
    excluirán en vez de atribuirlo a google.com).

    Returns:
        dict: {'redirects', 'via_token', 'via_http', 'via_metadata', 'unresolved'}
    """
    stats = {'redirects': 0, 'via_token': 0, 'via_http': 0, 'via_metadata': 0, 'unresolved': 0}
    if not isinstance(serp_data, dict):
        return stats

    for ref in _iter_link_dicts(serp_data):
        original = ref['link']
        if not is_google_redirect_link(original):
            continue
        stats['redirects'] += 1

        resolved = resolve_google_redirect(original)
        if resolved:
            stats['via_token'] += 1
        else:
            resolved = resolve_redirect_via_http(original, context)
            if resolved:
                stats['via_http'] += 1
            else:
                domain = _domain_from_reference_metadata(ref)
                if domain:
                    resolved = f'https://{domain}/'
                    ref['google_goto_domain_only'] = True
                    stats['via_metadata'] += 1

        if resolved:
            ref.setdefault('google_goto_original', original)
            ref['link'] = resolved
        else:
            stats['unresolved'] += 1
            _note_unresolved(original, context or 'resolve_payload_redirects')

    if stats['redirects']:
        suffix = f" | keyword: '{context}'" if context else ''
        logger.info(
            f"[GOOGLE GOTO] Payload saneado: {stats['redirects']} redirect(s) → "
            f"{stats['via_token']} por token, {stats['via_http']} por HTTP, "
            f"{stats['via_metadata']} por metadata (solo dominio), "
            f"{stats['unresolved']} sin resolver{suffix}"
        )
    return stats


def sanitize_serp_response(serp_data: dict, context: str = '') -> dict:
    """
    Punto de entrada único para cada respuesta SERP recibida del proveedor:
    deja la alarma en logs si venía con enlaces goto (regresión de SerpAPI)
    y después los resuelve in place para que aguas abajo todo sea fidedigno.
    """
    log_redirect_stats(serp_data, context)
    return resolve_payload_redirects(serp_data, context)
