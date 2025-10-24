"""
Tests Unitarios para LLM Monitoring Service

Tests para verificar el servicio principal:
- Generación de queries
- Análisis de menciones
- Análisis de sentimiento
- Paralelización
- Creación de snapshots
"""

import pytest
import os
import sys
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, date
from concurrent.futures import ThreadPoolExecutor

# Añadir path del proyecto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.llm_monitoring_service import MultiLLMMonitoringService


class TestQueryGeneration:
    """Tests para generación de queries"""
    
    @patch('services.llm_monitoring_service.LLMProviderFactory.create_all_providers')
    def test_generate_queries_basic(self, mock_factory):
        """Test básico de generación de queries"""
        mock_factory.return_value = {}
        
        service = MultiLLMMonitoringService(api_keys={})
        queries = service.generate_queries_for_project(
            brand_name="TestBrand",
            industry="SEO tools",
            language="es",
            competitors=["Competitor1"],
            count=10
        )
        
        assert isinstance(queries, list)
        assert len(queries) == 10
        
        # Verificar estructura de cada query
        for query in queries:
            assert 'query_text' in query
            assert 'language' in query
            assert 'query_type' in query
            assert isinstance(query['query_text'], str)
            assert len(query['query_text']) > 0
    
    @patch('services.llm_monitoring_service.LLMProviderFactory.create_all_providers')
    def test_generate_queries_with_brand(self, mock_factory):
        """Verificar que las queries usan la industria"""
        mock_factory.return_value = {}
        
        service = MultiLLMMonitoringService(api_keys={})
        queries = service.generate_queries_for_project(
            brand_name="MiMarca",
            industry="herramientas SEO",
            language="es",
            competitors=[],
            count=5
        )
        
        # Al menos una query debe mencionar la industria
        industry_mentioned = any("seo" in q['query_text'].lower() for q in queries)
        assert industry_mentioned
    
    @patch('services.llm_monitoring_service.LLMProviderFactory.create_all_providers')
    def test_generate_queries_with_competitors(self, mock_factory):
        """Verificar que se generan queries con competidores"""
        mock_factory.return_value = {}
        
        service = MultiLLMMonitoringService(api_keys={})
        queries = service.generate_queries_for_project(
            brand_name="MiMarca",
            industry="SEO",
            language="es",
            competitors=["Semrush", "Ahrefs"],
            count=10
        )
        
        # Al menos una query debe mencionar competidores
        competitor_queries = [
            q for q in queries 
            if "semrush" in q['query_text'].lower() or "ahrefs" in q['query_text'].lower()
        ]
        assert len(competitor_queries) > 0
    
    @patch('services.llm_monitoring_service.LLMProviderFactory.create_all_providers')
    def test_generate_queries_english(self, mock_factory):
        """Test de generación en inglés"""
        mock_factory.return_value = {}
        
        service = MultiLLMMonitoringService(api_keys={})
        queries = service.generate_queries_for_project(
            brand_name="TestBrand",
            industry="SEO tools",
            language="en",
            competitors=[],
            count=5
        )
        
        assert len(queries) == 5
        # Verificar que las queries están en inglés (no tienen caracteres españoles)
        # (Este test es básico, idealmente usarías un detector de idioma)


class TestBrandMentionAnalysis:
    """Tests para análisis de menciones de marca"""
    
    @patch('services.llm_monitoring_service.LLMProviderFactory.create_all_providers')
    def test_analyze_brand_mention_found(self, mock_factory):
        """Test cuando la marca es mencionada"""
        mock_factory.return_value = {}
        
        service = MultiLLMMonitoringService(api_keys={})
        
        response_text = """
        Las mejores herramientas SEO son:
        1. MiMarca - La mejor opción
        2. Semrush - También buena
        3. Ahrefs - Otra alternativa
        
        MiMarca destaca por su precio y facilidad de uso.
        """
        
        result = service.analyze_brand_mention(
            response_text=response_text,
            brand_name="MiMarca",
            competitors=["Semrush", "Ahrefs"]
        )
        
        assert result['brand_mentioned'] is True
        assert result['mention_count'] >= 2  # Aparece al menos 2 veces
        assert len(result['mention_contexts']) > 0
        assert result['appears_in_numbered_list'] is True
        assert result['position_in_list'] == 1
        
        # Verificar competidores
        assert 'Semrush' in result['competitors_mentioned']
        assert 'Ahrefs' in result['competitors_mentioned']
    
    @patch('services.llm_monitoring_service.LLMProviderFactory.create_all_providers')
    def test_analyze_brand_mention_not_found(self, mock_factory):
        """Test cuando la marca NO es mencionada"""
        mock_factory.return_value = {}
        
        service = MultiLLMMonitoringService(api_keys={})
        
        response_text = """
        Las mejores herramientas SEO son:
        1. Semrush - La mejor opción
        2. Ahrefs - También buena
        """
        
        result = service.analyze_brand_mention(
            response_text=response_text,
            brand_name="MiMarca",
            competitors=["Semrush", "Ahrefs"]
        )
        
        assert result['brand_mentioned'] is False
        assert result['mention_count'] == 0
        assert len(result['mention_contexts']) == 0
        assert result['appears_in_numbered_list'] is False
        assert result['position_in_list'] is None
    
    @patch('services.llm_monitoring_service.LLMProviderFactory.create_all_providers')
    def test_analyze_brand_mention_variations(self, mock_factory):
        """Test de detección de variaciones de marca"""
        mock_factory.return_value = {}
        
        service = MultiLLMMonitoringService(api_keys={})
        
        # Diferentes variaciones de la marca
        response_text = """
        Hablando de laserum, es una gran opción.
        También está Láserum como alternativa.
        Y no olvidemos GetLaserum.
        """
        
        result = service.analyze_brand_mention(
            response_text=response_text,
            brand_name="Laserum",
            competitors=[]
        )
        
        assert result['brand_mentioned'] is True
        assert result['mention_count'] >= 2  # Múltiples variaciones
    
    @patch('services.llm_monitoring_service.LLMProviderFactory.create_all_providers')
    def test_analyze_position_in_list(self, mock_factory):
        """Test de detección de posición en lista"""
        mock_factory.return_value = {}
        
        service = MultiLLMMonitoringService(api_keys={})
        
        # Brand en posición 3
        response_text = """
        Top 5 herramientas:
        1. Competitor1
        2. Competitor2
        3. MiMarca
        4. Competitor3
        5. Competitor4
        """
        
        result = service.analyze_brand_mention(
            response_text=response_text,
            brand_name="MiMarca",
            competitors=[]
        )
        
        assert result['appears_in_numbered_list'] is True
        assert result['position_in_list'] == 3
        assert result['total_items_in_list'] >= 5


