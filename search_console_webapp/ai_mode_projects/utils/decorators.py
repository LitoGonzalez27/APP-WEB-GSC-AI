"""
Decoradores y utilidades para reintentos y manejo de errores
"""

import time
import logging

logger = logging.getLogger(__name__)


def with_backoff(max_attempts: int = 3, base_delay_sec: float = 1.0):
    """
    Decorador sencillo de reintentos con backoff exponencial y jitter pequeño.
    Reintenta solo para errores transitorios; el callable debe lanzar Exception para reintentar.
    
    Args:
        max_attempts: Número máximo de intentos
        base_delay_sec: Delay base en segundos (se multiplica exponencialmente)
    
    Returns:
        Decorador que envuelve la función con lógica de reintento
    """
    def _decorator(func):
        def _wrapper(*args, **kwargs):
            attempt = 0
            last_err = None
            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as err:  # noqa: BLE001
                    last_err = err
                    attempt += 1
                    if attempt >= max_attempts:
                        break
                    delay = base_delay_sec * (2 ** (attempt - 1))
                    # Pequeño jitter para evitar thundering herd
                    time.sleep(delay + 0.05 * attempt)
            raise last_err
        return _wrapper
    return _decorator

