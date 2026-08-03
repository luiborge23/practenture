"""SQLite persistence for Admin V2 users; schema ownership remains with migrations."""
from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
import sqlite3
from typing import Any
from uuid import uuid4

from database import db
from .errors import AdminError

_SORT_COLUMNS = {
    "username": "lower(u.username)",
    "name": "lower(COALESCE(u.name, ''))",
    "email": "lower(COALESCE(u.email, ''))",
    "role": "u.role",
    "status": "COALESCE(u.status, 'active')",
    "createdAt": "u.created_at",
    "lastLoginAt": "COALESCE(u.last_login_at, '')",
}


@dataclass(frozen=True)
class UserRecord:
    id: str
    username: str
    role: str
    status: str
    name: str | None
    email: str | None
    provider: str
    organization_ids: list[str]
    must_change_password: bool
    last_login_at: str | None
    created_by: str | None
    created_at: str | None
    disabled_at: str | None
    disabled_by: str | None
    disable_reason: str | None


@dataclass(frozen=True)
class UserPage:
    items: list[UserRecord]
    total_count: int
    next_cursor: str | None


def _fingerprint(search: str | None, role: str | None, status: str | None, organization_id: str | None, sort: str) -> str:
    raw = json.dumps({"search": search or "", "role": role or "", "status": status or "", "organizationId": organization_id or "", "sort": sort}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _encode_cursor(offset: int, fingerprint: str) -> str:
    raw = json.dumps({"v": 1, "o": offset, "f": fingerprint}, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _decode_cursor(cursor: str | None, fingerprint: str) -> int:
    if cursor is None:
        return 0
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        value = json.loads(base64.urlsafe_b64decode(padded).decode())
        if value.get("v") != 1 or value.get("f") != fingerprint or not isinstance(value.get("o"), int) or value["o"] < 0:
            raise ValueError
        return value["o"]
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeDecodeError):
        raise AdminError(400, "ADMIN_CURSOR_INVALID", "Cursor is invalid for this query")


class UserRepository:
    def __init__(self, database=db) -> None:
        self._db = database

    @staticmethod
    def _select_sql() -> str:
        return """
            SELECT u.username, u.role, COALESCE(u.status, 'active') status,
                   u.name, u.email, COALESCE(u.provider, 'password') provider,
                   COALESCE(u.must_change_password, 0) must_change_password,
                   u.last_login_at, u.created_by, u.created_at, u.disabled_at,
                   u.disabled_by, u.disable_reason,
                   COALESCE((SELECT json_group_array(org_id) FROM
                       (SELECT m.org_id FROM memberships m WHERE m.user_id=u.username ORDER BY m.org_id)), '[]') organization_ids
            FROM users u
        """

    @staticmethod
    def _record(row: sqlite3.Row) -> UserRecord:
        return UserRecord(
            id=str(row["username"]), username=str(row["username"]), role=str(row["role"]),
            status=str(row["status"]), name=row["name"], email=row["email"], provider=str(row["provider"]),
            organization_ids=list(json.loads(row["organization_ids"])),
            must_change_password=bool(row["must_change_password"]), last_login_at=row["last_login_at"],
            created_by=row["created_by"], created_at=row["created_at"], disabled_at=row["disabled_at"],
            disabled_by=row["disabled_by"], disable_reason=row["disable_reason"],
        )

    def get(self, user_id: str, *, conn: sqlite3.Connection | None = None) -> UserRecord | None:
        owned = conn is None
        connection = conn or self._db.connect()
        try:
            row = connection.execute(
                self._select_sql()
                + " WHERE u.username=? AND COALESCE(u.status, 'active')<>'deleted'",
                (user_id,),
            ).fetchone()
            return self._record(row) if row else None
        finally:
            if owned:
                connection.close()

    def list(self, *, search: str | None, role: str | None, status: str | None, organization_id: str | None, sort: str, cursor: str | None, limit: int) -> UserPage:
        descending = sort.startswith("-")
        sort_name = sort[1:] if descending else sort
        if sort_name not in _SORT_COLUMNS:
            raise AdminError(400, "ADMIN_SORT_INVALID", "Unsupported user sort")
        normalized_search = search.strip() if search else None
        normalized_sort = ("-" if descending else "") + sort_name
        fingerprint = _fingerprint(normalized_search, role, status, organization_id, normalized_sort)
        offset = _decode_cursor(cursor, fingerprint)
        where: list[str] = ["COALESCE(u.status, 'active')<>'deleted'"]
        params: list[Any] = []
        if normalized_search:
            where.append("(lower(u.username) LIKE ? OR lower(COALESCE(u.name,'')) LIKE ? OR lower(COALESCE(u.email,'')) LIKE ?)")
            needle = f"%{normalized_search.casefold()}%"
            params.extend([needle, needle, needle])
        if role:
            where.append("u.role=?")
            params.append(role)
        if status:
            where.append("COALESCE(u.status, 'active')=?")
            params.append(status)
        if organization_id:
            where.append("EXISTS (SELECT 1 FROM memberships mf WHERE mf.user_id=u.username AND mf.org_id=?)")
            params.append(organization_id)
        where_sql = " WHERE " + " AND ".join(where) if where else ""
        direction = "DESC" if descending else "ASC"
        conn = self._db.connect()
        try:
            total = int(conn.execute("SELECT COUNT(*) FROM users u" + where_sql, params).fetchone()[0])
            rows = conn.execute(self._select_sql() + where_sql + f" ORDER BY {_SORT_COLUMNS[sort_name]} {direction}, u.username {direction} LIMIT ? OFFSET ?", [*params, limit + 1, offset]).fetchall()
            has_next = len(rows) > limit
            return UserPage([self._record(row) for row in rows[:limit]], total, _encode_cursor(offset + limit, fingerprint) if has_next else None)
        finally:
            conn.close()

    def create(self, conn: sqlite3.Connection, *, username: str, password_hash: str, role: str, name: str, email: str, organization_id: str | None, created_by: str) -> UserRecord:
        if conn.execute("SELECT 1 FROM users WHERE lower(username)=lower(?) OR lower(COALESCE(email,''))=lower(?)", (username, email)).fetchone():
            raise AdminError(409, "ADMIN_USER_CONFLICT", "Username or email already exists")
        if organization_id and not conn.execute("SELECT 1 FROM organizations WHERE id=?", (organization_id,)).fetchone():
            raise AdminError(404, "ADMIN_ORGANIZATION_NOT_FOUND", "Organization not found")
        try:
            conn.execute("""INSERT INTO users
                (username,password_hash,role,name,email,provider,provider_uid,must_change_password,status,created_by)
                VALUES (?,?,?,?,?,'password',?,1,'active',?)""",
                (username, password_hash, role, name, email, username, created_by))
            if organization_id:
                conn.execute("INSERT INTO memberships (id,user_id,org_id,role) VALUES (?,?,?,?)", (f"membership_{uuid4()}", username, organization_id, role))
        except sqlite3.IntegrityError as exc:
            raise AdminError(409, "ADMIN_USER_CONFLICT", "Username or email already exists") from exc
        record = self.get(username, conn=conn)
        assert record is not None
        return record

    def set_status(self, conn: sqlite3.Connection, *, user_id: str, status: str, actor_id: str, reason: str | None, now: str) -> UserRecord:
        current = self.get(user_id, conn=conn)
        if current is None:
            raise AdminError(404, "ADMIN_USER_NOT_FOUND", "User not found")
        if status == "suspended":
            conn.execute("UPDATE users SET status='suspended',disabled_at=?,disabled_by=?,disable_reason=? WHERE username=?", (now, actor_id, reason, user_id))
        else:
            conn.execute("UPDATE users SET status='active',disabled_at=NULL,disabled_by=NULL,disable_reason=NULL WHERE username=?", (user_id,))
        record = self.get(user_id, conn=conn)
        assert record is not None
        return record

    def require_password_reset(self, conn: sqlite3.Connection, user_id: str) -> UserRecord:
        if conn.execute("UPDATE users SET must_change_password=1 WHERE username=?", (user_id,)).rowcount != 1:
            raise AdminError(404, "ADMIN_USER_NOT_FOUND", "User not found")
        record = self.get(user_id, conn=conn)
        assert record is not None
        return record

    @staticmethod
    def revoke_sessions(conn: sqlite3.Connection, user_id: str, *, now: str, reason: str) -> None:
        if not conn.execute("SELECT 1 FROM users WHERE username=?", (user_id,)).fetchone():
            raise AdminError(404, "ADMIN_USER_NOT_FOUND", "User not found")
        # Access JWTs are invalidated by the same persisted cutoff enforced by auth.decode_token.
        conn.execute("UPDATE users SET password_changed_at=? WHERE username=?", (now, user_id))
        conn.execute("UPDATE refresh_tokens SET revoked=1 WHERE user_id=? AND revoked=0", (user_id,))
        conn.execute("UPDATE admin_sessions SET revoked_at=?,revocation_reason=? WHERE owner_user_id=? AND revoked_at IS NULL", (now, reason, user_id))
