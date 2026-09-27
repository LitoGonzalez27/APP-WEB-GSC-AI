"""
Migración: Mejorar estructura de competidores en LLM Monitoring
Cambiar de arrays separados (domains, keywords) a estructura unificada (selected_competitors)
"""

import logging
from database import get_db_connection

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def migrate():
    """
    Añade campo selected_competitors JSONB y migra datos existentes
    
    Estructura nueva:
    selected_competitors: [
        {
            "id": 1,
            "name": "Holded",
            "domain": "holded.com",
            "keywords": ["holded", "holded software"]
        },
        {
            "id": 2,
            "name": "Declarando",
            "domain": "declarando.es",
            "keywords": ["declarando"]
        }
    ]
    """
    
    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la base de datos")
        return False
    
    try:
        cur = conn.cursor()
        
        logger.info("=" * 70)
        logger.info("🔧 MIGRACIÓN: Mejorar estructura de competidores")
        logger.info("=" * 70)
        
        # 1. Verificar si el campo ya existe
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'llm_monitoring_projects' 
                AND column_name = 'selected_competitors'
        """)
        
        if cur.fetchone():
            logger.info("ℹ️  El campo 'selected_competitors' ya existe")
        else:
            # 2. Añadir campo selected_competitors
            logger.info("📝 Añadiendo campo 'selected_competitors'...")
            cur.execute("""
                ALTER TABLE llm_monitoring_projects 
                ADD COLUMN selected_competitors JSONB DEFAULT '[]'::jsonb
            """)
            conn.commit()
            logger.info("✅ Campo 'selected_competitors' añadido")
        
        # 3. Migrar datos existentes de competitor_domains/keywords a selected_competitors
        logger.info("\n📊 Migrando datos existentes...")
        cur.execute("""
            SELECT id, name, competitor_domains, competitor_keywords, selected_competitors
            FROM llm_monitoring_projects
            WHERE (competitor_domains IS NOT NULL AND jsonb_array_length(competitor_domains) > 0)
               OR (competitor_keywords IS NOT NULL AND jsonb_array_length(competitor_keywords) > 0)
        """)
        
        projects = cur.fetchall()
        logger.info(f"   Encontrados {len(projects)} proyectos con competidores")
        
        for project in projects:
            project_id = project['id']
            project_name = project['name']
            # JSONB viene como lista de Python directamente
            domains = project['competitor_domains'] if project['competitor_domains'] else []
            keywords = project['competitor_keywords'] if project['competitor_keywords'] else []
            current_selected = project['selected_competitors'] if project['selected_competitors'] else []
            
            # Si ya tiene selected_competitors poblado, skip
            if len(current_selected) > 0:
                logger.info(f"   ⏭️  Proyecto '{project_name}' ya tiene selected_competitors")
                continue
            
            logger.info(f"\n   🔄 Migrando proyecto '{project_name}'...")
            logger.info(f"      Domains: {domains}")
            logger.info(f"      Keywords: {keywords}")
            
            # Construir selected_competitors
            selected_competitors = []
            
            # Estrategia: intentar asociar keywords con domains por similitud
            for idx, domain in enumerate(domains, 1):
                # Extraer nombre base del dominio
                domain_base = domain.replace('.com', '').replace('.es', '').replace('.io', '').replace('www.', '')
                
                # Buscar keywords que contengan el domain_base
                matched_keywords = []
                remaining_keywords = []
                
                for kw in keywords:
                    if domain_base.lower() in kw.lower() or kw.lower() in domain_base.lower():
                        matched_keywords.append(kw)
                    else:
                        remaining_keywords.append(kw)
                
                competitor = {
                    "id": idx,
                    "name": domain_base.capitalize(),
                    "domain": domain,
                    "keywords": matched_keywords
                }
                selected_competitors.append(competitor)
                keywords = remaining_keywords  # Actualizar para próxima iteración
            
            # Si quedan keywords sin asociar, crear un competidor genérico
            if len(keywords) > 0:
                selected_competitors.append({
                    "id": len(selected_competitors) + 1,
                    "name": "Other",
                    "domain": "",
                    "keywords": keywords
                })
            
            # Actualizar en BD
            import json
            cur.execute("""
                UPDATE llm_monitoring_projects
                SET selected_competitors = %s
                WHERE id = %s
            """, (json.dumps(selected_competitors), project_id))
            
            logger.info(f"      ✅ Creados {len(selected_competitors)} competidores")
            for comp in selected_competitors:
                logger.info(f"         • {comp['name']}: {comp['domain']} → {comp['keywords']}")
        
        conn.commit()
        
        logger.info("\n" + "=" * 70)
        logger.info("✅ MIGRACIÓN COMPLETADA")
        logger.info("=" * 70)
        logger.info("\n⚠️  NOTA: Los campos legacy competitor_domains y competitor_keywords")
        logger.info("   se mantienen por compatibilidad pero NO se deben usar.")
        logger.info("   Usar solo 'selected_competitors' de ahora en adelante.")
        
        cur.close()
        conn.close()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error en migración: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return False


if __name__ == '__main__':
    success = migrate()
    exit(0 if success else 1)

