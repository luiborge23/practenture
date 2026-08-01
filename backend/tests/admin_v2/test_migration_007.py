"""Execution-level verification for Admin MFA challenge migration 007."""
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


def test_migration_007_tracks_login_reservation_and_invalidates_old_challenges(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "migration-007.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")
    config = _config(path)
    command.upgrade(config, "006")

    with sqlite3.connect(path) as conn:
        conn.execute(
            """INSERT INTO users (username, password_hash, role, name)
               VALUES ('owner-007', 'hash', 'owner', 'Owner 007')"""
        )
        conn.execute(
            """INSERT INTO admin_mfa_challenges
               (id, token_hash, owner_user_id, created_at, expires_at)
               VALUES ('challenge-existing', 'token-existing', 'owner-007',
                       '2026-07-31T00:00:00+00:00', '2026-07-31T00:05:00+00:00')"""
        )
        conn.commit()

    command.upgrade(config, "007")
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone() == ("007",)
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(admin_mfa_challenges)")
        }
        assert {
            "login_identity",
            "login_client_signal",
            "login_identity_window_started_at",
            "login_pair_window_started_at",
            "login_client_window_started_at",
        } <= columns
        assert conn.execute(
            "SELECT COUNT(*) FROM admin_mfa_challenges"
        ).fetchone() == (0,)
        conn.execute(
            """INSERT INTO admin_mfa_challenges
               (id, token_hash, owner_user_id, created_at, expires_at,
                login_identity, login_client_signal,
                login_identity_window_started_at, login_pair_window_started_at,
                login_client_window_started_at)
               VALUES ('challenge-new', 'token-new', 'owner-007',
                       '2026-07-31T00:00:00+00:00', '2026-07-31T00:05:00+00:00',
                       'owner-007', '198.51.100.10', 1234.5, 1234.5, 1234.5)"""
        )
        conn.commit()

    command.downgrade(config, "006")
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone() == ("006",)
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(admin_mfa_challenges)")
        }
        assert columns.isdisjoint({
            "login_identity",
            "login_client_signal",
            "login_identity_window_started_at",
            "login_pair_window_started_at",
            "login_client_window_started_at",
        })
        assert conn.execute(
            "SELECT COUNT(*) FROM admin_mfa_challenges"
        ).fetchone() == (1,)

    command.upgrade(config, "007")
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone() == ("007",)
        assert conn.execute(
            "SELECT COUNT(*) FROM admin_mfa_challenges"
        ).fetchone() == (0,)
