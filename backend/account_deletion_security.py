"""Durable proof challenges, throttling, and provider-revocation jobs."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class DeletionSecurityError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _identity_digest(value: str) -> str:
    return hmac.new(
        _encryption_key(), value.casefold().encode("utf-8"), hashlib.sha256
    ).hexdigest()


def create_deletion_challenge(database, *, user_id: str, provider: str) -> dict[str, Any]:
    now = time.time()
    challenge = secrets.token_urlsafe(32)
    challenge_id = f"adc_{secrets.token_urlsafe(18)}"
    nonce_hash = _digest(challenge)
    user_id_hash = _identity_digest(user_id)
    with database.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "DELETE FROM account_deletion_challenges WHERE user_id_hash=? OR expires_at<?",
            (user_id_hash, now),
        )
        conn.execute(
            """INSERT INTO account_deletion_challenges
               (id, user_id_hash, provider, nonce_hash, issued_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (challenge_id, user_id_hash, provider, nonce_hash, now, now + 300),
        )
        conn.commit()
    return {
        "challengeId": challenge_id,
        "challenge": challenge,
        "operationToken": challenge,
        "issuedAt": now,
        "expiresAt": now + 300,
    }


def consume_deletion_challenge(
    conn,
    *,
    challenge_id: str | None,
    user_id: str,
    provider: str,
    operation_token: str | None,
    provider_nonce: str | None,
    provider_issued_at: float | None,
) -> None:
    if not challenge_id:
        raise DeletionSecurityError(
            "deletion_challenge_required",
            "Start account deletion again to obtain a fresh security challenge.",
        )
    now = time.time()
    row = conn.execute(
        """SELECT * FROM account_deletion_challenges
           WHERE id=? AND user_id_hash=? AND provider=? AND consumed_at IS NULL""",
        (challenge_id, _identity_digest(user_id), provider),
    ).fetchone()
    if row is None or float(row["expires_at"]) < now:
        raise DeletionSecurityError(
            "deletion_challenge_invalid",
            "The account-deletion challenge expired. Start again.",
        )
    if not operation_token or not secrets.compare_digest(
        str(row["nonce_hash"]), _digest(operation_token)
    ):
        raise DeletionSecurityError(
            "deletion_challenge_invalid",
            "The account-deletion challenge is invalid. Start again.",
        )
    if provider == "apple":
        if not provider_nonce or not secrets.compare_digest(
            str(row["nonce_hash"]), provider_nonce
        ):
            raise DeletionSecurityError(
                "provider_nonce_mismatch",
                "Apple reauthentication was not bound to this deletion request.",
            )
    elif provider == "google":
        if provider_issued_at is None or provider_issued_at < float(row["issued_at"]) - 60:
            raise DeletionSecurityError(
                "provider_token_not_fresh",
                "Sign in with Google again to confirm account deletion.",
            )
    updated = conn.execute(
        """UPDATE account_deletion_challenges SET consumed_at=?, expires_at=?
           WHERE id=? AND consumed_at IS NULL""",
        (now, now + 86400, challenge_id),
    )
    if updated.rowcount != 1:
        raise DeletionSecurityError(
            "deletion_challenge_replayed",
            "This account-deletion challenge was already used. Start again.",
        )


def account_deletion_status(database, *, operation_token: str) -> str | None:
    """Resolve an opaque deletion receipt without exposing account identity."""
    if len(operation_token) < 32:
        return None
    with database.connect() as conn:
        row = conn.execute(
            """SELECT consumed_at FROM account_deletion_challenges
               WHERE nonce_hash=? AND expires_at>=?""",
            (_digest(operation_token), time.time()),
        ).fetchone()
    if row is None:
        return None
    return "completed" if row["consumed_at"] is not None else "pending"


def validate_provider_security_configuration() -> None:
    material = os.environ.get("PRACTENTURE_PROVIDER_JOB_ENCRYPTION_KEY", "")
    if len(material) < 32:
        raise RuntimeError(
            "PRACTENTURE_PROVIDER_JOB_ENCRYPTION_KEY must be configured with "
            "at least 32 characters and preserved independently of JWT rotation"
        )


def _encryption_key() -> bytes:
    validate_provider_security_configuration()
    material = os.environ["PRACTENTURE_PROVIDER_JOB_ENCRYPTION_KEY"]
    return hashlib.sha256(material.encode("utf-8")).digest()


def mark_account_deleted(conn, *, user_id: str, deleted_at: float | str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO account_deletion_markers (user_id_hash, deleted_at) VALUES (?, ?)",
        (_identity_digest(user_id), deleted_at),
    )


