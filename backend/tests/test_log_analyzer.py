"""
Comprehensive pytest tests for PostgreSQLLogAnalyzer class
"""
import pytest
import tempfile
from unittest.mock import Mock, patch, mock_open
from pathlib import Path
from datetime import datetime, timedelta

from log_analyzer import PostgreSQLLogAnalyzer


class TestPostgreSQLLogAnalyzer:
    """Test cases for PostgreSQLLogAnalyzer class"""

    @pytest.fixture
    def temp_log_dir(self):
        """Create temporary log directory for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def analyzer(self, temp_log_dir):
        """Create PostgreSQLLogAnalyzer instance for testing"""
        return PostgreSQLLogAnalyzer(log_directory=str(temp_log_dir))

    def test_analyzer_initialization(self, temp_log_dir):
        """Test PostgreSQLLogAnalyzer initialization"""
        analyzer = PostgreSQLLogAnalyzer(log_directory=str(temp_log_dir))
        
        assert analyzer.log_directory == str(temp_log_dir)
        assert "slow_query" in analyzer.log_patterns
        assert "error" in analyzer.log_patterns
        assert "connection" in analyzer.log_patterns
        assert "checkpoint" in analyzer.log_patterns
        assert "deadlock" in analyzer.log_patterns
        assert "lock_timeout" in analyzer.log_patterns

    def test_analyzer_initialization_default_directory(self):
        """Test PostgreSQLLogAnalyzer initialization with default directory"""
        analyzer = PostgreSQLLogAnalyzer()
        
        assert analyzer.log_directory == "/var/log/postgresql"

    @pytest.mark.asyncio
    async def test_analyze_logs_success(self, analyzer, temp_log_dir):
        """Test successful log analysis"""
        # Create test log file
        log_file = temp_log_dir / "postgresql.log"
        log_content = """2023-01-01 10:00:00.000 UTC [12345] LOG:  duration: 150.5 ms  statement: SELECT * FROM users WHERE id = 1;
