"""Atomic professor enrollment and provider-neutral authentication identities."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from database import db


def ensure_identity_schema() -> None:
    with db._lock:
        conn = db._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS auth_identities (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                provider TEXT NOT NULL CHECK(provider IN ('password','google','apple')),
                provider_subject TEXT NOT NULL,
                email TEXT DEFAULT '',
                created_at REAL NOT NULL,
                last_login_at REAL,
                UNIQUE(provider, provider_subject),
                UNIQUE(user_id, provider)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_auth_identities_user ON auth_identities(user_id)")
        conn.commit()


def _code_row(conn: sqlite3.Connection, code: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM professor_codes WHERE code=? AND used=0 AND (expires_at IS NULL OR expires_at>?)",
        (code.strip().upper(), time.time()),
    ).fetchone()


def _admin_invitation_row(
    conn: sqlite3.Connection, secret: str, email: str
) -> Optional[sqlite3.Row]:
    """Resolve an Admin V2 invitation without storing or logging its secret."""
    secret_hash = hashlib.sha256(secret.strip().encode("utf-8")).hexdigest()
    row = conn.execute(
        "SELECT * FROM professor_invitations WHERE secret_hash=?",
        (secret_hash,),
    ).fetchone()
    if row is None:
        return None
    intended_email = str(row["intended_email"] or "").strip().casefold()
    if not hmac.compare_digest(intended_email, email.strip().casefold()):
        raise ValueError("Invitation email does not match")
    if (
        str(row["status"] or "active").casefold() == "redeemed"
        or int(row["use_count"] or 0) >= int(row["max_uses"] or 1)
    ):
        raise ValueError("Invitation was already used")
    if str(row["status"] or "active").casefold() != "active":
        raise ValueError("Invalid, revoked, or expired invitation")
    expires_at = datetime.fromisoformat(str(row["expires_at"]).replace("Z", "+00:00"))
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        raise ValueError("Invalid, revoked, or expired invitation")
    return row


def _add_org_membership(conn: sqlite3.Connection, user_id: str, university: str) -> None:
    if not university:
        return
    org = conn.execute("SELECT id FROM organizations WHERE university_name=?", (university,)).fetchone()
    org_id = org["id"] if org else str(uuid.uuid4())
    if not org:
        conn.execute(
            "INSERT INTO organizations (id,name,university_name,created_by) VALUES (?,?,?,?)",
            (org_id, university, university, user_id),
        )
    conn.execute(
        "INSERT OR IGNORE INTO memberships (id,user_id,org_id,role) VALUES (?,?,?,'professor')",
        (str(uuid.uuid4()), user_id, org_id),
    )


def _consume_code(conn: sqlite3.Connection, code: str, user_id: str) -> Dict[str, Any]:
    row = _code_row(conn, code)
    if not row:
        raise ValueError("Invalid, already used, or expired professor code")
    updated = conn.execute(
        "UPDATE professor_codes SET used=1, used_by=?, used_at=datetime('now') WHERE code=? AND used=0",
        (user_id, code.strip().upper()),
    ).rowcount
    if updated != 1:
        raise ValueError("Professor code was already used")
    return dict(row)


def _consume_invitation(
    conn: sqlite3.Connection, code: str, user_id: str, email: str
) -> Dict[str, Any]:
    """Consume either an Admin V2 invitation or a legacy PROF code atomically."""
    normalized = code.strip()
    if normalized.upper().startswith("PROF-"):
        result = _consume_code(conn, normalized, user_id)
        result["invitation_kind"] = "legacy"
        return result

    row = _admin_invitation_row(conn, normalized, email)
    if row is None:
        raise ValueError("Invalid, already used, or expired invitation")
    updated = conn.execute(
        """UPDATE professor_invitations
           SET status='redeemed', use_count=COALESCE(use_count, 0)+1,
               last_used_at=?, redeemed_at=?, redeemed_by=?
           WHERE id=? AND lower(COALESCE(status, 'active'))='active'
             AND COALESCE(use_count, 0) < COALESCE(max_uses, 1)""",
        (
            datetime.now(timezone.utc).isoformat(),
            datetime.now(timezone.utc).isoformat(),
            user_id,
            row["id"],
        ),
    ).rowcount
    if updated != 1:
        raise ValueError("Invitation was already used")
    result = dict(row)
    result["invitation_kind"] = "admin_v2"
    return result


def _add_invitation_membership(
    conn: sqlite3.Connection,
    user_id: str,
    invitation: Dict[str, Any],
    fallback_university: str,
) -> None:
    organization_id = invitation.get("organization_id")
    if organization_id:
        organization = conn.execute(
            "SELECT 1 FROM organizations WHERE id=?", (organization_id,)
        ).fetchone()
        if organization is None:
            raise ValueError("Invitation organization no longer exists")
        conn.execute(
            "INSERT OR IGNORE INTO memberships (id,user_id,org_id,role) VALUES (?,?,?,'professor')",
            (str(uuid.uuid4()), user_id, organization_id),
        )
        return
    _add_org_membership(
        conn, user_id, invitation.get("university_name") or fallback_university
    )


def activate_password_professor(*, code: str, username: str, email: str, name: str,
                                university_name: str, password_hash: str) -> Dict[str, Any]:
    ensure_identity_schema()
    username = username.strip()
    email = email.strip().lower()
    if not username or not email or not name.strip():
        raise ValueError("Name, email, and username are required")
    with db._lock:
        # This multi-statement unit of work must not share the legacy process-
        # wide connection: an unrelated request could otherwise commit or roll
        # back its partially completed enrollment. BEGIN IMMEDIATE also
        # serializes competing redemptions from other workers/processes.
        conn = db.connect(check_same_thread=False)
        try:
            conn.execute("BEGIN IMMEDIATE")
            # Validate and reserve the invitation before checking account
            # uniqueness. This makes replay semantics authoritative: a holder
            # of an already-consumed secret always receives the same 409,
            # rather than a misleading email-exists response. Any later
            # conflict rolls the reservation back with the transaction.
            code_info = _consume_invitation(conn, code, username, email)
            if conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
                raise ValueError("Username already exists")
            if conn.execute("SELECT 1 FROM users WHERE lower(email)=?", (email,)).fetchone():
                raise ValueError("Email already exists")
            invitation_university = code_info.get("university_name") or university_name.strip()
            conn.execute(
                "INSERT INTO users (username,password_hash,role,name,email,provider,provider_uid,must_change_password) VALUES (?,?,?,?,?,'password',?,0)",
                (username, password_hash, "professor", name.strip(), email, username),
            )
            conn.execute(
                "INSERT INTO auth_identities (id,user_id,provider,provider_subject,email,created_at,last_login_at) VALUES (?,?, 'password',?,?,?,?)",
                (str(uuid.uuid4()), username, username, email, time.time(), time.time()),
            )
            _add_invitation_membership(conn, username, code_info, invitation_university)
            conn.commit()
            return {"username": username, "role": "professor", "email": email, "name": name.strip()}
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def find_social_user(provider: str, subject: str) -> Optional[Dict[str, Any]]:
    ensure_identity_schema()
    conn = db._get_conn()
    row = conn.execute(
        "SELECT u.* FROM auth_identities i JOIN users u ON u.username=i.user_id WHERE i.provider=? AND i.provider_subject=?",
        (provider, subject),
    ).fetchone()
    if row:
        conn.execute("UPDATE auth_identities SET last_login_at=? WHERE provider=? AND provider_subject=?", (time.time(), provider, subject))
        conn.commit()
        return dict(row)
    # One-time migration for existing legacy social records; never merge by email.
    legacy = conn.execute(
        "SELECT * FROM users WHERE provider=? AND provider_uid=?", (provider, subject)
    ).fetchone()
    if legacy:
        try:
            conn.execute(
                "INSERT INTO auth_identities (id,user_id,provider,provider_subject,email,created_at,last_login_at) VALUES (?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), legacy["username"], provider, subject, legacy["email"] or "", time.time(), time.time()),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()
        return dict(legacy)
    return None


def enroll_social_professor(*, provider: str, subject: str, email: str, name: str, code: str,
                            password_hash: str) -> Dict[str, Any]:
    ensure_identity_schema()
    internal_id = f"{provider}_{hashlib.sha256(subject.encode()).hexdigest()[:24]}"
    with db._lock:
        conn = db.connect(check_same_thread=False)
        try:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT user_id FROM auth_identities WHERE provider=? AND provider_subject=?",
                (provider, subject),
            ).fetchone()
            if existing:
                user = conn.execute("SELECT * FROM users WHERE username=?", (existing["user_id"],)).fetchone()
                conn.commit()
                return dict(user)
            code_info = _consume_invitation(conn, code, internal_id, email)
            conn.execute(
                "INSERT INTO users (username,password_hash,role,name,email,provider,provider_uid,must_change_password) VALUES (?,?,?,?,?,?,?,0)",
                (internal_id, password_hash, "professor", name.strip(), email.strip().lower(), provider, subject),
            )
            conn.execute(
                "INSERT INTO auth_identities (id,user_id,provider,provider_subject,email,created_at,last_login_at) VALUES (?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), internal_id, provider, subject, email.strip().lower(), time.time(), time.time()),
            )
            _add_invitation_membership(conn, internal_id, code_info, "")
            conn.commit()
            return dict(conn.execute("SELECT * FROM users WHERE username=?", (internal_id,)).fetchone())
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
