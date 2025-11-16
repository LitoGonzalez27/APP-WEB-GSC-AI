"""
Script de diagnóstico para analizar por qué las posiciones del 14 de noviembre aparecen como N/A
"""

import logging
from database import get_db_connection
from datetime import date
import json

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def diagnose_nov14_positions(project_id: int):
    """
    Analiza los resultados del 14 de noviembre para ver por qué position_in_list es NULL
    """
    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la BD")
        return
    
    try:
        cur = conn.cursor()
        
        # Obtener información del proyecto
        cur.execute("""
            SELECT name, brand_name, brand_domain, brand_keywords
            FROM llm_monitoring_projects
            WHERE id = %s
        """, (project_id,))
        
        project = cur.fetchone()
        if not project:
            logger.error(f"❌ Proyecto {project_id} no encontrado")
            return
        
        logger.info("=" * 80)
        logger.info(f"🔍 DIAGNÓSTICO DE POSICIONES - {project['name']}")
        logger.info("=" * 80)
        logger.info(f"Fecha: 14 de noviembre 2025")
        logger.info(f"Proyecto ID: {project_id}")
        logger.info(f"Brand: {project['brand_name']}")
        logger.info(f"Domain: {project['brand_domain']}")
        logger.info(f"Keywords: {project['brand_keywords']}")
        logger.info("")
        
        # Obtener resultados del 14 de noviembre
        cur.execute("""
            SELECT 
                id,
                llm_provider,
                query_text,
                brand_mentioned,
                position_in_list,
                appears_in_numbered_list,
                full_response,
                mention_contexts
            FROM llm_monitoring_results
            WHERE project_id = %s
            AND analysis_date = '2025-11-14'
            ORDER BY llm_provider, id
        """, (project_id,))
        
        results = cur.fetchall()
        
        if not results:
            logger.warning("⚠️ No hay resultados para el 14 de noviembre")
            return
        
        logger.info(f"📊 Total de resultados: {len(results)}")
        logger.info("")
        
        # Estadísticas por LLM
        by_llm = {}
        for r in results:
            llm = r['llm_provider']
            if llm not in by_llm:
                by_llm[llm] = {
                    'total': 0,
                    'mentioned': 0,
                    'with_position': 0,
                    'without_position': 0,
                    'examples_no_position': []
                }
            
            by_llm[llm]['total'] += 1
            if r['brand_mentioned']:
                by_llm[llm]['mentioned'] += 1
            
            if r['position_in_list'] is not None:
                by_llm[llm]['with_position'] += 1
            elif r['brand_mentioned']:  # Solo contar si fue mencionado
                by_llm[llm]['without_position'] += 1
                # Guardar ejemplo
                if len(by_llm[llm]['examples_no_position']) < 2:
                    by_llm[llm]['examples_no_position'].append({
                        'query': r['query_text'][:80] + '...' if len(r['query_text']) > 80 else r['query_text'],
                        'response': r['full_response'][:300] + '...' if r['full_response'] and len(r['full_response']) > 300 else (r['full_response'] or 'NO RESPONSE'),
                        'contexts': r['mention_contexts'] or []
                    })
        
        # Mostrar estadísticas
        logger.info("=" * 80)
        logger.info("📊 ESTADÍSTICAS POR LLM")
        logger.info("=" * 80)
        logger.info("")
        
        for llm, stats in by_llm.items():
            logger.info(f"🤖 {llm.upper()}")
            logger.info(f"   Total queries: {stats['total']}")
            logger.info(f"   Menciones: {stats['mentioned']}")
            logger.info(f"   ✅ Con posición: {stats['with_position']}")
            logger.info(f"   ❌ Sin posición: {stats['without_position']}")
            
            if stats['without_position'] > 0:
                logger.info("")
                logger.info(f"   📝 EJEMPLOS DE RESPUESTAS SIN POSICIÓN:")
                for idx, example in enumerate(stats['examples_no_position'], 1):
                    logger.info(f"")
                    logger.info(f"   Ejemplo {idx}:")
                    logger.info(f"   Query: {example['query']}")
                    logger.info(f"   Response preview: {example['response'][:200]}...")
                    if example['contexts']:
                        logger.info(f"   Contexts: {example['contexts'][0][:100]}...")
                    logger.info("")
            
            logger.info("")
        
        # Verificar snapshots
        logger.info("=" * 80)
        logger.info("📸 SNAPSHOTS DEL 14 DE NOVIEMBRE")
        logger.info("=" * 80)
        logger.info("")
        
        cur.execute("""
            SELECT 
                llm_provider,
                total_queries,
                total_mentions,
                avg_position,
                mention_rate
            FROM llm_monitoring_snapshots
            WHERE project_id = %s
            AND snapshot_date = '2025-11-14'
            ORDER BY llm_provider
        """, (project_id,))
        
        snapshots = cur.fetchall()
        
        for snap in snapshots:
            logger.info(f"🤖 {snap['llm_provider'].upper()}")
            logger.info(f"   Queries: {snap['total_queries']}")
            logger.info(f"   Mentions: {snap['total_mentions']}")
            logger.info(f"   Mention Rate: {snap['mention_rate']}%")
            logger.info(f"   Avg Position: {snap['avg_position'] or 'N/A'} ⬅️ {'❌ NULL' if snap['avg_position'] is None else '✅ OK'}")
            logger.info("")
        
        logger.info("=" * 80)
        logger.info("💡 DIAGNÓSTICO")
        logger.info("=" * 80)
        logger.info("")
        
        total_without_position = sum(stats['without_position'] for stats in by_llm.values())
        total_with_mention = sum(stats['mentioned'] for stats in by_llm.values())
        
        if total_without_position > 0:
            percentage = (total_without_position / total_with_mention * 100) if total_with_mention > 0 else 0
            logger.info(f"⚠️ {total_without_position} de {total_with_mention} menciones ({percentage:.1f}%) NO tienen posición detectada")
            logger.info("")
            logger.info("Posibles causas:")
            logger.info("1. Las respuestas fueron en formato narrativo (sin listas)")
            logger.info("2. La marca no aparece en el texto de la respuesta")
            logger.info("3. La marca solo aparece en URLs/sources pero no en texto")
            logger.info("4. Error en la detección de brand_variations")
        else:
            logger.info("✅ Todas las menciones tienen posición detectada")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        if conn:
            conn.close()

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Uso: python diagnose_nov14_positions.py <project_id>")
        print("Ejemplo: python diagnose_nov14_positions.py 1")
        sys.exit(1)
    
    project_id = int(sys.argv[1])
    diagnose_nov14_positions(project_id)

