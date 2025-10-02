"""
Servicio para gestión de dominios globales detectados en AI Overview
"""

import logging
from datetime import date
from typing import Dict, List
from database import get_db_connection
from services.utils import normalize_search_console_url
from manual_ai.utils.helpers import extract_domain_from_url

logger = logging.getLogger(__name__)


class DomainsService:
    """Servicio para almacenar y gestionar dominios detectados"""
    
    @staticmethod
    def store_global_domains_detected(project_id: int, keyword_id: int, keyword: str, 
                                     project_domain: str, ai_analysis_data: Dict, 
                                     analysis_date: date, country_code: str, 
                                     selected_competitors: List[str]) -> None:
        """
        Almacenar TODOS los dominios detectados en AI Overview para detección global
        
        Esta función implementa el nuevo flujo solicitado:
        1. Detección global automática: guarda todos los dominios encontrados en AI Overview
        2. Marcado especial: identifica qué dominios son el del proyecto y cuáles son competidores seleccionados
        
        Args:
            project_id: ID del proyecto
            keyword_id: ID de la keyword
            keyword: Texto de la keyword
            project_domain: Dominio del proyecto
            ai_analysis_data: Datos del análisis AI
            analysis_date: Fecha del análisis
            country_code: Código de país
            selected_competitors: Lista de competidores seleccionados
        """
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Limpiar datos existentes del día para evitar duplicados
            cur.execute("""
                DELETE FROM manual_ai_global_domains 
                WHERE project_id = %s AND keyword_id = %s AND analysis_date = %s
            """, (project_id, keyword_id, analysis_date))
            
            # Extraer todos los dominios de debug_info.references_found
            debug_info = ai_analysis_data.get('debug_info', {})
            references_found = debug_info.get('references_found', [])
            
            if not references_found:
                logger.debug(f"No references found in AI Overview for keyword '{keyword}' in project {project_id}")
                return
            
            # Normalizar dominio del proyecto y competidores para comparación
            normalized_project_domain = normalize_search_console_url(project_domain) or project_domain.lower()
            normalized_competitors = [
                normalize_search_console_url(comp) or comp.lower() 
                for comp in (selected_competitors or [])
            ]
            
            domains_stored = 0
            
            for ref in references_found:
                ref_link = ref.get('link', '')
                ref_index = ref.get('index', 0)
                ref_title = ref.get('title', '')
                ref_source = ref.get('source', '')
                
                if not ref_link:
                    continue
                
                # Extraer dominio de la URL
                detected_domain = extract_domain_from_url(ref_link)
                if not detected_domain:
                    continue
                
                # Determinar flags
                is_project_domain = (detected_domain == normalized_project_domain)
                is_selected_competitor = (detected_domain in normalized_competitors)
                
                # Posición en AI Overview (index + 1 porque SERPAPI usa índice 0-based)
                domain_position = ref_index + 1 if ref_index is not None else 1
                
                try:
                    # Insertar dominio detectado
                    cur.execute("""
                        INSERT INTO manual_ai_global_domains (
                            project_id, keyword_id, analysis_date, keyword, project_domain,
                            detected_domain, domain_position, domain_title, domain_source_url,
                            country_code, is_project_domain, is_selected_competitor
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (project_id, keyword_id, analysis_date, detected_domain) 
                        DO UPDATE SET
                            domain_position = EXCLUDED.domain_position,
                            domain_title = EXCLUDED.domain_title,
                            domain_source_url = EXCLUDED.domain_source_url,
                            is_project_domain = EXCLUDED.is_project_domain,
                            is_selected_competitor = EXCLUDED.is_selected_competitor
                    """, (
                        project_id, keyword_id, analysis_date, keyword, project_domain,
                        detected_domain, domain_position, ref_title, ref_link,
                        country_code, is_project_domain, is_selected_competitor
                    ))
                    
                    domains_stored += 1
                    
                except Exception as insert_error:
                    logger.warning(f"Error storing domain '{detected_domain}' for keyword '{keyword}': {insert_error}")
                    continue
            
            conn.commit()
            cur.close()
            conn.close()
            
            logger.debug(f"✅ Stored {domains_stored} global domains for keyword '{keyword}' in project {project_id}")
            
        except Exception as e:
            logger.error(f"❌ Error storing global domains for keyword '{keyword}' in project {project_id}: {e}")
            # No re-raise para no afectar el análisis principal

