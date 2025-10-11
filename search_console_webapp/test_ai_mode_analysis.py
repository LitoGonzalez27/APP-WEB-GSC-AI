"""
Script para probar el análisis de AI Mode con una keyword
"""

import os
os.environ['DATABASE_URL'] = 'postgresql://postgres:XCkoyokCzfRlyPCFNGpfIhqteibfbojQ@caboose.proxy.rlwy.net:13631/railway'

from ai_mode_projects.services.analysis_service import AnalysisService
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_single_keyword_analysis():
    """Probar análisis de una sola keyword"""
    
    project_id = 1
    
    logger.info("=" * 80)
    logger.info("PROBANDO ANÁLISIS DE AI MODE")
    logger.info("=" * 80)
    
    try:
        # Crear instancia del servicio
        service = AnalysisService()
        
        # Ejecutar análisis para el proyecto 1
        logger.info(f"\n🚀 Analizando proyecto {project_id}...")
        
        result = service.run_project_analysis(
            project_id=project_id,
            force_overwrite=True,  # Forzar sobreescritura para probar
            user_id=5  # Usuario del proyecto
        )
        
        logger.info(f"\n📊 RESULTADOS:")
        logger.info(f"   Successful: {result.get('successful', 0)}")
        logger.info(f"   Failed: {result.get('failed', 0)}")
        logger.info(f"   Skipped: {result.get('skipped', 0)}")
        logger.info(f"   Total Keywords: {result.get('total_keywords', 0)}")
        
        if result.get('results'):
            logger.info(f"\n✅ PRIMER RESULTADO:")
            first_result = result['results'][0]
            logger.info(f"   Keyword: {first_result.get('keyword')}")
            logger.info(f"   Success: {first_result.get('success')}")
            if first_result.get('error'):
                logger.error(f"   Error: {first_result.get('error')}")
            else:
                logger.info(f"   Brand Mentioned: {first_result.get('brand_mentioned')}")
                logger.info(f"   Position: {first_result.get('mention_position')}")
                logger.info(f"   Total Sources: {first_result.get('total_sources')}")
        
        logger.info("\n" + "=" * 80)
        logger.info("PRUEBA COMPLETADA")
        logger.info("=" * 80)
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error en análisis: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

if __name__ == '__main__':
    test_single_keyword_analysis()

