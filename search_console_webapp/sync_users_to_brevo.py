import os
import logging
from typing import List, Dict, Any

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from database import get_all_users

try:
    from brevo_api_service import get_or_create_list_id, upsert_brevo_contact, bulk_upsert_contacts
    BREVO_API_AVAILABLE = True
except Exception as e:
    logger.error(f"Brevo API service no disponible: {e}")
    BREVO_API_AVAILABLE = False


def main() -> None:
    if not BREVO_API_AVAILABLE:
        logger.error("Brevo API no disponible. Aborta.")
        return

    target_list_name = os.getenv('BREVO_TARGET_LIST_NAME', 'Usuarios Registrados')
    list_id = get_or_create_list_id(target_list_name)
    if list_id is None:
        logger.error("No se pudo obtener o crear la lista de Brevo.")
        return

    users: List[Dict[str, Any]] = get_all_users() or []
    if not users:
        logger.info("No hay usuarios para sincronizar.")
        return

    contacts: List[Dict[str, Any]] = []
    for u in users:
        email = (u.get('email') or '').strip().lower()
        name = (u.get('name') or '').strip() or None
        if not email:
            continue
        # Preparar atributos adicionales
        current_plan = u.get('current_plan') or u.get('plan') or 'free'
        last_login_at = u.get('last_login_at')
        if hasattr(last_login_at, 'isoformat'):
            last_login_at_str = last_login_at.isoformat()
        else:
            last_login_at_str = str(last_login_at) if last_login_at else None
        contacts.append({
            'email': email,
            'name': name,
            'attributes': {
                'SOURCE': 'db_sync',
                'ROLE': u.get('role') or 'user',
                'PLAN': current_plan,
                'CURRENT_PLAN': current_plan,
                'LAST_LOGIN_AT': last_login_at_str,
                'ACTIVE': 'yes' if (u.get('is_active') is True) else 'no',
            }
        })

    result = bulk_upsert_contacts(contacts, list_id=list_id)
    logger.info(f"Sincronización completada. Éxito: {result['success']} | Fallos: {result['failed']}")


if __name__ == '__main__':
    main()


