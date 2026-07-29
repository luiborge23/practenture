"""Execution-level verification for invitation redemption lifecycle migration 004."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config


BACKEND_DIR = Path(__file__).resolve().parents[2]


def _alembic_config(database_path: Path) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")
    return config


def test_migration_004_backfills_created_at_and_preserves_redemption_evidence(
    tmp_path: Path, monkeypatch,
) -> None:
    database_path = tmp_path / "migration-004.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    config = _alembic_config(database_path)

    command.upgrade(config, "003")
    with sqlite3.connect(database_path) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone() == ("003",)
        columns_before = {
            row[1] for row in conn.execute("PRAGMA table_info(professor_invitations)")
        }
        assert not {"created_at", "last_used_at", "redeemed_at", "redeemed_by"} & columns_before
        conn.execute(
            """INSERT INTO professor_invitations
               (id, secret_hash, masked_code, organization_id, intended_email,
                status, expires_at, max_uses, use_count, issued_by)
               VALUES (?, ?, ?, ?, ?, 'active', ?, 1, 0, ?)""",
            (
                "inv-before-004",
                "legacy-secret-hash",
                "lega...hash",
                "org-before-004",
                "professor@example.edu",
                "2027-01-01T00:00:00+00:00",
                "Admin",
            ),
        )
        conn.commit()

    command.upgrade(config, "004")
    with sqlite3.connect(database_path) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone() == ("004",)
        columns_after = {
            row[1] for row in conn.execute("PRAGMA table_info(professor_invitations)")
        }
        assert {"created_at", "last_used_at", "redeemed_at", "redeemed_by"} <= columns_after
        created_at = conn.execute(
            "SELECT created_at FROM professor_invitations WHERE id='inv-before-004'"
        ).fetchone()[0]
        assert created_at
        conn.execute(
            """UPDATE professor_invitations
               SET status='redeemed', use_count=1,
                   last_used_at='2026-07-29T12:00:00+00:00',
                   redeemed_at='2026-07-29T12:00:00+00:00',
                   redeemed_by='professor-004'
               WHERE id='inv-before-004'"""
        )
        conn.commit()

    command.downgrade(config, "003")
    with sqlite3.connect(database_path) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone() == ("003",)
        assert conn.execute(
            """SELECT status, use_count, redeemed_at, redeemed_by
               FROM professor_invitations WHERE id='inv-before-004'"""
        ).fetchone() == (
            "redeemed",
            1,
            "2026-07-29T12:00:00+00:00",
            "professor-004",
        )
