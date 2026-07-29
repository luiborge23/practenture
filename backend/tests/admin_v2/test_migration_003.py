"""Execution-level verification for the additive Admin V2 session migration."""

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


def _legacy_snapshot(conn: sqlite3.Connection) -> dict[str, object]:
    tables = {
        row[0]: row[1]
        for row in conn.execute(
            """
            SELECT name, sql
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
              AND name NOT IN (
                  'alembic_version', 'admin_sessions', 'privileged_login_attempts',
                  'privileged_login_buckets', 'admin_mfa_replay_state',
                  'admin_mfa_challenges', 'admin_recent_auth',
                  'admin_audit_events', 'admin_idempotency_records'
              )
            ORDER BY name
            """
        )
    }
    indexes = {
        row[0]: (row[1], row[2])
        for row in conn.execute(
            """
            SELECT name, tbl_name, sql
            FROM sqlite_master
            WHERE type = 'index'
              AND tbl_name NOT IN (
                  'admin_sessions', 'privileged_login_attempts',
                  'privileged_login_buckets', 'admin_mfa_replay_state',
                  'admin_mfa_challenges', 'admin_recent_auth',
                  'admin_audit_events', 'admin_idempotency_records'
              )
            ORDER BY name
            """
        )
    }
    rows = {
        table: sorted(
            (tuple(row) for row in conn.execute(f'SELECT * FROM "{table}"')),
            key=repr,
        )
        for table in tables
    }
    return {"tables": tables, "indexes": indexes, "rows": rows}