def was_account_deleted(database, *, user_id: str) -> bool:
    with database.connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM account_deletion_markers WHERE user_id_hash=?",
            (_identity_digest(user_id),),
        ).fetchone()
    return row is not None


_BOOTSTRAP_PROFESSOR_MARKER = "bootstrap-professor-deleted-v1"


def mark_bootstrap_professor_deleted(conn, *, deleted_at: float | str) -> None:
    """Persist bootstrap suppression independently of rotatable application keys."""
    conn.execute(
        "INSERT OR REPLACE INTO account_deletion_markers (user_id_hash, deleted_at) VALUES (?, ?)",
        (_BOOTSTRAP_PROFESSOR_MARKER, deleted_at),
    )


def was_bootstrap_professor_deleted(database) -> bool:
    with database.connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM account_deletion_markers WHERE user_id_hash=?",
            (_BOOTSTRAP_PROFESSOR_MARKER,),
        ).fetchone()
    return row is not None


def _encrypt_payload(payload: dict[str, Any]) -> str:
    nonce = os.urandom(12)
    plaintext = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ciphertext = AESGCM(_encryption_key()).encrypt(
        nonce, plaintext, b"practenture-provider-revocation-v1"
    )
    return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def _decrypt_payload(ciphertext: str) -> dict[str, Any]:
    raw = base64.urlsafe_b64decode(ciphertext.encode("ascii"))
    plaintext = AESGCM(_encryption_key()).decrypt(
        raw[:12], raw[12:], b"practenture-provider-revocation-v1"
    )
    decoded = json.loads(plaintext)
    if not isinstance(decoded, dict):
        raise ValueError("Invalid provider revocation payload")
    return decoded


def enqueue_provider_revocation(conn, *, provider: str, payload: dict[str, Any]) -> str:
    job_id = f"prj_{secrets.token_urlsafe(18)}"
    now = time.time()
    conn.execute(
        """INSERT INTO provider_revocation_jobs
           (id, provider, payload_ciphertext, status, attempts, next_attempt_at, created_at)
           VALUES (?, ?, ?, 'pending', 0, ?, ?)""",
        (job_id, provider, _encrypt_payload(payload), now, now),
    )
    return job_id


def process_provider_revocation_job(database, job_id: str) -> bool:
    now = time.time()
    lease_token = secrets.token_urlsafe(24)
    with database.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """SELECT * FROM provider_revocation_jobs
               WHERE id=? AND status IN ('pending', 'processing') AND next_attempt_at<=?""",
            (job_id, now),
        ).fetchone()
        if row is None:
            conn.rollback()
            completed = conn.execute(
                "SELECT status FROM provider_revocation_jobs WHERE id=?", (job_id,)
            ).fetchone()
            return bool(completed and completed["status"] == "completed")
        claimed = conn.execute(
            """UPDATE provider_revocation_jobs
               SET status='processing', attempts=attempts+1, next_attempt_at=?, lease_token=?
               WHERE id=? AND status IN ('pending', 'processing') AND next_attempt_at<=?""",
            (now + 60, lease_token, job_id, now),
        )
        if claimed.rowcount != 1:
            conn.rollback()
            return False
        payload_ciphertext = str(row["payload_ciphertext"])
        provider = str(row["provider"])
        attempts = int(row["attempts"]) + 1
        conn.commit()

    try:
        payload = _decrypt_payload(payload_ciphertext)
        if provider == "apple":
            from apple_token_revocation import revoke_apple_tokens

            revoke_apple_tokens(payload)
        else:
            raise ValueError(f"Unsupported revocation provider: {provider}")
    except Exception as exc:
        delay = min(3600, 30 * (2 ** min(attempts - 1, 7)))
        with database.connect() as conn:
            conn.execute(
                """UPDATE provider_revocation_jobs
                   SET status='pending', next_attempt_at=?, last_error=?, lease_token=NULL
                   WHERE id=? AND status='processing' AND lease_token=?""",
                (time.time() + delay, str(exc)[:500], job_id, lease_token),
            )
            conn.commit()
        return False

    with database.connect() as conn:
        completed = conn.execute(
            """UPDATE provider_revocation_jobs
               SET status='completed', payload_ciphertext='', last_error=NULL,
                   completed_at=?, next_attempt_at=?, lease_token=NULL
               WHERE id=? AND status='processing' AND lease_token=?""",
            (time.time(), time.time(), job_id, lease_token),
        )
        conn.commit()
    if completed.rowcount == 1:
        return True
    with database.connect() as conn:
        row = conn.execute(
            "SELECT status FROM provider_revocation_jobs WHERE id=?", (job_id,)
        ).fetchone()
    return bool(row and row["status"] == "completed")


