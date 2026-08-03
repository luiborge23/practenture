"""Migration 008 upgrade/downgrade and legacy-schema compatibility tests."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def _load_migration():
    path = Path(__file__).parent / "migrations/versions/008_add_account_deletion_security.py"
    spec = importlib.util.spec_from_file_location("migration_008", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_008_upgrades_legacy_schema_and_downgrades_without_identity_loss(
    tmp_path,
) -> None:
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'migration-008.db'}")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            """CREATE TABLE auth_identities (
                   id TEXT PRIMARY KEY,
                   provider TEXT NOT NULL,
                   provider_subject TEXT NOT NULL,
                   user_id TEXT NOT NULL,
                   created_at REAL NOT NULL
               )"""
        )
        conn.exec_driver_sql(
            """INSERT INTO auth_identities
               VALUES ('identity', 'apple', 'subject', 'user', 1)"""
        )
        conn.exec_driver_sql(
            """CREATE TABLE provider_revocation_jobs (
                   id TEXT PRIMARY KEY,
                   provider TEXT NOT NULL,
                   payload_ciphertext TEXT NOT NULL,
                   status TEXT NOT NULL DEFAULT 'pending',
                   attempts INTEGER NOT NULL DEFAULT 0,
                   next_attempt_at REAL NOT NULL,
                   last_error TEXT,
                   created_at REAL NOT NULL,
                   completed_at REAL
               )"""
        )

        migration = _load_migration()
        setattr(migration, "op", Operations(MigrationContext.configure(conn)))
        migration.upgrade()

        tables = set(sa.inspect(conn).get_table_names())
        assert "account_deletion_challenges" in tables
        assert "account_deletion_markers" in tables
        assert "protected_action_throttles" in tables
        revocation_columns = {
            column["name"]
            for column in sa.inspect(conn).get_columns("provider_revocation_jobs")
        }
        assert "lease_token" in revocation_columns

        migration.downgrade()

        tables = set(sa.inspect(conn).get_table_names())
        assert "account_deletion_challenges" not in tables
        assert "account_deletion_markers" not in tables
        assert "protected_action_throttles" not in tables
        assert "provider_revocation_jobs" not in tables
        assert conn.exec_driver_sql(
            "SELECT provider_subject FROM auth_identities WHERE id='identity'"
        ).scalar_one() == "subject"
