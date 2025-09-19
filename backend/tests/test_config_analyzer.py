"""
Comprehensive pytest tests for PostgreSQLConfigAnalyzer class
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import asyncpg

from config_analyzer import PostgreSQLConfigAnalyzer


class TestPostgreSQLConfigAnalyzer:
    """Test cases for PostgreSQLConfigAnalyzer class"""

    @pytest.fixture
    def analyzer(self):
        """Create PostgreSQLConfigAnalyzer instance for testing"""
        return PostgreSQLConfigAnalyzer("postgresql://test:test@localhost:5432/testdb")

    def test_analyzer_initialization_with_url(self):
        """Test analyzer initialization with custom URL"""
        custom_url = "postgresql://user:pass@host:5432/db"
        analyzer = PostgreSQLConfigAnalyzer(custom_url)
        assert analyzer.database_url == custom_url

    def test_analyzer_initialization_without_url(self):
        """Test analyzer initialization without URL (uses default)"""
        with patch('config_analyzer.settings') as mock_settings:
            mock_settings.database_url = "postgresql://default:default@localhost:5432/default"
            analyzer = PostgreSQLConfigAnalyzer()
            assert analyzer.database_url == mock_settings.database_url

    @pytest.mark.asyncio
    async def test_get_configuration_analysis_success(self, analyzer):
        """Test successful configuration analysis"""
        mock_connection = AsyncMock()
        
        # Mock settings data
        mock_connection.fetch.return_value = [
            {
                "name": "shared_buffers",
                "setting": "128MB",
                "unit": "8kB",
                "context": "postmaster",
                "short_desc": "Sets the number of shared memory buffers used by the server"
            },
            {
                "name": "work_mem",
                "setting": "4MB",
                "unit": "kB",
                "context": "user",
                "short_desc": "Sets the maximum memory to be used by a query operation"
            }
        ]
        
        # Mock system info queries
        mock_connection.fetchrow.side_effect = [
            {"version": "PostgreSQL 15.0"},
            {"size": "10 MB"},
            {"total": 5},
            {"active": 2},
            {"idle": 3},
            {"max_conn": 100},
            {"shared_buffers": "128MB"},
            {"work_mem": "4MB"}
        ]
        
        # Mock statistics queries
        mock_connection.fetch.side_effect = [
            [{"active_connections": 5, "committed_transactions": 1000, "rolled_back_transactions": 50, "blocks_read": 100, "blocks_hit": 900, "tuples_returned": 5000, "tuples_fetched": 4500, "tuples_inserted": 100, "tuples_updated": 50, "tuples_deleted": 10}],  # database_stats
            [{"schemaname": "public", "tablename": "users", "inserts": 100, "updates": 50, "deletes": 10, "live_tuples": 1000, "dead_tuples": 50, "last_vacuum": None, "last_autovacuum": "2023-01-01 10:00:00", "last_analyze": None, "last_autoanalyze": "2023-01-01 10:00:00"}],  # table_stats
            [{"schemaname": "public", "tablename": "users", "indexname": "idx_users_id", "index_tuples_read": 1000, "index_tuples_fetched": 950, "index_scans": 100}],  # index_stats
            [{"state": "active", "count": 2}, {"state": "idle", "count": 3}]  # connection_stats
        ]
        
        with patch('asyncpg.connect', return_value=mock_connection):
            result = await analyzer.get_configuration_analysis()
        
        assert "settings" in result
        assert "system_info" in result
        assert "statistics" in result
        assert "analysis" in result
        assert "recommendations" in result
        
        # Check settings
        assert "shared_buffers" in result["settings"]
        assert result["settings"]["shared_buffers"]["value"] == "128MB"
        assert "work_mem" in result["settings"]
        assert result["settings"]["work_mem"]["value"] == "4MB"
        
        # Check system info
        assert result["system_info"]["version"] == "PostgreSQL 15.0"
        assert result["system_info"]["database_size"] == "10 MB"
        assert result["system_info"]["total_connections"] == 5
        assert result["system_info"]["active_connections"] == 2
        assert result["system_info"]["idle_connections"] == 3
        assert result["system_info"]["max_connections"] == 100
        
        # Check statistics
        assert "database_stats" in result["statistics"]
        assert "table_stats" in result["statistics"]
        assert "index_stats" in result["statistics"]
        assert "connection_stats" in result["statistics"]
        
        # Check analysis
        assert "memory_usage" in result["analysis"]
        assert "connection_usage" in result["analysis"]
        assert "performance_indicators" in result["analysis"]
        assert "maintenance_issues" in result["analysis"]
        assert "overall_health" in result["analysis"]

    @pytest.mark.asyncio
    async def test_get_configuration_analysis_error(self, analyzer):
        """Test configuration analysis with error"""
        with patch('asyncpg.connect', side_effect=Exception("Connection error")):
            with pytest.raises(Exception, match="Connection error"):
                await analyzer.get_configuration_analysis()

    @pytest.mark.asyncio
    async def test_get_settings_success(self, analyzer):
        """Test successful settings retrieval"""
        mock_connection = AsyncMock()
        mock_connection.fetch.return_value = [
            {
                "name": "shared_buffers",
                "setting": "128MB",
                "unit": "8kB",
                "context": "postmaster",
                "short_desc": "Sets the number of shared memory buffers"
            }
        ]
        
        result = await analyzer._get_settings(mock_connection)
        
        assert "shared_buffers" in result
        assert result["shared_buffers"]["value"] == "128MB"
        assert result["shared_buffers"]["unit"] == "8kB"
        assert result["shared_buffers"]["context"] == "postmaster"
        assert "Sets the number of shared memory buffers" in result["shared_buffers"]["description"]

    @pytest.mark.asyncio
    async def test_get_system_info_success(self, analyzer):
        """Test successful system info retrieval"""
        mock_connection = AsyncMock()
        mock_connection.fetchrow.side_effect = [
            {"version": "PostgreSQL 15.0"},
            {"size": "10 MB"},
            {"total": 5},
            {"active": 2},
            {"idle": 3},
            {"max_conn": 100},
            {"shared_buffers": "128MB"},
            {"work_mem": "4MB"}
        ]
        
        result = await analyzer._get_system_info(mock_connection)
        
        assert result["version"] == "PostgreSQL 15.0"
        assert result["database_size"] == "10 MB"
        assert result["total_connections"] == 5
        assert result["active_connections"] == 2
        assert result["idle_connections"] == 3
        assert result["max_connections"] == 100
        assert result["shared_buffers"] == "128MB"
        assert result["work_mem"] == "4MB"

    @pytest.mark.asyncio
    async def test_get_system_info_with_errors(self, analyzer):
        """Test system info retrieval with some query errors"""
        mock_connection = AsyncMock()
        mock_connection.fetchrow.side_effect = [
            {"version": "PostgreSQL 15.0"},
            Exception("Query error"),  # database_size query fails
            {"total": 5},
            {"active": 2},
            {"idle": 3},
            {"max_conn": 100},
            {"shared_buffers": "128MB"},
            {"work_mem": "4MB"}
        ]
        
        result = await analyzer._get_system_info(mock_connection)
        
        assert result["version"] == "PostgreSQL 15.0"
        assert result["database_size"] is None  # Failed query
        assert result["total_connections"] == 5
        assert result["active_connections"] == 2

    @pytest.mark.asyncio
    async def test_get_statistics_success(self, analyzer):
        """Test successful statistics retrieval"""
        mock_connection = AsyncMock()
        
        # Mock database_stats query (fetchrow)
        mock_connection.fetchrow.return_value = {
            "active_connections": 5,
            "committed_transactions": 1000,
            "rolled_back_transactions": 50,
            "blocks_read": 100,
            "blocks_hit": 900,
            "tuples_returned": 5000,
            "tuples_fetched": 4500,
            "tuples_inserted": 100,
            "tuples_updated": 50,
            "tuples_deleted": 10
        }
        
        # Mock other queries (fetch)
        mock_connection.fetch.side_effect = [
            [{"schemaname": "public", "tablename": "users", "inserts": 100, "updates": 50, "deletes": 10, "live_tuples": 1000, "dead_tuples": 50, "last_vacuum": None, "last_autovacuum": "2023-01-01 10:00:00", "last_analyze": None, "last_autoanalyze": "2023-01-01 10:00:00"}],  # table_stats
            [{"schemaname": "public", "tablename": "users", "indexname": "idx_users_id", "index_tuples_read": 1000, "index_tuples_fetched": 950, "index_scans": 100}],  # index_stats
            [{"state": "active", "count": 2}, {"state": "idle", "count": 3}]  # connection_stats
        ]
        
        result = await analyzer._get_statistics(mock_connection)
        
        assert "database_stats" in result
        assert "table_stats" in result
        assert "index_stats" in result
        assert "connection_stats" in result
        
        # Check database_stats
        assert result["database_stats"]["active_connections"] == 5
        assert result["database_stats"]["committed_transactions"] == 1000
        assert result["database_stats"]["blocks_hit"] == 900
        
        # Check table_stats
        assert len(result["table_stats"]) == 1
        assert result["table_stats"][0]["tablename"] == "users"
        assert result["table_stats"][0]["live_tuples"] == 1000
        
        # Check index_stats
        assert len(result["index_stats"]) == 1
        assert result["index_stats"][0]["indexname"] == "idx_users_id"
        assert result["index_stats"][0]["index_scans"] == 100
        
        # Check connection_stats
        assert len(result["connection_stats"]) == 2
        assert result["connection_stats"][0]["state"] == "active"
        assert result["connection_stats"][0]["count"] == 2

    @pytest.mark.asyncio
    async def test_get_statistics_with_errors(self, analyzer):
        """Test statistics retrieval with some query errors"""
        mock_connection = AsyncMock()
        mock_connection.fetchrow.side_effect = Exception("Database stats error")
        mock_connection.fetch.side_effect = [
            [],  # table_stats (empty)
            Exception("Index stats error"),  # index_stats fails
            [{"state": "active", "count": 2}]  # connection_stats
        ]
        
        result = await analyzer._get_statistics(mock_connection)
        
        assert result["database_stats"] == {}  # Failed query
        assert result["table_stats"] == []  # Empty result
        assert result["index_stats"] == []  # Failed query
        assert len(result["connection_stats"]) == 1  # Successful query

    def test_analyze_configuration_good_health(self, analyzer):
        """Test configuration analysis with good health"""
        settings = {
            "shared_buffers": {"value": "256MB"},
            "work_mem": {"value": "8MB"}
        }
        
        system_info = {
            "active_connections": 5,
            "max_connections": 100
        }
        
        stats = {
            "database_stats": {
                "blocks_hit": 900,
                "blocks_read": 100,
                "committed_transactions": 1000,
                "rolled_back_transactions": 50
            },
            "table_stats": []
        }
        
        result = analyzer._analyze_configuration(settings, system_info, stats)
        
        assert result["overall_health"] == "good"
        assert result["total_issues"] == 0
        assert "memory_usage" in result
        assert "connection_usage" in result
        assert "performance_indicators" in result
        assert "maintenance_issues" in result

    def test_analyze_configuration_poor_health(self, analyzer):
        """Test configuration analysis with poor health"""
        settings = {
            "shared_buffers": {"value": "64MB"},  # Too small
            "work_mem": {"value": "1MB"}  # Too small
        }
        
        system_info = {
            "active_connections": 90,  # High usage
            "max_connections": 100
        }
        
        stats = {
            "database_stats": {
                "blocks_hit": 100,  # Low hit ratio
                "blocks_read": 900,
                "committed_transactions": 100,
                "rolled_back_transactions": 50  # High rollback ratio
            },
            "table_stats": [
                {
                    "tablename": "users",
                    "live_tuples": 1000,
                    "dead_tuples": 500  # High dead tuple ratio
                }
            ]
        }
        
        result = analyzer._analyze_configuration(settings, system_info, stats)
        
        assert result["overall_health"] == "poor"
        assert result["total_issues"] > 5
        assert len(result["issues"]) > 5

    def test_analyze_memory_settings_good(self, analyzer):
        """Test memory settings analysis with good values"""
        settings = {
            "shared_buffers": {"value": "256MB"},
            "work_mem": {"value": "8MB"}
        }
        
        system_info = {}
        
        result = analyzer._analyze_memory_settings(settings, system_info)
        
        assert result["status"] == "good"
        assert len(result["issues"]) == 0
        assert len(result["recommendations"]) == 0

    def test_analyze_memory_settings_issues(self, analyzer):
        """Test memory settings analysis with issues"""
        settings = {
            "shared_buffers": {"value": "64MB"},  # Too small
            "work_mem": {"value": "1MB"}  # Too small
        }
        
        system_info = {}
        
        result = analyzer._analyze_memory_settings(settings, system_info)
        
        assert result["status"] == "needs_attention"
        assert len(result["issues"]) > 0
        assert len(result["recommendations"]) > 0
        assert any("shared_buffers слишком мал" in issue for issue in result["issues"])
        assert any("work_mem слишком мал" in issue for issue in result["issues"])

    def test_analyze_memory_settings_work_mem_too_large(self, analyzer):
        """Test memory settings analysis with work_mem too large"""
        settings = {
            "shared_buffers": {"value": "256MB"},
            "work_mem": {"value": "128MB"}  # Too large
        }
        
        system_info = {}
        
        result = analyzer._analyze_memory_settings(settings, system_info)
        
        assert result["status"] == "needs_attention"
        assert any("work_mem слишком велик" in issue for issue in result["issues"])
        assert any("Уменьшите work_mem" in rec for rec in result["recommendations"])

    def test_analyze_connection_usage_good(self, analyzer):
        """Test connection usage analysis with good usage"""
        system_info = {
            "active_connections": 20,
            "max_connections": 100
        }
        
        result = analyzer._analyze_connection_usage(system_info)
        
        assert result["status"] == "good"
        assert result["usage_percentage"] == 20.0
        assert len(result["issues"]) == 0

    def test_analyze_connection_usage_high(self, analyzer):
        """Test connection usage analysis with high usage"""
        system_info = {
            "active_connections": 85,
            "max_connections": 100
        }
        
        result = analyzer._analyze_connection_usage(system_info)
        
        assert result["status"] == "needs_attention"
        assert result["usage_percentage"] == 85.0
        assert len(result["issues"]) == 1
        assert "Высокое использование подключений: 85.0%" in result["issues"][0]

    def test_analyze_connection_usage_medium(self, analyzer):
        """Test connection usage analysis with medium usage"""
        system_info = {
            "active_connections": 65,
            "max_connections": 100
        }
        
        result = analyzer._analyze_connection_usage(system_info)
        
        assert result["status"] == "needs_attention"
        assert result["usage_percentage"] == 65.0
        assert len(result["issues"]) == 1
        assert "Среднее использование подключений: 65.0%" in result["issues"][0]

    def test_analyze_connection_usage_no_max_connections(self, analyzer):
        """Test connection usage analysis with no max_connections"""
        system_info = {
            "active_connections": 50,
            "max_connections": 0
        }
        
        result = analyzer._analyze_connection_usage(system_info)
        
        assert result["status"] == "good"
        assert result["usage_percentage"] == 0
        assert len(result["issues"]) == 0

    def test_analyze_performance_indicators_good(self, analyzer):
        """Test performance indicators analysis with good values"""
        stats = {
            "database_stats": {
                "blocks_hit": 900,
                "blocks_read": 100,
                "committed_transactions": 1000,
                "rolled_back_transactions": 50
            }
        }
        
        result = analyzer._analyze_performance_indicators(stats)
        
        assert result["status"] == "good"
        assert result["hit_ratio"] == 90.0
        assert result["rollback_ratio"] == 4.76  # 50 / (1000 + 50) * 100
        assert len(result["issues"]) == 0

    def test_analyze_performance_indicators_low_hit_ratio(self, analyzer):
        """Test performance indicators analysis with low hit ratio"""
        stats = {
            "database_stats": {
                "blocks_hit": 100,
                "blocks_read": 900,
                "committed_transactions": 1000,
                "rolled_back_transactions": 50
            }
        }
        
        result = analyzer._analyze_performance_indicators(stats)
        
        assert result["status"] == "needs_attention"
        assert result["hit_ratio"] == 10.0
        assert len(result["issues"]) == 1
        assert "Низкий hit ratio: 10.0%" in result["issues"][0]

    def test_analyze_performance_indicators_high_rollback_ratio(self, analyzer):
        """Test performance indicators analysis with high rollback ratio"""
        stats = {
            "database_stats": {
                "blocks_hit": 900,
                "blocks_read": 100,
                "committed_transactions": 100,
                "rolled_back_transactions": 50
            }
        }
        
        result = analyzer._analyze_performance_indicators(stats)
        
        assert result["status"] == "needs_attention"
        assert result["rollback_ratio"] == 33.33  # 50 / (100 + 50) * 100
        assert len(result["issues"]) == 1
        assert "Высокий процент роллбеков: 33.3%" in result["issues"][0]

    def test_analyze_performance_indicators_no_data(self, analyzer):
        """Test performance indicators analysis with no data"""
        stats = {
            "database_stats": {}
        }
        
        result = analyzer._analyze_performance_indicators(stats)
        
        assert result["status"] == "good"
        assert result["hit_ratio"] == 0
        assert result["rollback_ratio"] == 0
        assert len(result["issues"]) == 0

    def test_analyze_maintenance_issues_good(self, analyzer):
        """Test maintenance issues analysis with good values"""
        stats = {
            "table_stats": [
                {
                    "tablename": "users",
                    "live_tuples": 1000,
                    "dead_tuples": 50
                }
            ]
        }
        
        result = analyzer._analyze_maintenance_issues(stats)
        
        assert result["status"] == "good"
        assert len(result["issues"]) == 0

    def test_analyze_maintenance_issues_high_dead_tuples(self, analyzer):
        """Test maintenance issues analysis with high dead tuples"""
        stats = {
            "table_stats": [
                {
                    "tablename": "users",
                    "live_tuples": 1000,
                    "dead_tuples": 300  # 30% dead tuples
                }
            ]
        }
        
        result = analyzer._analyze_maintenance_issues(stats)
        
        assert result["status"] == "needs_attention"
        assert len(result["issues"]) == 1
        assert "Высокий процент мертвых кортежей в users: 30.0%" in result["issues"][0]
        assert "Запустите VACUUM для таблицы users" in result["recommendations"][0]

    def test_analyze_maintenance_issues_no_live_tuples(self, analyzer):
        """Test maintenance issues analysis with no live tuples"""
        stats = {
            "table_stats": [
                {
                    "tablename": "empty_table",
                    "live_tuples": 0,
                    "dead_tuples": 100
                }
            ]
        }
        
        result = analyzer._analyze_maintenance_issues(stats)
        
        assert result["status"] == "good"
        assert len(result["issues"]) == 0  # Should not divide by zero

    def test_generate_config_recommendations(self, analyzer):
        """Test configuration recommendations generation"""
        settings = {
            "shared_buffers": {"value": "128MB"},  # Too small
            "work_mem": {"value": "4MB"},  # Too small
            "log_min_duration_statement": {"value": "-1"}  # Disabled
        }
        
        system_info = {}
        stats = {}
        
        result = analyzer._generate_config_recommendations(settings, system_info, stats)
        
        assert len(result) >= 2  # At least shared_buffers and work_mem recommendations
        
        # Check shared_buffers recommendation
        shared_buffers_rec = next((r for r in result if r["setting"] == "shared_buffers"), None)
        assert shared_buffers_rec is not None
        assert shared_buffers_rec["category"] == "memory"
        assert shared_buffers_rec["priority"] == "high"
        assert shared_buffers_rec["current_value"] == "128MB"
        assert shared_buffers_rec["recommended_value"] == "256MB"
        
        # Check work_mem recommendation
        work_mem_rec = next((r for r in result if r["setting"] == "work_mem"), None)
        assert work_mem_rec is not None
        assert work_mem_rec["category"] == "memory"
        assert work_mem_rec["priority"] == "medium"
        assert work_mem_rec["current_value"] == "4MB"
        assert work_mem_rec["recommended_value"] == "8MB"
        
        # Check logging recommendation
        logging_rec = next((r for r in result if r["setting"] == "log_min_duration_statement"), None)
        assert logging_rec is not None
        assert logging_rec["category"] == "monitoring"
        assert logging_rec["priority"] == "low"
        assert logging_rec["current_value"] == "disabled"
        assert logging_rec["recommended_value"] == "1000ms"

    def test_generate_config_recommendations_good_settings(self, analyzer):
        """Test configuration recommendations with good settings"""
        settings = {
            "shared_buffers": {"value": "512MB"},  # Good size
            "work_mem": {"value": "16MB"},  # Good size
            "log_min_duration_statement": {"value": "1000"}  # Enabled
        }
        
        system_info = {}
        stats = {}
        
        result = analyzer._generate_config_recommendations(settings, system_info, stats)
        
        # Should have no recommendations for good settings
        assert len(result) == 0

    def test_generate_config_recommendations_invalid_values(self, analyzer):
        """Test configuration recommendations with invalid values"""
        settings = {
            "shared_buffers": {"value": "invalid"},  # Invalid value
            "work_mem": {"value": "invalid"}  # Invalid value
        }
        
        system_info = {}
        stats = {}
        
        result = analyzer._generate_config_recommendations(settings, system_info, stats)
        
        # Should handle invalid values gracefully
        assert len(result) == 0
