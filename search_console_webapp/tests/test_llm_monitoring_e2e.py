"""
Tests End-to-End para LLM Monitoring System

Flujo completo:
1. Crear proyecto vía API
2. Añadir queries
3. Ejecutar análisis
4. Verificar resultados en BD
5. Obtener métricas vía API
"""

import pytest
import os
import sys
import json
from unittest.mock import patch, MagicMock
from datetime import datetime, date, timedelta

# Añadir path del proyecto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Imports después de añadir al path
from database import get_db_connection
import psycopg2.extras


class TestEndToEndFlow:
    """Tests End-to-End del flujo completo"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup y teardown para cada test"""
        # Setup: Limpiar datos de test
        conn = None
        cur = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Limpiar datos de test (usar RETURNING para verificar)
            cur.execute("""
                DELETE FROM llm_monitoring_projects 
                WHERE name LIKE 'TEST_%'
            """)
            conn.commit()
            
            yield  # Ejecutar el test
            
            # Teardown: Limpiar de nuevo
            cur.execute("""
                DELETE FROM llm_monitoring_projects 
                WHERE name LIKE 'TEST_%'
            """)
            conn.commit()
            
        except Exception as e:
            print(f"Warning: Error en setup/teardown: {e}")
            if conn:
                conn.rollback()
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    def test_create_project_in_database(self):
        """Test E2E: Crear proyecto en BD"""
        conn = None
        cur = None
        try:
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Obtener un user_id válido
            cur.execute("SELECT id FROM users LIMIT 1")
            user = cur.fetchone()
            
            if not user:
                pytest.skip("No hay usuarios en la BD para testing")
            
            user_id = user['id']
            
            # Crear proyecto
            cur.execute("""
                INSERT INTO llm_monitoring_projects (
                    user_id, name, brand_name, industry,
                    enabled_llms, competitors, language, queries_per_llm
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s
                ) RETURNING id
            """, (
                user_id,
                'TEST_E2E_Project',
                'TestBrand',
                'SEO tools',
                ['openai', 'google'],
                json.dumps(['Competitor1', 'Competitor2']),
                'es',
                10
            ))
            
            project_id = cur.fetchone()['id']
            conn.commit()
            
            # Verificar que se creó
            cur.execute("""
                SELECT * FROM llm_monitoring_projects WHERE id = %s
            """, (project_id,))
            
            project = cur.fetchone()
            
            assert project is not None
            assert project['name'] == 'TEST_E2E_Project'
            assert project['brand_name'] == 'TestBrand'
            assert 'openai' in project['enabled_llms']
            
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    def test_add_queries_to_project(self):
        """Test E2E: Añadir queries a un proyecto"""
        conn = None
        cur = None
        try:
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Obtener un user_id válido
            cur.execute("SELECT id FROM users LIMIT 1")
            user = cur.fetchone()
            if not user:
                pytest.skip("No hay usuarios en la BD para testing")
            
            user_id = user['id']
            
            # Crear proyecto
            cur.execute("""
                INSERT INTO llm_monitoring_projects (
                    user_id, name, brand_name, industry, language
                ) VALUES (%s, %s, %s, %s, %s) RETURNING id
            """, (user_id, 'TEST_Queries_Project', 'TestBrand', 'SEO', 'es'))
            
            project_id = cur.fetchone()['id']
            conn.commit()
            
            # Añadir queries
            queries = [
                "¿Cuáles son las mejores herramientas SEO?",
                "Top 10 software de SEO",
                "Comparativa de herramientas SEO"
            ]
            
            for query_text in queries:
                cur.execute("""
                    INSERT INTO llm_monitoring_queries (
                        project_id, query_text, language, query_type
                    ) VALUES (%s, %s, %s, %s)
                """, (project_id, query_text, 'es', 'general'))
            
            conn.commit()
            
            # Verificar que se añadieron
            cur.execute("""
                SELECT COUNT(*) as count 
                FROM llm_monitoring_queries 
                WHERE project_id = %s
            """, (project_id,))
            
            count = cur.fetchone()['count']
            assert count == 3
            
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    @patch('services.llm_monitoring_service.LLMProviderFactory.create_all_providers')
    def test_execute_analysis_and_store_results(self, mock_factory):
        """Test E2E: Ejecutar análisis y guardar resultados"""
        # Mock de provider
        mock_provider = MagicMock()
        mock_provider.execute_query.return_value = {
            'success': True,
            'response_text': 'TestBrand es una excelente herramienta de SEO.',
            'tokens_used': 100,
            'cost_usd': 0.001,
            'model_id': 'gpt-5'
        }
        mock_provider.get_provider_name.return_value = 'openai'
        mock_provider.get_model_display_name.return_value = 'GPT-5'
        
        mock_factory.return_value = {'openai': mock_provider}
        
        conn = None
        cur = None
        try:
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Obtener un user_id válido
            cur.execute("SELECT id FROM users LIMIT 1")
            user = cur.fetchone()
            if not user:
                pytest.skip("No hay usuarios en la BD para testing")
            
            user_id = user['id']
            
            # Crear proyecto
            cur.execute("""
                INSERT INTO llm_monitoring_projects (
                    user_id, name, brand_name, industry, 
                    enabled_llms, language, queries_per_llm
                ) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
            """, (
                user_id, 'TEST_Analysis_Project', 'TestBrand', 'SEO',
                ['openai'], 'es', 3
            ))
            
            project_id = cur.fetchone()['id']
            conn.commit()
            
            # Ejecutar análisis
            from services.llm_monitoring_service import MultiLLMMonitoringService
            
            service = MultiLLMMonitoringService(api_keys={'openai': 'test-key'})
            result = service.analyze_project(project_id=project_id, max_workers=1)
            
            # Verificar resultados
            assert result is not None
            assert 'total_queries_executed' in result
            assert result['total_queries_executed'] > 0
            
            # Verificar que se guardaron en BD
            cur.execute("""
                SELECT COUNT(*) as count 
                FROM llm_monitoring_results 
                WHERE project_id = %s
            """, (project_id,))
            
            count = cur.fetchone()['count']
            assert count > 0
            
            # Verificar que se creó snapshot
            cur.execute("""
                SELECT COUNT(*) as count 
                FROM llm_monitoring_snapshots 
                WHERE project_id = %s
            """, (project_id,))
            
            snapshot_count = cur.fetchone()['count']
            assert snapshot_count > 0
            
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    def test_retrieve_metrics_from_database(self):
        """Test E2E: Obtener métricas desde BD"""
        conn = None
        cur = None
        try:
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Obtener un user_id válido
            cur.execute("SELECT id FROM users LIMIT 1")
            user = cur.fetchone()
            if not user:
                pytest.skip("No hay usuarios en la BD para testing")
            
            user_id = user['id']
            
            # Crear proyecto
            cur.execute("""
                INSERT INTO llm_monitoring_projects (
                    user_id, name, brand_name, industry, language
                ) VALUES (%s, %s, %s, %s, %s) RETURNING id
            """, (user_id, 'TEST_Metrics_Project', 'TestBrand', 'SEO', 'es'))
            
            project_id = cur.fetchone()['id']
            conn.commit()
            
            # Insertar snapshot de prueba
            cur.execute("""
                INSERT INTO llm_monitoring_snapshots (
                    project_id, analysis_date, llm_provider,
                    mention_rate, avg_position, share_of_voice,
                    sentiment_positive, sentiment_neutral, sentiment_negative,
                    total_cost
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                project_id, date.today(), 'openai',
                0.75, 2.5, 0.33,
                0.80, 0.15, 0.05,
                0.05
            ))
            conn.commit()
            
            # Obtener métricas
            cur.execute("""
                SELECT * FROM llm_monitoring_snapshots 
                WHERE project_id = %s 
                ORDER BY analysis_date DESC
            """, (project_id,))
            
            metrics = cur.fetchall()
            
            assert len(metrics) > 0
            assert metrics[0]['mention_rate'] == 0.75
            assert metrics[0]['avg_position'] == 2.5
            
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    def test_comparison_view_works(self):
        """Test E2E: Verificar que la vista de comparación funciona"""
        conn = None
        cur = None
        try:
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Obtener un user_id válido
            cur.execute("SELECT id FROM users LIMIT 1")
            user = cur.fetchone()
            if not user:
                pytest.skip("No hay usuarios en la BD para testing")
            
            user_id = user['id']
            
            # Crear proyecto
            cur.execute("""
                INSERT INTO llm_monitoring_projects (
                    user_id, name, brand_name, industry, language
                ) VALUES (%s, %s, %s, %s, %s) RETURNING id
            """, (user_id, 'TEST_Comparison_Project', 'TestBrand', 'SEO', 'es'))
            
            project_id = cur.fetchone()['id']
            conn.commit()
            
            # Insertar snapshots para múltiples LLMs
            for llm_provider in ['openai', 'google']:
                cur.execute("""
                    INSERT INTO llm_monitoring_snapshots (
                        project_id, analysis_date, llm_provider,
                        mention_rate, avg_position, share_of_voice,
                        sentiment_positive, sentiment_neutral, sentiment_negative,
                        total_cost
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    project_id, date.today(), llm_provider,
                    0.75, 2.5, 0.33,
                    0.80, 0.15, 0.05,
                    0.05
                ))
            conn.commit()
            
            # Query la vista de comparación
            cur.execute("""
                SELECT * FROM llm_visibility_comparison 
                WHERE project_id = %s 
                AND analysis_date = %s
            """, (project_id, date.today()))
            
            comparison = cur.fetchall()
            
            assert len(comparison) == 2  # openai y google
            
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()


