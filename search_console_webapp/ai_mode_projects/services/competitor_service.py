"""
Servicio para gestión de competidores en proyectos
"""

import logging
import json
from datetime import date, timedelta
from typing import List, Dict
from database import get_db_connection
from services.utils import normalize_search_console_url
from ai_mode_projects.config import MAX_COMPETITORS_PER_PROJECT

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
                FROM ai_mode_events
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
                    FROM ai_mode_projects
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
        
        Actualiza los flags is_selected_competitor en ai_mode_global_domains
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
                UPDATE ai_mode_global_domains
                SET is_selected_competitor = false
                WHERE project_id = %s AND is_selected_competitor = true
            """, (project_id,))
            
            affected_unmarked = cur.rowcount
            
            # 2. Marcar dominios actuales como competidores
            if normalized_competitors:
                cur.execute("""
                    UPDATE ai_mode_global_domains
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
        ACTUALIZADO: Ahora lee del JSON raw_ai_mode_data (coherente con ranking de dominios)
        
        Args:
            project_id: ID del proyecto
            days: Número de días hacia atrás
            
        Returns:
            Dict con datos para Brand Visibility Index y Brand Position Over Time
        """
        from urllib.parse import urlparse
        from collections import defaultdict
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        try:
            # Obtener configuración de competidores del proyecto
            cur.execute("""
                SELECT selected_competitors, brand_name
                FROM ai_mode_projects
                WHERE id = %s
            """, (project_id,))
            
            project = cur.fetchone()
            if not project:
                return {'error': 'Project not found'}
            
            selected_competitors = project['selected_competitors'] or []
            brand_name = project['brand_name']
            
            # Normalizar dominios
            project_domain = brand_name.lower() if brand_name else ''
            normalized_competitors = [comp.lower() for comp in selected_competitors if comp]
            
            # Incluir el dominio del proyecto en el análisis
            all_domains = ([project_domain] if project_domain else []) + normalized_competitors
            
            if not all_domains:
                return {
                    'brand_visibility_index': [],
                    'brand_position_over_time': {}
                }
            
            # Obtener todos los resultados con AI Mode del periodo
            cur.execute("""
                SELECT 
                    r.raw_ai_mode_data,
                    r.analysis_date,
                    r.keyword_id
                FROM ai_mode_results r
                WHERE r.project_id = %s 
                    AND r.analysis_date >= %s 
                    AND r.analysis_date <= %s
                    AND r.raw_ai_mode_data IS NOT NULL
            """, (project_id, start_date, end_date))
            
            results = cur.fetchall()
            
            cur.close()
            conn.close()
            
            # Procesar datos por dominio
            domain_stats = defaultdict(lambda: {
                'keywords': set(),
                'positions': [],
                'total_mentions': 0
            })
            
            # Datos por fecha para evolution chart
            domain_by_date = defaultdict(lambda: defaultdict(lambda: {
                'positions': [],
                'keywords': set()
            }))
            
            # Procesar cada resultado
            for row in results:
                try:
                    serp_data = row['raw_ai_mode_data']
                    references = serp_data.get('references', [])
                    analysis_date = str(row['analysis_date'])
                    keyword_id = row['keyword_id']
                    
                    for ref in references:
                        link = ref.get('link', '')
                        position = ref.get('position', 0)
                        
                        if link:
                            try:
                                parsed = urlparse(link)
                                domain = parsed.netloc.lower()
                                if domain.startswith('www.'):
                                    domain = domain[4:]
                                
                                # Verificar si el dominio está en la lista de competidores
                                matched_domain = None
                                for target_domain in all_domains:
                                    if target_domain in domain or domain in target_domain:
                                        matched_domain = target_domain
                                        break
                                
                                if matched_domain:
                                    # Estadísticas globales
                                    domain_stats[matched_domain]['keywords'].add(keyword_id)
                                    domain_stats[matched_domain]['positions'].append(position if position else 1)
                                    domain_stats[matched_domain]['total_mentions'] += 1
                                    
                                    # Estadísticas por fecha
                                    domain_by_date[matched_domain][analysis_date]['positions'].append(position if position else 1)
                                    domain_by_date[matched_domain][analysis_date]['keywords'].add(keyword_id)
                            except:
                                continue
                except Exception as e:
                    logger.warning(f"Error processing result: {e}")
                    continue
            
            # 1. Brand Visibility Index
            visibility_data = []
            for domain in all_domains:
                if domain in domain_stats:
                    stats = domain_stats[domain]
                    avg_pos = sum(stats['positions']) / len(stats['positions']) if stats['positions'] else None
                    visibility_data.append({
                        'detected_domain': domain,
                        'keywords_mentioned': len(stats['keywords']),
                        'avg_position': float(avg_pos) if avg_pos else None,
                        'total_mentions': stats['total_mentions']
                    })
            
            # Ordenar por keywords mencionados
            visibility_data.sort(key=lambda x: x['keywords_mentioned'], reverse=True)
            
            # 2. Brand Position Over Time
            position_over_time = {}
            for domain in all_domains:
                if domain in domain_by_date:
                    date_data = []
                    for analysis_date in sorted(domain_by_date[domain].keys()):
                        day_stats = domain_by_date[domain][analysis_date]
                        avg_pos = sum(day_stats['positions']) / len(day_stats['positions']) if day_stats['positions'] else None
                        date_data.append({
                            'analysis_date': analysis_date,
                            'avg_position': float(avg_pos) if avg_pos else None,
                            'keyword_count': len(day_stats['keywords'])
                        })
                    position_over_time[domain] = date_data
                else:
                    position_over_time[domain] = []
            
            return {
                'brand_visibility_index': visibility_data,
                'brand_position_over_time': position_over_time,
                'domains_analyzed': all_domains
            }
            
        except Exception as e:
            logger.error(f"Error getting competitors charts data: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {'error': str(e)}
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    @staticmethod
    def get_competitors_for_date_range(project_id: int, start_date: date, end_date: date) -> Dict[str, List[str]]:
        """
        Obtiene qué competidores estaban activos en cada fecha del rango.
        
        Esta función reconstruye el estado temporal de los competidores basándose en:
        1. Eventos de cambios de competidores (competitors_changed)
        2. Evento de creación del proyecto (project_created)
        
        Args:
            project_id: ID del proyecto
            start_date: Fecha inicial del rango
            end_date: Fecha final del rango
            
        Returns:
            Dict con formato {fecha_iso: [lista_competidores]}
        """
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Obtener todos los cambios de competidores ordenados cronológicamente
            cur.execute("""
                SELECT event_date, event_type, event_description 
                FROM ai_mode_events 
                WHERE project_id = %s 
                AND event_type IN ('competitors_changed', 'competitors_updated', 'project_created')
                AND event_date <= %s
                ORDER BY event_date ASC, created_at ASC
            """, (project_id, end_date))
            
            competitor_changes = cur.fetchall()
            
            # Obtener competidores actuales como fallback
            cur.execute("SELECT selected_competitors FROM ai_mode_projects WHERE id = %s", (project_id,))
            current_result = cur.fetchone()
            current_competitors = current_result['selected_competitors'] if current_result else []
            
            cur.close()
            conn.close()
            
            # Reconstruir estado temporal correctamente
            date_range = {}
            active_competitors = []
            
            # Primer paso: determinar competidores iniciales
            if competitor_changes:
                # Buscar el evento más antiguo para competidores iniciales
                first_event = competitor_changes[0]
                if first_event['event_type'] == 'project_created':
                    try:
                        event_desc = first_event['event_description']
                        if event_desc:
                            change_data = json.loads(event_desc)
                            if 'competitors' in change_data:
                                active_competitors = change_data['competitors'].copy()
                        else:
                            active_competitors = current_competitors.copy()
                    except (json.JSONDecodeError, KeyError, TypeError):
                        active_competitors = current_competitors.copy()
                else:
                    # Si el primer evento no es de creación, usar competidores actuales como base
                    active_competitors = current_competitors.copy()
            else:
                # No hay eventos, usar competidores actuales
                active_competitors = current_competitors.copy()
            
            # Segundo paso: aplicar cambios cronológicamente
            changes_applied = set()  # Evitar aplicar el mismo cambio múltiples veces
            
            for n in range((end_date - start_date).days + 1):
                single_date = start_date + timedelta(n)
                
                # Aplicar SOLO los cambios que ocurren exactamente en esta fecha
                for i, change in enumerate(competitor_changes):
                    change_id = f"{change['event_date']}_{i}"  # ID único para cada cambio
                    
                    if (change['event_date'] == single_date and 
                        change_id not in changes_applied):
                        
                        changes_applied.add(change_id)
                        
                        try:
                            if change['event_type'] == 'competitors_changed':
                                # Cambio detallado con información temporal
                                event_desc = change['event_description']
                                if event_desc:
                                    change_data = json.loads(event_desc)
                                    if 'new_competitors' in change_data:
                                        active_competitors = change_data['new_competitors'].copy()
                                        logger.info(f"📅 Applied competitor change on {single_date}: {active_competitors}")
                            
                            elif change['event_type'] == 'competitors_updated':
                                # Actualización simple - extraer de descripción si es posible
                                description = change['event_description']
                                if description and 'competitors:' in description:
                                    try:
                                        competitors_part = description.split('competitors:')[1].strip()
                                        if competitors_part and competitors_part != 'None':
                                            active_competitors = [c.strip() for c in competitors_part.split(',')]
                                            logger.info(f"📅 Applied competitor update on {single_date}: {active_competitors}")
                                    except:
                                        pass
                        except (json.JSONDecodeError, KeyError, TypeError) as e:
                            logger.warning(f"Error parsing event description for date {single_date}: {e}")
                            continue
                
                # Asignar estado actual a esta fecha
                date_range[single_date.isoformat()] = active_competitors.copy()
            
            logger.info(f"🔄 Reconstructed temporal competitor state for project {project_id}: {len(date_range)} dates")
            return date_range
            
        except Exception as e:
            logger.error(f"💥 Error getting competitors for date range: {e}")
            logger.error(f"📋 Debug info - project_id: {project_id}, start_date: {start_date}, end_date: {end_date}")
            # Fallback: usar competidores actuales para todo el rango
            fallback_competitors = current_competitors if 'current_competitors' in locals() else []
            logger.info(f"🔄 Using fallback competitors: {fallback_competitors}")
            return {
                (start_date + timedelta(n)).isoformat(): fallback_competitors.copy()
                for n in range((end_date - start_date).days + 1)
            }
    
    @staticmethod
    def get_project_comparative_charts_data(project_id: int, days: int = 30) -> Dict:
        """
        Obtener datos para gráficas comparativas: dominio del proyecto vs competidores seleccionados.
        
        Retorna datos para:
        1. Gráfica de % visibilidad en AI Mode (líneas por dominio)
        2. Gráfica de posición media en AI Mode (líneas por dominio)
        """
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            
            # Obtener proyecto con competidores seleccionados
            cur.execute("""
                SELECT brand_name, selected_competitors 
                FROM ai_mode_projects 
                WHERE id = %s
            """, (project_id,))
            project_data = cur.fetchone()
            
            if not project_data:
                return {'visibility_chart': {}, 'position_chart': {}, 'domains': []}
            
            project_domain = project_data['brand_name']
            selected_competitors = project_data['selected_competitors'] or []
            
            # Lista de dominios a comparar: proyecto + competidores seleccionados
            domains_to_compare = [project_domain] + selected_competitors
            
            # Obtener datos de visibilidad y posición por fecha para cada dominio
            visibility_chart_data = {'dates': [], 'datasets': []}
            position_chart_data = {'dates': [], 'datasets': []}
            
            # Obtener fechas reales con datos
            cur.execute("""
                SELECT DISTINCT r.analysis_date
                FROM ai_mode_results r
                WHERE r.project_id = %s AND r.analysis_date >= %s AND r.analysis_date <= %s
                ORDER BY r.analysis_date
            """, (project_id, start_date, end_date))
            
            date_range = [str(row['analysis_date']) for row in cur.fetchall()]
            
            # Total de keywords analizadas por fecha (denominador SoV)
            cur.execute("""
                SELECT r.analysis_date, COUNT(DISTINCT r.keyword_id) AS total_keywords
                FROM ai_mode_results r
                WHERE r.project_id = %s AND r.analysis_date >= %s AND r.analysis_date <= %s
                GROUP BY r.analysis_date
            """, (project_id, start_date, end_date))
            totals_rows = cur.fetchall()
            total_keywords_by_date = {str(r['analysis_date']): r['total_keywords'] for r in totals_rows}

            visibility_chart_data['dates'] = date_range
            position_chart_data['dates'] = date_range
            
            # Paleta de colores
            domain_colors = {
                project_domain: '#5BF0AF',  # Verde para dominio del usuario
            }
            
            competitor_colors = ['#F0715B', '#1851F1', '#A1A9FF', '#8EAA96']
            for i, competitor in enumerate(selected_competitors):
                if i < len(competitor_colors):
                    domain_colors[competitor] = competitor_colors[i]
            
            # Obtener información temporal de competidores
            temporal_competitors = CompetitorService.get_competitors_for_date_range(project_id, start_date, end_date)
            logger.info(f"🕒 Temporal competitors data for comparative charts: {len(temporal_competitors)} dates")
            
            # Para cada dominio, obtener sus métricas por fecha
            for domain in domains_to_compare:
                # Datos de Share of Voice por fecha
                visibility_by_date = {}
                position_by_date = {}
                if domain == project_domain:
                    # Proyecto: directo desde ai_mode_results
                    cur.execute("""
                        SELECT r.analysis_date,
                               (COUNT(DISTINCT CASE WHEN r.brand_mentioned = true THEN r.keyword_id END)::float /
                               NULLIF(COUNT(DISTINCT r.keyword_id), 0)::float * 100) AS visibility_percentage
                        FROM ai_mode_results r
                        WHERE r.project_id = %s AND r.analysis_date >= %s AND r.analysis_date <= %s
                        GROUP BY r.analysis_date
                        ORDER BY r.analysis_date
                    """, (project_id, start_date, end_date))
                    for row in cur.fetchall():
                        visibility_by_date[str(row['analysis_date'])] = row['visibility_percentage']
                    cur.execute("""
                        SELECT r.analysis_date,
                               AVG(CASE WHEN r.mention_position IS NOT NULL THEN r.mention_position END) AS avg_position
                        FROM ai_mode_results r
                        WHERE r.project_id = %s AND r.analysis_date >= %s AND r.analysis_date <= %s
                          AND r.brand_mentioned = true
                        GROUP BY r.analysis_date
                        ORDER BY r.analysis_date
                    """, (project_id, start_date, end_date))
                    for row in cur.fetchall():
                        position_by_date[str(row['analysis_date'])] = row['avg_position']
                else:
                    # Competidor: leer del JSON raw_ai_mode_data
                    from urllib.parse import urlparse
                    from collections import defaultdict
                    
                    domain_lower = domain.lower()
                    
                    # Obtener todos los resultados para procesar
                    cur.execute("""
                        SELECT raw_ai_mode_data, analysis_date, keyword_id
                        FROM ai_mode_results
                        WHERE project_id = %s 
                          AND analysis_date >= %s 
                          AND analysis_date <= %s
                          AND raw_ai_mode_data IS NOT NULL
                    """, (project_id, start_date, end_date))
                    
                    comp_results = cur.fetchall()
                    
                    # Agrupar por fecha
                    mentions_by_date = defaultdict(lambda: {'keywords': set(), 'positions': []})
                    
                    for row in comp_results:
                        try:
                            serp_data = row['raw_ai_mode_data']
                            references = serp_data.get('references', [])
                            date_key = str(row['analysis_date'])
                            keyword_id = row['keyword_id']
                            
                            for ref in references:
                                link = ref.get('link', '')
                                position = ref.get('position', 0)
                                
                                if link:
                                    try:
                                        parsed = urlparse(link)
                                        link_domain = parsed.netloc.lower()
                                        if link_domain.startswith('www.'):
                                            link_domain = link_domain[4:]
                                        
                                        # Verificar si coincide con el competidor
                                        if domain_lower in link_domain or link_domain in domain_lower:
                                            mentions_by_date[date_key]['keywords'].add(keyword_id)
                                            mentions_by_date[date_key]['positions'].append(position if position else 1)
                                    except:
                                        continue
                        except Exception as e:
                            logger.warning(f"Error processing result for competitor {domain}: {e}")
                            continue
                    
                    # Calcular métricas por fecha
                    for date_key, stats in mentions_by_date.items():
                        keywords_count = len(stats['keywords'])
                        total_kw = total_keywords_by_date.get(date_key, 0) or 0
                        sov = (float(keywords_count) / float(total_kw) * 100.0) if total_kw > 0 else 0.0
                        visibility_by_date[date_key] = sov
                        
                        if stats['positions']:
                            avg_pos = sum(stats['positions']) / len(stats['positions'])
                            position_by_date[date_key] = avg_pos
                    
                    logger.info(f"🔎 Competitor '{domain}' -> {len(visibility_by_date)} dates with data from JSON")
                
                # Preparar datos con lógica temporal
                visibility_data = []
                position_data = []
                
                # Para competidores, encontrar primer y último día activo
                if domain != project_domain:
                    first_active_date = None
                    last_active_date = None
                    for date_str in date_range:
                        active_competitors = temporal_competitors.get(date_str, [])
                        if domain in active_competitors:
                            if first_active_date is None:
                                first_active_date = date_str
                            last_active_date = date_str
                    
                    logger.info(f"🏢 Competitor {domain}: active from {first_active_date} to {last_active_date}")
                
                for date_str in date_range:
                    if domain == project_domain:
                        # Dominio del proyecto: siempre valores reales
                        visibility_data.append(visibility_by_date.get(date_str, None))
                        position_data.append(position_by_date.get(date_str, None))
                    else:
                        # Competidores: Implementar lógica temporal
                        active_competitors = temporal_competitors.get(date_str, [])
                        
                        if domain in active_competitors:
                            # Competidor activo: usar datos reales
                            real_visibility = visibility_by_date.get(date_str)
                            if real_visibility is not None:
                                visibility_data.append(real_visibility)
                            else:
                                # Si está activo pero no hay datos de visibilidad, usar 0% como valor por defecto
                                visibility_data.append(0)
                            position_data.append(position_by_date.get(date_str, None))
                        else:
                            # Lógica temporal: Competidor no activo
                            if first_active_date and date_str < first_active_date:
                                # Antes de añadirse: None para que no aparezca línea
                                visibility_data.append(None) 
                                position_data.append(None)
                            elif last_active_date and date_str > last_active_date:
                                # Después de eliminarse: None para que no aparezca línea
                                visibility_data.append(None)
                                position_data.append(None)
                            else:
                                # No debería llegar aquí
                                visibility_data.append(None)
                                position_data.append(None)
                                logger.warning(f"⚠️ Unexpected temporal state for {domain} on {date_str}")
                
                # Determinar el label del dominio
                domain_label = domain
                
                logger.info(f"📈 Adding {domain} to visibility chart: {len([v for v in visibility_data if v is not None])} non-null points")
                
                # Dataset para gráfica de visibilidad
                visibility_chart_data['datasets'].append({
                    'label': domain_label,
                    'data': visibility_data,
                    'borderColor': domain_colors.get(domain, '#6B7280'),
                    'backgroundColor': domain_colors.get(domain, '#6B7280') + '20',
                    'tension': 0.4,
                    'pointRadius': 3,
                    'pointHoverRadius': 5,
                    'borderWidth': 3 if domain == project_domain else 2,
                    'spanGaps': False
                })
                
                # Dataset para gráfica de posición
                position_chart_data['datasets'].append({
                    'label': domain_label,
                    'data': position_data,
                    'borderColor': domain_colors.get(domain, '#6B7280'),
                    'backgroundColor': domain_colors.get(domain, '#6B7280') + '20',
                    'tension': 0.4,
                    'pointRadius': 3,
                    'pointHoverRadius': 5,
                    'borderWidth': 3 if domain == project_domain else 2
                })
            
            return {
                'visibility_chart': visibility_chart_data,
                'position_chart': position_chart_data,
                'domains': domains_to_compare,
                'date_range': {
                    'start': str(start_date),
                    'end': str(end_date)
                }
            }
            
        except Exception as e:
            logger.error(f"💥 Error getting comparative charts data for project {project_id}: {e}")
            import traceback
            logger.error(f"🔍 Full traceback: {traceback.format_exc()}")
            return {'visibility_chart': {}, 'position_chart': {}, 'domains': []}
        finally:
            cur.close()
            conn.close()

