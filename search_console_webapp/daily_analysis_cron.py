#!/usr/bin/env python3
"""
Script para el cron job diario del Manual AI Analysis System
Este script debe ejecutarse diariamente para analizar todos los proyectos activos.

CONFIGURACIÓN CRON:
# Ejecutar todos los días a las 2:00 AM
0 2 * * * cd /path/to/your/app && python3 daily_analysis_cron.py >> /var/log/manual_ai_cron.log 2>&1

RAILWAY SETUP:
Agregar este comando al Procfile como job separado o usar Railway Cron addon.
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
logger = logging.getLogger('manual_ai_cron')

def main():
    try:
        logger.info("🕒 === MANUAL AI CRON JOB STARTED ===")
        
        # Importar la función de análisis diario
        from manual_ai_system import run_daily_analysis_for_all_projects
        
        # Ejecutar análisis diario
        result = run_daily_analysis_for_all_projects()
        
        if result["success"]:
            logger.info(f"✅ Daily analysis completed successfully:")
            logger.info(f"   📊 Total projects: {result.get('total_projects', 0)}")
            logger.info(f"   ✅ Successful: {result.get('successful', 0)}")
            logger.info(f"   ❌ Failed: {result.get('failed', 0)}")
            logger.info(f"   ⏭️ Skipped: {result.get('skipped', 0)}")
            
            # Exit code 0 para éxito
            sys.exit(0)
        else:
            logger.error(f"❌ Daily analysis failed: {result.get('error', 'Unknown error')}")
            # Exit code 1 para error
            sys.exit(1)
            
    except ImportError as e:
        logger.error(f"❌ Import error - ensure you're running from the correct directory: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Critical error in cron job: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()