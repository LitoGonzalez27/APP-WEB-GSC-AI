#!/usr/bin/env python3
"""
Script para actualizar el sistema a GPT-5.2
Fecha: 12 Diciembre 2025

Este script:
1. Añade GPT-5.2 al registro de modelos LLM
2. Marca GPT-5.2 como modelo actual de OpenAI
3. Desmarca modelos anteriores

PRECIOS GPT-5.2 (según documentación oficial):
- GPT-5.2: $1.75/1M entrada, $14/1M salida
- GPT-5.2 Pro: $21/1M entrada, $168/1M salida
- GPT-5 Mini: $0.25/1M entrada, $2/1M salida

USO:
    python update_to_gpt52.py
    
    # O con Railway:
    railway run python update_to_gpt52.py
"""

import os
import sys
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def update_openai_model_to_gpt52():
    """Actualiza la base de datos para usar GPT-5.2"""
    
    from database import get_db_connection
    
    logger.info("")
    logger.info("=" * 70)
    logger.info("🚀 ACTUALIZANDO SISTEMA A GPT-5.2")
    logger.info("=" * 70)
    logger.info(f"   Fecha: {datetime.now().isoformat()}")
    logger.info("")
    
    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la base de datos")
        return False
    
    try:
        cur = conn.cursor()
        
        # Paso 1: Desmarcar todos los modelos de OpenAI como 'current'
        logger.info("1️⃣ Desmarcando modelos anteriores de OpenAI...")
        cur.execute("""
            UPDATE llm_model_registry
            SET is_current = FALSE
            WHERE llm_provider = 'openai'
        """)
        updated = cur.rowcount
        logger.info(f"   ✅ {updated} modelo(s) desmarcado(s)")
        
        # Paso 2: Insertar/Actualizar GPT-5.2
        logger.info("")
        logger.info("2️⃣ Configurando GPT-5.2 como modelo actual...")
        
        # Precios de GPT-5.2 según documentación oficial
        gpt52_config = {
            'model_id': 'gpt-5.2',
            'display_name': 'GPT-5.2',
            'input_price': 1.75,    # $1.75 por 1M tokens de entrada
            'output_price': 14.00,  # $14 por 1M tokens de salida
        }
        
        cur.execute("""
            INSERT INTO llm_model_registry (
                llm_provider, 
                model_id, 
                model_display_name,
                cost_per_1m_input_tokens,
                cost_per_1m_output_tokens,
                is_current,
                is_available
            ) VALUES (
                'openai',
                %s,
                %s,
                %s,
                %s,
                TRUE,
                TRUE
            )
            ON CONFLICT (llm_provider, model_id) 
            DO UPDATE SET
                model_display_name = EXCLUDED.model_display_name,
                cost_per_1m_input_tokens = EXCLUDED.cost_per_1m_input_tokens,
                cost_per_1m_output_tokens = EXCLUDED.cost_per_1m_output_tokens,
                is_current = TRUE,
                is_available = TRUE,
                updated_at = NOW()
            RETURNING id
        """, (
            gpt52_config['model_id'],
            gpt52_config['display_name'],
            gpt52_config['input_price'],
            gpt52_config['output_price']
        ))
        
        result = cur.fetchone()
        if result:
            logger.info(f"   ✅ GPT-5.2 configurado correctamente (ID: {result['id']})")
        
        # Paso 3: Insertar GPT-5.2 Pro (opcional, para futura referencia)
        logger.info("")
        logger.info("3️⃣ Añadiendo GPT-5.2 Pro y GPT-5 Mini al registro...")
        
        additional_models = [
            {
                'model_id': 'gpt-5.2-pro',
                'display_name': 'GPT-5.2 Pro',
                'input_price': 21.00,
                'output_price': 168.00
            },
            {
                'model_id': 'gpt-5-mini',
                'display_name': 'GPT-5 Mini',
                'input_price': 0.25,
                'output_price': 2.00
            }
        ]
        
        for model in additional_models:
            cur.execute("""
                INSERT INTO llm_model_registry (
                    llm_provider, 
                    model_id, 
                    model_display_name,
                    cost_per_1m_input_tokens,
                    cost_per_1m_output_tokens,
                    is_current,
                    is_available
                ) VALUES (
                    'openai',
                    %s,
                    %s,
                    %s,
                    %s,
                    FALSE,
                    TRUE
                )
                ON CONFLICT (llm_provider, model_id) 
                DO UPDATE SET
                    model_display_name = EXCLUDED.model_display_name,
                    cost_per_1m_input_tokens = EXCLUDED.cost_per_1m_input_tokens,
                    cost_per_1m_output_tokens = EXCLUDED.cost_per_1m_output_tokens,
                    is_available = TRUE,
                    updated_at = NOW()
            """, (
                model['model_id'],
                model['display_name'],
                model['input_price'],
                model['output_price']
            ))
            logger.info(f"   ✅ {model['display_name']} añadido")
        
        conn.commit()
        
        # Paso 4: Verificar configuración final
        logger.info("")
        logger.info("4️⃣ Verificando configuración final...")
        
        cur.execute("""
            SELECT model_id, model_display_name, is_current, 
                   cost_per_1m_input_tokens, cost_per_1m_output_tokens
            FROM llm_model_registry
            WHERE llm_provider = 'openai'
            ORDER BY is_current DESC, model_id
        """)
        
        models = cur.fetchall()
        
        logger.info("")
        logger.info("   Modelos OpenAI en el sistema:")
        logger.info("   " + "-" * 60)
        for m in models:
            current_marker = "⭐ ACTUAL" if m['is_current'] else ""
            logger.info(f"   • {m['model_display_name']} ({m['model_id']})")
            input_price = m['cost_per_1m_input_tokens'] or 0
            output_price = m['cost_per_1m_output_tokens'] or 0
            logger.info(f"     Pricing: ${input_price:.2f}/${output_price:.2f} per 1M tokens {current_marker}")
        
        cur.close()
        conn.close()
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("✅ ACTUALIZACIÓN COMPLETADA EXITOSAMENTE")
        logger.info("=" * 70)
        logger.info("")
        logger.info("📋 PRÓXIMOS PASOS:")
        logger.info("   1. El cron diario ahora usará GPT-5.2 automáticamente")
        logger.info("   2. Puedes forzar un análisis manualmente si lo deseas")
        logger.info("   3. Verifica los logs del próximo cron para confirmar")
        logger.info("")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error actualizando modelo: {e}", exc_info=True)
        conn.rollback()
        cur.close()
        conn.close()
        return False


