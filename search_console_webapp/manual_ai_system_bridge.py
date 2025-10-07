"""
ARCHIVO DE COMPATIBILIDAD - Bridge entre sistema antiguo y nuevo

Este archivo permite la transición gradual del sistema monolítico
al nuevo sistema modular sin romper código existente.

Durante la migración:
1. El código viejo importa desde aquí
2. Este archivo delega al sistema nuevo cuando está disponible
3. Si no está disponible, usa el sistema antiguo

Una vez completada la migración, este archivo puede eliminarse.
"""

import logging

logger = logging.getLogger(__name__)

# Intentar importar del nuevo sistema modular
try:
    from manual_ai import manual_ai_bp
    from manual_ai.services.cron_service import CronService
    
    # Exportar función de cron para compatibilidad
    def run_daily_analysis_for_all_projects():
        """Wrapper de compatibilidad para cron service"""
        cron_service = CronService()
        return cron_service.run_daily_analysis_for_all_projects()
    
    logger.info("✅ Using NEW modular Manual AI system")
    USING_NEW_SYSTEM = True

except ImportError as e:
    # Fallback al sistema antiguo
    logger.warning(f"⚠️ New system not available ({e}), falling back to legacy system")
    
    try:
        from manual_ai_system import manual_ai_bp, run_daily_analysis_for_all_projects
        logger.info("✅ Using LEGACY Manual AI system")
        USING_NEW_SYSTEM = False
    except ImportError as e2:
        logger.error(f"❌ Neither new nor legacy system available: {e2}")
        raise

# Exportar para compatibilidad
__all__ = ['manual_ai_bp', 'run_daily_analysis_for_all_projects', 'USING_NEW_SYSTEM']

