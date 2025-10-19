"""
Script para verificar el sistema de detección de marca en AI Mode
"""
import sys
from database import get_db_connection
import json

def verify_brand_detection(project_id: int):
    """Verificar detección de marca para un proyecto"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Obtener info del proyecto
    cur.execute("""
        SELECT id, brand_name, domain 
        FROM ai_mode_projects 
        WHERE id = %s
    """, (project_id,))
    
    project = dict(cur.fetchone() or {})
    if not project:
        print(f"❌ Proyecto {project_id} no encontrado")
        return
    
    print(f"\n{'='*60}")
    print(f"📊 VERIFICACIÓN DE DETECCIÓN DE MARCA EN AI MODE")
    print(f"{'='*60}")
    print(f"Proyecto: {project['brand_name']}")
    print(f"Dominio: {project['domain']}")
    print(f"{'='*60}\n")
    
    # Obtener últimos 10 resultados con datos raw
    cur.execute("""
        SELECT 
            k.keyword,
            r.analysis_date,
            r.brand_mentioned,
            r.mention_position,
            r.raw_ai_mode_data
        FROM ai_mode_results r
        JOIN ai_mode_keywords k ON r.keyword_id = k.id
        WHERE r.project_id = %s
            AND r.raw_ai_mode_data IS NOT NULL
        ORDER BY r.analysis_date DESC
        LIMIT 10
    """, (project_id,))
    
    results = cur.fetchall()
    
    if not results:
        print("⚠️  No hay resultados de análisis disponibles")
        return
    
    print(f"📋 Analizando últimos {len(results)} resultados:\n")
    
    for idx, row in enumerate(results, 1):
        keyword = row['keyword']
        date = row['analysis_date']
        mentioned = row['brand_mentioned']
        position = row['mention_position']
        raw_data = row['raw_ai_mode_data'] or {}
        
        text_blocks = raw_data.get('text_blocks', [])
        references = raw_data.get('references', [])
        
        print(f"{idx}. Keyword: '{keyword}' ({date})")
        print(f"   Brand Mentioned: {'✅ SÍ' if mentioned else '❌ NO'}")
        if mentioned:
            print(f"   Position: {position if position else 'N/A'}")
        print(f"   Text Blocks: {len(text_blocks)}")
        print(f"   References: {len(references)}")
        
        # Verificar si hay menciones de la marca en las referencias
        brand_lower = project['brand_name'].lower()
        brand_refs = []
        for ref in references:
            title = str(ref.get('title', '')).lower()
            link = str(ref.get('link', '')).lower()
            source = str(ref.get('source', '')).lower()
            
            if brand_lower in title or brand_lower in link or brand_lower in source:
                brand_refs.append(ref)
        
        if brand_refs:
            print(f"   🎯 Referencias con marca:")
            for ref in brand_refs:
                print(f"      - {ref.get('title', 'Sin título')}")
                print(f"        URL: {ref.get('link', 'Sin URL')}")
                print(f"        Position: {ref.get('position', 'N/A')}")
        
        print()
    
    # Estadísticas generales
    cur.execute("""
        SELECT 
            COUNT(*) as total_keywords,
            COUNT(CASE WHEN brand_mentioned = true THEN 1 END) as with_brand,
            (COUNT(CASE WHEN brand_mentioned = true THEN 1 END)::float / 
             NULLIF(COUNT(*), 0)::float * 100) as visibility_pct
        FROM ai_mode_results r
        WHERE r.project_id = %s
            AND r.analysis_date >= CURRENT_DATE - INTERVAL '30 days'
    """, (project_id,))
    
    stats = dict(cur.fetchone() or {})
    
    print(f"\n{'='*60}")
    print(f"📈 ESTADÍSTICAS ÚLTIMOS 30 DÍAS")
    print(f"{'='*60}")
    print(f"Total análisis: {stats['total_keywords']}")
    print(f"Con mención de marca: {stats['with_brand']}")
    print(f"Visibilidad: {stats['visibility_pct']:.2f}%")
    print(f"{'='*60}\n")
    
    # URLs más mencionadas
    from ai_mode_projects.services.statistics_service import StatisticsService
    stats_service = StatisticsService()
    urls_ranking = stats_service.get_project_urls_ranking(project_id, days=30, limit=10)
    
    if urls_ranking:
        print(f"\n{'='*60}")
        print(f"🔗 TOP 10 URLs MÁS MENCIONADAS")
        print(f"{'='*60}")
        for url_data in urls_ranking:
            print(f"{url_data['rank']}. {url_data['url']}")
            print(f"   Menciones: {url_data['mentions']} ({url_data['percentage']}%)")
            print(f"   Posición Promedio: {url_data['avg_position'] if url_data['avg_position'] else 'N/A'}")
            
            # Verificar si es del dominio del proyecto
            if project['domain'].lower() in url_data['url'].lower():
                print(f"   ✅ ES TU DOMINIO")
            print()
        print(f"{'='*60}\n")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso: python verify_ai_mode_brand_detection.py <project_id>")
        print("Ejemplo: python verify_ai_mode_brand_detection.py 1")
        sys.exit(1)
    
    project_id = int(sys.argv[1])
    verify_brand_detection(project_id)

