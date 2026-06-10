#!/usr/bin/env python3
"""
Re-ejecuta el análisis LLM Monitoring para UN solo proyecto.
Uso: python3 rerun_single_project.py <project_id>

Seguro de ejecutar múltiples veces — usa ON CONFLICT DO UPDATE.
"""

import sys
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('rerun_single_project')


def main():
    if len(sys.argv) < 2:
        print("Uso: python3 rerun_single_project.py <project_id>")
        print("Ejemplo: python3 rerun_single_project.py 16")
        sys.exit(1)

    project_id = int(sys.argv[1])
    logger.info(f"🚀 Re-ejecutando análisis para proyecto #{project_id}")

    from services.llm_monitoring_service import MultiLLMMonitoringService

    service = MultiLLMMonitoringService(api_keys=None)
    result = service.analyze_project(project_id=project_id, max_workers=8)

    if result.get('success') or result.get('total_queries_executed', 0) > 0:
        logger.info(f"✅ Análisis completado para proyecto #{project_id}")
        logger.info(f"   Queries ejecutadas: {result.get('total_queries_executed', 0)}")
        logger.info(f"   LLMs analizados: {result.get('llms_analyzed', 0)}")
        logger.info(f"   Duración: {result.get('duration_seconds', 0):.1f}s")
        incomplete = result.get('incomplete_llms', [])
        if incomplete:
            logger.warning(f"   ⚠️ LLMs incompletos: {', '.join(incomplete)}")
    else:
        logger.error(f"❌ Error: {result.get('error', 'unknown')}")
        logger.error(f"   {result.get('message', '')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
