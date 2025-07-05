"""
mobile_detector.py - Detector de dispositivos móviles
"""

import re
from flask import request


def is_mobile_device():
    """
    Detecta si el usuario está usando un dispositivo móvil basándose en el User-Agent.
    
    Returns:
        bool: True si es un dispositivo móvil, False si no
    """
    user_agent = request.headers.get('User-Agent', '').lower()
    
    # Patrones para detectar dispositivos móviles
    mobile_patterns = [
        r'mobile',
        r'android',
        r'iphone',
        r'ipod',
        r'blackberry',
        r'iemobile',
        r'opera mini',
        r'opera mobi',
        r'webos',
        r'palm',
        r'windows phone',
        r'symbian',
        r'series60',
        r'fennec',
        r'maemo',
        r'silk',
        r'kindle',
        r'mobile safari',
        r'phone'
    ]
    
    # Verificar si algún patrón coincide
    for pattern in mobile_patterns:
        if re.search(pattern, user_agent):
            return True
    
    return False


def is_tablet_device():
    """
    Detecta si el usuario está usando una tablet.
    
    Returns:
        bool: True si es una tablet, False si no
    """
    user_agent = request.headers.get('User-Agent', '').lower()
    
    # Patrones específicos para tablets (más específicos)
    tablet_patterns = [
        r'ipad',  # iPad específico
        r'tablet',  # Tablet genérico
        r'kindle',  # Kindle tablets
        r'playbook',  # BlackBerry PlayBook
        r'gt-p1000',  # Samsung Galaxy Tab
        r'sgh-t849',  # Samsung tablet
        r'shw-m180s',  # Samsung tablet
        r'android.*tablet',  # Android con "tablet" explícito
        r'sm-t\d+',  # Samsung Galaxy Tab (SM-T870, SM-T860, etc.)
        r'kfthwi',  # Kindle Fire HDX
        r'kftt',  # Kindle Fire HD
        r'kfjwi',  # Kindle Fire HDX
        r'kfapwi',  # Kindle Fire HDX
        r'kfarwi',  # Kindle Fire HDX
        r'kfaswi',  # Kindle Fire HDX
        r'kfsowi',  # Kindle Fire HDX
        r'kfgiwi',  # Kindle Fire HDX
        r'kfmewi',  # Kindle Fire HDX
        r'kffowi',  # Kindle Fire HDX
        r'kfmawi',  # Kindle Fire HDX
        r'kfauwi',  # Kindle Fire HDX
        r'kfkawi',  # Kindle Fire HDX
        r'kftrwi',  # Kindle Fire HDX
        r'kftetw',  # Kindle Fire HDX
        r'kfthw',  # Kindle Fire HDX
        r'kftt',  # Kindle Fire HD
        r'kfot',  # Kindle Fire HDX
        r'kfjw',  # Kindle Fire HDX
        r'kfap',  # Kindle Fire HDX
        r'kfar',  # Kindle Fire HDX
        r'kfas',  # Kindle Fire HDX
        r'kfso',  # Kindle Fire HDX
        r'kfgi',  # Kindle Fire HDX
        r'kfme',  # Kindle Fire HDX
        r'kffo',  # Kindle Fire HDX
        r'kfma',  # Kindle Fire HDX
        r'kfau',  # Kindle Fire HDX
        r'kfka',  # Kindle Fire HDX
        r'kftr',  # Kindle Fire HDX
        r'kfte',  # Kindle Fire HDX
        r'kfth',  # Kindle Fire HDX
        r'kf.*wi',  # Kindle Fire genérico
        r'silk',  # Amazon Silk browser (usado en tablets Kindle)
    ]
    
    # Verificar si algún patrón de tablet coincide
    for pattern in tablet_patterns:
        if re.search(pattern, user_agent):
            return True
    
    # Patrón especial: Android sin "mobile" pero con indicadores de tablet
    if re.search(r'android', user_agent):
        # Si es Android y NO contiene "mobile", podría ser tablet
        if not re.search(r'mobile', user_agent):
            # Verificar si tiene otros indicadores de tablet
            if any(indicator in user_agent for indicator in ['tablet', 'pad', 'book', 'tab']):
                return True
    
    return False


