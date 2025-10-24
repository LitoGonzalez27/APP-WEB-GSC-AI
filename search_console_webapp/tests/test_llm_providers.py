"""
Tests Unitarios para LLM Providers

Tests para verificar que todos los proveedores funcionan correctamente:
- OpenAI, Anthropic, Google, Perplexity
- Factory Pattern
- Pricing desde BD
- Manejo de errores
"""

import pytest
import os
import sys
from unittest.mock import Mock, patch, MagicMock

# Añadir path del proyecto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.llm_providers import (
    BaseLLMProvider,
    OpenAIProvider,
    AnthropicProvider,
    GoogleProvider,
    PerplexityProvider,
    LLMProviderFactory
)
from services.llm_providers.base_provider import (
    get_model_pricing_from_db,
    get_current_model_for_provider
)


class TestBaseLLMProvider:
    """Tests para la interfaz base"""
    
    def test_base_provider_is_abstract(self):
        """Verificar que BaseLLMProvider es abstracta"""
        with pytest.raises(TypeError):
            BaseLLMProvider()
    
    def test_base_provider_has_required_methods(self):
        """Verificar que la interfaz define los métodos requeridos"""
        required_methods = [
            'execute_query',
            'get_provider_name',
            'get_model_display_name',
            'test_connection',
            'get_pricing_info'
        ]
        
        for method in required_methods:
            assert hasattr(BaseLLMProvider, method), f"Método {method} no encontrado"


class TestPricingFromDatabase:
    """Tests para helpers de BD"""
    
    @patch('database.get_db_connection')
    def test_get_model_pricing_from_db(self, mock_get_db):
        """Test de obtención de precios desde BD"""
        # Mock de la conexión
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        
        # Mock del resultado
        mock_cur.fetchone.return_value = {
            'cost_per_1m_input_tokens': 15.0,
            'cost_per_1m_output_tokens': 45.0
        }
        
        # Ejecutar
        result = get_model_pricing_from_db('openai', 'gpt-5')
        
        # Verificar
        assert result is not None
        assert 'input' in result
        assert 'output' in result
        assert result['input'] == 15.0 / 1_000_000
        assert result['output'] == 45.0 / 1_000_000
        
        # Verificar que se cerró la conexión
        mock_cur.close.assert_called_once()
        mock_conn.close.assert_called_once()
    
    @patch('database.get_db_connection')
    def test_get_current_model_for_provider(self, mock_get_db):
        """Test de obtención del modelo actual desde BD"""
        # Mock de la conexión
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        
        # Mock del resultado - simular acceso por índice y por clave
        mock_result = MagicMock()
        mock_result.__getitem__ = lambda self, key: 'gpt-5' if key == 'model_id' else 'GPT-5'
        mock_cur.fetchone.return_value = mock_result
        
        # Ejecutar
        result = get_current_model_for_provider('openai')
        
        # Verificar
        assert result == 'gpt-5'
        
        # Verificar que se cerró la conexión
        mock_cur.close.assert_called_once()
        mock_conn.close.assert_called_once()


class TestOpenAIProvider:
    """Tests para OpenAIProvider"""
    
    @patch('services.llm_providers.openai_provider.get_model_pricing_from_db')
    @patch('services.llm_providers.openai_provider.get_current_model_for_provider')
    def test_provider_initialization(self, mock_get_model, mock_get_pricing):
        """Test de inicialización del provider"""
        mock_get_model.return_value = 'gpt-5'
        mock_get_pricing.return_value = {'input': 0.000015, 'output': 0.000045}
        
        provider = OpenAIProvider(api_key='test-key')
        
        assert provider.model == 'gpt-5'
        assert provider.pricing is not None
        assert provider.get_provider_name() == 'openai'
    
    @patch('services.llm_providers.openai_provider.openai.OpenAI')
    @patch('services.llm_providers.openai_provider.get_model_pricing_from_db')
    @patch('services.llm_providers.openai_provider.get_current_model_for_provider')
    def test_execute_query_success(self, mock_get_model, mock_get_pricing, mock_openai_class):
        """Test de ejecución exitosa de query"""
        # Setup mocks
        mock_get_model.return_value = 'gpt-5'
        mock_get_pricing.return_value = {'input': 0.000015, 'output': 0.000045}
        
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        # Mock de la respuesta con valores reales
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        
        # Mock del usage con valores enteros reales
        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 100
        mock_usage.completion_tokens = 50
        mock_usage.total_tokens = 150
        mock_response.usage = mock_usage
        
        mock_client.chat.completions.create.return_value = mock_response
        
        # Ejecutar
        provider = OpenAIProvider(api_key='test-key')
        result = provider.execute_query("Test query")
        
        # Verificar
        assert result['success'] is True
        assert 'content' in result
        # Verificar que se usaron tokens - comprobar valores específicos
        assert result.get('input_tokens', 0) == 100
        assert result.get('output_tokens', 0) == 50
        assert 'cost_usd' in result
    
    @patch('services.llm_providers.openai_provider.openai.OpenAI')
    @patch('services.llm_providers.openai_provider.get_model_pricing_from_db')
    @patch('services.llm_providers.openai_provider.get_current_model_for_provider')
    def test_execute_query_error(self, mock_get_model, mock_get_pricing, mock_openai_class):
        """Test de manejo de errores en query"""
        mock_get_model.return_value = 'gpt-5'
        mock_get_pricing.return_value = {'input': 0.000015, 'output': 0.000045}
        
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        # Mock de error
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        
        # Ejecutar
        provider = OpenAIProvider(api_key='test-key')
        result = provider.execute_query("Test query")
        
        # Verificar
        assert result['success'] is False
        assert 'error' in result
        assert 'API Error' in result['error']