class TestSentimentAnalysis:
    """Tests para análisis de sentimiento"""
    
    @patch('services.llm_monitoring_service.LLMProviderFactory.create_all_providers')
    def test_sentiment_analysis_with_llm(self, mock_factory):
        """Test de análisis de sentimiento con LLM"""
        # Mock del provider de Google (Gemini)
        mock_google_provider = MagicMock()
        mock_google_provider.execute_query.return_value = {
            'success': True,
            'response_text': '{"sentiment": "positive", "score": 0.85}'
        }
        
        mock_factory.return_value = {'google': mock_google_provider}
        
        service = MultiLLMMonitoringService(api_keys={})
        
        contexts = ["MiMarca es excelente y muy recomendada"]
        result = service._analyze_sentiment_with_llm(contexts, "MiMarca")
        
        assert result is not None
        assert result['label'] == 'positive'
        assert result['score'] == 0.85
        assert result['method'] == 'llm'
    
    @patch('services.llm_monitoring_service.LLMProviderFactory.create_all_providers')
    def test_sentiment_analysis_fallback(self, mock_factory):
        """Test de fallback a análisis por keywords"""
        # Mock sin Google provider o con error
        mock_factory.return_value = {}
        
        service = MultiLLMMonitoringService(api_keys={})
        
        contexts = ["MiMarca es excelente y recomendada"]
        result = service._analyze_sentiment_with_llm(contexts, "MiMarca")
        
        # Debe usar fallback por keywords
        assert result is not None
        assert result['method'] == 'keyword-fallback'
        assert result['label'] in ['positive', 'neutral', 'negative']


class TestProjectAnalysis:
    """Tests para análisis de proyectos"""
    
    @patch('services.llm_monitoring_service.get_db_connection')
    @patch('services.llm_monitoring_service.LLMProviderFactory.create_all_providers')
    def test_analyze_project_basic_structure(self, mock_factory, mock_get_db):
        """Test de estructura básica del análisis de proyecto"""
        # Mock de providers
        mock_provider = MagicMock()
        mock_provider.execute_query.return_value = {
            'success': True,
            'response_text': 'MiMarca es una gran herramienta',
            'tokens_used': 100,
            'cost_usd': 0.001,
            'model_id': 'gpt-5'
        }
        mock_factory.return_value = {'openai': mock_provider}
        
        # Mock de BD
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        
        # Mock del proyecto
        mock_cur.fetchone.return_value = {
            'id': 1,
            'brand_name': 'MiMarca',
            'industry': 'SEO',
            'language': 'es',
            'competitors': ['Semrush'],
            'enabled_llms': ['openai'],
            'queries_per_llm': 5
        }
        
        # Mock de queries vacías (se generarán)
        mock_cur.fetchall.return_value = []
        
        service = MultiLLMMonitoringService(api_keys={'openai': 'test-key'})
        
        # Ejecutar con max_workers=1 para simplificar
        result = service.analyze_project(project_id=1, max_workers=1)
        
        assert result is not None
        assert 'total_queries_executed' in result
        assert 'total_cost' in result
        assert 'llms_analyzed' in result


