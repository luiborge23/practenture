"""Admin V2 authentication service with opaque, server-managed sessions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
import secrets
import sqlite3
from typing import Any

from database import db
from security import hash_password, is_bcrypt_hash, is_legacy_hash, verify_password
from .errors import AdminError
from .repository import (
    AdminMutationRepository,
    AdminSessionRecord,
    AdminSessionRepository,
    MutationExecution,
    StoredResponse,
    fingerprint_request,
)

COOKIE_NAME = "practenture_admin_v2_session"
COOKIE_PATH = "/api/admin/v2"
IDLE_TIMEOUT = timedelta(minutes=15)
ABSOLUTE_TIMEOUT = timedelta(hours=8)
_DUMMY_PASSWORD_HASH = "$2b$12$kbOCzw.LZxI1pPmcC6cJLuzc1oQGaYrLIFcrNpKHYFaZadqlP9zvy"


@dataclass(frozen=True)
class AuthenticatedSession:
    record: AdminSessionRecord
    user: dict


class AdminAuthService:
    def __init__(self, repository: AdminSessionRepository | None = None) -> None:
        self.repository = repository or AdminSessionRepository()
        self.mutations = AdminMutationRepository()
        self.absolute_seconds = int(ABSOLUTE_TIMEOUT.total_seconds())
        self.login_threshold = max(
            2, int(os.environ.get("PRACTENTURE_ADMIN_LOGIN_THRESHOLD", "5"))
        )
        self.login_window_seconds = max(
            1, int(os.environ.get("PRACTENTURE_ADMIN_LOGIN_WINDOW_SECONDS", "900"))
        )
        self.login_identity_threshold = max(
            1,
            int(os.environ.get("PRACTENTURE_ADMIN_LOGIN_IDENTITY_THRESHOLD", "20")),
        )
        self.login_client_threshold = max(
            1,
            int(os.environ.get("PRACTENTURE_ADMIN_LOGIN_CLIENT_THRESHOLD", "50")),
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _hash_secret(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    @staticmethod
    def _csrf_for_session_token(token: str) -> str:
        secret = os.environ.get("PRACTENTURE_ADMIN_CSRF_SECRET") or os.environ.get(
            "PRACTENTURE_JWT_SECRET"
        )
        if not secret:
            raise RuntimeError("Admin CSRF signing secret is not configured")
        return hmac.new(secret.encode(), token.encode(), hashlib.sha256).hexdigest()

    def _verify_owner_password(self, username: str, password: str) -> dict | None:
        """Verify an owner while equalizing every failed non-bcrypt path."""
        user = db.get_user(username)
        if user is None:
            verify_password(password, _DUMMY_PASSWORD_HASH)
            return None

        stored_hash = user.get("password_hash", "")
        if is_legacy_hash(stored_hash):
            if not verify_password(password, stored_hash):
                verify_password(password, _DUMMY_PASSWORD_HASH)
                return None
            # Preserve the existing transparent SHA-256 -> bcrypt migration.
            db.update_user_password(username, hash_password(password))
            return user

        if is_bcrypt_hash(stored_hash):
            return user if verify_password(password, stored_hash) else None

        # Malformed and unsupported stored hashes must pay the same fixed
        # current-cost work as an absent user rather than returning quickly.
        verify_password(password, _DUMMY_PASSWORD_HASH)
        return None

    def login(
        self,
        username: str,
        password: str,
        *,
        mfa_code: str | None,
        client_signal: str | None,
        replacement_token: str | None = None,
    ) -> tuple[AuthenticatedSession, str, str]:
        now = self._now()
        decision = self.repository.reserve_login_attempt(
            username,
            client_signal,
            now=now.timestamp(),
            threshold=self.login_threshold,
            window_seconds=self.login_window_seconds,
            identity_threshold=self.login_identity_threshold,
            client_threshold=self.login_client_threshold,
        )
        if not decision.allowed:
            raise AdminError(
                429,
                "ADMIN_LOGIN_THROTTLED",
                "Too many login attempts",
                headers={"Retry-After": str(decision.retry_after)},
            )

        user = self._verify_owner_password(username, password)
        if not user:
            raise AdminError(401, "ADMIN_INVALID_CREDENTIALS", "Invalid credentials")
        if user.get("role") != "owner":
            raise AdminError(403, "ADMIN_OWNER_REQUIRED", "Owner role required")
        if user.get("status", "active") != "active":
            raise AdminError(403, "ADMIN_ACCOUNT_INACTIVE", "Account is inactive")

        token = secrets.token_urlsafe(48)
        csrf_token = self._csrf_for_session_token(token)
        token_hash = self._hash_secret(token)
        csrf_hash = self._hash_secret(csrf_token)
        idle_expires = now + IDLE_TIMEOUT
        absolute_expires = now + ABSOLUTE_TIMEOUT
        session_id = f"adm_{secrets.token_urlsafe(18)}"

        result = self.repository.create_after_mfa(
            session_id=session_id,
            token_hash=token_hash,
            csrf_hash=csrf_hash,
            user_id=user["username"],
            role="owner",
            created_at=now.isoformat(),
            idle_expires_at=idle_expires.isoformat(),
            absolute_expires_at=absolute_expires.isoformat(),
            mfa_code=mfa_code,
            login_identity=username,
            client_signal=client_signal,
            client_window_started_at=decision.client_window_started_at,
            replacement_token_hash=(
                self._hash_secret(replacement_token) if replacement_token else None
            ),
        )
        if result == "mfa_required":
            challenge_token = secrets.token_urlsafe(48)
            challenge_id = f"mfa_{secrets.token_urlsafe(18)}"
            self.repository.create_mfa_challenge(
                challenge_id=challenge_id,
                token_hash=self._hash_secret(challenge_token),
                user_id=user["username"],
                created_at=now.isoformat(),
                expires_at=(now + timedelta(minutes=5)).isoformat(),
            )
            raise AdminError(
                401,
                "ADMIN_MFA_REQUIRED",
                "MFA verification required",
                headers={"X-Admin-MFA-Challenge": challenge_token},
            )
        if result == "invalid_mfa":
            raise AdminError(401, "ADMIN_INVALID_MFA", "Invalid MFA code")
        if result == "mfa_replayed":
            raise AdminError(401, "ADMIN_MFA_REPLAYED", "MFA code has already been used")

        record, state = self.repository.touch_active(
            token_hash, now=now, idle_expires_at=idle_expires.isoformat()
        )
        if state != "active" or record is None:
            raise AdminError(401, "ADMIN_AUTH_REQUIRED", "Authentication required")
        return AuthenticatedSession(record=record, user=user), token, csrf_token

    def verify_mfa_challenge(
        self, challenge_token: str, mfa_code: str
    ) -> tuple[AuthenticatedSession, str, str]:
        now = self._now()
        token = secrets.token_urlsafe(48)
        csrf_token = self._csrf_for_session_token(token)
        token_hash = self._hash_secret(token)
        idle_expires = now + IDLE_TIMEOUT
        status, user_id = self.repository.create_from_mfa_challenge(
            challenge_token_hash=self._hash_secret(challenge_token),
            mfa_code=mfa_code,
            session_id=f"adm_{secrets.token_urlsafe(18)}",
            token_hash=token_hash,
            csrf_hash=self._hash_secret(csrf_token),
            created_at=now.isoformat(),
            idle_expires_at=idle_expires.isoformat(),
            absolute_expires_at=(now + ABSOLUTE_TIMEOUT).isoformat(),
        )
        error_map = {
            "invalid_challenge": (401, "ADMIN_MFA_CHALLENGE_INVALID", "MFA challenge is invalid or expired"),
            "invalid_mfa": (401, "ADMIN_INVALID_MFA", "Invalid MFA code"),
            "mfa_replayed": (401, "ADMIN_MFA_REPLAYED", "MFA code has already been used"),
            "mfa_required": (401, "ADMIN_MFA_REQUIRED", "MFA verification required"),
        }
        if status != "created" or user_id is None:
            args = error_map.get(status, error_map["invalid_challenge"])
            raise AdminError(*args)
        record, state = self.repository.touch_active(
            token_hash, now=now, idle_expires_at=idle_expires.isoformat()
        )
        user = db.get_user(user_id)
        if state != "active" or record is None or user is None:
            raise AdminError(401, "ADMIN_AUTH_REQUIRED", "Authentication required")
        return AuthenticatedSession(record=record, user=user), token, csrf_token

    def authenticate(
        self, token: str | None
    ) -> tuple[AuthenticatedSession, str]:
        if not token:
            raise AdminError(401, "ADMIN_AUTH_REQUIRED", "Authentication required")

        now = self._now()
        token_hash = self._hash_secret(token)
        record, state = self.repository.touch_active(
            token_hash,
            now=now,
            idle_expires_at=(now + IDLE_TIMEOUT).isoformat(),
        )
        if record is None:
            code = "ADMIN_SESSION_EXPIRED" if state == "expired" else "ADMIN_AUTH_REQUIRED"
            message = "Session expired" if state == "expired" else "Authentication required"
            raise AdminError(401, code, message)

        csrf_token = self._csrf_for_session_token(token)
        if not hmac.compare_digest(
            record.csrf_token_hash, self._hash_secret(csrf_token)
        ):
            self.repository.revoke(token_hash, now.isoformat(), "csrf_state_invalid")
            raise AdminError(401, "ADMIN_AUTH_REQUIRED", "Authentication required")

        user = db.get_user(record.owner_user_id)
        if not user or user.get("role") != "owner" or user.get("status", "active") != "active":
            self.repository.revoke(token_hash, now.isoformat(), "owner_no_longer_active")
            raise AdminError(401, "ADMIN_AUTH_REQUIRED", "Authentication required")
        return AuthenticatedSession(record=record, user=user), csrf_token

    def verify_csrf(
        self, session: AuthenticatedSession, supplied_token: str | None
    ) -> None:
        supplied_hash = self._hash_secret(supplied_token or "")
        if not hmac.compare_digest(
            supplied_hash, session.record.csrf_token_hash
        ):
            raise AdminError(403, "ADMIN_CSRF_INVALID", "CSRF token is missing or invalid")

    def logout(self, session: AuthenticatedSession) -> None:
        revoked = self.repository.revoke(
            session.record.token_hash,
            self._now().isoformat(),
            "logout",
        )
        if not revoked:
            raise AdminError(401, "ADMIN_AUTH_REQUIRED", "Authentication required")

    def reauthenticate(
        self, session: AuthenticatedSession, password: str, mfa_code: str | None
    ) -> datetime:
        user = self._verify_owner_password(session.record.owner_user_id, password)
        if user is None:
            raise AdminError(401, "ADMIN_REAUTH_FAILED", "Reauthentication failed")
        now = self._now()
        status = self.repository.record_recent_auth(
            session_id=session.record.id,
            user_id=session.record.owner_user_id,
            mfa_code=mfa_code,
            authenticated_at=now.isoformat(),
        )
        if status == "mfa_required":
            raise AdminError(401, "ADMIN_MFA_REQUIRED", "MFA verification required")
        if status == "mfa_replayed":
            raise AdminError(401, "ADMIN_MFA_REPLAYED", "MFA code has already been used")
        if status == "invalid_mfa":
            raise AdminError(401, "ADMIN_INVALID_MFA", "Invalid MFA code")
        if status != "accepted":
            raise AdminError(401, "ADMIN_AUTH_REQUIRED", "Authentication required")
        return now + timedelta(minutes=5)

    def require_recent_auth(self, session: AuthenticatedSession) -> None:
        cutoff = (self._now() - timedelta(minutes=5)).isoformat()
        if not self.repository.has_recent_auth(session.record.id, cutoff):
            raise AdminError(
                403, "ADMIN_RECENT_AUTH_REQUIRED", "Recent authentication required"
            )

    def change_password(
        self, session: AuthenticatedSession, current_password: str,
        new_password: str, request_id: str,
    ) -> tuple[AuthenticatedSession, str, str]:
        from security import validate_password_complexity

        valid, message = validate_password_complexity(new_password)
        if not valid:
            raise AdminError(400, "ADMIN_PASSWORD_POLICY", message or "Password does not meet policy")
        if hmac.compare_digest(current_password, new_password):
            raise AdminError(400, "ADMIN_PASSWORD_REUSE", "New password must be different")
        now = self._now()
        token = secrets.token_urlsafe(48)
        csrf = self._csrf_for_session_token(token)
        token_hash = self._hash_secret(token)
        new_id = f"adm_{secrets.token_urlsafe(18)}"
        password_hash = hash_password(new_password)

        def mutation(conn: sqlite3.Connection) -> StoredResponse:
            row = conn.execute(
                "SELECT password_hash FROM users WHERE username=?",
                (session.record.owner_user_id,),
            ).fetchone()
            if row is None or not verify_password(current_password, str(row[0])):
                raise AdminError(401, "ADMIN_CURRENT_PASSWORD_INVALID", "Current password is invalid")
            conn.execute(
                """UPDATE users
                   SET password_hash=?, password_changed_at=?
                   WHERE username=?""",
                (password_hash, now.isoformat(), session.record.owner_user_id),
            )
            conn.execute(
                """UPDATE admin_sessions SET revoked_at=?, revocation_reason='password_changed'
                   WHERE owner_user_id=? AND revoked_at IS NULL""",
                (now.isoformat(), session.record.owner_user_id),
            )
            conn.execute(
                """INSERT INTO admin_sessions
                   (id, token_hash, csrf_token_hash, owner_user_id, role, created_at,
                    last_seen_at, idle_expires_at, absolute_expires_at)
                   VALUES (?, ?, ?, ?, 'owner', ?, ?, ?, ?)""",
                (new_id, token_hash, self._hash_secret(csrf), session.record.owner_user_id,
                 now.isoformat(), now.isoformat(), (now + IDLE_TIMEOUT).isoformat(),
                 (now + ABSOLUTE_TIMEOUT).isoformat()),
            )
            conn.execute(
                "INSERT INTO admin_recent_auth(session_id, authenticated_at) VALUES (?, ?)",
                (new_id, now.isoformat()),
            )
            conn.execute("DELETE FROM refresh_tokens WHERE user_id=?", (session.record.owner_user_id,))
            return StoredResponse(200, {"status": "password_changed"}, {})

        self.mutations.execute(
            request_id=request_id,
            actor={"id": session.record.owner_user_id, "role": "owner"},
            target={"type": "owner", "id": session.record.owner_user_id},
            action="admin.auth.password_changed",
            outcome="succeeded",
            metadata={"sessionsRevoked": True},
            mutation=mutation,
            now=now,
        )
        record, state = self.repository.touch_active(
            token_hash, now=now, idle_expires_at=(now + IDLE_TIMEOUT).isoformat()
        )
        user = db.get_user(session.record.owner_user_id)
        if state != "active" or record is None or user is None:
            raise RuntimeError("replacement admin session was not created")
        return AuthenticatedSession(record, user), token, csrf

    def start_recovery(self, identifier: str, request_id: str) -> str | None:
        now = self._now()
        token = secrets.token_urlsafe(48)
        token_hash = self._hash_secret(token)
        normalized = identifier.strip().casefold()

        def mutation(conn: sqlite3.Connection) -> StoredResponse:
            user = conn.execute(
                """SELECT username FROM users
                   WHERE role='owner' AND status='active'
                     AND (lower(username)=? OR lower(email)=?) LIMIT 1""",
                (normalized, normalized),
            ).fetchone()
            if user is not None:
                conn.execute("DELETE FROM password_reset_tokens WHERE user_id=?", (user[0],))
                conn.execute(
                    """INSERT INTO password_reset_tokens
                       (token_hash, user_id, expires_at, used) VALUES (?, ?, ?, 0)""",
                    (token_hash, user[0], (now + timedelta(minutes=30)).timestamp()),
                )
            return StoredResponse(202, {"status": "accepted"}, {})

        execution = self.mutations.execute(
            request_id=request_id,
            actor={"type": "anonymous"},
            target={"type": "owner_recovery"},
            action="admin.auth.recovery_requested",
            outcome="accepted",
            metadata={},
            mutation=mutation,
            now=now,
        )
        # A production mail adapter can consume this value; routes expose it only
        # in the explicit isolated test harness.
        conn = db.connect()
        try:
            created = conn.execute(
                "SELECT 1 FROM password_reset_tokens WHERE token_hash=?", (token_hash,)
            ).fetchone() is not None
        finally:
            conn.close()
        return token if created else None

    def complete_recovery(
        self, recovery_token: str, new_password: str, request_id: str
    ) -> None:
        from security import validate_password_complexity

        valid, message = validate_password_complexity(new_password)
        if not valid:
            raise AdminError(400, "ADMIN_PASSWORD_POLICY", message or "Password does not meet policy")
        now = self._now()
        token_hash = self._hash_secret(recovery_token)
        password_hash = hash_password(new_password)

        def mutation(conn: sqlite3.Connection) -> StoredResponse:
            reset = conn.execute(
                """SELECT user_id FROM password_reset_tokens
                   WHERE token_hash=? AND used=0 AND expires_at>?""",
                (token_hash, now.timestamp()),
            ).fetchone()
            if reset is None:
                raise AdminError(400, "ADMIN_RECOVERY_TOKEN_INVALID", "Recovery token is invalid or expired")
            user_id = str(reset[0])
            consumed = conn.execute(
                "UPDATE password_reset_tokens SET used=1 WHERE token_hash=? AND used=0",
                (token_hash,),
            )
            if consumed.rowcount != 1:
                raise AdminError(400, "ADMIN_RECOVERY_TOKEN_INVALID", "Recovery token is invalid or expired")
            updated = conn.execute(
                """UPDATE users
                   SET password_hash=?, password_changed_at=?
                   WHERE username=?""",
                (password_hash, now.isoformat(), user_id),
            )
            if updated.rowcount != 1:
                raise AdminError(
                    400,
                    "ADMIN_RECOVERY_TOKEN_INVALID",
                    "Recovery token is invalid or expired",
                )
            conn.execute(
                """UPDATE admin_sessions SET revoked_at=?, revocation_reason='password_recovery'
                   WHERE owner_user_id=? AND revoked_at IS NULL""",
                (now.isoformat(), user_id),
            )
            conn.execute("DELETE FROM refresh_tokens WHERE user_id=?", (user_id,))
            return StoredResponse(200, {"status": "password_reset"}, {})

        self.mutations.execute(
            request_id=request_id,
            actor={"type": "recovery_token"},
            target={"type": "owner"},
            action="admin.auth.recovery_completed",
            outcome="succeeded",
            metadata={"sessionsRevoked": True},
            mutation=mutation,
            now=now,
        )


class AdminMutationService:
    """Route-facing orchestration for high-risk transactional mutations."""

    def __init__(self, repository: AdminMutationRepository | None = None) -> None:
        self.repository = repository or AdminMutationRepository()

    def execute_high_risk(
        self,
        *,
        session: AuthenticatedSession,
        route: str,
        idempotency_key: str,
        request_payload: Any,
        request_id: str,
        target: Any,
        action: str,
        metadata: Any,
        mutation: Callable[[sqlite3.Connection], StoredResponse],
    ) -> MutationExecution:
        """Bind the caller and canonical request to a transactional reservation."""
        return self.repository.execute_idempotent(
            owner_id=session.record.owner_user_id,
            route=route,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint_request(request_payload),
            request_id=request_id,
            actor={
                "id": session.record.owner_user_id,
                "role": session.record.role,
            },
            target=target,
            action=action,
            outcome="succeeded",
            metadata=metadata,
            mutation=mutation,
        )


def cookie_secure() -> bool:
    """Secure is mandatory unless the explicit test harness opts into HTTP."""
    insecure_test_override = (
        os.environ.get("PRACTENTURE_TESTING") == "1"
        and os.environ.get("PRACTENTURE_ADMIN_COOKIE_SECURE", "").casefold()
        in {"0", "false", "no"}
    )
    return not insecure_test_override


auth_service = AdminAuthService()
mutation_service = AdminMutationService()
