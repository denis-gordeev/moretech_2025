from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from datetime import datetime
import tempfile
from pathlib import Path

# Mock the cache directory before importing main
with patch('execution_plan_cache.Path.mkdir') as mock_mkdir:
    mock_mkdir.return_value = None
    from main import app

client = TestClient(app)


class TestHealthEndpoint:
    def test_health_check_success(self):
        with patch("main.db_analyzer.test_connection", return_value=True), patch(
            "main.llm_analyzer.test_connection", return_value=True
        ):

            response = client.get("/health")
            assert response.status_code == 200

            data = response.json()
            assert data["status"] == "healthy"
            assert data["database_connected"] is True
            assert data["openai_available"] is True

    def test_health_check_database_failure(self):
        with patch("main.db_analyzer.test_connection", return_value=False), patch(
            "main.llm_analyzer.test_connection", return_value=True
        ):

            response = client.get("/health")
            assert response.status_code == 200

            data = response.json()
            assert data["status"] == "unhealthy"
            assert data["database_connected"] is False
            assert data["openai_available"] is True

    def test_health_check_openai_failure(self):
        with patch("main.db_analyzer.test_connection", return_value=True), patch(
            "main.llm_analyzer.test_connection", return_value=False
        ):

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

    @patch("main.db_analyzer.analyze_query_performance")
    @patch("main.llm_analyzer.analyze_query_with_llm")
    def test_analyze_success(self, mock_llm, mock_db):
        # Mock database response
        mock_db.return_value = {
            "total_cost": 100.0,
            "execution_time": 50.0,
            "rows": 1000,
            "width": 64,
            "plan_json": {"Total Cost": 100.0, "Actual Total Time": 50.0},
        }

        # Mock LLM response
        mock_llm.return_value = {
            "resource_metrics": {
                "cpu_usage": 75.0,
                "memory_usage": 128.0,
                "io_operations": 10,
                "disk_reads": 5,
                "disk_writes": 2,
            },
            "recommendations": [
                {
                    "type": "index",
                    "priority": "high",
                    "title": "Add index",
                    "description": "Add index on email column",
                    "potential_improvement": "Will improve query performance",
                    "implementation": "CREATE INDEX idx_email ON users(email);",
                    "estimated_speedup": 50.0,
                }
            ],
            "warnings": ["High CPU usage detected"],
        }

        response = client.post("/analyze", json={"query": "SELECT * FROM users WHERE email = 'test@example.com'"})
        assert response.status_code == 200

        data = response.json()
        assert data["query"] == "SELECT * FROM users WHERE email = 'test@example.com'"
        assert data["execution_plan"]["total_cost"] == 100.0
        assert len(data["recommendations"]) == 1
        assert len(data["warnings"]) == 1

    @patch("main.db_analyzer.analyze_query_performance")
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
    @patch("main.db_analyzer.get_database_info")
    def test_get_database_info_success(self, mock_get_info):
        mock_get_info.return_value = {
            "version": "PostgreSQL 15.0",
            "database_size": "10 MB",
            "table_count": 5,
            "index_count": 3,
        }

        response = client.get("/database/info")
        assert response.status_code == 200

        data = response.json()
        assert data["version"] == "PostgreSQL 15.0"
        assert data["table_count"] == 5

    @patch("main.db_analyzer.get_database_info")
    def test_get_database_info_error(self, mock_get_info):
        mock_get_info.side_effect = Exception("Database error")

        response = client.get("/database/info")
        assert response.status_code == 500
        assert "Failed to get database info" in response.json()["detail"]


class TestDatabaseConnectionEndpoint:
    def test_test_database_connection_success(self):
        with patch("main.PostgreSQLAnalyzer") as mock_analyzer_class:
            mock_analyzer = MagicMock()
            mock_analyzer.test_connection = AsyncMock(return_value=True)
            mock_analyzer_class.return_value = mock_analyzer

            config = {
                "host": "localhost",
                "port": 5432,
                "database": "test_db",
                "username": "test_user",
                "password": "test_pass",
            }

            response = client.post("/database/test", json=config)
            assert response.status_code == 200

            data = response.json()
            assert data["status"] == "success"
            assert "successful" in data["message"]

    def test_test_database_connection_failure(self):
        with patch("main.PostgreSQLAnalyzer") as mock_analyzer_class:
            mock_analyzer = MagicMock()
            mock_analyzer.test_connection = AsyncMock(return_value=False)
            mock_analyzer_class.return_value = mock_analyzer

            config = {
                "host": "localhost",
                "port": 5432,
                "database": "test_db",
                "username": "test_user",
                "password": "test_pass",
            }

            response = client.post("/database/test", json=config)
            assert response.status_code == 200

            data = response.json()
            assert data["status"] == "error"
            assert "failed" in data["message"]


