"""
Servicio para gestión de competidores en proyectos
"""

import logging
import json
from datetime import date, timedelta
from typing import List, Dict
from database import get_db_connection
from services.utils import normalize_search_console_url
from manual_ai.config import MAX_COMPETITORS_PER_PROJECT

logger = logging.getLogger(__name__)

from manual_ai.services._competitor.validation import _ValidationMixin
from manual_ai.services._competitor.historical import _HistoricalMixin
from manual_ai.services._competitor.charts import _ChartsMixin


class CompetitorService(_ValidationMixin, _HistoricalMixin, _ChartsMixin):
    """Servicio para gestión de competidores"""
    pass
