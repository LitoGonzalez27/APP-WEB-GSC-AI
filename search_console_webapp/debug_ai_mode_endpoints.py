"""
Script para diagnosticar los endpoints de AI Mode y verificar qué datos están devolviendo
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = "postgresql://postgres:XCkoyokCzfRlyPCFNGpfIhqteibfbojQ@caboose.proxy.rlwy.net:13631/railway"

def test_stats_endpoint_query(project_id=1, days=30):
    """Simular la query del endpoint /stats"""
    from datetime import date, timedelta
    
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor()
    
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    logger.info("=" * 80)
    logger.info(f"SIMULANDO ENDPOINT: /api/projects/{project_id}/stats?days={days}")
    logger.info("=" * 80)
    
    # 1. Main Stats
    logger.info("\n📊 MAIN STATS (Latest Results):")
    cur.execute("""
        WITH latest_results AS (
            SELECT DISTINCT ON (k.id) 
                k.id as keyword_id,
                k.is_active,
                r.brand_mentioned,
                r.mention_position,
                r.analysis_date
            FROM ai_mode_keywords k
            LEFT JOIN ai_mode_results r ON k.id = r.keyword_id 
            WHERE k.project_id = %s
            ORDER BY k.id, r.analysis_date DESC
        )
        SELECT 
            COUNT(*) as total_keywords,
            COUNT(CASE WHEN is_active = true THEN 1 END) as active_keywords,
            COUNT(CASE WHEN brand_mentioned = true THEN 1 END) as total_mentions,
            AVG(CASE WHEN mention_position IS NOT NULL THEN mention_position END) as avg_position,
            (COUNT(CASE WHEN brand_mentioned = true THEN 1 END)::float / 
             NULLIF(COUNT(CASE WHEN analysis_date IS NOT NULL THEN 1 END), 0)::float * 100) as visibility_percentage
        FROM latest_results
    """, (project_id,))
    
    main_stats = dict(cur.fetchone() or {})
    logger.info(f"   Total Keywords: {main_stats.get('total_keywords', 0)}")
    logger.info(f"   Active Keywords: {main_stats.get('active_keywords', 0)}")
    logger.info(f"   Total Mentions: {main_stats.get('total_mentions', 0)}")
    logger.info(f"   Avg Position: {main_stats.get('avg_position')}")
    logger.info(f"   Visibility %: {main_stats.get('visibility_percentage')}")
    
    # 2. Visibility Chart Data
    logger.info("\n📈 VISIBILITY CHART DATA:")
    cur.execute("""
        SELECT 
            r.analysis_date,
            COUNT(DISTINCT r.keyword_id) as total_keywords,
            COUNT(DISTINCT CASE WHEN r.brand_mentioned = true THEN r.keyword_id END) as mentions,
            (COUNT(DISTINCT CASE WHEN r.brand_mentioned = true THEN r.keyword_id END)::float / 
             NULLIF(COUNT(DISTINCT r.keyword_id), 0)::float * 100) as visibility_pct
        FROM ai_mode_results r
        WHERE r.project_id = %s AND r.analysis_date >= %s AND r.analysis_date <= %s
        GROUP BY r.analysis_date
        ORDER BY r.analysis_date
    """, (project_id, start_date, end_date))
    
    visibility_data = [dict(row) for row in cur.fetchall()]
    logger.info(f"   Total data points: {len(visibility_data)}")
    for v in visibility_data:
        logger.info(f"   • {v['analysis_date']}: total_keywords={v['total_keywords']}, mentions={v['mentions']}, visibility={v['visibility_pct']}%")
    
    if len(visibility_data) == 0:
        logger.warning("   ⚠️ NO HAY DATOS PARA GRÁFICA DE VISIBILIDAD")
    
    # 3. Position Chart Data
    logger.info("\n📊 POSITION CHART DATA:")
    cur.execute("""
        SELECT 
            r.analysis_date,
            COUNT(DISTINCT CASE WHEN r.mention_position BETWEEN 1 AND 3 THEN r.keyword_id END) as pos_1_3,
            COUNT(DISTINCT CASE WHEN r.mention_position BETWEEN 4 AND 10 THEN r.keyword_id END) as pos_4_10,
            COUNT(DISTINCT CASE WHEN r.mention_position BETWEEN 11 AND 20 THEN r.keyword_id END) as pos_11_20,
            COUNT(DISTINCT CASE WHEN r.mention_position > 20 THEN r.keyword_id END) as pos_21_plus
        FROM ai_mode_results r
        WHERE r.project_id = %s AND r.analysis_date >= %s AND r.analysis_date <= %s
            AND r.brand_mentioned = true
        GROUP BY r.analysis_date
        ORDER BY r.analysis_date
    """, (project_id, start_date, end_date))
    
    positions_data = [dict(row) for row in cur.fetchall()]
    logger.info(f"   Total data points: {len(positions_data)}")
    for p in positions_data:
        logger.info(f"   • {p['analysis_date']}: 1-3={p['pos_1_3']}, 4-10={p['pos_4_10']}, 11-20={p['pos_11_20']}, 21+={p['pos_21_plus']}")
    
    if len(positions_data) == 0:
        logger.warning("   ⚠️ NO HAY DATOS PARA GRÁFICA DE POSICIONES (Normal si no hay menciones)")
    
    # 4. Verificar estructura de datos que se devuelve
    logger.info("\n📦 ESTRUCTURA DE DATOS DEVUELTA:")
    result = {
        'main_stats': main_stats,
        'visibility_chart': visibility_data,
        'positions_chart': positions_data,
        'date_range': {
            'start': str(start_date),
            'end': str(end_date)
        }
    }
    
    logger.info(f"   Claves en respuesta: {list(result.keys())}")
    logger.info(f"   visibility_chart es lista: {isinstance(result['visibility_chart'], list)}")
    logger.info(f"   visibility_chart length: {len(result['visibility_chart'])}")
    
    # 5. Verificar datos crudos de results
    logger.info("\n🔍 DATOS CRUDOS DE ai_mode_results:")
    cur.execute("""
        SELECT 
            analysis_date,
            keyword_id,
            brand_mentioned,
            mention_position
        FROM ai_mode_results
        WHERE project_id = %s
        ORDER BY analysis_date DESC, keyword_id
        LIMIT 20
    """, (project_id,))
    
    raw_results = cur.fetchall()
    logger.info(f"   Total resultados en BD: {len(raw_results)}")
    for r in raw_results[:5]:
        logger.info(f"   • Date: {r['analysis_date']}, KW_ID: {r['keyword_id']}, Mentioned: {r['brand_mentioned']}, Position: {r['mention_position']}")
    
    logger.info("\n" + "=" * 80)
    logger.info("DIAGNÓSTICO COMPLETADO")
    logger.info("=" * 80)
    
    cur.close()
    conn.close()
    
    return result

if __name__ == '__main__':
    test_stats_endpoint_query()

