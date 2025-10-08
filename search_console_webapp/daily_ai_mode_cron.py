#!/usr/bin/env python3
"""
Script para el cron job diario del AI Mode Monitoring System
Este script debe ejecutarse diariamente para analizar todos los proyectos activos.

CONFIGURACIÓN CRON:
# Ejecutar todos los días a las 3:00 AM (diferente de manual_ai para evitar conflictos)
0 3 * * * cd /path/to/your/app && python3 daily_ai_mode_cron.py >> /var/log/ai_mode_cron.log 2>&1

RAILWAY SETUP:
Se configura en railway.json como job separado
"""

import sys
import os
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ai_mode_cron')

def main():
    try:
        logger.info("🕒 === AI MODE MONITORING CRON JOB STARTED ===")
        logger.info(f"⏰ Timestamp: {datetime.now().isoformat()}")
        
        # Importar la función de análisis diario a través del bridge
        from ai_mode_system_bridge import run_daily_analysis_for_all_ai_mode_projects, USING_AI_MODE_SYSTEM
        
        if USING_AI_MODE_SYSTEM:
            logger.info("📦 Usando el sistema AI Mode Monitoring")
        else:
            logger.warning("⚠️ AI Mode system not available")
            sys.exit(1)
        
        # Ejecutar análisis diario
        logger.info("🚀 Iniciando análisis diario de proyectos AI Mode...")
        result = run_daily_analysis_for_all_ai_mode_projects()
        
        if result.get("success"):
            logger.info(f"✅ AI Mode daily analysis completed successfully:")
            logger.info(f"   📊 Total projects: {result.get('total_projects', 0)}")
            logger.info(f"   ✅ Successful: {result.get('successful', 0)}")
            logger.info(f"   ❌ Failed: {result.get('failed', 0)}")
            logger.info(f"   ⏭️ Skipped: {result.get('skipped', 0)}")
            logger.info(f"   🎯 Total keywords analyzed: {result.get('total_keywords_analyzed', 0)}")
            logger.info(f"   💰 RU consumed: {result.get('total_ru_consumed', 0)}")
            
            logger.info("🎉 AI MODE CRON JOB COMPLETED SUCCESSFULLY")
            # Exit code 0 para éxito
            sys.exit(0)
        else:
            logger.error(f"❌ AI Mode daily analysis failed: {result.get('error', 'Unknown error')}")
            logger.error("💥 AI MODE CRON JOB FAILED")
            # Exit code 1 para error
            sys.exit(1)
            
    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        logger.error("Sugerencia: verifica que ai-mode-projects esté correctamente instalado")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        logger.error("💥 AI MODE CRON JOB CRASHED")
        sys.exit(1)

if __name__ == "__main__":
    main()