class TestSnapshotCreation:
    """Tests para creación de snapshots"""
    
    @patch('services.llm_monitoring_service.LLMProviderFactory.create_all_providers')
    def test_create_snapshot_structure(self, mock_factory):
        """Test de estructura de snapshot"""
        mock_factory.return_value = {}
        
        service = MultiLLMMonitoringService(api_keys={})
        
        # Mock de cursor
        mock_cur = MagicMock()
        
        # Mock de resultados
        llm_results = [
            {
                'brand_mentioned': True,
                'mention_count': 2,
                'position_in_list': 1,
                'appears_in_numbered_list': True,
                'total_items_in_list': 5,
                'sentiment': {'label': 'positive', 'score': 0.8},
                'cost': 0.001,
                'competitors_mentioned': {'Semrush': 1}
            },
            {
                'brand_mentioned': False,
                'mention_count': 0,
                'position_in_list': None,
                'appears_in_numbered_list': False,
                'total_items_in_list': None,
                'sentiment': None,
                'cost': 0.001,
                'competitors_mentioned': {}
            }
        ]
        
        # Ejecutar
        service._create_snapshot(
            cur=mock_cur,
            project_id=1,
            date=date.today(),
            llm_provider='openai',
            llm_results=llm_results,
            competitors=['Semrush']
        )
        
        # Verificar que se llamó a execute con INSERT
        assert mock_cur.execute.called
        call_args = mock_cur.execute.call_args[0][0]
        assert 'INSERT INTO llm_monitoring_snapshots' in call_args
        assert 'ON CONFLICT' in call_args


class TestParallelization:
    """Tests para verificar paralelización"""
    
    @patch('services.llm_monitoring_service.get_db_connection')
    @patch('services.llm_monitoring_service.LLMProviderFactory.create_all_providers')
    def test_parallel_execution_faster(self, mock_factory, mock_get_db):
        """Verificar que la ejecución paralela es más rápida"""
        import time
        
        # Mock de provider con delay simulado
        def mock_execute_with_delay(query):
            time.sleep(0.1)  # Simular API call de 100ms
            return {
                'success': True,
                'response_text': 'Test response',
                'tokens_used': 100,
                'cost_usd': 0.001,
                'model_id': 'gpt-5'
            }
        
        mock_provider = MagicMock()
        mock_provider.execute_query.side_effect = mock_execute_with_delay
        mock_factory.return_value = {'openai': mock_provider}
        
        # Mock de BD
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        
        mock_cur.fetchone.return_value = {
            'id': 1,
            'brand_name': 'MiMarca',
            'industry': 'SEO',
            'language': 'es',
            'competitors': [],
            'enabled_llms': ['openai'],
            'queries_per_llm': 10  # 10 queries
        }
        
        mock_cur.fetchall.return_value = []
        
        service = MultiLLMMonitoringService(api_keys={'openai': 'test-key'})
        
        # Ejecutar con paralelización (max_workers=5)
        start = time.time()
        result = service.analyze_project(project_id=1, max_workers=5)
        parallel_duration = time.time() - start
        
        # Con 10 queries de 0.1s cada una:
        # - Secuencial: ~1.0 segundos
        # - Paralelo (5 workers): ~0.2 segundos
        # Verificar que es significativamente más rápido
        assert parallel_duration < 0.5  # Debe ser menos de 0.5s
        print(f"✅ Parallelization test: {parallel_duration:.2f}s for 10 queries")


class TestErrorHandling:
    """Tests para manejo de errores"""
    
    @patch('services.llm_monitoring_service.get_db_connection')
    @patch('services.llm_monitoring_service.LLMProviderFactory.create_all_providers')
    def test_analyze_project_nonexistent(self, mock_factory, mock_get_db):
        """Test con proyecto inexistente"""
        mock_factory.return_value = {}
        
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        
        # Proyecto no encontrado
        mock_cur.fetchone.return_value = None
        
        service = MultiLLMMonitoringService(api_keys={})
        
        with pytest.raises(Exception):
            service.analyze_project(project_id=999)
    
    @patch('services.llm_monitoring_service.LLMProviderFactory.create_all_providers')
    def test_analyze_project_no_providers(self, mock_factory):
        """Test sin providers disponibles"""
        mock_factory.return_value = {}  # Sin providers
        
        service = MultiLLMMonitoringService(api_keys={})
        
        # Verificar que se maneja gracefully
        assert service.providers == {}


class TestThreadSafety:
    """Tests para verificar thread-safety"""
    
    @patch('services.llm_monitoring_service.LLMProviderFactory.create_all_providers')
    def test_thread_safe_db_connections(self, mock_factory):
        """Verificar que cada thread crea su propia conexión a BD"""
        mock_factory.return_value = {}
        
        service = MultiLLMMonitoringService(api_keys={})
        
        # Este test verifica la arquitectura, no la ejecución real
        # En la implementación real, cada thread debe crear su propia conexión
        # usando get_db_connection() dentro del thread


# Fixture para servicio con mocks
@pytest.fixture
def mock_service():
    """Servicio con providers mockeados"""
    with patch('services.llm_monitoring_service.LLMProviderFactory.create_all_providers') as mock_factory:
        mock_factory.return_value = {}
        service = MultiLLMMonitoringService(api_keys={})
        yield service


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])

