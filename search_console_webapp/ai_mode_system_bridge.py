"""
ARCHIVO DE COMPATIBILIDAD - Bridge para AI Mode Monitoring System

Este archivo permite la integración del sistema AI Mode Monitoring
con la aplicación principal de forma segura y modular.

Funciones:
- Exporta el blueprint ai_mode_bp para registro en app.py
- Exporta funciones de cron para análisis automático
- Maneja importaciones de forma segura con fallback
"""

import logging

logger = logging.getLogger(__name__)

# Intentar importar del sistema AI Mode
try:
    from ai_mode_projects import ai_mode_bp
    from ai_mode_projects.services.cron_service import CronService
    
    # Exportar función de cron para compatibilidad
    def run_daily_analysis_for_all_ai_mode_projects():
        """Wrapper de compatibilidad para cron service de AI Mode"""
        cron_service = CronService()
        return cron_service.run_daily_analysis_for_all_projects()
    
    logger.info("✅ AI Mode Monitoring system loaded successfully")
    USING_AI_MODE_SYSTEM = True

except ImportError as e:
    # Fallback si el sistema no está disponible
    logger.warning(f"⚠️ AI Mode system not available ({e})")
    
    ai_mode_bp = None
    USING_AI_MODE_SYSTEM = False
    
    def run_daily_analysis_for_all_ai_mode_projects():
        """Placeholder cuando el sistema no está disponible"""
        logger.error("AI Mode system not available - cannot run daily analysis")
        return {
            'success': False,
            'error': 'AI Mode system not loaded',
            'total_projects': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0
        }

# Exportar para compatibilidad
__all__ = [
    'ai_mode_bp',
    'run_daily_analysis_for_all_ai_mode_projects',
    'USING_AI_MODE_SYSTEM'
]

