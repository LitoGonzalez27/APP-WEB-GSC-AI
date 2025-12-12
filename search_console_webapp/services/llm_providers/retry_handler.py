"""
Sistema de Retry Inteligente para LLM Providers

Características:
- Exponential backoff para rate limits
- Reintentos selectivos según tipo de error
- Máximo de reintentos configurable
- Timeout configurable
- Logging detallado
- Optimizado para costos
"""

import logging
import time
from typing import Dict, Callable, Optional
from functools import wraps

logger = logging.getLogger(__name__)


class RetryConfig:
    """
    Configuración de reintentos por tipo de error
    """
    # Errores que vale la pena reintentar
    RETRYABLE_ERRORS = {
        'rate_limit': {
            'max_retries': 3,
            'initial_delay': 2,  # segundos
            'backoff_multiplier': 2,
            'max_delay': 30
        },
        'timeout': {
            'max_retries': 2,
            'initial_delay': 1,
            'backoff_multiplier': 1.5,
            'max_delay': 10
        },
        'server_error': {  # 500, 502, 503
            'max_retries': 2,
            'initial_delay': 3,
            'backoff_multiplier': 2,
            'max_delay': 20
        },
        'network': {
            'max_retries': 2,
            'initial_delay': 1,
            'backoff_multiplier': 2,
            'max_delay': 10
        }
    }
    
    # Errores que NO vale la pena reintentar (fallan inmediatamente)
    NON_RETRYABLE_ERRORS = [
        'invalid_api_key',
        'authentication_error',
        'invalid_request',
        'content_blocked',  # Safety filters
        'model_not_found'
    ]
    
    # Timeout por defecto para todas las requests
    DEFAULT_TIMEOUT = 60  # segundos
    
    # Timeouts específicos por provider (pueden ajustarse)
    PROVIDER_TIMEOUTS = {
        'openai': 60,      # GPT-5.2 puede tardar en respuestas largas
        'google': 30,      # Gemini es muy rápido
        'anthropic': 90,   # Claude puede hacer reasoning extenso
        'perplexity': 45   # Búsqueda en tiempo real
    }


def classify_error(error: Exception) -> str:
    """
    Clasifica un error para saber si es retriable
    
    Returns:
        Tipo de error: 'rate_limit', 'timeout', 'server_error', 'network', 'non_retryable'
    """
    error_str = str(error).lower()
    
    # Rate limit
    if 'rate' in error_str and 'limit' in error_str:
        return 'rate_limit'
    if '429' in error_str:
        return 'rate_limit'
    if 'quota' in error_str and 'exceeded' in error_str:
        return 'rate_limit'
    
    # Timeout
    if 'timeout' in error_str:
        return 'timeout'
    if 'timed out' in error_str:
        return 'timeout'
    
    # Server errors (retriables)
    if '500' in error_str or '502' in error_str or '503' in error_str:
        return 'server_error'
    if 'internal server error' in error_str:
        return 'server_error'
    if 'bad gateway' in error_str:
        return 'server_error'
    if 'service unavailable' in error_str:
        return 'server_error'
    
    # Network errors
    if 'connection' in error_str:
        return 'network'
    if 'network' in error_str:
        return 'network'
    
    # Errores no retriables
    if 'api key' in error_str or 'api_key' in error_str:
        return 'non_retryable'
    if 'authentication' in error_str or 'unauthorized' in error_str:
        return 'non_retryable'
    if 'invalid' in error_str and 'request' in error_str:
        return 'non_retryable'
    if 'safety' in error_str or 'blocked' in error_str:
        return 'non_retryable'
    if 'not found' in error_str and 'model' in error_str:
        return 'non_retryable'
    
    # Por defecto, no retriable (para evitar loops infinitos)
    return 'non_retryable'