class TestAnthropicProvider:
    """Tests para AnthropicProvider"""
    
    @patch('services.llm_providers.anthropic_provider.get_model_pricing_from_db')
    @patch('services.llm_providers.anthropic_provider.get_current_model_for_provider')
    def test_provider_initialization(self, mock_get_model, mock_get_pricing):
        """Test de inicialización del provider"""
        mock_get_model.return_value = 'claude-sonnet-4-5-20250929'
        mock_get_pricing.return_value = {'input': 0.000003, 'output': 0.000015}
        
        provider = AnthropicProvider(api_key='test-key')
        
        assert provider.model == 'claude-sonnet-4-5-20250929'
        assert provider.pricing is not None
        assert provider.get_provider_name() == 'anthropic'


class TestGoogleProvider:
    """Tests para GoogleProvider"""
    
    @patch('services.llm_providers.google_provider.genai.configure')
    @patch('services.llm_providers.google_provider.genai.GenerativeModel')
    @patch('services.llm_providers.google_provider.get_model_pricing_from_db')
    @patch('services.llm_providers.google_provider.get_current_model_for_provider')
    def test_provider_initialization(self, mock_get_model, mock_get_pricing, mock_gen_model, mock_configure):
        """Test de inicialización del provider"""
        mock_get_model.return_value = 'gemini-2.0-flash'
        mock_get_pricing.return_value = {'input': 0.000000075, 'output': 0.0000003}
        
        provider = GoogleProvider(api_key='test-key')
        
        assert provider.model_name == 'gemini-2.0-flash'
        assert provider.pricing is not None
        assert provider.get_provider_name() == 'google'
        
        # Verificar que se configuró genai
        mock_configure.assert_called_once_with(api_key='test-key')


class TestPerplexityProvider:
    """Tests para PerplexityProvider"""
    
    @patch('services.llm_providers.perplexity_provider.get_model_pricing_from_db')
    @patch('services.llm_providers.perplexity_provider.get_current_model_for_provider')
    def test_provider_initialization(self, mock_get_model, mock_get_pricing):
        """Test de inicialización del provider"""
        mock_get_model.return_value = 'llama-3.1-sonar-large-128k-online'
        mock_get_pricing.return_value = {'input': 0.000001, 'output': 0.000001}
        
        provider = PerplexityProvider(api_key='test-key')
        
        assert provider.model == 'llama-3.1-sonar-large-128k-online'
        assert provider.pricing is not None
        assert provider.get_provider_name() == 'perplexity'
    
    @patch('services.llm_providers.perplexity_provider.openai.OpenAI')
    @patch('services.llm_providers.perplexity_provider.get_model_pricing_from_db')
    @patch('services.llm_providers.perplexity_provider.get_current_model_for_provider')
    def test_uses_correct_base_url(self, mock_get_model, mock_get_pricing, mock_openai_class):
        """Verificar que usa base_url de Perplexity"""
        mock_get_model.return_value = 'llama-3.1-sonar-large-128k-online'
        mock_get_pricing.return_value = {'input': 0.000001, 'output': 0.000001}
        
        provider = PerplexityProvider(api_key='test-key')
        
        # Verificar que OpenAI se llamó con base_url correcto
        mock_openai_class.assert_called_once()
        call_kwargs = mock_openai_class.call_args[1]
        assert call_kwargs['base_url'] == "https://api.perplexity.ai"


