#!/usr/bin/env python3
"""
Migración: Separar campos de marca y competidores en dominios y palabras clave

CAMBIOS:
- brand_name (VARCHAR) -> mantener pero será obsoleto
- brand_domain (VARCHAR) -> nuevo campo para dominio
- brand_keywords (JSONB) -> nuevo campo para palabras clave de marca
- competitors (JSONB) -> mantener pero será obsoleto  
- competitor_domains (JSONB) -> nuevo campo para dominios de competidores
- competitor_keywords (JSONB) -> nuevo campo para palabras clave de competidores

MIGRACIÓN DE DATOS EXISTENTES:
- brand_name se copia a brand_keywords[0] (por compatibilidad)
- competitors se copia a competitor_keywords (por compatibilidad)
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def migrate_llm_brand_fields():
    """
    Añade nuevos campos para dominios y palabras clave separados
    """
    
    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la base de datos")
        return False
    
    try:
        cur = conn.cursor()
        logger.info("=" * 70)
        logger.info("🔄 MIGRANDO CAMPOS DE MARCA Y COMPETIDORES")
        logger.info("=" * 70)
        logger.info("")
        
        # ===================================
        # 1. AÑADIR NUEVOS CAMPOS
        # ===================================
        logger.info("📋 Paso 1: Añadiendo nuevos campos...")
        
        # Campo para dominio de marca
        logger.info("   → Añadiendo brand_domain...")
        cur.execute("""
            ALTER TABLE llm_monitoring_projects
            ADD COLUMN IF NOT EXISTS brand_domain VARCHAR(255)
        """)
        
        # Campo para palabras clave de marca (array JSON)
        logger.info("   → Añadiendo brand_keywords...")
        cur.execute("""
            ALTER TABLE llm_monitoring_projects
            ADD COLUMN IF NOT EXISTS brand_keywords JSONB DEFAULT '[]'::jsonb
        """)
        
        # Campo para dominios de competidores (array JSON)
        logger.info("   → Añadiendo competitor_domains...")
        cur.execute("""
            ALTER TABLE llm_monitoring_projects
            ADD COLUMN IF NOT EXISTS competitor_domains JSONB DEFAULT '[]'::jsonb
        """)
        
        # Campo para palabras clave de competidores (array JSON)
        logger.info("   → Añadiendo competitor_keywords...")
        cur.execute("""
            ALTER TABLE llm_monitoring_projects
            ADD COLUMN IF NOT EXISTS competitor_keywords JSONB DEFAULT '[]'::jsonb
        """)
        
        logger.info("   ✅ Nuevos campos añadidos")
        
        # ===================================
        # 2. MIGRAR DATOS EXISTENTES
        # ===================================
        logger.info("")
        logger.info("📦 Paso 2: Migrando datos existentes...")
        
        # Obtener proyectos existentes
        cur.execute("""
            SELECT id, brand_name, competitors
            FROM llm_monitoring_projects
            WHERE brand_keywords = '[]'::jsonb
        """)
        
        projects = cur.fetchall()
        logger.info(f"   Proyectos a migrar: {len(projects)}")
        
        migrated = 0
        for project in projects:
            project_id = project['id']
            brand_name = project['brand_name']
            competitors = project['competitors'] or []
            
            # Migrar brand_name a brand_keywords (por compatibilidad)
            if brand_name:
                cur.execute("""
                    UPDATE llm_monitoring_projects
                    SET brand_keywords = %s::jsonb
                    WHERE id = %s
                """, (f'["{brand_name}"]', project_id))
            
            # Migrar competitors a competitor_keywords (por compatibilidad)
            if competitors and len(competitors) > 0:
                import json
                cur.execute("""
                    UPDATE llm_monitoring_projects
                    SET competitor_keywords = %s::jsonb
                    WHERE id = %s
                """, (json.dumps(competitors), project_id))
            
            migrated += 1
        
        logger.info(f"   ✅ {migrated} proyectos migrados")
        
        # ===================================
        # 3. COMMIT
        # ===================================
        conn.commit()
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("✅ MIGRACIÓN COMPLETADA EXITOSAMENTE")
        logger.info("=" * 70)
        logger.info("")
        logger.info("📋 Cambios realizados:")
        logger.info("   ✓ brand_domain (VARCHAR) - nuevo campo")
        logger.info("   ✓ brand_keywords (JSONB) - nuevo campo con datos migrados")
        logger.info("   ✓ competitor_domains (JSONB) - nuevo campo")
        logger.info("   ✓ competitor_keywords (JSONB) - nuevo campo con datos migrados")
        logger.info("")
        logger.info("💡 Nota:")
        logger.info("   • Los campos brand_name y competitors se mantienen por compatibilidad")
        logger.info("   • Los nuevos campos ya contienen los datos migrados")
        logger.info("")
        
        return True
        
    except Exception as e:
        logger.error("")
        logger.error("=" * 70)
        logger.error("❌ ERROR EN LA MIGRACIÓN")
        logger.error("=" * 70)
        logger.error(f"Error: {e}", exc_info=True)
        logger.error("")
        conn.rollback()
        return False
        
    finally:
        cur.close()
        conn.close()


def main():
    """Función principal"""
    logger.info("")
    logger.info("╔" + "═" * 68 + "╗")
    logger.info("║" + " " * 10 + "MIGRACIÓN: CAMPOS DE MARCA Y COMPETIDORES" + " " * 17 + "║")
    logger.info("╚" + "═" * 68 + "╝")
    logger.info("")
    
    success = migrate_llm_brand_fields()
    
    if not success:
        logger.error("❌ Migración falló. Revisa los errores arriba.")
        sys.exit(1)
    
    logger.info("🎉 Migración completada con éxito!")
    sys.exit(0)


if __name__ == "__main__":
    main()


