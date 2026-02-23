"""
Validadores de acceso y permisos
"""

import logging
from services.project_access_service import user_has_any_module_access

logger = logging.getLogger(__name__)


def check_manual_ai_access(user, allow_shared=False):
    """
    Verifica si el usuario tiene acceso a Manual AI
    
    Args:
        user: Dict con información del usuario
        
    Returns:
        Tuple (has_access: bool, error_response: dict or None)
    """
    if user.get('plan') == 'free':
        user_id = user.get('id')
        if allow_shared and user_id and user_has_any_module_access(user_id, 'manual_ai'):
            return True, None
        return False, {'error': 'Manual AI requires a paid plan', 'upgrade_required': True}
    return True, None
