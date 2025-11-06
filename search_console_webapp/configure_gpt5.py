#!/usr/bin/env python3
"""
Script para configurar GPT-5 como modelo actual en el sistema

Este script:
1. Actualiza GPT-5 con precios correctos ($1.25/$10)
2. Marca GPT-5 como modelo actual (is_current=TRUE)
3. Desmarca otros modelos de OpenAI como current
4. Verifica que todo esté configurado correctamente
"""

import sys
import logging
from database import get_db_connection

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def configure_gpt5():
    """Configura GPT-5 como modelo actual"""
    logger.info("\n" + "="*60)
    logger.info("CONFIGURANDO GPT-5 COMO MODELO ACTUAL")
    logger.info("="*60)
    
    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la BD")
        return False
    
    try:
        cur = conn.cursor()
        
        # Paso 1: Desmarcamos todos los modelos de OpenAI como current
        logger.info("\n1️⃣ Desmarcando modelos anteriores de OpenAI...")
        cur.execute("""
            UPDATE llm_model_registry
            SET is_current = FALSE
            WHERE llm_provider = 'openai'
        """)
        logger.info(f"   ✅ {cur.rowcount} modelos desmarcados")
        
        # Paso 2: Aseguramos que GPT-5 existe con precios correctos
        logger.info("\n2️⃣ Configurando GPT-5...")
        logger.info("   Precios correctos según OpenAI:")
        logger.info("   - Input:  $1.25 per 1M tokens")
        logger.info("   - Output: $10.00 per 1M tokens")
        logger.info("   - Context: 400,000 tokens")
        logger.info("   - Max output: 128,000 tokens")
        
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
                'gpt-5', 
                'GPT-5',
                1.25,  -- Input: $1.25 per 1M tokens
                10.00, -- Output: $10.00 per 1M tokens
                400000, -- Context window
                TRUE,  -- Modelo actual
                TRUE,  -- Disponible
                NOW(),
                NOW()
            )
            ON CONFLICT (llm_provider, model_id) 
            DO UPDATE SET
                cost_per_1m_input_tokens = 1.25,
                cost_per_1m_output_tokens = 10.00,
                max_tokens = 400000,
                is_current = TRUE,
                is_available = TRUE,
                updated_at = NOW()
            RETURNING id, model_id, is_current
        """)
        
        result = cur.fetchone()
        if result:
            logger.info(f"   ✅ GPT-5 configurado correctamente (ID: {result['id']})")
            logger.info(f"      is_current: {result['is_current']}")
        else:
            logger.error("   ❌ Error configurando GPT-5")
            return False
        
        # Paso 3: Verificar configuración
        logger.info("\n3️⃣ Verificando configuración...")
        cur.execute("""
            SELECT 
                model_id,
                model_display_name,
                cost_per_1m_input_tokens,
                cost_per_1m_output_tokens,
                max_tokens,
                is_current,
                is_available
            FROM llm_model_registry
            WHERE llm_provider = 'openai'
            ORDER BY is_current DESC, model_id
        """)
        
        models = cur.fetchall()
        
        logger.info("\n   📊 Modelos de OpenAI en BD:")
        for model in models:
            status = "✅ CURRENT" if model['is_current'] else "   "
            available = "✓" if model['is_available'] else "✗"
            logger.info(f"   {status} [{available}] {model['model_id']} ({model['model_display_name']})")
            logger.info(f"        Input:  ${model['cost_per_1m_input_tokens']:.2f}/1M")
            logger.info(f"        Output: ${model['cost_per_1m_output_tokens']:.2f}/1M")
            logger.info(f"        Max tokens: {model['max_tokens']:,}")
        
        # Commit
        conn.commit()
        logger.info("\n✅ Configuración guardada exitosamente")
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ Error configurando GPT-5: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()


def test_gpt5_configuration():
    """Prueba que GPT-5 esté correctamente configurado"""
    logger.info("\n" + "="*60)
    logger.info("VERIFICANDO CONFIGURACIÓN DE GPT-5")
    logger.info("="*60)
    
    import os
    
    # Verificar API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        logger.error("\n❌ OPENAI_API_KEY no está configurada")
        logger.info("   Configúrala con: export OPENAI_API_KEY='sk-proj-...'")
        return False
    
    logger.info(f"\n✅ API Key configurada: {api_key[:10]}...{api_key[-4:]}")
    
    # Intentar importar y probar el provider
    try:
        from services.llm_providers.openai_provider import OpenAIProvider
        
        logger.info("\n🧪 Probando OpenAI Provider con GPT-5...")
        provider = OpenAIProvider(api_key=api_key)
        
        logger.info(f"   Modelo: {provider.model}")
        logger.info(f"   Pricing:")
        logger.info(f"      Input:  ${provider.pricing['input']*1000000:.2f}/1M tokens")
        logger.info(f"      Output: ${provider.pricing['output']*1000000:.2f}/1M tokens")
        
        # Test simple
        logger.info("\n   Ejecutando query de prueba...")
        result = provider.execute_query("Di solo 'OK' si puedes leerme")
        
        if result['success']:
            logger.info(f"   ✅ Query exitosa!")
            logger.info(f"      Respuesta: {result['content'][:50]}...")
            logger.info(f"      Modelo usado: {result['model_used']}")
            logger.info(f"      Tokens: {result['tokens']}")
            logger.info(f"      Costo: ${result['cost_usd']:.6f}")
            return True
        else:
            logger.error(f"   ❌ Query falló: {result.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        logger.error(f"\n❌ Error probando provider: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Función principal"""
    logger.info("\n" + "="*80)
    logger.info("🚀 CONFIGURACIÓN DE GPT-5 PARA LLM MONITORING")
    logger.info("="*80)
    
    # 1. Configurar BD
    if not configure_gpt5():
        logger.error("\n❌ Error configurando GPT-5 en BD")
        return 1
    
    # 2. Verificar configuración
    if not test_gpt5_configuration():
        logger.error("\n❌ Error verificando configuración")
        return 1
    
    logger.info("\n" + "="*80)
    logger.info("✅ GPT-5 CONFIGURADO Y PROBADO EXITOSAMENTE")
    logger.info("="*80)
    logger.info("""
    📝 PRÓXIMOS PASOS:
    
    1. En Railway, asegúrate de que OPENAI_API_KEY esté configurada:
       railway variables set OPENAI_API_KEY="sk-proj-..."
    
    2. Reinicia el servicio en Railway para que use la nueva configuración
    
    3. Prueba el sistema desde el dashboard:
       - Ve a LLM Monitoring
       - Selecciona un proyecto
       - Haz clic en "Run Analysis"
       - Verifica que OpenAI/GPT-5 funcione
    
    4. El cron job diario se ejecutará automáticamente y usará GPT-5
    """)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

