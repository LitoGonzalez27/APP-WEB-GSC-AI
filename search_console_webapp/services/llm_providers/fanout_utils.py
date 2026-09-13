"""
Utilidades compartidas para el query fan-out de LLM Monitoring.

Normalización de URLs, dominios y sub-consultas que usan los providers al
construir `sources` y `search_queries` (contrato en base_provider.py) y la capa
de persistencia al agregarlos. Salvo `resolve_redirects`, funciones puras.
Tests en tests/test_fanout_utils.py.
"""

import logging
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Iterable, List, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

logger = logging.getLogger(__name__)


# ─── URLs y dominios ─────────────────────────────────────────────────────────

def normalize_url(url: Optional[str]) -> Optional[str]:
    """
    Forma canónica de una URL para deduplicar y agregar.

    - Esquema y host en minúsculas. El `www.` se conserva: la agrupación por
      dominio la hace `normalize_domain`.
    - Elimina parámetros de tracking `utm_*` (OpenAI añade `utm_source=openai`).
    - Elimina el fragmento `#...` y la barra final del path salvo en la raíz.

    Devuelve la entrada tal cual si no es una URL http(s) parseable.
    """
    if not url or not isinstance(url, str):
        return url
    raw = url.strip()
    try:
        parts = urlsplit(raw)
    except ValueError:
        return raw
    if parts.scheme not in ('http', 'https') or not parts.netloc:
        return raw

    query = urlencode(
        [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
         if not k.lower().startswith('utm_')],
        doseq=True,
    )
    path = parts.path
    if len(path) > 1 and path.endswith('/'):
        path = path.rstrip('/')
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ''))


def normalize_domain(value: Optional[str]) -> str:
    """'https://www.Foo.com/x' → 'foo.com'. Acepta dominios sin esquema."""
    raw = str(value or '').strip().lower()
    if not raw:
        return ''
    if not raw.startswith(('http://', 'https://')):
        raw = f'https://{raw}'
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return ''
    host = (parsed.netloc or '').split('@')[-1].split(':')[0].strip()
    if host.startswith('www.'):
        host = host[4:]
    return host


def host_matches_domain(host: str, domain: str) -> bool:
    """True si `host` es el dominio o un subdominio suyo (ambos normalizados)."""
    if not host or not domain:
        return False
    return host == domain or host.endswith(f'.{domain}')


# ─── Sub-consultas ───────────────────────────────────────────────────────────

_SEARCH_OPERATOR = re.compile(r'\b(?:site|inurl|intitle|filetype|intext):\S+', re.IGNORECASE)
_BOOLEAN_OR = re.compile(r'\s(?:OR|\|)\s')
_EXCLUDED_TERM = re.compile(r'(?:^|\s)-\S+')
_STANDALONE_YEAR = re.compile(r'\b(?:19|20)\d{2}\b')
_NON_WORD = re.compile(r'[^\w\s]', re.UNICODE)
_SPACES = re.compile(r'\s+')


def _strip_accents(text: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))


def normalize_query(text: Optional[str]) -> str:
    """
    Clave de agrupación de una sub-consulta: el mismo intento de búsqueda escrito
    de formas distintas debe dar la misma clave.

    Quita operadores (`site:`, `-término`, `OR`), años sueltos, signos, tildes y
    espacios repetidos; pasa a minúsculas. El texto original se guarda aparte.
    """
    if not text:
        return ''
    value = _SEARCH_OPERATOR.sub(' ', text)
    value = _BOOLEAN_OR.sub(' ', value)
    value = _EXCLUDED_TERM.sub(' ', value)
    value = _STANDALONE_YEAR.sub(' ', value)
    value = _strip_accents(value.lower())
    value = _NON_WORD.sub(' ', value)
    return _SPACES.sub(' ', value).strip()


def dedupe_preserving_order(items: Iterable[str]) -> List[str]:
    """Elimina repetidos exactos conservando la primera aparición."""
    seen = set()
    out = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


# ─── Redirecciones de grounding (Gemini) ─────────────────────────────────────

GROUNDING_REDIRECT_HOST = 'vertexaisearch.cloud.google.com'


def resolve_redirects(urls: List[str], timeout: float = 5.0, max_workers: int = 8,
                      limit: int = 20) -> Dict[str, str]:
    """
    Resuelve URLs de redirección leyendo la cabecera `Location` de un HEAD sin
    seguir la redirección (no descarga la página destino: ~0,2 s por URL).

    Las URIs de grounding de Gemini caducan, así que hay que resolverlas al
    guardar. Devuelve {url_original: url_final normalizada}; las que fallan no
    aparecen (el llamador conserva la original).
    """
    targets = dedupe_preserving_order(u for u in urls if u)[:limit]
    if not targets:
        return {}

    def _resolve(url: str) -> Optional[str]:
        try:
            response = requests.head(url, allow_redirects=False, timeout=timeout)
            location = response.headers.get('Location')
            if response.is_redirect and location:
                return normalize_url(location)
        except requests.RequestException as e:
            logger.debug(f"No se pudo resolver la redirección {url[:80]}: {e}")
        return None

    with ThreadPoolExecutor(max_workers=min(max_workers, len(targets))) as pool:
        resolved = dict(zip(targets, pool.map(_resolve, targets)))
    return {src: dst for src, dst in resolved.items() if dst}