def test_gpt52_connection():
    """Prueba que GPT-5.2 funcione correctamente"""
    
    logger.info("")
    logger.info("=" * 70)
    logger.info("🧪 PROBANDO CONEXIÓN CON GPT-5.2")
    logger.info("=" * 70)
    
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        logger.error("❌ OPENAI_API_KEY no está configurada")
        logger.info("   Configúrala con: export OPENAI_API_KEY='sk-proj-...'")
        return False
    
    logger.info(f"   API Key encontrada: {api_key[:10]}...{api_key[-4:]}")
    
    try:
        from services.llm_providers import LLMProviderFactory
        
        logger.info("")
        logger.info("1️⃣ Creando proveedor OpenAI...")
        
        provider = LLMProviderFactory.create_provider(
            'openai', 
            api_key,
            validate_connection=True
        )
        
        if not provider:
            logger.error("❌ No se pudo crear el proveedor OpenAI")
            return False
        
        logger.info(f"   ✅ Proveedor creado")
        logger.info(f"   Modelo: {provider.model}")
        logger.info(f"   Display: {provider.get_model_display_name()}")
        
        logger.info("")
        logger.info("2️⃣ Ejecutando query de prueba...")
        
        result = provider.execute_query("Responde solo con 'OK' si me escuchas.")
        
        if result.get('success'):
            logger.info(f"   ✅ Query exitosa")
            logger.info(f"   Respuesta: {result.get('content', '')[:100]}...")
            logger.info(f"   Tokens: {result.get('tokens', 0)}")
            logger.info(f"   Coste: ${result.get('cost_usd', 0):.6f}")
            logger.info(f"   Tiempo: {result.get('response_time_ms', 0)}ms")
            return True
        else:
            logger.error(f"   ❌ Query falló: {result.get('error', 'Unknown')}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error probando GPT-5.2: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    logger.info("")
    logger.info("🚀 SCRIPT DE ACTUALIZACIÓN A GPT-5.2")
    logger.info("   Fecha de lanzamiento: 12 Diciembre 2025")
    logger.info("")
    
    # Paso 1: Actualizar BD
    if not update_openai_model_to_gpt52():
        logger.error("❌ Falló la actualización de la base de datos")
        sys.exit(1)
    
    # Paso 2: Probar conexión
    if not test_gpt52_connection():
        logger.warning("⚠️ La conexión a GPT-5.2 falló, pero la BD se actualizó")
        logger.warning("   Verifica la API key y los permisos")
        sys.exit(0)  # No es un error fatal
    
    logger.info("")
    logger.info("🎉 TODO LISTO - GPT-5.2 CONFIGURADO Y FUNCIONANDO")
    logger.info("")
    sys.exit(0)

