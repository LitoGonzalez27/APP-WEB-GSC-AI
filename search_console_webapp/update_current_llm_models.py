#!/usr/bin/env python3
"""
Script para actualizar los modelos LLM actuales en la base de datos.

Este script marca los modelos más recientes como 'is_current = TRUE'
para que el sistema de LLM Monitoring los use.

IMPORTANTE: Ejecutar este script en producción para que los análisis
usen los modelos correctos (GPT-5, Gemini 3, Claude Sonnet 4.5, Sonar).

Uso:
    python update_current_llm_models.py
"""

import os
import sys

# Añadir el directorio padre al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection


def update_current_models():
    """
    Actualiza los modelos actuales en la BD.
    
    Modelos a configurar como actuales:
    - OpenAI: gpt-4o (GPT-5 no está disponible aún en la API real)
    - Google: gemini-2.0-flash (Gemini 3 no está disponible aún)  
    - Anthropic: claude-sonnet-4-5-20241022 (Claude Sonnet 4.5)
    - Perplexity: sonar
    
    NOTA: Actualiza estos valores cuando los modelos realmente estén disponibles.
    """
    
    conn = get_db_connection()
    if not conn:
        print("❌ Error: No se pudo conectar a la base de datos")
        return False
    
    try:
        cur = conn.cursor()
        
        # Primero, mostrar estado actual
        print("\n📊 Estado ACTUAL de modelos en BD:")
        print("=" * 60)
        cur.execute("""
            SELECT llm_provider, model_id, model_display_name, is_current, is_available
            FROM llm_model_registry
            ORDER BY llm_provider, is_current DESC
        """)
        rows = cur.fetchall()
        
        current_models = {}
        for row in rows:
            status = "✅ CURRENT" if row['is_current'] else "  "
            avail = "🟢" if row['is_available'] else "🔴"
            print(f"  {avail} {status} {row['llm_provider']:12} | {row['model_id']:30} | {row['model_display_name']}")
            if row['is_current']:
                current_models[row['llm_provider']] = row['model_id']
        
        print("\n" + "=" * 60)
        print("📌 Modelos ACTUALES por proveedor:")
        for provider, model in current_models.items():
            print(f"   {provider}: {model}")
        
        # Definir los modelos que DEBERÍAN ser actuales
        # Model IDs correctos según documentación oficial (Dic 2025):
        desired_models = {
            'openai': 'gpt-5.1',  # GPT-5.1 flagship (nuevo)
            'google': 'gemini-3-pro-preview',  # Gemini 3 Pro Preview
            'anthropic': 'claude-sonnet-4-5-20250929',  # Claude Sonnet 4.5 (correcto)
            'perplexity': 'sonar'  # Sonar
        }
        
        print("\n" + "=" * 60)
        print("🎯 Modelos DESEADOS (más recientes disponibles):")
        for provider, model in desired_models.items():
            print(f"   {provider}: {model}")
        
        # Preguntar confirmación
        print("\n" + "=" * 60)
        response = input("¿Deseas actualizar los modelos actuales? (y/n): ").strip().lower()
        
        if response != 'y':
            print("❌ Operación cancelada")
            return False
        
        # Actualizar cada proveedor
        print("\n🔄 Actualizando modelos...")
        
        for provider, new_model in desired_models.items():
            # 1. Primero, quitar is_current de todos los modelos del proveedor
            cur.execute("""
                UPDATE llm_model_registry
                SET is_current = FALSE
                WHERE llm_provider = %s
            """, (provider,))
            
            # 2. Marcar el nuevo modelo como current
            cur.execute("""
                UPDATE llm_model_registry
                SET is_current = TRUE, is_available = TRUE
                WHERE llm_provider = %s AND model_id = %s
            """, (provider, new_model))
            
            if cur.rowcount > 0:
                print(f"   ✅ {provider}: {new_model} marcado como actual")
            else:
                # El modelo no existe, insertarlo
                print(f"   ⚠️ {provider}: {new_model} no existe en BD, insertando...")
                
                # Pricing según documentación oficial (Dic 2025)
                # Gemini 3 Pro: $2/$12 per 1M tokens
                # GPT-5.1: Verificar docs, estimado similar a GPT-5
                default_pricing = {
                    'openai': {'input': 2.50, 'output': 10.00},  # GPT-5.1 estimado
                    'google': {'input': 2.00, 'output': 12.00},  # Gemini 3 Pro (<200k)
                    'anthropic': {'input': 3.00, 'output': 15.00},  # Claude Sonnet 4.5
                    'perplexity': {'input': 1.00, 'output': 1.00}  # Sonar
                }
                
                pricing = default_pricing.get(provider, {'input': 1.0, 'output': 1.0})
                
                cur.execute("""
                    INSERT INTO llm_model_registry 
                    (llm_provider, model_id, model_display_name, input_price_per_1m, output_price_per_1m, is_current, is_available)
                    VALUES (%s, %s, %s, %s, %s, TRUE, TRUE)
                """, (provider, new_model, new_model.upper(), pricing['input'], pricing['output']))
                
                print(f"   ✅ {provider}: {new_model} insertado y marcado como actual")
        
        conn.commit()
        
        # Mostrar estado final
        print("\n" + "=" * 60)
        print("📊 Estado FINAL de modelos actuales:")
        cur.execute("""
            SELECT llm_provider, model_id, model_display_name
            FROM llm_model_registry
            WHERE is_current = TRUE
            ORDER BY llm_provider
        """)
        final_rows = cur.fetchall()
        
        for row in final_rows:
            print(f"   ✅ {row['llm_provider']:12} | {row['model_id']:30} | {row['model_display_name']}")
        
        print("\n✅ ¡Modelos actualizados correctamente!")
        print("ℹ️  Los próximos análisis usarán estos modelos.")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()


def check_available_models():
    """
    Verifica qué modelos están realmente disponibles en cada API.
    """
    print("\n🔍 Verificando disponibilidad real de modelos...")
    print("=" * 60)
    
    # OpenAI
    try:
        import openai
        client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        models = client.models.list()
        gpt_models = [m.id for m in models.data if 'gpt' in m.id.lower()]
        print(f"\n📦 OpenAI - Modelos GPT disponibles:")
        for m in sorted(gpt_models)[:10]:
            print(f"   • {m}")
    except Exception as e:
        print(f"   ⚠️ OpenAI: {e}")
    
    # Google
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv('GOOGLE_AI_API_KEY'))
        models = genai.list_models()
        print(f"\n📦 Google - Modelos Gemini disponibles:")
        for m in models:
            if 'gemini' in m.name.lower():
                print(f"   • {m.name}")
    except Exception as e:
        print(f"   ⚠️ Google: {e}")
    
    print("\n" + "=" * 60)


if __name__ == '__main__':
    print("=" * 60)
    print("🤖 Actualizador de Modelos LLM - LLM Monitoring")
    print("=" * 60)
    
    # Opción para verificar modelos disponibles
    if len(sys.argv) > 1 and sys.argv[1] == '--check':
        check_available_models()
    else:
        update_current_models()

