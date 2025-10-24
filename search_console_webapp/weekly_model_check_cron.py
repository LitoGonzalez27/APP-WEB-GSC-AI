#!/usr/bin/env python3
"""
Script para verificación semanal de nuevos modelos LLM
Este script detecta si OpenAI, Anthropic, Google o Perplexity han lanzado nuevos modelos

CONFIGURACIÓN CRON:
# Ejecutar todos los domingos a las 00:00
0 0 * * 0 cd /path/to/your/app && python3 weekly_model_check_cron.py >> /var/log/model_check_cron.log 2>&1

RAILWAY SETUP:
Se configura en railway.json como job separado

IMPORTANTE:
- Detecta nuevos modelos de APIs de OpenAI, Google y Perplexity
- Anthropic requiere verificación manual (no expone lista de modelos)
- Inserta nuevos modelos en llm_model_registry con is_current=FALSE
- Notifica al admin por email/log
"""

import sys
import os
import logging
from datetime import datetime
from typing import List, Dict

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('model_check_cron')


def get_openai_models(api_key: str) -> List[Dict]:
    """
    Obtiene lista de modelos disponibles de OpenAI
    
    Returns:
        Lista de dicts con id, created, owned_by
    """
    try:
        import openai
        
        client = openai.OpenAI(api_key=api_key)
        models = client.models.list()
        
        # Filtrar solo modelos de chat
        chat_models = [
            {
                'model_id': m.id,
                'created': m.created,
                'owned_by': m.owned_by
            }
            for m in models.data
            if 'gpt' in m.id.lower()
        ]
        
        logger.info(f"   OpenAI: {len(chat_models)} modelos encontrados")
        return chat_models
        
    except Exception as e:
        logger.error(f"   ❌ Error obteniendo modelos de OpenAI: {e}")
        return []


def get_google_models(api_key: str) -> List[Dict]:
    """
    Obtiene lista de modelos disponibles de Google Gemini
    
    Returns:
        Lista de dicts con name, display_name, description
    """
    try:
        import google.generativeai as genai
        
        genai.configure(api_key=api_key)
        models = genai.list_models()
        
        # Filtrar solo modelos generativos (no embeddings)
        generative_models = []
        
        for m in models:
            if 'generateContent' in m.supported_generation_methods:
                # Extraer ID limpio (quitar 'models/' prefix)
                model_id = m.name.replace('models/', '')
                
                generative_models.append({
                    'model_id': model_id,
                    'display_name': m.display_name,
                    'description': m.description[:100] if m.description else ''
                })
        
        logger.info(f"   Google: {len(generative_models)} modelos encontrados")
        return generative_models
        
    except Exception as e:
        logger.error(f"   ❌ Error obteniendo modelos de Google: {e}")
        return []


def get_perplexity_models(api_key: str) -> List[Dict]:
    """
    Obtiene lista de modelos de Perplexity
    
    NOTA: Perplexity usa API compatible con OpenAI pero con base_url diferente
    
    Returns:
        Lista de dicts con model_id
    """
    try:
        import openai
        
        client = openai.OpenAI(
            api_key=api_key,
            base_url="https://api.perplexity.ai"
        )
        
        models = client.models.list()
        
        perplexity_models = [
            {
                'model_id': m.id,
                'created': m.created if hasattr(m, 'created') else None
            }
            for m in models.data
        ]
        
        logger.info(f"   Perplexity: {len(perplexity_models)} modelos encontrados")
        return perplexity_models
        
    except Exception as e:
        logger.error(f"   ❌ Error obteniendo modelos de Perplexity: {e}")
        return []


def get_existing_models_from_db():
    """
    Obtiene lista de modelos ya registrados en BD
    
    Returns:
        Dict[provider, List[model_id]]
    """
    from database import get_db_connection
    
    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a BD")
        return {}
    
    try:
        cur = conn.cursor()
        
        cur.execute("""
            SELECT llm_provider, model_id, is_current
            FROM llm_model_registry
            ORDER BY llm_provider, model_id
        """)
        
        models = cur.fetchall()
        
        # Agrupar por proveedor
        by_provider = {}
        for m in models:
            provider = m['llm_provider']
            if provider not in by_provider:
                by_provider[provider] = []
            by_provider[provider].append({
                'model_id': m['model_id'],
                'is_current': m['is_current']
            })
        
        return by_provider
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo modelos de BD: {e}")
        return {}
    finally:
        cur.close()
        conn.close()


