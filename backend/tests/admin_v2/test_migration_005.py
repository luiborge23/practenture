"""Execution-level verification for SES invitation delivery migration 005."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _config(path: Path) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{path}")
    return config


def test_migration_005_adds_delivery_evidence_without_mutating_invitations(tmp_path, monkeypatch):
    path = tmp_path / "migration-005.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")
    config = _config(path)
    command.upgrade(config, "004")
    with sqlite3.connect(path) as conn:
        conn.execute(
            """INSERT INTO professor_invitations
               (id, secret_hash, masked_code, organization_id, intended_email, status, expires_at, max_uses, use_count)
               VALUES ('before-005', 'hashed', 'mask...hash', 'org', 'prof@example.edu', 'active', '2027-01-01T00:00:00+00:00', 1, 0)"""
        )
        conn.commit()

    command.upgrade(config, "005")
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone() == ("005",)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(invitation_email_deliveries)")}
        assert {"id", "invitation_id", "idempotency_key_hash", "provider_message_id", "state"} <= columns
        assert conn.execute(
            "SELECT id, secret_hash, intended_email FROM professor_invitations WHERE id='before-005'"
        ).fetchone() == ("before-005", "hashed", "prof@example.edu")
        conn.execute(
            """INSERT INTO invitation_email_deliveries
               (id, invitation_id, recipient_email, owner_id, idempotency_key_hash, request_fingerprint, state, created_at, updated_at)
               VALUES ('delivery-005', 'before-005', 'prof@example.edu', 'owner', 'keyhash', 'fingerprint', 'failed', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')"""
        )
        conn.commit()

    command.downgrade(config, "004")
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone() == ("004",)
        assert conn.execute("SELECT state FROM invitation_email_deliveries WHERE id='delivery-005'").fetchone() == ("failed",)
