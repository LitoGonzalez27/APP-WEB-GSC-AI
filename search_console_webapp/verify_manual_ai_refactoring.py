#!/usr/bin/env python3
"""
Script de verificación de la refactorización de Manual AI
Verifica que todos los módulos se puedan importar correctamente
"""

import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def verify_imports():
    """Verificar que todos los módulos nuevos se pueden importar"""
    errors = []
    successes = []
    
    # Lista de imports a verificar
    imports_to_check = [
        ("manual_ai", "Módulo principal"),
        ("manual_ai.config", "Configuración"),
        ("manual_ai.utils.decorators", "Decoradores"),
        ("manual_ai.utils.validators", "Validadores"),
        ("manual_ai.utils.helpers", "Helpers"),
        ("manual_ai.utils.country_utils", "Country Utils"),
        ("manual_ai.models.project_repository", "Project Repository"),
        ("manual_ai.models.keyword_repository", "Keyword Repository"),
        ("manual_ai.models.result_repository", "Result Repository"),
        ("manual_ai.models.event_repository", "Event Repository"),
        ("manual_ai.services.project_service", "Project Service"),
        ("manual_ai.services.domains_service", "Domains Service"),
        ("manual_ai.services.analysis_service", "Analysis Service"),
        ("manual_ai.services.statistics_service", "Statistics Service"),
        ("manual_ai.services.competitor_service", "Competitor Service"),
        ("manual_ai.services.cron_service", "Cron Service"),
        ("manual_ai.services.export_service", "Export Service"),
        ("manual_ai.routes.health", "Health Route"),
        ("manual_ai.routes.projects", "Projects Routes"),
        ("manual_ai.routes.keywords", "Keywords Routes"),
        ("manual_ai.routes.analysis", "Analysis Routes"),
        ("manual_ai.routes.results", "Results Routes"),
        ("manual_ai.routes.competitors", "Competitors Routes"),
        ("manual_ai.routes.exports", "Exports Routes"),
        ("manual_ai_system_bridge", "Compatibility Bridge"),
    ]
    
    logger.info("=" * 60)
    logger.info("VERIFICACIÓN DE IMPORTS DEL NUEVO SISTEMA")
    logger.info("=" * 60)
    
    for module_path, description in imports_to_check:
        try:
            __import__(module_path)
            successes.append((module_path, description))
            logger.info(f"✅ {description:30s} OK")
        except Exception as e:
            errors.append((module_path, description, str(e)))
            logger.error(f"❌ {description:30s} FAIL: {e}")
    
    return errors, successes


def verify_bridge():
    """Verificar que el bridge está funcionando correctamente"""
    logger.info("\n" + "=" * 60)
    logger.info("VERIFICACIÓN DEL BRIDGE")
    logger.info("=" * 60)
    
    try:
        from manual_ai_system_bridge import manual_ai_bp, run_daily_analysis_for_all_projects, USING_NEW_SYSTEM
        
        if USING_NEW_SYSTEM:
            logger.info("✅ Bridge está usando el NUEVO sistema modular")
        else:
            logger.info("⚠️  Bridge está usando el sistema ORIGINAL (fallback)")
        
        # Verificar que el blueprint existe
        if manual_ai_bp is None:
            logger.error("❌ manual_ai_bp es None")
            return False
        
        logger.info(f"✅ Blueprint cargado: {manual_ai_bp.name}")
        
        # Verificar que la función de cron existe
        if run_daily_analysis_for_all_projects is None:
            logger.error("❌ run_daily_analysis_for_all_projects es None")
            return False
        
        logger.info(f"✅ Función cron cargada: {run_daily_analysis_for_all_projects.__name__}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error verificando bridge: {e}")
        return False


def check_old_system_imports():
    """Verificar qué archivos aún importan del sistema antiguo"""
    import subprocess
    
    logger.info("\n" + "=" * 60)
    logger.info("BÚSQUEDA DE IMPORTS DEL SISTEMA ANTIGUO")
    logger.info("=" * 60)
    
    try:
        result = subprocess.run(
            ["grep", "-r", "--include=*.py", "from manual_ai_system import", "."],
            capture_output=True,
            text=True,
            cwd="/Users/carlosgonzalez/Desktop/app/APP-WEB-GSC-AI/search_console_webapp"
        )
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            # Filtrar el bridge y archivos de documentación
            relevant_lines = [
                line for line in lines 
                if 'manual_ai_system_bridge.py' not in line 
                and '/manual_ai/' not in line
                and '.md:' not in line
                and 'verify_manual_ai_refactoring.py' not in line
                and 'check_manual_ai_system.py' not in line
            ]
            
            if relevant_lines:
                logger.warning("⚠️  Archivos que aún importan del sistema antiguo:")
                for line in relevant_lines:
                    logger.warning(f"   {line}")
                return False
            else:
                logger.info("✅ No hay imports directos del sistema antiguo (excepto bridge)")
                return True
        else:
            logger.info("✅ No se encontraron imports del sistema antiguo")
            return True
            
    except Exception as e:
        logger.error(f"❌ Error buscando imports antiguos: {e}")
        return False


def main():
    """Función principal"""
    logger.info("\n")
    logger.info("╔" + "=" * 58 + "╗")
    logger.info("║" + "  VERIFICACIÓN DE REFACTORIZACIÓN - MANUAL AI SYSTEM  ".center(58) + "║")
    logger.info("╚" + "=" * 58 + "╝")
    logger.info("\n")
    
    # 1. Verificar imports
    errors, successes = verify_imports()
    
    # 2. Verificar bridge
    bridge_ok = verify_bridge()
    
    # 3. Verificar imports del sistema antiguo
    no_old_imports = check_old_system_imports()
    
    # Resumen final
    logger.info("\n" + "=" * 60)
    logger.info("RESUMEN FINAL")
    logger.info("=" * 60)
    logger.info(f"✅ Imports exitosos: {len(successes)}")
    logger.info(f"❌ Imports fallidos: {len(errors)}")
    logger.info(f"{'✅' if bridge_ok else '❌'} Bridge funcionando correctamente: {'Sí' if bridge_ok else 'No'}")
    logger.info(f"{'✅' if no_old_imports else '⚠️ '} Sin imports del sistema antiguo: {'Sí' if no_old_imports else 'No (revisar)'}")
    
    if errors:
        logger.error("\n❌ ERRORES ENCONTRADOS:")
        for module_path, description, error in errors:
            logger.error(f"   {description}: {error}")
    
    # Decisión final
    logger.info("\n" + "=" * 60)
    if not errors and bridge_ok:
        logger.info("✅ VERIFICACIÓN COMPLETADA CON ÉXITO")
        logger.info("✅ El sistema antiguo (manual_ai_system.py) PUEDE SER ELIMINADO")
        logger.info("\nSin embargo, se recomienda:")
        logger.info("1. Hacer un backup del archivo antes de eliminarlo")
        logger.info("2. Probar la aplicación en modo completo")
        logger.info("3. Verificar que los endpoints funcionan correctamente")
        logger.info("=" * 60)
        return 0
    else:
        logger.error("❌ VERIFICACIÓN FALLIDA")
        logger.error("❌ NO eliminar el sistema antiguo hasta resolver los errores")
        logger.error("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())