2023-01-01 10:01:00.000 UTC [12346] ERROR:  relation "nonexistent_table" does not exist
2023-01-01 10:02:00.000 UTC [12347] LOG:  connection received: host=192.168.1.1 port=5432
2023-01-01 10:03:00.000 UTC [12348] ERROR:  deadlock detected
2023-01-01 10:04:00.000 UTC [12349] ERROR:  canceling statement because of lock timeout
2023-01-01 10:05:00.000 UTC [12350] LOG:  checkpoint complete: wrote 100 buffers
"""
        
        with open(log_file, 'w') as f:
            f.write(log_content)
        
        result = await analyzer.analyze_logs(hours_back=24)
        
        assert result["status"] == "success" or "slow_queries" in result
        assert len(result["slow_queries"]) == 1
        assert len(result["errors"]) == 2
        assert len(result["deadlocks"]) == 1
        assert len(result["lock_timeouts"]) == 1
        assert len(result["checkpoints"]) == 1
        assert "summary" in result

    @pytest.mark.asyncio
    async def test_analyze_logs_no_files(self, analyzer):
        """Test log analysis with no log files"""
        # Use non-existent directory
        analyzer.log_directory = "/nonexistent/directory"
        
        result = await analyzer.analyze_logs(hours_back=24)
        
        assert result["slow_queries"] == []
        assert result["errors"] == []
        assert result["deadlocks"] == []
        assert result["lock_timeouts"] == []
        assert result["checkpoints"] == []
        assert result["summary"]["total_slow_queries"] == 0

    @pytest.mark.asyncio
    async def test_analyze_logs_error(self, analyzer, temp_log_dir):
        """Test log analysis with error"""
        # Create log file that will cause read error
        log_file = temp_log_dir / "postgresql.log"
        log_file.touch()
        
        # Mock file read to raise exception
        with patch('builtins.open', side_effect=IOError("Read error")):
            result = await analyzer.analyze_logs(hours_back=24)
        
        assert result["slow_queries"] == []
        assert result["errors"] == []
        assert result["summary"]["total_slow_queries"] == 0

    @pytest.mark.asyncio
    async def test_find_log_files(self, analyzer, temp_log_dir):
        """Test finding log files"""
        # Create test log files
        log_files = [
            temp_log_dir / "postgresql-2023-01-01.log",
            temp_log_dir / "postgresql-2023-01-02.log",
            temp_log_dir / "postgresql.log",
            temp_log_dir / "other.log"
        ]
        
        for log_file in log_files:
            log_file.touch()
        
        files = await analyzer._find_log_files()
        
        # Should find PostgreSQL log files
        assert len(files) >= 3  # At least the postgresql files
        file_names = [f.name for f in files]
        assert "postgresql-2023-01-01.log" in file_names
        assert "postgresql-2023-01-02.log" in file_names
        assert "postgresql.log" in file_names

    @pytest.mark.asyncio
    async def test_find_log_files_nonexistent_directory(self, analyzer):
        """Test finding log files in nonexistent directory"""
        analyzer.log_directory = "/nonexistent/directory"
        
        files = await analyzer._find_log_files()
        
        assert files == []

    def test_extract_timestamp_success(self, analyzer):
        """Test successful timestamp extraction"""
        line = "2023-01-01 10:00:00.123 UTC [12345] LOG:  test message"
        
        timestamp = analyzer._extract_timestamp(line)
        
        assert timestamp is not None
        assert timestamp.year == 2023
        assert timestamp.month == 1
        assert timestamp.day == 1
        assert timestamp.hour == 10
        assert timestamp.minute == 0
        assert timestamp.second == 0

    def test_extract_timestamp_without_microseconds(self, analyzer):
        """Test timestamp extraction without microseconds"""
        line = "2023-01-01 10:00:00 UTC [12345] LOG:  test message"
        
        timestamp = analyzer._extract_timestamp(line)
        
        assert timestamp is not None
        assert timestamp.year == 2023
        assert timestamp.microsecond == 0

    def test_extract_timestamp_invalid_format(self, analyzer):
        """Test timestamp extraction with invalid format"""
        line = "Invalid log line without timestamp"
        
        timestamp = analyzer._extract_timestamp(line)
        
        assert timestamp is None

    def test_extract_timestamp_malformed(self, analyzer):
        """Test timestamp extraction with malformed timestamp"""
        line = "2023-13-45 25:70:80 UTC [12345] LOG:  test message"
        
        timestamp = analyzer._extract_timestamp(line)
        
        assert timestamp is None

    def test_analyze_line_slow_query(self, analyzer):
        """Test analyzing line with slow query"""
        line = "2023-01-01 10:00:00.000 UTC [12345] LOG:  duration: 150.5 ms  statement: SELECT * FROM users WHERE id = 1;"
        timestamp = datetime(2023, 1, 1, 10, 0, 0)
        results = {
            "slow_queries": [],
            "errors": [],
            "connection_issues": [],
            "deadlocks": [],
            "lock_timeouts": [],
            "checkpoints": []
        }
        
        analyzer._analyze_line(line, timestamp, results)
        
        assert len(results["slow_queries"]) == 1
        assert results["slow_queries"][0]["duration_ms"] == 150.5
        assert results["slow_queries"][0]["statement"] == "SELECT * FROM users WHERE id = 1;"
        assert results["slow_queries"][0]["severity"] == "medium"

    def test_analyze_line_slow_query_high_severity(self, analyzer):
        """Test analyzing line with very slow query"""
        line = "2023-01-01 10:00:00.000 UTC [12345] LOG:  duration: 1500.5 ms  statement: SELECT * FROM large_table;"
        timestamp = datetime(2023, 1, 1, 10, 0, 0)
        results = {
            "slow_queries": [],
            "errors": [],
            "connection_issues": [],
            "deadlocks": [],
            "lock_timeouts": [],
            "checkpoints": []
        }
        
        analyzer._analyze_line(line, timestamp, results)
        
        assert len(results["slow_queries"]) == 1
        assert results["slow_queries"][0]["severity"] == "high"

    def test_analyze_line_slow_query_fast(self, analyzer):
        """Test analyzing line with fast query (should be ignored)"""
        line = "2023-01-01 10:00:00.000 UTC [12345] LOG:  duration: 50.5 ms  statement: SELECT 1;"
        timestamp = datetime(2023, 1, 1, 10, 0, 0)
        results = {
            "slow_queries": [],
            "errors": [],
            "connection_issues": [],
            "deadlocks": [],
            "lock_timeouts": [],
            "checkpoints": []
        }
        
        analyzer._analyze_line(line, timestamp, results)
        
        assert len(results["slow_queries"]) == 0

    def test_analyze_line_error(self, analyzer):
        """Test analyzing line with error"""
        line = "2023-01-01 10:00:00.000 UTC [12345] ERROR:  relation \"nonexistent_table\" does not exist"
        timestamp = datetime(2023, 1, 1, 10, 0, 0)
        results = {
            "slow_queries": [],
            "errors": [],
            "connection_issues": [],
            "deadlocks": [],
            "lock_timeouts": [],
            "checkpoints": []
        }
        
        analyzer._analyze_line(line, timestamp, results)
        
        assert len(results["errors"]) == 1
        assert "nonexistent_table" in results["errors"][0]["message"]
        assert results["errors"][0]["type"] == "other"

    def test_analyze_line_deadlock(self, analyzer):
        """Test analyzing line with deadlock"""
        line = "2023-01-01 10:00:00.000 UTC [12345] ERROR:  deadlock detected"
        timestamp = datetime(2023, 1, 1, 10, 0, 0)
        results = {
            "slow_queries": [],
            "errors": [],
            "connection_issues": [],
            "deadlocks": [],
            "lock_timeouts": [],
            "checkpoints": []
        }
        
        analyzer._analyze_line(line, timestamp, results)
        
        assert len(results["deadlocks"]) == 1
        assert results["deadlocks"][0]["message"] == "Deadlock detected"

    def test_analyze_line_lock_timeout(self, analyzer):
        """Test analyzing line with lock timeout"""
        line = "2023-01-01 10:00:00.000 UTC [12345] ERROR:  canceling statement because of lock timeout"
        timestamp = datetime(2023, 1, 1, 10, 0, 0)
        results = {
            "slow_queries": [],
            "errors": [],
            "connection_issues": [],
            "deadlocks": [],
            "lock_timeouts": [],
            "checkpoints": []
        }
        
        analyzer._analyze_line(line, timestamp, results)
        
        assert len(results["lock_timeouts"]) == 1
        assert results["lock_timeouts"][0]["message"] == "Lock timeout detected"

    def test_analyze_line_connection_issue(self, analyzer):
        """Test analyzing line with connection issue"""
        line = "2023-01-01 10:00:00.000 UTC [12345] LOG:  connection received: host=192.168.1.1 port=5432"
        timestamp = datetime(2023, 1, 1, 10, 0, 0)
        results = {
            "slow_queries": [],
            "errors": [],
            "connection_issues": [],
            "deadlocks": [],
            "lock_timeouts": [],
            "checkpoints": []
        }
        
        analyzer._analyze_line(line, timestamp, results)
        
        # Should not add to connection_issues (no failure keywords)
        assert len(results["connection_issues"]) == 0

    def test_analyze_line_connection_failure(self, analyzer):
        """Test analyzing line with connection failure"""
        line = "2023-01-01 10:00:00.000 UTC [12345] LOG:  connection failed: host=192.168.1.1 port=5432"
        timestamp = datetime(2023, 1, 1, 10, 0, 0)
        results = {
            "slow_queries": [],
            "errors": [],
            "connection_issues": [],
            "deadlocks": [],
            "lock_timeouts": [],
            "checkpoints": []
        }
        
        analyzer._analyze_line(line, timestamp, results)
        
        assert len(results["connection_issues"]) == 1
        assert "failed" in results["connection_issues"][0]["message"]

    def test_analyze_line_checkpoint(self, analyzer):
        """Test analyzing line with checkpoint"""
        line = "2023-01-01 10:00:00.000 UTC [12345] LOG:  checkpoint complete: wrote 100 buffers"
        timestamp = datetime(2023, 1, 1, 10, 0, 0)
        results = {
            "slow_queries": [],
            "errors": [],
            "connection_issues": [],
            "deadlocks": [],
            "lock_timeouts": [],
            "checkpoints": []
        }
        
        analyzer._analyze_line(line, timestamp, results)
        
        assert len(results["checkpoints"]) == 1
        assert "checkpoint complete" in results["checkpoints"][0]["message"]

    def test_classify_error(self, analyzer):
        """Test error classification"""
        assert analyzer._classify_error("connection refused") == "connection"
        assert analyzer._classify_error("permission denied") == "permission"
        assert analyzer._classify_error("syntax error") == "syntax"
        assert analyzer._classify_error("constraint violation") == "constraint"
        assert analyzer._classify_error("timeout occurred") == "timeout"
        assert analyzer._classify_error("unknown error") == "other"

    def test_generate_summary(self, analyzer):
        """Test summary generation"""
        results = {
            "slow_queries": [
                {"duration_ms": 100.0},
                {"duration_ms": 200.0},
                {"duration_ms": 1500.0}
            ],
            "errors": [
                {"type": "connection"},
                {"type": "syntax"},
                {"type": "connection"}
            ],
            "deadlocks": [{"message": "Deadlock 1"}],
            "lock_timeouts": [{"message": "Timeout 1"}],
            "connection_issues": [{"message": "Connection 1"}],
            "checkpoints": [{"message": "Checkpoint 1"}]
        }
        
        summary = analyzer._generate_summary(results)
        
        assert summary["total_slow_queries"] == 3
        assert summary["total_errors"] == 3
        assert summary["total_deadlocks"] == 1
        assert summary["total_lock_timeouts"] == 1
        assert summary["total_connection_issues"] == 1
        assert summary["total_checkpoints"] == 1
        assert summary["slowest_query_duration"] == 1500.0
        assert summary["error_types"]["connection"] == 2
        assert summary["error_types"]["syntax"] == 1
        assert len(summary["recommendations"]) > 0

    def test_generate_recommendations(self, analyzer):
        """Test recommendation generation"""
        results = {
            "slow_queries": [{"duration_ms": 100.0}] * 15,  # 15 slow queries
            "deadlocks": [{"message": "Deadlock 1"}],
            "lock_timeouts": [{"message": "Timeout 1"}],
            "connection_issues": [{"message": "Connection 1"}]
        }
        
        recommendations = analyzer._generate_recommendations(results)
        
        assert len(recommendations) == 4
        assert any("15 медленных запросов" in rec for rec in recommendations)
        assert any("дедлоков" in rec for rec in recommendations)
        assert any("таймаутов блокировок" in rec for rec in recommendations)
        assert any("проблем с подключениями" in rec for rec in recommendations)

    def test_generate_recommendations_no_issues(self, analyzer):
        """Test recommendation generation with no issues"""
        results = {
            "slow_queries": [],
            "deadlocks": [],
            "lock_timeouts": [],
            "connection_issues": []
        }
        
        recommendations = analyzer._generate_recommendations(results)
        
        assert len(recommendations) == 0

    def test_empty_analysis(self, analyzer):
        """Test empty analysis result"""
        result = analyzer._empty_analysis()
        
        assert result["slow_queries"] == []
        assert result["errors"] == []
        assert result["deadlocks"] == []
        assert result["lock_timeouts"] == []
        assert result["checkpoints"] == []
        assert result["summary"]["total_slow_queries"] == 0
        assert result["summary"]["total_errors"] == 0
        assert result["summary"]["recommendations"] == []

    @pytest.mark.asyncio
    async def test_analyze_log_file_success(self, analyzer, temp_log_dir):
        """Test successful log file analysis"""
        log_file = temp_log_dir / "test.log"
        log_content = """2023-01-01 10:00:00.000 UTC [12345] LOG:  duration: 150.5 ms  statement: SELECT * FROM users;
