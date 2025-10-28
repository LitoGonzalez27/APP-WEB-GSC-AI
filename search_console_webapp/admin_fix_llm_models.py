"""
Endpoint de administración para corregir modelos LLM
"""
from flask import Blueprint, jsonify
from database import get_db_connection
import logging

admin_fix_bp = Blueprint('admin_fix', __name__)
logger = logging.getLogger(__name__)


@admin_fix_bp.route('/admin/fix-llm-models', methods=['POST'])
def fix_llm_models_endpoint():
    """
    Endpoint para corregir los modelos LLM en la base de datos
    
    NOTA: Este es un endpoint temporal de administración
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        results = {
            'success': True,
            'steps': [],
            'models_updated': []
        }
        
        # 0. Crear tabla si no existe
        results['steps'].append("Verificando tabla llm_models...")
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
        results['steps'].append("✅ Tabla verificada/creada")
        
        # 1. Desactivar todos los modelos de OpenAI
        results['steps'].append("Desactivando modelos antiguos de OpenAI...")
        cur.execute("""
            UPDATE llm_models
            SET is_current = FALSE
            WHERE llm_provider = 'openai'
        """)
        
        # 2. Agregar/actualizar GPT-4o
        results['steps'].append("Configurando gpt-4o como modelo actual de OpenAI...")
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
        results['models_updated'].append('openai: gpt-4o')
        
        # 3. Desactivar todos los modelos de Anthropic
        results['steps'].append("Desactivando modelos antiguos de Anthropic...")
        cur.execute("""
            UPDATE llm_models
            SET is_current = FALSE
            WHERE llm_provider = 'anthropic'
        """)
        
        # 4. Agregar/actualizar Claude Sonnet 4.5
        results['steps'].append("Configurando claude-sonnet-4-5 como modelo actual...")
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
        results['models_updated'].append('anthropic: claude-sonnet-4-5')
        
        # 5. Verificar/actualizar Google
        results['steps'].append("Verificando Google Gemini...")
        cur.execute("""
            INSERT INTO llm_models (
                llm_provider, model_id, model_name,
                cost_per_1m_input_tokens, cost_per_1m_output_tokens,
                max_tokens, is_current
            ) VALUES (
                'google', 'gemini-1.5-flash', 'Gemini 1.5 Flash',
                0.075, 0.30, 1000000, TRUE
            )
            ON CONFLICT (llm_provider, model_id) 
            DO UPDATE SET
                is_current = TRUE,
                updated_at = NOW()
        """)
        results['models_updated'].append('google: gemini-1.5-flash')
        
        # 6. Verificar/actualizar Perplexity
        results['steps'].append("Verificando Perplexity...")
        cur.execute("""
            INSERT INTO llm_models (
                llm_provider, model_id, model_name,
                cost_per_1m_input_tokens, cost_per_1m_output_tokens,
                max_tokens, is_current
            ) VALUES (
                'perplexity', 'llama-3.1-sonar-large-128k-online', 'Perplexity Sonar Large',
                1.00, 1.00, 128000, TRUE
            )
            ON CONFLICT (llm_provider, model_id) 
            DO UPDATE SET
                is_current = TRUE,
                updated_at = NOW()
        """)
        results['models_updated'].append('perplexity: llama-3.1-sonar-large-128k-online')
        
        # Commit todos los cambios
        conn.commit()
        results['steps'].append("✅ Todos los cambios guardados")
        
        # Verificar modelos finales
        cur.execute("""
            SELECT llm_provider, model_id, model_name, is_current,
                   cost_per_1m_input_tokens, cost_per_1m_output_tokens
            FROM llm_models
            WHERE is_current = TRUE
            ORDER BY llm_provider
        """)
        
        current_models = cur.fetchall()
        results['current_models'] = [
            {
                'provider': m['llm_provider'],
                'model_id': m['model_id'],
                'model_name': m['model_name'],
                'cost_input': float(m['cost_per_1m_input_tokens']),
                'cost_output': float(m['cost_per_1m_output_tokens'])
            }
            for m in current_models
        ]
        
        cur.close()
        conn.close()
        
        logger.info(f"✅ Modelos LLM corregidos exitosamente: {results['models_updated']}")
        
        return jsonify(results), 200
        
    except Exception as e:
        logger.error(f"❌ Error corrigiendo modelos LLM: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

