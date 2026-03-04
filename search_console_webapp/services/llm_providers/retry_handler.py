"""
Sistema de Retry Inteligente para LLM Providers

Características:
- Exponential backoff para rate limits
- Reintentos selectivos según tipo de error
- Máximo de reintentos configurable
- Timeout configurable
- Circuit Breaker para providers inestables
- Logging detallado
- Optimizado para costos
"""

import logging
import time
import threading
from typing import Dict, Callable, Optional
from functools import wraps

logger = logging.getLogger(__name__)


# ============================================
# CIRCUIT BREAKER
# ============================================

class CircuitBreaker:
    """
    Circuit Breaker para proteger contra providers inestables.

    Estados:
    - CLOSED:    Todo normal, requests pasan.
    - OPEN:      Provider ha fallado N veces seguidas, requests rechazadas inmediatamente.
    - HALF_OPEN: Cooldown expirado, permite 1 request de prueba.

    Configuración via env vars:
    - CIRCUIT_BREAKER_THRESHOLD: Fallos consecutivos para abrir (default: 3)
    - CIRCUIT_BREAKER_COOLDOWN: Segundos de cooldown (default: 120)
    """

    STATE_CLOSED = 'closed'
    STATE_OPEN = 'open'
    STATE_HALF_OPEN = 'half_open'

    def __init__(self, failure_threshold: int = 3, cooldown_seconds: int = 120):
        import os
        self.failure_threshold = int(os.getenv('CIRCUIT_BREAKER_THRESHOLD', str(failure_threshold)))
        self.cooldown_seconds = int(os.getenv('CIRCUIT_BREAKER_COOLDOWN', str(cooldown_seconds)))
        self._lock = threading.Lock()
        # Per-provider state
        self._failures: Dict[str, int] = {}           # consecutive failures
        self._last_failure_time: Dict[str, float] = {} # timestamp of last failure
        self._state: Dict[str, str] = {}               # current state

    def _get_state(self, provider: str) -> str:
        """Get current state for a provider, checking cooldown expiry."""
        state = self._state.get(provider, self.STATE_CLOSED)

        if state == self.STATE_OPEN:
            last_fail = self._last_failure_time.get(provider, 0)
            if time.time() - last_fail >= self.cooldown_seconds:
                # Cooldown expired → allow one test request
                return self.STATE_HALF_OPEN

        return state

    def is_open(self, provider: str) -> bool:
        """Check if circuit is open (should skip this provider)."""
        with self._lock:
            state = self._get_state(provider)
            if state == self.STATE_OPEN:
                return True
            if state == self.STATE_HALF_OPEN:
                # Allow one request through (transition to half_open)
                self._state[provider] = self.STATE_HALF_OPEN
                return False
            return False

    def record_success(self, provider: str):
        """Record a successful request — reset failures."""
        with self._lock:
            self._failures[provider] = 0
            self._state[provider] = self.STATE_CLOSED

    def record_failure(self, provider: str):
        """Record a failed request — increment counter, possibly open circuit."""
        with self._lock:
            self._failures[provider] = self._failures.get(provider, 0) + 1
            self._last_failure_time[provider] = time.time()

            if self._failures[provider] >= self.failure_threshold:
                if self._state.get(provider) != self.STATE_OPEN:
                    logger.warning(
                        f"🔴 Circuit Breaker OPEN para '{provider}' — "
                        f"{self._failures[provider]} fallos consecutivos. "
                        f"Cooldown: {self.cooldown_seconds}s"
                    )
                self._state[provider] = self.STATE_OPEN

    def get_status(self, provider: str) -> Dict:
        """Get diagnostic info for a provider."""
        with self._lock:
            return {
                'provider': provider,
                'state': self._get_state(provider),
                'consecutive_failures': self._failures.get(provider, 0),
                'failure_threshold': self.failure_threshold,
                'cooldown_seconds': self.cooldown_seconds
            }


