#!/usr/bin/env python3
"""
Script para agregar campo de topic_clusters a la tabla manual_ai_projects
SEGURO: Solo agrega el campo si no existe
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_topic_clusters_field():
    """Agregar campo para topic clusters a manual_ai_projects"""
    
    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la base de datos")
        return False
    
    try:
        cur = conn.cursor()
        
        logger.info("🚀 Agregando campo de topic_clusters a manual_ai_projects...")
        
        # Agregar campo para topic clusters
        try:
            cur.execute("""
                ALTER TABLE manual_ai_projects 
                ADD COLUMN IF NOT EXISTS topic_clusters JSONB DEFAULT '{"enabled": false, "clusters": []}'::jsonb
            """)
            logger.info("✅ Campo topic_clusters agregado")
        except Exception as e:
            logger.warning(f"⚠️ topic_clusters ya existe o error: {e}")
        
        # Agregar índice GIN para búsquedas rápidas en clusters
        try:
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_manual_ai_projects_topic_clusters 
                ON manual_ai_projects USING GIN (topic_clusters)
            """)
            logger.info("✅ Índice GIN para topic_clusters creado")
        except Exception as e:
            logger.warning(f"⚠️ Error creando índice: {e}")
        
        # Commit de cambios
        conn.commit()
        logger.info("✅ Migración completada exitosamente")
        
        # Verificar que el campo existe
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'manual_ai_projects' 
            AND column_name = 'topic_clusters'
        """)
        
        result = cur.fetchone()
        if result:
            logger.info(f"✅ Verificación: Campo topic_clusters existe (tipo: {result['data_type']})")
            return True
        else:
            logger.error("❌ Error: Campo topic_clusters no se creó correctamente")
            return False
        
    except Exception as e:
        logger.error(f"❌ Error en migración: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            cur.close()
            conn.close()

if __name__ == '__main__':
    success = add_topic_clusters_field()
    sys.exit(0 if success else 1)

