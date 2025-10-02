"""
Validadores de acceso y permisos
"""

import logging

logger = logging.getLogger(__name__)


def check_manual_ai_access(user):
    """
    Verifica si el usuario tiene acceso a Manual AI
    
    Args:
        user: Dict con información del usuario
        
    Returns:
        Tuple (has_access: bool, error_response: dict or None)
    """
    if user.get('plan') == 'free':
        return False, {'error': 'Manual AI requires a paid plan', 'upgrade_required': True}
    return True, None

