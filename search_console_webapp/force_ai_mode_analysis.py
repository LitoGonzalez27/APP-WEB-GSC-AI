#!/usr/bin/env python3
"""
Script para forzar un análisis AI Mode con sobreescritura de datos del día
"""

import sys
import logging
from ai_mode_projects.services.analysis_service import AnalysisService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def force_analysis(project_id: int, user_id: int):
    """Forzar análisis con sobreescritura"""
    analysis_service = AnalysisService()
    
    logger.info(f"🔄 Forzando análisis para proyecto {project_id} con sobreescritura...")
    
    try:
        results = analysis_service.run_project_analysis(
            project_id=project_id,
            force_overwrite=True,  # Esto fuerza sobreescritura
            user_id=user_id
        )
        
        if isinstance(results, dict) and not results.get('success', True):
            logger.error(f"❌ Error en análisis: {results.get('error')}")
            return False
        
        logger.info(f"✅ Análisis completado: {len(results)} keywords procesadas")
        logger.info(f"📊 Resultados:")
        
        for r in results[:5]:  # Mostrar primeros 5
            logger.info(f"   • {r['keyword']}: mentioned={r['brand_mentioned']}, pos={r.get('mention_position', 'N/A')}")
        
        if len(results) > 5:
            logger.info(f"   ... y {len(results) - 5} más")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error ejecutando análisis: {e}", exc_info=True)
        return False

if __name__ == '__main__':
    project_id = 1
    user_id = 5
    
    logger.info("="*80)
    logger.info("FORZAR ANÁLISIS AI MODE (CON SOBREESCRITURA)")
    logger.info("="*80)
    logger.info(f"Proyecto: {project_id}")
    logger.info(f"Usuario: {user_id}")
    logger.info("="*80)
    
    success = force_analysis(project_id, user_id)
    
    if success:
        logger.info("\n✅ ANÁLISIS FORZADO COMPLETADO")
        logger.info("🔍 Ejecuta ahora: python3 check_raw_ai_mode_data.py")
    else:
        logger.error("\n❌ ANÁLISIS FORZADO FALLÓ")
        sys.exit(1)

