"""Transactional persistence for opaque Admin V2 sessions and login throttles.

Schema ownership belongs exclusively to Alembic revision 003.  This module never
creates or evolves tables at import/runtime.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hmac
import hashlib
import ipaddress
import json
import math
import sqlite3
from typing import Any
from uuid import uuid4

from admin_v2.errors import AdminError
from admin_v2.redaction import redact_secrets
from database import db


@dataclass(frozen=True)
class AdminSessionRecord:
    id: str
    token_hash: str
    csrf_token_hash: str
    owner_user_id: str
    role: str
    created_at: str
    last_seen_at: str
    idle_expires_at: str
    absolute_expires_at: str
    revoked_at: str | None
    revocation_reason: str | None


@dataclass(frozen=True)
class LoginAttemptDecision:
    allowed: bool
    retry_after: int = 0
    client_window_started_at: float | None = None
    lock_created: bool = False


class AdminSessionRepository:
    def __init__(self, database=db) -> None:
        self._db = database

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        """Run one unit of work on a connection owned by this transaction."""
        conn = self._db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def normalize_identity(identity: str) -> str:
        return identity.strip().casefold()

    @staticmethod
    def normalize_client_signal(signal: str | None) -> str:
        value = (signal or "unknown").strip()
        try:
            return ipaddress.ip_address(value).compressed.casefold()
        except ValueError:
            return value.casefold() or "unknown"

    @staticmethod
    def pair_scope_key(identity_key: str, client_key: str) -> str:
        """Return an unambiguous opaque key for a normalized identity/client pair."""
        return hashlib.sha256(f"{identity_key}\0{client_key}".encode()).hexdigest()

    def reserve_login_attempt(
        self,
        identity: str,
        client_signal: str | None,
        *,
        now: float,
        threshold: int,
        window_seconds: int,
        identity_threshold: int = 20,
        client_threshold: int = 50,
        identity_window_seconds: int | None = None,
        client_window_seconds: int | None = None,
        include_client_scopes: bool = True,
    ) -> LoginAttemptDecision:
        """Reserve pair, identity, and client budgets in one write transaction."""
        identity_key = self.normalize_identity(identity)
        client_key = self.normalize_client_signal(client_signal)
        identity_window = identity_window_seconds or window_seconds
        client_window = client_window_seconds or window_seconds
        dimensions = [
            ("identity", identity_key, identity_threshold, identity_window),
        ]
        if include_client_scopes:
            dimensions.extend(
                (
                    ("pair", self.pair_scope_key(identity_key, client_key), threshold, window_seconds),
                    ("client", client_key, client_threshold, client_window),
                )
            )

        with self._transaction() as conn:
            # Indexed bounded retention: never delete a still-active lock.
            retention = 2 * max(window_seconds, identity_window, client_window)
            conn.execute(
                """DELETE FROM privileged_login_buckets
                   WHERE last_attempt_at < ?
                     AND (locked_until IS NULL OR locked_until <= ?)""",
                (now - retention, now),
            )

            states: list[tuple[str, str, int, int, sqlite3.Row | None]] = []
            retry_after = 0
            for scope_type, scope_key, limit, window in dimensions:
                row = conn.execute(
                    """SELECT attempt_count, window_started_at, locked_until
                       FROM privileged_login_buckets
                       WHERE scope_type=? AND scope_key=?""",
                    (scope_type, scope_key),
                ).fetchone()
                states.append((scope_type, scope_key, limit, window, row))
                if row and row[2] is not None and float(row[2]) > now:
                    retry_after = max(retry_after, math.ceil(float(row[2]) - now))

            # A blocked reservation mutates no dimension. Retry-After reflects the
            # longest active bucket rather than whichever scope was read first.
            if retry_after:
                return LoginAttemptDecision(False, max(1, retry_after))

            client_window_started_at = now
            lock_created = False
            for scope_type, scope_key, limit, window, row in states:
                if row is None or now >= float(row[1]) + window:
                    attempt_count = 1
                    window_started_at = now
                else:
                    attempt_count = int(row[0]) + 1
                    window_started_at = float(row[1])
                locked_until = now + window if attempt_count >= limit else None
                lock_created = lock_created or locked_until is not None
                conn.execute(
                    """INSERT INTO privileged_login_buckets
                           (scope_type, scope_key, attempt_count, window_started_at,
                            locked_until, last_attempt_at)
                       VALUES (?, ?, ?, ?, ?, ?)
                       ON CONFLICT(scope_type, scope_key) DO UPDATE SET
                           attempt_count=excluded.attempt_count,
                           window_started_at=excluded.window_started_at,
                           locked_until=excluded.locked_until,
                           last_attempt_at=excluded.last_attempt_at""",
                    (
                        scope_type,
                        scope_key,
                        attempt_count,
                        window_started_at,
                        locked_until,
                        now,
                    ),
                )
                if scope_type == "client":
                    client_window_started_at = window_started_at
            return LoginAttemptDecision(
                True,
                client_window_started_at=client_window_started_at,
                lock_created=lock_created,
            )

    def _reset_login_attempt(
        self,
        conn,
        identity: str,
        client_signal: str | None,
        *,
        client_window_started_at: float | None,
    ) -> None:
        identity_key = self.normalize_identity(identity)
        client_key = self.normalize_client_signal(client_signal)
        conn.execute(
            """DELETE FROM privileged_login_buckets
               WHERE (scope_type='identity' AND scope_key=?)
                  OR (scope_type='pair' AND scope_key=?)""",
            (identity_key, self.pair_scope_key(identity_key, client_key)),
        )
        if client_window_started_at is not None:
            # Remove exactly this successful request's client-wide reservation;
            # unrelated identities' failures on this client remain counted.
            conn.execute(
                """UPDATE privileged_login_buckets
                   SET attempt_count=attempt_count-1, locked_until=NULL
                   WHERE scope_type='client' AND scope_key=?
                     AND window_started_at=? AND attempt_count > 0""",
                (client_key, client_window_started_at),
            )
            conn.execute(
                """DELETE FROM privileged_login_buckets
                   WHERE scope_type='client' AND scope_key=?
                     AND window_started_at=? AND attempt_count=0""",
                (client_key, client_window_started_at),
            )

    def create_after_mfa(
        self,
        *,
        session_id: str,
        token_hash: str,
        csrf_hash: str,
        user_id: str,
        role: str,
        created_at: str,
        idle_expires_at: str,
        absolute_expires_at: str,
        mfa_code: str | None,
        login_identity: str,
        client_signal: str | None,
        client_window_started_at: float | None = None,
        replacement_token_hash: str | None = None,
    ) -> str:
        """Verify/consume MFA and create exactly one session in one transaction.

        Returns ``created``, ``mfa_required``, ``invalid_mfa``, or
        ``mfa_replayed``. Backup-code
        consumption is rolled back if session insertion fails.
        """
        from mfa import backup_code_matches, resolve_totp_counter

        with self._transaction() as conn:
            mfa_row = conn.execute(
                "SELECT secret, enabled, backup_codes FROM mfa_secrets WHERE user_id=?",
                (user_id,),
            ).fetchone()
            if mfa_row is not None and int(mfa_row[1] or 0) == 1:
                candidate = (mfa_code or "").strip().replace(" ", "")
                if not candidate:
                    return "mfa_required"

                accepted_totp_step = None
                try:
                    accepted_totp_step = resolve_totp_counter(
                        str(mfa_row[0]), candidate
                    )
                except (TypeError, ValueError, KeyError):
                    accepted_totp_step = None

                if accepted_totp_step is not None:
                    replay_row = conn.execute(
                        """SELECT last_accepted_totp_step
                           FROM admin_mfa_replay_state WHERE owner_user_id=?""",
                        (user_id,),
                    ).fetchone()
                    if replay_row is not None and accepted_totp_step <= int(replay_row[0]):
                        return "mfa_replayed"
                    conn.execute(
                        """INSERT INTO admin_mfa_replay_state
                               (owner_user_id, last_accepted_totp_step, accepted_at)
                           VALUES (?, ?, ?)
                           ON CONFLICT(owner_user_id) DO UPDATE SET
                               last_accepted_totp_step=excluded.last_accepted_totp_step,
                               accepted_at=excluded.accepted_at""",
                        (user_id, accepted_totp_step, created_at),
                    )
                else:
                    try:
                        backup_codes = json.loads(mfa_row[2] or "[]")
                    except (TypeError, ValueError):
                        backup_codes = []
                    matched_index = next(
                        (
                            index
                            for index, code in enumerate(backup_codes)
                            if isinstance(code, str)
                            and backup_code_matches(code, candidate)
                        ),
                        None,
                    )
                    if matched_index is None:
                        return "invalid_mfa"
                    del backup_codes[matched_index]
                    conn.execute(
                        "UPDATE mfa_secrets SET backup_codes=? WHERE user_id=?",
                        (json.dumps(backup_codes), user_id),
                    )

            now = created_at
            if replacement_token_hash is not None:
                # Rotation is scoped to the valid session credential presented by
                # this request.  An absent, unknown, revoked, or differently owned
                # credential never invalidates another session.
                conn.execute(
                    """UPDATE admin_sessions
                       SET revoked_at=?, revocation_reason='login_rotation'
                       WHERE token_hash=? AND owner_user_id=? AND revoked_at IS NULL""",
                    (now, replacement_token_hash, user_id),
                )
            conn.execute(
                """INSERT INTO admin_sessions
                   (id, token_hash, csrf_token_hash, owner_user_id, role,
                    created_at, last_seen_at, idle_expires_at,
                    absolute_expires_at, revoked_at, revocation_reason)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)""",
                (
                    session_id,
                    token_hash,
                    csrf_hash,
                    user_id,
                    role,
                    now,
                    now,
                    idle_expires_at,
                    absolute_expires_at,
                ),
            )
            self._reset_login_attempt(
                conn,
                login_identity,
                client_signal,
                client_window_started_at=client_window_started_at,
            )
            return "created"

    @staticmethod
    def _verify_mfa_in_transaction(
        conn: sqlite3.Connection, user_id: str, code: str | None, accepted_at: str
    ) -> str:
        """Verify and consume a privileged MFA credential in the caller's transaction."""
        from mfa import backup_code_matches, resolve_totp_counter

        row = conn.execute(
            "SELECT secret, enabled, backup_codes FROM mfa_secrets WHERE user_id=?",
            (user_id,),
        ).fetchone()
        if row is None or int(row[1] or 0) != 1:
            return "not_required"
        candidate = (code or "").strip().replace(" ", "")
        if not candidate:
            return "mfa_required"
        try:
            step = resolve_totp_counter(str(row[0]), candidate)
        except (TypeError, ValueError, KeyError):
            step = None
        if step is not None:
            replay = conn.execute(
                "SELECT last_accepted_totp_step FROM admin_mfa_replay_state WHERE owner_user_id=?",
                (user_id,),
            ).fetchone()
            if replay is not None and step <= int(replay[0]):
                return "mfa_replayed"
            conn.execute(
                """INSERT INTO admin_mfa_replay_state
                       (owner_user_id, last_accepted_totp_step, accepted_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(owner_user_id) DO UPDATE SET
                       last_accepted_totp_step=excluded.last_accepted_totp_step,
                       accepted_at=excluded.accepted_at""",
                (user_id, step, accepted_at),
            )
            return "accepted"
        try:
            codes = json.loads(row[2] or "[]")
        except (TypeError, ValueError):
            codes = []
        index = next(
            (i for i, value in enumerate(codes) if isinstance(value, str) and backup_code_matches(value, candidate)),
            None,
        )
        if index is None:
            return "invalid_mfa"
        del codes[index]
        conn.execute(
            "UPDATE mfa_secrets SET backup_codes=? WHERE user_id=?",
            (json.dumps(codes), user_id),
        )
        return "accepted"

    def create_mfa_challenge(
        self, *, challenge_id: str, token_hash: str, user_id: str,
        created_at: str, expires_at: str,
    ) -> None:
        with self._transaction() as conn:
            conn.execute(
                "DELETE FROM admin_mfa_challenges WHERE expires_at<=? OR owner_user_id=?",
                (created_at, user_id),
            )
            conn.execute(
                """INSERT INTO admin_mfa_challenges
                       (id, token_hash, owner_user_id, created_at, expires_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (challenge_id, token_hash, user_id, created_at, expires_at),
            )

    def active_mfa_challenge_owner(self, token_hash: str, now: str) -> str | None:
        conn = self._db.connect()
        try:
            row = conn.execute(
                """SELECT owner_user_id FROM admin_mfa_challenges
                   WHERE token_hash=? AND consumed_at IS NULL AND expires_at>?""",
                (token_hash, now),
            ).fetchone()
            return str(row[0]) if row is not None else None
        finally:
            conn.close()

    def invalidate_mfa_challenge(self, token_hash: str) -> None:
        with self._transaction() as conn:
            conn.execute(
                "DELETE FROM admin_mfa_challenges WHERE token_hash=? AND consumed_at IS NULL",
                (token_hash,),
            )

    def create_from_mfa_challenge(
        self, *, challenge_token_hash: str, mfa_code: str, session_id: str,
        token_hash: str, csrf_hash: str, created_at: str,
        idle_expires_at: str, absolute_expires_at: str,
    ) -> tuple[str, str | None]:
        """Consume one challenge/MFA credential and create one session atomically."""
        with self._transaction() as conn:
            challenge = conn.execute(
                """SELECT owner_user_id FROM admin_mfa_challenges
                   WHERE token_hash=? AND consumed_at IS NULL AND expires_at>?""",
                (challenge_token_hash, created_at),
            ).fetchone()
            if challenge is None:
                return "invalid_challenge", None
            user_id = str(challenge[0])
            mfa_status = self._verify_mfa_in_transaction(conn, user_id, mfa_code, created_at)
            if mfa_status not in {"accepted", "not_required"}:
                return mfa_status, None
            consumed = conn.execute(
                """UPDATE admin_mfa_challenges SET consumed_at=?
                   WHERE token_hash=? AND consumed_at IS NULL""",
                (created_at, challenge_token_hash),
            )
            if consumed.rowcount != 1:
                return "invalid_challenge", None
            conn.execute(
                """INSERT INTO admin_sessions
                   (id, token_hash, csrf_token_hash, owner_user_id, role,
                    created_at, last_seen_at, idle_expires_at, absolute_expires_at)
                   VALUES (?, ?, ?, ?, 'owner', ?, ?, ?, ?)""",
                (session_id, token_hash, csrf_hash, user_id, created_at, created_at,
                 idle_expires_at, absolute_expires_at),
            )
            return "created", user_id

    def record_recent_auth(
        self, *, session_id: str, user_id: str, mfa_code: str | None, authenticated_at: str,
    ) -> str:
        with self._transaction() as conn:
            active = conn.execute(
                """SELECT 1 FROM admin_sessions
                   WHERE id=? AND owner_user_id=? AND revoked_at IS NULL
                     AND idle_expires_at>? AND absolute_expires_at>?""",
                (session_id, user_id, authenticated_at, authenticated_at),
            ).fetchone()
            if active is None:
                return "invalid_session"
            status = self._verify_mfa_in_transaction(conn, user_id, mfa_code, authenticated_at)
            if status not in {"accepted", "not_required"}:
                return status
            conn.execute(
                """INSERT INTO admin_recent_auth (session_id, authenticated_at)
                   VALUES (?, ?) ON CONFLICT(session_id) DO UPDATE SET
                   authenticated_at=excluded.authenticated_at""",
                (session_id, authenticated_at),
            )
            return "accepted"

    def has_recent_auth(self, session_id: str, not_before: str) -> bool:
        conn = self._db.connect()
        try:
            return conn.execute(
                "SELECT 1 FROM admin_recent_auth WHERE session_id=? AND authenticated_at>=?",
                (session_id, not_before),
            ).fetchone() is not None
        finally:
            conn.close()

    def touch_active(
        self, token_hash: str, *, now: datetime, idle_expires_at: str
    ) -> tuple[AdminSessionRecord | None, str]:
        """Conditionally touch and read an active session atomically."""
        now = now.astimezone(timezone.utc)
        now_iso = now.isoformat()
        with self._transaction() as conn:
            row = conn.execute(
                "SELECT * FROM admin_sessions WHERE token_hash=?", (token_hash,)
            ).fetchone()
            if row is None or row[9] is not None:
                return None, "missing"
            if row[7] <= now_iso or row[8] <= now_iso:
                conn.execute(
                    """UPDATE admin_sessions
                       SET revoked_at=?, revocation_reason='expired'
                       WHERE token_hash=? AND revoked_at IS NULL""",
                    (now_iso, token_hash),
                )
                return None, "expired"
            updated = conn.execute(
                """UPDATE admin_sessions
                   SET last_seen_at=CASE
                           WHEN last_seen_at > ? THEN last_seen_at ELSE ? END,
                       idle_expires_at=CASE
                           WHEN idle_expires_at > ? THEN idle_expires_at ELSE ? END
                   WHERE token_hash=? AND revoked_at IS NULL
                     AND idle_expires_at>? AND absolute_expires_at>?""",
                (
                    now_iso,
                    now_iso,
                    idle_expires_at,
                    idle_expires_at,
                    token_hash,
                    now_iso,
                    now_iso,
                ),
            )
            if updated.rowcount != 1:
                return None, "missing"
            active = conn.execute(
                "SELECT * FROM admin_sessions WHERE token_hash=? AND revoked_at IS NULL",
                (token_hash,),
            ).fetchone()
            if active is None:
                return None, "missing"
            return AdminSessionRecord(**dict(active)), "active"

    def revoke(self, token_hash: str, revoked_at: str, reason: str) -> bool:
        with self._transaction() as conn:
            result = conn.execute(
                """UPDATE admin_sessions
                   SET revoked_at=?, revocation_reason=?
                   WHERE token_hash=? AND revoked_at IS NULL""",
                (revoked_at, reason, token_hash),
            )
            return result.rowcount == 1

    def count_for_user(self, user_id: str, *, active_only: bool = False) -> int:
        query = "SELECT COUNT(*) FROM admin_sessions WHERE owner_user_id=?"
        if active_only:
            query += " AND revoked_at IS NULL"
        conn = self._db.connect()
        try:
            row = conn.execute(query, (user_id,)).fetchone()
            return int(row[0])
        finally:
            conn.close()


@dataclass(frozen=True)
class StoredResponse:
    """The exact HTTP result retained for deterministic idempotent replay."""

    status_code: int
    body: Any
    headers: Mapping[str, str]


@dataclass(frozen=True)
class AuditEventRecord:
    id: str
    request_id: str
    actor: Any
    target: Any
    action: str
    outcome: str
    metadata: Any
    timestamp: str


@dataclass(frozen=True)
class MutationExecution:
    response: StoredResponse
    replayed: bool
    audit_event_id: str


def _canonical_json(value: Any) -> str:
    """Serialize a JSON API value deterministically and reject ambiguous values."""
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("value must be finite JSON data") from exc


def fingerprint_request(value: Any) -> str:
    """Return a non-reversible fingerprint without retaining request secrets."""
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


class AdminMutationRepository:
    """Own one SQLite transaction for mutation, audit, and idempotency state.

    ``BEGIN IMMEDIATE`` serializes contenders before reading a scoped key. The
    reservation is deliberately not committed separately: if business logic or
    audit persistence fails, SQLite removes the effect and reservation together.
    """

    DEFAULT_TTL_SECONDS = 24 * 60 * 60
    MIN_TTL_SECONDS = 60
    MAX_TTL_SECONDS = 7 * 24 * 60 * 60
    MAX_KEY_LENGTH = 255
    MAX_ROUTE_LENGTH = 512

    def __init__(self, database=db) -> None:
        self._db = database

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self._db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _validate_scope(owner_id: str, route: str, idempotency_key: str) -> None:
        if not owner_id or not owner_id.strip():
            raise ValueError("owner_id is required")
        if not route or len(route) > AdminMutationRepository.MAX_ROUTE_LENGTH:
            raise ValueError("route is required and must be at most 512 characters")
        if not idempotency_key or len(idempotency_key) > AdminMutationRepository.MAX_KEY_LENGTH:
            raise AdminError(
                400,
                "ADMIN_IDEMPOTENCY_KEY_INVALID",
                "Idempotency-Key must be between 1 and 255 characters",
            )

    @staticmethod
    def _normalize_response(response: StoredResponse) -> tuple[StoredResponse, str, str]:
        if not isinstance(response, StoredResponse):
            raise TypeError("mutation must return StoredResponse")
        if not 100 <= response.status_code <= 599:
            raise ValueError("response status must be a valid HTTP status code")
        headers = {str(key): str(value) for key, value in response.headers.items()}
        body_json = _canonical_json(response.body)
        headers_json = _canonical_json(headers)
        normalized = StoredResponse(
            status_code=response.status_code,
            body=json.loads(body_json),
            headers=json.loads(headers_json),
        )
        return normalized, body_json, headers_json

    @staticmethod
    def _insert_audit(
        conn: sqlite3.Connection,
        *,
        request_id: str,
        actor: Any,
        target: Any,
        action: str,
        outcome: str,
        metadata: Any,
        timestamp: str,
    ) -> str:
        event_id = f"audit_{uuid4()}"
        conn.execute(
            """INSERT INTO admin_audit_events (
                   id, request_id, actor_json, target_json, action, outcome,
                   metadata_json, occurred_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event_id,
                request_id,
                _canonical_json(redact_secrets(actor)),
                _canonical_json(redact_secrets(target)),
                action,
                outcome,
                _canonical_json(redact_secrets(metadata)),
                timestamp,
            ),
        )
        return event_id

    def execute(
        self,
        *,
        request_id: str,
        actor: Any,
        target: Any,
        action: str,
        outcome: str,
        metadata: Any,
        mutation: Callable[[sqlite3.Connection], StoredResponse],
        now: datetime | None = None,
    ) -> MutationExecution:
        """Execute a non-idempotent mutation with its audit event atomically."""
        timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
        with self._transaction() as conn:
            response, _, _ = self._normalize_response(mutation(conn))
            event_id = self._insert_audit(
                conn,
                request_id=request_id,
                actor=actor,
                target=target,
                action=action,
                outcome=outcome,
                metadata=metadata,
                timestamp=timestamp,
            )
            return MutationExecution(response, False, event_id)

    def execute_idempotent(
        self,
        *,
        owner_id: str,
        route: str,
        idempotency_key: str,
        request_fingerprint: str,
        request_id: str,
        actor: Any,
        target: Any,
        action: str,
        outcome: str,
        metadata: Any,
        mutation: Callable[[sqlite3.Connection], StoredResponse],
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        now: datetime | None = None,
    ) -> MutationExecution:
        """Reserve, mutate, audit, and finalize one owner/route/key atomically."""
        self._validate_scope(owner_id, route, idempotency_key)
        if len(request_fingerprint) != 64 or any(
            char not in "0123456789abcdef" for char in request_fingerprint
        ):
            raise ValueError("request_fingerprint must be a lowercase SHA-256 digest")
        if not self.MIN_TTL_SECONDS <= ttl_seconds <= self.MAX_TTL_SECONDS:
            raise ValueError("idempotency TTL must be between 60 and 604800 seconds")

        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        current_iso = current.isoformat()
        expires_at = (current + timedelta(seconds=ttl_seconds)).isoformat()
        key_hash = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()

        with self._transaction() as conn:
            # Keep expiry cleanup bounded so a request cannot become a table sweep.
            conn.execute(
                """DELETE FROM admin_idempotency_records
                   WHERE rowid IN (
                       SELECT rowid FROM admin_idempotency_records
                       WHERE expires_at <= ? LIMIT 100
                   )""",
                (current_iso,),
            )
            row = conn.execute(
                """SELECT request_fingerprint, state, response_status,
                          response_body_json, response_headers_json, audit_event_id
                   FROM admin_idempotency_records
                   WHERE owner_id=? AND route=? AND key_hash=?""",
                (owner_id, route, key_hash),
            ).fetchone()
            if row is not None:
                if row[0] != request_fingerprint:
                    raise AdminError(
                        409,
                        "ADMIN_IDEMPOTENCY_CONFLICT",
                        "Idempotency key was already used for a different request",
                    )
                if row[1] == "in_progress":
                    raise AdminError(
                        409,
                        "ADMIN_IDEMPOTENCY_IN_PROGRESS",
                        "An identical request is still in progress",
                        headers={"Retry-After": "1"},
                    )
                return MutationExecution(
                    StoredResponse(
                        status_code=int(row[2]),
                        body=json.loads(row[3]),
                        headers=json.loads(row[4]),
                    ),
                    True,
                    str(row[5]),
                )

            conn.execute(
                """INSERT INTO admin_idempotency_records (
                       owner_id, route, key_hash, request_fingerprint, state,
                       created_at, expires_at
                   ) VALUES (?, ?, ?, ?, 'in_progress', ?, ?)""",
                (
                    owner_id,
                    route,
                    key_hash,
                    request_fingerprint,
                    current_iso,
                    expires_at,
                ),
            )
            response, body_json, headers_json = self._normalize_response(mutation(conn))
            event_id = self._insert_audit(
                conn,
                request_id=request_id,
                actor=actor,
                target=target,
                action=action,
                outcome=outcome,
                metadata=metadata,
                timestamp=current_iso,
            )
            updated = conn.execute(
                """UPDATE admin_idempotency_records
                   SET state='completed', response_status=?, response_body_json=?,
                       response_headers_json=?, audit_event_id=?, completed_at=?
                   WHERE owner_id=? AND route=? AND key_hash=? AND state='in_progress'""",
                (
                    response.status_code,
                    body_json,
                    headers_json,
                    event_id,
                    current_iso,
                    owner_id,
                    route,
                    key_hash,
                ),
            )
            if updated.rowcount != 1:
                raise RuntimeError("idempotency reservation finalization failed")
            return MutationExecution(response, False, event_id)

    def get_audit_event(self, event_id: str) -> AuditEventRecord | None:
        conn = self._db.connect()
        try:
            row = conn.execute(
                """SELECT id, request_id, actor_json, target_json, action, outcome,
                          metadata_json, occurred_at
                   FROM admin_audit_events WHERE id=?""",
                (event_id,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return AuditEventRecord(
            id=row[0],
            request_id=row[1],
            actor=json.loads(row[2]),
            target=json.loads(row[3]),
            action=row[4],
            outcome=row[5],
            metadata=json.loads(row[6]),
            timestamp=row[7],
        )
