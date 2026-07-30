"""Tests for database migrations - syntax and structure verification."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent  # backend/
MIGRATIONS_DIR = ROOT / "migrations" / "versions"


def test_migration_file_syntax():
    """Test that migration files have valid Python syntax."""
    migration_files = list(MIGRATIONS_DIR.glob("*.py"))
    assert len(migration_files) > 0, "No migration files found"

    for migration_file in migration_files:
        # Skip __pycache__ and other non-migration files
        if migration_file.name.startswith("_") or migration_file.name == "__init__.py":
            continue

        # Check syntax
        with open(migration_file) as f:
            code = f.read()

        try:
            compile(code, str(migration_file), "exec")
        except SyntaxError as e:
            pytest.fail(f"Syntax error in {migration_file.name}: {e}")


def test_migration_000_structure():
    """Test that migration 000 (initial schema) has the expected structure."""
    migration_file = MIGRATIONS_DIR / "000_initial_schema.py"

    with open(migration_file) as f:
        content = f.read()

    # Check for required elements
    assert "revision: str = \"000\"" in content, "Missing revision identifier"
    assert "def upgrade()" in content, "Missing upgrade function"
    assert "def downgrade()" in content, "Missing downgrade function"

    # Check for expected tables
    assert "CREATE TABLE IF NOT EXISTS users" in content, "Missing users table"
    assert "CREATE TABLE IF NOT EXISTS sessions" in content, "Missing sessions table"
    assert "CREATE TABLE IF NOT EXISTS professor_invitations" in content, "Missing professor_invitations table"
    assert "CREATE TABLE IF NOT EXISTS audit_events" in content, "Missing audit_events table"

    # Check for status column
    assert "status TEXT DEFAULT 'active'" in content, "Missing status column"


def test_migration_graph_heads():
    """Test that the migration graph has a single head."""
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "heads"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=True,
    )

    # Should have exactly one head
    heads = [line.strip() for line in result.stdout.split("\n") if line.strip() and not line.startswith("INFO")]
    assert len(heads) == 1, f"Expected 1 head, got {len(heads)}: {heads}"
