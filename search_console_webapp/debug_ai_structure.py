#!/usr/bin/env python3
"""
Script para examinar en detalle la estructura del AI Overview de SERPAPI
para entender por qué no detecta las fuentes
"""

import os
import json
import logging
from dotenv import load_dotenv

load_dotenv()

from services.serp_service import get_serp_json
from services.country_config import get_country_config

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

def examine_ai_structure():
    """Examinar estructura detallada del AI Overview"""
    
    keyword = "reserva ovárica"
    country = "esp"
    api_key = os.getenv('SERPAPI_KEY') or 'c4e7fb7d18a8972fcc86098a1698f0fd5c4e4069d7e049c6fb130cccf8acfab0'
    
    print("🔍 EXAMINANDO ESTRUCTURA AI OVERVIEW EN DETALLE")
    print("="*60)
    print(f"Keyword: {keyword}")
    print()
    
    # Obtener datos SERP
    country_config = get_country_config(country)
    params = {
        'q': keyword,
        'api_key': api_key,
        'engine': 'google',
        'hl': 'es',
        'gl': 'es', 
        'location': country_config.get('serp_location', 'Spain'),
        'google_domain': 'google.es'
    }
    
    print(f"📡 Parámetros SERP: {params}")
    print()
    
    serp_data = get_serp_json(params)
    
    if not serp_data or 'error' in serp_data:
        print("❌ Error obteniendo datos SERP")
        return
    
    # Guardar datos completos para análisis
    with open('debug_ai_complete.json', 'w', encoding='utf-8') as f:
        json.dump(serp_data, f, indent=2, ensure_ascii=False)
    
    print("💾 Datos completos guardados en: debug_ai_complete.json")
    print()
    
    # Examinar AI Overview
    ai_overview = serp_data.get('ai_overview')
    if not ai_overview:
        print("❌ No hay ai_overview en los datos")
        return
    
    print("🤖 ESTRUCTURA AI OVERVIEW:")
    print("-"*40)
    
    # Claves principales
    print(f"Claves en ai_overview: {list(ai_overview.keys())}")
    print()
    
    # Text blocks
    text_blocks = ai_overview.get('text_blocks', [])
    print(f"📝 Text blocks: {len(text_blocks)}")
    
    for i, block in enumerate(text_blocks):
        print(f"\n--- Text Block {i+1} ---")
        print(f"Type: {block.get('type', 'N/A')}")
        print(f"Snippet: {block.get('snippet', '')[:100]}...")
        print(f"Reference indexes: {block.get('reference_indexes', [])}")
        
        # Si es una lista, examinar elementos
        if block.get('type') == 'list' and 'list' in block:
            print(f"Lista con {len(block['list'])} elementos:")
            for j, item in enumerate(block['list'][:3]):  # Solo primeros 3
                print(f"  Item {j+1}: {item.get('title', 'Sin título')}")
                print(f"    Refs: {item.get('reference_indexes', [])}")
    
    # References
    references = ai_overview.get('references', [])
    print(f"\n🔗 References: {len(references)}")
    
    if references:
        for i, ref in enumerate(references):
            print(f"\n--- Reference {i} ---")
            print(f"Index: {ref.get('index', 'N/A')}")
            print(f"Title: {ref.get('title', 'N/A')}")
            print(f"Link: {ref.get('link', 'N/A')}")
            print(f"Source: {ref.get('source', 'N/A')}")
    else:
        print("⚠️ NO HAY REFERENCES - Este es el problema!")
    
    # Page token
    if 'page_token' in ai_overview:
        print(f"\n🎫 Page token presente: {ai_overview['page_token'][:50]}...")
        print(f"🔗 SerpAPI link: {ai_overview.get('serpapi_link', 'N/A')}")
        print("\n⚠️ ESTO PUEDE SER LA CAUSA: Requiere petición adicional")
    
    # Examinar otras claves
    print(f"\n🔍 OTRAS CLAVES EN AI OVERVIEW:")
    for key, value in ai_overview.items():
        if key not in ['text_blocks', 'references']:
            print(f"{key}: {type(value).__name__}")
            if isinstance(value, str) and len(value) > 100:
                print(f"  Value: {value[:100]}...")
            else:
                print(f"  Value: {value}")
    
    print("\n" + "="*60)
    print("🎯 ANÁLISIS:")
    
    if not references and 'page_token' not in ai_overview:
        print("❌ PROBLEMA: No hay references NI page_token")
        print("   SERPAPI no está devolviendo las fuentes del AI Overview")
        
    elif 'page_token' in ai_overview:
        print("⚠️ POSIBLE SOLUCIÓN: Usar page_token para segunda petición")
        print("   Google requiere petición adicional para obtener fuentes")
        
    else:
        print("✅ Estructura parece correcta, verificar lógica de matching")

if __name__ == "__main__":
    examine_ai_structure() 