def process_pending_provider_revocations(database, *, limit: int = 20) -> dict[str, int]:
    now = time.time()
    with database.connect() as conn:
        conn.execute(
            "DELETE FROM account_deletion_challenges WHERE expires_at<?", (now,)
        )
        conn.commit()
        rows = conn.execute(
            """SELECT id FROM provider_revocation_jobs
               WHERE status IN ('pending', 'processing') AND next_attempt_at<=?
               ORDER BY created_at LIMIT ?""",
            (now, limit),
        ).fetchall()
    completed = 0
    for row in rows:
        completed += int(process_provider_revocation_job(database, str(row["id"])))
    return {"attempted": len(rows), "completed": completed}


def _throttle_scopes(user_id: str, client_signal: str) -> tuple[str, str]:
    return (
        "account:" + _digest(user_id.casefold()),
        "pair:" + _digest(user_id.casefold() + "\0" + client_signal),
    )


def reserve_deletion_attempt(database, *, user_id: str, client_signal: str) -> None:
    now = time.time()
    scopes = _throttle_scopes(user_id, client_signal)
    with database.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        rows = {
            row["scope_key"]: row
            for row in conn.execute(
                "SELECT * FROM protected_action_throttles WHERE scope_key IN (?, ?)",
                scopes,
            ).fetchall()
        }
        for scope in scopes:
            row = rows.get(scope)
            if row and float(row["blocked_until"] or 0) > now:
                conn.rollback()
                raise DeletionSecurityError(
                    "deletion_rate_limited",
                    "Too many failed deletion attempts. Try again later.",
                )
        for scope in scopes:
            row = rows.get(scope)
            if row is None or now - float(row["window_started_at"]) >= 900:
                failures, window_started = 1, now
            else:
                failures = int(row["failures"]) + 1
                window_started = float(row["window_started_at"])
            blocked_until = now + 900 if failures >= 5 else 0
            conn.execute(
                """INSERT INTO protected_action_throttles
                   (scope_key, window_started_at, failures, blocked_until)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(scope_key) DO UPDATE SET
                     window_started_at=excluded.window_started_at,
                     failures=excluded.failures,
                     blocked_until=MAX(protected_action_throttles.blocked_until, excluded.blocked_until)""",
                (scope, window_started, failures, blocked_until),
            )
        conn.commit()


def assert_deletion_not_throttled(database, *, user_id: str, client_signal: str) -> None:
    """Read-only compatibility helper; routes reserve attempts atomically."""
    now = time.time()
    with database.connect() as conn:
        row = conn.execute(
            "SELECT MAX(blocked_until) AS blocked_until FROM protected_action_throttles WHERE scope_key IN (?, ?)",
            _throttle_scopes(user_id, client_signal),
        ).fetchone()
    if row and float(row["blocked_until"] or 0) > now:
        raise DeletionSecurityError(
            "deletion_rate_limited",
            "Too many failed deletion attempts. Try again later.",
        )


def record_deletion_failure(database, *, user_id: str, client_signal: str) -> None:
    now = time.time()
    with database.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        for scope in _throttle_scopes(user_id, client_signal):
            row = conn.execute(
                "SELECT * FROM protected_action_throttles WHERE scope_key=?", (scope,)
            ).fetchone()
            if row is None or now - float(row["window_started_at"]) >= 900:
                failures = 1
                window_started = now
            else:
                failures = int(row["failures"]) + 1
                window_started = float(row["window_started_at"])
            blocked_until = now + 900 if failures >= 5 else 0
            conn.execute(
                """INSERT INTO protected_action_throttles
                   (scope_key, window_started_at, failures, blocked_until)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(scope_key) DO UPDATE SET
                     window_started_at=excluded.window_started_at,
                     failures=excluded.failures,
                     blocked_until=MAX(protected_action_throttles.blocked_until, excluded.blocked_until)""",
                (scope, window_started, failures, blocked_until),
            )
        conn.commit()


def clear_deletion_failures(database, *, user_id: str, client_signal: str) -> None:
    with database.connect() as conn:
        conn.execute(
            "DELETE FROM protected_action_throttles WHERE scope_key IN (?, ?)",
            _throttle_scopes(user_id, client_signal),
        )
        conn.commit()
