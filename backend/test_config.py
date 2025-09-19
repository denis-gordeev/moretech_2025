"""
Test configuration to override cache directories for testing
"""
import os
from pathlib import Path

# Set test cache directory
TEST_CACHE_DIR = Path("/tmp/test_cache")
TEST_CACHE_DIR.mkdir(exist_ok=True)

# Override environment variables for testing
os.environ["TEST_CACHE_DIR"] = str(TEST_CACHE_DIR)
