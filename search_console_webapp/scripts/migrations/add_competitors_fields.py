#!/usr/bin/env python3
"""
Script para agregar campos de competidores a la tabla manual_ai_projects
SEGURO: Solo agrega campos nuevos si no existen
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_competitors_fields():
    """Agregar campos para competidores seleccionados a manual_ai_projects"""
    
    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la base de datos")
        return False
    
    try:
        cur = conn.cursor()
        
        logger.info("🚀 Agregando campos de competidores a manual_ai_projects...")
        
        # Agregar campo para competidores seleccionados (máximo 4)
        try:
            cur.execute("""
                ALTER TABLE manual_ai_projects 
                ADD COLUMN IF NOT EXISTS selected_competitors JSONB DEFAULT '[]'::jsonb
            """)
            logger.info("✅ Campo selected_competitors agregado")
        except Exception as e:
            logger.warning(f"⚠️ selected_competitors ya existe o error: {e}")
        
        # Agregar constraint para validar máximo 4 competidores
        try:
            cur.execute("""
                SELECT 1 FROM information_schema.table_constraints 
                WHERE constraint_name = 'check_max_competitors' 
                AND table_name = 'manual_ai_projects'
            """)
            if not cur.fetchone():
                cur.execute("""
                    ALTER TABLE manual_ai_projects 
                    ADD CONSTRAINT check_max_competitors 
                    CHECK (jsonb_array_length(selected_competitors) <= 4)
                """)
                logger.info("✅ Constraint check_max_competitors agregado")
            else:
                logger.info("ℹ️ Constraint check_max_competitors ya existe")
        except Exception as e:
            logger.warning(f"⚠️ Error con constraint: {e}")
        
        # Agregar índice para búsquedas rápidas en competidores
        try:
            cur.execute("""
                SELECT 1 FROM pg_indexes 
                WHERE indexname = 'idx_manual_ai_projects_competitors'
            """)
            if not cur.fetchone():
                cur.execute("""
                    CREATE INDEX idx_manual_ai_projects_competitors 
                    ON manual_ai_projects USING GIN (selected_competitors)
                """)
                logger.info("✅ Índice idx_manual_ai_projects_competitors creado")
            else:
                logger.info("ℹ️ Índice idx_manual_ai_projects_competitors ya existe")
        except Exception as e:
            logger.warning(f"⚠️ Error con índice: {e}")
        
        # Verificar la estructura actualizada
        cur.execute("""
            SELECT column_name, data_type, column_default 
            FROM information_schema.columns 
            WHERE table_name = 'manual_ai_projects' 
            AND column_name = 'selected_competitors'
        """)
        result = cur.fetchone()
        
        if result:
            logger.info(f"✅ Campo verificado: {result[0]} ({result[1]}) - default: {result[2]}")
            
            # Verificar que no hay problemas con el constraint
            cur.execute("SELECT COUNT(*) FROM manual_ai_projects")
            count = cur.fetchone()[0]
            logger.info(f"✅ Tabla manual_ai_projects tiene {count} registros")
            
        else:
            logger.error("❌ Campo selected_competitors no encontrado")
            return False
        
        conn.commit()
        logger.info("🎉 Modificaciones aplicadas exitosamente")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error modificando tabla: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    success = add_competitors_fields()
    if success:
        print("✅ Campos de competidores agregados exitosamente")
        sys.exit(0)
    else:
        print("❌ Error agregando campos de competidores")
        sys.exit(1)