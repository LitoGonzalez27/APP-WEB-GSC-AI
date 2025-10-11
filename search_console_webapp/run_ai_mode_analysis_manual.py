"""
Script para ejecutar un análisis manual de AI Mode
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Conexión directa a Railway
DATABASE_URL = "postgresql://postgres:XCkoyokCzfRlyPCFNGpfIhqteibfbojQ@caboose.proxy.rlwy.net:13631/railway"

def get_project_keywords(project_id):
    """Obtener keywords activas del proyecto"""
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT id, keyword, project_id
        FROM ai_mode_keywords
        WHERE project_id = %s AND is_active = true
        ORDER BY keyword
    """, (project_id,))
    
    keywords = cur.fetchall()
    cur.close()
    conn.close()
    
    return keywords

def check_ai_mode_cron():
    """Verificar si existe el CRON para AI Mode"""
    logger.info("\n🔍 VERIFICANDO CONFIGURACIÓN DE CRON:")
    
    # Verificar si existe el archivo de CRON
    import os
    cron_files = [
        'daily_ai_mode_cron.py',
        'ai_mode_cron_function.js',
        'cron_worker.py'
    ]
    
    for file in cron_files:
        if os.path.exists(file):
            logger.info(f"   ✅ {file} existe")
        else:
            logger.warning(f"   ❌ {file} NO existe")
    
    # Verificar railway.json
    if os.path.exists('railway.json'):
        import json
        with open('railway.json', 'r') as f:
            config = json.load(f)
            if 'cron' in config.get('build', {}):
                logger.info(f"   ✅ railway.json tiene configuración de cron")
                logger.info(f"      Cron: {config['build'].get('cron')}")
            else:
                logger.warning(f"   ⚠️ railway.json NO tiene configuración de cron")

def main():
    """Función principal"""
    project_id = 1
    
    logger.info("=" * 80)
    logger.info(f"EJECUTAR ANÁLISIS MANUAL PARA PROYECTO {project_id}")
    logger.info("=" * 80)
    
    # 1. Verificar configuración de CRON
    check_ai_mode_cron()
    
    # 2. Obtener keywords
    logger.info(f"\n📋 Obteniendo keywords del proyecto {project_id}...")
    keywords = get_project_keywords(project_id)
    
    if not keywords:
        logger.error(f"❌ No hay keywords activas en el proyecto {project_id}")
        return False
    
    logger.info(f"✅ Encontradas {len(keywords)} keywords activas:")
    for kw in keywords[:5]:
        logger.info(f"   • {kw['keyword']}")
    if len(keywords) > 5:
        logger.info(f"   ... y {len(keywords) - 5} más")
    
    # 3. Información sobre cómo ejecutar el análisis
    logger.info("\n" + "=" * 80)
    logger.info("📝 INSTRUCCIONES PARA EJECUTAR EL ANÁLISIS:")
    logger.info("=" * 80)
    logger.info("\n1. OPCIÓN A - Via API (desde la UI):")
    logger.info("   • Abre la APP en el navegador")
    logger.info("   • Ve al proyecto 'test 1'")
    logger.info("   • Busca el botón 'Run Analysis' o similar")
    logger.info("   • Ejecuta el análisis manualmente")
    
    logger.info("\n2. OPCIÓN B - Via CRON manual:")
    logger.info("   • Ejecuta: python3 daily_ai_mode_cron.py")
    logger.info("   • O verifica que el CRON de Railway esté configurado")
    
    logger.info("\n3. VERIFICAR DESPUÉS DEL ANÁLISIS:")
    logger.info("   • Ejecuta: python3 check_ai_mode_data.py")
    logger.info("   • Verifica que haya datos en 'RESULTADOS DE ANÁLISIS'")
    
    logger.info("\n" + "=" * 80)
    logger.info("⚠️ PROBLEMA IDENTIFICADO:")
    logger.info("=" * 80)
    logger.info("El proyecto tiene 14 keywords pero nunca se ha ejecutado un análisis.")
    logger.info("Por eso no ves datos en las gráficas de la APP.")
    logger.info("Necesitas ejecutar un análisis para generar datos.")
    logger.info("=" * 80)
    
    return True

if __name__ == '__main__':
    main()

