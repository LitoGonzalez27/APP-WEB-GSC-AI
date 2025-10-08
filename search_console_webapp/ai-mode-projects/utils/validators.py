"""
Validadores de acceso y permisos para AI Mode Monitoring
"""

import logging

logger = logging.getLogger(__name__)


def check_ai_mode_access(user):
    """
    Verifica si el usuario tiene acceso a AI Mode Monitoring
    
    Args:
        user: Dict con información del usuario
        
    Returns:
        Tuple (has_access: bool, error_response: dict or None)
    """
    # AI Mode requiere plan Premium o superior
    allowed_plans = ['premium', 'business', 'enterprise']
    
    if user.get('plan') not in allowed_plans:
        return False, {
            'error': 'AI Mode Monitoring requires Premium plan or higher',
            'upgrade_required': True,
            'required_plan': 'premium',
            'current_plan': user.get('plan', 'unknown')
        }
    
    return True, None