class TestAPIEndpointsE2E:
    """Tests E2E para API endpoints (sin Flask test client)"""
    
    def test_project_crud_in_database(self):
        """Test CRUD de proyectos en BD directamente"""
        conn = None
        cur = None
        try:
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Obtener user_id
            cur.execute("SELECT id FROM users LIMIT 1")
            user = cur.fetchone()
            if not user:
                pytest.skip("No hay usuarios en la BD para testing")
            
            user_id = user['id']
            
            # CREATE
            cur.execute("""
                INSERT INTO llm_monitoring_projects (
                    user_id, name, brand_name, industry, language
                ) VALUES (%s, %s, %s, %s, %s) RETURNING id
            """, (user_id, 'TEST_CRUD_Project', 'TestBrand', 'SEO', 'es'))
            
            project_id = cur.fetchone()['id']
            conn.commit()
            
            # READ
            cur.execute("""
                SELECT * FROM llm_monitoring_projects WHERE id = %s
            """, (project_id,))
            project = cur.fetchone()
            assert project['name'] == 'TEST_CRUD_Project'
            
            # UPDATE
            cur.execute("""
                UPDATE llm_monitoring_projects 
                SET name = %s, updated_at = NOW()
                WHERE id = %s
            """, ('TEST_CRUD_Project_Updated', project_id))
            conn.commit()
            
            cur.execute("""
                SELECT name FROM llm_monitoring_projects WHERE id = %s
            """, (project_id,))
            updated_project = cur.fetchone()
            assert updated_project['name'] == 'TEST_CRUD_Project_Updated'
            
            # DELETE
            cur.execute("""
                DELETE FROM llm_monitoring_projects WHERE id = %s
            """, (project_id,))
            conn.commit()
            
            cur.execute("""
                SELECT COUNT(*) as count 
                FROM llm_monitoring_projects 
                WHERE id = %s
            """, (project_id,))
            count = cur.fetchone()['count']
            assert count == 0
            
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()


