#!/usr/bin/env python3
"""
Script para testear el sistema AI Mode Monitoring
Verifica que todos los componentes del backend estén correctamente configurados
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_ai_mode_tables():
    """Verificar que las tablas AI Mode existen en la base de datos"""
    logger.info("\n🧪 TEST 1: Verificando tablas de base de datos...")
    
    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la base de datos")
        return False
    
    cur = conn.cursor()
    
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name LIKE 'ai_mode_%'
        ORDER BY table_name
    """)
    
    tables = cur.fetchall()
    logger.info(f"📋 Tablas AI Mode encontradas: {[t['table_name'] for t in tables]}")
    
    expected = ['ai_mode_projects', 'ai_mode_keywords', 'ai_mode_results', 
                'ai_mode_snapshots', 'ai_mode_events']
    
    all_exist = True
    for table in expected:
        exists = any(t['table_name'] == table for t in tables)
        status = "✅" if exists else "❌"
        logger.info(f"{status} Tabla: {table}")
        if not exists:
            all_exist = False
    
    cur.close()
    conn.close()
    
    if all_exist:
        logger.info("✅ TEST 1 PASSED: Todas las tablas existen")
    else:
        logger.error("❌ TEST 1 FAILED: Faltan algunas tablas")
    
    return all_exist

def test_bridge_import():
    """Test de importación del bridge"""
    logger.info("\n🧪 TEST 2: Verificando bridge import...")
    
    try:
        from ai_mode_system_bridge import ai_mode_bp, USING_AI_MODE_SYSTEM
        logger.info(f"✅ Bridge importado correctamente")
        logger.info(f"   - ai_mode_bp: {ai_mode_bp}")
        logger.info(f"   - USING_AI_MODE_SYSTEM: {USING_AI_MODE_SYSTEM}")
        
        if ai_mode_bp and USING_AI_MODE_SYSTEM:
            logger.info("✅ TEST 2 PASSED: Bridge funciona correctamente")
            return True
        else:
            logger.error("❌ TEST 2 FAILED: Bridge no cargó correctamente")
            return False
            
    except Exception as e:
        logger.error(f"❌ TEST 2 FAILED: Error importando bridge: {e}")
        return False

def test_config():
    """Test de configuración"""
    logger.info("\n🧪 TEST 3: Verificando configuración...")
    
    try:
        from ai_mode_projects.config import AI_MODE_KEYWORD_ANALYSIS_COST, CRON_LOCK_CLASS_ID, EVENT_TYPES
        logger.info(f"✅ Configuración cargada:")
        logger.info(f"   - AI_MODE_KEYWORD_ANALYSIS_COST: {AI_MODE_KEYWORD_ANALYSIS_COST}")
        logger.info(f"   - CRON_LOCK_CLASS_ID: {CRON_LOCK_CLASS_ID}")
        logger.info(f"   - EVENT_TYPES: {len(EVENT_TYPES)} tipos definidos")
        logger.info("✅ TEST 3 PASSED: Configuración correcta")
        return True
    except Exception as e:
        logger.error(f"❌ TEST 3 FAILED: Error cargando config: {e}")
        return False

def test_repositories():
    """Test de repositorios"""
    logger.info("\n🧪 TEST 4: Verificando repositorios...")
    
    try:
        from ai_mode_projects.models.project_repository import ProjectRepository
        from ai_mode_projects.models.keyword_repository import KeywordRepository
        from ai_mode_projects.models.result_repository import ResultRepository
        
        project_repo = ProjectRepository()
        keyword_repo = KeywordRepository()
        result_repo = ResultRepository()
        
        logger.info("✅ Repositorios instanciados correctamente:")
        logger.info(f"   - ProjectRepository: {project_repo}")
        logger.info(f"   - KeywordRepository: {keyword_repo}")
        logger.info(f"   - ResultRepository: {result_repo}")
        logger.info("✅ TEST 4 PASSED: Repositorios funcionan")
        return True
    except Exception as e:
        logger.error(f"❌ TEST 4 FAILED: Error con repositorios: {e}")
        return False

