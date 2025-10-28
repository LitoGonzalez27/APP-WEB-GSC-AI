#!/usr/bin/env python3
"""
Script para verificar que los modelos LLM se corrigieron correctamente
"""
import psycopg2
from database import get_db_connection
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def verify_llm_models():
    """Verifica que los modelos LLM estén correctos en la BD"""
    
    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la base de datos")
        return False
    
    try:
        cursor = conn.cursor()
        
        # Verificar tabla existe
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'llm_models'
            )
        """)
        result = cursor.fetchone()
        # RealDictCursor devuelve un diccionario
        exists = result['exists'] if result else False
        
        if not exists:
            logger.error("❌ La tabla llm_models NO existe")
            return False
        
        logger.info("✅ Tabla llm_models existe")
        logger.info("\n" + "="*80)
        logger.info("MODELOS ACTUALES EN BASE DE DATOS:")
        logger.info("="*80 + "\n")
        
        # Obtener todos los modelos actuales
        cursor.execute("""
            SELECT 
                llm_provider,
                model_id,
                model_name,
                cost_per_1m_input_tokens,
                cost_per_1m_output_tokens,
                is_current
            FROM llm_models
            ORDER BY llm_provider, is_current DESC, model_id
        """)
        
        models = cursor.fetchall()
        
        if not models:
            logger.error("❌ NO hay modelos en la tabla llm_models")
            return False
        
        current_models = {}
        all_models_by_provider = {}
        
        # RealDictCursor devuelve diccionarios, no tuples
        for model in models:
            provider = model['llm_provider']
            model_id = model['model_id']
            model_name = model['model_name']
            input_cost = model['cost_per_1m_input_tokens']
            output_cost = model['cost_per_1m_output_tokens']
            is_current = model['is_current']
            if provider not in all_models_by_provider:
                all_models_by_provider[provider] = []
            
            all_models_by_provider[provider].append({
                'model_id': model_id,
                'model_name': model_name,
                'input_cost': float(input_cost),
                'output_cost': float(output_cost),
                'is_current': is_current
            })
            
            if is_current:
                current_models[provider] = {
                    'model_id': model_id,
                    'model_name': model_name,
                    'input_cost': float(input_cost),
                    'output_cost': float(output_cost)
                }
        
        # Mostrar modelos actuales (is_current=true)
        logger.info("🎯 MODELOS MARCADOS COMO ACTUALES (is_current=true):\n")
        
        for provider in sorted(current_models.keys()):
            model = current_models[provider]
            icon = {
                'openai': '🤖',
                'anthropic': '🧠',
                'google': '🔍',
                'perplexity': '🌐'
            }.get(provider, '📌')
            
            logger.info(f"{icon} {provider.upper()}")
            logger.info(f"   Model ID: {model['model_id']}")
            logger.info(f"   Name: {model['model_name']}")
            logger.info(f"   Cost: ${model['input_cost']:.2f}/${model['output_cost']:.2f} per 1M tokens")
            logger.info("")
        
        # Mostrar TODOS los modelos por proveedor
        logger.info("\n" + "="*80)
        logger.info("TODOS LOS MODELOS EN BASE DE DATOS:")
        logger.info("="*80 + "\n")
        
        for provider in sorted(all_models_by_provider.keys()):
            logger.info(f"\n📦 {provider.upper()}:")
            for model in all_models_by_provider[provider]:
                status = "✅ ACTIVO" if model['is_current'] else "⚪ Inactivo"
                logger.info(f"   {status} - {model['model_id']} ({model['model_name']})")
        
        # Verificar los modelos correctos
        logger.info("\n" + "="*80)
        logger.info("VERIFICACIÓN DE CORRECCIONES:")
        logger.info("="*80 + "\n")
        
        checks = {
            'openai': {
                'expected_id': 'gpt-4o',
                'wrong_ids': ['gpt-5'],
                'message': 'OpenAI debe usar gpt-4o (NO gpt-5)'
            },
            'anthropic': {
                'expected_id': 'claude-sonnet-4-5',
                'wrong_ids': ['claude-sonnet-4-5-20250929'],
                'message': 'Anthropic debe usar claude-sonnet-4-5 (NO con fecha)'
            },
            'google': {
                'expected_id': 'gemini-1.5-flash',
                'wrong_ids': [],
                'message': 'Google debe usar gemini-1.5-flash'
            },
            'perplexity': {
                'expected_id': 'llama-3.1-sonar-large-128k-online',
                'wrong_ids': [],
                'message': 'Perplexity debe usar llama-3.1-sonar-large-128k-online'
            }
        }
        
        all_good = True
        
        for provider, check in checks.items():
            if provider in current_models:
                actual_id = current_models[provider]['model_id']
                if actual_id == check['expected_id']:
                    logger.info(f"✅ {provider.upper()}: Correcto - {actual_id}")
                elif actual_id in check['wrong_ids']:
                    logger.error(f"❌ {provider.upper()}: INCORRECTO - {actual_id}")
                    logger.error(f"   {check['message']}")
                    all_good = False
                else:
                    logger.warning(f"⚠️ {provider.upper()}: Usando {actual_id} (esperado: {check['expected_id']})")
            else:
                logger.error(f"❌ {provider.upper()}: NO CONFIGURADO")
                all_good = False
        
        logger.info("\n" + "="*80)
        if all_good:
            logger.info("✅ TODOS LOS MODELOS ESTÁN CORRECTOS")
            logger.info("\n🚀 Ahora puedes:")
            logger.info("   1. Ir a LLM Monitoring")
            logger.info("   2. Click en 'Run Analysis'")
            logger.info("   3. Deberías ver resultados de los 4 LLMs")
        else:
            logger.error("❌ HAY MODELOS INCORRECTOS")
            logger.error("\n🔧 Ejecuta nuevamente: /admin/fix-llm-models")
        logger.info("="*80 + "\n")
        
        cursor.close()
        return all_good
        
    except Exception as e:
        logger.error(f"❌ Error verificando modelos: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    verify_llm_models()

