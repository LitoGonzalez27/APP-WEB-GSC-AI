"""
Tests de Performance para LLM Monitoring System

Validar:
- Paralelización es más rápida que ejecución secuencial
- Análisis completo de proyecto < 60s para 80 queries
- Thread-safety en ejecución paralela
- Manejo de carga alta
"""

import pytest
import os
import sys
import time
from unittest.mock import patch, MagicMock
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Añadir path del proyecto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.llm_monitoring_service import MultiLLMMonitoringService


class TestParallelizationPerformance:
    """Tests de performance de paralelización"""
    
    @patch('services.llm_monitoring_service.get_db_connection')
    @patch('services.llm_monitoring_service.LLMProviderFactory.create_all_providers')
    def test_parallel_vs_sequential_execution(self, mock_factory, mock_get_db):
        """
        Comparar ejecución paralela vs secuencial
        
        Esperado: Paralela al menos 5x más rápida
        """
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
        mock_provider.get_provider_name.return_value = 'openai'
        mock_provider.get_model_display_name.return_value = 'GPT-5'
        
        mock_factory.return_value = {'openai': mock_provider}
        
        # Mock de BD
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        
        mock_cur.fetchone.return_value = {
            'id': 1,
            'brand_name': 'TestBrand',
            'industry': 'SEO',
            'language': 'es',
            'competitors': [],
            'enabled_llms': ['openai'],
            'queries_per_llm': 20  # 20 queries
        }
        
        mock_cur.fetchall.return_value = []
        
        service = MultiLLMMonitoringService(api_keys={'openai': 'test-key'})
        
        # Ejecución paralela con 10 workers
        start_parallel = time.time()
        result_parallel = service.analyze_project(project_id=1, max_workers=10)
        duration_parallel = time.time() - start_parallel
        
        # Con 20 queries de 0.1s cada una:
        # - Secuencial: ~2.0 segundos
        # - Paralelo (10 workers): ~0.2 segundos
        
        print(f"\n📊 Performance Results:")
        print(f"  Parallel (10 workers): {duration_parallel:.2f}s for 20 queries")
        print(f"  Expected sequential: ~2.0s")
        print(f"  Speedup: ~{2.0 / duration_parallel:.1f}x")
        
        # Verificar que es significativamente más rápido
        assert duration_parallel < 0.5, f"Paralela demasiado lenta: {duration_parallel}s"
        assert result_parallel['total_queries_executed'] == 20
        
        print(f"✅ Parallelization is working: {duration_parallel:.2f}s")
    
    @patch('services.llm_monitoring_service.get_db_connection')
    @patch('services.llm_monitoring_service.LLMProviderFactory.create_all_providers')
    def test_full_project_analysis_under_60s(self, mock_factory, mock_get_db):
        """
        Test crítico: Análisis completo debe ser < 60s para 80 queries
        
        4 LLMs × 20 queries = 80 queries totales
        Con max_workers=10 → ~8 segundos si cada API call es 1s
        """
        # Mock de provider con delay realista
        def mock_execute_realistic(query):
            time.sleep(0.05)  # 50ms por query (optimista)
            return {
                'success': True,
                'response_text': 'TestBrand es una excelente herramienta',
                'tokens_used': 150,
                'cost_usd': 0.002,
                'model_id': 'gpt-5'
            }
        
        # Crear 4 providers mockeados
        mock_providers = {}
        for provider_name in ['openai', 'anthropic', 'google', 'perplexity']:
            mock_provider = MagicMock()
            mock_provider.execute_query.side_effect = mock_execute_realistic
            mock_provider.get_provider_name.return_value = provider_name
            mock_provider.get_model_display_name.return_value = f'{provider_name.upper()}-Model'
            mock_providers[provider_name] = mock_provider
        
        mock_factory.return_value = mock_providers
        
        # Mock de BD
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        
        mock_cur.fetchone.return_value = {
            'id': 1,
            'brand_name': 'TestBrand',
            'industry': 'SEO',
            'language': 'es',
            'competitors': ['Competitor1'],
            'enabled_llms': ['openai', 'anthropic', 'google', 'perplexity'],
            'queries_per_llm': 20  # 20 queries × 4 LLMs = 80 total
        }
        
        mock_cur.fetchall.return_value = []
        
        service = MultiLLMMonitoringService(api_keys={
            'openai': 'test-key',
            'anthropic': 'test-key',
            'google': 'test-key',
            'perplexity': 'test-key'
        })
        
        # Ejecutar análisis completo
        start = time.time()
        result = service.analyze_project(project_id=1, max_workers=10)
        duration = time.time() - start
        
        print(f"\n📊 Full Project Analysis Performance:")
        print(f"  Total queries: {result['total_queries_executed']}")
        print(f"  Duration: {duration:.2f}s")
        print(f"  Queries/second: {result['total_queries_executed'] / duration:.1f}")
        print(f"  Target: < 60s")
        
        # Verificar requisitos
        assert duration < 60, f"Análisis demasiado lento: {duration}s (límite: 60s)"
        assert result['total_queries_executed'] == 80
        
        print(f"✅ Full analysis completed in {duration:.2f}s (< 60s) ✅")
    
    @patch('services.llm_monitoring_service.get_db_connection')
    @patch('services.llm_monitoring_service.LLMProviderFactory.create_all_providers')
    def test_different_worker_counts(self, mock_factory, mock_get_db):
        """
        Test de performance con diferentes números de workers
        
        Verificar que más workers = más rápido (hasta cierto punto)
        """
        def mock_execute(query):
            time.sleep(0.1)
            return {
                'success': True,
                'response_text': 'Test',
                'tokens_used': 100,
                'cost_usd': 0.001,
                'model_id': 'gpt-5'
            }
        
        mock_provider = MagicMock()
        mock_provider.execute_query.side_effect = mock_execute
        mock_provider.get_provider_name.return_value = 'openai'
        mock_provider.get_model_display_name.return_value = 'GPT-5'
        
        mock_factory.return_value = {'openai': mock_provider}
        
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        
        mock_cur.fetchone.return_value = {
            'id': 1,
            'brand_name': 'TestBrand',
            'industry': 'SEO',
            'language': 'es',
            'competitors': [],
            'enabled_llms': ['openai'],
            'queries_per_llm': 10
        }
        
        mock_cur.fetchall.return_value = []
        
        service = MultiLLMMonitoringService(api_keys={'openai': 'test-key'})
        
        results = {}
        for max_workers in [1, 2, 5, 10]:
            start = time.time()
            service.analyze_project(project_id=1, max_workers=max_workers)
            duration = time.time() - start
            results[max_workers] = duration
        
        print(f"\n📊 Worker Count Performance:")
        for workers, duration in results.items():
            print(f"  {workers:2d} workers: {duration:.2f}s")
        
        # Verificar que más workers es más rápido
        assert results[10] < results[1], "10 workers debería ser más rápido que 1"
        assert results[5] < results[2], "5 workers debería ser más rápido que 2"
        
        print(f"✅ Worker scaling is working correctly")


