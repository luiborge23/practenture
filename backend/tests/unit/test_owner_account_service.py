"""Unit tests for OwnerAccountService."""

import pytest
from datetime import datetime, timezone

from services.owner_account_service import OwnerAccountService


class TestOwnerAccountService:
    """Tests for the OwnerAccountService."""
    
    @pytest.fixture
    def account_service(self):
        """Create an OwnerAccountService with a test database."""
        from services.owner_account_service import OwnerAccountService
        from database import db
        
        # Initialize the test database with required tables
        db._init_db()
        
        return OwnerAccountService(db)
    
    def test_get_user(self, account_service):
        """Test getting a user by ID."""
        # First create a test user
        from database import db
        
        with db._get_conn() as conn:
            conn.execute(
                """
                    INSERT INTO users (username, role, status, name, email, password_hash)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("user-001", "professor", "active", "Test User", "test@example.com", "$2b$12$testhash")
            )
            
            conn.commit()
        
        result = account_service.get_user("user-001")
        
        assert result is not None
        assert result["username"] == "user-001"
    
    def test_get_user_not_found(self, account_service):
        """Test getting a non-existent user."""
        result = account_service.get_user("non-existent")
        
        assert result is None
    
    def test_list_users(self, account_service):
        """Test listing users."""
        # First create test users
        from database import db
        
        with db._get_conn() as conn:
            conn.execute(
                """
                    INSERT INTO users (username, role, status, name, email, password_hash)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("user-001", "professor", "active", "Test User 1", "test1@example.com", "$2b$12$testhash")
            )
            
            conn.execute(
                """
                    INSERT INTO users (username, role, status, name, email, password_hash)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("user-002", "student", "active", "Test User 2", "test2@example.com", "$2b$12$testhash")
            )
            
            conn.commit()
        
        result = account_service.list_users()
        
        # conftest seeds professor + owner; test adds user-001 and user-002
        assert len(result) == 4
    
    def test_list_users_by_role(self, account_service):
        """Test listing users filtered by role."""
        # First create test users
        from database import db
        
        with db._get_conn() as conn:
            conn.execute(
                """
                    INSERT INTO users (username, role, status, name, email, password_hash)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("user-001", "professor", "active", "Test User 1", "test1@example.com", "$2b$12$testhash")
            )
            
            conn.execute(
                """
                    INSERT INTO users (username, role, status, name, email, password_hash)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("user-002", "student", "active", "Test User 2", "test2@example.com", "$2b$12$testhash")
            )
            
            conn.commit()
        
        result = account_service.list_users(role="professor")
        
        # conftest seeds a 'professor' user; test adds user-001 (professor)
        assert len(result) == 2
        usernames = [u["username"] for u in result]
        assert "user-001" in usernames
    
    def test_suspend_user(self, account_service):
        """Test suspending a user."""
        # First create a test user
        from database import db
        
        with db._get_conn() as conn:
            conn.execute(
                """
                    INSERT INTO users (username, role, status, name, email, password_hash)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("user-001", "professor", "active", "Test User", "test@example.com", "$2b$12$testhash")
            )
            
            conn.commit()
        
        result = account_service.suspend_user(
            "user-001",
            suspended_by="owner-001",
            reason="Violation of terms"
        )
        
        assert result is not None
        assert result["status"] == "suspended"
    
    def test_suspend_user_not_found(self, account_service):
        """Test suspending a non-existent user."""
        with pytest.raises(Exception):
            account_service.suspend_user(
                "non-existent",
                suspended_by="owner-001"
            )
    
    def test_reactivate_user(self, account_service):
        """Test reactivating a suspended user."""
        # First create and suspend a test user
        from database import db
        
        with db._get_conn() as conn:
            conn.execute(
                """
                    INSERT INTO users (username, role, status, name, email, password_hash)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("user-001", "professor", "active", "Test User", "test@example.com", "$2b$12$testhash")
            )
            
            conn.commit()
        
        # Suspend the user
        account_service.suspend_user(
            "user-001",
            suspended_by="owner-001"
        )
        
        # Reactivate the user
        result = account_service.reactivate_user(
            "user-001",
            reactivated_by="owner-001"
        )
        
        assert result is not None
        assert result["status"] == "active"
    
    def test_force_password_reset(self, account_service):
        """Test forcing password reset."""
        # First create a test user
        from database import db
        
        with db._get_conn() as conn:
            conn.execute(
                """
                    INSERT INTO users (username, role, status, name, email, password_hash)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("user-001", "professor", "active", "Test User", "test@example.com", "$2b$12$testhash")
            )
            
            conn.commit()
        
        result = account_service.force_password_reset(
            "user-001",
            requested_by="owner-001"
        )
        
        assert result is not None
        assert "user_id" in result
    
    def test_update_last_login(self, account_service):
        """Test updating last login timestamp."""
        # First create a test user
        from database import db
        
        with db._get_conn() as conn:
            conn.execute(
                """
                    INSERT INTO users (username, role, status, name, email, password_hash)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("user-001", "professor", "active", "Test User", "test@example.com", "$2b$12$testhash")
            )
            
            conn.commit()
        
        result = account_service.update_last_login("user-001")
        
        assert result is True
