"""
Repositorio para operaciones de base de datos relacionadas con eventos y anotaciones
"""

import logging
from datetime import date, datetime
from typing import Optional
from database import get_db_connection

logger = logging.getLogger(__name__)


class EventRepository:
    """Repositorio para gestión de eventos del sistema"""
    
    @staticmethod
    def create_event(project_id: int, event_type: str, event_title: str,
                    event_description: str = '', keywords_affected: int = 0,
                    user_id: Optional[int] = None):
        """
        Crear un evento en el sistema
        
        Args:
            project_id: ID del proyecto
            event_type: Tipo de evento
            event_title: Título del evento
            event_description: Descripción del evento
            keywords_affected: Número de keywords afectadas
            user_id: ID del usuario que generó el evento
        """
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                INSERT INTO manual_ai_events 
                (project_id, event_type, event_title, event_description, 
                 event_date, keywords_affected, user_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                project_id, event_type, event_title, event_description,
                date.today(), keywords_affected, user_id, datetime.now()
            ))
            
            conn.commit()
            logger.debug(f"Event created: {event_type} for project {project_id}")
            
        except Exception as e:
            logger.error(f"Error creating event: {e}")
            # No lanzar excepción - los eventos son no críticos
        finally:
            cur.close()
            conn.close()