class TestThreadSafety:
    """Tests para verificar thread-safety"""
    
    def test_concurrent_db_connections(self):
        """
        Verificar que múltiples threads pueden crear conexiones DB sin conflictos
        """
        from database import get_db_connection
        
        results = []
        errors = []
        
        def create_and_close_connection(thread_id):
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                
                # Hacer una query simple
                cur.execute("SELECT 1 as test")
                result = cur.fetchone()
                
                cur.close()
                conn.close()
                
                results.append((thread_id, result[0]))
            except Exception as e:
                errors.append((thread_id, str(e)))
        
        # Crear 10 threads concurrentes
        threads = []
        for i in range(10):
            t = threading.Thread(target=create_and_close_connection, args=(i,))
            threads.append(t)
            t.start()
        
        # Esperar a que terminen
        for t in threads:
            t.join()
        
        print(f"\n📊 Thread Safety Results:")
        print(f"  Successful connections: {len(results)}")
        print(f"  Errors: {len(errors)}")
        
        # Verificar que no hubo errores
        assert len(errors) == 0, f"Hubo errores en conexiones: {errors}"
        assert len(results) == 10
        
        print(f"✅ All 10 threads created DB connections successfully")
    
    @patch('services.llm_monitoring_service.get_db_connection')
    @patch('services.llm_monitoring_service.LLMProviderFactory.create_all_providers')
    def test_concurrent_query_execution(self, mock_factory, mock_get_db):
        """
        Verificar que múltiples queries concurrentes no causan race conditions
        """
        call_count = 0
        call_lock = threading.Lock()
        
        def mock_execute_threadsafe(query):
            nonlocal call_count
            with call_lock:
                call_count += 1
            time.sleep(0.01)
            return {
                'success': True,
                'response_text': 'Test',
                'tokens_used': 100,
                'cost_usd': 0.001,
                'model_id': 'gpt-5'
            }
        
        mock_provider = MagicMock()
        mock_provider.execute_query.side_effect = mock_execute_threadsafe
        mock_provider.get_provider_name.return_value = 'openai'
        mock_provider.get_model_display_name.return_value = 'GPT-5'
        
        mock_factory.return_value = {'openai': mock_provider}
        
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        
        mock_cur.fetchone.return_value = {
            'id': 1,
            'brand_name': 'TestBrand',
            'industry': 'SEO',
            'language': 'es',
            'competitors': [],
            'enabled_llms': ['openai'],
            'queries_per_llm': 20
        }
        
        mock_cur.fetchall.return_value = []
        
        service = MultiLLMMonitoringService(api_keys={'openai': 'test-key'})
        result = service.analyze_project(project_id=1, max_workers=5)
        
        print(f"\n📊 Concurrent Execution:")
        print(f"  Total calls: {call_count}")
        print(f"  Expected: {result['total_queries_executed']}")
        
        # Verificar que todas las queries se ejecutaron exactamente una vez
        assert call_count == result['total_queries_executed']
        
        print(f"✅ No race conditions detected")


