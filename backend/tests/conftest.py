"""
Pytest configuration and fixtures for the test suite
"""
import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

# Add the backend directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

@pytest.fixture(autouse=True)
def setup_test_environment():
    """Set up test environment before each test"""
    # Create a temporary cache directory
    temp_cache_dir = tempfile.mkdtemp(prefix="test_cache_")
    
    # Mock the cache directory creation
    with patch('execution_plan_cache.Path.mkdir') as mock_mkdir:
        mock_mkdir.return_value = None
        yield
    
    # Cleanup
    import shutil
    if os.path.exists(temp_cache_dir):
        shutil.rmtree(temp_cache_dir, ignore_errors=True)

@pytest.fixture
def mock_cache_dir():
    """Provide a mock cache directory for tests"""
    return Path("/tmp/test_cache")

@pytest.fixture
def mock_database_connection():
    """Mock database connection for tests"""
    with patch('database.asyncpg.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_connect.return_value.__aenter__.return_value = mock_conn
        yield mock_conn

@pytest.fixture
def mock_llm_response():
    """Mock LLM response for tests"""
    return {
        "resource_metrics": {
            "cpu_usage": 75.0,
            "memory_usage": 128.0,
            "io_operations": 10,
            "disk_reads": 5,
            "disk_writes": 2
        },
        "recommendations": [
            {
                "type": "index",
                "priority": "high",
                "title": "Add index",
                "description": "Add index on email column",
                "potential_improvement": "Will improve query performance",
                "implementation": "CREATE INDEX idx_email ON users(email);",
                "estimated_speedup": 50.0
            }
        ],
        "warnings": ["High CPU usage detected"]
    }

@pytest.fixture
def mock_execution_plan():
    """Mock execution plan for tests"""
    return {
        "total_cost": 100.0,
        "execution_time": 50.0,
        "rows": 1000,
        "width": 64,
        "plan_json": {
            "Node Type": "Seq Scan",
            "Total Cost": 100.0,
            "Actual Total Time": 50.0
        }
    }
