"""
Prompt Sets (núcleo / tendencia / estacionales) — LLM Visibility Monitor

Funciones puras compartidas entre las rutas HTTP y el engine del cron.

Modelo:
- El set "núcleo" (core) es implícito: llm_monitoring_queries.prompt_set = NULL.
  Siempre está activo y no aparece en la config del proyecto.
- Los sets adicionales viven en llm_monitoring_projects.prompt_sets:
      {"enabled": bool,
       "sets": [{"name": "Black Friday",
                 "window": {"start": "11-15", "end": "12-02"}}]}
- La ventana es opcional (sin ventana = siempre activo) y se evalúa contra el
  día UTC en formato MM-DD, con soporte de wrap-around (p.ej. 12-20 → 01-06).
  Decisión de diseño: la ventana NUNCA muta is_active; se evalúa en lectura.
"""

import json
import logging
import re
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Nombres que no puede usar un set adicional: chocarían con el set implícito.
RESERVED_CORE_NAMES = {'core', 'núcleo', 'nucleo'}

_WINDOW_RE = re.compile(r'^(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$')


def normalize_set_name(name):
    """Trim + compacta espacios. Devuelve '' si es inválido. Cap a 80 chars."""
    if not name:
        return ''
    trimmed = re.sub(r'\s+', ' ', str(name)).strip()
    return trimmed[:80]


def parse_window(raw):
    """
    Valida una ventana estacional {"start": "MM-DD", "end": "MM-DD"}.

    Returns:
        dict con la ventana normalizada, o None si raw es None/{}.
    Raises:
        ValueError si la ventana está malformada.
    """
    if not raw:
        return None
    if not isinstance(raw, dict):
        raise ValueError('window must be an object with start/end')
    start = str(raw.get('start') or '').strip()
    end = str(raw.get('end') or '').strip()
    if not start and not end:
        return None
    if not (_WINDOW_RE.match(start) and _WINDOW_RE.match(end)):
        raise ValueError('window start/end must use MM-DD format (e.g. "11-15")')
    return {'start': start, 'end': end}


def _mmdd_tuple(mmdd):
    month, day = mmdd.split('-')
    return (int(month), int(day))


def is_window_active(window, today=None):
    """
    ¿Está la ventana activa hoy (día UTC)?

    Sin ventana → siempre activa. Con wrap-around: si start > end la ventana
    cruza el fin de año (p.ej. 12-20 → 01-06).
    """
    if not window:
        return True
    try:
        start = _mmdd_tuple(window['start'])
        end = _mmdd_tuple(window['end'])
    except (KeyError, ValueError, AttributeError):
        # Ventana corrupta: mejor analizar de más que silenciar un set entero.
        logger.warning(f"Ventana de set malformada, se ignora: {window}")
        return True
    now = today or datetime.now(timezone.utc)
    current = (now.month, now.day)
    if start <= end:
        return start <= current <= end
    return current >= start or current <= end


def sanitize_prompt_sets_config(raw):
    """
    Sanea la config entrante. Shape esperada:
        {"enabled": bool, "sets": [{"name": "...", "window": {...}|null}]}

    Returns:
        (config_dict, list_of_names_in_order)
    Raises:
        ValueError si la entrada es inválida.
    """
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError('sets_config must be an object')

    enabled = bool(raw.get('enabled'))
    sets_in = raw.get('sets') or []
    if not isinstance(sets_in, list):
        raise ValueError('sets must be a list')

    seen = set()
    cleaned = []
    names_in_order = []
    for entry in sets_in:
        if isinstance(entry, str):
            name = normalize_set_name(entry)
            window = None
        elif isinstance(entry, dict):
            name = normalize_set_name(entry.get('name'))
            window = parse_window(entry.get('window'))
        else:
            continue
        if not name:
            continue
        key = name.lower()
        if key in RESERVED_CORE_NAMES:
            raise ValueError(f'"{name}" is reserved for the core set')
        if key in seen:
            continue
        seen.add(key)
        item = {'name': name}
        if window:
            item['window'] = window
        cleaned.append(item)
        names_in_order.append(name)

    return (
        {'enabled': enabled and len(cleaned) > 0, 'sets': cleaned},
        names_in_order,
    )


def parse_sets_config(raw_config):
    """Parsea el JSONB prompt_sets de BD (dict o string JSON) a dict seguro."""
    cfg = raw_config or {'enabled': False, 'sets': []}
    if isinstance(cfg, str):
        try:
            cfg = json.loads(cfg)
        except (json.JSONDecodeError, TypeError):
            cfg = {'enabled': False, 'sets': []}
    if not isinstance(cfg, dict):
        cfg = {'enabled': False, 'sets': []}
    return cfg


def get_defined_set_names(raw_config):
    """Nombres de sets definidos en la config (sin el core implícito)."""
    cfg = parse_sets_config(raw_config)
    return [
        c.get('name') for c in (cfg.get('sets') or [])
        if isinstance(c, dict) and c.get('name')
    ]


def get_inactive_set_names(raw_config, today=None):
    """
    Nombres de sets cuya ventana estacional NO está activa hoy (día UTC).

    Es la lista que el engine excluye del análisis diario. El core (NULL) y los
    sets sin ventana nunca aparecen aquí. Si la feature está deshabilitada
    (enabled=false) devuelve [], de modo que deshabilitar sets nunca detiene
    análisis ya configurados.
    """
    cfg = parse_sets_config(raw_config)
    if not cfg.get('enabled'):
        return []
    inactive = []
    for entry in (cfg.get('sets') or []):
        if not isinstance(entry, dict) or not entry.get('name'):
            continue
        window = entry.get('window')
        if window and not is_window_active(window, today=today):
            inactive.append(entry['name'])
    return inactive
