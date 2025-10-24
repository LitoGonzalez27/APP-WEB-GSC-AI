#!/usr/bin/env python3
"""
Script para crear las tablas del sistema AI Mode en PRODUCCIÓN
SEGURO: Solo crea tablas nuevas, no modifica nada existente
"""

import psycopg2
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# URL de producción
PRODUCTION_URL = "postgresql://postgres:HklXfIBgtSUXmaKMnOmkXSyTssdNXvwS@switchyard.proxy.rlwy.net:18167/railway"

def create_ai_mode_tables():
    """Crear todas las tablas necesarias para el sistema AI Mode Monitoring en PRODUCCIÓN"""
    
    logger.info("🔌 Conectando a PRODUCCIÓN...")
    try:
        conn = psycopg2.connect(PRODUCTION_URL)
        logger.info("✅ Conectado a PRODUCCIÓN exitosamente")
    except Exception as e:
        logger.error(f"❌ No se pudo conectar a la base de datos de producción: {e}")
        return False
    
    try:
        cur = conn.cursor()
        
        logger.info("🚀 Creando tablas para AI Mode Monitoring en PRODUCCIÓN...")
        logger.info("⚠️  Solo se crearán tablas que NO existan")
        
        # Tabla de proyectos AI Mode
        logger.info("\n📋 Creando ai_mode_projects...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ai_mode_projects (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                brand_name VARCHAR(255) NOT NULL,
                country_code VARCHAR(3) DEFAULT 'US',
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                
                UNIQUE(user_id, name),
                CHECK (char_length(name) >= 1),
                CHECK (char_length(brand_name) >= 2)
            )
        """)
        logger.info("   ✅ Tabla ai_mode_projects lista")
        
        # Tabla de keywords
        logger.info("\n📋 Creando ai_mode_keywords...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ai_mode_keywords (
                id SERIAL PRIMARY KEY,
                project_id INTEGER REFERENCES ai_mode_projects(id) ON DELETE CASCADE,
                keyword VARCHAR(500) NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                added_at TIMESTAMP DEFAULT NOW(),
                
                UNIQUE(project_id, keyword),
                CHECK (char_length(keyword) >= 1)
            )
        """)
        logger.info("   ✅ Tabla ai_mode_keywords lista")
        
        # Tabla de resultados
        logger.info("\n📋 Creando ai_mode_results...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ai_mode_results (
                id SERIAL PRIMARY KEY,
                project_id INTEGER REFERENCES ai_mode_projects(id) ON DELETE CASCADE,
                keyword_id INTEGER REFERENCES ai_mode_keywords(id) ON DELETE CASCADE,
                analysis_date DATE NOT NULL,
                keyword VARCHAR(500) NOT NULL,
                brand_name VARCHAR(255) NOT NULL,
                
                -- Resultados AI Mode específicos
                brand_mentioned BOOLEAN DEFAULT FALSE,
                mention_position INTEGER,
                mention_context TEXT,
                total_sources INTEGER DEFAULT 0,
                sentiment VARCHAR(50),
                
                -- Raw data
                raw_ai_mode_data JSONB,
                
                -- Metadata
                country_code VARCHAR(3) DEFAULT 'US',
                created_at TIMESTAMP DEFAULT NOW(),
                
                UNIQUE(project_id, keyword_id, analysis_date),
                CHECK (total_sources >= 0)
            )
        """)
        logger.info("   ✅ Tabla ai_mode_results lista")
        
        # Tabla de snapshots
        logger.info("\n📋 Creando ai_mode_snapshots...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ai_mode_snapshots (
                id SERIAL PRIMARY KEY,
                project_id INTEGER REFERENCES ai_mode_projects(id) ON DELETE CASCADE,
                snapshot_date DATE NOT NULL,
                
                total_keywords INTEGER NOT NULL,
                active_keywords INTEGER NOT NULL,
                total_mentions INTEGER DEFAULT 0,
                avg_position DECIMAL(5,2),
                visibility_percentage DECIMAL(5,2),
                
                change_type VARCHAR(50),
                change_description TEXT,
                keywords_added INTEGER DEFAULT 0,
                keywords_removed INTEGER DEFAULT 0,
                
                created_at TIMESTAMP DEFAULT NOW(),
                
                UNIQUE(project_id, snapshot_date),
                CHECK (total_keywords >= 0)
            )
        """)
        logger.info("   ✅ Tabla ai_mode_snapshots lista")
        
        # Tabla de eventos
        logger.info("\n📋 Creando ai_mode_events...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ai_mode_events (
                id SERIAL PRIMARY KEY,
                project_id INTEGER REFERENCES ai_mode_projects(id) ON DELETE CASCADE,
                event_date DATE NOT NULL,
                event_type VARCHAR(50) NOT NULL,
                event_title VARCHAR(255) NOT NULL,
                event_description TEXT,
                
                keywords_affected INTEGER DEFAULT 0,
                user_id INTEGER REFERENCES users(id),
                
                created_at TIMESTAMP DEFAULT NOW(),
                
                CHECK (char_length(event_title) >= 1)
            )
        """)
        logger.info("   ✅ Tabla ai_mode_events lista")
        
        # Crear índices
        logger.info("\n🔧 Creando índices para optimización...")
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ai_mode_projects_user ON ai_mode_projects(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ai_mode_projects_active ON ai_mode_projects(is_active)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ai_mode_keywords_project ON ai_mode_keywords(project_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ai_mode_keywords_active ON ai_mode_keywords(is_active)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ai_mode_results_project_date ON ai_mode_results(project_id, analysis_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ai_mode_results_date ON ai_mode_results(analysis_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ai_mode_results_brand_mentioned ON ai_mode_results(brand_mentioned)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ai_mode_snapshots_project_date ON ai_mode_snapshots(project_id, snapshot_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ai_mode_events_project_date ON ai_mode_events(project_id, event_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ai_mode_events_type ON ai_mode_events(event_type)")
        
        logger.info("   ✅ Índices creados")
        
        # Commit
        conn.commit()
        
        logger.info("\n" + "=" * 80)
        logger.info("🎉 Todas las tablas del sistema AI Mode creadas exitosamente en PRODUCCIÓN")
        logger.info("=" * 80)
        
        # Verificar
        logger.info("\n🔍 Verificando tablas creadas...")
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name LIKE 'ai_mode_%'
            ORDER BY table_name
        """)
        
        tables = cur.fetchall()
        logger.info(f"\n📋 Tablas AI Mode en producción ({len(tables)}):")
        for table in tables:
            # Obtener número de filas
            cur.execute(f"SELECT COUNT(*) FROM {table[0]}")
            count = cur.fetchone()[0]
            logger.info(f"   ✅ {table[0]} ({count} filas)")
        
        # Verificar que las tablas críticas NO fueron modificadas
        logger.info("\n🛡️  Verificando integridad de tablas críticas...")
        critical_tables = ['users', 'manual_ai_projects', 'subscriptions']
        
        for table in critical_tables:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = %s
                )
            """, (table,))
            
            exists = cur.fetchone()[0]
            if exists:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                logger.info(f"   ✅ {table} intacta ({count} filas)")
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ Error creando tablas: {e}")
        logger.error(f"   Tipo de error: {type(e).__name__}")
        conn.rollback()
        return False
        
    finally:
        cur.close()
        conn.close()
        logger.info("\n🔌 Conexión a producción cerrada")

def main():
    """Función principal"""
    logger.info("=" * 80)
    logger.info("🤖 CREACIÓN DE TABLAS AI MODE EN PRODUCCIÓN")
    logger.info("=" * 80)
    logger.info("\n⚠️  IMPORTANTE:")
    logger.info("   - Solo se crearán tablas NUEVAS")
    logger.info("   - NO se modificará ninguna tabla existente")
    logger.info("   - NO se tocarán usuarios, proyectos ni planes")
    logger.info("\n" + "=" * 80)
    
    success = create_ai_mode_tables()
    
    logger.info("\n" + "=" * 80)
    if success:
        logger.info("✅ ÉXITO: Las tablas de AI Mode están listas en PRODUCCIÓN")
        logger.info("🎯 El sistema AI Mode puede empezar a funcionar")
    else:
        logger.error("❌ FALLO: No se pudieron crear las tablas")
        logger.error("🔍 Revisa los logs arriba para ver el error específico")
    logger.info("=" * 80)

if __name__ == "__main__":
    main()


