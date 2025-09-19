#!/usr/bin/env python3
"""
Test runner script that sets up the environment properly for testing
"""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

# Set up test environment
def setup_test_env():
    """Set up test environment"""
    # Create temporary cache directory
    temp_cache_dir = tempfile.mkdtemp(prefix="test_cache_")
    os.environ["TEST_CACHE_DIR"] = temp_cache_dir
    
    # Mock the problematic cache directory creation
    original_mkdir = Path.mkdir
    
    def mock_mkdir(self, mode=0o777, parents=False, exist_ok=False):
        """Mock mkdir to handle cache directory creation"""
        if str(self).startswith("/app/cache"):
            # Create in temp directory instead
            temp_path = Path(temp_cache_dir) / "cache"
            temp_path.mkdir(parents=True, exist_ok=True)
            return
        return original_mkdir(self, mode, parents, exist_ok)
    
    Path.mkdir = mock_mkdir

if __name__ == "__main__":
    setup_test_env()
    
    # Now run pytest
    import pytest
    sys.exit(pytest.main(sys.argv[1:]))