def insert_new_model(provider: str, model_id: str, display_name: str = None):
    """
    Inserta un nuevo modelo en la BD con is_current=FALSE
    
    Args:
        provider: Proveedor (openai, anthropic, google, perplexity)
        model_id: ID del modelo
        display_name: Nombre para mostrar (opcional)
    """
    from database import get_db_connection
    
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cur = conn.cursor()
        
        # Insertar con precios por defecto (admin deberá actualizarlos)
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
                %s, %s, %s,
                0.0, 0.0,
                FALSE,
                FALSE
            )
            ON CONFLICT (llm_provider, model_id) DO NOTHING
            RETURNING id
        """, (provider, model_id, display_name or model_id))
        
        result = cur.fetchone()
        conn.commit()
        
        if result:
            logger.info(f"      ✅ Insertado: {provider}/{model_id}")
            return True
        else:
            logger.debug(f"      ℹ️ Ya existe: {provider}/{model_id}")
            return False
        
    except Exception as e:
        logger.error(f"      ❌ Error insertando modelo: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()


def main():
    try:
        logger.info("")
        logger.info("=" * 70)
        logger.info("🕒 === WEEKLY MODEL CHECK CRON JOB STARTED ===")
        logger.info("=" * 70)
        logger.info(f"⏰ Timestamp: {datetime.now().isoformat()}")
        logger.info("")
        
        # 1. Obtener API keys (de env por ahora)
        logger.info("🔑 Obteniendo API keys...")
        api_keys = {
            'openai': os.getenv('OPENAI_API_KEY'),
            'anthropic': os.getenv('ANTHROPIC_API_KEY'),
            'google': os.getenv('GOOGLE_API_KEY'),
            'perplexity': os.getenv('PERPLEXITY_API_KEY')
        }
        
        # Filtrar keys vacías
        api_keys = {k: v for k, v in api_keys.items() if v}
        
        if not api_keys:
            logger.warning("⚠️ No se encontraron API keys en variables de entorno")
            logger.warning("   Variables esperadas: OPENAI_API_KEY, GOOGLE_API_KEY, PERPLEXITY_API_KEY")
            logger.info("🔔 MODEL CHECK SKIPPED: NO API KEYS")
            sys.exit(0)
        
        logger.info(f"✅ API keys disponibles: {list(api_keys.keys())}")
        logger.info("")
        
        # 2. Obtener modelos existentes en BD
        logger.info("📋 Obteniendo modelos registrados en BD...")
        existing_models = get_existing_models_from_db()
        
        for provider, models in existing_models.items():
            current = [m['model_id'] for m in models if m['is_current']]
            logger.info(f"   {provider}: {len(models)} modelos ({len(current)} actual(es))")
        
        logger.info("")
        
        # 3. Obtener modelos disponibles en APIs
        logger.info("🔍 Consultando APIs de proveedores...")
        
        available_models = {}
        
        # OpenAI
        if 'openai' in api_keys:
            logger.info("   Consultando OpenAI...")
            available_models['openai'] = get_openai_models(api_keys['openai'])
        
        # Google
        if 'google' in api_keys:
            logger.info("   Consultando Google Gemini...")
            available_models['google'] = get_google_models(api_keys['google'])
        
        # Perplexity
        if 'perplexity' in api_keys:
            logger.info("   Consultando Perplexity...")
            available_models['perplexity'] = get_perplexity_models(api_keys['perplexity'])
        
        # Anthropic (no tiene API para listar modelos)
        logger.info("   ⚠️ Anthropic: Verificación manual requerida")
        logger.info("      Modelos conocidos: claude-sonnet-4-5-20250929, claude-3-5-sonnet-20241022")
        
        logger.info("")
        
        # 4. Comparar y detectar nuevos modelos
        logger.info("🆕 Detectando nuevos modelos...")
        logger.info("")
        
        new_models_found = False
        
        for provider, models in available_models.items():
            existing_ids = [m['model_id'] for m in existing_models.get(provider, [])]
            
            new_models = [
                m for m in models
                if m['model_id'] not in existing_ids
            ]
            
            if new_models:
                new_models_found = True
                logger.info(f"🆕 {provider.upper()}: {len(new_models)} modelo(s) nuevo(s):")
                
                for model in new_models:
                    logger.info(f"   • {model['model_id']}")
                    
                    # Insertar en BD
                    display_name = model.get('display_name') or model['model_id']
                    insert_new_model(provider, model['model_id'], display_name)
                
                logger.info("")
            else:
                logger.info(f"✅ {provider.upper()}: No hay modelos nuevos")
        
        # 5. Resumen final
        logger.info("")
        logger.info("=" * 70)
        logger.info("📊 RESUMEN")
        logger.info("=" * 70)
        
        if new_models_found:
            logger.info("🆕 Se encontraron nuevos modelos")
            logger.info("   ⚠️ ACCIÓN REQUERIDA:")
            logger.info("      1. Revisar los nuevos modelos en llm_model_registry")
            logger.info("      2. Actualizar precios (cost_per_1m_input/output_tokens)")
            logger.info("      3. Marcar como disponible (is_available=TRUE)")
            logger.info("      4. Opcionalmente, marcar como actual (is_current=TRUE)")
        else:
            logger.info("✅ No se encontraron modelos nuevos")
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("")
        logger.info("🎉 MODEL CHECK COMPLETED SUCCESSFULLY")
        sys.exit(0)
        
    except ImportError as e:
        logger.error(f"❌ Import error: {e}", exc_info=True)
        logger.error("Sugerencia: instala las dependencias necesarias")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        logger.error("💥 MODEL CHECK CRON JOB CRASHED")
        sys.exit(1)


if __name__ == "__main__":
    main()

