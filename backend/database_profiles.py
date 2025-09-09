"""
Database Profiles System - Secure user database management
"""
import json
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from database import PostgreSQLAnalyzer
from security import validate_database_url, sanitize_db_url_for_logging

logger = logging.getLogger(__name__)

class DatabaseProfile(BaseModel):
    """User database profile"""
    id: str = Field(..., description="Unique profile ID")
    name: str = Field(..., description="User-friendly name")
    host: str = Field(..., description="Database host")
    port: int = Field(default=5432, description="Database port")
    database: str = Field(..., description="Database name")
    username: str = Field(..., description="Database username")
    # Note: password is not stored in this model for security
    created_at: datetime = Field(default_factory=datetime.now)
    last_used: Optional[datetime] = None
    is_active: bool = Field(default=True)
    connection_test_passed: bool = Field(default=False)

class DatabaseConnection(BaseModel):
    """Temporary database connection (includes password)"""
    profile: DatabaseProfile
    password: str
    
    def get_connection_url(self) -> str:
        """Generate PostgreSQL connection URL"""
        return (
            f"postgresql://{self.profile.username}:{self.password}@"
            f"{self.profile.host}:{self.profile.port}/{self.profile.database}"
        )

class DatabaseProfileManager:
    """Manages user database profiles securely"""
    
    def __init__(self):
        # In production, this would be a proper database
        # For demo, we'll use in-memory storage
        self._profiles: Dict[str, DatabaseProfile] = {}
        self._active_connections: Dict[str, DatabaseConnection] = {}
    
    async def create_profile(self, name: str, host: str, port: int, database: str, 
                      username: str, password: str) -> tuple:
        """
        Create a new database profile with security validation
        
        Returns:
            tuple: (success: bool, profile_id: str or error_message: str)
        """
        try:
            # Create connection URL for validation
            connection_url = f"postgresql://{username}:{password}@{host}:{port}/{database}"
            
            # Validate URL security
            is_valid, error_msg = validate_database_url(connection_url)
            if not is_valid:
                return False, f"Security validation failed: {error_msg}"
            
            # Test actual connection
            analyzer = PostgreSQLAnalyzer(connection_url)
            connection_ok = await analyzer.test_connection()
            
            if not connection_ok:
                return False, "Failed to connect to database. Please check credentials."
            
            # Generate unique profile ID
            profile_id = self._generate_profile_id(host, port, database, username)
            
            # Create profile (without password)
            profile = DatabaseProfile(
                id=profile_id,
                name=name,
                host=host,
                port=port,
                database=database,
                username=username,
                connection_test_passed=True
            )
            
            # Store profile
            self._profiles[profile_id] = profile
            
            # Store temporary connection (with password) for immediate use
            connection = DatabaseConnection(profile=profile, password=password)
            self._active_connections[profile_id] = connection
            
            # Log safely
            safe_url = sanitize_db_url_for_logging(connection_url)
            logger.info(f"Created database profile: {profile_id} -> {safe_url}")
            
            return True, profile_id
            
        except Exception as e:
            logger.error(f"Failed to create database profile: {e}")
            return False, f"Profile creation failed: {str(e)}"
    
    def get_profile(self, profile_id: str) -> Optional[DatabaseProfile]:
        """Get database profile by ID"""
        return self._profiles.get(profile_id)
    
    def get_connection(self, profile_id: str) -> Optional[DatabaseConnection]:
        """Get active database connection"""
        return self._active_connections.get(profile_id)
    
    def list_profiles(self) -> List[DatabaseProfile]:
        """List all database profiles"""
        return list(self._profiles.values())
    
    def update_last_used(self, profile_id: str):
        """Update last used timestamp"""
        if profile_id in self._profiles:
            self._profiles[profile_id].last_used = datetime.now()
    
    def delete_profile(self, profile_id: str) -> bool:
        """Delete database profile"""
        if profile_id in self._profiles:
            del self._profiles[profile_id]
            if profile_id in self._active_connections:
                del self._active_connections[profile_id]
            logger.info(f"Deleted database profile: {profile_id}")
            return True
        return False
    
    async def refresh_connection(self, profile_id: str, password: str) -> tuple:
        """
        Refresh connection for existing profile
        
        Returns:
            tuple: (success: bool, message: str)
        """
        profile = self.get_profile(profile_id)
        if not profile:
            return False, "Profile not found"
        
        try:
            # Create new connection
            connection = DatabaseConnection(profile=profile, password=password)
            connection_url = connection.get_connection_url()
            
            # Validate security (should pass since profile was validated before)
            is_valid, error_msg = validate_database_url(connection_url)
            if not is_valid:
                return False, f"Security validation failed: {error_msg}"
            
            # Test connection
            analyzer = PostgreSQLAnalyzer(connection_url)
            connection_ok = await analyzer.test_connection()
            
            if not connection_ok:
                return False, "Failed to connect. Please check password."
            
            # Update active connection
            self._active_connections[profile_id] = connection
            self.update_last_used(profile_id)
            
            return True, "Connection refreshed successfully"
            
        except Exception as e:
            logger.error(f"Failed to refresh connection for {profile_id}: {e}")
            return False, f"Connection refresh failed: {str(e)}"
    
    def _generate_profile_id(self, host: str, port: int, database: str, username: str) -> str:
        """Generate unique profile ID"""
        content = f"{host}:{port}/{database}@{username}@{datetime.now().isoformat()}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def cleanup_inactive_connections(self, max_age_hours: int = 24):
        """Clean up old inactive connections"""
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        to_remove = []
        
        for profile_id, profile in self._profiles.items():
            if profile.last_used and profile.last_used < cutoff:
                to_remove.append(profile_id)
        
        for profile_id in to_remove:
            if profile_id in self._active_connections:
                del self._active_connections[profile_id]
                logger.info(f"Cleaned up inactive connection: {profile_id}")

# Global instance
profile_manager = DatabaseProfileManager()
