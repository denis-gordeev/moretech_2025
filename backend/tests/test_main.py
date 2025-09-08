import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main import app

client = TestClient(app)


class TestHealthEndpoint:
    def test_health_check_success(self):
        with patch('main.db_analyzer.test_connection', return_value=True), \
             patch('main.llm_analyzer.test_connection', return_value=True):
            
            response = client.get("/health")
            assert response.status_code == 200
            
            data = response.json()
            assert data["status"] == "healthy"
            assert data["database_connected"] is True
            assert data["openai_available"] is True

    def test_health_check_database_failure(self):
        with patch('main.db_analyzer.test_connection', return_value=False), \
             patch('main.llm_analyzer.test_connection', return_value=True):
            
            response = client.get("/health")
            assert response.status_code == 200
            
            data = response.json()
            assert data["status"] == "unhealthy"
            assert data["database_connected"] is False
            assert data["openai_available"] is True

    def test_health_check_openai_failure(self):
        with patch('main.db_analyzer.test_connection', return_value=True), \
             patch('main.llm_analyzer.test_connection', return_value=False):
            
            response = client.get("/health")
            assert response.status_code == 200
            
            data = response.json()
            assert data["status"] == "unhealthy"
            assert data["database_connected"] is True
            assert data["openai_available"] is False


class TestAnalyzeEndpoint:
    def test_analyze_empty_query(self):
        response = client.post("/analyze", json={"query": ""})
        assert response.status_code == 400
        assert "Query cannot be empty" in response.json()["detail"]

    def test_analyze_query_too_long(self):
        long_query = "SELECT * FROM users " * 1000  # Very long query
        response = client.post("/analyze", json={"query": long_query})
        assert response.status_code == 400
        assert "Query too long" in response.json()["detail"]

    @patch('main.db_analyzer.analyze_query_performance')
    @patch('main.llm_analyzer.analyze_query_with_llm')
    def test_analyze_success(self, mock_llm, mock_db):
        # Mock database response
        mock_db.return_value = {
            'total_cost': 100.0,
            'execution_time': 50.0,
            'rows': 1000,
            'width': 64,
            'plan_json': {'Total Cost': 100.0, 'Actual Total Time': 50.0}
        }
        
        # Mock LLM response
        mock_llm.return_value = {
            'resource_metrics': {
                'cpu_usage': 75.0,
                'memory_usage': 128.0,
                'io_operations': 10,
                'disk_reads': 5,
                'disk_writes': 2
            },
            'recommendations': [
                {
                    'type': 'index',
                    'priority': 'high',
                    'title': 'Add index',
                    'description': 'Add index on email column',
                    'potential_improvement': 'Will improve query performance',
                    'implementation': 'CREATE INDEX idx_email ON users(email);',
                    'estimated_speedup': 50.0
                }
            ],
            'warnings': ['High CPU usage detected']
        }
        
        response = client.post("/analyze", json={"query": "SELECT * FROM users WHERE email = 'test@example.com'"})
        assert response.status_code == 200
        
        data = response.json()
        assert data["query"] == "SELECT * FROM users WHERE email = 'test@example.com'"
        assert data["execution_plan"]["total_cost"] == 100.0
        assert len(data["recommendations"]) == 1
        assert len(data["warnings"]) == 1

    @patch('main.db_analyzer.analyze_query_performance')
    def test_analyze_database_error(self, mock_db):
        mock_db.side_effect = Exception("Database connection failed")
        
        response = client.post("/analyze", json={"query": "SELECT * FROM users"})
        assert response.status_code == 500
        assert "Analysis failed" in response.json()["detail"]


class TestExamplesEndpoint:
    def test_get_examples(self):
        response = client.get("/examples")
        assert response.status_code == 200
        
        data = response.json()
        assert "examples" in data
        assert len(data["examples"]) > 0
        
        # Check structure of first example
        example = data["examples"][0]
        assert "name" in example
        assert "query" in example
        assert "description" in example


class TestDatabaseInfoEndpoint:
    @patch('main.db_analyzer.get_database_info')
    def test_get_database_info_success(self, mock_get_info):
        mock_get_info.return_value = {
            'version': 'PostgreSQL 15.0',
            'database_size': '10 MB',
            'table_count': 5,
            'index_count': 3
        }
        
        response = client.get("/database/info")
        assert response.status_code == 200
        
        data = response.json()
        assert data["version"] == "PostgreSQL 15.0"
        assert data["table_count"] == 5

    @patch('main.db_analyzer.get_database_info')
    def test_get_database_info_error(self, mock_get_info):
        mock_get_info.side_effect = Exception("Database error")
        
        response = client.get("/database/info")
        assert response.status_code == 500
        assert "Failed to get database info" in response.json()["detail"]


class TestDatabaseConnectionEndpoint:
    def test_test_database_connection_success(self):
        with patch('main.PostgreSQLAnalyzer') as mock_analyzer_class:
            mock_analyzer = MagicMock()
            mock_analyzer.test_connection.return_value = True
            mock_analyzer_class.return_value = mock_analyzer
            
            config = {
                "host": "localhost",
                "port": 5432,
                "database": "test_db",
                "username": "test_user",
                "password": "test_pass"
            }
            
            response = client.post("/database/test", json=config)
            assert response.status_code == 200
            
            data = response.json()
            assert data["status"] == "success"
            assert "successful" in data["message"]

    def test_test_database_connection_failure(self):
        with patch('main.PostgreSQLAnalyzer') as mock_analyzer_class:
            mock_analyzer = MagicMock()
            mock_analyzer.test_connection.return_value = False
            mock_analyzer_class.return_value = mock_analyzer
            
            config = {
                "host": "localhost",
                "port": 5432,
                "database": "test_db",
                "username": "test_user",
                "password": "test_pass"
            }
            
            response = client.post("/database/test", json=config)
            assert response.status_code == 200
            
            data = response.json()
            assert data["status"] == "error"
            assert "failed" in data["message"]
