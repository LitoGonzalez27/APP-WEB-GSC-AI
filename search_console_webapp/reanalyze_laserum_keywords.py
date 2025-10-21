#!/usr/bin/env python3
"""
Script para re-analizar keywords específicas de laserum.com con el código mejorado de detección de acentos.

Este script:
1. Encuentra el proyecto de laserum.com
2. Re-analiza las keywords especificadas
3. Actualiza los resultados en la base de datos
"""

import sys
import os
import logging
from datetime import date

# Setup path
sys.path.insert(0, os.path.dirname(__file__))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from database import get_db_connection
from manual_ai.services.analysis_service import AnalysisService
from manual_ai.models.project_repository import ProjectRepository
from manual_ai.models.keyword_repository import KeywordRepository
from manual_ai.models.result_repository import ResultRepository

def find_laserum_project():
    """Encuentra el proyecto de laserum.com"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT * FROM manual_ai_projects 
            WHERE domain ILIKE '%laserum%' 
            AND is_active = true
            ORDER BY created_at DESC
            LIMIT 1
        """)
        
        project = cur.fetchone()
        
        if project:
            return dict(project)
        else:
            logger.error("No se encontró proyecto de laserum.com")
            return None
            
    finally:
        cur.close()
        conn.close()

def find_keywords_to_reanalyze(project_id, keyword_texts=None):
    """
    Encuentra las keywords a re-analizar
    
    Args:
        project_id: ID del proyecto
        keyword_texts: Lista opcional de keywords específicas. Si es None, re-analiza todas.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        if keyword_texts:
            # Re-analizar solo keywords específicas
            placeholders = ','.join(['%s'] * len(keyword_texts))
            query = f"""
                SELECT * FROM manual_ai_keywords 
                WHERE project_id = %s 
                AND keyword IN ({placeholders})
                AND is_active = true
            """
            cur.execute(query, [project_id] + keyword_texts)
        else:
            # Re-analizar todas las keywords
            cur.execute("""
                SELECT * FROM manual_ai_keywords 
                WHERE project_id = %s 
                AND is_active = true
            """, (project_id,))
        
        keywords = cur.fetchall()
        return [dict(k) for k in keywords]
        
    finally:
        cur.close()
        conn.close()

def reanalyze_keywords(project, keywords):
    """
    Re-analiza las keywords especificadas
    
    Args:
        project: Dict con datos del proyecto
        keywords: Lista de dicts con keywords a analizar
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"RE-ANÁLISIS CON DETECCIÓN MEJORADA DE MARCA")
    logger.info(f"{'='*80}\n")
    
    logger.info(f"📌 Proyecto: {project['name']}")
    logger.info(f"📌 Dominio: {project['domain']}")
    logger.info(f"📌 Keywords a re-analizar: {len(keywords)}\n")
    
    # Inicializar servicio de análisis
    analysis_service = AnalysisService()
    result_repo = ResultRepository()
    
    today = date.today()
    success_count = 0
    error_count = 0
    
    for keyword_data in keywords:
        keyword = keyword_data['keyword']
        keyword_id = keyword_data['id']
        
        try:
            logger.info(f"\n🔍 Analizando: '{keyword}'...")
            
            # Eliminar resultado anterior del día de hoy si existe
            if result_repo.result_exists_for_date(project['id'], keyword_id, today):
                logger.info(f"   ⚠️  Eliminando resultado anterior de hoy...")
                result_repo.delete_result_for_date(project['id'], keyword_id, today)
            
            # Ejecutar análisis con código MEJORADO
            from manual_ai.services.serp_service import SerpService
            serp_service = SerpService()
            
            ai_result, serp_data = analysis_service._analyze_keyword(
                keyword, 
                project, 
                keyword_id
            )
            
            # Guardar resultado actualizado
            result_repo.create_result(
                project_id=project['id'],
                keyword_id=keyword_id,
                analysis_date=today,
                keyword=keyword,
                domain=project['domain'],
                ai_result=ai_result,
                serp_data=serp_data,
                country_code=project['country_code']
            )
            
            # Mostrar resultado
            has_ai = ai_result.get('has_ai_overview', False)
            is_mentioned = ai_result.get('domain_is_ai_source', False)
            position = ai_result.get('domain_ai_source_position', '-')
            detection_method = ai_result.get('debug_info', {}).get('detection_method', 'N/A')
            
            logger.info(f"   ✅ AI Overview: {'SÍ' if has_ai else 'NO'}")
            logger.info(f"   ✅ Marca mencionada: {'SÍ' if is_mentioned else 'NO'}")
            if is_mentioned:
                logger.info(f"   📍 Posición: #{position}")
                logger.info(f"   🔍 Método de detección: {detection_method}")
            
            success_count += 1
            
        except Exception as e:
            logger.error(f"   ❌ Error analizando '{keyword}': {e}")
            error_count += 1
            continue
    
    logger.info(f"\n{'='*80}")
    logger.info(f"📊 RESUMEN DEL RE-ANÁLISIS")
    logger.info(f"{'='*80}")
    logger.info(f"✅ Exitosos: {success_count}")
    logger.info(f"❌ Errores: {error_count}")
    logger.info(f"{'='*80}\n")

def main():
    """Función principal"""
    
    # Keywords específicas a re-analizar (las que reportaste)
    KEYWORDS_TO_REANALYZE = [
        "clínica láser",
        "depilacion ingles brasileñas"
    ]
    
    logger.info("\n🚀 Iniciando re-análisis de keywords de laserum.com...")
    logger.info(f"   Keywords específicas: {KEYWORDS_TO_REANALYZE}\n")
    
    # 1. Encontrar proyecto
    project = find_laserum_project()
    if not project:
        logger.error("❌ No se encontró el proyecto de laserum.com")
        return 1
    
    # 2. Encontrar keywords
    keywords = find_keywords_to_reanalyze(project['id'], KEYWORDS_TO_REANALYZE)
    if not keywords:
        logger.error(f"❌ No se encontraron las keywords especificadas en el proyecto")
        logger.info(f"   Buscadas: {KEYWORDS_TO_REANALYZE}")
        return 1
    
    logger.info(f"✅ Encontradas {len(keywords)} keyword(s) para re-analizar")
    
    # 3. Re-analizar
    reanalyze_keywords(project, keywords)
    
    logger.info("\n✅ Re-análisis completado!")
    logger.info("   Recarga tu app para ver los cambios actualizados.\n")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