class TestLLMProviderFactory:
    """Tests para el Factory Pattern"""
    
    @patch('services.llm_providers.openai_provider.OpenAIProvider.test_connection')
    @patch('services.llm_providers.openai_provider.get_model_pricing_from_db')
    @patch('services.llm_providers.openai_provider.get_current_model_for_provider')
    def test_create_provider_openai(self, mock_get_model, mock_get_pricing, mock_test_connection):
        """Test de creación de OpenAI provider"""
        mock_get_model.return_value = 'gpt-5'
        mock_get_pricing.return_value = {'input': 0.000015, 'output': 0.000045}
        mock_test_connection.return_value = True  # Mock test_connection para que pase
        
        provider = LLMProviderFactory.create_provider('openai', 'test-key')
        
        assert provider is not None
        assert isinstance(provider, OpenAIProvider)
        assert provider.get_provider_name() == 'openai'
    
    @patch('services.llm_providers.anthropic_provider.AnthropicProvider.test_connection')
    @patch('services.llm_providers.anthropic_provider.get_model_pricing_from_db')
    @patch('services.llm_providers.anthropic_provider.get_current_model_for_provider')
    def test_create_provider_anthropic(self, mock_get_model, mock_get_pricing, mock_test_connection):
        """Test de creación de Anthropic provider"""
        mock_get_model.return_value = 'claude-sonnet-4-5-20250929'
        mock_get_pricing.return_value = {'input': 0.000003, 'output': 0.000015}
        mock_test_connection.return_value = True  # Mock test_connection para que pase
        
        provider = LLMProviderFactory.create_provider('anthropic', 'test-key')
        
        assert provider is not None
        assert isinstance(provider, AnthropicProvider)
        assert provider.get_provider_name() == 'anthropic'
    
    def test_create_provider_invalid(self):
        """Test de provider inválido"""
        provider = LLMProviderFactory.create_provider('invalid', 'test-key')
        
        assert provider is None
    
    def test_get_available_providers(self):
        """Test de obtención de providers disponibles"""
        providers = LLMProviderFactory.get_available_providers()
        
        assert isinstance(providers, list)
        assert 'openai' in providers
        assert 'anthropic' in providers
        assert 'google' in providers
        assert 'perplexity' in providers
        assert len(providers) == 4


class TestProviderPricing:
    """Tests para verificar cálculo de precios"""
    
    @patch('services.llm_providers.openai_provider.openai.OpenAI')
    @patch('services.llm_providers.openai_provider.get_model_pricing_from_db')
    @patch('services.llm_providers.openai_provider.get_current_model_for_provider')
    def test_cost_calculation(self, mock_get_model, mock_get_pricing, mock_openai_class):
        """Verificar que el coste se calcula correctamente"""
        mock_get_model.return_value = 'gpt-5'
        mock_get_pricing.return_value = {'input': 0.000015, 'output': 0.000045}
        
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        # Mock de la respuesta con tokens específicos
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test"
        mock_response.usage.prompt_tokens = 1000  # 1000 tokens input
        mock_response.usage.completion_tokens = 500  # 500 tokens output
        mock_client.chat.completions.create.return_value = mock_response
        
        provider = OpenAIProvider(api_key='test-key')
        result = provider.execute_query("Test")
        
        # Calcular coste esperado
        # Input: 1000 * 0.000015 = 0.015
        # Output: 500 * 0.000045 = 0.0225
        # Total: 0.0375
        expected_cost = (1000 * 0.000015) + (500 * 0.000045)
        
        assert result['success'] is True
        assert abs(result['cost_usd'] - expected_cost) < 0.0001  # Tolerancia de error


# Fixture para API keys de prueba
@pytest.fixture
def test_api_keys():
    """API keys de prueba"""
    return {
        'openai': os.getenv('OPENAI_API_KEY', 'test-openai-key'),
        'anthropic': os.getenv('ANTHROPIC_API_KEY', 'test-anthropic-key'),
        'google': os.getenv('GOOGLE_API_KEY', 'test-google-key'),
        'perplexity': os.getenv('PERPLEXITY_API_KEY', 'test-perplexity-key')
    }


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])

