"""
Comprehensive pytest tests for DatabaseProfileManager class
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timedelta

from database_profiles import DatabaseProfileManager, DatabaseProfile, DatabaseConnection


class TestDatabaseProfile:
    """Test cases for DatabaseProfile model"""

    def test_database_profile_creation(self):
        """Test DatabaseProfile creation"""
        profile = DatabaseProfile(
            id="test_id",
            name="Test Profile",
            host="localhost",
            port=5432,
            database="testdb",
            username="testuser"
        )
        
        assert profile.id == "test_id"
        assert profile.name == "Test Profile"
        assert profile.host == "localhost"
        assert profile.port == 5432
        assert profile.database == "testdb"
        assert profile.username == "testuser"
        assert profile.is_active is True
        assert profile.connection_test_passed is False

    def test_database_profile_with_optional_fields(self):
        """Test DatabaseProfile creation with optional fields"""
        now = datetime.now()
        profile = DatabaseProfile(
            id="test_id",
            name="Test Profile",
            host="localhost",
            port=5432,
            database="testdb",
            username="testuser",
            last_used=now,
            is_active=False,
            connection_test_passed=True
        )
        
        assert profile.last_used == now
        assert profile.is_active is False
        assert profile.connection_test_passed is True


class TestDatabaseConnection:
    """Test cases for DatabaseConnection model"""

    def test_database_connection_creation(self):
        """Test DatabaseConnection creation"""
        profile = DatabaseProfile(
            id="test_id",
            name="Test Profile",
            host="localhost",
            port=5432,
            database="testdb",
            username="testuser"
        )
        
        connection = DatabaseConnection(profile=profile, password="testpass")
        
        assert connection.profile == profile
        assert connection.password == "testpass"

    def test_get_connection_url(self):
        """Test connection URL generation"""
        profile = DatabaseProfile(
            id="test_id",
            name="Test Profile",
            host="localhost",
            port=5432,
            database="testdb",
            username="testuser"
        )
        
        connection = DatabaseConnection(profile=profile, password="testpass")
        url = connection.get_connection_url()
        
        expected_url = "postgresql://testuser:testpass@localhost:5432/testdb"
        assert url == expected_url


class TestDatabaseProfileManager:
    """Test cases for DatabaseProfileManager class"""

    @pytest.fixture
    def manager(self):
        """Create DatabaseProfileManager instance for testing"""
        return DatabaseProfileManager()

    def test_manager_initialization(self, manager):
        """Test DatabaseProfileManager initialization"""
        assert manager._profiles == {}
        assert manager._active_connections == {}

    @pytest.mark.asyncio
    async def test_create_profile_success(self, manager):
        """Test successful profile creation"""
        with patch('database_profiles.PostgreSQLAnalyzer') as mock_analyzer_class:
            mock_analyzer = AsyncMock()
            mock_analyzer.test_connection = AsyncMock(return_value=True)
            mock_analyzer_class.return_value = mock_analyzer
            
            success, result = await manager.create_profile(
                name="Test Profile",
                host="localhost",
                port=5432,
                database="testdb",
                username="testuser",
                password="testpass"
            )
            
            assert success is True
            assert isinstance(result, str)  # profile_id
            assert len(result) == 16  # SHA256 hash length
            
            # Verify profile was created
            profile = manager.get_profile(result)
            assert profile is not None
            assert profile.name == "Test Profile"
            assert profile.host == "localhost"
            assert profile.port == 5432
            assert profile.database == "testdb"
            assert profile.username == "testuser"
            assert profile.connection_test_passed is True
            
            # Verify connection was stored
            connection = manager.get_connection(result)
            assert connection is not None
            assert connection.password == "testpass"

    @pytest.mark.asyncio
    async def test_create_profile_connection_failed(self, manager):
        """Test profile creation with connection failure"""
        with patch('database_profiles.PostgreSQLAnalyzer') as mock_analyzer_class:
            mock_analyzer = AsyncMock()
            mock_analyzer.test_connection = AsyncMock(return_value=False)
            mock_analyzer_class.return_value = mock_analyzer
            
            success, result = await manager.create_profile(
                name="Test Profile",
                host="localhost",
                port=5432,
                database="testdb",
                username="testuser",
                password="testpass"
            )
            
            assert success is False
            assert "Failed to connect to database" in result

    @pytest.mark.asyncio
    async def test_create_profile_exception(self, manager):
        """Test profile creation with exception"""
        with patch('database_profiles.PostgreSQLAnalyzer') as mock_analyzer_class:
            mock_analyzer_class.side_effect = Exception("Database error")
            
            success, result = await manager.create_profile(
                name="Test Profile",
                host="localhost",
                port=5432,
                database="testdb",
                username="testuser",
                password="testpass"
            )
            
            assert success is False
            assert "Profile creation failed" in result

    def test_get_profile_existing(self, manager):
        """Test getting existing profile"""
        profile = DatabaseProfile(
            id="test_id",
            name="Test Profile",
            host="localhost",
            port=5432,
            database="testdb",
            username="testuser"
        )
        
        manager._profiles["test_id"] = profile
        
        result = manager.get_profile("test_id")
        assert result == profile

    def test_get_profile_nonexistent(self, manager):
        """Test getting nonexistent profile"""
        result = manager.get_profile("nonexistent_id")
        assert result is None

    def test_get_connection_existing(self, manager):
        """Test getting existing connection"""
        profile = DatabaseProfile(
            id="test_id",
            name="Test Profile",
            host="localhost",
            port=5432,
            database="testdb",
            username="testuser"
        )
        
        connection = DatabaseConnection(profile=profile, password="testpass")
        manager._active_connections["test_id"] = connection
        
        result = manager.get_connection("test_id")
        assert result == connection

    def test_get_connection_nonexistent(self, manager):
        """Test getting nonexistent connection"""
        result = manager.get_connection("nonexistent_id")
        assert result is None

    def test_list_profiles(self, manager):
        """Test listing all profiles"""
        profile1 = DatabaseProfile(
            id="id1",
            name="Profile 1",
            host="localhost",
            port=5432,
            database="db1",
            username="user1"
        )
        
        profile2 = DatabaseProfile(
            id="id2",
            name="Profile 2",
            host="localhost",
            port=5432,
            database="db2",
            username="user2"
        )
        
        manager._profiles = {"id1": profile1, "id2": profile2}
        
        profiles = manager.list_profiles()
        assert len(profiles) == 2
        assert profile1 in profiles
        assert profile2 in profiles

    def test_list_profiles_empty(self, manager):
        """Test listing profiles when none exist"""
        profiles = manager.list_profiles()
        assert profiles == []

    def test_update_last_used(self, manager):
        """Test updating last used timestamp"""
        profile = DatabaseProfile(
            id="test_id",
            name="Test Profile",
            host="localhost",
            port=5432,
            database="testdb",
            username="testuser"
        )
        
        manager._profiles["test_id"] = profile
        
        # Initially should be None
        assert profile.last_used is None
        
        manager.update_last_used("test_id")
        
        # Should now have a timestamp
        assert profile.last_used is not None
        assert isinstance(profile.last_used, datetime)

    def test_update_last_used_nonexistent(self, manager):
        """Test updating last used for nonexistent profile"""
        # Should not raise exception
        manager.update_last_used("nonexistent_id")

    def test_delete_profile_existing(self, manager):
        """Test deleting existing profile"""
        profile = DatabaseProfile(
            id="test_id",
            name="Test Profile",
            host="localhost",
            port=5432,
            database="testdb",
            username="testuser"
        )
        
        connection = DatabaseConnection(profile=profile, password="testpass")
        
        manager._profiles["test_id"] = profile
        manager._active_connections["test_id"] = connection
        
        result = manager.delete_profile("test_id")
        
        assert result is True
        assert "test_id" not in manager._profiles
        assert "test_id" not in manager._active_connections

    def test_delete_profile_nonexistent(self, manager):
        """Test deleting nonexistent profile"""
        result = manager.delete_profile("nonexistent_id")
        assert result is False

    @pytest.mark.asyncio
    async def test_refresh_connection_success(self, manager):
        """Test successful connection refresh"""
        profile = DatabaseProfile(
            id="test_id",
            name="Test Profile",
            host="localhost",
            port=5432,
            database="testdb",
            username="testuser"
        )
        
        manager._profiles["test_id"] = profile
        
        with patch('database_profiles.PostgreSQLAnalyzer') as mock_analyzer_class:
            mock_analyzer = AsyncMock()
            mock_analyzer.test_connection = AsyncMock(return_value=True)
            mock_analyzer_class.return_value = mock_analyzer
            
            success, message = await manager.refresh_connection("test_id", "newpass")
            
            assert success is True
            assert "refreshed successfully" in message
            
            # Verify connection was updated
            connection = manager.get_connection("test_id")
            assert connection is not None
            assert connection.password == "newpass"
            assert connection.profile == profile

    @pytest.mark.asyncio
    async def test_refresh_connection_profile_not_found(self, manager):
        """Test connection refresh for nonexistent profile"""
        success, message = await manager.refresh_connection("nonexistent_id", "newpass")
        
        assert success is False
        assert "Profile not found" in message

    @pytest.mark.asyncio
    async def test_refresh_connection_failed(self, manager):
        """Test connection refresh with connection failure"""
        profile = DatabaseProfile(
            id="test_id",
            name="Test Profile",
            host="localhost",
            port=5432,
            database="testdb",
            username="testuser"
        )
        
        manager._profiles["test_id"] = profile
        
        with patch('database_profiles.PostgreSQLAnalyzer') as mock_analyzer_class:
            mock_analyzer = AsyncMock()
            mock_analyzer.test_connection = AsyncMock(return_value=False)
            mock_analyzer_class.return_value = mock_analyzer
            
            success, message = await manager.refresh_connection("test_id", "wrongpass")
            
            assert success is False
            assert "Failed to connect" in message

    @pytest.mark.asyncio
    async def test_refresh_connection_exception(self, manager):
        """Test connection refresh with exception"""
        profile = DatabaseProfile(
            id="test_id",
            name="Test Profile",
            host="localhost",
            port=5432,
            database="testdb",
            username="testuser"
        )
        
        manager._profiles["test_id"] = profile
        
        with patch('database_profiles.PostgreSQLAnalyzer') as mock_analyzer_class:
            mock_analyzer_class.side_effect = Exception("Database error")
            
            success, message = await manager.refresh_connection("test_id", "newpass")
            
            assert success is False
            assert "Connection refresh failed" in message

    def test_generate_profile_id(self, manager):
        """Test profile ID generation"""
        profile_id = manager._generate_profile_id("localhost", 5432, "testdb", "testuser")
        
        assert isinstance(profile_id, str)
        assert len(profile_id) == 16  # SHA256 hash truncated to 16 chars
        
        # Same inputs should produce same ID
        profile_id2 = manager._generate_profile_id("localhost", 5432, "testdb", "testuser")
        assert profile_id == profile_id2
        
        # Different inputs should produce different IDs
        profile_id3 = manager._generate_profile_id("localhost", 5432, "testdb", "differentuser")
        assert profile_id != profile_id3

    def test_cleanup_inactive_connections(self, manager):
        """Test cleanup of inactive connections"""
        # Create profiles with different last_used timestamps
        old_time = datetime.now() - timedelta(hours=25)  # 25 hours ago
        recent_time = datetime.now() - timedelta(hours=1)  # 1 hour ago
        
        old_profile = DatabaseProfile(
            id="old_id",
            name="Old Profile",
            host="localhost",
            port=5432,
            database="olddb",
            username="olduser",
            last_used=old_time
        )
        
        recent_profile = DatabaseProfile(
            id="recent_id",
            name="Recent Profile",
            host="localhost",
            port=5432,
            database="recentdb",
            username="recentuser",
            last_used=recent_time
        )
        
        old_connection = DatabaseConnection(profile=old_profile, password="oldpass")
        recent_connection = DatabaseConnection(profile=recent_profile, password="recentpass")
        
        manager._profiles = {"old_id": old_profile, "recent_id": recent_profile}
        manager._active_connections = {"old_id": old_connection, "recent_id": recent_connection}
        
        # Cleanup connections older than 24 hours
        manager.cleanup_inactive_connections(max_age_hours=24)
        
        # Old connection should be removed, recent should remain
        assert "old_id" not in manager._active_connections
        assert "recent_id" in manager._active_connections

    def test_cleanup_inactive_connections_no_last_used(self, manager):
        """Test cleanup with profiles that have no last_used timestamp"""
        profile = DatabaseProfile(
            id="no_time_id",
            name="No Time Profile",
            host="localhost",
            port=5432,
            database="notimedb",
            username="notimeuser"
            # last_used is None
        )
        
        connection = DatabaseConnection(profile=profile, password="notimepass")
        
        manager._profiles = {"no_time_id": profile}
        manager._active_connections = {"no_time_id": connection}
        
        # Cleanup should not remove profiles without last_used
        manager.cleanup_inactive_connections(max_age_hours=24)
        
        assert "no_time_id" in manager._active_connections

    def test_cleanup_inactive_connections_empty(self, manager):
        """Test cleanup with no connections"""
        # Should not raise exception
        manager.cleanup_inactive_connections(max_age_hours=24)

    def test_profile_dict_conversion(self, manager):
        """Test profile dictionary conversion"""
        profile = DatabaseProfile(
            id="test_id",
            name="Test Profile",
            host="localhost",
            port=5432,
            database="testdb",
            username="testuser",
            is_active=True,
            connection_test_passed=True
        )
        
        profile_dict = profile.dict()
        
        assert profile_dict["id"] == "test_id"
        assert profile_dict["name"] == "Test Profile"
        assert profile_dict["host"] == "localhost"
        assert profile_dict["port"] == 5432
        assert profile_dict["database"] == "testdb"
        assert profile_dict["username"] == "testuser"
        assert profile_dict["is_active"] is True
        assert profile_dict["connection_test_passed"] is True

    @pytest.mark.asyncio
    async def test_create_profile_duplicate_handling(self, manager):
        """Test handling of duplicate profile creation"""
        with patch('database_profiles.PostgreSQLAnalyzer') as mock_analyzer_class:
            mock_analyzer = AsyncMock()
            mock_analyzer.test_connection = AsyncMock(return_value=True)
            mock_analyzer_class.return_value = mock_analyzer
            
            # Create first profile
            success1, profile_id1 = await manager.create_profile(
                name="Test Profile",
                host="localhost",
                port=5432,
                database="testdb",
                username="testuser",
                password="testpass"
            )
            
            # Create second profile with same details
            success2, profile_id2 = await manager.create_profile(
                name="Test Profile",
                host="localhost",
                port=5432,
                database="testdb",
                username="testuser",
                password="testpass"
            )
            
            # Both should succeed but have different IDs (due to timestamp in ID generation)
            assert success1 is True
            assert success2 is True
            assert profile_id1 != profile_id2
            
            # Both profiles should exist
            assert manager.get_profile(profile_id1) is not None
            assert manager.get_profile(profile_id2) is not None