class TestRootEndpoint:
    def test_root_endpoint(self):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert "PostgreSQL Query Analyzer" in data["message"]


class TestModelsEndpoint:
    def test_get_models(self):
        """Test GET /models endpoint"""
        response = client.get("/models")
        assert response.status_code == 200
        
        data = response.json()
        assert "available_models" in data
        assert len(data["available_models"]) >= 1

    @patch("main.llm_analyzer.switch_model")
    def test_switch_model_success(self, mock_switch):
        """Test POST /models/switch endpoint success"""
        mock_switch.return_value = True
        
        response = client.post("/models/switch", json={"model_name": "Test Model"})
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "success"

    @patch("main.llm_analyzer.switch_model")
    def test_switch_model_failure(self, mock_switch):
        """Test POST /models/switch endpoint failure"""
        mock_switch.return_value = False
        
        response = client.post("/models/switch", json={"model_name": "Invalid Model"})
        assert response.status_code == 400


class TestExecutionPlanEndpoint:
    @patch("main.execution_plan_cache.get_plan")
    @patch("main.db_analyzer.analyze_query_performance")
    def test_execution_plan_from_cache(self, mock_analyze, mock_get_plan):
        """Test execution plan endpoint with cached result"""
        mock_plan = {
            "total_cost": 100.0,
            "execution_time": 50.0,
            "rows": 1000,
            "width": 64,
            "plan_json": {"Node Type": "Seq Scan"}
        }
        mock_get_plan.return_value = mock_plan
        
        response = client.post("/analyze/execution-plan", json={
            "query": "SELECT * FROM users"
        })
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "execution_plan_ready"
        assert data["execution_plan"]["total_cost"] == 100.0

    @patch("main.execution_plan_cache.get_plan")
    @patch("main.execution_plan_cache.set_plan")
    @patch("main.db_analyzer.analyze_query_performance")
    def test_execution_plan_not_cached(self, mock_analyze, mock_set_plan, mock_get_plan):
        """Test execution plan endpoint without cache"""
        mock_get_plan.return_value = None
        mock_analyze.return_value = {
            "total_cost": 100.0,
            "execution_time": 50.0,
            "rows": 1000,
            "width": 64,
            "plan_json": {"Node Type": "Seq Scan"}
        }
        
        response = client.post("/analyze/execution-plan", json={
            "query": "SELECT * FROM users"
        })
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "execution_plan_ready"


class TestLLMAnalyzeEndpoint:
    @patch("main.llm_analyzer.analyze_query_with_llm")
    def test_llm_analyze_success(self, mock_analyze):
        """Test LLM analyze endpoint success"""
        mock_analyze.return_value = {
            "resource_metrics": {
                "cpu_usage": 75.0,
                "memory_usage": 128.0,
                "io_operations": 10,
                "disk_reads": 5,
                "disk_writes": 2
            },
            "recommendations": [],
            "warnings": []
        }
        
        response = client.post("/analyze/llm", json={
            "query": "SELECT * FROM users"
        })
        assert response.status_code == 200
        
        data = response.json()
        assert "resource_metrics" in data
        assert data["resource_metrics"]["cpu_usage"] == 75.0

    @patch("main.llm_analyzer.analyze_query_with_llm")
    def test_llm_analyze_failure(self, mock_analyze):
        """Test LLM analyze endpoint failure"""
        mock_analyze.side_effect = Exception("LLM analysis failed")
        
        response = client.post("/analyze/llm", json={
            "query": "SELECT * FROM users"
        })
        assert response.status_code == 500


