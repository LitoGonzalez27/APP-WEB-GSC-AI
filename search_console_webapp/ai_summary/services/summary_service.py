"""
Servicio orquestador del panel AI Visibility Summary.

Combina los ChannelSummary de los adapters en un payload único:
- AI Visibility Score compuesto, ponderado SOLO sobre los canales que la
  marca tiene vinculados y con datos (los pesos se renormalizan; un canal
  no configurado nunca penaliza el score).
- Ranking unificado de competidores entre canales.
- Highlights automáticos por reglas simples y deterministas.
"""

import logging
from collections import defaultdict
from typing import Dict, List, Optional

from ai_summary.services.adapters import (
    manual_ai_adapter,
    ai_mode_adapter,
    llm_monitoring_adapter,
)
from ai_summary.services.adapters.base import empty_channel

logger = logging.getLogger(__name__)

# Pesos base del score compuesto. Se renormalizan sobre los canales con datos,
# de modo que una marca con 2 canales se puntúa sobre esos 2, no sobre 3.
CHANNEL_WEIGHTS = {
    'ai_overview': 0.4,
    'ai_mode': 0.2,
    'llm': 0.4,
}

CHANNEL_ADAPTERS = {
    'ai_overview': ('manual_ai_project_id', manual_ai_adapter),
    'ai_mode': ('ai_mode_project_id', ai_mode_adapter),
    'llm': ('llm_project_id', llm_monitoring_adapter),
}

CHANNEL_LABELS = {
    'ai_overview': 'Google AI Overview',
    'ai_mode': 'Google AI Mode',
    'llm': 'LLMs (ChatGPT, Gemini...)',
}


class SummaryService:
    """Orquestador de resumen por marca"""

    @staticmethod
    def get_brand_summary(brand: Dict, days: int = 30) -> Dict:
        channels = {}
        for channel, (link_field, adapter) in CHANNEL_ADAPTERS.items():
            project_id = brand.get(link_field)
            if not project_id:
                channels[channel] = empty_channel(channel)
                continue
            try:
                channels[channel] = adapter.get_channel_summary(project_id, days)
            except Exception as e:
                logger.error(f"AI Summary: adapter '{channel}' failed for brand {brand['id']}: {e}",
                             exc_info=True)
                channels[channel] = empty_channel(channel, reason='error')
                channels[channel]['project_id'] = project_id

        score = _composite_score(channels)
        return {
            'brand': brand,
            'days': days,
            'score': score,
            'channels': channels,
            'competitors_unified': _unified_competitors(brand, channels),
            'highlights': _build_highlights(channels, score),
        }


# ----------------------------------------------------------------------
# Score compuesto
# ----------------------------------------------------------------------

def _composite_score(channels: Dict) -> Dict:
    used = {
        name: ch for name, ch in channels.items()
        if ch['available'] and ch['visibility_pct'] is not None
    }
    missing = [name for name in CHANNEL_WEIGHTS if name not in used]

    if not used:
        return {
            'value': None, 'previous': None, 'delta': None,
            'channels_used': [], 'channels_missing': missing, 'weights': {},
        }

    total_weight = sum(CHANNEL_WEIGHTS[name] for name in used)
    weights = {name: round(CHANNEL_WEIGHTS[name] / total_weight, 3) for name in used}

    value = sum(used[name]['visibility_pct'] * weights[name] for name in used)

    # Score del periodo anterior con los mismos pesos, solo si todos los
    # canales usados tienen delta (es decir, datos en el periodo previo).
    previous = None
    if all(used[name]['visibility_delta'] is not None for name in used):
        previous = sum(
            (used[name]['visibility_pct'] - used[name]['visibility_delta']) * weights[name]
            for name in used
        )

    return {
        'value': round(value, 1),
        'previous': round(previous, 1) if previous is not None else None,
        'delta': round(value - previous, 1) if previous is not None else None,
        'channels_used': list(used.keys()),
        'channels_missing': missing,
        'weights': weights,
    }


# ----------------------------------------------------------------------
# Competidores unificados
# ----------------------------------------------------------------------

