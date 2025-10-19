#!/usr/bin/env python3
"""
Script para forzar análisis de la keyword 'qipu' y verificar detección de getquipu.com
"""

import os
import sys
from datetime import date

# Añadir el directorio padre al path para imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection
from ai_mode_projects.services.analysis_service import AnalysisService

def force_qipu_analysis():
    """Forzar análisis de keyword 'qipu' y mostrar resultados"""
    
    print("\n" + "="*80)
    print("FORZAR ANÁLISIS: Keyword 'qipu' para proyecto ID 1")
    print("="*80 + "\n")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 1. Obtener proyecto
    cur.execute("""
        SELECT id, name, brand_name, country_code
        FROM ai_mode_projects
        WHERE id = 1
    """)
    project = dict(cur.fetchone())
    
    print(f"📋 PROYECTO:")
    print(f"   ID: {project['id']}")
    print(f"   Nombre: {project['name']}")
    print(f"   Brand: {project['brand_name']}")
    print(f"   País: {project['country_code']}")
    print()
    
    # 2. Obtener keyword 'qipu'
    cur.execute("""
        SELECT id, keyword
        FROM ai_mode_keywords
        WHERE project_id = 1 AND keyword = 'qipu'
    """)
    keyword_row = cur.fetchone()
    
    if not keyword_row:
        print("❌ Keyword 'qipu' no encontrada")
        cur.close()
        conn.close()
        return
    
    keyword_id = keyword_row['id']
    keyword = keyword_row['keyword']
    
    print(f"🔑 KEYWORD:")
    print(f"   ID: {keyword_id}")
    print(f"   Texto: '{keyword}'")
    print()
    
    # 3. Ejecutar análisis
    print("🚀 Iniciando análisis con Google AI Mode...")
    print()
    
    service = AnalysisService()
    
    try:
        ai_result, serp_data = service._analyze_keyword(
            keyword=keyword,
            project=project,
            keyword_id=keyword_id
        )
        
        print("="*80)
        print("RESULTADO DEL ANÁLISIS:")
        print("="*80 + "\n")
        
        print(f"✅ Análisis completado")
        print(f"   Brand Mentioned: {ai_result.get('brand_mentioned')}")
        print(f"   Mention Position: {ai_result.get('mention_position')}")
        print(f"   Total Sources: {ai_result.get('total_sources')}")
        print(f"   Sentiment: {ai_result.get('sentiment')}")
        print()
        
        if ai_result.get('mention_context'):
            print(f"📝 Contexto de mención:")
            print(f"   {ai_result.get('mention_context')[:200]}...")
            print()
        
        # 4. Mostrar references para debug
        if 'references' in serp_data:
            references = serp_data['references']
            print(f"📚 REFERENCES ({len(references)} total):")
            print()
            
            quipu_found = False
            for i, ref in enumerate(references[:15], 1):  # Mostrar primeras 15
                link = ref.get('link', '')
                title = ref.get('title', '')
                position = ref.get('position', i)
                
                # Verificar si contiene quipu
                has_quipu = 'quipu' in link.lower() or 'quipu' in title.lower()
                
                if has_quipu:
                    print(f"   ✨ #{position} (QUIPU DETECTADO):")
                    quipu_found = True
                else:
                    print(f"   #{position}:")
                
                print(f"      Link: {link[:60]}...")
                print(f"      Title: {title[:60]}...")
                print()
            
            if not quipu_found and len(references) > 15:
                print(f"   ... y {len(references) - 15} referencias más (revisa logs)")
            
        # 5. Guardar en base de datos
        print("💾 Guardando resultado en base de datos...")
        
        from ai_mode_projects.models.result_repository import ResultRepository
        
        result_repo = ResultRepository()
        result_repo.save_keyword_result(
            project_id=project['id'],
            keyword_id=keyword_id,
            keyword=keyword,
            ai_result=ai_result,
            serp_data=serp_data,
            country_code=project['country_code']
        )
        
        print("✅ Resultado guardado")
        print()
        
        # 6. Verificar en BD
        cur.execute("""
            SELECT brand_mentioned, mention_position
            FROM ai_mode_results
            WHERE project_id = %s AND keyword_id = %s AND analysis_date = %s
        """, (project['id'], keyword_id, date.today()))
        
        db_result = cur.fetchone()
        
        if db_result:
            print("🔍 VERIFICACIÓN EN BD:")
            print(f"   Brand Mentioned: {db_result['brand_mentioned']}")
            print(f"   Mention Position: {db_result['mention_position']}")
            print()
            
            if db_result['brand_mentioned']:
                print("🎉 ¡ÉXITO! getquipu.com detectado correctamente")
            else:
                print("⚠️ getquipu.com NO detectado - revisar references arriba")
        
    except Exception as e:
        print(f"❌ Error durante análisis: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    force_qipu_analysis()