def is_small_screen():
    """
    Detecta si el usuario podría estar usando una pantalla pequeña.
    Esto es menos preciso pero sirve como respaldo.
    
    Returns:
        bool: True si probablemente es una pantalla pequeña
    """
    user_agent = request.headers.get('User-Agent', '').lower()
    
    # Patrones que sugieren pantallas pequeñas
    small_screen_patterns = [
        r'mobi',
        r'mini',
        r'240x320',
        r'320x480',
        r'480x800',
        r'small',
        r'compact'
    ]
    
    for pattern in small_screen_patterns:
        if re.search(pattern, user_agent):
            return True
    
    return False


def should_block_mobile_access():
    """
    Determina si se debe bloquear el acceso desde este dispositivo.
    
    Returns:
        bool: True si se debe bloquear, False si se permite
    """
    # PRIMERO: Verificar si es tablet - si es tablet, PERMITIR
    if is_tablet_device():
        return False  # Las tablets pueden funcionar, especialmente en orientación horizontal
    
    # SEGUNDO: Verificar si es móvil - si es móvil (y no tablet), BLOQUEAR
    if is_mobile_device():
        return True
    
    # TERCERO: Verificar pantalla pequeña como respaldo final
    if is_small_screen():
        return True
    
    # DEFAULT: Permitir todo lo demás (desktop)
    return False


def get_device_info():
    """
    Obtiene información detallada del dispositivo para debug.
    
    Returns:
        dict: Información del dispositivo
    """
    user_agent = request.headers.get('User-Agent', '')
    
    return {
        'user_agent': user_agent,
        'is_mobile': is_mobile_device(),
        'is_tablet': is_tablet_device(),
        'is_small_screen': is_small_screen(),
        'should_block': should_block_mobile_access(),
        'remote_addr': request.remote_addr,
        'headers': dict(request.headers)
    }


def is_desktop_device():
    """
    Detecta si el usuario está usando un dispositivo de escritorio.
    
    Returns:
        bool: True si es un dispositivo de escritorio, False si no
    """
    return not (is_mobile_device() or is_tablet_device())


def get_device_type():
    """
    Obtiene el tipo de dispositivo de forma más específica.
    
    Returns:
        str: 'mobile', 'tablet', 'desktop'
    """
    # PRIMERO verificar si es tablet - tiene prioridad sobre móvil
    if is_tablet_device():
        return 'tablet'
    elif is_mobile_device():
        return 'mobile'
    else:
        return 'desktop'


def log_device_access(logger):
    """
    Registra información del acceso del dispositivo en los logs.
    
    Args:
        logger: Logger instance para registrar la información
    """
    device_info = get_device_info()
    
    logger.info(f"Device Access - Type: {get_device_type()}, "
                f"Should Block: {device_info['should_block']}, "
                f"IP: {device_info['remote_addr']}, "
                f"User-Agent: {device_info['user_agent'][:100]}...")


# Funciones auxiliares para casos específicos
def is_ios_device():
    """Detecta dispositivos iOS específicamente"""
    user_agent = request.headers.get('User-Agent', '').lower()
    return 'iphone' in user_agent or 'ipad' in user_agent or 'ipod' in user_agent


def is_android_device():
    """Detecta dispositivos Android específicamente"""
    user_agent = request.headers.get('User-Agent', '').lower()
    return 'android' in user_agent


def is_windows_mobile():
    """Detecta dispositivos Windows Mobile específicamente"""
    user_agent = request.headers.get('User-Agent', '').lower()
    return 'windows phone' in user_agent or 'windows mobile' in user_agent 