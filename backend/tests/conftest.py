"""Test fixtures for Owner service tests."""

import os
import tempfile
from pathlib import Path

# Configure and migrate an isolated database before importing any singleton.
os.environ.setdefault("PRACTENTURE_TESTING", "1")
os.environ.setdefault("PRACTENTURE_JWT_SECRET", "test-secret-key-for-pytest-only")
# The repository-wide fixture establishes the sole disposable database path before
# this nested conftest loads. Alembic must migrate that exact same path so the
# database singleton and migration runner never diverge.
_TEST_DATABASE_PATH = Path(os.environ["PRACTENTURE_DB_PATH"])
_TEST_DATABASE_DIR = _TEST_DATABASE_PATH.parent
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DATABASE_PATH}"

from alembic import command
from alembic.config import Config

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_alembic_config = Config(str(_BACKEND_DIR / "alembic.ini"))
_alembic_config.set_main_option("script_location", str(_BACKEND_DIR / "migrations"))
command.upgrade(_alembic_config, "head")

import pytest
from datetime import datetime, timezone

from database import db


def _clear_login_buckets() -> None:
    """Clear the durable throttle table only when this fixture's schema includes it."""
    with db._lock:
        conn = db._get_conn()
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            ("privileged_login_buckets",),
        ).fetchone()
        if exists:
            conn.execute("DELETE FROM privileged_login_buckets")
            conn.commit()


@pytest.fixture(autouse=True)
def isolate_admin_v2_login_buckets():
    """Prevent durable client-wide failure budgets from leaking between tests."""
    _clear_login_buckets()
    yield
    _clear_login_buckets()


@pytest.fixture
def setup_test_db():
    """Provide the explicitly migrated isolated test database."""
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
