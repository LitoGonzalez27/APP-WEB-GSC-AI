"""
Repositorio para operaciones de base de datos relacionadas con eventos y anotaciones (AI Mode)

Refactor 2026-05-25: null-check + try/finally so the pool slot is always
released, even when the connection is None or the SQL fails.
"""

import logging
from datetime import date, datetime
from typing import Optional
from database import get_db_connection

logger = logging.getLogger(__name__)


class EventRepository:
    """Repositorio para gestión de eventos del sistema AI Mode"""

    @staticmethod
    def create_event(project_id: int, event_type: str, event_title: str,
                    event_description: str = '', keywords_affected: int = 0,
                    user_id: Optional[int] = None):
        """
        Crear un evento en el sistema AI Mode
        """
        conn = get_db_connection()
        if not conn:
            logger.error(f"create_event[ai_mode]({project_id}, {event_type}): no DB connection")
            return
        try:
            cur = conn.cursor()
            try:
                cur.execute("""
                    INSERT INTO ai_mode_events
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
            try:
                conn.close()
            except Exception:
                pass
