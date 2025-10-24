"""
Factory Pattern para Proveedores LLM

IMPORTANTE:
- Crea proveedores dinámicamente sin imports manuales
- Valida conexión antes de retornar
- Soporta creación individual o batch
"""

import logging
from typing import Dict, Optional, List
from .base_provider import BaseLLMProvider
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider
from .google_provider import GoogleProvider
from .perplexity_provider import PerplexityProvider

logger = logging.getLogger(__name__)


class LLMProviderFactory:
    """
    Factory para crear proveedores LLM dinámicamente
    
    Uso:
        # Crear un proveedor específico
        provider = LLMProviderFactory.create_provider('openai', 'sk-...')
        
        # Crear todos los proveedores disponibles
        api_keys = {'openai': 'sk-...', 'google': 'AIza...'}
        providers = LLMProviderFactory.create_all_providers(api_keys)
    """
    
    # Mapeo de nombres a clases
    PROVIDER_CLASSES = {
        'openai': OpenAIProvider,
        'anthropic': AnthropicProvider,
        'google': GoogleProvider,
        'perplexity': PerplexityProvider
    }
    
    @classmethod
    def create_provider(
        cls, 
        provider_name: str, 
        api_key: str, 
        model: str = None,
        validate_connection: bool = True
    ) -> Optional[BaseLLMProvider]:
        """
        Crea un proveedor específico
        
        Args:
            provider_name: Nombre del proveedor ('openai', 'anthropic', 'google', 'perplexity')
            api_key: API key del proveedor
            model: Modelo específico (opcional, usa el de BD si no se especifica)
            validate_connection: Si True, valida la conexión antes de retornar
            
        Returns:
            Instancia del proveedor o None si falla
            
        Example:
            >>> provider = LLMProviderFactory.create_provider('openai', 'sk-...')
            >>> if provider:
            ...     result = provider.execute_query("Hi")
        """
        provider_name = provider_name.lower()
        
        if provider_name not in cls.PROVIDER_CLASSES:
            logger.error(f"❌ Proveedor desconocido: {provider_name}")
            logger.error(f"   Proveedores disponibles: {list(cls.PROVIDER_CLASSES.keys())}")
            return None
        
        try:
            # Crear instancia del proveedor
            provider_class = cls.PROVIDER_CLASSES[provider_name]
            
            if model:
                provider = provider_class(api_key=api_key, model=model)
            else:
                provider = provider_class(api_key=api_key)
            
            # Validar conexión si se solicita
            if validate_connection:
                logger.info(f"🔍 Validando conexión para {provider_name}...")
                if not provider.test_connection():
                    logger.error(f"❌ Validación fallida para {provider_name}")
                    return None
                logger.info(f"✅ {provider_name} validado correctamente")
            
            return provider
            
        except Exception as e:
            logger.error(f"❌ Error creando proveedor {provider_name}: {e}", exc_info=True)
            return None
    
    @classmethod
    def create_all_providers(
        cls, 
        api_keys: Dict[str, str],
        validate_connections: bool = True
    ) -> Dict[str, BaseLLMProvider]:
        """
        Crea múltiples proveedores en batch
        
        IMPORTANTE: Solo retorna los proveedores que pasaron la validación.
        Esto permite que la app funcione aunque algunos LLMs fallen.
        
        Args:
            api_keys: Dict con API keys por proveedor
                     Ejemplo: {'openai': 'sk-...', 'google': 'AIza...'}
            validate_connections: Si True, solo retorna proveedores válidos
            
        Returns:
            Dict con proveedores creados exitosamente
            
        Example:
            >>> api_keys = {
            ...     'openai': 'sk-...',
            ...     'anthropic': 'sk-ant-...',
            ...     'google': 'AIza...',
            ...     'perplexity': 'pplx-...'
            ... }
            >>> providers = LLMProviderFactory.create_all_providers(api_keys)
            >>> print(f"Proveedores activos: {list(providers.keys())}")
            >>> # Proveedores activos: ['openai', 'google']
        """
        providers = {}
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("🚀 CREANDO PROVEEDORES LLM")
        logger.info("=" * 70)
        logger.info(f"API keys recibidas: {list(api_keys.keys())}")
        logger.info("")
        
        for provider_name, api_key in api_keys.items():
            if not api_key or api_key.strip() == '':
                logger.warning(f"⚠️ {provider_name}: API key vacía, saltando...")
                continue
            
            logger.info(f"🔧 Creando proveedor: {provider_name}...")
            
            provider = cls.create_provider(
                provider_name=provider_name,
                api_key=api_key,
                validate_connection=validate_connections
            )
            
            if provider:
                providers[provider_name] = provider
                logger.info(f"   ✅ {provider_name} listo")
                
                # Mostrar info de pricing
                pricing = provider.get_pricing_info()
                logger.info(f"   💰 Pricing: ${pricing['input_per_1m']:.2f}/${pricing['output_per_1m']:.2f} per 1M tokens")
            else:
                logger.warning(f"   ❌ {provider_name} falló (API key inválida o error de conexión)")
        
        logger.info("")
        logger.info("=" * 70)
        logger.info(f"✅ PROVEEDORES CREADOS: {len(providers)}/{len(api_keys)}")
        logger.info("=" * 70)
        
        if len(providers) == 0:
            logger.error("")
            logger.error("⚠️ ADVERTENCIA: No se pudo crear ningún proveedor")
            logger.error("   Verifica que las API keys sean válidas")
            logger.error("")
        else:
            logger.info(f"Proveedores activos: {', '.join(providers.keys())}")
            logger.info("")
        
        return providers
    
    @classmethod
    def get_available_providers(cls) -> List[str]:
        """
        Retorna lista de proveedores disponibles en el sistema
        
        Útil para:
        - Mostrar opciones en UI
        - Validar nombres de proveedores
        - Documentación
        
        Returns:
            Lista de nombres de proveedores disponibles
            
        Example:
            >>> providers = LLMProviderFactory.get_available_providers()
            >>> print(providers)
            ['openai', 'anthropic', 'google', 'perplexity']
        """
        return list(cls.PROVIDER_CLASSES.keys())
    
    @classmethod
    def get_provider_info(cls) -> Dict[str, Dict]:
        """
        Retorna información detallada de todos los proveedores disponibles
        
        Útil para:
        - Mostrar info en UI (qué proveedores hay)
        - Documentación automática
        - Ayuda para usuarios
        
        Returns:
            Dict con info de cada proveedor
            
        Example:
            >>> info = LLMProviderFactory.get_provider_info()
            >>> print(info['openai']['display_name'])
            'OpenAI (ChatGPT)'
        """
        return {
            'openai': {
                'display_name': 'OpenAI (ChatGPT)',
                'models': ['gpt-5', 'gpt-4o', 'gpt-4-turbo'],
                'description': 'Modelo más potente, razonamiento complejo',
                'website': 'https://platform.openai.com',
                'pricing_note': 'Alto coste pero máxima calidad'
            },
            'anthropic': {
                'display_name': 'Anthropic (Claude)',
                'models': ['claude-sonnet-4-5-20250929', 'claude-3-5-sonnet-20241022'],
                'description': 'Excelente análisis de texto, razonamiento largo',
                'website': 'https://console.anthropic.com',
                'pricing_note': 'Mejor balance precio/calidad'
            },
            'google': {
                'display_name': 'Google (Gemini)',
                'models': ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-pro'],
                'description': 'Muy rápido y económico, multimodal',
                'website': 'https://aistudio.google.com',
                'pricing_note': 'El más económico del mercado'
            },
            'perplexity': {
                'display_name': 'Perplexity (Sonar)',
                'models': ['llama-3.1-sonar-large-128k-online'],
                'description': 'Búsqueda en tiempo real, cita fuentes',
                'website': 'https://www.perplexity.ai',
                'pricing_note': 'Precio competitivo, info actualizada'
            }
        }