# Singleton global — compartido entre todos los providers y threads
circuit_breaker = CircuitBreaker()


class RetryConfig:
    """
    Configuración de reintentos por tipo de error
    """
    # Errores que vale la pena reintentar
    RETRYABLE_ERRORS = {
        'rate_limit': {
            # ✅ Rate limit temporal (RPM exceeded) — vale la pena esperar
            'max_retries': 2,       # Reducido de 4: no agravar el problema
            'initial_delay': 5,     # Esperar más para que pase el minuto
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
        'model_not_found',
        'quota_exhausted'   # ✅ NUEVO: cuota diaria agotada, NO reintentar
    ]
    
    # Timeout por defecto para todas las requests
    DEFAULT_TIMEOUT = 60  # segundos
    
    # Timeouts específicos por provider (pueden ajustarse)
    PROVIDER_TIMEOUTS = {
        'openai': 60,      # GPT-5.1 puede tardar en respuestas largas
        'google': 45,      # Gemini puede tener picos de latencia
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

    # ✅ QUOTA EXHAUSTED — cuota diaria agotada, NO reintentar
    # Estos errores dicen "retry in Xh" — reintentar es inútil y agrava el problema
    if 'quota' in error_str and ('exceeded' in error_str or 'exhausted' in error_str):
        return 'quota_exhausted'
    if 'per_day' in error_str or 'per day' in error_str:
        return 'quota_exhausted'
    if 'requests_per_model_per_day' in error_str:
        return 'quota_exhausted'
    if 'retry in' in error_str and ('h' in error_str or 'hour' in error_str):
        # "retry in 12h58m" → cuota diaria, no rate limit temporal
        return 'quota_exhausted'

    # Rate limit TEMPORAL (RPM exceeded) — vale la pena reintentar
    if 'rate' in error_str and 'limit' in error_str:
        return 'rate_limit'
    if '429' in error_str:
        return 'rate_limit'
    if 'resource_exhausted' in error_str:
        return 'rate_limit'
    if 'too many requests' in error_str:
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
        provider_name = self.get_provider_name()

        # ── Circuit Breaker check ──
        if circuit_breaker.is_open(provider_name):
            cb_status = circuit_breaker.get_status(provider_name)
            logger.warning(
                f"⚡ Circuit Breaker: '{provider_name}' bloqueado "
                f"({cb_status['consecutive_failures']} fallos). Skipping."
            )
            return {
                'success': False,
                'error': f"Circuit breaker open for {provider_name} "
                         f"(cooldown {cb_status['cooldown_seconds']}s)",
                'circuit_breaker': True
            }

        last_error = None
        total_attempts = 0

        # Primer intento sin delay
        try:
            result = func(self, query, *args, **kwargs)

            # Si tiene éxito, retornar
            if result.get('success'):
                circuit_breaker.record_success(provider_name)
                return result
            
            # Si falla, clasificar el error
            last_error = result.get('error', 'Unknown error')
            error_type = classify_error(Exception(last_error))
            
            # Si no es retriable, retornar inmediatamente
            if error_type == 'non_retryable':
                logger.warning(f"⚠️ {provider_name}: Error no retriable, abortando")
                return result

            # ✅ Quota exhausted: abrir circuit breaker con cooldown largo
            if error_type == 'quota_exhausted':
                logger.error(f"🚫 {provider_name}: Cuota diaria agotada — NO reintentar")
                logger.error(f"   El circuit breaker bloqueará este provider")
                # Forzar apertura inmediata del circuit breaker
                for _ in range(circuit_breaker.failure_threshold):
                    circuit_breaker.record_failure(provider_name)
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
                        logger.info(f"✅ {provider_name}: Éxito en intento {total_attempts}")
                        circuit_breaker.record_success(provider_name)
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
            circuit_breaker.record_failure(provider_name)
            logger.error(f"❌ {provider_name}: Falló después de {total_attempts} intentos")
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

