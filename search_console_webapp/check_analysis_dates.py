#!/usr/bin/env python3
"""
Script para verificar cuándo se ejecutaron los análisis
"""
import logging
from database import get_db_connection

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def check_analysis_dates():
    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la BD")
        return
    
    try:
        cur = conn.cursor()
        
        # Verificar cuándo se ejecutaron los análisis más recientes
        cur.execute("""
            SELECT 
                analysis_date,
                llm_provider,
                COUNT(*) as total_queries,
                SUM(CASE WHEN position_in_list IS NOT NULL THEN 1 ELSE 0 END) as with_position
            FROM llm_monitoring_results
            WHERE project_id = 5
            GROUP BY analysis_date, llm_provider
            ORDER BY analysis_date DESC, llm_provider
            LIMIT 20
        """)
        
        results = cur.fetchall()
        
        logger.info("=" * 70)
        logger.info("📅 HISTORIAL DE ANÁLISIS - PROYECTO #5 (HM Fertility)")
        logger.info("=" * 70)
        logger.info("")
        logger.info("   Fecha       | LLM          | Queries | Con Posición")
        logger.info("   " + "-" * 60)
        
        for r in results:
            date = r['analysis_date'].strftime('%Y-%m-%d')
            llm = (r['llm_provider'] or 'Unknown')[:12].ljust(12)
            queries = str(r['total_queries']).rjust(7)
            with_pos = str(r['with_position']).rjust(12)
            
            logger.info(f"   {date} | {llm} | {queries} | {with_pos}")
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("")
        
        # Contar total
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN position_in_list IS NOT NULL THEN 1 ELSE 0 END) as with_position
            FROM llm_monitoring_results
            WHERE project_id = 5
        """)
        
        totals = cur.fetchone()
        
        logger.info(f"📊 TOTALES:")
        logger.info(f"   Total queries analizadas: {totals['total']}")
        logger.info(f"   Con posición detectada: {totals['with_position']}")
        logger.info(f"   Tasa de detección: {totals['with_position']/totals['total']*100:.1f}%")
        logger.info("")
    
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    check_analysis_dates()