class TestDataIntegrity:
    """Tests para verificar integridad de datos"""
    
    def test_foreign_key_constraints(self):
        """Verificar que las foreign keys funcionan"""
        conn = None
        cur = None
        try:
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Intentar crear query sin proyecto válido
            with pytest.raises(Exception):
                cur.execute("""
                    INSERT INTO llm_monitoring_queries (
                        project_id, query_text, language
                    ) VALUES (%s, %s, %s)
                """, (999999, 'Test query', 'es'))
                conn.commit()
            
            conn.rollback()
            
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    def test_cascade_delete(self):
        """Verificar que ON DELETE CASCADE funciona"""
        conn = None
        cur = None
        try:
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Obtener user_id
            cur.execute("SELECT id FROM users LIMIT 1")
            user = cur.fetchone()
            if not user:
                pytest.skip("No hay usuarios en la BD para testing")
            
            user_id = user['id']
            
            # Crear proyecto
            cur.execute("""
                INSERT INTO llm_monitoring_projects (
                    user_id, name, brand_name, industry, language
                ) VALUES (%s, %s, %s, %s, %s) RETURNING id
            """, (user_id, 'TEST_Cascade_Project', 'TestBrand', 'SEO', 'es'))
            
            project_id = cur.fetchone()['id']
            conn.commit()
            
            # Añadir query
            cur.execute("""
                INSERT INTO llm_monitoring_queries (
                    project_id, query_text, language
                ) VALUES (%s, %s, %s) RETURNING id
            """, (project_id, 'Test query', 'es'))
            
            query_id = cur.fetchone()['id']
            conn.commit()
            
            # Verificar que existe
            cur.execute("""
                SELECT COUNT(*) as count 
                FROM llm_monitoring_queries 
                WHERE id = %s
            """, (query_id,))
            assert cur.fetchone()['count'] == 1
            
            # Eliminar proyecto
            cur.execute("""
                DELETE FROM llm_monitoring_projects WHERE id = %s
            """, (project_id,))
            conn.commit()
            
            # Verificar que la query también se eliminó
            cur.execute("""
                SELECT COUNT(*) as count 
                FROM llm_monitoring_queries 
                WHERE id = %s
            """, (query_id,))
            assert cur.fetchone()['count'] == 0
            
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])

