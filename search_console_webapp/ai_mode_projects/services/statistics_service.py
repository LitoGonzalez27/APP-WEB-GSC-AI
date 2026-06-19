"""
Servicio para cálculo de estadísticas y métricas del sistema Manual AI
"""

import logging
from datetime import date, timedelta
from typing import List, Dict
from database import get_db_connection

logger = logging.getLogger(__name__)

from ai_mode_projects.services._statistics.overview import _OverviewMixin
from ai_mode_projects.services._statistics.keywords import _KeywordsMixin
from ai_mode_projects.services._statistics.domains import _DomainsMixin


class StatisticsService(_OverviewMixin, _KeywordsMixin, _DomainsMixin):
    """Servicio para generar estadísticas y métricas de proyectos"""
    pass