2023-01-01 10:01:00.000 UTC [12346] ERROR:  test error message
"""
        
        with open(log_file, 'w') as f:
            f.write(log_content)
        
        results = {
            "slow_queries": [],
            "errors": [],
            "connection_issues": [],
            "deadlocks": [],
            "lock_timeouts": [],
            "checkpoints": []
        }
        
        cutoff_time = datetime(2023, 1, 1, 9, 0, 0)  # 1 hour before log entries
        
        await analyzer._analyze_log_file(log_file, cutoff_time, results)
        
        assert len(results["slow_queries"]) == 1
        assert len(results["errors"]) == 1

    @pytest.mark.asyncio
    async def test_analyze_log_file_old_entries(self, analyzer, temp_log_dir):
        """Test log file analysis with old entries (should be filtered out)"""
        log_file = temp_log_dir / "test.log"
        log_content = """2023-01-01 08:00:00.000 UTC [12345] LOG:  duration: 150.5 ms  statement: SELECT * FROM users;
2023-01-01 10:00:00.000 UTC [12346] LOG:  duration: 200.5 ms  statement: SELECT * FROM orders;
"""
        
        with open(log_file, 'w') as f:
            f.write(log_content)
        
        results = {
            "slow_queries": [],
            "errors": [],
            "connection_issues": [],
            "deadlocks": [],
            "lock_timeouts": [],
            "checkpoints": []
        }
        
        cutoff_time = datetime(2023, 1, 1, 9, 0, 0)  # Between the two entries
        
        await analyzer._analyze_log_file(log_file, cutoff_time, results)
        
        # Only the second entry should be included
        assert len(results["slow_queries"]) == 1
        assert results["slow_queries"][0]["duration_ms"] == 200.5

    @pytest.mark.asyncio
    async def test_analyze_log_file_parse_error(self, analyzer, temp_log_dir):
        """Test log file analysis with parse error"""
        log_file = temp_log_dir / "test.log"
        log_content = """2023-01-01 10:00:00.000 UTC [12345] LOG:  duration: 150.5 ms  statement: SELECT * FROM users;
