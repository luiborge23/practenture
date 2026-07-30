"""Execution-level verification for Professor workflow migration 006."""
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


def test_migration_006_backfills_unambiguous_scope_and_adds_durable_controls(
    tmp_path, monkeypatch
):
    path = tmp_path / "migration-006.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")
    config = _config(path)
    command.upgrade(config, "005")

    with sqlite3.connect(path) as conn:
        conn.executemany(
            "INSERT INTO organizations (id, name, created_at) VALUES (?, ?, ?)",
            [
                ("org-a", "Organization A", "2026-01-01T00:00:00+00:00"),
                ("org-b", "Organization B", "2026-01-01T00:00:00+00:00"),
            ],
        )
        conn.executemany(
            """INSERT INTO memberships
               (id, org_id, user_id, role, created_at)
               VALUES (?, ?, ?, 'professor', '2026-01-01T00:00:00+00:00')""",
            [
                ("member-one", "org-a", "prof-one"),
                ("member-many-a", "org-a", "prof-many"),
                ("member-many-b", "org-b", "prof-many"),
            ],
        )
        conn.executemany(
            """INSERT INTO classes
               (id, professor_user_id, name, description, join_code, is_active, created_at)
               VALUES (?, ?, ?, '', ?, 1, '2026-01-01T00:00:00+00:00')""",
            [
                ("class-one", "prof-one", "One", "CLS-ONE"),
                ("class-many", "prof-many", "Many", "CLS-MANY"),
                ("class-zero", "prof-zero", "Zero", "CLS-ZERO"),
            ],
        )
        conn.executemany(
            """INSERT INTO sessions
               (code, session_id, config_json, teams_json, created_by,
                professor_user_id, class_id, max_human_teams, current_round,
                state, scenario_id, scenario_version, created_at)
               VALUES (?, ?, '{}', '[]', ?, ?, ?, 30, 0, 'creating',
                       'athletic-footwear-classic', '1.0.0',
                       '2026-01-01T00:00:00+00:00')""",
            [
                ("BIZ-ONE", "session-one", "prof-one", "prof-one", "class-one"),
                ("BIZ-MANY", "session-many", "prof-many", "prof-many", "class-many"),
                ("BIZ-ZERO", "session-zero", "prof-zero", "prof-zero", "class-zero"),
            ],
        )
        conn.commit()

    command.upgrade(config, "006")
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone() == ("006",)
        session_columns = {row[1] for row in conn.execute("PRAGMA table_info(sessions)")}
        class_columns = {row[1] for row in conn.execute("PRAGMA table_info(classes)")}
        request_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(session_create_requests)")
        }
        assert {"organization_id", "version"} <= session_columns
        assert "organization_id" in class_columns
        assert {
            "professor_user_id",
            "idempotency_key_hash",
            "request_fingerprint",
            "session_code",
            "response_json",
        } <= request_columns
        assert conn.execute(
            "SELECT organization_id, version FROM sessions WHERE code='BIZ-ONE'"
        ).fetchone() == ("org-a", 0)
        assert conn.execute(
            "SELECT organization_id FROM classes WHERE id='class-one'"
        ).fetchone() == ("org-a",)
        assert conn.execute(
            "SELECT organization_id FROM sessions WHERE code='BIZ-MANY'"
        ).fetchone() == (None,)
        assert conn.execute(
            "SELECT organization_id FROM classes WHERE id='class-many'"
        ).fetchone() == (None,)
        assert conn.execute(
            "SELECT organization_id FROM sessions WHERE code='BIZ-ZERO'"
        ).fetchone() == (None,)
        assert conn.execute(
            "SELECT organization_id FROM classes WHERE id='class-zero'"
        ).fetchone() == (None,)

        row = (
            "prof-one",
            "key-hash",
            "fingerprint",
            "BIZ-ONE",
            '{"sessionCode":"BIZ-ONE"}',
            "2026-01-01T00:00:00+00:00",
        )
        conn.execute(
            """INSERT INTO session_create_requests
               (professor_user_id, idempotency_key_hash, request_fingerprint,
                session_code, response_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            row,
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO session_create_requests
                   (professor_user_id, idempotency_key_hash, request_fingerprint,
                    session_code, response_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                row,
            )

    command.downgrade(config, "005")
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone() == ("005",)
        assert conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='session_create_requests'"
        ).fetchone() is None
        assert "organization_id" not in {
            row[1] for row in conn.execute("PRAGMA table_info(classes)")
        }
        assert {
            row[1] for row in conn.execute("PRAGMA table_info(sessions)")
        }.isdisjoint({"organization_id", "version"})

    command.upgrade(config, "006")
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone() == ("006",)
        assert conn.execute(
            "SELECT organization_id, version FROM sessions WHERE code='BIZ-ONE'"
        ).fetchone() == ("org-a", 0)
        assert conn.execute(
            "SELECT organization_id FROM sessions WHERE code='BIZ-ZERO'"
        ).fetchone() == (None,)
