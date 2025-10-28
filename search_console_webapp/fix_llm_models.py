"""
Script para corregir los modelos LLM en la base de datos
"""
import logging
from database import get_db_connection

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)

def fix_llm_models():
    """
    Corrige los modelos LLM que no existen o tienen nombres incorrectos
    """
    print("\n" + "="*70)
    print("🔧 CORRIGIENDO MODELOS LLM EN BASE DE DATOS")
    print("="*70 + "\n")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 0. Crear tabla si no existe
        print("📋 Verificando tabla llm_models...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS llm_models (
                id SERIAL PRIMARY KEY,
                llm_provider VARCHAR(50) NOT NULL,
                model_id VARCHAR(100) NOT NULL,
                model_name VARCHAR(200) NOT NULL,
                cost_per_1m_input_tokens DECIMAL(10,2) NOT NULL,
                cost_per_1m_output_tokens DECIMAL(10,2) NOT NULL,
                max_tokens INTEGER,
                is_current BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(llm_provider, model_id)
            )
        """)
        conn.commit()
        print("   ✅ Tabla verificada/creada\n")
        
        # 1. Ver modelos actuales
        print("📋 Modelos actuales en BD:")
        cur.execute("""
            SELECT llm_provider, model_id, model_name, is_current
            FROM llm_models
            ORDER BY llm_provider, is_current DESC
        """)
        
        models = cur.fetchall()
        for model in models:
            status = "✅ ACTUAL" if model['is_current'] else "  "
            print(f"   {status} {model['llm_provider']}: {model['model_id']} ({model['model_name']})")
        
        print("\n" + "="*70)
        print("🔄 ACTUALIZANDO MODELOS INCORRECTOS")
        print("="*70 + "\n")
        
        # 2. Desactivar todos los modelos de OpenAI
        print("1️⃣ Desactivando todos los modelos de OpenAI...")
        cur.execute("""
            UPDATE llm_models
            SET is_current = FALSE
            WHERE llm_provider = 'openai'
        """)
        
        # 3. Agregar/actualizar GPT-4o (modelo real más reciente)
        print("2️⃣ Configurando gpt-4o como modelo actual de OpenAI...")
        cur.execute("""
            INSERT INTO llm_models (
                llm_provider, model_id, model_name,
                cost_per_1m_input_tokens, cost_per_1m_output_tokens,
                max_tokens, is_current
            ) VALUES (
                'openai', 'gpt-4o', 'GPT-4o',
                2.50, 10.00, 128000, TRUE
            )
            ON CONFLICT (llm_provider, model_id) 
            DO UPDATE SET
                is_current = TRUE,
                cost_per_1m_input_tokens = 2.50,
                cost_per_1m_output_tokens = 10.00,
                updated_at = NOW()
        """)
        print("   ✅ gpt-4o configurado")
        
        # 4. Desactivar todos los modelos de Anthropic
        print("\n3️⃣ Desactivando todos los modelos de Anthropic...")
        cur.execute("""
            UPDATE llm_models
            SET is_current = FALSE
            WHERE llm_provider = 'anthropic'
        """)
        
        # 5. Agregar/actualizar Claude Sonnet 4.5 (nombre correcto)
        print("4️⃣ Configurando claude-sonnet-4-5 como modelo actual de Anthropic...")
        cur.execute("""
            INSERT INTO llm_models (
                llm_provider, model_id, model_name,
                cost_per_1m_input_tokens, cost_per_1m_output_tokens,
                max_tokens, is_current
            ) VALUES (
                'anthropic', 'claude-sonnet-4-5', 'Claude Sonnet 4.5',
                3.00, 15.00, 200000, TRUE
            )
            ON CONFLICT (llm_provider, model_id) 
            DO UPDATE SET
                is_current = TRUE,
                cost_per_1m_input_tokens = 3.00,
                cost_per_1m_output_tokens = 15.00,
                updated_at = NOW()
        """)
        print("   ✅ claude-sonnet-4-5 configurado")
        
        # 6. Verificar Perplexity (debería estar bien)
        print("\n5️⃣ Verificando Perplexity...")
        cur.execute("""
            SELECT model_id, is_current
            FROM llm_models
            WHERE llm_provider = 'perplexity'
        """)
        
        perplexity = cur.fetchone()
        if perplexity:
            print(f"   ✅ Perplexity: {perplexity['model_id']} (is_current: {perplexity['is_current']})")
        else:
            print("   ⚠️ No hay modelo de Perplexity, agregando...")
            cur.execute("""
                INSERT INTO llm_models (
                    llm_provider, model_id, model_name,
                    cost_per_1m_input_tokens, cost_per_1m_output_tokens,
                    max_tokens, is_current
                ) VALUES (
                    'perplexity', 'llama-3.1-sonar-large-128k-online', 'Perplexity Sonar Large',
                    1.00, 1.00, 128000, TRUE
                )
            """)
            print("   ✅ Perplexity Sonar Large agregado")
        
        # 7. Commit cambios
        conn.commit()
        
        print("\n" + "="*70)
        print("✅ MODELOS ACTUALIZADOS CORRECTAMENTE")
        print("="*70 + "\n")
        
        # 8. Mostrar modelos finales
        print("📋 Modelos actuales (después de la corrección):")
        cur.execute("""
            SELECT llm_provider, model_id, model_name, is_current,
                   cost_per_1m_input_tokens, cost_per_1m_output_tokens
            FROM llm_models
            WHERE is_current = TRUE
            ORDER BY llm_provider
        """)
        
        current_models = cur.fetchall()
        for model in current_models:
            print(f"   ✅ {model['llm_provider']}: {model['model_id']}")
            print(f"      Nombre: {model['model_name']}")
            print(f"      Coste: ${model['cost_per_1m_input_tokens']}/{model['cost_per_1m_output_tokens']} per 1M tokens")
            print()
        
        print("="*70)
        print("🎉 ¡LISTO! Ahora ejecuta un nuevo análisis")
        print("="*70)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    fix_llm_models()

