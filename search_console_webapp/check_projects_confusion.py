"""
Script para verificar la confusión entre Manual AI y AI Mode
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = "postgresql://postgres:XCkoyokCzfRlyPCFNGpfIhqteibfbojQ@caboose.proxy.rlwy.net:13631/railway"

def check_projects():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor()
    
    logger.info("=" * 80)
    logger.info("VERIFICANDO PROYECTOS EN AMBOS SISTEMAS")
    logger.info("=" * 80)
    
    # 1. Proyectos en Manual AI
    logger.info("\n📁 PROYECTOS EN MANUAL_AI_PROJECTS:")
    cur.execute("""
        SELECT id, name, domain, user_id, country_code, is_active
        FROM manual_ai_projects
        WHERE is_active = true
        ORDER BY id
    """)
    manual_ai_projects = cur.fetchall()
    
    if manual_ai_projects:
        for p in manual_ai_projects:
            logger.info(f"   ID: {p['id']} | Name: {p['name']} | Domain: {p['domain']} | User: {p['user_id']}")
            
            # Contar keywords
            cur.execute("SELECT COUNT(*) as count FROM manual_ai_keywords WHERE project_id = %s", (p['id'],))
            kw_count = cur.fetchone()['count']
            logger.info(f"      Keywords: {kw_count}")
    else:
        logger.info("   No hay proyectos en manual_ai_projects")
    
    # 2. Proyectos en AI Mode
    logger.info("\n📁 PROYECTOS EN AI_MODE_PROJECTS:")
    cur.execute("""
        SELECT id, name, brand_name, user_id, country_code, is_active
        FROM ai_mode_projects
        WHERE is_active = true
        ORDER BY id
    """)
    ai_mode_projects = cur.fetchall()
    
    if ai_mode_projects:
        for p in ai_mode_projects:
            logger.info(f"   ID: {p['id']} | Name: {p['name']} | Brand: {p['brand_name']} | User: {p['user_id']}")
            
            # Contar keywords
            cur.execute("SELECT COUNT(*) as count FROM ai_mode_keywords WHERE project_id = %s", (p['id'],))
            kw_count = cur.fetchone()['count']
            logger.info(f"      Keywords: {kw_count}")
    else:
        logger.info("   No hay proyectos en ai_mode_projects")
    
    # 3. Verificar resultados
    logger.info("\n📊 RESULTADOS:")
    
    logger.info("\n   Manual AI Results:")
    cur.execute("SELECT project_id, COUNT(*) as count FROM manual_ai_results GROUP BY project_id")
    manual_results = cur.fetchall()
    if manual_results:
        for r in manual_results:
            logger.info(f"      Project {r['project_id']}: {r['count']} results")
    else:
        logger.info("      No hay resultados en manual_ai_results")
    
    logger.info("\n   AI Mode Results:")
    cur.execute("SELECT project_id, COUNT(*) as count FROM ai_mode_results GROUP BY project_id")
    ai_results = cur.fetchall()
    if ai_results:
        for r in ai_results:
            logger.info(f"      Project {r['project_id']}: {r['count']} results")
    else:
        logger.info("      No hay resultados en ai_mode_results")
    
    logger.info("\n" + "=" * 80)
    logger.info("PROBLEMA DETECTADO:")
    logger.info("=" * 80)
    logger.info("El CRON está analizando proyectos de MANUAL AI (tabla manual_ai_projects)")
    logger.info("pero el usuario está viendo la UI de AI MODE (tabla ai_mode_projects)")
    logger.info("")
    logger.info("Proyecto Manual AI ID 17 'hm' ≠ Proyecto AI Mode ID 1 'test 1'")
    logger.info("=" * 80)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    check_projects()