def _seed_representative_revision_002_data(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        INSERT INTO users (
            username, password_hash, role, name, student_id, email, department,
            provider, provider_uid, must_change_password, status, last_login_at,
            password_changed_at, created_by, created_at
        ) VALUES (
            'legacy-owner', 'legacy-password-hash', 'owner', 'Legacy Owner',
            NULL, 'owner@example.edu', 'Business', 'password', NULL, 0,
            'active', '2026-07-20T10:00:00+00:00',
            '2026-07-01T09:00:00+00:00', 'bootstrap',
            '2026-06-01T08:00:00+00:00'
        );
        INSERT INTO users (
            username, password_hash, role, name, student_id, email, status, created_at
        ) VALUES (
            'legacy-student', 'student-password-hash', 'student', 'Legacy Student',
            'STU-LEGACY', 'student@example.edu', 'active',
            '2026-06-02T08:00:00+00:00'
        );
        INSERT INTO organizations (
            id, name, university_name, slug, status, created_by, created_at
        ) VALUES (
            'org-legacy', 'Legacy School', 'Legacy University', 'legacy-school',
            'active', 'legacy-owner', '2026-06-03T08:00:00+00:00'
        );
        INSERT INTO memberships (id, user_id, org_id, role, created_at)
        VALUES (
            'membership-legacy', 'legacy-owner', 'org-legacy', 'owner',
            '2026-06-04T08:00:00+00:00'
        );
        INSERT INTO classes (
            id, professor_user_id, name, description, join_code, is_active, created_at
        ) VALUES (
            'class-legacy', 'legacy-owner', 'Legacy Class', 'Preserve this text',
            'JOIN-OLD', 1, '2026-06-05T08:00:00+00:00'
        );
        INSERT INTO class_enrollments (id, class_id, student_user_id, enrolled_at)
        VALUES (
            'enrollment-legacy', 'class-legacy', 'legacy-student',
            '2026-06-06T08:00:00+00:00'
        );
        INSERT INTO sessions (
            code, session_id, config_json, teams_json, created_by,
            professor_user_id, class_id, max_human_teams, current_round, state,
            scenario_id, scenario_version, created_at
        ) VALUES (
            'BIZ-LEGACY', 'session-legacy', '{"rounds":8}',
            '[{"id":"team-legacy","cash":123.45}]', 'legacy-owner',
            'legacy-owner', 'class-legacy', 12, 3, 'running',
            'athletic-footwear-classic', '1.0.0',
            '2026-06-07T08:00:00+00:00'
        );
        INSERT INTO decisions (session_code, round_num, team_id, decision_json)
        VALUES ('BIZ-LEGACY', 3, 'team-legacy', '{"price":99.95}');
        INSERT INTO results (session_code, round_num, team_id, result_json)
        VALUES ('BIZ-LEGACY', 2, 'team-legacy', '{"profit":321.09}');
        INSERT INTO announcements (
            id, session_id, message, author_id, author_name, timestamp
        ) VALUES (
            'announcement-legacy', 'session-legacy', 'Legacy announcement',
            'legacy-owner', 'Legacy Owner', '2026-06-08T08:00:00+00:00'
        );
        """
    )
    conn.commit()


def test_migration_003_preserves_revision_002_and_downgrade_is_non_destructive(
    tmp_path: Path, monkeypatch,
) -> None:
    database_path = tmp_path / "migration-003.sqlite3"
    database_url = f"sqlite:///{database_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = _alembic_config(database_path)

    command.upgrade(config, "002")
    with sqlite3.connect(database_path) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone() == ("002",)
        assert conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='admin_sessions'"
        ).fetchone() is None
        _seed_representative_revision_002_data(conn)
        before = _legacy_snapshot(conn)

    command.upgrade(config, "003")
    with sqlite3.connect(database_path) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone() == ("003",)
        assert _legacy_snapshot(conn) == before

        table_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='admin_sessions'"
        ).fetchone()
        assert table_sql is not None
        assert [row[1] for row in conn.execute("PRAGMA table_info(admin_sessions)")] == [
            "id", "token_hash", "csrf_token_hash", "owner_user_id", "role",
            "created_at", "last_seen_at", "idle_expires_at", "absolute_expires_at",
            "revoked_at", "revocation_reason",
        ]
        index_names = {row[1] for row in conn.execute("PRAGMA index_list(admin_sessions)")}
        assert "idx_admin_sessions_owner" in index_names
        assert "idx_admin_sessions_expiry" in index_names
        assert [
            row[2] for row in conn.execute("PRAGMA index_info(idx_admin_sessions_owner)")
        ] == ["owner_user_id"]
        assert [
            row[2] for row in conn.execute("PRAGMA index_info(idx_admin_sessions_expiry)")
        ] == ["idle_expires_at", "absolute_expires_at"]
        assert conn.execute("SELECT COUNT(*) FROM admin_sessions").fetchone() == (0,)

        assert [
            row[1] for row in conn.execute("PRAGMA table_info(privileged_login_buckets)")
        ] == [
            "scope_type", "scope_key", "attempt_count", "window_started_at",
            "locked_until", "last_attempt_at",
        ]
        bucket_indexes = {
            row[1] for row in conn.execute("PRAGMA index_list(privileged_login_buckets)")
        }
        assert {
            "idx_privileged_login_buckets_last_attempt",
            "idx_privileged_login_buckets_lock",
        } <= bucket_indexes
        assert [
            row[2] for row in conn.execute(
                "PRAGMA index_info(idx_privileged_login_buckets_last_attempt)"
            )
        ] == ["last_attempt_at"]
        assert conn.execute(
            "SELECT COUNT(*) FROM privileged_login_buckets"
        ).fetchone() == (0,)

        assert [
            row[1] for row in conn.execute("PRAGMA table_info(admin_mfa_replay_state)")
        ] == ["owner_user_id", "last_accepted_totp_step", "accepted_at"]
        replay_indexes = {
            row[1] for row in conn.execute("PRAGMA index_list(admin_mfa_replay_state)")
        }
        assert "idx_admin_mfa_replay_state_accepted_at" in replay_indexes
        assert [
            row[2] for row in conn.execute(
                "PRAGMA index_info(idx_admin_mfa_replay_state_accepted_at)"
            )
        ] == ["accepted_at"]
        assert conn.execute("SELECT COUNT(*) FROM admin_mfa_replay_state").fetchone() == (0,)

        conn.execute(
            """
            INSERT INTO admin_sessions (
                id, token_hash, csrf_token_hash, owner_user_id, role,
                created_at, last_seen_at, idle_expires_at, absolute_expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "admin-session-after-upgrade", "token-hash", "csrf-hash",
                "legacy-owner", "owner", "2026-07-28T10:00:00+00:00",
                "2026-07-28T10:00:00+00:00", "2026-07-28T10:30:00+00:00",
                "2026-07-29T10:00:00+00:00",
            ),
        )
        conn.execute(
            """INSERT INTO admin_mfa_replay_state
                   (owner_user_id, last_accepted_totp_step, accepted_at)
               VALUES (?, ?, ?)""",
            ("legacy-owner", 123456, "2026-07-28T10:00:00+00:00"),
        )
        conn.execute(
            """INSERT INTO privileged_login_buckets
                   (scope_type, scope_key, attempt_count, window_started_at,
                    locked_until, last_attempt_at)
               VALUES ('identity', 'legacy-owner', 3, 100, 200, 102)"""
        )
        conn.commit()

    command.downgrade(config, "002")
    with sqlite3.connect(database_path) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone() == ("002",)
        assert _legacy_snapshot(conn) == before
        retained = conn.execute(
            "SELECT id, owner_user_id, role FROM admin_sessions"
        ).fetchall()
        assert retained == [("admin-session-after-upgrade", "legacy-owner", "owner")]
        assert conn.execute(
            """SELECT owner_user_id, last_accepted_totp_step
               FROM admin_mfa_replay_state"""
        ).fetchall() == [("legacy-owner", 123456)]
        table_names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert {
            "admin_mfa_replay_state",
            "admin_mfa_challenges",
            "admin_recent_auth",
            "admin_audit_events",
            "admin_idempotency_records",
        } <= table_names
        assert conn.execute(
            """SELECT scope_type, scope_key, attempt_count
               FROM privileged_login_buckets"""
        ).fetchall() == [("identity", "legacy-owner", 3)]
        index_names = {row[1] for row in conn.execute("PRAGMA index_list(admin_sessions)")}
        assert "idx_admin_sessions_owner" in index_names
        assert "idx_admin_sessions_expiry" in index_names