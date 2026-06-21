"""
Servicio para cálculo de estadísticas y métricas del sistema Manual AI
"""

import logging
from datetime import date, timedelta
from typing import List, Dict
from database import get_db_connection

logger = logging.getLogger(__name__)

from manual_ai.services._statistics.overview import _OverviewMixin
from manual_ai.services._statistics.keywords import _KeywordsMixin
from manual_ai.services._statistics.domains import _DomainsMixin
from manual_ai.services._statistics.aio_organic import _AioOrganicMixin
from manual_ai.services._statistics.historical import _HistoricalMixin


class StatisticsService(_OverviewMixin, _KeywordsMixin, _DomainsMixin, _AioOrganicMixin, _HistoricalMixin):
    """Servicio para generar estadísticas y métricas de proyectos"""
    pass
