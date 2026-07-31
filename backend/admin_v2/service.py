"""Admin V2 authentication service with opaque, server-managed sessions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
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
        self.mfa_challenge_threshold = max(
            2,
            int(os.environ.get("PRACTENTURE_ADMIN_MFA_CHALLENGE_THRESHOLD", "5")),
        )
        self.mfa_challenge_window_seconds = max(
            60,
            int(
                os.environ.get(
                    "PRACTENTURE_ADMIN_MFA_CHALLENGE_WINDOW_SECONDS", "300"
                )
            ),
        )
        # Password-known attackers can obtain replacement challenges, so
        # verification failures need an account-wide budget independent from
        # password-login throttling.
        self.mfa_owner_threshold = max(
            2,
            int(os.environ.get("PRACTENTURE_ADMIN_MFA_OWNER_THRESHOLD", "20")),
        )
        self.recovery_threshold = max(
            2, int(os.environ.get("PRACTENTURE_ADMIN_RECOVERY_THRESHOLD", "3"))
        )
        self.recovery_window_seconds = max(
            60,
            int(os.environ.get("PRACTENTURE_ADMIN_RECOVERY_WINDOW_SECONDS", "3600")),
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
        self, challenge_token: str, mfa_code: str, client_signal: str | None
    ) -> tuple[AuthenticatedSession, str, str]:
        now = self._now()
        challenge_hash = self._hash_secret(challenge_token)
        owner_user_id = self.repository.active_mfa_challenge_owner(
            challenge_hash, now.isoformat()
        )
        if owner_user_id is None:
            raise AdminError(
                401,
                "ADMIN_MFA_CHALLENGE_INVALID",
                "MFA challenge is invalid or expired",
            )

        challenge_decision = self.repository.reserve_login_attempt(
            f"mfa-challenge:{challenge_hash}",
            None,
            now=now.timestamp(),
            threshold=self.mfa_challenge_threshold,
            window_seconds=self.mfa_challenge_window_seconds,
            identity_threshold=self.mfa_challenge_threshold,
            identity_window_seconds=self.mfa_challenge_window_seconds,
            include_client_scopes=False,
        )
        if not challenge_decision.allowed:
            self.repository.invalidate_mfa_challenge(challenge_hash)
            raise AdminError(
                429,
                "ADMIN_MFA_CHALLENGE_THROTTLED",
                "Too many MFA verification attempts",
                headers={"Retry-After": str(challenge_decision.retry_after)},
            )

        owner_decision = self.repository.reserve_login_attempt(
            f"mfa-owner:{owner_user_id.casefold()}",
            client_signal,
            now=now.timestamp(),
            threshold=self.mfa_owner_threshold,
            window_seconds=self.mfa_challenge_window_seconds,
            identity_threshold=self.mfa_owner_threshold,
            client_threshold=self.login_client_threshold,
            identity_window_seconds=self.mfa_challenge_window_seconds,
            client_window_seconds=self.login_window_seconds,
        )
        if not owner_decision.allowed:
            self.repository.invalidate_mfa_challenge(challenge_hash)
            raise AdminError(
                429,
                "ADMIN_MFA_CHALLENGE_THROTTLED",
                "Too many MFA verification attempts",
                headers={"Retry-After": str(owner_decision.retry_after)},
            )
        token = secrets.token_urlsafe(48)
        csrf_token = self._csrf_for_session_token(token)
        token_hash = self._hash_secret(token)
        idle_expires = now + IDLE_TIMEOUT
        status, user_id = self.repository.create_from_mfa_challenge(
            challenge_token_hash=challenge_hash,
            mfa_code=mfa_code,
            session_id=f"adm_{secrets.token_urlsafe(18)}",
            token_hash=token_hash,
            csrf_hash=self._hash_secret(csrf_token),
            created_at=now.isoformat(),
            idle_expires_at=idle_expires.isoformat(),
            absolute_expires_at=(now + ABSOLUTE_TIMEOUT).isoformat(),
            challenge_throttle_identity=f"mfa-challenge:{challenge_hash}",
            owner_throttle_identity=f"mfa-owner:{owner_user_id.casefold()}",
            client_signal=client_signal,
            owner_client_window_started_at=owner_decision.client_window_started_at,
        )
        error_map = {
            "invalid_challenge": (401, "ADMIN_MFA_CHALLENGE_INVALID", "MFA challenge is invalid or expired"),
            "invalid_mfa": (401, "ADMIN_INVALID_MFA", "Invalid MFA code"),
            "mfa_replayed": (401, "ADMIN_MFA_REPLAYED", "MFA code has already been used"),
            "mfa_required": (401, "ADMIN_MFA_REQUIRED", "MFA verification required"),
        }
        if status != "created" or user_id is None:
            if challenge_decision.lock_created:
                self.repository.invalidate_mfa_challenge(challenge_hash)
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

    def _reserve_mfa_owner_attempt(
        self,
        owner_user_id: str,
        client_signal: str | None,
        now: datetime,
    ):
        decision = self.repository.reserve_login_attempt(
            f"mfa-owner:{owner_user_id.casefold()}",
            client_signal,
            now=now.timestamp(),
            threshold=self.mfa_owner_threshold,
            window_seconds=self.mfa_challenge_window_seconds,
            identity_threshold=self.mfa_owner_threshold,
            client_threshold=self.login_client_threshold,
            identity_window_seconds=self.mfa_challenge_window_seconds,
            client_window_seconds=self.login_window_seconds,
        )
        if not decision.allowed:
            raise AdminError(
                429,
                "ADMIN_MFA_THROTTLED",
                "Too many MFA verification attempts",
                headers={"Retry-After": str(decision.retry_after)},
            )
        return decision

    def _reserve_mfa_management_attempt(
        self,
        owner_user_id: str,
        client_signal: str | None,
        now: datetime,
    ):
        identity = f"mfa-management:{owner_user_id.casefold()}"
        decision = self.repository.reserve_login_attempt(
            identity,
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
                "ADMIN_REAUTH_THROTTLED",
                "Too many authentication attempts",
                headers={"Retry-After": str(decision.retry_after)},
            )
        return identity, decision

    @staticmethod
    def _verify_active_management_session(
        conn: sqlite3.Connection,
        session: AuthenticatedSession,
        now: datetime,
    ) -> str:
        owner_user_id = session.record.owner_user_id
        row = conn.execute(
            """SELECT u.password_hash, u.role, u.status
               FROM admin_sessions AS s
               JOIN users AS u ON u.username=s.owner_user_id
               WHERE s.id=? AND s.owner_user_id=? AND s.revoked_at IS NULL
                 AND s.idle_expires_at>? AND s.absolute_expires_at>?""",
            (session.record.id, owner_user_id, now.isoformat(), now.isoformat()),
        ).fetchone()
        if row is None:
            raise AdminError(401, "ADMIN_AUTH_REQUIRED", "Authentication required")
        if str(row[1]) != "owner" or str(row[2] or "active") != "active":
            raise AdminError(403, "ADMIN_OWNER_REQUIRED", "Active Owner role required")
        return str(row[0] or "")

    @classmethod
    def _verify_management_authorization(
        cls,
        conn: sqlite3.Connection,
        session: AuthenticatedSession,
        password: str,
        now: datetime,
    ) -> None:
        owner_user_id = session.record.owner_user_id
        stored_hash = cls._verify_active_management_session(conn, session, now)
        password_valid = False
        if is_legacy_hash(stored_hash):
            password_valid = verify_password(password, stored_hash)
            if password_valid:
                conn.execute(
                    "UPDATE users SET password_hash=? WHERE username=? AND password_hash=?",
                    (hash_password(password), owner_user_id, stored_hash),
                )
            else:
                verify_password(password, _DUMMY_PASSWORD_HASH)
        elif is_bcrypt_hash(stored_hash):
            password_valid = verify_password(password, stored_hash)
        else:
            verify_password(password, _DUMMY_PASSWORD_HASH)
        if not password_valid:
            raise AdminError(401, "ADMIN_REAUTH_FAILED", "Reauthentication failed")

    @staticmethod
    def _recovery_code_count(owner_user_id: str) -> int:
        record = db.get_mfa_secret(owner_user_id)
        if not record or int(record.get("enabled") or 0) != 1:
            return 0
        try:
            codes = json.loads(record.get("backup_codes") or "[]")
        except (TypeError, ValueError):
            return 0
        return len(codes) if isinstance(codes, list) else 0

    def mfa_status(self, session: AuthenticatedSession) -> tuple[bool, int]:
        owner_user_id = session.record.owner_user_id
        enabled = db.is_mfa_enabled(owner_user_id)
        return enabled, self._recovery_code_count(owner_user_id) if enabled else 0

    def start_mfa_enrollment(
        self,
        session: AuthenticatedSession,
        password: str,
        request_id: str,
        client_signal: str | None,
        qr_code_factory: Callable[[str], str],
    ) -> tuple[str, str, str]:
        from mfa import (
            generate_totp_secret,
            get_totp_uri,
            protect_totp_secret,
            reveal_totp_secret,
        )

        owner_user_id = session.record.owner_user_id
        candidate_secret = generate_totp_secret()
        protected_secret = protect_totp_secret(candidate_secret)
        now = self._now()
        throttle_identity, throttle_decision = self._reserve_mfa_management_attempt(
            owner_user_id,
            client_signal,
            now,
        )

        def mutation(conn: sqlite3.Connection) -> StoredResponse:
            self._verify_management_authorization(conn, session, password, now)
            current = conn.execute(
                "SELECT secret, enabled FROM mfa_secrets WHERE user_id=?",
                (owner_user_id,),
            ).fetchone()
            if current is not None and int(current[1] or 0) == 1:
                raise AdminError(409, "ADMIN_MFA_ALREADY_ENABLED", "MFA is already enabled")
            enrollment_secret = candidate_secret
            if current is None:
                conn.execute(
                    """INSERT INTO mfa_secrets (user_id, secret, enabled, backup_codes)
                       VALUES (?, ?, 0, '[]')""",
                    (owner_user_id, protected_secret),
                )
                conn.execute(
                    "DELETE FROM admin_mfa_replay_state WHERE owner_user_id=?",
                    (owner_user_id,),
                )
            else:
                try:
                    enrollment_secret = reveal_totp_secret(str(current[0]))
                except (TypeError, ValueError, KeyError) as exc:
                    raise AdminError(
                        500,
                        "ADMIN_MFA_SECRET_INVALID",
                        "Stored MFA enrollment cannot be resumed",
                    ) from exc
            uri = get_totp_uri(enrollment_secret, owner_user_id, "Practenture")
            qr_code = qr_code_factory(uri)
            self.repository.reset_login_attempt_in_transaction(
                conn,
                throttle_identity,
                client_signal,
                client_window_started_at=throttle_decision.client_window_started_at,
            )
            return StoredResponse(
                200,
                {
                    "status": "enrollment_started",
                    "secret": enrollment_secret,
                    "uri": uri,
                    "qrCode": qr_code,
                },
                {},
            )

        result = self.mutations.execute(
            request_id=request_id,
            actor={"id": owner_user_id, "role": "owner"},
            target={"type": "owner", "id": owner_user_id},
            action="admin.auth.mfa_enrollment_started",
            outcome="succeeded",
            metadata={},
            mutation=mutation,
            now=now,
        )
        secret = str(result.response.body["secret"])
        return (
            secret,
            str(result.response.body["uri"]),
            str(result.response.body["qrCode"]),
        )

    def confirm_mfa_enrollment(
        self,
        session: AuthenticatedSession,
        code: str,
        request_id: str,
        client_signal: str | None,
    ) -> list[str]:
        from mfa import generate_backup_codes, hash_backup_code, resolve_totp_counter

        owner_user_id = session.record.owner_user_id
        now = self._now()
        throttle_identity = f"mfa-owner:{owner_user_id.casefold()}"
        throttle_decision = self._reserve_mfa_owner_attempt(
            owner_user_id, client_signal, now
        )
        recovery_codes = generate_backup_codes()
        encoded_codes = json.dumps([hash_backup_code(value) for value in recovery_codes])

        def mutation(conn: sqlite3.Connection) -> StoredResponse:
            self._verify_active_management_session(conn, session, now)
            record = conn.execute(
                "SELECT secret, enabled FROM mfa_secrets WHERE user_id=?",
                (owner_user_id,),
            ).fetchone()
            if record is None or int(record[1] or 0) == 1:
                raise AdminError(
                    409,
                    "ADMIN_MFA_ENROLLMENT_REQUIRED",
                    "Start a new MFA enrollment first",
                )
            try:
                step = resolve_totp_counter(str(record[0]), code)
            except (TypeError, ValueError, KeyError):
                step = None
            if step is None:
                raise AdminError(400, "ADMIN_INVALID_MFA", "Invalid authenticator code")
            updated = conn.execute(
                """UPDATE mfa_secrets
                   SET enabled=1, backup_codes=?, enabled_at=?
                   WHERE user_id=? AND enabled=0""",
                (encoded_codes, now.isoformat(), owner_user_id),
            )
            if updated.rowcount != 1:
                raise AdminError(
                    409,
                    "ADMIN_MFA_ENROLLMENT_REQUIRED",
                    "Start a new MFA enrollment first",
                )
            conn.execute(
                """INSERT INTO admin_mfa_replay_state
                       (owner_user_id, last_accepted_totp_step, accepted_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(owner_user_id) DO UPDATE SET
                       last_accepted_totp_step=excluded.last_accepted_totp_step,
                       accepted_at=excluded.accepted_at""",
                (owner_user_id, step, now.isoformat()),
            )
            self.repository.reset_login_attempt_in_transaction(
                conn,
                throttle_identity,
                client_signal,
                client_window_started_at=throttle_decision.client_window_started_at,
            )
            return StoredResponse(200, {"status": "enabled"}, {})

        self.mutations.execute(
            request_id=request_id,
            actor={"id": owner_user_id, "role": "owner"},
            target={"type": "owner", "id": owner_user_id},
            action="admin.auth.mfa_enabled",
            outcome="succeeded",
            metadata={"recoveryCodesIssued": len(recovery_codes)},
            mutation=mutation,
            now=now,
        )
        return recovery_codes

    def _verify_mfa_management_factor(
        self,
        conn: sqlite3.Connection,
        owner_user_id: str,
        code: str,
        accepted_at: str,
    ) -> None:
        result = self.repository.verify_mfa_in_transaction(
            conn, owner_user_id, code, accepted_at
        )
        if result == "not_required":
            raise AdminError(409, "ADMIN_MFA_NOT_ENABLED", "MFA is not enabled")
        if result == "mfa_replayed":
            raise AdminError(401, "ADMIN_MFA_REPLAYED", "MFA code has already been used")
        if result != "accepted":
            raise AdminError(401, "ADMIN_INVALID_MFA", "Invalid MFA code")

    def regenerate_mfa_recovery_codes(
        self,
        session: AuthenticatedSession,
        password: str,
        code: str,
        request_id: str,
        client_signal: str | None,
    ) -> list[str]:
        from mfa import generate_backup_codes, hash_backup_code

        owner_user_id = session.record.owner_user_id
        now = self._now()
        throttle_identity, throttle_decision = self._reserve_mfa_management_attempt(
            owner_user_id, client_signal, now
        )
        recovery_codes = generate_backup_codes()
        encoded_codes = json.dumps([hash_backup_code(value) for value in recovery_codes])

        def mutation(conn: sqlite3.Connection) -> StoredResponse:
            self._verify_management_authorization(conn, session, password, now)
            self._verify_mfa_management_factor(
                conn, owner_user_id, code, now.isoformat()
            )
            conn.execute(
                "UPDATE mfa_secrets SET backup_codes=? WHERE user_id=? AND enabled=1",
                (encoded_codes, owner_user_id),
            )
            self.repository.reset_login_attempt_in_transaction(
                conn,
                throttle_identity,
                client_signal,
                client_window_started_at=throttle_decision.client_window_started_at,
            )
            return StoredResponse(200, {"status": "regenerated"}, {})

        self.mutations.execute(
            request_id=request_id,
            actor={"id": owner_user_id, "role": "owner"},
            target={"type": "owner", "id": owner_user_id},
            action="admin.auth.mfa_recovery_codes_regenerated",
            outcome="succeeded",
            metadata={"recoveryCodesIssued": len(recovery_codes)},
            mutation=mutation,
            now=now,
        )
        return recovery_codes

    def disable_mfa(
        self,
        session: AuthenticatedSession,
        password: str,
        code: str,
        request_id: str,
        client_signal: str | None,
    ) -> None:
        owner_user_id = session.record.owner_user_id
        now = self._now()
        throttle_identity, throttle_decision = self._reserve_mfa_management_attempt(
            owner_user_id, client_signal, now
        )

        def mutation(conn: sqlite3.Connection) -> StoredResponse:
            self._verify_management_authorization(conn, session, password, now)
            self._verify_mfa_management_factor(
                conn, owner_user_id, code, now.isoformat()
            )
            conn.execute("DELETE FROM mfa_secrets WHERE user_id=?", (owner_user_id,))
            conn.execute(
                "DELETE FROM admin_mfa_replay_state WHERE owner_user_id=?",
                (owner_user_id,),
            )
            self.repository.reset_login_attempt_in_transaction(
                conn,
                throttle_identity,
                client_signal,
                client_window_started_at=throttle_decision.client_window_started_at,
            )
            return StoredResponse(200, {"status": "disabled"}, {})

        self.mutations.execute(
            request_id=request_id,
            actor={"id": owner_user_id, "role": "owner"},
            target={"type": "owner", "id": owner_user_id},
            action="admin.auth.mfa_disabled",
            outcome="succeeded",
            metadata={},
            mutation=mutation,
            now=now,
        )

    def reauthenticate(
        self,
        session: AuthenticatedSession,
        password: str,
        mfa_code: str | None,
        client_signal: str | None,
        request_id: str,
    ) -> datetime:
        owner_user_id = session.record.owner_user_id
        now = self._now()
        throttle_identity, throttle_decision = self._reserve_mfa_management_attempt(
            owner_user_id, client_signal, now
        )

        def mutation(conn: sqlite3.Connection) -> StoredResponse:
            self._verify_management_authorization(conn, session, password, now)
            status = self.repository.verify_mfa_in_transaction(
                conn, owner_user_id, mfa_code, now.isoformat()
            )
            if status == "mfa_required":
                raise AdminError(401, "ADMIN_MFA_REQUIRED", "MFA verification required")
            if status == "mfa_replayed":
                raise AdminError(401, "ADMIN_MFA_REPLAYED", "MFA code has already been used")
            if status == "invalid_mfa":
                raise AdminError(401, "ADMIN_INVALID_MFA", "Invalid MFA code")
            if status not in {"accepted", "not_required"}:
                raise AdminError(401, "ADMIN_AUTH_REQUIRED", "Authentication required")
            conn.execute(
                """INSERT INTO admin_recent_auth (session_id, authenticated_at)
                   VALUES (?, ?) ON CONFLICT(session_id) DO UPDATE SET
                   authenticated_at=excluded.authenticated_at""",
                (session.record.id, now.isoformat()),
            )
            self.repository.reset_login_attempt_in_transaction(
                conn,
                throttle_identity,
                client_signal,
                client_window_started_at=throttle_decision.client_window_started_at,
            )
            return StoredResponse(200, {"status": "reauthenticated"}, {})

        self.mutations.execute(
            request_id=request_id,
            actor={"id": owner_user_id, "role": "owner"},
            target={"type": "owner", "id": owner_user_id},
            action="admin.auth.reauthenticated",
            outcome="succeeded",
            metadata={},
            mutation=mutation,
            now=now,
        )
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

    def start_recovery(
        self,
        identifier: str,
        request_id: str,
        client_signal: str | None = None,
        delivery_scheduler: Callable[..., None] | None = None,
    ) -> str | None:
        """Create and deliver an opaque one-time Administrator recovery token.

        The public response remains enumeration-safe. Outside the isolated test
        harness, a token is usable only when SES accepts delivery to the active
        Administrator email; failed delivery immediately invalidates it.
        """
        now = self._now()
        normalized = identifier.strip().casefold()
        recovery_decision = self.repository.reserve_login_attempt(
            f"recovery:{normalized}",
            f"recovery:{client_signal or 'unknown'}",
            now=now.timestamp(),
            threshold=self.recovery_threshold,
            window_seconds=self.recovery_window_seconds,
            identity_threshold=self.recovery_threshold,
            client_threshold=max(self.recovery_threshold * 4, 12),
        )
        if not recovery_decision.allowed:
            raise AdminError(
                429,
                "ADMIN_RECOVERY_THROTTLED",
                "Too many recovery requests",
                headers={"Retry-After": str(recovery_decision.retry_after)},
            )
        token = secrets.token_urlsafe(48)
        token_hash = self._hash_secret(token)
        delivery: dict[str, str] = {}

        def mutation(conn: sqlite3.Connection) -> StoredResponse:
            user = conn.execute(
                """SELECT username, email FROM users
                   WHERE role='owner' AND status='active'
                     AND (lower(username)=? OR lower(email)=?) LIMIT 1""",
                (normalized, normalized),
            ).fetchone()
            if user is not None:
                user_id = str(user[0])
                recipient = str(user[1] or "").strip().casefold()
                # Never revoke a previously issued recovery credential merely
                # because a later asynchronous delivery was requested.  If the
                # later provider call fails, the earlier accepted email must
                # remain usable.  Each token is short-lived, one-time, and all
                # outstanding tokens are revoked after any successful reset.
                conn.execute(
                    "DELETE FROM password_reset_tokens WHERE user_id=? AND (used=1 OR expires_at<=?)",
                    (user_id, now.timestamp()),
                )
                conn.execute(
                    """INSERT INTO password_reset_tokens
                       (token_hash, user_id, expires_at, used) VALUES (?, ?, ?, 0)""",
                    (token_hash, user_id, (now + timedelta(minutes=30)).timestamp()),
                )
                delivery.update(user_id=user_id, matched="true")
                if recipient:
                    delivery["recipient"] = recipient
            return StoredResponse(202, {"status": "accepted"}, {})

        self.mutations.execute(
            request_id=request_id,
            actor={"type": "anonymous"},
            target={"type": "owner_recovery"},
            action="admin.auth.recovery_requested",
            outcome="accepted",
            metadata={},
            mutation=mutation,
            now=now,
        )
        if os.environ.get("PRACTENTURE_TESTING") == "1":
            return token if delivery.get("matched") else None
        if delivery_scheduler is None:
            raise RuntimeError("production recovery delivery requires a background scheduler")

        # Schedule the same callable for matches and misses so the public 202 is
        # sent before any provider I/O and does not reveal whether SES was used.
        delivery_scheduler(
            self._deliver_recovery,
            delivery.get("recipient"),
            token if delivery.get("matched") else None,
            token_hash if delivery.get("matched") else None,
        )
        return None

    @staticmethod
    def _deliver_recovery(
        recipient: str | None,
        token: str | None,
        token_hash: str | None,
    ) -> None:
        delivered = False
        if recipient and token:
            try:
                from password_reset_email import send_admin_recovery_link

                send_admin_recovery_link(recipient=recipient, token=token)
                delivered = True
            except Exception:
                delivered = False
        if token_hash and not delivered:
            # An undisclosed credential must never survive missing or failed
            # delivery. The public response has already been sent.
            with db._lock:
                conn = db._get_conn()
                conn.execute(
                    "UPDATE password_reset_tokens SET used=1 WHERE token_hash=?",
                    (token_hash,),
                )
                conn.commit()

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
                "UPDATE password_reset_tokens SET used=1 WHERE user_id=? AND used=0",
                (user_id,),
            )
            # The submitted token was checked in this transaction before all
            # outstanding credentials were invalidated; a later concurrent
            # reset cannot make this winner ambiguous.
            if consumed.rowcount < 1:
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
