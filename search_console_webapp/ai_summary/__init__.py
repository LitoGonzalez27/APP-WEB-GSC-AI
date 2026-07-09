"""
AI Visibility Summary - Módulo Principal

Panel de resumen unificado de visibilidad en IA por marca. Agrega métricas de
los tres módulos existentes (Manual AI / AI Overview, AI Mode y LLM Monitoring)
sin duplicar su lógica: cada canal se lee a través de un adapter que normaliza
las métricas a un contrato común (ChannelSummary).
"""

from flask import Blueprint
import logging

logger = logging.getLogger(__name__)

# Crear el blueprint principal
ai_summary_bp = Blueprint('ai_summary', __name__, url_prefix='/ai-summary')

# Importar y registrar todas las rutas
try:
    from ai_summary import routes  # noqa: F401
    logger.info("✅ AI Summary routes loaded successfully")
except ImportError as e:
    logger.error(f"❌ Error loading AI Summary routes: {e}")
    raise

__all__ = ['ai_summary_bp']
