"""
Utilidades compartidas para el query fan-out de LLM Monitoring.

Normalización de URLs y de sub-consultas que usan todos los providers al
construir `sources` y `search_queries` (contrato en base_provider.py).
Funciones puras, sin I/O: se testean en tests/test_fanout_utils.py.
"""

from typing import Iterable, List, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def normalize_url(url: Optional[str]) -> Optional[str]:
    """
    Forma canónica de una URL para deduplicar y agregar.

    - Esquema y host en minúsculas. El `www.` se conserva: la agrupación por
      dominio la hace la capa de estadísticas con su propia normalización.
    - Elimina parámetros de tracking `utm_*` (OpenAI añade `utm_source=openai`).
    - Elimina el fragmento `#...`.
    - Elimina la barra final del path salvo en la raíz.

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
