"""Test fixtures for Owner service tests."""

import pytest
from datetime import datetime, timezone

from database import db


@pytest.fixture
def setup_test_db():
    """Set up a test database with required tables."""
    from database import db
    
    # Create all required tables
    db._init_db()
    
    yield db


@pytest.fixture
def invitation_service(setup_test_db):
    """Create an InvitationService with a test database."""
    from services.invitation_service import InvitationService
    
    return InvitationService(setup_test_db)


@pytest.fixture
def account_service(setup_test_db):
    """Create an OwnerAccountService with a test database."""
    from services.owner_account_service import OwnerAccountService
    
    return OwnerAccountService(setup_test_db)


@pytest.fixture
def sample_user(setup_test_db):
    """Create a sample user for testing."""
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
    
    return {"username": "user-001", "role": "professor"}


@pytest.fixture
def sample_invitation(setup_test_db):
    """Create a sample invitation for testing."""
    from database import db
    
    with db._get_conn() as conn:
        conn.execute(
            """
                INSERT INTO professor_invitations (
                    id, secret_hash, masked_code, organization_id,
                    intended_email, status, expires_at, max_uses,
                    use_count, issued_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "inv_test_001",
                "$2b$12$testhash",
                "PROF-XXXX-XXXX",
                "org-001",
                "prof@example.edu",
                "active",
                datetime.now(timezone.utc).isoformat(),
                1,
                0,
                "owner-001"
            )
        )
        
        conn.commit()
    
    return {"id": "inv_test_001", "masked_code": "PROF-XXXX-XXXX"}
