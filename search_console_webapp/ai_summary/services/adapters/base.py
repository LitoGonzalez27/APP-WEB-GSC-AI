"""
Contrato común de los adapters de canal del panel AI Visibility Summary.

Cada adapter traduce las métricas de su módulo (Manual AI, AI Mode,
LLM Monitoring) a un ChannelSummary normalizado. El panel nunca consulta
las tablas de los módulos directamente: solo habla con adapters, de modo
que añadir un canal nuevo es escribir un adapter más.
"""

from datetime import date, timedelta
from typing import Dict, List, Optional


def empty_channel(channel: str, reason: str = 'not_linked') -> Dict:
    """Canal sin proyecto vinculado o sin datos. No participa en el score."""
    return {
        'channel': channel,
        'available': False,
        'reason': reason,  # 'not_linked' | 'no_data' | 'error'
        'project_id': None,
        'project_name': None,
        'visibility_pct': None,
        'visibility_delta': None,
        'avg_position': None,
        'position_delta': None,
        'timeseries': [],
        'competitors': [],
        'last_date': None,
        'extras': {},
    }


def window_bounds(period: str = '30'):
    """
    Ventana actual y ventana anterior del mismo tamaño para calcular deltas.

    period: número de días como string ('7', '14', '28', '30', '90', '180')
    o 'last_month' (el mes natural anterior completo, comparado con el mes
    natural previo a ese).

    Devuelve (previous_start, current_start, end), con ventana actual
    = (current_start, end] y ventana anterior = (previous_start, current_start].
    """
    today = date.today()
    if period == 'last_month':
        end = today.replace(day=1) - timedelta(days=1)              # último día del mes anterior
        current_start = end.replace(day=1) - timedelta(days=1)      # último día de hace 2 meses
        previous_start = current_start.replace(day=1) - timedelta(days=1)
        return previous_start, current_start, end

    days = int(period)
    current_start = today - timedelta(days=days)
    previous_start = today - timedelta(days=days * 2)
    return previous_start, current_start, today


def ranking_days(current_start: date) -> int:
    """
    Días aproximados para los rankings de competidores de StatisticsService
    (que siempre trabajan en "últimos N días desde hoy"): cubre desde el
    inicio de la ventana actual hasta hoy.
    """
    return max((date.today() - current_start).days, 1)


def split_windows(rows: List[Dict], date_key: str, current_start: date):
    """Separar filas de snapshot en ventana anterior / ventana actual."""
    previous, current = [], []
    for row in rows:
        row_date = row[date_key]
        (current if row_date > current_start else previous).append(row)
    return previous, current


def avg(values: List[Optional[float]]) -> Optional[float]:
    clean = [float(v) for v in values if v is not None]
    if not clean:
        return None
    return sum(clean) / len(clean)


def delta(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    """Delta absoluto en puntos. None si falta alguno de los dos periodos."""
    if current is None or previous is None:
        return None
    return round(current - previous, 2)


def rounded(value: Optional[float], digits: int = 1) -> Optional[float]:
    return round(value, digits) if value is not None else None
