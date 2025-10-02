"""
Servicio para gestión de competidores en proyectos
"""

import logging
import json
from datetime import date, timedelta
from typing import List, Dict
from database import get_db_connection
from services.utils import normalize_search_console_url
from manual_ai.config import MAX_COMPETITORS_PER_PROJECT

logger = logging.getLogger(__name__)


class CompetitorService:
    """Servicio para gestión de competidores"""
    
    @staticmethod
    def validate_competitors(competitors: List[str], project_domain: str) -> Dict:
        """
        Validar y normalizar lista de competidores
        
        Args:
            competitors: Lista de dominios competidores
            project_domain: Dominio del proyecto (para excluir)
            
        Returns:
            Dict con competidores validados y errores
        """
        if not isinstance(competitors, list):
            return {
                'success': False,
                'error': 'Competitors must be a list',
                'validated': []
            }
        
        if len(competitors) > MAX_COMPETITORS_PER_PROJECT:
            return {
                'success': False,
                'error': f'Maximum {MAX_COMPETITORS_PER_PROJECT} competitors allowed',
                'validated': []
            }
        
        # Normalizar dominio del proyecto
        normalized_project_domain = normalize_search_console_url(project_domain) or project_domain.lower()
        
        # Validar y normalizar competidores
        validated_competitors = []
        errors = []
        
        for competitor in competitors:
            if not competitor or not isinstance(competitor, str):
                continue
            
            # Normalizar dominio
            normalized = normalize_search_console_url(competitor.strip())
            if not normalized:
                errors.append(f'Invalid domain: {competitor}')
                continue
            
            # No permitir el dominio del proyecto como competidor
            if normalized == normalized_project_domain:
                continue
            
            # Evitar duplicados
            if normalized not in validated_competitors:
                validated_competitors.append(normalized)
        
        return {
            'success': True,
            'validated': validated_competitors,
            'errors': errors if errors else None
        }
    
    @staticmethod
    def get_competitors_for_date_range(project_id: int, start_date: date, end_date: date) -> Dict[str, List[str]]:
        """
        Obtener competidores por fecha en un rango (para detectar cambios históricos)
        
        Args:
            project_id: ID del proyecto
            start_date: Fecha inicial
            end_date: Fecha final
            
        Returns:
            Dict con fecha como key y lista de competidores como value
        """
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # Obtener eventos de cambio de competidores
            cur.execute("""
                SELECT event_date, event_description
                FROM manual_ai_events
                WHERE project_id = %s 
                    AND event_type IN ('competitors_changed', 'competitors_updated')
                    AND event_date >= %s 
                    AND event_date <= %s
                ORDER BY event_date DESC
            """, (project_id, start_date, end_date))
            
            events = cur.fetchall()
            
            # Mapear fechas a listas de competidores
            competitors_by_date = {}
            
            for event in events:
                event_date = event['event_date']
                description = event['event_description']
                
                # Intentar parsear descripción JSON
                try:
                    if description:
                        desc_data = json.loads(description)
                        new_competitors = desc_data.get('new_competitors', [])
                        if new_competitors:
                            competitors_by_date[str(event_date)] = new_competitors
                except (json.JSONDecodeError, TypeError):
                    continue
            
            # Si no hay cambios históricos, usar configuración actual
            if not competitors_by_date:
                cur.execute("""
                    SELECT selected_competitors
                    FROM manual_ai_projects
                    WHERE id = %s
                """, (project_id,))
                
                result = cur.fetchone()
                if result and result['selected_competitors']:
                    competitors_by_date['current'] = result['selected_competitors']
            
            return competitors_by_date
            
        except Exception as e:
            logger.error(f"Error getting competitors for date range: {e}")
            return {}
        finally:
            cur.close()
            conn.close()
    
    @staticmethod
    def sync_historical_competitor_flags(project_id: int, current_competitors: List[str]) -> None:
        """
        Sincronizar flags de competidores en datos históricos
        
        Actualiza los flags is_selected_competitor en manual_ai_global_domains
        para reflejar la configuración actual de competidores
        
        Args:
            project_id: ID del proyecto
            current_competitors: Lista actual de competidores
        """
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Normalizar competidores actuales
            normalized_competitors = [
                normalize_search_console_url(comp) or comp.lower()
                for comp in current_competitors
            ]
            
            # 1. Desmarcar todos los dominios como competidores
            cur.execute("""
                UPDATE manual_ai_global_domains
                SET is_selected_competitor = false
                WHERE project_id = %s AND is_selected_competitor = true
            """, (project_id,))
            
            affected_unmarked = cur.rowcount
            
            # 2. Marcar dominios actuales como competidores
            if normalized_competitors:
                cur.execute("""
                    UPDATE manual_ai_global_domains
                    SET is_selected_competitor = true
                    WHERE project_id = %s 
                        AND detected_domain = ANY(%s)
                        AND is_selected_competitor = false
                """, (project_id, normalized_competitors))
                
                affected_marked = cur.rowcount
            else:
                affected_marked = 0
            
            conn.commit()
            cur.close()
            conn.close()
            
            logger.info(f"✅ Synced competitor flags for project {project_id}: "
                       f"{affected_unmarked} unmarked, {affected_marked} marked as competitors")
            
        except Exception as e:
            logger.error(f"❌ Error syncing competitor flags for project {project_id}: {e}")
    
    @staticmethod
    def get_competitors_charts_data(project_id: int, days: int = 30) -> Dict:
        """
        Obtener datos para gráficas de competidores
        
        Args:
            project_id: ID del proyecto
            days: Número de días hacia atrás
            
        Returns:
            Dict con datos para Brand Visibility Index y Brand Position Over Time
        """
        conn = get_db_connection()
        cur = conn.cursor()
        
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        try:
            # Obtener configuración de competidores del proyecto
            cur.execute("""
                SELECT selected_competitors, domain
                FROM manual_ai_projects
                WHERE id = %s
            """, (project_id,))
            
            project = cur.fetchone()
            if not project:
                return {'error': 'Project not found'}
            
            selected_competitors = project['selected_competitors'] or []
            project_domain = normalize_search_console_url(project['domain']) or project['domain'].lower()
            
            # Normalizar competidores
            normalized_competitors = [
                normalize_search_console_url(comp) or comp.lower()
                for comp in selected_competitors
            ]
            
            # Incluir el dominio del proyecto en el análisis
            all_domains = [project_domain] + normalized_competitors
            
            if not all_domains:
                return {
                    'brand_visibility_index': [],
                    'brand_position_over_time': {}
                }
            
            # 1. Brand Visibility Index (visibilidad por dominio)
            cur.execute("""
                SELECT 
                    detected_domain,
                    COUNT(DISTINCT keyword_id) as keywords_mentioned,
                    AVG(domain_position) as avg_position,
                    COUNT(*) as total_mentions
                FROM manual_ai_global_domains
                WHERE project_id = %s 
                    AND analysis_date >= %s 
                    AND analysis_date <= %s
                    AND detected_domain = ANY(%s)
                GROUP BY detected_domain
                ORDER BY keywords_mentioned DESC
            """, (project_id, start_date, end_date, all_domains))
            
            visibility_data = [dict(row) for row in cur.fetchall()]
            
            # 2. Brand Position Over Time (posición promedio por fecha)
            position_over_time = {}
            
            for domain in all_domains:
                cur.execute("""
                    SELECT 
                        analysis_date,
                        AVG(domain_position) as avg_position,
                        COUNT(DISTINCT keyword_id) as keyword_count
                    FROM manual_ai_global_domains
                    WHERE project_id = %s 
                        AND detected_domain = %s
                        AND analysis_date >= %s 
                        AND analysis_date <= %s
                    GROUP BY analysis_date
                    ORDER BY analysis_date
                """, (project_id, domain, start_date, end_date))
                
                position_over_time[domain] = [dict(row) for row in cur.fetchall()]
            
            return {
                'brand_visibility_index': visibility_data,
                'brand_position_over_time': position_over_time,
                'domains_analyzed': all_domains
            }
            
        except Exception as e:
            logger.error(f"Error getting competitors charts data: {e}")
            return {'error': str(e)}
        finally:
            cur.close()
            conn.close()

