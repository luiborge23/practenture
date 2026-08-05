"""Execution-level verification for SES feedback-correlation migration 011."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _config(path: Path) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{path}")
    return config


def test_migration_011_adds_only_privacy_preserving_feedback_correlations(tmp_path, monkeypatch):
    path = tmp_path / "migration-011.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")
    config = _config(path)
    command.upgrade(config, "010")

    suppression = ("b" * 64, "complaint", "2026-01-01T00:00:00+00:00", "2026-01-02T00:00:00+00:00", 1)
    feedback = ("sns-before-011", "Complaint", "ses-before-011", "suppressed", "2026-01-02T00:00:00+00:00")
    with sqlite3.connect(path) as conn:
        before_objects = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        conn.execute("INSERT INTO ses_recipient_suppressions VALUES (?, ?, ?, ?, ?)", suppression)
        conn.execute("INSERT INTO ses_feedback_events VALUES (?, ?, ?, ?, ?)", feedback)
        conn.commit()

    command.upgrade(config, "011")
    with sqlite3.connect(path) as conn:
        after_objects = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone() == ("011",)
        assert after_objects - before_objects == {"ses_feedback_correlations"}
        columns = [row[1] for row in conn.execute("PRAGMA table_info(ses_feedback_correlations)")]
        assert columns == [
            "provider",
            "provider_message_id",
            "recipient_hash",
            "accepted_at",
            "feedback_expires_at",
        ]
        primary_key = {
            row[1]: row[5] for row in conn.execute("PRAGMA table_info(ses_feedback_correlations)")
        }
        assert primary_key == {
            "provider": 1,
            "provider_message_id": 2,
            "recipient_hash": 0,
            "accepted_at": 0,
            "feedback_expires_at": 0,
        }
        indexes = {
            row[1]: tuple(column[2] for column in conn.execute(f"PRAGMA index_info({row[1]})"))
            for row in conn.execute("PRAGMA index_list(ses_feedback_correlations)")
        }
        assert indexes["idx_ses_feedback_correlations_expiry"] == ("feedback_expires_at",)
        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='ses_feedback_correlations'"
        ).fetchone()[0].casefold()
        assert "email" not in ddl
        assert "invitation" not in ddl
        assert "owner" not in ddl
        assert "idempotency" not in ddl
        assert "body" not in ddl
        assert "foreign key" not in ddl
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO ses_feedback_correlations
                   VALUES ('other', 'provider-id', ?, '2026-01-01T00:00:00+00:00',
                           '2027-01-01T00:00:00+00:00')""",
                ("c" * 64,),
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO ses_feedback_correlations
                   VALUES ('ses', 'provider-id', 'short', '2026-01-01T00:00:00+00:00',
                           '2027-01-01T00:00:00+00:00')"""
            )
        assert conn.execute("SELECT * FROM ses_recipient_suppressions").fetchone() == suppression
        assert conn.execute("SELECT * FROM ses_feedback_events").fetchone() == feedback

    command.downgrade(config, "010")
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone() == ("010",)
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ses_feedback_correlations'"
        ).fetchone() == ("ses_feedback_correlations",)
