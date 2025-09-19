"""
Comprehensive pytest tests for ExecutionPlanCache class
"""
import pytest
import json
import tempfile
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path

from execution_plan_cache import ExecutionPlanCache


class TestExecutionPlanCache:
    """Test cases for ExecutionPlanCache class"""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary cache directory for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def cache(self, temp_cache_dir):
        """Create ExecutionPlanCache instance for testing"""
        return ExecutionPlanCache(cache_dir=temp_cache_dir)

    def test_cache_initialization(self, temp_cache_dir):
        """Test ExecutionPlanCache initialization"""
        cache = ExecutionPlanCache(cache_dir=temp_cache_dir)
        
        assert cache._cache == {}
        assert cache._cache_max_size == 1000
        assert cache._cache_dir == temp_cache_dir
        assert cache._cache_file == temp_cache_dir / "execution_plans.json"

    def test_create_plan_hash(self, cache):
        """Test plan hash creation"""
        query = "SELECT * FROM users WHERE id = 1"
        database_url = "postgresql://user:pass@localhost:5432/db"
        
        hash1 = cache._create_plan_hash(query, database_url)
        hash2 = cache._create_plan_hash(query, database_url)
        
        # Same inputs should produce same hash
        assert hash1 == hash2
        assert len(hash1) == 32  # MD5 hash length
        
        # Different inputs should produce different hashes
        different_url = "postgresql://user:pass@localhost:5432/different_db"
        hash3 = cache._create_plan_hash(query, different_url)
        assert hash1 != hash3

    def test_normalize_database_url(self, cache):
        """Test database URL normalization"""
        # Test with password
        url_with_password = "postgresql://user:password@localhost:5432/db"
        normalized = cache._normalize_database_url(url_with_password)
        assert normalized == "postgresql://user:***@localhost:5432/db"
        
        # Test without password
        url_without_password = "postgresql://user@localhost:5432/db"
        normalized = cache._normalize_database_url(url_without_password)
        assert normalized == url_without_password
        
        # Test without protocol
        url_no_protocol = "user:password@localhost:5432/db"
        normalized = cache._normalize_database_url(url_no_protocol)
        assert normalized == url_no_protocol

    def test_get_plan_cache_hit(self, cache):
        """Test getting plan from cache (hit)"""
        query = "SELECT * FROM users WHERE id = 1"
        database_url = "postgresql://user:pass@localhost:5432/db"
        plan_data = {"total_cost": 100.0, "execution_time": 50.0}
        
        # Add to cache
        plan_hash = cache._create_plan_hash(query, database_url)
        cache._cache[plan_hash] = plan_data
        
        result = cache.get_plan(query, database_url)
        
        assert result == plan_data

    def test_get_plan_cache_miss(self, cache):
        """Test getting plan from cache (miss)"""
        query = "SELECT * FROM users WHERE id = 1"
        database_url = "postgresql://user:pass@localhost:5432/db"
        
        result = cache.get_plan(query, database_url)
        
        assert result is None

    def test_set_plan_success(self, cache):
        """Test setting plan in cache"""
        query = "SELECT * FROM users WHERE id = 1"
        database_url = "postgresql://user:pass@localhost:5432/db"
        plan_data = {"total_cost": 100.0, "execution_time": 50.0}
        
        cache.set_plan(query, database_url, plan_data)
        
        plan_hash = cache._create_plan_hash(query, database_url)
        assert plan_hash in cache._cache
        assert cache._cache[plan_hash] == plan_data

    def test_set_plan_cache_eviction(self, cache):
        """Test cache eviction when max size reached"""
        # Set small cache size for testing
        cache._cache_max_size = 2
        
        # Add items to fill cache
        cache.set_plan("query1", "url1", {"data": 1})
        cache.set_plan("query2", "url2", {"data": 2})
        
        # Add third item - should evict first
        cache.set_plan("query3", "url3", {"data": 3})
        
        assert len(cache._cache) == 2
        assert cache.get_plan("query1", "url1") is None
        assert cache.get_plan("query2", "url2") is not None
        assert cache.get_plan("query3", "url3") is not None

    def test_save_to_file_success(self, cache, temp_cache_dir):
        """Test successful cache saving to file"""
        # Add some data to cache
        cache._cache = {
            "hash1": {"plan": "data1"},
            "hash2": {"plan": "data2"}
        }
        
        cache._save_to_file()
        
        # Verify file was created
        assert cache._cache_file.exists()
        
        # Verify content
        with open(cache._cache_file, 'r') as f:
            saved_data = json.load(f)
        assert saved_data == cache._cache

    def test_save_to_file_error(self, cache):
        """Test cache saving with error"""
        # Mock file write to raise exception
        with patch('builtins.open', side_effect=IOError("Write error")):
            # Should not raise exception, just log error
            cache._save_to_file()

    def test_load_from_file_success(self, cache, temp_cache_dir):
        """Test successful cache loading from file"""
        # Create test data
        test_data = {
            "hash1": {"plan": "data1"},
            "hash2": {"plan": "data2"}
        }
        
        # Write to file
        with open(cache._cache_file, 'w') as f:
            json.dump(test_data, f)
        
        # Load from file
        cache._load_from_file()
        
        assert cache._cache == test_data

    def test_load_from_file_not_found(self, cache):
        """Test cache loading when file doesn't exist"""
        cache._load_from_file()
        assert cache._cache == {}

    def test_load_from_file_invalid_json(self, cache, temp_cache_dir):
        """Test cache loading with invalid JSON"""
        # Create invalid JSON file
        with open(cache._cache_file, 'w') as f:
            f.write("invalid json content")
        
        cache._load_from_file()
        assert cache._cache == {}

    def test_get_cache_stats(self, cache):
        """Test cache statistics retrieval"""
        cache._cache = {
            "hash1": {"plan": "data1"},
            "hash2": {"plan": "data2"},
            "hash3": {"plan": "data3"}
        }
        
        stats = cache.get_cache_stats()
        
        assert stats["cache_size"] == 3
        assert stats["cache_max_size"] == 1000
        assert len(stats["cache_keys"]) == 3
        assert all(key.endswith("...") for key in stats["cache_keys"])
        assert str(cache._cache_file) in stats["cache_file"]

    def test_clear_cache(self, cache, temp_cache_dir):
        """Test cache clearing"""
        # Add some data
        cache._cache = {"hash1": {"plan": "data1"}}
        
        cache.clear_cache()
        
        assert cache._cache == {}
        # File should still exist but be empty
        assert cache._cache_file.exists()

    def test_has_plan(self, cache):
        """Test plan existence check"""
        query = "SELECT * FROM users WHERE id = 1"
        database_url = "postgresql://user:pass@localhost:5432/db"
        
        # Initially should not have plan
        assert not cache.has_plan(query, database_url)
        
        # Add plan
        cache.set_plan(query, database_url, {"data": "test"})
        
        # Should now have plan
        assert cache.has_plan(query, database_url)

    def test_save_cache_to_file_public(self, cache, temp_cache_dir):
        """Test public save cache to file method"""
        cache._cache = {"hash1": {"plan": "data1"}}
        
        cache.save_cache_to_file()
        
        assert cache._cache_file.exists()
        with open(cache._cache_file, 'r') as f:
            saved_data = json.load(f)
        assert saved_data == cache._cache

    def test_load_cache_from_file_public(self, cache, temp_cache_dir):
        """Test public load cache from file method"""
        test_data = {"hash1": {"plan": "data1"}}
        
        with open(cache._cache_file, 'w') as f:
            json.dump(test_data, f)
        
        result = cache.load_cache_from_file()
        
        assert result == test_data
        assert cache._cache == test_data

    def test_get_cache_data(self, cache):
        """Test getting cache data copy"""
        cache._cache = {"hash1": {"plan": "data1"}}
        
        result = cache.get_cache_data()
        
        assert result == cache._cache
        assert result is not cache._cache  # Should be a copy

    def test_load_cache_data(self, cache):
        """Test loading cache data from external source"""
        external_data = {
            "hash1": {"plan": "data1"},
            "hash2": {"plan": "data2"}
        }
        
        cache.load_cache_data(external_data)
        
        assert cache._cache == external_data

    @pytest.mark.asyncio
    async def test_precompute_execution_plans_success(self, cache):
        """Test successful execution plan precomputation"""
        # Mock database analyzer
        mock_db_analyzer = AsyncMock()
        mock_db_analyzer.database_url = "postgresql://user:pass@localhost:5432/db"
        mock_db_analyzer.analyze_query_performance = AsyncMock(return_value={
            "total_cost": 100.0,
            "execution_time": 50.0,
            "rows": 1000,
            "width": 64,
            "plan_json": {"Total Cost": 100.0}
        })
        
        test_queries = [
            {
                "name": "Test Query 1",
                "query": "SELECT * FROM users WHERE id = 1"
            },
            {
                "name": "Test Query 2",
                "query": "SELECT * FROM users WHERE id = 2"
            }
        ]
        
        result = await cache.precompute_execution_plans(mock_db_analyzer, test_queries, max_queries=2)
        
        assert result["status"] == "completed"
        assert result["processed"] == 2
        assert result["errors"] == 0
        assert result["total_queries"] == 2
        assert len(result["results"]) == 2
        assert result["cache_size"] == 2

    @pytest.mark.asyncio
    async def test_precompute_execution_plans_with_errors(self, cache):
        """Test execution plan precomputation with errors"""
        # Mock database analyzer
        mock_db_analyzer = AsyncMock()
        mock_db_analyzer.database_url = "postgresql://user:pass@localhost:5432/db"
        mock_db_analyzer.analyze_query_performance = AsyncMock(side_effect=Exception("Database error"))
        
        test_queries = [
            {
                "name": "Failing Query",
                "query": "SELECT * FROM nonexistent_table"
            }
        ]
        
        result = await cache.precompute_execution_plans(mock_db_analyzer, test_queries, max_queries=1)
        
        assert result["status"] == "completed"
        assert result["processed"] == 0
        assert result["errors"] == 1
        assert len(result["results"]) == 1
        assert result["results"][0]["status"] == "error"

    @pytest.mark.asyncio
    async def test_precompute_execution_plans_skip_cached(self, cache):
        """Test execution plan precomputation skipping cached plans"""
        # Mock database analyzer
        mock_db_analyzer = AsyncMock()
        mock_db_analyzer.database_url = "postgresql://user:pass@localhost:5432/db"
        mock_db_analyzer.analyze_query_performance = AsyncMock(return_value={
            "total_cost": 100.0,
            "execution_time": 50.0,
            "rows": 1000,
            "width": 64,
            "plan_json": {"Total Cost": 100.0}
        })
        
        test_queries = [
            {
                "name": "Test Query 1",
                "query": "SELECT * FROM users WHERE id = 1"
            },
            {
                "name": "Test Query 2",
                "query": "SELECT * FROM users WHERE id = 2"
            }
        ]
        
        # Pre-cache one query
        cache.set_plan(test_queries[0]["query"], mock_db_analyzer.database_url, {"cached": True})
        
        result = await cache.precompute_execution_plans(mock_db_analyzer, test_queries, max_queries=2)
        
        assert result["status"] == "completed"
        assert result["processed"] == 1  # Only one new query processed
        assert result["errors"] == 0

    @pytest.mark.asyncio
    async def test_precompute_for_all_database_profiles_success(self, cache):
        """Test precomputation for all database profiles"""
        # Mock profile manager
        mock_profile_manager = Mock()
        mock_profile = Mock()
        mock_profile.id = "profile1"
        mock_profile.name = "Test Profile"
        mock_profile.host = "localhost"
        mock_profile.port = 5432
        mock_profile.database = "testdb"
        mock_profile_manager.list_profiles.return_value = [mock_profile]
        
        # Mock connection
        mock_connection = Mock()
        mock_connection.get_connection_url.return_value = "postgresql://user:pass@localhost:5432/testdb"
        mock_profile_manager.get_connection.return_value = mock_connection
        
        # Mock database analyzer
        mock_db_analyzer = AsyncMock()
        mock_db_analyzer.database_url = "postgresql://user:pass@localhost:5432/testdb"
        mock_db_analyzer.test_connection = AsyncMock(return_value=True)
        mock_db_analyzer.analyze_query_performance = AsyncMock(return_value={
            "total_cost": 100.0,
            "execution_time": 50.0,
            "rows": 1000,
            "width": 64,
            "plan_json": {"Total Cost": 100.0}
        })
        
        test_queries = [
            {
                "name": "Test Query",
                "query": "SELECT * FROM users WHERE id = 1"
            }
        ]
        
        with patch('execution_plan_cache.PostgreSQLAnalyzer', return_value=mock_db_analyzer):
            result = await cache.precompute_for_all_database_profiles(
                mock_profile_manager, test_queries, max_queries_per_db=1
            )
        
        assert result["status"] == "completed"
        assert result["total_processed"] == 1
        assert result["total_errors"] == 0
        assert result["total_profiles"] == 1
        assert "Test Profile" in result["profiles"]

    @pytest.mark.asyncio
    async def test_precompute_for_all_database_profiles_no_connection(self, cache):
        """Test precomputation with no available connection"""
        # Mock profile manager
        mock_profile_manager = Mock()
        mock_profile = Mock()
        mock_profile.id = "profile1"
        mock_profile.name = "Test Profile"
        mock_profile_manager.list_profiles.return_value = [mock_profile]
        mock_profile_manager.get_connection.return_value = None
        
        test_queries = [
            {
                "name": "Test Query",
                "query": "SELECT * FROM users WHERE id = 1"
            }
        ]
        
        result = await cache.precompute_for_all_database_profiles(
            mock_profile_manager, test_queries, max_queries_per_db=1
        )
        
        assert result["status"] == "completed"
        assert result["total_processed"] == 0
        assert result["total_errors"] == 1
        assert result["profiles"]["Test Profile"]["status"] == "error"

    @pytest.mark.asyncio
    async def test_precompute_for_all_database_profiles_connection_failed(self, cache):
        """Test precomputation with connection failure"""
        # Mock profile manager
        mock_profile_manager = Mock()
        mock_profile = Mock()
        mock_profile.id = "profile1"
        mock_profile.name = "Test Profile"
        mock_profile_manager.list_profiles.return_value = [mock_profile]
        
        # Mock connection
        mock_connection = Mock()
        mock_connection.get_connection_url.return_value = "postgresql://user:pass@localhost:5432/testdb"
        mock_profile_manager.get_connection.return_value = mock_connection
        
        # Mock database analyzer with connection failure
        mock_db_analyzer = AsyncMock()
        mock_db_analyzer.test_connection = AsyncMock(return_value=False)
        
        test_queries = [
            {
                "name": "Test Query",
                "query": "SELECT * FROM users WHERE id = 1"
            }
        ]
        
        with patch('execution_plan_cache.PostgreSQLAnalyzer', return_value=mock_db_analyzer):
            result = await cache.precompute_for_all_database_profiles(
                mock_profile_manager, test_queries, max_queries_per_db=1
            )
        
        assert result["status"] == "completed"
        assert result["total_processed"] == 0
        assert result["total_errors"] == 1
        assert result["profiles"]["Test Profile"]["status"] == "error"

    def test_cache_file_creation_on_init(self, temp_cache_dir):
        """Test that cache file is created during initialization"""
        # Directory should exist
        assert temp_cache_dir.exists()
        
        # Create cache instance
        cache = ExecutionPlanCache(cache_dir=temp_cache_dir)
        
        # Cache file should exist (even if empty)
        assert cache._cache_file.exists()

    def test_cache_persistence_across_instances(self, temp_cache_dir):
        """Test that cache persists across different instances"""
        # Create first instance and add data
        cache1 = ExecutionPlanCache(cache_dir=temp_cache_dir)
        cache1.set_plan("SELECT 1", "postgresql://test", {"data": "test"})
        
        # Create second instance and verify data is loaded
        cache2 = ExecutionPlanCache(cache_dir=temp_cache_dir)
        result = cache2.get_plan("SELECT 1", "postgresql://test")
        
        assert result == {"data": "test"}
