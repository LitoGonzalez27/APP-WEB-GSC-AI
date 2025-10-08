"""
AI Mode Monitoring System - Módulo Principal
Sistema modular para monitorización de menciones de marca en AI Mode
"""

from flask import Blueprint
import logging

logger = logging.getLogger(__name__)

# Crear el blueprint principal con URL prefix específico
ai_mode_bp = Blueprint('ai_mode', __name__, url_prefix='/ai-mode-projects')

# Importar y registrar todas las rutas
try:
    from ai_mode_projects.routes import (
        health,
        projects,
        keywords,
        analysis,
        results,
        exports
    )
    logger.info("✅ AI Mode routes loaded successfully")
except ImportError as e:
    logger.error(f"❌ Error loading AI Mode routes: {e}")
    raise

# Importar servicios principales para acceso externo
try:
    from ai_mode_projects.services.cron_service import run_daily_analysis_for_all_projects
    logger.info("✅ AI Mode cron service loaded successfully")
except ImportError as e:
    logger.error(f"❌ Error loading AI Mode cron service: {e}")
    raise

__all__ = [
    'ai_mode_bp',
    'run_daily_analysis_for_all_projects'
]

