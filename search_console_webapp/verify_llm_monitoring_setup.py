#!/usr/bin/env python3
"""
Verificación de Setup Multi-LLM Brand Monitoring
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def verify_setup():
    """Verificar que todas las tablas y modelos estén correctamente creados"""
    
    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la base de datos")
        return False
    
    try:
        cur = conn.cursor()
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("🔍 VERIFICACIÓN DEL SISTEMA MULTI-LLM BRAND MONITORING")
        logger.info("=" * 70)
        logger.info("")
        
        # 1. Verificar tablas
        logger.info("📋 [1/3] Verificando tablas...")
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND (table_name LIKE 'llm_%' OR table_name LIKE 'user_llm_%')
            ORDER BY table_name
        """)
        
        tables = cur.fetchall()
        expected_tables = [
            'llm_model_registry',
            'llm_monitoring_projects',
            'llm_monitoring_queries',
            'llm_monitoring_results',
            'llm_monitoring_snapshots',
            'llm_visibility_comparison',
            'user_llm_api_keys'
        ]
        
        found_tables = [t['table_name'] for t in tables]
        
        for table in expected_tables:
            if table in found_tables:
                logger.info(f"   ✅ {table}")
            else:
                logger.error(f"   ❌ {table} - NO ENCONTRADA")
        
        # 2. Verificar modelos insertados
        logger.info("")
        logger.info("📦 [2/3] Verificando modelos insertados...")
        cur.execute("""
            SELECT 
                llm_provider, 
                model_id, 
                model_display_name, 
                cost_per_1m_input_tokens,
                cost_per_1m_output_tokens,
                is_current,
                is_available
            FROM llm_model_registry
            ORDER BY llm_provider
        """)
        
        models = cur.fetchall()
        
        if len(models) == 0:
            logger.error("   ❌ No se encontraron modelos insertados")
            return False
        
        logger.info(f"   Modelos encontrados: {len(models)}")
        logger.info("")
        for model in models:
            status = "✅" if model['is_current'] and model['is_available'] else "⚠️"
            logger.info(f"   {status} {model['llm_provider'].upper()}")
            logger.info(f"      • Modelo: {model['model_display_name']}")
            logger.info(f"      • ID: {model['model_id']}")
            logger.info(f"      • Coste Input: ${model['cost_per_1m_input_tokens']}/1M tokens")
            logger.info(f"      • Coste Output: ${model['cost_per_1m_output_tokens']}/1M tokens")
            logger.info(f"      • Actual: {model['is_current']}")
            logger.info(f"      • Disponible: {model['is_available']}")
            logger.info("")
        
        # 3. Verificar índices
        logger.info("🔧 [3/3] Verificando índices...")
        cur.execute("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE schemaname = 'public' 
            AND indexname LIKE 'idx_llm%'
            ORDER BY indexname
        """)
        
        indices = cur.fetchall()
        logger.info(f"   Índices encontrados: {len(indices)}")
        for idx in indices:
            logger.info(f"   ✅ {idx['indexname']}")
        
        # 4. Verificar vista
        logger.info("")
        logger.info("📊 Verificando vista llm_visibility_comparison...")
        cur.execute("""
            SELECT table_name 
            FROM information_schema.views 
            WHERE table_schema = 'public' 
            AND table_name = 'llm_visibility_comparison'
        """)
        
        view = cur.fetchone()
        if view:
            logger.info("   ✅ Vista llm_visibility_comparison creada")
        else:
            logger.error("   ❌ Vista llm_visibility_comparison NO encontrada")
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("✅ VERIFICACIÓN COMPLETADA CON ÉXITO")
        logger.info("=" * 70)
        logger.info("")
        logger.info("🎯 El sistema está listo para el PASO 2: Proveedores LLM")
        logger.info("")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error durante la verificación: {e}")
        return False
        
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    success = verify_setup()
    sys.exit(0 if success else 1)

