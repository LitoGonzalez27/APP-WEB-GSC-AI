"""
Script para diagnosticar el endpoint de comparative charts
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import logging
import json
from datetime import date, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = "postgresql://postgres:XCkoyokCzfRlyPCFNGpfIhqteibfbojQ@caboose.proxy.rlwy.net:13631/railway"

def test_comparative_charts_endpoint(project_id=1, days=30):
    """Simular la query del endpoint /comparative-charts"""
    
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor()
    
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    logger.info("=" * 80)
    logger.info(f"SIMULANDO ENDPOINT: /api/projects/{project_id}/comparative-charts?days={days}")
    logger.info("=" * 80)
    
    # 1. Obtener project info
    cur.execute("""
        SELECT brand_name, selected_competitors
        FROM ai_mode_projects
        WHERE id = %s
    """, (project_id,))
    
    project = cur.fetchone()
    logger.info(f"\n📦 PROJECT INFO:")
    logger.info(f"   Brand: {project['brand_name']}")
    logger.info(f"   Selected Competitors: {project['selected_competitors']}")
    
    # 2. Query para visibilidad del proyecto (user's domain)
    logger.info(f"\n📊 VISIBILITY DATA FOR PROJECT DOMAIN:")
    cur.execute("""
        SELECT 
            r.analysis_date,
            COUNT(DISTINCT CASE WHEN r.brand_mentioned = true THEN r.keyword_id END) as mentions,
            COUNT(DISTINCT r.keyword_id) as total_keywords,
            (COUNT(DISTINCT CASE WHEN r.brand_mentioned = true THEN r.keyword_id END)::float / 
             NULLIF(COUNT(DISTINCT r.keyword_id), 0)::float * 100) as visibility_percentage
        FROM ai_mode_results r
        WHERE r.project_id = %s
            AND r.analysis_date >= %s AND r.analysis_date <= %s
        GROUP BY r.analysis_date
        ORDER BY r.analysis_date
    """, (project_id, start_date, end_date))
    
    user_visibility = [dict(row) for row in cur.fetchall()]
    logger.info(f"   Total data points: {len(user_visibility)}")
    for v in user_visibility:
        logger.info(f"   • {v['analysis_date']}: mentions={v['mentions']}, total={v['total_keywords']}, visibility={v['visibility_percentage']}%")
    
    # 3. Query para posición del proyecto
    logger.info(f"\n📍 POSITION DATA FOR PROJECT DOMAIN:")
    cur.execute("""
        SELECT 
            r.analysis_date,
            AVG(r.mention_position) as avg_position
        FROM ai_mode_results r
        WHERE r.project_id = %s
            AND r.analysis_date >= %s AND r.analysis_date <= %s
            AND r.brand_mentioned = true
        GROUP BY r.analysis_date
        ORDER BY r.analysis_date
    """, (project_id, start_date, end_date))
    
    user_position = [dict(row) for row in cur.fetchall()]
    logger.info(f"   Total data points: {len(user_position)}")
    for p in user_position:
        logger.info(f"   • {p['analysis_date']}: avg_position={p['avg_position']}")
    
    # 4. Verificar selected_competitors
    selected_competitors = project.get('selected_competitors') or []
    logger.info(f"\n🏢 SELECTED COMPETITORS: {selected_competitors}")
    logger.info(f"   Total competitors: {len(selected_competitors)}")
    
    if not selected_competitors:
        logger.warning("   ⚠️ NO HAY COMPETIDORES SELECCIONADOS")
    
    # 5. Query para competidores
    if selected_competitors:
        logger.info(f"\n📊 COMPETITORS DATA:")
        for competitor in selected_competitors:
            logger.info(f"\n   Competitor: {competitor}")
            cur.execute("""
                SELECT 
                    r.analysis_date,
                    COUNT(DISTINCT CASE WHEN ms.domain = %s THEN r.keyword_id END) as mentions,
                    COUNT(DISTINCT r.keyword_id) as total_keywords
                FROM ai_mode_results r
                LEFT JOIN LATERAL jsonb_array_elements(r.media_sources::jsonb) AS ms(domain) ON true
                WHERE r.project_id = %s
                    AND r.analysis_date >= %s AND r.analysis_date <= %s
                GROUP BY r.analysis_date
                ORDER BY r.analysis_date
            """, (competitor, project_id, start_date, end_date))
            
            competitor_data = [dict(row) for row in cur.fetchall()]
            logger.info(f"      Data points: {len(competitor_data)}")
            for d in competitor_data[:3]:
                visibility_pct = (d['mentions'] / d['total_keywords'] * 100) if d['total_keywords'] > 0 else 0
                logger.info(f"      • {d['analysis_date']}: mentions={d['mentions']}, total={d['total_keywords']}, visibility={visibility_pct}%")
    
    # 6. Construir estructura de respuesta
    logger.info(f"\n📦 ESTRUCTURA DE RESPUESTA:")
    
    # Dates
    dates = sorted(list(set([v['analysis_date'] for v in user_visibility])))
    logger.info(f"   Dates: {dates}")
    
    # Visibility chart
    visibility_datasets = []
    
    # User domain dataset
    user_visibility_data = []
    for date_val in dates:
        matching = [v for v in user_visibility if v['analysis_date'] == date_val]
        if matching:
            user_visibility_data.append(matching[0]['visibility_percentage'])
        else:
            user_visibility_data.append(0)
    
    visibility_datasets.append({
        'label': project['brand_name'],
        'data': user_visibility_data,
        'borderColor': 'rgb(99, 102, 241)',
        'domain': 'user_domain'
    })
    
    logger.info(f"\n   Visibility Chart:")
    logger.info(f"      Datasets count: {len(visibility_datasets)}")
    logger.info(f"      User domain data: {user_visibility_data}")
    
    # Position chart
    position_datasets = []
    
    user_position_data = []
    for date_val in dates:
        matching = [p for p in user_position if p['analysis_date'] == date_val]
        if matching:
            user_position_data.append(float(matching[0]['avg_position']) if matching[0]['avg_position'] else None)
        else:
            user_position_data.append(None)
    
    position_datasets.append({
        'label': project['brand_name'],
        'data': user_position_data,
        'borderColor': 'rgb(99, 102, 241)',
        'domain': 'user_domain'
    })
    
    logger.info(f"\n   Position Chart:")
    logger.info(f"      Datasets count: {len(position_datasets)}")
    logger.info(f"      User domain data: {user_position_data}")
    
    result = {
        'success': True,
        'data': {
            'visibility_chart': {
                'dates': [str(d) for d in dates],
                'datasets': visibility_datasets
            },
            'position_chart': {
                'dates': [str(d) for d in dates],
                'datasets': position_datasets
            }
        }
    }
    
    logger.info(f"\n📋 FINAL RESULT:")
    logger.info(json.dumps(result, indent=2, default=str))
    
    logger.info("\n" + "=" * 80)
    logger.info("DIAGNÓSTICO COMPLETADO")
    logger.info("=" * 80)
    
    cur.close()
    conn.close()
    
    return result

if __name__ == '__main__':
    test_comparative_charts_endpoint()