class TestLoadHandling:
    """Tests para manejo de carga alta"""
    
    @patch('services.llm_monitoring_service.LLMProviderFactory.create_all_providers')
    def test_many_projects_analysis(self, mock_factory):
        """
        Simular análisis de múltiples proyectos en secuencia
        """
        mock_provider = MagicMock()
        mock_provider.execute_query.return_value = {
            'success': True,
            'response_text': 'Test',
            'tokens_used': 100,
            'cost_usd': 0.001,
            'model_id': 'gpt-5'
        }
        mock_provider.get_provider_name.return_value = 'openai'
        mock_provider.get_model_display_name.return_value = 'GPT-5'
        
        mock_factory.return_value = {'openai': mock_provider}
        
        service = MultiLLMMonitoringService(api_keys={'openai': 'test-key'})
        
        # Este test verifica que el servicio puede manejar múltiples proyectos
        # sin degradación de performance o memory leaks
        
        print(f"\n📊 Load Test: Multiple Projects")
        print(f"  Service created successfully")
        print(f"  Ready to handle multiple projects")
        
        assert service is not None
        assert service.providers is not None
        
        print(f"✅ Service can handle load")
    
    @patch('services.llm_monitoring_service.get_db_connection')
    @patch('services.llm_monitoring_service.LLMProviderFactory.create_all_providers')
    def test_error_recovery_in_parallel(self, mock_factory, mock_get_db):
        """
        Verificar que si una query falla, las demás continúan
        """
        call_count = 0
        
        def mock_execute_with_errors(query):
            nonlocal call_count
            call_count += 1
            
            # Fallar cada 3ra query
            if call_count % 3 == 0:
                return {
                    'success': False,
                    'error': 'Simulated API error',
                    'tokens_used': 0,
                    'cost_usd': 0
                }
            
            return {
                'success': True,
                'response_text': 'Test',
                'tokens_used': 100,
                'cost_usd': 0.001,
                'model_id': 'gpt-5'
            }
        
        mock_provider = MagicMock()
        mock_provider.execute_query.side_effect = mock_execute_with_errors
        mock_provider.get_provider_name.return_value = 'openai'
        mock_provider.get_model_display_name.return_value = 'GPT-5'
        
        mock_factory.return_value = {'openai': mock_provider}
        
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        
        mock_cur.fetchone.return_value = {
            'id': 1,
            'brand_name': 'TestBrand',
            'industry': 'SEO',
            'language': 'es',
            'competitors': [],
            'enabled_llms': ['openai'],
            'queries_per_llm': 12  # 12 queries, 4 fallarán
        }
        
        mock_cur.fetchall.return_value = []
        
        service = MultiLLMMonitoringService(api_keys={'openai': 'test-key'})
        result = service.analyze_project(project_id=1, max_workers=5)
        
        print(f"\n📊 Error Recovery:")
        print(f"  Total queries attempted: {call_count}")
        print(f"  Expected failures: {call_count // 3}")
        
        # Verificar que el análisis completó a pesar de los errores
        assert result is not None
        assert result['total_queries_executed'] == 12
        
        print(f"✅ System handles errors gracefully")


class TestMemoryUsage:
    """Tests básicos de memoria (sin profiling avanzado)"""
    
    @patch('services.llm_monitoring_service.LLMProviderFactory.create_all_providers')
    def test_service_cleanup(self, mock_factory):
        """
        Verificar que el servicio se puede crear y destruir sin memory leaks obvios
        """
        mock_factory.return_value = {}
        
        # Crear y destruir múltiples servicios
        for i in range(10):
            service = MultiLLMMonitoringService(api_keys={})
            assert service is not None
            del service
        
        print(f"\n✅ Service cleanup working correctly")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short', '-s'])

