"""
Validadores de acceso y permisos para AI Mode Monitoring
"""

import logging
from services.project_access_service import user_has_any_module_access

logger = logging.getLogger(__name__)


def check_ai_mode_access(user):
    """
    Verifica si el usuario tiene acceso a AI Mode Monitoring
    
    Args:
        user: Dict con información del usuario
        
    Returns:
        Tuple (has_access: bool, error_response: dict or None)
    """
    # AI Mode disponible para todos los planes excepto free
    if user.get('plan') == 'free':
        user_id = user.get('id')
        if user_id and user_has_any_module_access(user_id, 'ai_mode'):
            return True, None
        return False, {
            'error': 'AI Mode Monitoring requires a paid plan',
            'upgrade_required': True,
            'required_plan': 'basic',
            'current_plan': user.get('plan', 'unknown')
        }
    
    return True, None