def with_retry(func: Callable) -> Callable:
    """
    Decorator que agrega retry inteligente a execute_query
    
    Uso:
        @with_retry
        def execute_query(self, query: str) -> Dict:
            # ... código original ...
    """
    @wraps(func)
    def wrapper(self, query: str, *args, **kwargs) -> Dict:
        last_error = None
        total_attempts = 0
        
        # Primer intento sin delay
        try:
            result = func(self, query, *args, **kwargs)
            
            # Si tiene éxito, retornar
            if result.get('success'):
                return result
            
            # Si falla, clasificar el error
            last_error = result.get('error', 'Unknown error')
            error_type = classify_error(Exception(last_error))
            
            # Si no es retriable, retornar inmediatamente
            if error_type == 'non_retryable':
                logger.warning(f"⚠️ {self.get_provider_name()}: Error no retriable, abortando")
                return result
            
            # Obtener configuración de retry
            config = RetryConfig.RETRYABLE_ERRORS.get(error_type)
            if not config:
                logger.warning(f"⚠️ {self.get_provider_name()}: Sin configuración de retry para {error_type}")
                return result
            
            # Reintentos con backoff
            delay = config['initial_delay']
            max_retries = config['max_retries']
            
            for attempt in range(1, max_retries + 1):
                total_attempts = attempt + 1
                
                logger.warning(f"🔄 {self.get_provider_name()}: Reintento {attempt}/{max_retries} ({error_type})")
                logger.warning(f"   Esperando {delay}s antes de reintentar...")
                
                time.sleep(delay)
                
                try:
                    result = func(self, query, *args, **kwargs)
                    
                    if result.get('success'):
                        logger.info(f"✅ {self.get_provider_name()}: Éxito en intento {total_attempts}")
                        return result
                    
                    last_error = result.get('error', 'Unknown error')
                    
                    # Si ahora es un error diferente (no retriable), abortar
                    new_error_type = classify_error(Exception(last_error))
                    if new_error_type == 'non_retryable':
                        logger.warning(f"⚠️ {self.get_provider_name()}: Cambió a error no retriable, abortando")
                        return result
                    
                except Exception as e:
                    last_error = str(e)
                    logger.error(f"❌ {self.get_provider_name()}: Excepción en reintento: {e}")
                
                # Aumentar delay con backoff exponencial
                delay = min(delay * config['backoff_multiplier'], config['max_delay'])
            
            # Se acabaron los reintentos
            logger.error(f"❌ {self.get_provider_name()}: Falló después de {total_attempts} intentos")
            logger.error(f"   Último error: {last_error}")
            
            return {
                'success': False,
                'error': f"Failed after {total_attempts} attempts: {last_error}",
                'retry_info': {
                    'total_attempts': total_attempts,
                    'error_type': error_type,
                    'last_error': last_error
                }
            }
            
        except Exception as e:
            logger.error(f"❌ {self.get_provider_name()}: Error en decorator de retry: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    return wrapper


def with_timeout(timeout_seconds: int = RetryConfig.DEFAULT_TIMEOUT):
    """
    Decorator que agrega timeout a execute_query
    
    Uso:
        @with_timeout(60)
        def execute_query(self, query: str) -> Dict:
            # ... código original ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Dict:
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError(f"Query execution exceeded {timeout_seconds}s")
            
            # Solo funciona en Unix/Linux/Mac
            try:
                old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(timeout_seconds)
                
                try:
                    result = func(*args, **kwargs)
                    signal.alarm(0)  # Cancelar alarma
                    return result
                finally:
                    signal.signal(signal.SIGALRM, old_handler)
                    
            except AttributeError:
                # Windows no soporta signal.SIGALRM, usar sin timeout
                logger.warning("⚠️ Timeout no soportado en este sistema operativo")
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


# ============================================
# UTILIDADES PARA ANÁLISIS DE COSTOS
# ============================================

class RetryMetrics:
    """
    Clase para trackear métricas de retry y analizar costos
    """
    def __init__(self):
        self.total_requests = 0
        self.successful_first_try = 0
        self.successful_after_retry = 0
        self.failed_after_retry = 0
        self.total_retries = 0
        self.retry_by_error_type = {}
    
    def record_request(self, success_first_try: bool, retries: int = 0, error_type: str = None):
        """Registra una request para análisis"""
        self.total_requests += 1
        
        if success_first_try:
            self.successful_first_try += 1
        elif retries > 0:
            if error_type:
                self.retry_by_error_type[error_type] = self.retry_by_error_type.get(error_type, 0) + 1
            self.total_retries += retries
            self.successful_after_retry += 1
        else:
            self.failed_after_retry += 1
    
    def get_summary(self) -> Dict:
        """Retorna resumen de métricas"""
        total = self.total_requests
        if total == 0:
            return {}
        
        return {
            'total_requests': total,
            'success_rate': (self.successful_first_try + self.successful_after_retry) / total * 100,
            'first_try_success_rate': self.successful_first_try / total * 100,
            'retry_recovery_rate': self.successful_after_retry / max(1, self.failed_after_retry + self.successful_after_retry) * 100,
            'avg_retries_per_request': self.total_retries / total,
            'retry_by_error_type': self.retry_by_error_type
        }


# Instancia global para trackear métricas
retry_metrics = RetryMetrics()

