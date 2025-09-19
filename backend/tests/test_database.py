"""
Comprehensive pytest tests for PostgreSQLAnalyzer class
"""
import pytest
import json
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import asyncpg

from database import PostgreSQLAnalyzer


class TestPostgreSQLAnalyzer:
    """Test cases for PostgreSQLAnalyzer class"""

    @pytest.fixture
    def mock_connection(self):
        """Mock asyncpg connection for testing"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock()
        mock_conn.fetch = AsyncMock()
        mock_conn.fetchval = AsyncMock()
        mock_conn.close = AsyncMock()
        return mock_conn

    @pytest.fixture
    def analyzer(self):
        """Create PostgreSQLAnalyzer instance for testing"""
        return PostgreSQLAnalyzer("postgresql://test:test@localhost:5432/testdb")

    @pytest.mark.asyncio
    async def test_get_connection_success(self, analyzer, mock_connection):
        """Test successful database connection"""
        with patch('asyncpg.connect', return_value=mock_connection) as mock_connect:
            async with analyzer.get_connection() as conn:
                assert conn == mock_connection
                mock_connect.assert_called_once_with(analyzer.database_url)

    @pytest.mark.asyncio
    async def test_get_connection_error(self, analyzer):
        """Test database connection error"""
        with patch('asyncpg.connect', side_effect=Exception("Connection failed")):
            with pytest.raises(Exception, match="Connection failed"):
                async with analyzer.get_connection() as conn:
                    pass

    @pytest.mark.asyncio
    async def test_explain_query_select_success(self, analyzer, mock_connection):
        """Test successful SELECT query explanation"""
        mock_plan = {
            "QUERY PLAN": json.dumps([{
                "Plan": {
                    "Node Type": "Seq Scan",
                    "Total Cost": 100.0,
                    "Plan Rows": 1000,
                    "Plan Width": 64,
                    "Relation Name": "users"
                }
            }])
        }
        
        mock_connection.fetchrow.return_value = mock_plan
        
        with patch.object(analyzer, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            result = await analyzer.explain_query("SELECT * FROM users WHERE id = 1")
            
            assert result["Node Type"] == "Seq Scan"
            assert result["Total Cost"] == 100.0
            assert result["Plan Rows"] == 1000
            assert result["Query Type"] == "SELECT"

    @pytest.mark.asyncio
    async def test_explain_query_update_success(self, analyzer, mock_connection):
        """Test successful UPDATE query explanation with conversion"""
        mock_plan = {
            "QUERY PLAN": json.dumps([{
                "Plan": {
                    "Node Type": "Seq Scan",
                    "Total Cost": 50.0,
                    "Plan Rows": 1,
                    "Plan Width": 32,
                    "Relation Name": "users"
                }
            }])
        }
        
        mock_connection.fetchrow.return_value = mock_plan
        
        with patch.object(analyzer, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            result = await analyzer.explain_query("UPDATE users SET name = 'test' WHERE id = 1")
            
            assert result["Node Type"] == "Seq Scan"
            assert result["Query Type"] == "UPDATE"
            assert "Original Query Type" in result
            assert "Converted Query" in result

    @pytest.mark.asyncio
    async def test_explain_query_delete_success(self, analyzer, mock_connection):
        """Test successful DELETE query explanation with conversion"""
        mock_plan = {
            "QUERY PLAN": json.dumps([{
                "Plan": {
                    "Node Type": "Seq Scan",
                    "Total Cost": 25.0,
                    "Plan Rows": 1,
                    "Plan Width": 16,
                    "Relation Name": "users"
                }
            }])
        }
        
        mock_connection.fetchrow.return_value = mock_plan
        
        with patch.object(analyzer, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            result = await analyzer.explain_query("DELETE FROM users WHERE id = 1")
            
            assert result["Node Type"] == "Seq Scan"
            assert result["Query Type"] == "DELETE"
            assert "Original Query Type" in result

    @pytest.mark.asyncio
    async def test_explain_query_insert_success(self, analyzer, mock_connection):
        """Test successful INSERT query explanation with conversion"""
        mock_plan = {
            "QUERY PLAN": json.dumps([{
                "Plan": {
                    "Node Type": "Result",
                    "Total Cost": 0.0,
                    "Plan Rows": 1,
                    "Plan Width": 0
                }
            }])
        }
        
        mock_connection.fetchrow.return_value = mock_plan
        
        with patch.object(analyzer, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            result = await analyzer.explain_query("INSERT INTO users (name) VALUES ('test')")
            
            assert result["Node Type"] == "Result"
            assert result["Query Type"] == "INSERT"

    @pytest.mark.asyncio
    async def test_explain_query_utility_command(self, analyzer):
        """Test utility command (CREATE, DROP, ALTER) explanation"""
        result = await analyzer.explain_query("CREATE TABLE test (id INT)")
        
        assert result["Node Type"] == "Utility"
        assert result["Query Type"] == "CREATE"
        assert result["Total Cost"] == 0
        assert "Utility command: CREATE" in result["Description"]

    @pytest.mark.asyncio
    async def test_explain_query_error(self, analyzer, mock_connection):
        """Test query explanation with error"""
        mock_connection.fetchrow.side_effect = Exception("Query error")
        
        with patch.object(analyzer, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            result = await analyzer.explain_query("SELECT * FROM nonexistent_table")
            
            assert result["Node Type"] == "Error"
            assert result["Query Type"] == "SELECT"
            assert "Error" in result

    def test_get_query_type(self, analyzer):
        """Test query type detection"""
        assert analyzer._get_query_type("SELECT * FROM users") == "SELECT"
        assert analyzer._get_query_type("WITH cte AS (...) SELECT * FROM cte") == "SELECT"
        assert analyzer._get_query_type("INSERT INTO users VALUES (1)") == "INSERT"
        assert analyzer._get_query_type("UPDATE users SET name = 'test'") == "UPDATE"
        assert analyzer._get_query_type("DELETE FROM users WHERE id = 1") == "DELETE"
        assert analyzer._get_query_type("CREATE TABLE test (id INT)") == "CREATE"
        assert analyzer._get_query_type("DROP TABLE test") == "DROP"
        assert analyzer._get_query_type("ALTER TABLE test ADD COLUMN name TEXT") == "ALTER"
        assert analyzer._get_query_type("EXPLAIN SELECT * FROM users") == "EXPLAIN"
        assert analyzer._get_query_type("UNKNOWN COMMAND") == "UNKNOWN"

    def test_convert_update_to_select(self, analyzer):
        """Test UPDATE to SELECT conversion"""
        # Simple UPDATE
        result = analyzer._convert_update_to_select("UPDATE users SET name = 'test' WHERE id = 1")
        assert "SELECT * FROM users WHERE id = 1" in result
        
        # UPDATE with FROM clause
        result = analyzer._convert_update_to_select(
            "UPDATE users SET name = 'test' FROM profiles WHERE users.id = profiles.user_id"
        )
        assert "SELECT * FROM users, profiles WHERE users.id = profiles.user_id" in result

    def test_convert_delete_to_select(self, analyzer):
        """Test DELETE to SELECT conversion"""
        result = analyzer._convert_delete_to_select("DELETE FROM users WHERE id = 1")
        assert result == "SELECT * FROM users WHERE id = 1"
        
        result = analyzer._convert_delete_to_select("DELETE FROM users WHERE name = 'test' AND active = true")
        assert "SELECT * FROM users WHERE name = 'test' AND active = true" in result

    def test_convert_insert_to_select(self, analyzer):
        """Test INSERT to SELECT conversion"""
        # INSERT ... VALUES
        result = analyzer._convert_insert_to_select("INSERT INTO users (name) VALUES ('test')")
        assert "SELECT * FROM users WHERE 1=0" in result
        
        # INSERT ... SELECT
        result = analyzer._convert_insert_to_select(
            "INSERT INTO users (name) SELECT name FROM profiles WHERE active = true"
        )
        assert "SELECT name FROM profiles WHERE active = true" in result

    def test_extract_table_name_from_dml(self, analyzer):
        """Test table name extraction from DML queries"""
        assert analyzer._extract_table_name_from_dml("UPDATE users SET name = 'test'") == "USERS"
        assert analyzer._extract_table_name_from_dml("INSERT INTO orders (id) VALUES (1)") == "ORDERS"
        assert analyzer._extract_table_name_from_dml("DELETE FROM products WHERE id = 1") == "PRODUCTS"
        assert analyzer._extract_table_name_from_dml("INVALID QUERY") == "unknown_table"

    def test_create_dml_plan_info(self, analyzer):
        """Test DML plan info creation"""
        result = analyzer._create_dml_plan_info("UPDATE", "UPDATE users SET name = 'test'")
        
        assert result["Node Type"] == "UPDATE"
        assert result["Query Type"] == "UPDATE"
        assert result["Relation Name"] == "USERS"
        assert result["Total Cost"] == 1.0
        assert "DML operation on table: USERS" in result["Description"]

    def test_create_error_plan_info(self, analyzer):
        """Test error plan info creation"""
        result = analyzer._create_error_plan_info("SELECT", "SELECT * FROM nonexistent", "Table does not exist")
        
        assert result["Node Type"] == "Error"
        assert result["Query Type"] == "SELECT"
        assert result["Total Cost"] == 0
        assert result["Error"] == "Table does not exist"

    @pytest.mark.asyncio
    async def test_analyze_query_performance_success(self, analyzer, mock_connection):
        """Test successful query performance analysis"""
        mock_plan = {
            "QUERY PLAN": json.dumps([{
                "Plan": {
                    "Node Type": "Seq Scan",
                    "Total Cost": 100.0,
                    "Actual Total Time": 50.0,
                    "Actual Rows": 1000,
                    "Plan Width": 64,
                    "Relation Name": "users",
                    "Plans": [
                        {
                            "Node Type": "Sort",
                            "Total Cost": 50.0,
                            "Plans": []
                        }
                    ]
                }
            }])
        }
        
        mock_connection.fetchrow.return_value = mock_plan
        
        with patch.object(analyzer, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            result = await analyzer.analyze_query_performance("SELECT * FROM users ORDER BY name")
            
            assert result["total_cost"] == 100.0
            assert result["execution_time"] == 50.0
            assert result["rows"] == 1000
            assert result["width"] == 64
            assert result["io_operations"] == 2  # Seq Scan + Sort
            assert result["has_errors"] is False
            assert result["postgresql_errors"] == []

    @pytest.mark.asyncio
    async def test_analyze_query_performance_with_errors(self, analyzer, mock_connection):
        """Test query performance analysis with errors"""
        mock_plan = {
            "Node Type": "Error",
            "Error": "Table 'nonexistent' does not exist"
        }
        
        with patch.object(analyzer, 'explain_query', return_value=mock_plan):
            result = await analyzer.analyze_query_performance("SELECT * FROM nonexistent")
            
            assert result["has_errors"] is True
            assert "Table 'nonexistent' does not exist" in result["postgresql_errors"]

    def test_count_io_operations(self, analyzer):
        """Test I/O operations counting"""
        plan = {
            "Node Type": "Seq Scan",
            "Plans": [
                {
                    "Node Type": "Index Scan",
                    "Plans": []
                },
                {
                    "Node Type": "Sort",
                    "Plans": [
                        {
                            "Node Type": "Hash Join",
                            "Plans": []
                        }
                    ]
                }
            ]
        }
        
        io_count = analyzer._count_io_operations(plan)
        assert io_count == 4  # Seq Scan + Index Scan + Sort + Hash

    @pytest.mark.asyncio
    async def test_get_database_info_success(self, analyzer, mock_connection):
        """Test successful database info retrieval"""
        mock_connection.fetchrow.side_effect = [
            {"version": "PostgreSQL 15.0"},
            {"size": "10 MB"},
            {"table_count": 5},
            {"index_count": 3}
        ]
        
        with patch.object(analyzer, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            result = await analyzer.get_database_info()
            
            assert result["version"] == "PostgreSQL 15.0"
            assert result["database_size"] == "10 MB"
            assert result["table_count"] == 5
            assert result["index_count"] == 3

    @pytest.mark.asyncio
    async def test_get_database_info_error(self, analyzer, mock_connection):
        """Test database info retrieval with error"""
        mock_connection.fetchrow.side_effect = Exception("Database error")
        
        with patch.object(analyzer, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            with pytest.raises(Exception, match="Database info error"):
                await analyzer.get_database_info()

    @pytest.mark.asyncio
    async def test_get_table_statistics_success(self, analyzer, mock_connection):
        """Test successful table statistics retrieval"""
        mock_connection.fetch.side_effect = [
            [  # table_stats_query
                {
                    "tablename": "users",
                    "inserts": 100,
                    "updates": 50,
                    "deletes": 10,
                    "live_tuples": 1000,
                    "dead_tuples": 50,
                    "last_vacuum": None,
                    "last_autovacuum": "2023-01-01 10:00:00",
                    "last_analyze": None,
                    "last_autoanalyze": "2023-01-01 10:00:00"
                }
            ],
            [  # size_query
                {
                    "tablename": "users",
                    "size_pretty": "1 MB",
                    "size_bytes": 1048576
                }
            ]
        ]
        
        with patch.object(analyzer, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            result = await analyzer.get_table_statistics()
            
            assert "users" in result["tables"]
            assert result["tables"]["users"]["live_tuples"] == 1000
            assert result["tables"]["users"]["size_pretty"] == "1 MB"
            assert result["total_tables"] == 1
            assert result["total_live_tuples"] == 1000
            assert result["total_size_bytes"] == 1048576

    @pytest.mark.asyncio
    async def test_get_table_statistics_error(self, analyzer, mock_connection):
        """Test table statistics retrieval with error"""
        mock_connection.fetch.side_effect = Exception("Database error")
        
        with patch.object(analyzer, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            result = await analyzer.get_table_statistics()
            
            assert result["tables"] == {}
            assert result["total_tables"] == 0
            assert result["total_live_tuples"] == 0
            assert result["total_size_bytes"] == 0

    @pytest.mark.asyncio
    async def test_test_connection_success(self, analyzer, mock_connection):
        """Test successful connection test"""
        mock_connection.fetchval.return_value = 1
        
        with patch.object(analyzer, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            result = await analyzer.test_connection()
            
            assert result is True

    @pytest.mark.asyncio
    async def test_test_connection_failure(self, analyzer, mock_connection):
        """Test connection test failure"""
        mock_connection.fetchval.side_effect = Exception("Connection failed")
        
        with patch.object(analyzer, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            result = await analyzer.test_connection()
            
            assert result is False

    def test_analyzer_initialization_with_url(self):
        """Test analyzer initialization with custom URL"""
        custom_url = "postgresql://user:pass@host:5432/db"
        analyzer = PostgreSQLAnalyzer(custom_url)
        assert analyzer.database_url == custom_url

    def test_analyzer_initialization_without_url(self):
        """Test analyzer initialization without URL (uses default)"""
        with patch('database.settings') as mock_settings:
            mock_settings.database_url = "postgresql://default:default@localhost:5432/default"
            analyzer = PostgreSQLAnalyzer()
            assert analyzer.database_url == mock_settings.database_url

    @pytest.mark.asyncio
    async def test_explain_select_query_success(self, analyzer, mock_connection):
        """Test successful SELECT query explanation"""
        mock_plan = {
            "QUERY PLAN": json.dumps([{
                "Plan": {
                    "Node Type": "Seq Scan",
                    "Total Cost": 100.0,
                    "Plan Rows": 1000,
                    "Plan Width": 64
                }
            }])
        }
        
        mock_connection.fetchval.return_value = json.loads(mock_plan["QUERY PLAN"])
        
        with patch.object(analyzer, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            result = await analyzer._explain_select_query(
                "SELECT * FROM users WHERE id = 1",
                "UPDATE",
                "UPDATE users SET name = 'test' WHERE id = 1"
            )
            
            assert result["Node Type"] == "Seq Scan"
            assert result["Query Type"] == "UPDATE"
            assert "Converted Query" in result

    @pytest.mark.asyncio
    async def test_explain_select_query_error(self, analyzer, mock_connection):
        """Test SELECT query explanation with error"""
        mock_connection.fetchval.side_effect = Exception("Query error")
        
        with patch.object(analyzer, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            result = await analyzer._explain_select_query(
                "SELECT * FROM users WHERE id = 1",
                "UPDATE",
                "UPDATE users SET name = 'test' WHERE id = 1"
            )
            
            assert result["Node Type"] == "UPDATE"
            assert result["Query Type"] == "UPDATE"
