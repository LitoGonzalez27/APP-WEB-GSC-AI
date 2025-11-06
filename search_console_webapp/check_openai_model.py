#!/usr/bin/env python3
"""
Script para verificar la configuración del modelo de OpenAI en la BD
"""

from database import get_db_connection

def main():
    print("=" * 80)
    print("🔍 VERIFICANDO CONFIGURACIÓN DE OPENAI")
    print("=" * 80)
    print()
    
    conn = get_db_connection()
    if not conn:
        print("   ❌ ERROR: No se pudo conectar a la base de datos")
        return
    
    try:
        cur = conn.cursor()
        
        # Ver todos los modelos de OpenAI
        print("1️⃣ MODELOS DE OPENAI EN LA BASE DE DATOS")
        print("-" * 80)
        
        cur.execute("""
            SELECT 
                id,
                model_id,
                model_display_name,
                is_current,
                is_available,
                cost_per_1m_input_tokens,
                cost_per_1m_output_tokens,
                max_tokens,
                created_at
            FROM llm_model_registry
            WHERE llm_provider = 'openai'
            ORDER BY is_current DESC, created_at DESC
        """)
        
        models = cur.fetchall()
        
        if not models:
            print("   ⚠️  NO HAY MODELOS DE OPENAI EN LA BASE DE DATOS")
        else:
            print(f"   Total de modelos: {len(models)}")
            print()
            
            current_model = None
            for model in models:
                current_indicator = "⭐ ACTUAL" if model['is_current'] else "  "
                available_indicator = "✅" if model['is_available'] else "❌"
                
                if model['is_current']:
                    current_model = model
                
                print(f"   [{current_indicator}] [{available_indicator}] {model['model_id']}")
                print(f"      Display: {model['model_display_name']}")
                print(f"      Is Current: {model['is_current']}")
                print(f"      Is Available: {model['is_available']}")
                print(f"      Cost: ${model['cost_per_1m_input_tokens']:.2f}/${model['cost_per_1m_output_tokens']:.2f} per 1M tokens")
                print(f"      Max tokens: {model['max_tokens']}")
                print()
            
            if current_model:
                print(f"   📍 Modelo actual configurado: {current_model['model_id']}")
                print(f"      Display: {current_model['model_display_name']}")
                print(f"      Available: {current_model['is_available']}")
            else:
                print("   ⚠️  NO HAY MODELO MARCADO COMO ACTUAL (is_current=TRUE)")
        
        print()
        
        # Verificar variables de entorno
        print("2️⃣ VARIABLES DE ENTORNO")
        print("-" * 80)
        
        import os
        openai_api_key = os.getenv('OPENAI_API_KEY')
        preferred_model = os.getenv('OPENAI_PREFERRED_MODEL')
        use_responses = os.getenv('OPENAI_USE_RESPONSES')
        
        if openai_api_key:
            print(f"   ✅ OPENAI_API_KEY: {openai_api_key[:20]}...")
        else:
            print(f"   ❌ OPENAI_API_KEY: NO CONFIGURADA")
        
        if preferred_model:
            print(f"   ℹ️  OPENAI_PREFERRED_MODEL: {preferred_model}")
        else:
            print(f"   ℹ️  OPENAI_PREFERRED_MODEL: No configurada (usará BD)")
        
        if use_responses:
            print(f"   ℹ️  OPENAI_USE_RESPONSES: {use_responses}")
        else:
            print(f"   ℹ️  OPENAI_USE_RESPONSES: No configurada")
        
        print()
        
        # Probar inicialización del provider
        print("3️⃣ PROBAR INICIALIZACIÓN DEL PROVIDER")
        print("-" * 80)
        
        if openai_api_key:
            try:
                from services.llm_providers.openai_provider import OpenAIProvider
                
                print("   Inicializando OpenAIProvider...")
                provider = OpenAIProvider(api_key=openai_api_key)
                
                print(f"   ✅ Provider inicializado exitosamente")
                print(f"      Modelo seleccionado: {provider.model}")
                print(f"      Pricing: ${provider.pricing['input']*1000000:.2f}/${provider.pricing['output']*1000000:.2f} per 1M tokens")
                
            except Exception as e:
                print(f"   ❌ ERROR al inicializar provider: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("   ⚠️  No se puede probar sin OPENAI_API_KEY")
        
        print()
        print("=" * 80)
        print("✅ Verificación completada")
        print("=" * 80)
        
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()

