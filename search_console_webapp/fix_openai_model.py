"""
Script para actualizar el modelo actual de OpenAI a uno que realmente existe
"""

from database import get_db_connection

def fix_openai_model():
    """
    Cambia el modelo actual de OpenAI de gpt-5 a gpt-4o
    """
    print("\n" + "="*80)
    print("🔧 ACTUALIZANDO MODELO OPENAI")
    print("="*80)
    
    conn = get_db_connection()
    if not conn:
        print("❌ No se pudo conectar a la base de datos")
        return False
    
    try:
        cur = conn.cursor()
        
        # Verificar modelo actual
        cur.execute("""
            SELECT model_id, is_available
            FROM llm_model_registry
            WHERE llm_provider = 'openai' AND is_current = TRUE
        """)
        
        current = cur.fetchone()
        
        if current:
            print(f"\n📊 Modelo actual: {current['model_id']}")
            print(f"   Disponible: {'Sí' if current['is_available'] else 'No'}")
        
        # Verificar si gpt-4o existe en la BD
        cur.execute("""
            SELECT id, model_id, is_current, is_available
            FROM llm_model_registry
            WHERE llm_provider = 'openai' AND model_id = 'gpt-4o'
        """)
        
        gpt4o = cur.fetchone()
        
        if not gpt4o:
            print("\n⚠️ gpt-4o no está en la BD, agregándolo...")
            
            # Agregar gpt-4o
            cur.execute("""
                INSERT INTO llm_model_registry (
                    llm_provider,
                    model_id,
                    model_display_name,
                    cost_per_1m_input_tokens,
                    cost_per_1m_output_tokens,
                    max_tokens,
                    is_current,
                    is_available,
                    created_at,
                    updated_at
                ) VALUES (
                    'openai',
                    'gpt-4o',
                    'GPT-4o',
                    2.50,  -- $2.50 por 1M tokens de input
                    10.00,  -- $10.00 por 1M tokens de output
                    128000,
                    FALSE,  -- Lo marcaremos como current en el siguiente paso
                    TRUE,
                    NOW(),
                    NOW()
                )
                RETURNING id
            """)
            
            gpt4o_id = cur.fetchone()['id']
            print(f"✅ gpt-4o agregado con ID {gpt4o_id}")
        else:
            print(f"\n✅ gpt-4o ya existe en la BD")
            print(f"   Actual: {'Sí' if gpt4o['is_current'] else 'No'}")
            print(f"   Disponible: {'Sí' if gpt4o['is_available'] else 'No'}")
        
        # Desmarcar todos los modelos OpenAI como current
        cur.execute("""
            UPDATE llm_model_registry
            SET is_current = FALSE, updated_at = NOW()
            WHERE llm_provider = 'openai' AND is_current = TRUE
        """)
        
        print(f"\n🔄 Desmarcando modelos anteriores como current...")
        
        # Marcar gpt-4o como current y available
        cur.execute("""
            UPDATE llm_model_registry
            SET is_current = TRUE, is_available = TRUE, updated_at = NOW()
            WHERE llm_provider = 'openai' AND model_id = 'gpt-4o'
        """)
        
        conn.commit()
        
        print("✅ gpt-4o marcado como current y available")
        
        # Verificar cambio
        cur.execute("""
            SELECT model_id, model_display_name, is_current, is_available
            FROM llm_model_registry
            WHERE llm_provider = 'openai' AND is_current = TRUE
        """)
        
        new_current = cur.fetchone()
        
        print(f"\n📊 NUEVO MODELO ACTUAL:")
        print(f"   {new_current['model_id']} ({new_current['model_display_name']})")
        print(f"   Available: {'Sí' if new_current['is_available'] else 'No'}")
        
        cur.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        conn.rollback()
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    import sys
    success = fix_openai_model()
    sys.exit(0 if success else 1)