Invalid line without timestamp
2023-01-01 10:01:00.000 UTC [12346] ERROR:  test error message
"""
        
        with open(log_file, 'w') as f:
            f.write(log_content)
        
        results = {
            "slow_queries": [],
            "errors": [],
            "connection_issues": [],
            "deadlocks": [],
            "lock_timeouts": [],
            "checkpoints": []
        }
        
        cutoff_time = datetime(2023, 1, 1, 9, 0, 0)
        
        # Should not raise exception, just skip invalid lines
        await analyzer._analyze_log_file(log_file, cutoff_time, results)
        
        assert len(results["slow_queries"]) == 1
        assert len(results["errors"]) == 1

    @pytest.mark.asyncio
    async def test_analyze_log_file_read_error(self, analyzer, temp_log_dir):
        """Test log file analysis with read error"""
        log_file = temp_log_dir / "test.log"
        log_file.touch()
        
        results = {
            "slow_queries": [],
            "errors": [],
            "connection_issues": [],
            "deadlocks": [],
            "lock_timeouts": [],
            "checkpoints": []
        }
        
        cutoff_time = datetime(2023, 1, 1, 9, 0, 0)
        
        # Mock file read to raise exception
        with patch('builtins.open', side_effect=IOError("Read error")):
            # Should not raise exception, just log error
            await analyzer._analyze_log_file(log_file, cutoff_time, results)
        
        # Results should remain empty
        assert len(results["slow_queries"]) == 0
        assert len(results["errors"]) == 0
