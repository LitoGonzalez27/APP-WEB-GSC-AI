#!/usr/bin/env python3
"""
Migración: Añadir campo country_code a llm_monitoring_projects

Este script añade el campo country_code (VARCHAR 2) para almacenar el código ISO-2
del país desde el cual se ejecutará el análisis de menciones de marca en LLMs.

Similar a AI Mode y Manual AI, permite análisis regionalizados.
"""

import sys
import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Añadir path para imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection


def main():
    """Añadir campo country_code a la tabla llm_monitoring_projects"""
    
    logger.info("=" * 70)
    logger.info("INICIANDO MIGRACIÓN: Añadir country_code a LLM Monitoring Projects")
    logger.info("=" * 70)
    
    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la base de datos")
        sys.exit(1)
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. Añadir columna country_code
        logger.info("\n📊 Paso 1: Añadiendo columna country_code...")
        cur.execute("""
            ALTER TABLE llm_monitoring_projects 
            ADD COLUMN IF NOT EXISTS country_code VARCHAR(2) DEFAULT 'ES'
        """)
        conn.commit()
        logger.info("✅ Columna country_code añadida (VARCHAR(2), default 'ES')")
        
        # 2. Actualizar proyectos existentes que tengan NULL
        logger.info("\n📊 Paso 2: Actualizando proyectos existentes...")
        cur.execute("""
            UPDATE llm_monitoring_projects
            SET country_code = 'ES'
            WHERE country_code IS NULL
        """)
        updated_count = cur.rowcount
        conn.commit()
        logger.info(f"✅ {updated_count} proyectos actualizados con país por defecto (ES)")
        
        # 3. Verificar la migración
        logger.info("\n📊 Paso 3: Verificando migración...")
        cur.execute("""
            SELECT 
                column_name,
                data_type,
                character_maximum_length,
                column_default,
                is_nullable
            FROM information_schema.columns
            WHERE table_name = 'llm_monitoring_projects'
                AND column_name = 'country_code'
        """)
        
        column_info = cur.fetchone()
        if column_info:
            logger.info("✅ Columna verificada:")
            logger.info(f"   - Nombre: {column_info['column_name']}")
            logger.info(f"   - Tipo: {column_info['data_type']}")
            logger.info(f"   - Longitud: {column_info['character_maximum_length']}")
            logger.info(f"   - Default: {column_info['column_default']}")
            logger.info(f"   - Nullable: {column_info['is_nullable']}")
        else:
            logger.warning("⚠️  No se pudo verificar la columna")
        
        # 4. Mostrar resumen de proyectos por país
        logger.info("\n📊 Paso 4: Resumen de proyectos por país...")
        cur.execute("""
            SELECT 
                country_code,
                COUNT(*) as total_projects
            FROM llm_monitoring_projects
            WHERE is_active = TRUE
            GROUP BY country_code
            ORDER BY total_projects DESC
        """)
        
        projects_by_country = cur.fetchall()
        if projects_by_country:
            logger.info("Proyectos activos por país:")
            for row in projects_by_country:
                logger.info(f"   - {row['country_code']}: {row['total_projects']} proyectos")
        else:
            logger.info("   (No hay proyectos activos)")
        
        logger.info("\n" + "=" * 70)
        logger.info("✅ MIGRACIÓN COMPLETADA EXITOSAMENTE")
        logger.info("=" * 70)
        logger.info("\nPróximos pasos:")
        logger.info("1. Actualizar frontend (templates/llm_monitoring.html) con selector de país")
        logger.info("2. Modificar endpoints (llm_monitoring_routes.py) para guardar/leer country_code")
        logger.info("3. Actualizar JavaScript (static/js/llm_monitoring.js) para manejar el campo")
        logger.info("4. Configurar las APIs de LLM para usar el país en las consultas")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"\n❌ Error durante la migración: {e}", exc_info=True)
        conn.rollback()
        sys.exit(1)


if __name__ == '__main__':
    main()

