#!/usr/bin/env python3
"""
Script para corregir la configuración del modelo de OpenAI
Cambiar de gpt-5 (que no existe) a gpt-4o (el modelo real más potente)
"""

from database import get_db_connection
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    print("=" * 80)
    print("🔧 CORRIGIENDO CONFIGURACIÓN DE MODELO OPENAI")
    print("=" * 80)
    print()
    
    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la base de datos")
        return False
    
    try:
        cur = conn.cursor()
        
        # 1. Desmarcar gpt-5 como actual
        print("1️⃣ Desmarcando gpt-5 como modelo actual...")
        cur.execute("""
            UPDATE llm_model_registry
            SET is_current = FALSE
            WHERE llm_provider = 'openai' AND model_id = 'gpt-5'
            RETURNING model_id
        """)
        
        result = cur.fetchone()
        if result:
            print(f"   ✅ {result['model_id']} desmarcado como actual")
        else:
            print("   ℹ️  gpt-5 no estaba marcado como actual")
        
        print()
        
        # 2. Marcar gpt-4o como actual
        print("2️⃣ Marcando gpt-4o como modelo actual...")
        cur.execute("""
            UPDATE llm_model_registry
            SET is_current = TRUE
            WHERE llm_provider = 'openai' AND model_id = 'gpt-4o'
            RETURNING model_id, model_display_name
        """)
        
        result = cur.fetchone()
        if result:
            print(f"   ✅ {result['model_id']} ({result['model_display_name']}) marcado como actual")
        else:
            # Si gpt-4o no existe, crearlo
            print("   ℹ️  gpt-4o no existe, creándolo...")
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
                    2.50,
                    10.00,
                    128000,
                    TRUE,
                    TRUE,
                    NOW(),
                    NOW()
                )
                ON CONFLICT (llm_provider, model_id) DO UPDATE
                SET is_current = TRUE,
                    updated_at = NOW()
                RETURNING model_id, model_display_name
            """)
            result = cur.fetchone()
            print(f"   ✅ {result['model_id']} ({result['model_display_name']}) creado y marcado como actual")
        
        print()
        
        # 3. Verificar configuración final
        print("3️⃣ Verificando configuración final...")
        cur.execute("""
            SELECT 
                model_id,
                model_display_name,
                is_current,
                is_available,
                cost_per_1m_input_tokens,
                cost_per_1m_output_tokens
            FROM llm_model_registry
            WHERE llm_provider = 'openai'
            ORDER BY is_current DESC, model_id
        """)
        
        models = cur.fetchall()
        
        for model in models:
            indicator = "⭐ ACTUAL" if model['is_current'] else "  "
            available = "✅" if model['is_available'] else "❌"
            print(f"   [{indicator}] [{available}] {model['model_id']}")
            print(f"      Display: {model['model_display_name']}")
            print(f"      Cost: ${model['cost_per_1m_input_tokens']:.2f}/${model['cost_per_1m_output_tokens']:.2f} per 1M tokens")
        
        print()
        
        # 4. Commit de cambios
        conn.commit()
        
        print("=" * 80)
        print("✅ CONFIGURACIÓN CORREGIDA EXITOSAMENTE")
        print("=" * 80)
        print()
        print("📝 Cambios realizados:")
        print("   - gpt-5 (inexistente) → desmarcado como actual")
        print("   - gpt-4o (modelo real) → marcado como actual")
        print()
        print("🚀 Próximos pasos:")
        print("   1. El próximo análisis automático (cron) usará gpt-4o")
        print("   2. O puedes ejecutar un análisis manual ahora desde el frontend")
        print()
        
        return True
        
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

