#!/usr/bin/env python3
"""
Entrypoint CLI del análisis diario de Manual AI (analiza todos los proyectos activos).

⚠️ DISPARADOR REAL EN PRODUCCIÓN (verificado vía Railway API, 2026-06-19):
El cron NO se ejecuta desde este script ni desde Procfile/railway.json. El disparador
real es el servicio Bun de Railway **`function-bun-AI-Overview`**, configurado en el
dashboard con `cronSchedule`:
    - production: `0 04 * * 1,4,6`  (lun/jue/sáb 04:00 UTC)
    - staging:    `0 05 * * 6`      (sáb 05:00 UTC)
Ese Bun service hace POST a `/manual-ai/api/cron/daily-analysis?async=1` con Bearer CRON_TOKEN.
Ver CLAUDE-manual-ai.md §10.

USO DE ESTE SCRIPT: invocación MANUAL puntual (no programado), p.ej. para forzar un run:
    railway run --service "Clicandseo" python3 daily_analysis_cron.py
Llama directamente a run_daily_analysis_for_all_projects() (mismo motor que el endpoint).
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
        
        # Importar la función de análisis diario a través del bridge
        from manual_ai_system_bridge import run_daily_analysis_for_all_projects, USING_NEW_SYSTEM
        
        if USING_NEW_SYSTEM:
            logger.info("📦 Usando el NUEVO sistema modular de Manual AI")
        else:
            logger.info("📦 Usando el sistema ORIGINAL de Manual AI (fallback)")
        
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