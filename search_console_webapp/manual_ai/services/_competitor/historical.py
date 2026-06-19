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


class _HistoricalMixin:

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
        # Refactor 2026-05-25: explicit try/finally to GUARANTEE conn release
        # even if the SQL or commit raises (previous outer try/except let conn
        # leak because close() was inside the try body).
        conn = None
        try:
            conn = get_db_connection()
            if not conn:
                logger.error(f"sync_historical_competitor_flags({project_id}): no DB connection")
                return
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

            logger.info(f"✅ Synced competitor flags for project {project_id}: "
                       f"{affected_unmarked} unmarked, {affected_marked} marked as competitors")

        except Exception as e:
            logger.error(f"❌ Error syncing competitor flags for project {project_id}: {e}")
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

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
        # Refactor 2026-05-25: nested try/finally to GUARANTEE conn release
        # even on early SQL failure (the outer try/except let conn leak).
        conn = None
        try:
            conn = get_db_connection()
            if not conn:
                logger.error(f"get_competitors_for_date_range({project_id}): no DB connection")
                return {}
            try:
                cur = conn.cursor()

                # Obtener todos los cambios de competidores ordenados cronológicamente
                cur.execute("""
                    SELECT event_date, event_type, event_description
                    FROM manual_ai_events
                    WHERE project_id = %s
                    AND event_type IN ('competitors_changed', 'competitors_updated', 'project_created')
                    AND event_date <= %s
                    ORDER BY event_date ASC, created_at ASC
                """, (project_id, end_date))

                competitor_changes = cur.fetchall()

                # Obtener competidores actuales como fallback
                cur.execute("SELECT selected_competitors FROM manual_ai_projects WHERE id = %s", (project_id,))
                current_result = cur.fetchone()
                current_competitors = current_result['selected_competitors'] if current_result else []
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
                conn = None  # mark as released so outer finally is a no-op
            
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
