"""
Comprehensive pytest tests for TableStatsService class
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import asyncpg

from table_stats_service import TableStatsService


class TestTableStatsService:
    """Test cases for TableStatsService class"""

    @pytest.fixture
    def service(self):
        """Create TableStatsService instance for testing"""
        with patch('table_stats_service.settings') as mock_settings:
            mock_settings.database_url = "postgresql://test:test@localhost:5432/testdb"
            return TableStatsService()

    def test_service_initialization(self, service):
        """Test TableStatsService initialization"""
        assert service.table_stats == {}
        assert service._connection_string == "postgresql://test:test@localhost:5432/testdb"

    @pytest.mark.asyncio
    async def test_get_connection(self, service):
        """Test getting database connection"""
        with patch('asyncpg.connect') as mock_connect:
            mock_connection = AsyncMock()
            mock_connect.return_value = mock_connection
            
            connection = await service.get_connection()
            
            assert connection == mock_connection
            mock_connect.assert_called_once_with(service._connection_string)

    @pytest.mark.asyncio
    async def test_collect_table_statistics_success(self, service):
        """Test successful table statistics collection"""
        mock_connection = AsyncMock()
        
        # Mock table stats query
        mock_connection.fetch.return_value = [
            {
                "tablename": "users",
                "row_count": 1000,
                "dead_rows": 50,
                "table_size": "1 MB",
                "table_size_bytes": 1048576,
                "last_vacuum": None,
                "last_autovacuum": "2023-01-01 10:00:00",
                "last_analyze": None,
                "last_autoanalyze": "2023-01-01 10:00:00"
            },
            {
                "tablename": "orders",
                "row_count": 5000,
                "dead_rows": 100,
                "table_size": "5 MB",
                "table_size_bytes": 5242880,
                "last_vacuum": "2023-01-01 09:00:00",
                "last_autovacuum": None,
                "last_analyze": "2023-01-01 09:00:00",
                "last_autoanalyze": None
            }
        ]
        
        # Mock index stats query
        mock_connection.fetch.side_effect = [
            # First call for table stats
            [
                {
                    "tablename": "users",
                    "row_count": 1000,
                    "dead_rows": 50,
                    "table_size": "1 MB",
                    "table_size_bytes": 1048576,
                    "last_vacuum": None,
                    "last_autovacuum": "2023-01-01 10:00:00",
                    "last_analyze": None,
                    "last_autoanalyze": "2023-01-01 10:00:00"
                },
                {
                    "tablename": "orders",
                    "row_count": 5000,
                    "dead_rows": 100,
                    "table_size": "5 MB",
                    "table_size_bytes": 5242880,
                    "last_vacuum": "2023-01-01 09:00:00",
                    "last_autovacuum": None,
                    "last_analyze": "2023-01-01 09:00:00",
                    "last_autoanalyze": None
                }
            ],
            # Second call for index stats
            [
                {
                    "tablename": "users",
                    "indexname": "idx_users_id",
                    "scans": 100,
                    "tuples_read": 1000,
                    "tuples_fetched": 950
                },
                {
                    "tablename": "users",
                    "indexname": "idx_users_email",
                    "scans": 50,
                    "tuples_read": 500,
                    "tuples_fetched": 480
                },
                {
                    "tablename": "orders",
                    "indexname": "idx_orders_user_id",
                    "scans": 200,
                    "tuples_read": 2000,
                    "tuples_fetched": 1900
                }
            ]
        ]
        
        with patch.object(service, 'get_connection', return_value=mock_connection):
            result = await service.collect_table_statistics()
        
        assert "tables" in result
        assert "summary" in result
        
        # Check tables
        assert "users" in result["tables"]
        assert "orders" in result["tables"]
        
        # Check users table
        users_stats = result["tables"]["users"]
        assert users_stats["row_count"] == 1000
        assert users_stats["dead_rows"] == 50
        assert users_stats["table_size"] == "1 MB"
        assert users_stats["table_size_bytes"] == 1048576
        assert len(users_stats["indexes"]) == 2
        assert users_stats["indexes"][0]["index_name"] == "idx_users_id"
        assert users_stats["indexes"][0]["scans"] == 100
        
        # Check orders table
        orders_stats = result["tables"]["orders"]
        assert orders_stats["row_count"] == 5000
        assert orders_stats["dead_rows"] == 100
        assert orders_stats["table_size"] == "5 MB"
        assert orders_stats["table_size_bytes"] == 5242880
        assert len(orders_stats["indexes"]) == 1
        assert orders_stats["indexes"][0]["index_name"] == "idx_orders_user_id"
        
        # Check summary
        summary = result["summary"]
        assert summary["total_tables"] == 2
        assert summary["total_rows"] == 6000
        assert summary["total_size_bytes"] == 6291456  # 1048576 + 5242880
        assert "total_size_pretty" in summary

    @pytest.mark.asyncio
    async def test_collect_table_statistics_error(self, service):
        """Test table statistics collection with error"""
        mock_connection = AsyncMock()
        mock_connection.fetch.side_effect = Exception("Database error")
        
        with patch.object(service, 'get_connection', return_value=mock_connection):
            result = await service.collect_table_statistics()
        
        assert result["tables"] == {}
        assert result["summary"]["total_tables"] == 0
        assert result["summary"]["total_rows"] == 0
        assert result["summary"]["total_size_bytes"] == 0
        assert result["summary"]["total_size_pretty"] == "0 B"

    def test_format_bytes(self, service):
        """Test byte formatting"""
        assert service._format_bytes(0) == "0 B"
        assert service._format_bytes(1024) == "1.0 KB"
        assert service._format_bytes(1048576) == "1.0 MB"
        assert service._format_bytes(1073741824) == "1.0 GB"
        assert service._format_bytes(1099511627776) == "1.0 TB"
        assert service._format_bytes(1125899906842624) == "1.0 PB"

    def test_get_table_info_for_llm_specific_table(self, service):
        """Test getting table info for LLM for specific table"""
        service.table_stats = {
            "tables": {
                "users": {
                    "row_count": 1000,
                    "table_size": "1 MB",
                    "indexes": [
                        {"index_name": "idx_users_id", "scans": 100},
                        {"index_name": "idx_users_email", "scans": 50}
                    ],
                    "dead_rows": 50
                },
                "orders": {
                    "row_count": 5000,
                    "table_size": "5 MB",
                    "indexes": [
                        {"index_name": "idx_orders_user_id", "scans": 200}
                    ],
                    "dead_rows": 100
                }
            },
            "summary": {
                "total_tables": 2,
                "total_rows": 6000,
                "total_size_pretty": "6 MB"
            }
        }
        
        result = service.get_table_info_for_llm("users")
        
        assert result["table_name"] == "users"
        assert result["row_count"] == 1000
        assert result["table_size"] == "1 MB"
        assert result["indexes_count"] == 2
        assert result["dead_rows_ratio"] == 5.0  # 50 / 1000 * 100

    def test_get_table_info_for_llm_nonexistent_table(self, service):
        """Test getting table info for LLM for nonexistent table"""
        service.table_stats = {
            "tables": {
                "users": {
                    "row_count": 1000,
                    "table_size": "1 MB",
                    "indexes": [],
                    "dead_rows": 50
                }
            }
        }
        
        result = service.get_table_info_for_llm("nonexistent")
        
        assert result == {}

    def test_get_table_info_for_llm_no_stats(self, service):
        """Test getting table info for LLM with no stats loaded"""
        service.table_stats = {}
        
        result = service.get_table_info_for_llm("users")
        
        assert result == {}

    def test_get_table_info_for_llm_all_tables(self, service):
        """Test getting table info for LLM for all tables"""
        service.table_stats = {
            "tables": {
                "users": {
                    "row_count": 1000,
                    "table_size": "1 MB",
                    "indexes": [
                        {"index_name": "idx_users_id", "scans": 100}
                    ],
                    "dead_rows": 50
                },
                "orders": {
                    "row_count": 5000,
                    "table_size": "5 MB",
                    "indexes": [
                        {"index_name": "idx_orders_user_id", "scans": 200}
                    ],
                    "dead_rows": 100
                }
            },
            "summary": {
                "total_tables": 2,
                "total_rows": 6000,
                "total_size_pretty": "6 MB"
            }
        }
        
        result = service.get_table_info_for_llm()
        
        assert result["total_tables"] == 2
        assert result["total_rows"] == 6000
        assert result["total_size"] == "6 MB"
        assert len(result["tables"]) == 2
        
        # Check table summary
        users_summary = next(t for t in result["tables"] if t["name"] == "users")
        assert users_summary["rows"] == 1000
        assert users_summary["size"] == "1 MB"
        assert users_summary["indexes"] == 1
        
        orders_summary = next(t for t in result["tables"] if t["name"] == "orders")
        assert orders_summary["rows"] == 5000
        assert orders_summary["size"] == "5 MB"
        assert orders_summary["indexes"] == 1

    def test_get_table_info_for_llm_no_stats_all_tables(self, service):
        """Test getting table info for LLM for all tables with no stats"""
        service.table_stats = {}
        
        result = service.get_table_info_for_llm()
        
        assert result == {}

    def test_get_table_row_count_existing_table(self, service):
        """Test getting row count for existing table"""
        service.table_stats = {
            "tables": {
                "users": {
                    "row_count": 1000,
                    "table_size": "1 MB",
                    "indexes": [],
                    "dead_rows": 50
                }
            }
        }
        
        result = service.get_table_row_count("users")
        
        assert result == 1000

    def test_get_table_row_count_nonexistent_table(self, service):
        """Test getting row count for nonexistent table"""
        service.table_stats = {
            "tables": {
                "users": {
                    "row_count": 1000,
                    "table_size": "1 MB",
                    "indexes": [],
                    "dead_rows": 50
                }
            }
        }
        
        result = service.get_table_row_count("nonexistent")
        
        assert result == 0

    def test_get_table_row_count_no_stats(self, service):
        """Test getting row count with no stats loaded"""
        service.table_stats = {}
        
        result = service.get_table_row_count("users")
        
        assert result == 0

    @pytest.mark.asyncio
    async def test_collect_table_statistics_empty_result(self, service):
        """Test table statistics collection with empty result"""
        mock_connection = AsyncMock()
        mock_connection.fetch.side_effect = [
            [],  # No tables
            []   # No indexes
        ]
        
        with patch.object(service, 'get_connection', return_value=mock_connection):
            result = await service.collect_table_statistics()
        
        assert result["tables"] == {}
        assert result["summary"]["total_tables"] == 0
        assert result["summary"]["total_rows"] == 0
        assert result["summary"]["total_size_bytes"] == 0

    @pytest.mark.asyncio
    async def test_collect_table_statistics_with_null_values(self, service):
        """Test table statistics collection with null values"""
        mock_connection = AsyncMock()
        mock_connection.fetch.side_effect = [
            # Table stats with null values
            [
                {
                    "tablename": "users",
                    "row_count": None,  # Null value
                    "dead_rows": None,
                    "table_size": "1 MB",
                    "table_size_bytes": None,
                    "last_vacuum": None,
                    "last_autovacuum": None,
                    "last_analyze": None,
                    "last_autoanalyze": None
                }
            ],
            # Index stats
            []
        ]
        
        with patch.object(service, 'get_connection', return_value=mock_connection):
            result = await service.collect_table_statistics()
        
        assert "users" in result["tables"]
        users_stats = result["tables"]["users"]
        assert users_stats["row_count"] == 0  # Should default to 0
        assert users_stats["dead_rows"] == 0  # Should default to 0
        assert users_stats["table_size_bytes"] == 0  # Should default to 0

    @pytest.mark.asyncio
    async def test_collect_table_statistics_indexes_by_table(self, service):
        """Test table statistics collection with proper index grouping"""
        mock_connection = AsyncMock()
        mock_connection.fetch.side_effect = [
            # Table stats
            [
                {
                    "tablename": "users",
                    "row_count": 1000,
                    "dead_rows": 50,
                    "table_size": "1 MB",
                    "table_size_bytes": 1048576,
                    "last_vacuum": None,
                    "last_autovacuum": None,
                    "last_analyze": None,
                    "last_autoanalyze": None
                },
                {
                    "tablename": "orders",
                    "row_count": 5000,
                    "dead_rows": 100,
                    "table_size": "5 MB",
                    "table_size_bytes": 5242880,
                    "last_vacuum": None,
                    "last_autovacuum": None,
                    "last_analyze": None,
                    "last_autoanalyze": None
                }
            ],
            # Index stats
            [
                {
                    "tablename": "users",
                    "indexname": "idx_users_id",
                    "scans": 100,
                    "tuples_read": 1000,
                    "tuples_fetched": 950
                },
                {
                    "tablename": "users",
                    "indexname": "idx_users_email",
                    "scans": 50,
                    "tuples_read": 500,
                    "tuples_fetched": 480
                },
                {
                    "tablename": "orders",
                    "indexname": "idx_orders_user_id",
                    "scans": 200,
                    "tuples_read": 2000,
                    "tuples_fetched": 1900
                }
            ]
        ]
        
        with patch.object(service, 'get_connection', return_value=mock_connection):
            result = await service.collect_table_statistics()
        
        # Check that indexes are properly grouped by table
        users_indexes = result["tables"]["users"]["indexes"]
        assert len(users_indexes) == 2
        assert users_indexes[0]["index_name"] == "idx_users_id"
        assert users_indexes[1]["index_name"] == "idx_users_email"
        
        orders_indexes = result["tables"]["orders"]["indexes"]
        assert len(orders_indexes) == 1
        assert orders_indexes[0]["index_name"] == "idx_orders_user_id"

    def test_format_bytes_edge_cases(self, service):
        """Test byte formatting edge cases"""
        # Test very large numbers
        assert service._format_bytes(1024**5) == "1.0 PB"  # Petabyte
        
        # Test fractional values
        assert service._format_bytes(1536) == "1.5 KB"  # 1.5 KB
        assert service._format_bytes(1572864) == "1.5 MB"  # 1.5 MB
        
        # Test values just below thresholds
        assert service._format_bytes(1023) == "1023.0 B"
        assert service._format_bytes(1048575) == "1024.0 KB"

    def test_dead_rows_ratio_calculation(self, service):
        """Test dead rows ratio calculation"""
        service.table_stats = {
            "tables": {
                "users": {
                    "row_count": 1000,
                    "dead_rows": 100,
                    "table_size": "1 MB",
                    "indexes": []
                }
            }
        }
        
        result = service.get_table_info_for_llm("users")
        
        assert result["dead_rows_ratio"] == 10.0  # 100 / 1000 * 100

    def test_dead_rows_ratio_zero_live_tuples(self, service):
        """Test dead rows ratio calculation with zero live tuples"""
        service.table_stats = {
            "tables": {
                "empty_table": {
                    "row_count": 0,
                    "dead_rows": 100,
                    "table_size": "1 MB",
                    "indexes": []
                }
            }
        }
        
        result = service.get_table_info_for_llm("empty_table")
        
        # Should not divide by zero, ratio should be 0
        assert result["dead_rows_ratio"] == 0.0
