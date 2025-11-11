#!/usr/bin/env python3
"""
Script para re-ejecutar el análisis de un proyecto con el código actualizado
"""
import logging
import sys
from services.llm_monitoring_service import MultiLLMMonitoringService
from database import get_db_connection
from datetime import date

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def rerun_analysis(project_id: int):
    """
    Re-ejecuta el análisis para un proyecto específico
    
    Args:
        project_id: ID del proyecto a analizar
    """
    logger.info("\n" + "="*70)
    logger.info(f"🔄 RE-EJECUTANDO ANÁLISIS - PROYECTO #{project_id}")
    logger.info("="*70 + "\n")
    
    # Verificar que el proyecto existe
    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la BD")
        return False
    
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM llm_monitoring_projects WHERE id = %s", (project_id,))
        project = cur.fetchone()
        
        if not project:
            logger.error(f"❌ No se encontró el proyecto #{project_id}")
            return False
        
        logger.info(f"📋 Proyecto: {project['name']}")
        logger.info("")
        
        cur.close()
        conn.close()
        
        # Ejecutar análisis
        service = MultiLLMMonitoringService()
        result = service.analyze_project(
            project_id=project_id,
            max_workers=8,
            analysis_date=date.today()
        )
        
        logger.info("\n" + "="*70)
        logger.info("✅ ANÁLISIS COMPLETADO")
        logger.info("="*70 + "\n")
        
        logger.info("📊 RESULTADOS:")
        logger.info(f"   Completitud global: {result.get('overall_completion_rate', 0):.1f}%")
        logger.info("")
        
        if 'by_llm' in result:
            logger.info("   Por LLM:")
            for llm_name, llm_data in result['by_llm'].items():
                logger.info(f"      {llm_name}: {llm_data.get('completion_rate', 0):.1f}%")
        
        logger.info("")
        return True
        
    except Exception as e:
        logger.error(f"\n❌ Error durante el análisis: {e}", exc_info=True)
        return False

if __name__ == '__main__':
    if len(sys.argv) < 2:
        logger.error("❌ Uso: python3 rerun_analysis.py <project_id>")
        logger.error("   Ejemplo: python3 rerun_analysis.py 5")
        sys.exit(1)
    
    try:
        project_id = int(sys.argv[1])
    except ValueError:
        logger.error(f"❌ El project_id debe ser un número, recibido: {sys.argv[1]}")
        sys.exit(1)
    
    success = rerun_analysis(project_id)
    sys.exit(0 if success else 1)

