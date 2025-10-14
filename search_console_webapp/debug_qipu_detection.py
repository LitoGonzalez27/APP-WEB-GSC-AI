#!/usr/bin/env python3
"""
Script para depurar por qué no se detecta getquipu.com para la keyword 'qipu'
"""

from database import get_db_connection

def debug_qipu():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("DEBUG: Detección de getquipu.com para keyword 'qipu'")
    print("="*80 + "\n")
    
    # 1. Verificar configuración del proyecto
    cur.execute("""
        SELECT id, name, brand_name
        FROM ai_mode_projects
        WHERE id = 1
    """)
    project = cur.fetchone()
    
    print("📋 PROYECTO:")
    print(f"   ID: {project['id']}")
    print(f"   Nombre: {project['name']}")
    print(f"   Brand Name: '{project['brand_name']}'")
    print()
    
    # 2. Buscar la keyword 'qipu'
    cur.execute("""
        SELECT id, keyword, is_active
        FROM ai_mode_keywords
        WHERE project_id = 1 AND keyword ILIKE '%qipu%'
    """)
    keywords = cur.fetchall()
    
    print("🔑 KEYWORDS que contienen 'qipu':")
    for kw in keywords:
        print(f"   ID: {kw['id']} | Keyword: '{kw['keyword']}' | Activo: {kw['is_active']}")
    print()
    
    if not keywords:
        print("❌ No se encontró ninguna keyword con 'qipu'")
        cur.close()
        conn.close()
        return
    
    # 3. Ver resultados de análisis para esta keyword
    keyword_id = keywords[0]['id']
    keyword_text = keywords[0]['keyword']
    
    cur.execute("""
        SELECT 
            id,
            analysis_date,
            brand_mentioned,
            mention_position,
            total_sources,
            raw_ai_mode_data
        FROM ai_mode_results
        WHERE project_id = 1 AND keyword_id = %s
        ORDER BY analysis_date DESC
        LIMIT 1
    """, (keyword_id,))
    
    result = cur.fetchone()
    
    if not result:
        print(f"❌ No hay resultados de análisis para '{keyword_text}'")
        cur.close()
        conn.close()
        return
    
    print(f"📊 ÚLTIMO ANÁLISIS para '{keyword_text}':")
    print(f"   Fecha: {result['analysis_date']}")
    print(f"   Brand Mentioned: {result['brand_mentioned']}")
    print(f"   Mention Position: {result['mention_position']}")
    print(f"   Total Sources: {result['total_sources']}")
    print()
    
    # 4. Examinar raw_ai_mode_data
    if result['raw_ai_mode_data']:
        data = result['raw_ai_mode_data']
        
        print("📦 RAW AI MODE DATA:")
        print(f"   Keys disponibles: {list(data.keys())}")
        print()
        
        # Ver si hay error
        if 'error' in data:
            print(f"   ❌ ERROR en datos: {data['error']}")
            print()
        
        # Ver text_blocks
        text_blocks = data.get('text_blocks', [])
        print(f"   text_blocks: {len(text_blocks)} bloques")
        for i, block in enumerate(text_blocks[:2], 1):
            text = block.get('text', '')[:200]
            print(f"      Block {i}: {text}...")
        print()
        
        # Ver references
        references = data.get('references', [])
        print(f"   references: {len(references)} referencias")
        print()
        
        if references:
            print("   🔍 BUSCANDO 'quipu' y 'getquipu' en references:")
            brand_name = project['brand_name'].lower()
            
            for i, ref in enumerate(references, 1):
                link = ref.get('link', '')
                title = ref.get('title', '')
                source = ref.get('source', '')
                position = ref.get('position', 0)
                
                # Verificar si contiene quipu o getquipu
                has_quipu = 'quipu' in link.lower() or 'quipu' in title.lower() or 'quipu' in source.lower()
                has_getquipu = 'getquipu' in link.lower()
                
                if has_quipu or has_getquipu:
                    print(f"\n      ✅ Referencia {i} (position {position}):")
                    print(f"         Link: {link}")
                    print(f"         Title: {title[:80]}...")
                    print(f"         Source: {source}")
                    print(f"         Contiene 'quipu': {has_quipu}")
                    print(f"         Contiene 'getquipu': {has_getquipu}")
                    
                    # Verificar lógica de detección
                    brand_detected = brand_name in title.lower() or brand_name in link.lower() or brand_name in source.lower()
                    print(f"         ¿Detectado con brand_name '{brand_name}'?: {brand_detected}")
        
        print()
        print("="*80)
        print("ANÁLISIS:")
        print("="*80)
        
        if result['brand_mentioned']:
            print("✅ La marca SÍ fue detectada en el análisis")
        else:
            print("❌ La marca NO fue detectada en el análisis")
            
            # Ver por qué no se detectó
            if 'error' in data:
                print("   Causa: Hay un error en los datos de SERPAPI")
            elif not references:
                print("   Causa: No hay references en los datos")
            else:
                print("   Causa posible: La lógica de detección no encontró coincidencia")
                print(f"   Brand name buscado: '{project['brand_name']}'")
                print("   Verifica si hay alguna referencia con 'quipu' arriba")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    debug_qipu()

