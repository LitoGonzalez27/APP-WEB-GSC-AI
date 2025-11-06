#!/usr/bin/env python3
"""
Script de diagnóstico para verificar endpoints de LLM Monitoring
"""
import sys
import os
import logging
from database import get_db_connection

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_project_endpoint(project_id: int):
    """Simula lo que hace el endpoint GET /projects/<id>"""
    
    logger.info("=" * 70)
    logger.info(f"🔍 DIAGNÓSTICO: Endpoint GET /projects/{project_id}")
    logger.info("=" * 70)
    
    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la BD")
        return False
    
    try:
        cur = conn.cursor()
        
        # 1. Verificar proyecto existe
        cur.execute("SELECT * FROM llm_monitoring_projects WHERE id = %s", (project_id,))
        project = cur.fetchone()
        
        if not project:
            logger.error(f"❌ Proyecto {project_id} no existe")
            return False
        
        logger.info(f"✅ Proyecto encontrado: {project['name']}")
        
        # 2. Verificar snapshots
        cur.execute("""
            SELECT 
                llm_provider,
                mention_rate,
                avg_position,
                share_of_voice,
                positive_mentions,
                neutral_mentions,
                negative_mentions,
                total_mentions,
                total_queries,
                snapshot_date
            FROM llm_monitoring_snapshots
            WHERE project_id = %s
            ORDER BY snapshot_date DESC, llm_provider
            LIMIT 4
        """, (project_id,))
        
        snapshots = cur.fetchall()
        logger.info(f"📊 Snapshots encontrados: {len(snapshots)}")
        
        if snapshots:
            for snap in snapshots:
                logger.info(f"   - {snap['llm_provider']}: {snap['mention_rate']}% menciones, {snap['total_queries']} queries")
        
        # 3. Verificar que los datos son válidos
        for snap in snapshots:
            if snap['total_queries'] is None or snap['total_queries'] == 0:
                logger.warning(f"⚠️  {snap['llm_provider']}: total_queries es {snap['total_queries']}")
            
            if snap['mention_rate'] is None:
                logger.warning(f"⚠️  {snap['llm_provider']}: mention_rate es None")
        
        # 4. Verificar queries
        cur.execute("""
            SELECT COUNT(*) as total
            FROM llm_monitoring_queries
            WHERE project_id = %s AND is_active = TRUE
        """, (project_id,))
        
        queries_count = cur.fetchone()['total']
        logger.info(f"📝 Queries activas: {queries_count}")
        
        # 5. Verificar resultados recientes
        cur.execute("""
            SELECT 
                llm_provider,
                COUNT(*) as total_results,
                MAX(analysis_date) as last_analysis
            FROM llm_monitoring_results
            WHERE project_id = %s
            GROUP BY llm_provider
            ORDER BY llm_provider
        """, (project_id,))
        
        results_by_llm = cur.fetchall()
        logger.info(f"🔬 Resultados por LLM:")
        for r in results_by_llm:
            logger.info(f"   - {r['llm_provider']}: {r['total_results']} resultados, último: {r['last_analysis']}")
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("✅ DIAGNÓSTICO COMPLETADO SIN ERRORES")
        logger.info("=" * 70)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error durante diagnóstico: {e}", exc_info=True)
        return False
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    if len(sys.argv) > 1:
        project_id = int(sys.argv[1])
    else:
        # Usar proyecto por defecto
        project_id = 5  # Test LLM
    
    success = test_project_endpoint(project_id)
    sys.exit(0 if success else 1)

