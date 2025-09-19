"""
Comprehensive pytest tests for CacheWarmupService class
"""
import pytest
import json
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path
import tempfile
import os

from cache_warmup import CacheWarmupService
from config import LLMModel


class TestCacheWarmupService:
    """Test cases for CacheWarmupService class"""

    @pytest.fixture
    def mock_llm_model(self):
        """Mock LLM model for testing"""
        return LLMModel(
            name="Test Model",
            api_key="test_key",
            model="test-model",
            url="https://test.com"
        )

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing"""
        with patch('cache_warmup.settings') as mock_settings:
            mock_settings.get_model_by_index.return_value = self.mock_llm_model()
            mock_settings.get_available_models.return_value = [self.mock_llm_model()]
            yield mock_settings

    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary cache directory for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def temp_test_queries_file(self):
        """Create temporary test queries file for testing"""
        test_queries = {
            "test_queries": [
                {
                    "name": "Test Query 1",
                    "query": "SELECT * FROM users WHERE id = 1",
                    "description": "Simple test query"
                },
                {
                    "name": "Test Query 2", 
                    "query": "SELECT u.name, o.total FROM users u JOIN orders o ON u.id = o.user_id",
                    "description": "JOIN test query"
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_queries, f)
            temp_file = Path(f.name)
        
        yield temp_file
        
        # Cleanup
        if temp_file.exists():
            temp_file.unlink()

    @pytest.fixture
    def cache_warmup_service(self, mock_settings, temp_cache_dir, temp_test_queries_file):
        """Create CacheWarmupService instance for testing"""
        with patch('cache_warmup.PostgreSQLAnalyzer') as mock_db, \
             patch('cache_warmup.LLMAnalyzer') as mock_llm, \
             patch('cache_warmup.ExecutionPlanCache') as mock_cache:
            
            # Mock the path resolution to use our temp files
            with patch('cache_warmup.Path') as mock_path:
                # Mock __file__ to point to our temp directory
                mock_path.return_value.parent.parent = temp_cache_dir
                mock_path.return_value.parent = temp_cache_dir
                
                # Mock the test queries file path
                def mock_exists(path):
                    if str(path).endswith('test_queries.json'):
                        return temp_test_queries_file.exists()
                    return temp_cache_dir.exists()
                
                mock_path.return_value.exists = mock_exists
                mock_path.return_value = temp_test_queries_file
                
                service = CacheWarmupService()
                service.test_queries_file = temp_test_queries_file
                service.cache_dir = temp_cache_dir
                
                return service

    @pytest.mark.asyncio
    async def test_load_test_queries_success(self, cache_warmup_service, temp_test_queries_file):
        """Test successful loading of test queries"""
        queries = await cache_warmup_service.load_test_queries()
        
        assert len(queries) == 2
        assert queries[0]["name"] == "Test Query 1"
        assert queries[0]["query"] == "SELECT * FROM users WHERE id = 1"
        assert queries[1]["name"] == "Test Query 2"

    @pytest.mark.asyncio
    async def test_load_test_queries_file_not_found(self, cache_warmup_service):
        """Test loading test queries when file doesn't exist"""
        cache_warmup_service.test_queries_file = None
        queries = await cache_warmup_service.load_test_queries()
        
        assert queries == []

    @pytest.mark.asyncio
    async def test_load_test_queries_invalid_json(self, cache_warmup_service, temp_cache_dir):
        """Test loading test queries with invalid JSON"""
        # Create invalid JSON file
        invalid_file = temp_cache_dir / "invalid.json"
        with open(invalid_file, 'w') as f:
            f.write("invalid json content")
        
        cache_warmup_service.test_queries_file = invalid_file
        queries = await cache_warmup_service.load_test_queries()
        
        assert queries == []

    def test_get_cache_file_path(self, cache_warmup_service):
        """Test cache file path generation"""
        model_name = "test-model"
        cache_path = cache_warmup_service._get_cache_file_path(model_name)
        
        assert cache_path.parent == cache_warmup_service.cache_dir
        assert cache_path.name.startswith("cache_")
        assert cache_path.suffix == ".json"

    def test_create_cache_key(self, cache_warmup_service):
        """Test cache key creation"""
        model_name = "test-model"
        query = "SELECT * FROM users"
        execution_plan = {
            "Total Cost": 100.0,
            "Actual Total Time": 50.0,
            "Actual Rows": 1000,
            "Node Type": "Seq Scan"
        }
        
        cache_key = cache_warmup_service._create_cache_key(model_name, query, execution_plan)
        
        assert isinstance(cache_key, str)
        assert len(cache_key) == 32  # MD5 hash length

    @pytest.mark.asyncio
    async def test_save_cache_to_file_success(self, cache_warmup_service, temp_cache_dir):
        """Test successful cache saving to file"""
        model_name = "test-model"
        cache_data = {
            "key1": {"result": "test1"},
            "key2": {"result": "test2"}
        }
        
        result = await cache_warmup_service.save_cache_to_file(model_name, cache_data)
        
        assert result is True
        
        # Verify file was created
        cache_file = cache_warmup_service._get_cache_file_path(model_name)
        assert cache_file.exists()
        
        # Verify content
        with open(cache_file, 'r') as f:
            saved_data = json.load(f)
        assert saved_data == cache_data

    @pytest.mark.asyncio
    async def test_save_cache_to_file_error(self, cache_warmup_service):
        """Test cache saving with error"""
        model_name = "test-model"
        cache_data = {"key": "value"}
        
        # Mock file write to raise exception
        with patch('builtins.open', side_effect=IOError("Write error")):
            result = await cache_warmup_service.save_cache_to_file(model_name, cache_data)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_load_cache_from_file_success(self, cache_warmup_service, temp_cache_dir):
        """Test successful cache loading from file"""
        model_name = "test-model"
        cache_data = {
            "key1": {"result": "test1"},
            "key2": {"result": "test2"}
        }
        
        # First save cache
        await cache_warmup_service.save_cache_to_file(model_name, cache_data)
        
        # Then load it
        loaded_data = await cache_warmup_service.load_cache_from_file(model_name)
        
        assert loaded_data == cache_data

    @pytest.mark.asyncio
    async def test_load_cache_from_file_not_found(self, cache_warmup_service):
        """Test cache loading when file doesn't exist"""
        model_name = "nonexistent-model"
        loaded_data = await cache_warmup_service.load_cache_from_file(model_name)
        
        assert loaded_data == {}

    @pytest.mark.asyncio
    async def test_load_cache_from_file_error(self, cache_warmup_service, temp_cache_dir):
        """Test cache loading with error"""
        model_name = "test-model"
        cache_file = cache_warmup_service._get_cache_file_path(model_name)
        
        # Create invalid JSON file
        with open(cache_file, 'w') as f:
            f.write("invalid json")
        
        loaded_data = await cache_warmup_service.load_cache_from_file(model_name)
        
        assert loaded_data == {}

    @pytest.mark.asyncio
    async def test_warmup_cache_success(self, cache_warmup_service):
        """Test successful cache warmup"""
        with patch.object(cache_warmup_service, 'load_test_queries') as mock_load, \
             patch.object(cache_warmup_service.db_analyzer, 'analyze_query_performance') as mock_db, \
             patch.object(cache_warmup_service.llm_analyzer, 'analyze_query_with_llm') as mock_llm, \
             patch.object(cache_warmup_service.execution_plan_cache, 'get_plan') as mock_get_plan, \
             patch.object(cache_warmup_service.execution_plan_cache, 'set_plan') as mock_set_plan, \
             patch.object(cache_warmup_service.llm_analyzer, 'get_cache_stats') as mock_stats:
            
            # Setup mocks
            mock_load.return_value = [
                {
                    "name": "Test Query",
                    "query": "SELECT * FROM users WHERE id = 1"
                }
            ]
            
            mock_get_plan.return_value = None  # No cached plan
            mock_db.return_value = {
                "total_cost": 100.0,
                "execution_time": 50.0,
                "rows": 1000,
                "width": 64,
                "plan_json": {"Total Cost": 100.0}
            }
            
            mock_llm.return_value = {
                "rewritten_query": None,
                "resource_metrics": {"cpu_usage": 50.0},
                "recommendations": [],
                "warnings": []
            }
            
            mock_stats.return_value = {"size": 0}
            
            result = await cache_warmup_service.warmup_cache(max_queries=1)
            
            assert result["status"] == "completed"
            assert result["processed"] == 1
            assert result["errors"] == 0
            assert result["total_queries"] == 1
            assert len(result["results"]) == 1

    @pytest.mark.asyncio
    async def test_warmup_cache_no_queries(self, cache_warmup_service):
        """Test cache warmup with no test queries"""
        with patch.object(cache_warmup_service, 'load_test_queries') as mock_load:
            mock_load.return_value = []
            
            result = await cache_warmup_service.warmup_cache()
            
            assert result["status"] == "no_queries"
            assert result["processed"] == 0
            assert result["errors"] == 0

    @pytest.mark.asyncio
    async def test_warmup_cache_with_errors(self, cache_warmup_service):
        """Test cache warmup with errors"""
        with patch.object(cache_warmup_service, 'load_test_queries') as mock_load, \
             patch.object(cache_warmup_service.db_analyzer, 'analyze_query_performance') as mock_db, \
             patch.object(cache_warmup_service.execution_plan_cache, 'get_plan') as mock_get_plan:
            
            mock_load.return_value = [
                {
                    "name": "Failing Query",
                    "query": "SELECT * FROM nonexistent_table"
                }
            ]
            
            mock_get_plan.return_value = None
            mock_db.side_effect = Exception("Database error")
            
            result = await cache_warmup_service.warmup_cache(max_queries=1)
            
            assert result["status"] == "completed"
            assert result["processed"] == 0
            assert result["errors"] == 1
            assert len(result["results"]) == 1
            assert result["results"][0]["status"] == "error"

    @pytest.mark.asyncio
    async def test_warmup_cache_for_all_models_success(self, cache_warmup_service):
        """Test cache warmup for all models"""
        with patch.object(cache_warmup_service, 'load_test_queries') as mock_load, \
             patch.object(cache_warmup_service, 'load_cache_from_file') as mock_load_cache, \
             patch.object(cache_warmup_service, 'save_cache_to_file') as mock_save_cache, \
             patch('cache_warmup.LLMAnalyzer') as mock_llm_class, \
             patch.object(cache_warmup_service.db_analyzer, 'analyze_query_performance') as mock_db, \
             patch.object(cache_warmup_service.execution_plan_cache, 'get_plan') as mock_get_plan, \
             patch.object(cache_warmup_service.execution_plan_cache, 'set_plan') as mock_set_plan:
            
            # Setup mocks
            mock_load.return_value = [
                {
                    "name": "Test Query",
                    "query": "SELECT * FROM users WHERE id = 1"
                }
            ]
            
            mock_load_cache.return_value = {}
            mock_save_cache.return_value = True
            
            mock_get_plan.return_value = None
            mock_db.return_value = {
                "total_cost": 100.0,
                "execution_time": 50.0,
                "rows": 1000,
                "width": 64,
                "plan_json": {"Total Cost": 100.0}
            }
            
            # Mock LLM analyzer instance
            mock_llm_instance = AsyncMock()
            mock_llm_instance._cache = {}
            mock_llm_instance.analyze_query_with_llm.return_value = {
                "rewritten_query": None,
                "resource_metrics": {"cpu_usage": 50.0},
                "recommendations": [],
                "warnings": []
            }
            mock_llm_class.return_value = mock_llm_instance
            
            result = await cache_warmup_service.warmup_cache_for_all_models(max_queries=1)
            
            assert result["status"] == "completed"
            assert result["total_processed"] == 1
            assert result["total_errors"] == 0
            assert "models" in result

    @pytest.mark.asyncio
    async def test_warmup_new_examples_success(self, cache_warmup_service):
        """Test warmup of new examples"""
        with patch.object(cache_warmup_service, 'load_test_queries') as mock_load, \
             patch.object(cache_warmup_service.llm_analyzer, 'get_cache_stats') as mock_stats, \
             patch.object(cache_warmup_service.db_analyzer, 'analyze_query_performance') as mock_db, \
             patch.object(cache_warmup_service.llm_analyzer, 'analyze_query_with_llm') as mock_llm:
            
            mock_load.return_value = [
                {
                    "name": "Test Query 1",
                    "query": "SELECT * FROM users WHERE id = 1"
                },
                {
                    "name": "Test Query 2",
                    "query": "SELECT * FROM users WHERE id = 2"
                }
            ]
            
            # Simulate cache with 1 entry
            mock_stats.return_value = {"size": 1}
            
            mock_db.return_value = {
                "total_cost": 100.0,
                "execution_time": 50.0,
                "rows": 1000,
                "width": 64,
                "plan_json": {"Total Cost": 100.0}
            }
            
            mock_llm.return_value = {
                "rewritten_query": None,
                "resource_metrics": {"cpu_usage": 50.0},
                "recommendations": [],
                "warnings": []
            }
            
            result = await cache_warmup_service.warmup_new_examples(max_queries=1)
            
            assert result["status"] == "completed"
            assert result["processed"] == 1
            assert result["errors"] == 0

    @pytest.mark.asyncio
    async def test_warmup_new_examples_empty_cache(self, cache_warmup_service):
        """Test warmup new examples when cache is empty"""
        with patch.object(cache_warmup_service, 'load_test_queries') as mock_load, \
             patch.object(cache_warmup_service.llm_analyzer, 'get_cache_stats') as mock_stats, \
             patch.object(cache_warmup_service, 'warmup_cache') as mock_warmup:
            
            mock_load.return_value = [
                {
                    "name": "Test Query",
                    "query": "SELECT * FROM users WHERE id = 1"
                }
            ]
            
            # Simulate empty cache
            mock_stats.return_value = {"size": 0}
            mock_warmup.return_value = {"status": "completed", "processed": 1}
            
            result = await cache_warmup_service.warmup_new_examples()
            
            # Should call regular warmup_cache
            mock_warmup.assert_called_once()

    @pytest.mark.asyncio
    async def test_test_cache_hit_success(self, cache_warmup_service):
        """Test cache hit testing"""
        with patch.object(cache_warmup_service.db_analyzer, 'analyze_query_performance') as mock_db, \
             patch.object(cache_warmup_service.llm_analyzer, 'analyze_query_with_llm') as mock_llm, \
             patch.object(cache_warmup_service.llm_analyzer, 'get_cache_stats') as mock_stats:
            
            mock_db.return_value = {
                "total_cost": 100.0,
                "execution_time": 50.0,
                "rows": 1000,
                "width": 64,
                "plan_json": {"Total Cost": 100.0}
            }
            
            mock_llm.return_value = {
                "rewritten_query": None,
                "resource_metrics": {"cpu_usage": 50.0},
                "recommendations": [],
                "warnings": []
            }
            
            mock_stats.return_value = {"size": 5}
            
            result = await cache_warmup_service.test_cache_hit("SELECT * FROM users WHERE id = 1")
            
            assert result["status"] == "success"
            assert "execution_time" in result
            assert "cache_stats" in result

    @pytest.mark.asyncio
    async def test_test_cache_hit_error(self, cache_warmup_service):
        """Test cache hit testing with error"""
        with patch.object(cache_warmup_service.db_analyzer, 'analyze_query_performance') as mock_db:
            mock_db.side_effect = Exception("Database error")
            
            result = await cache_warmup_service.test_cache_hit("SELECT * FROM nonexistent_table")
            
            assert result["status"] == "error"
            assert "error" in result

    def test_cache_warmup_service_initialization(self, mock_settings, temp_cache_dir):
        """Test CacheWarmupService initialization"""
        with patch('cache_warmup.PostgreSQLAnalyzer') as mock_db, \
             patch('cache_warmup.LLMAnalyzer') as mock_llm, \
             patch('cache_warmup.ExecutionPlanCache') as mock_cache:
            
            service = CacheWarmupService()
            
            # Verify initialization
            assert service.db_analyzer is not None
            assert service.llm_analyzer is not None
            assert service.execution_plan_cache is not None
            assert service.cache_dir is not None

    def test_cache_warmup_service_initialization_no_model(self):
        """Test CacheWarmupService initialization with no available model"""
        with patch('cache_warmup.settings') as mock_settings, \
             patch('cache_warmup.PostgreSQLAnalyzer') as mock_db:
            
            mock_settings.get_model_by_index.return_value = None
            
            with pytest.raises(ValueError, match="No LLM model available for warmup"):
                CacheWarmupService()