def _unified_competitors(brand: Dict, channels: Dict) -> List[Dict]:
    """
    Fusión por dominio de los rankings de competidores de cada canal.
    Cada dominio lleva su visibilidad por canal y una media simple de los
    canales donde aparece, para poder ordenar el ranking global.
    """
    merged = defaultdict(lambda: {'channels': {}, 'is_brand': False, 'is_selected_competitor': False})

    for channel, summary in channels.items():
        for comp in summary.get('competitors') or []:
            domain = (comp.get('domain') or '').strip().lower()
            if not domain:
                continue
            entry = merged[domain]
            entry['channels'][channel] = comp.get('visibility_pct')
            entry['is_brand'] = entry['is_brand'] or bool(comp.get('is_brand'))
            entry['is_selected_competitor'] = (
                entry['is_selected_competitor'] or bool(comp.get('is_selected_competitor'))
            )

    result = []
    for domain, entry in merged.items():
        values = [v for v in entry['channels'].values() if v is not None]
        result.append({
            'domain': domain,
            'channels': entry['channels'],
            'avg_visibility': round(sum(values) / len(values), 1) if values else None,
            'channels_count': len(values),
            'is_brand': entry['is_brand'],
            'is_selected_competitor': entry['is_selected_competitor'],
        })

    result.sort(key=lambda e: (-(e['avg_visibility'] or 0), -e['channels_count']))
    for rank, entry in enumerate(result, start=1):
        entry['rank'] = rank
    return result[:15]


# ----------------------------------------------------------------------
# Highlights por reglas
# ----------------------------------------------------------------------

def _build_highlights(channels: Dict, score: Dict) -> List[Dict]:
    highlights = []

    if score.get('delta') is not None and abs(score['delta']) >= 2:
        improving = score['delta'] > 0
        highlights.append({
            'type': 'score_trend',
            'severity': 'positive' if improving else 'negative',
            'text': (f"Overall AI visibility {'improved' if improving else 'dropped'} "
                     f"{abs(score['delta'])} pts vs the previous period."),
        })

    # Mejor y peor movimiento por canal
    deltas = [
        (name, ch['visibility_delta'])
        for name, ch in channels.items()
        if ch['available'] and ch['visibility_delta'] is not None
    ]
    if deltas:
        best = max(deltas, key=lambda d: d[1])
        worst = min(deltas, key=lambda d: d[1])
        if best[1] >= 3:
            highlights.append({
                'type': 'channel_up',
                'severity': 'positive',
                'text': f"{CHANNEL_LABELS[best[0]]} is your fastest-growing channel (+{round(best[1], 1)} pts).",
            })
        if worst[1] <= -3 and worst[0] != best[0]:
            highlights.append({
                'type': 'channel_down',
                'severity': 'negative',
                'text': f"{CHANNEL_LABELS[worst[0]]} is losing visibility ({round(worst[1], 1)} pts).",
            })

    # Sentimiento negativo en LLMs
    llm = channels.get('llm') or {}
    sentiment = (llm.get('extras') or {}).get('sentiment') or {}
    if (sentiment.get('negative') or 0) >= 15:
        highlights.append({
            'type': 'sentiment_warning',
            'severity': 'negative',
            'text': f"{sentiment['negative']}% of your LLM mentions carry negative sentiment — review the responses tab.",
        })

    # LLM más débil (dónde reforzar)
    by_llm = (llm.get('extras') or {}).get('by_llm') or {}
    rates = [(data['label'], data['mention_rate']) for data in by_llm.values()
             if data.get('mention_rate') is not None]
    if len(rates) >= 2:
        weakest = min(rates, key=lambda r: r[1])
        strongest = max(rates, key=lambda r: r[1])
        if strongest[1] - weakest[1] >= 20:
            highlights.append({
                'type': 'llm_gap',
                'severity': 'neutral',
                'text': (f"Your brand is strong on {strongest[0]} ({strongest[1]}%) but weak on "
                         f"{weakest[0]} ({weakest[1]}%)."),
            })

    # Canales sin monitorizar (informativo, nunca penaliza el score)
    for name in score.get('channels_missing') or []:
        if not (channels.get(name) or {}).get('project_id'):
            highlights.append({
                'type': 'channel_not_monitored',
                'severity': 'info',
                'text': f"{CHANNEL_LABELS[name]} is not monitored for this brand yet.",
            })

    return highlights[:6]