def test_services():
    """Test de servicios"""
    logger.info("\n🧪 TEST 5: Verificando servicios...")
    
    try:
        from ai_mode_projects.services.analysis_service import AnalysisService
        from ai_mode_projects.services.project_service import ProjectService
        
        analysis_service = AnalysisService()
        project_service = ProjectService()
        
        logger.info("✅ Servicios instanciados correctamente:")
        logger.info(f"   - AnalysisService: {analysis_service}")
        logger.info(f"   - ProjectService: {project_service}")
        logger.info("✅ TEST 5 PASSED: Servicios funcionan")
        return True
    except Exception as e:
        logger.error(f"❌ TEST 5 FAILED: Error con servicios: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_routes():
    """Test de rutas"""
    logger.info("\n🧪 TEST 6: Verificando rutas...")
    
    try:
        from ai_mode_projects.routes import projects, keywords, analysis, results, exports
        
        logger.info("✅ Rutas importadas correctamente:")
        logger.info(f"   - projects: {projects}")
        logger.info(f"   - keywords: {keywords}")
        logger.info(f"   - analysis: {analysis}")
        logger.info(f"   - results: {results}")
        logger.info(f"   - exports: {exports}")
        logger.info("✅ TEST 6 PASSED: Rutas funcionan")
        return True
    except Exception as e:
        logger.error(f"❌ TEST 6 FAILED: Error con rutas: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_validators():
    """Test de validadores"""
    logger.info("\n🧪 TEST 7: Verificando validadores...")
    
    try:
        from ai_mode_projects.utils.validators import check_ai_mode_access
        
        # Test con usuario free (sin acceso)
        user_free = {'plan': 'free'}
        has_access, error = check_ai_mode_access(user_free)
        
        if not has_access:
            logger.info("✅ Validator rechaza correctamente plan free")
        else:
            logger.error("❌ Validator NO rechaza plan free")
            return False
        
        # Test con usuario premium (con acceso)
        user_premium = {'plan': 'premium'}
        has_access, error = check_ai_mode_access(user_premium)
        
        if has_access:
            logger.info("✅ Validator acepta correctamente plan premium")
        else:
            logger.error("❌ Validator NO acepta plan premium")
            return False
        
        logger.info("✅ TEST 7 PASSED: Validadores funcionan correctamente")
        return True
    except Exception as e:
        logger.error(f"❌ TEST 7 FAILED: Error con validadores: {e}")
        return False

if __name__ == "__main__":
    logger.info("=" * 70)
    logger.info("🧪 TESTING AI MODE MONITORING SYSTEM - BACKEND")
    logger.info("=" * 70)
    
    tests_passed = 0
    tests_total = 7
    
    if test_ai_mode_tables():
        tests_passed += 1
    
    if test_bridge_import():
        tests_passed += 1
    
    if test_config():
        tests_passed += 1
    
    if test_repositories():
        tests_passed += 1
    
    if test_services():
        tests_passed += 1
    
    if test_routes():
        tests_passed += 1
    
    if test_validators():
        tests_passed += 1
    
    logger.info("\n" + "=" * 70)
    logger.info(f"📊 RESULTADOS FINALES: {tests_passed}/{tests_total} tests passed")
    logger.info("=" * 70)
    
    if tests_passed == tests_total:
        logger.info("✅ ¡TODOS LOS TESTS DEL BACKEND PASARON!")
        logger.info("🎉 El sistema AI Mode está listo para el frontend")
        sys.exit(0)
    else:
        logger.error(f"❌ FALLOS: {tests_total - tests_passed} tests fallaron")
        logger.error("⚠️ Revisa los errores arriba antes de continuar con el frontend")
        sys.exit(1)