class TestCacheEndpoints:
    @patch("main.llm_analyzer.get_cache_stats")
    def test_cache_stats(self, mock_stats):
        """Test cache stats endpoint"""
        mock_stats.return_value = {
            "total_entries": 10,
            "cache_size": "1MB",
            "hit_rate": 85.5
        }
        
        response = client.get("/cache/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert "total_entries" in data or "cache_stats" in data

    @patch("main.execution_plan_cache.get_cache_stats")
    def test_execution_plan_cache_stats(self, mock_stats):
        """Test execution plan cache stats endpoint"""
        mock_stats.return_value = {
            "total_entries": 5,
            "cache_size": "500KB"
        }
        
        response = client.get("/cache/execution-plans/stats")
        assert response.status_code == 200

    @patch("main.llm_analyzer.clear_cache")
    def test_clear_cache(self, mock_clear):
        """Test clear cache endpoint"""
        mock_clear.return_value = True
        
        response = client.post("/cache/clear")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "success"

    @patch("main.execution_plan_cache.clear_cache")
    def test_clear_execution_plan_cache(self, mock_clear):
        """Test clear execution plan cache endpoint"""
        response = client.post("/cache/execution-plans/clear")
        assert response.status_code == 200

    @patch("main.execution_plan_cache.precompute_execution_plans")
    def test_precompute_execution_plans(self, mock_precompute):
        """Test precompute execution plans endpoint"""
        mock_precompute.return_value = {"processed": 5, "errors": 0}
        
        response = client.post("/cache/execution-plans/precompute", json={
            "database_profile_id": "test_profile",
            "max_queries": 10
        })
        assert response.status_code == 200

    @patch("main.execution_plan_cache.precompute_for_all_database_profiles")
    def test_precompute_all_databases(self, mock_precompute):
        """Test precompute all databases endpoint"""
        mock_precompute.return_value = {
            "total_profiles": 2,
            "total_processed": 10,
            "total_errors": 0
        }
        
        response = client.post("/cache/execution-plans/precompute-all-databases", json={
            "max_queries_per_db": 5
        })
        assert response.status_code == 200


class TestLogAnalyzerEndpoint:
    @patch("main.log_analyzer.analyze_logs")
    def test_analyze_logs_success(self, mock_analyze):
        """Test logs analyze endpoint success"""
        mock_analyze.return_value = {
            "summary": "Log analysis complete",
            "slow_queries": [],
            "errors": [],
            "recommendations": []
        }
        
        response = client.get("/logs/analyze", params={"log_file_path": "/var/log/postgresql.log"})
        assert response.status_code == 200

    @patch("main.log_analyzer.analyze_logs")
    def test_analyze_logs_failure(self, mock_analyze):
        """Test logs analyze endpoint failure"""
        mock_analyze.side_effect = Exception("Log analysis failed")
        
        response = client.get("/logs/analyze", params={"log_file_path": "/invalid/path.log"})
        assert response.status_code == 500


class TestConfigAnalyzerEndpoint:
    @patch("main.config_analyzer.get_configuration_analysis")
    def test_analyze_config_success(self, mock_analyze):
        """Test config analyze endpoint success"""
        mock_analyze.return_value = {
            "settings": {},
            "recommendations": [],
            "system_info": {}
        }
        
        response = client.get("/config/analyze")
        assert response.status_code == 200

    @patch("main.config_analyzer.get_configuration_analysis")
    def test_analyze_config_failure(self, mock_analyze):
        """Test config analyze endpoint failure"""
        mock_analyze.side_effect = Exception("Config analysis failed")
        
        response = client.get("/config/analyze")
        assert response.status_code == 500


class TestFullHealthEndpoint:
    @patch("main.db_analyzer.test_connection")
    @patch("main.llm_analyzer.test_connection")
    @patch("main.db_analyzer.get_database_info")
    def test_full_health_check(self, mock_db_info, mock_llm_test, mock_db_test):
        """Test full health check endpoint"""
        mock_db_test.return_value = True
        mock_llm_test.return_value = True
        mock_db_info.return_value = {
            "version": "PostgreSQL 15.0",
            "database_size": "10 MB"
        }
        
        response = client.get("/health/full")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "database_info" in data


class TestTableStatsEndpoint:
    @patch("main.table_stats_service.collect_table_statistics")
    def test_table_statistics_success(self, mock_collect):
        """Test table statistics endpoint success"""
        mock_collect.return_value = {
            "users": {"row_count": 1000, "size": "1MB"},
            "orders": {"row_count": 500, "size": "500KB"}
        }
        
        response = client.get("/tables/statistics")
        assert response.status_code == 200
        
        data = response.json()
        assert "statistics" in data

    @patch("main.table_stats_service.collect_table_statistics")
    def test_table_statistics_failure(self, mock_collect):
        """Test table statistics endpoint failure"""
        mock_collect.side_effect = Exception("Stats collection failed")
        
        response = client.get("/tables/statistics")
        assert response.status_code == 500


class TestCacheWarmupEndpoints:
    @patch("main.cache_warmup.warmup_cache")
    def test_cache_warmup_success(self, mock_warmup):
        """Test cache warmup endpoint success"""
        mock_warmup.return_value = (10, 0)  # cached, errors
        
        response = client.post("/cache/warmup", json={"model_name": "Test Model"})
        assert response.status_code == 200

    @patch("main.cache_warmup.warmup_cache_for_all_models")
    def test_cache_warmup_all_models(self, mock_warmup):
        """Test cache warmup all models endpoint"""
        mock_warmup.return_value = {
            "Test Model": {"cached": 10, "errors": 0}
        }
        
        response = client.post("/cache/warmup/all-models")
        assert response.status_code == 200

    @patch("main.cache_warmup.test_cache_hit")
    def test_cache_test_success(self, mock_test):
        """Test cache test endpoint success"""
        mock_test.return_value = {"hit": True, "response_time": 0.1}
        
        response = client.post("/cache/test", json={
            "query": "SELECT * FROM users",
            "model_name": "Test Model"
        })
        assert response.status_code == 200

    @patch("main.cache_warmup.test_cache_hit")
    def test_cache_test_failure(self, mock_test):
        """Test cache test endpoint failure"""
        mock_test.return_value = {"hit": False, "error": "Test failed"}
        
        response = client.post("/cache/test", json={
            "query": "SELECT * FROM users",
            "model_name": "Test Model"
        })
        assert response.status_code == 200  # The endpoint might return 200 even on failure


class TestDatabaseProfilesEndpoints:
    @patch("main.profile_manager.create_profile")
    def test_create_database_profile_success(self, mock_create):
        """Test create database profile endpoint success"""
        mock_create.return_value = (True, "profile_id_123")
        
        profile_data = {
            "name": "Test Profile",
            "host": "localhost",
            "port": 5432,
            "database": "test_db",
            "username": "test_user",
            "password": "test_pass"
        }
        
        response = client.post("/database/profiles", json=profile_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "success"

    @patch("main.profile_manager.create_profile")
    def test_create_database_profile_failure(self, mock_create):
        """Test create database profile endpoint failure"""
        mock_create.return_value = (False, "Profile creation failed")
        
        profile_data = {
            "name": "Test Profile",
            "host": "localhost",
            "port": 5432,
            "database": "test_db",
            "username": "test_user",
            "password": "test_pass"
        }
        
        response = client.post("/database/profiles", json=profile_data)
        assert response.status_code == 400

    @patch("main.profile_manager.list_profiles")
    def test_list_database_profiles(self, mock_list):
        """Test list database profiles endpoint"""
        mock_profile = MagicMock()
        mock_profile.name = "Test Profile"
        mock_profile.host = "localhost"
        mock_list.return_value = [mock_profile]
        
        response = client.get("/database/profiles")
        assert response.status_code == 200
        
        data = response.json()
        assert "profiles" in data

    @patch("main.profile_manager.refresh_connection")
    def test_connect_to_profile_success(self, mock_connect):
        """Test connect to profile endpoint success"""
        mock_connect.return_value = (True, "Connected successfully")
        
        response = client.post("/database/profiles/test_profile/connect", json={"password": "test_pass"})
        assert response.status_code == 200

    @patch("main.profile_manager.refresh_connection")
    def test_connect_to_profile_failure(self, mock_connect):
        """Test connect to profile endpoint failure"""
        mock_connect.return_value = (False, "Connection failed")
        
        response = client.post("/database/profiles/test_profile/connect", json={"password": "test_pass"})
        assert response.status_code == 200  # The endpoint returns 200 even on failure

    @patch("main.profile_manager.delete_profile")
    def test_delete_profile_success(self, mock_delete):
        """Test delete profile endpoint success"""
        mock_delete.return_value = (True, "Profile deleted")
        
        response = client.delete("/database/profiles/test_profile")
        assert response.status_code == 200

    @patch("main.profile_manager.delete_profile")
    def test_delete_profile_failure(self, mock_delete):
        """Test delete profile endpoint failure"""
        mock_delete.return_value = (False, "Profile not found")
        
        response = client.delete("/database/profiles/test_profile")
        assert response.status_code == 400

    @patch("main.profile_manager.get_connection")
    @patch("main.PostgreSQLAnalyzer.get_database_info")
    def test_get_profile_info_success(self, mock_get_info, mock_get_connection):
        """Test get profile info endpoint success"""
        mock_connection = MagicMock()
        mock_connection.get_connection_url.return_value = "postgresql://test:test@localhost:5432/testdb"
        mock_get_connection.return_value = mock_connection
        mock_get_info.return_value = {
            "version": "PostgreSQL 15.0",
            "database_size": "10 MB"
        }
        
        response = client.get("/database/profiles/test_profile/info")
        assert response.status_code == 200

    @patch("main.profile_manager.get_connection")
    def test_get_profile_info_failure(self, mock_get_connection):
        """Test get profile info endpoint failure"""
        mock_get_connection.return_value = None  # Profile not found
        
        response = client.get("/database/profiles/test_profile/info")
        assert response.status_code == 404

    def test_create_default_profiles(self):
        """Test create default profiles endpoint"""
        with patch("main.create_default_database_profiles", new_callable=AsyncMock) as mock_create:
            response = client.post("/database/profiles/default")
            assert response.status_code == 200


class TestValidationErrors:
    def test_analyze_missing_query(self):
        """Test analyze endpoint with missing query"""
        response = client.post("/analyze", json={})
        assert response.status_code == 422  # Validation error

    def test_database_test_missing_fields(self):
        """Test database test endpoint with missing fields"""
        response = client.post("/database/test", json={"host": "localhost"})
        assert response.status_code == 422  # Validation error

    def test_models_switch_missing_model_name(self):
        """Test model switch endpoint with missing model name"""
        response = client.post("/models/switch", json={})
        assert response.status_code == 422  # Validation error
