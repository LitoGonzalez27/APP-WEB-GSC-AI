#!/usr/bin/env python3
"""
Script para verificar configuración de proyecto y cómo se generan brand_variations
"""
import logging
from database import get_db_connection
from services.ai_analysis import extract_brand_variations

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)

def check_project_config():
    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la BD")
        return
    
    try:
        cur = conn.cursor()
        
        # Buscar el proyecto "HM Fertility"
        cur.execute("""
            SELECT 
                id,
                name,
                brand_domain,
                brand_keywords,
                competitor_domains,
                competitor_keywords
            FROM llm_monitoring_projects
            WHERE name ILIKE '%fertility%'
            ORDER BY id
            LIMIT 1
        """)
        
        project = cur.fetchone()
        
        if not project:
            logger.warning("⚠️  No se encontró un proyecto con 'Fertility' en el nombre")
            return
        
        logger.info("=" * 70)
        logger.info(f"📋 PROYECTO: {project['name']} (ID: {project['id']})")
        logger.info("=" * 70)
        logger.info("")
        
        # Mostrar configuración
        logger.info("🎯 CONFIGURACIÓN DE MARCA:")
        logger.info(f"   Brand Domain: {project['brand_domain']}")
        logger.info(f"   Brand Keywords: {project['brand_keywords']}")
        logger.info("")
        
        # Generar brand_variations como lo hace el servicio
        brand_variations = []
        
        if project['brand_domain']:
            domain_vars = extract_brand_variations(project['brand_domain'].lower())
            brand_variations.extend(domain_vars)
            logger.info("🔍 VARIACIONES DESDE DOMINIO:")
            for idx, var in enumerate(domain_vars, 1):
                logger.info(f"   {idx:2d}. '{var}'")
            logger.info("")
        
        if project['brand_keywords']:
            keywords = project['brand_keywords']
            if isinstance(keywords, list):
                for kw in keywords:
                    brand_variations.append(kw.lower())
                logger.info("🔍 VARIACIONES DESDE KEYWORDS:")
                for idx, kw in enumerate(keywords, 1):
                    logger.info(f"   {idx:2d}. '{kw.lower()}'")
                logger.info("")
        
        # Eliminar duplicados
        seen = set()
        unique_variations = [x for x in brand_variations if not (x in seen or seen.add(x))]
        
        logger.info("📊 RESUMEN DE VARIACIONES (total: {})".format(len(unique_variations)))
        for idx, var in enumerate(unique_variations, 1):
            logger.info(f"   {idx:2d}. '{var}'")
        logger.info("")
        
        # Probar con un texto de ejemplo
        logger.info("=" * 70)
        logger.info("🧪 PRUEBA DE DETECCIÓN")
        logger.info("=" * 70)
        logger.info("")
        
        test_texts = [
            "Para obtener información precisa sobre los programas de preservación de la fertilidad que ofrece HM Fertility, te recomiendo visitar su sitio web oficial...",
            "Sí. HM Fertility (HM Hospitales) ofrece programas de preservación de la fertilidad, que suelen incluir: Vitrificación de ovocitos...",
            "La diferencia principal entre la inseminación artificial y la fecundación in vitro (FIV) radica en dónde ocurre la fecundación...",
        ]
        
        import re
        
        for test_idx, test_text in enumerate(test_texts, 1):
            logger.info(f"📝 TEXTO {test_idx}:")
            logger.info(f"   {test_text[:100]}...")
            logger.info("")
            
            found_variations = []
            for var in unique_variations:
                pattern = r'\b' + re.escape(var.lower()) + r'\b'
                if re.search(pattern, test_text.lower()):
                    found_variations.append(var)
            
            if found_variations:
                logger.info(f"   ✅ Encontrado: {', '.join(found_variations)}")
            else:
                logger.info(f"   ❌ No se encontró ninguna variación")
            
            # Calcular posición relativa si se encontró
            if found_variations:
                first_match = None
                for var in found_variations:
                    pattern = r'\b' + re.escape(var.lower()) + r'\b'
                    match = re.search(pattern, test_text.lower())
                    if match:
                        first_match = match
                        break
                
                if first_match:
                    mention_position = first_match.start()
                    text_length = len(test_text)
                    relative_position = mention_position / text_length if text_length > 0 else 0.5
                    
                    if relative_position < 0.15:
                        inferred_position = 1
                    elif relative_position < 0.30:
                        inferred_position = 3
                    elif relative_position < 0.50:
                        inferred_position = 5
                    elif relative_position < 0.70:
                        inferred_position = 8
                    else:
                        inferred_position = 12
                    
                    logger.info(f"   📍 Posición en texto: char {mention_position} ({relative_position*100:.1f}%)")
                    logger.info(f"   🎯 Posición inferida: {inferred_position}")
            
            logger.info("")
        
        logger.info("=" * 70)
        logger.info("✅ VERIFICACIÓN COMPLETADA")
        logger.info("=" * 70)
    
    except Exception as e:
        logger.error(f"\n❌ Error: {e}", exc_info=True)
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    check_project_config()

