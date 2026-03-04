#!/usr/bin/env python3
"""
Script para actualizar los modelos LLM actuales SIN confirmación interactiva.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection


def update_models():
    """Actualiza los modelos actuales directamente."""
    
    conn = get_db_connection()
    if not conn:
        print("❌ Error: No se pudo conectar a la base de datos")
        return False
    
    try:
        cur = conn.cursor()
        
        # Primero, ver la estructura de la tabla
        print("\n📋 Estructura de llm_model_registry:")
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'llm_model_registry'
            ORDER BY ordinal_position
        """)
        columns = cur.fetchall()
        for col in columns:
            print(f"   • {col['column_name']}: {col['data_type']}")
        
        print("\n" + "=" * 60)
        
        # Model IDs correctos según documentación oficial (Dic 2025)
        desired_models = {
            'openai': ('gpt-5.2', 'GPT-5.2'),
            'google': ('gemini-3-flash-preview', 'Gemini 3 Flash'),
            'anthropic': ('claude-sonnet-4-5-20250929', 'Claude Sonnet 4.5'),
            'perplexity': ('sonar', 'Perplexity Sonar')
        }
        
        print("\n🔄 Actualizando modelos LLM...")
        print("=" * 60)
        
        for provider, (model_id, display_name) in desired_models.items():
            # 1. Verificar si el modelo existe
            cur.execute("""
                SELECT id FROM llm_model_registry 
                WHERE llm_provider = %s AND model_id = %s
            """, (provider, model_id))
            
            exists = cur.fetchone()
            
            if not exists:
                # Insertar el nuevo modelo (sin precios, usar defaults)
                print(f"   📥 Insertando {provider}: {model_id}...")
                cur.execute("""
                    INSERT INTO llm_model_registry 
                    (llm_provider, model_id, model_display_name, is_current, is_available)
                    VALUES (%s, %s, %s, FALSE, TRUE)
                """, (provider, model_id, display_name))
            
            # 2. Quitar is_current de todos los modelos del proveedor
            cur.execute("""
                UPDATE llm_model_registry
                SET is_current = FALSE
                WHERE llm_provider = %s
            """, (provider,))
            
            # 3. Marcar el modelo deseado como current
            cur.execute("""
                UPDATE llm_model_registry
                SET is_current = TRUE, is_available = TRUE
                WHERE llm_provider = %s AND model_id = %s
            """, (provider, model_id))
            
            print(f"   ✅ {provider}: {model_id} → CURRENT")
        
        conn.commit()
        
        # Mostrar estado final
        print("\n" + "=" * 60)
        print("📊 Estado FINAL de modelos actuales:")
        print("=" * 60)
        cur.execute("""
            SELECT llm_provider, model_id, model_display_name
            FROM llm_model_registry
            WHERE is_current = TRUE
            ORDER BY llm_provider
        """)
        
        for row in cur.fetchall():
            print(f"   ✅ {row['llm_provider']:12} | {row['model_id']:30} | {row['model_display_name']}")
        
        print("\n" + "=" * 60)
        print("✅ ¡Modelos actualizados correctamente!")
        print("ℹ️  Los próximos análisis usarán estos modelos.")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    update_models()
