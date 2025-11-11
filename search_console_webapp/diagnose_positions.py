#!/usr/bin/env python3
"""
Script de diagnóstico para analizar por qué las posiciones aparecen como N/A
"""
import logging
from database import get_db_connection

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def diagnose_positions():
    logger.info("\n" + "="*70)
    logger.info("🔍 DIAGNÓSTICO: Detección de posiciones en LLM Monitoring")
    logger.info("="*70 + "\n")
    
    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la BD")
        return
    
    try:
        cur = conn.cursor()
        
        # 1. Estadísticas generales de posiciones
        logger.info("1️⃣ Estadísticas generales de detección de posiciones\n")
        
        cur.execute("""
            SELECT 
                llm_provider,
                COUNT(*) as total_queries,
                SUM(CASE WHEN brand_mentioned THEN 1 ELSE 0 END) as total_mentions,
                SUM(CASE WHEN position_in_list IS NOT NULL THEN 1 ELSE 0 END) as positions_detected,
                ROUND(AVG(position_in_list), 2) as avg_position
            FROM llm_monitoring_results
            WHERE analysis_date >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY llm_provider
            ORDER BY llm_provider
        """)
        
        results = cur.fetchall()
        
        if not results:
            logger.warning("⚠️  No hay resultados en los últimos 30 días")
            return
        
        logger.info("   LLM              | Queries | Menciones | Posiciones | Avg Pos")
        logger.info("   " + "-"*65)
        
        for r in results:
            llm = (r['llm_provider'] or 'Unknown')[:15].ljust(15)
            queries = str(r['total_queries']).rjust(7)
            mentions = str(r['total_mentions']).rjust(9)
            positions = str(r['positions_detected']).rjust(10)
            avg_pos = str(r['avg_position'] or 'N/A').rjust(7)
            
            logger.info(f"   {llm} | {queries} | {mentions} | {positions} | {avg_pos}")
        
        # 2. Ver ejemplos de respuestas SIN posición detectada
        logger.info("\n\n2️⃣ Ejemplos de menciones SIN posición detectada\n")
        
        cur.execute("""
            SELECT 
                llm_provider,
                query_text,
                brand_mentioned,
                mention_count,
                position_in_list,
                appears_in_numbered_list,
                LEFT(full_response, 500) as response_preview
            FROM llm_monitoring_results
            WHERE analysis_date >= CURRENT_DATE - INTERVAL '30 days'
                AND brand_mentioned = TRUE
                AND position_in_list IS NULL
            ORDER BY analysis_date DESC
            LIMIT 5
        """)
        
        examples = cur.fetchall()
        
        if not examples:
            logger.info("   ✅ ¡Todas las menciones tienen posición detectada!")
        else:
            for idx, ex in enumerate(examples, 1):
                logger.info(f"\n   📋 EJEMPLO {idx}:")
                logger.info(f"      LLM: {ex['llm_provider']}")
                logger.info(f"      Query: {ex['query_text']}")
                logger.info(f"      Menciones: {ex['mention_count']}")
                logger.info(f"      En lista: {ex['appears_in_numbered_list']}")
                logger.info(f"      Posición: {ex['position_in_list']}")
                logger.info(f"      Respuesta (primeros 500 chars):")
                logger.info(f"      ---")
                logger.info(f"      {ex['response_preview']}")
                logger.info(f"      ---")
        
        # 3. Ver ejemplos de respuestas CON posición detectada
        logger.info("\n\n3️⃣ Ejemplos de menciones CON posición detectada\n")
        
        cur.execute("""
            SELECT 
                llm_provider,
                query_text,
                brand_mentioned,
                mention_count,
                position_in_list,
                appears_in_numbered_list,
                total_items_in_list,
                LEFT(full_response, 500) as response_preview
            FROM llm_monitoring_results
            WHERE analysis_date >= CURRENT_DATE - INTERVAL '30 days'
                AND brand_mentioned = TRUE
                AND position_in_list IS NOT NULL
            ORDER BY analysis_date DESC
            LIMIT 3
        """)
        
        examples_with_pos = cur.fetchall()
        
        if not examples_with_pos:
            logger.warning("   ⚠️  No hay menciones con posición detectada")
        else:
            for idx, ex in enumerate(examples_with_pos, 1):
                logger.info(f"\n   📋 EJEMPLO {idx}:")
                logger.info(f"      LLM: {ex['llm_provider']}")
                logger.info(f"      Query: {ex['query_text']}")
                logger.info(f"      Menciones: {ex['mention_count']}")
                logger.info(f"      En lista: {ex['appears_in_numbered_list']}")
                logger.info(f"      Posición: {ex['position_in_list']}")
                logger.info(f"      Total items: {ex['total_items_in_list']}")
                logger.info(f"      Respuesta (primeros 500 chars):")
                logger.info(f"      ---")
                logger.info(f"      {ex['response_preview']}")
                logger.info(f"      ---")
        
        # 4. Verificar snapshots
        logger.info("\n\n4️⃣ Verificar datos en snapshots\n")
        
        cur.execute("""
            SELECT 
                llm_provider,
                snapshot_date,
                total_queries,
                total_mentions,
                avg_position,
                appeared_in_top3,
                appeared_in_top5,
                appeared_in_top10
            FROM llm_monitoring_snapshots
            WHERE snapshot_date >= CURRENT_DATE - INTERVAL '7 days'
            ORDER BY snapshot_date DESC, llm_provider
            LIMIT 10
        """)
        
        snapshots = cur.fetchall()
        
        if not snapshots:
            logger.warning("   ⚠️  No hay snapshots en los últimos 7 días")
        else:
            logger.info("   LLM          | Fecha      | Queries | Menciones | Avg Pos | Top3/5/10")
            logger.info("   " + "-"*75)
            
            for s in snapshots:
                llm = (s['llm_provider'] or 'Unknown')[:12].ljust(12)
                date = s['snapshot_date'].strftime('%Y-%m-%d')
                queries = str(s['total_queries']).rjust(7)
                mentions = str(s['total_mentions']).rjust(9)
                avg_pos = str(s['avg_position'] or 'N/A').rjust(7)
                tops = f"{s['appeared_in_top3']}/{s['appeared_in_top5']}/{s['appeared_in_top10']}"
                
                logger.info(f"   {llm} | {date} | {queries} | {mentions} | {avg_pos} | {tops}")
        
        logger.info("\n" + "="*70)
        logger.info("✅ DIAGNÓSTICO COMPLETADO")
        logger.info("="*70 + "\n")
        
        # Resumen y recomendaciones
        logger.info("📊 RESUMEN:\n")
        
        total_mentions_all = sum(r['total_mentions'] for r in results)
        total_positions_all = sum(r['positions_detected'] for r in results)
        
        if total_mentions_all == 0:
            logger.info("   ⚠️  No hay menciones en los últimos 30 días")
        else:
            detection_rate = (total_positions_all / total_mentions_all * 100) if total_mentions_all > 0 else 0
            logger.info(f"   Total de menciones: {total_mentions_all}")
            logger.info(f"   Posiciones detectadas: {total_positions_all}")
            logger.info(f"   Tasa de detección: {detection_rate:.1f}%")
            logger.info("")
            
            if detection_rate < 10:
                logger.warning("   ⚠️  PROBLEMA CRÍTICO: Muy pocas posiciones detectadas")
                logger.warning("   Posibles causas:")
                logger.warning("     1. Las respuestas de LLMs no tienen formato de lista")
                logger.warning("     2. El algoritmo de detección necesita ajustes")
                logger.warning("     3. La mayoría de menciones son en texto corrido (sin lista)")
                logger.warning("")
                logger.warning("   💡 RECOMENDACIÓN:")
                logger.warning("     - Revisar ejemplos de respuestas arriba")
                logger.warning("     - Ajustar algoritmo _detect_position_in_list si es necesario")
                logger.warning("     - Considerar si es normal que muchas respuestas no tengan listas")
            elif detection_rate < 50:
                logger.info("   ℹ️  Tasa de detección moderada")
                logger.info("     Esto es normal si muchos LLMs responden en texto corrido")
            else:
                logger.info("   ✅ Buena tasa de detección de posiciones")
    
    except Exception as e:
        logger.error(f"\n❌ Error durante el diagnóstico: {e}", exc_info=True)
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    diagnose_positions()

