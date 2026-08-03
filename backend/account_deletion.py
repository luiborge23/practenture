"""Atomic self-service account deletion and retained-record anonymization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
import secrets
import sqlite3
from typing import Any

from database import Database
from security import hash_password, verify_password


class AccountDeletionError(Exception):
    """Typed deletion failure safe for translation at the HTTP boundary."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class DeletionResult:
    tombstone_id: str
    ended_sessions: int
    anonymized_teams: int
    provider_revocation_job_id: str | None = None


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    if not exists:
        return set()
    return {str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")')}


def _pseudonymize_json_text(
    value: str | None, *, sensitive_values: set[str], replacement: str
) -> str | None:
    if value is None:
        return None

    def scrub(item):
        if isinstance(item, dict):
            return {key: scrub(nested) for key, nested in item.items()}
        if isinstance(item, list):
            return [scrub(nested) for nested in item]
        if isinstance(item, str):
            scrubbed = item
            for sensitive in sensitive_values:
                if sensitive:
                    scrubbed = scrubbed.replace(sensitive, replacement)
            return scrubbed
        return item

    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        scrubbed = value
        for sensitive in sensitive_values:
            if sensitive:
                scrubbed = scrubbed.replace(sensitive, replacement)
        return scrubbed
    return json.dumps(scrub(decoded), separators=(",", ":"), sort_keys=True)


def _replace_json_identity(value: Any, *, old_user_id: str, old_team_id: str, new_team_id: str) -> Any:
    if isinstance(value, dict):
        return {
            key: _replace_json_identity(
                child,
                old_user_id=old_user_id,
                old_team_id=old_team_id,
                new_team_id=new_team_id,
            )
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [
            _replace_json_identity(
                child,
                old_user_id=old_user_id,
                old_team_id=old_team_id,
                new_team_id=new_team_id,
            )
            for child in value
        ]
    if value == old_user_id:
        return None
    if value == old_team_id:
        return new_team_id
    return value


def _anonymize_session_teams(
    conn: sqlite3.Connection, *, user_id: str, tombstone_id: str
) -> int:
    anonymized = 0
    rows = conn.execute("SELECT code, teams_json FROM sessions").fetchall()
    for row in rows:
        try:
            teams = json.loads(row["teams_json"] or "[]")
        except (TypeError, ValueError):
            continue
        changed = False
        for team in teams:
            if not isinstance(team, dict) or team.get("studentId") != user_id:
                continue
            old_team_id = str(team.get("teamName") or "")
            new_team_id = f"Deleted Team {secrets.token_hex(4)}"
            team["studentId"] = None
            team["teamName"] = new_team_id
            changed = True
            anonymized += 1

            for table, json_column in (
                ("decisions", "decision_json"),
                ("results", "result_json"),
                ("team_states", "state_json"),
            ):
                if not _table_columns(conn, table):
                    continue
                data_rows = conn.execute(
                    f'SELECT rowid, "{json_column}" FROM "{table}" '
                    "WHERE session_code=? AND team_id=?",
                    (row["code"], old_team_id),
                ).fetchall()
                for data_row in data_rows:
                    try:
                        payload = json.loads(data_row[json_column])
                    except (TypeError, ValueError):
                        payload = None
                    if payload is not None:
                        payload = _replace_json_identity(
                            payload,
                            old_user_id=user_id,
                            old_team_id=old_team_id,
                            new_team_id=new_team_id,
                        )
                        conn.execute(
                            f'UPDATE "{table}" SET "{json_column}"=? WHERE rowid=?',
                            (json.dumps(payload, separators=(",", ":")), data_row["rowid"]),
                        )
                conn.execute(
                    f'UPDATE "{table}" SET team_id=? '
                    "WHERE session_code=? AND team_id=?",
                    (new_team_id, row["code"], old_team_id),
                )
        if changed:
            conn.execute(
                "UPDATE sessions SET teams_json=?, version=version+1 WHERE code=?",
                (json.dumps(teams, separators=(",", ":")), row["code"]),
            )
    return anonymized


def _verify_mfa_in_transaction(
    conn: sqlite3.Connection, *, user_id: str, code: str | None
) -> None:
    """Consume an enabled TOTP/recovery factor in the deletion transaction."""
    from mfa import backup_code_matches, resolve_totp_counter

    row = conn.execute(
        "SELECT secret, enabled, backup_codes FROM mfa_secrets WHERE user_id=?",
        (user_id,),
    ).fetchone()
    if row is None or int(row["enabled"] or 0) != 1:
        return
    candidate = (code or "").strip()
    if not candidate:
        raise AccountDeletionError(
            "mfa_reauthentication_required",
            "Enter a current authenticator or recovery code.",
        )
    try:
        step = resolve_totp_counter(str(row["secret"]), candidate)
    except (TypeError, ValueError, KeyError):
        step = None
    replay_columns = _table_columns(conn, "admin_mfa_replay_state")
    if step is not None:
        if replay_columns:
            replay = conn.execute(
                "SELECT last_accepted_totp_step FROM admin_mfa_replay_state "
                "WHERE owner_user_id=?",
                (user_id,),
            ).fetchone()
            if replay is not None and step <= int(replay[0]):
                raise AccountDeletionError(
                    "mfa_reauthentication_invalid",
                    "That authenticator code has already been used.",
                )
            conn.execute(
                """INSERT INTO admin_mfa_replay_state
                       (owner_user_id, last_accepted_totp_step, accepted_at)
                   VALUES (?, ?, datetime('now'))
                   ON CONFLICT(owner_user_id) DO UPDATE SET
                       last_accepted_totp_step=excluded.last_accepted_totp_step,
                       accepted_at=excluded.accepted_at""",
                (user_id, step),
            )
        return
    try:
        codes = json.loads(row["backup_codes"] or "[]")
    except (TypeError, ValueError):
        codes = []
    index = next(
        (i for i, stored in enumerate(codes) if backup_code_matches(stored, candidate)),
        None,
    )
    if index is None:
        raise AccountDeletionError(
            "mfa_reauthentication_invalid",
            "The authenticator or recovery code is invalid.",
        )
    del codes[index]
    conn.execute(
        "UPDATE mfa_secrets SET backup_codes=? WHERE user_id=?",
        (json.dumps(codes), user_id),
    )


def delete_account(
    database: Database,
    *,
    user_id: str,
    confirmation: str,
    password: str | None = None,
    mfa_code: str | None = None,
    verified_provider: str | None = None,
    verified_provider_subject: str | None = None,
    challenge_id: str | None = None,
    operation_token: str | None = None,
    provider_nonce: str | None = None,
    provider_issued_at: float | None = None,
    provider_revocation_payload: dict[str, Any] | None = None,
) -> DeletionResult:
    """Delete authentication data and anonymize records in one write transaction."""
    if confirmation != "DELETE":
        raise AccountDeletionError("confirmation_required", 'Enter "DELETE" to confirm.')

    tombstone_id = f"deleted-{secrets.token_hex(16)}"
    tombstone_password = hash_password(secrets.token_urlsafe(48))
    now = datetime.now(timezone.utc).isoformat()

    conn = database.connect(check_same_thread=False)
    try:
        conn.execute("BEGIN IMMEDIATE")
        user = conn.execute("SELECT * FROM users WHERE username=?", (user_id,)).fetchone()
        if user is None:
            raise AccountDeletionError("not_found", "Account not found.")
        role = str(user["role"])
        email = str(user["email"] or "") if "email" in user.keys() else ""
        name = str(user["name"] or "") if "name" in user.keys() else ""
        pseudonym_email = f"{tombstone_id}@invalid.example"
        sensitive_values = {user_id, email, name} - {""}
        if role == "owner":
            raise AccountDeletionError(
                "owner_not_supported",
                "Administrator ownership must be transferred before deleting this account.",
            )

        provider = str(user["provider"] or "password").strip().casefold()
        if provider in {"apple", "google"}:
            if verified_provider != provider or not verified_provider_subject:
                raise AccountDeletionError(
                    "provider_reauthentication_required",
                    f"Reauthenticate with {provider.title()} to delete this account.",
                )
            if not secrets.compare_digest(
                str(user["provider_uid"] or ""), verified_provider_subject
            ):
                raise AccountDeletionError(
                    "provider_identity_mismatch",
                    "The reauthenticated identity does not match this account.",
                )
        else:
            if not password or not verify_password(password, str(user["password_hash"])):
                raise AccountDeletionError(
                    "password_reauthentication_required",
                    "The current password is incorrect.",
                )

        from account_deletion_security import (
            DeletionSecurityError,
            consume_deletion_challenge,
        )

        try:
            consume_deletion_challenge(
                conn,
                challenge_id=challenge_id,
                user_id=user_id,
                provider=provider,
                operation_token=operation_token,
                provider_nonce=provider_nonce,
                provider_issued_at=provider_issued_at,
            )
        except DeletionSecurityError as error:
            raise AccountDeletionError(error.code, error.message) from error

        _verify_mfa_in_transaction(conn, user_id=user_id, code=mfa_code)
        if role == "professor":
            active_count = int(
                conn.execute(
                    """SELECT COUNT(*) FROM sessions
                       WHERE professor_user_id=? AND state IN ('creating', 'active')""",
                    (user_id,),
                ).fetchone()[0]
            )
            if active_count:
                raise AccountDeletionError(
                    "active_sessions_require_resolution",
                    "End every active classroom session before deleting this account.",
                )
        conn.execute(
            """INSERT INTO users (
                   username, password_hash, role, name, student_id, email,
                   department, provider, provider_uid, must_change_password,
                   status, disabled_at, disable_reason, created_at
               ) VALUES (?, ?, ?, ?, NULL, NULL, NULL, 'deleted', NULL, 0,
                         'deleted', ?, 'self_service_deletion', ?)""",
            (
                tombstone_id,
                tombstone_password,
                role,
                "Deleted User",
                now,
                now,
            ),
        )

        anonymized_teams = _anonymize_session_teams(
            conn, user_id=user_id, tombstone_id=tombstone_id
        )

        provider_revocation_job_id = None
        if provider_revocation_payload is not None:
            from account_deletion_security import enqueue_provider_revocation

            provider_revocation_job_id = enqueue_provider_revocation(
                conn,
                provider=provider,
                payload=provider_revocation_payload,
            )

        ended_sessions = 0
        conn.execute(
            "UPDATE classes SET is_active=0 WHERE professor_user_id=?", (user_id,)
        )

        # Remove credentials, active authorization, and direct tenant participation.
        for table, column in (
            ("refresh_tokens", "user_id"),
            ("password_reset_tokens", "user_id"),
            ("mfa_secrets", "user_id"),
            ("scim_users", "user_id"),
            ("auth_identities", "user_id"),

            ("memberships", "user_id"),
            ("class_enrollments", "student_user_id"),
            ("admin_v2_sessions", "owner_user_id"),
            ("admin_sessions", "owner_user_id"),
            ("admin_mfa_replay_state", "owner_user_id"),
            ("admin_mfa_challenges", "owner_user_id"),
            ("admin_recent_auth", "owner_user_id"),
        ):
            if column in _table_columns(conn, table):
                conn.execute(f'DELETE FROM "{table}" WHERE "{column}"=?', (user_id,))

        # Pseudonymize retained institutional, operational, and audit records.
        for table, column in (
            ("sessions", "created_by"),
            ("sessions", "professor_user_id"),
            ("classes", "professor_user_id"),
            ("organizations", "created_by"),
            ("session_create_requests", "professor_user_id"),
            ("announcements", "author_id"),
            ("audit_logs", "actor_username"),
            ("audit_events", "actor_user_id"),
            ("audit_events", "target_id"),
            ("professor_codes", "used_by"),
            ("professor_invitations", "issued_by"),
            ("professor_invitations", "revoked_by"),
            ("professor_invitations", "redeemed_by"),
            ("invitation_email_deliveries", "owner_id"),
            ("cleanup_plans", "created_by"),
            ("cleanup_plans", "executed_by"),
            ("users", "created_by"),
            ("users", "disabled_by"),
        ):
            if column in _table_columns(conn, table):
                conn.execute(
                    f'UPDATE "{table}" SET "{column}"=? WHERE "{column}"=?',
                    (tombstone_id, user_id),
                )
        if "author_name" in _table_columns(conn, "announcements"):
            conn.execute(
                "UPDATE announcements SET author_name='Deleted User' WHERE author_id=?",
                (tombstone_id,),
            )

        if email and "intended_email" in _table_columns(conn, "professor_invitations"):
            conn.execute(
                "UPDATE professor_invitations SET intended_email=? WHERE LOWER(intended_email)=LOWER(?)",
                (pseudonym_email, email),
            )
        if email and "recipient_email" in _table_columns(conn, "invitation_email_deliveries"):
            conn.execute(
                "UPDATE invitation_email_deliveries SET recipient_email=? WHERE LOWER(recipient_email)=LOWER(?)",
                (pseudonym_email, email),
            )

        audit_columns = _table_columns(conn, "audit_events")
        audit_json_columns = tuple(
            column
            for column in ("before_json", "after_json", "metadata_json")
            if column in audit_columns
        )
        if audit_json_columns:
            select_columns = ", ".join(("id", "actor_user_id", "target_id", *audit_json_columns))
            for row in conn.execute(f"SELECT {select_columns} FROM audit_events").fetchall():
                updates = {
                    column: _pseudonymize_json_text(
                        row[column],
                        sensitive_values=sensitive_values,
                        replacement=tombstone_id,
                    )
                    for column in audit_json_columns
                }
                assignments = [f"{column}=?" for column in audit_json_columns]
                values = [updates[column] for column in audit_json_columns]
                if row["actor_user_id"] == tombstone_id or row["target_id"] == tombstone_id:
                    for column in ("source_ip", "user_agent"):
                        if column in audit_columns:
                            assignments.append(f"{column}=NULL")
                conn.execute(
                    f"UPDATE audit_events SET {', '.join(assignments)} WHERE id=?",
                    (*values, row["id"]),
                )

        if _table_columns(conn, "admin_audit_events"):
            conn.execute("DROP TRIGGER IF EXISTS trg_admin_audit_events_no_update")
            for row in conn.execute(
                "SELECT id, actor_json, target_json, metadata_json FROM admin_audit_events"
            ).fetchall():
                values = [
                    _pseudonymize_json_text(
                        row[column],
                        sensitive_values=sensitive_values,
                        replacement=tombstone_id,
                    )
                    for column in ("actor_json", "target_json", "metadata_json")
                ]
                conn.execute(
                    """UPDATE admin_audit_events
                       SET actor_json=?, target_json=?, metadata_json=? WHERE id=?""",
                    (*values, row["id"]),
                )
            conn.execute("""
                CREATE TRIGGER trg_admin_audit_events_no_update
                BEFORE UPDATE ON admin_audit_events
                BEGIN
                    SELECT RAISE(ABORT, 'admin audit events are immutable');
                END
            """)

        from account_deletion_security import (
            mark_account_deleted,
            mark_bootstrap_professor_deleted,
        )

        mark_account_deleted(conn, user_id=user_id, deleted_at=now)
        configured_professor = os.environ.get(
            "PRACTENTURE_PROFESSOR_USERNAME", "professor"
        )
        if user_id == configured_professor:
            mark_bootstrap_professor_deleted(conn, deleted_at=now)
        conn.execute("DELETE FROM users WHERE username=?", (user_id,))

        if _table_columns(conn, "audit_events"):
            conn.execute(
                """INSERT INTO audit_events (
                       id, occurred_at, actor_user_id, actor_role, action,
                       target_type, target_id, request_id, reason, outcome,
                       metadata_json
                   ) VALUES (?, ?, ?, ?, 'account.self_delete', 'user', ?, ?,
                             'self_service_request', 'success', ?)""",
                (
                    secrets.token_hex(16),
                    now,
                    tombstone_id,
                    role,
                    tombstone_id,
                    secrets.token_hex(16),
                    json.dumps(
                        {
                            "endedSessions": ended_sessions,
                            "anonymizedTeams": anonymized_teams,
                        },
                        separators=(",", ":"),
                    ),
                ),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    # Durable SQLite state is authoritative; drop process-local snapshots that may
    # still contain the deleted identity or un-anonymized team data.
    database.sessions.clear()
    database.decisions.clear()
    database.announcements.clear()
    database.results.clear()
    database.team_states.clear()
    return DeletionResult(
        tombstone_id=tombstone_id,
        ended_sessions=ended_sessions,
        anonymized_teams=anonymized_teams,
        provider_revocation_job_id=provider_revocation_job_id,
    )
