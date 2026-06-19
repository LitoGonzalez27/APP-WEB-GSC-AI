"""
Punto de entrada del sistema Manual AI.

Histórico: este archivo nació como "bridge" durante la migración del antiguo
sistema monolítico (`manual_ai_system.py`) al paquete modular (`manual_ai/`).
Esa migración ya está completa y el monolito ya no existe en el repo, así que
aquí solo queda la indirección estable que consumen `app.py` y
`daily_analysis_cron.py`.

Se mantiene el nombre de módulo y los símbolos exportados
(`manual_ai_bp`, `run_daily_analysis_for_all_projects`, `USING_NEW_SYSTEM`)
para no tocar a sus importadores.
"""

import logging

from manual_ai import manual_ai_bp
from manual_ai.services.cron_service import CronService

logger = logging.getLogger(__name__)


def run_daily_analysis_for_all_projects():
    """Wrapper de compatibilidad para el cron diario."""
    cron_service = CronService()
    return cron_service.run_daily_analysis_for_all_projects()


# El sistema modular es el único existente desde que se completó la migración.
USING_NEW_SYSTEM = True

logger.info("✅ Using modular Manual AI system")

__all__ = ['manual_ai_bp', 'run_daily_analysis_for_all_projects', 'USING_NEW_SYSTEM']
