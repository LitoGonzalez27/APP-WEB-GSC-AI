#!/usr/bin/env python3
"""
Script de inicialización de la base de datos
Crea las tablas necesarias y datos de prueba si es necesario
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import (
    init_database, 
    ensure_sample_data, 
    migrate_user_timestamps,
    get_ai_overview_stats,
    init_ai_overview_tables
)
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Función principal de inicialización"""
    logger.info("🚀 Iniciando inicialización de la base de datos...")
    
    try:
        # 1. Inicializar tablas principales (users + ai_overview_analysis)
        logger.info("📋 Creando tablas principales...")
        if init_database():
            logger.info("✅ Tablas principales inicializadas correctamente")
        else:
            logger.error("❌ Error inicializando tablas principales")
            return False
        
        # 2. Migrar timestamps si es necesario
        logger.info("🔄 Verificando migración de timestamps...")
        if migrate_user_timestamps():
            logger.info("✅ Migración de timestamps completada")
        else:
            logger.warning("⚠️ Error en migración de timestamps")
        
        # 3. Asegurar datos de muestra
        logger.info("👥 Verificando datos de muestra...")
        if ensure_sample_data():
            logger.info("✅ Datos de muestra verificados")
        else:
            logger.warning("⚠️ Error con datos de muestra")
        
        # 4. Verificar tablas de AI Overview específicamente
        logger.info("🤖 Verificando tablas de AI Overview...")
        if init_ai_overview_tables():
            logger.info("✅ Tablas de AI Overview verificadas")
        else:
            logger.error("❌ Error con tablas de AI Overview")
            return False
        
        # 5. Inicializar tablas del Manual AI System (opcional)
        logger.info("🔧 Verificando tablas del Manual AI System...")
        try:
            from create_manual_ai_tables import create_manual_ai_tables
            if create_manual_ai_tables():
                logger.info("✅ Tablas del Manual AI System verificadas")
            else:
                logger.warning("⚠️ Error con tablas del Manual AI System (no crítico)")
        except ImportError:
            logger.info("ℹ️ Manual AI System no disponible - saltando inicialización")
        except Exception as e:
            logger.warning(f"⚠️ Error inicializando Manual AI System: {e} (no crítico)")
        
        # 6. Obtener estadísticas iniciales
        logger.info("📊 Obteniendo estadísticas iniciales...")
        try:
            ai_stats = get_ai_overview_stats()
            logger.info(f"📈 Estadísticas AI Overview: {ai_stats.get('total_analyses', 0)} análisis en base de datos")
        except Exception as e:
            logger.warning(f"⚠️ Error obteniendo estadísticas: {e}")
        
        # 7. Verificar conexión Redis (no crítico)
        logger.info("💾 Verificando sistema de caché...")
        try:
            from services.ai_cache import ai_cache
            cache_stats = ai_cache.get_cache_stats()
            if cache_stats.get('cache_available'):
                logger.info("✅ Sistema de caché Redis disponible")
                logger.info(f"📦 Caché: {cache_stats.get('ai_analyses_cached', 0)} análisis en caché")
            else:
                logger.warning("⚠️ Redis no disponible - funcionando sin caché")
        except Exception as e:
            logger.warning(f"⚠️ Error verificando caché: {e}")
        
        logger.info("🎉 Inicialización completada exitosamente")
        logger.info("=" * 50)
        logger.info("💡 El sistema está listo para:")
        logger.info("   - Análisis de AI Overview con persistencia")
        logger.info("   - Manual AI Analysis (proyectos independientes)")
        logger.info("   - Sistema de caché inteligente")
        logger.info("   - Gráficos de tipología de consultas")
        logger.info("   - Gestión de usuarios y autenticación")
        logger.info("=" * 50)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error crítico en inicialización: {e}")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        logger.info("✅ Script de inicialización completado con éxito")
        sys.exit(0)
    else:
        logger.error("❌ Script de inicialización falló")
        sys.exit(1) 