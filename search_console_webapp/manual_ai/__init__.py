"""
Manual AI Analysis System - Módulo Principal
Sistema modular y escalable para análisis manual de AI Overview
"""

from flask import Blueprint
import logging

logger = logging.getLogger(__name__)

# Crear el blueprint principal
manual_ai_bp = Blueprint('manual_ai', __name__, url_prefix='/manual-ai')

# Importar y registrar todas las rutas
try:
    from manual_ai.routes import (
        health,
        projects,
        keywords,
        analysis,
        results,
        competitors,
        exports
    )
    logger.info("✅ Manual AI routes loaded successfully")
except ImportError as e:
    logger.error(f"❌ Error loading Manual AI routes: {e}")
    raise

# Importar servicios principales para acceso externo
try:
    from manual_ai.services.cron_service import run_daily_analysis_for_all_projects
    logger.info("✅ Manual AI cron service loaded successfully")
except ImportError as e:
    logger.error(f"❌ Error loading Manual AI cron service: {e}")
    raise

__all__ = [
    'manual_ai_bp',
    'run_daily_analysis_for_all_projects'
]

