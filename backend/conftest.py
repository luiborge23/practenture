"""Hermetic pytest configuration for the backend test suite.

This module is loaded before test modules, so production singletons bind to a
throw-away SQLite database rather than ``backend/data.db``.  The per-test reset
keeps SQLite-backed and in-memory state aligned without changing production
security behavior.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


_TEST_DB_DIR = Path(tempfile.mkdtemp(prefix="practenture-pytest-"))
os.environ["PRACTENTURE_DB_PATH"] = str(_TEST_DB_DIR / "test.db")
# Legacy auth tests exercise real password verification. These credentials are
# scoped to the pytest process and never become production defaults.
os.environ["PRACTENTURE_PROFESSOR_USERNAME"] = "professor"
os.environ["PRACTENTURE_PROFESSOR_PASSWORD"] = "practenture2026"
os.environ["PRACTENTURE_OWNER_USERNAME"] = "owner"
os.environ["PRACTENTURE_OWNER_PASSWORD"] = "practenture2026"


@pytest.fixture(scope="session")
def _bootstrap_password_hash() -> str:
    """Compute the deliberately slow test password hash only once."""
    from security import hash_password

    return hash_password("practenture2026")


@pytest.fixture(autouse=True)
def isolate_backend_state(_bootstrap_password_hash: str):
    """Reset every singleton store and provision secured test principals."""
    from database import db
    import rate_limiter

    db.sessions.clear()
    db.decisions.clear()
    db.announcements.clear()
    db.results.clear()
    db.team_states.clear()

    conn = db._get_conn()
    conn.execute("PRAGMA foreign_keys=OFF")
    table_names = [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    ]
    for table_name in table_names:
        # Names come exclusively from sqlite_master, not from external input.
        conn.execute(f'DELETE FROM "{table_name}"')
    conn.execute("PRAGMA foreign_keys=ON")
    conn.commit()

    db.create_user(
        username="professor",
        password_hash=_bootstrap_password_hash,
        role="professor",
        name="Professor",
    )
    db.create_user(
        username="owner",
        password_hash=_bootstrap_password_hash,
        role="owner",
        name="Owner",
    )

    rate_limiter._login_attempts.clear()
    rate_limiter._redeem_attempts.clear()
    yield

    # A failed-auth test must not lock out a later test during teardown/next setup.
    rate_limiter._login_attempts.clear()
    rate_limiter._redeem_attempts.clear()


def pytest_sessionfinish(session, exitstatus):
    """Close SQLite before removing the throw-away test database."""
    try:
        from database import db

        if db._conn is not None:
            db._conn.close()
            db._conn = None
    finally:
        import shutil

        shutil.rmtree(_TEST_DB_DIR, ignore_errors=True)
