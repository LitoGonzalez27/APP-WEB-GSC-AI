"""
Script para diagnosticar datos en AI Mode
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Conexión directa a Railway
DATABASE_URL = "postgresql://postgres:XCkoyokCzfRlyPCFNGpfIhqteibfbojQ@caboose.proxy.rlwy.net:13631/railway"

def check_ai_mode_data():
    """Verificar datos en tablas de AI Mode"""
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        cur = conn.cursor()
        
        logger.info("=" * 80)
        logger.info("DIAGNÓSTICO DE DATOS AI MODE")
        logger.info("=" * 80)
        
        # 1. Verificar si las tablas existen
        logger.info("\n📋 VERIFICANDO EXISTENCIA DE TABLAS:")
        tables = ['ai_mode_projects', 'ai_mode_keywords', 'ai_mode_results', 'ai_mode_events', 'ai_mode_snapshots']
        for table in tables:
            cur.execute(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = '{table}'
                )
            """)
            exists = cur.fetchone()['exists']
            logger.info(f"   {'✅' if exists else '❌'} {table}: {'Existe' if exists else 'NO EXISTE'}")
        
        # 2. Verificar proyectos
        logger.info("\n📁 PROYECTOS AI MODE:")
        cur.execute("""
            SELECT id, name, brand_name, user_id, country_code, created_at, is_active,
                   selected_competitors
            FROM ai_mode_projects
            ORDER BY created_at DESC
            LIMIT 5
        """)
        projects = cur.fetchall()
        
        if projects:
            logger.info(f"   Total proyectos activos: {len(projects)}")
            for p in projects:
                competitors_count = len(p['selected_competitors']) if p['selected_competitors'] else 0
                logger.info(f"   📌 ID: {p['id']} | Nombre: {p['name']} | Brand: {p['brand_name']} | User: {p['user_id']}")
                logger.info(f"      País: {p['country_code']} | Media Sources: {competitors_count} | Activo: {p['is_active']}")
                if p['selected_competitors']:
                    logger.info(f"      Competidores: {p['selected_competitors']}")
        else:
            logger.warning("   ⚠️ NO HAY PROYECTOS")
        
        # 3. Verificar keywords por proyecto
        if projects:
            logger.info("\n🔑 KEYWORDS POR PROYECTO:")
            for p in projects:
                cur.execute("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(CASE WHEN is_active = true THEN 1 END) as active
                    FROM ai_mode_keywords
                    WHERE project_id = %s
                """, (p['id'],))
                kw_stats = cur.fetchone()
                logger.info(f"   Proyecto {p['id']} ({p['name']}): {kw_stats['total']} keywords ({kw_stats['active']} activas)")
                
                # Mostrar algunas keywords de ejemplo
                cur.execute("""
                    SELECT keyword, is_active
                    FROM ai_mode_keywords
                    WHERE project_id = %s
                    LIMIT 5
                """, (p['id'],))
                sample_kws = cur.fetchall()
                if sample_kws:
                    for kw in sample_kws:
                        status = "✅" if kw['is_active'] else "❌"
                        logger.info(f"      {status} {kw['keyword']}")
        
        # 4. Verificar resultados de análisis
        if projects:
            logger.info("\n📊 RESULTADOS DE ANÁLISIS:")
            for p in projects:
                cur.execute("""
                    SELECT 
                        COUNT(DISTINCT analysis_date) as num_analyses,
                        MIN(analysis_date) as first_analysis,
                        MAX(analysis_date) as last_analysis,
                        COUNT(*) as total_results,
                        COUNT(CASE WHEN brand_mentioned = true THEN 1 END) as brand_mentions
                    FROM ai_mode_results
                    WHERE project_id = %s
                """, (p['id'],))
                results = cur.fetchone()
                
                if results['num_analyses'] and results['num_analyses'] > 0:
                    logger.info(f"   Proyecto {p['id']} ({p['name']}):")
                    logger.info(f"      📈 Total análisis: {results['num_analyses']}")
                    logger.info(f"      📅 Primer análisis: {results['first_analysis']}")
                    logger.info(f"      📅 Último análisis: {results['last_analysis']}")
                    logger.info(f"      📊 Total resultados: {results['total_results']}")
                    logger.info(f"      ✨ Brand mentions: {results['brand_mentions']}")
                else:
                    logger.warning(f"   ⚠️ Proyecto {p['id']} ({p['name']}): NO HAY RESULTADOS DE ANÁLISIS")
        
        # 5. Verificar datos del último análisis
        if projects:
            logger.info("\n🔍 ÚLTIMO ANÁLISIS DETALLADO:")
            for p in projects:
                cur.execute("""
                    SELECT 
                        k.keyword,
                        r.analysis_date,
                        r.brand_mentioned,
                        r.mention_position,
                        r.serp_data
                    FROM ai_mode_keywords k
                    LEFT JOIN ai_mode_results r ON k.id = r.keyword_id
                    WHERE k.project_id = %s
                    AND r.analysis_date = (
                        SELECT MAX(analysis_date) 
                        FROM ai_mode_results 
                        WHERE project_id = %s
                    )
                    LIMIT 10
                """, (p['id'], p['id']))
                
                latest_results = cur.fetchall()
                if latest_results:
                    logger.info(f"   Proyecto {p['id']} - Últimos resultados ({latest_results[0]['analysis_date']}):")
                    for r in latest_results:
                        mention_status = "✅ Mencionado" if r['brand_mentioned'] else "❌ No mencionado"
                        position = f"Posición {r['mention_position']}" if r['mention_position'] else "Sin posición"
                        logger.info(f"      • {r['keyword']}: {mention_status} | {position}")
                else:
                    logger.warning(f"   ⚠️ Proyecto {p['id']}: Sin datos del último análisis")
        
        # 6. Verificar eventos
        logger.info("\n📝 EVENTOS RECIENTES:")
        cur.execute("""
            SELECT event_date, event_type, event_title, project_id
            FROM ai_mode_events
            ORDER BY event_date DESC
            LIMIT 10
        """)
        events = cur.fetchall()
        if events:
            for e in events:
                logger.info(f"   {e['event_date']} | Proyecto {e['project_id']} | {e['event_type']}: {e['event_title']}")
        else:
            logger.info("   ℹ️ No hay eventos registrados")
        
        logger.info("\n" + "=" * 80)
        logger.info("DIAGNÓSTICO COMPLETADO")
        logger.info("=" * 80)
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Error durante diagnóstico: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == '__main__':
    check_ai_mode_data()

