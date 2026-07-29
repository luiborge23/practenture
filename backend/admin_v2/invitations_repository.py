"""SQLite persistence for Admin V2 invitations.

Only secret hashes are persisted. Read models deliberately do not select the
secret hash so it cannot accidentally enter list/detail responses or audit data.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
import sqlite3
from typing import Any

from database import db
from .errors import AdminError


_SORT_COLUMNS = {
    "createdAt": "created_at",
    "expiresAt": "i.expires_at",
    "intendedEmail": "lower(i.intended_email)",
    "status": "effective_status",
}


@dataclass(frozen=True)
class InvitationRecord:
    id: str
    organization_id: str
    intended_email: str
    status: str
    masked_code: str
    expires_at: str
    issued_by: str | None
    created_at: str
    revoked_at: str | None
    revoked_by: str | None
    redeemed_at: str | None
    notes: str | None
    change_ticket: str | None


@dataclass(frozen=True)
class InvitationPage:
    items: list[InvitationRecord]
    total_count: int
    next_cursor: str | None


def hash_invitation_secret(secret: str) -> str:
    """Hash a high-entropy invitation secret for at-rest storage."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _fingerprint(
    *, search: str | None, organization_id: str | None, status: str | None, sort: str
) -> str:
    raw = json.dumps(
        {
            "search": search or "",
            "organizationId": organization_id or "",
            "status": status or "",
            "sort": sort,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _encode_cursor(offset: int, fingerprint: str) -> str:
    raw = json.dumps({"v": 1, "o": offset, "f": fingerprint}, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _decode_cursor(cursor: str | None, fingerprint: str) -> int:
    if cursor is None:
        return 0
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        value = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
        if (
            value.get("v") != 1
            or value.get("f") != fingerprint
            or not isinstance(value.get("o"), int)
            or value["o"] < 0
        ):
            raise ValueError
        return value["o"]
    except (
        AttributeError,
        ValueError,
        TypeError,
        KeyError,
        binascii.Error,
        json.JSONDecodeError,
        UnicodeDecodeError,
    ):
        raise AdminError(400, "ADMIN_CURSOR_INVALID", "Cursor is invalid for this query")


class InvitationRepository:
    def __init__(self, database=db) -> None:
        self._db = database

    @staticmethod
    def _select_sql() -> str:
        return """
            SELECT i.id, i.organization_id, i.intended_email,
                   CASE
                       WHEN lower(COALESCE(i.status, 'active'))='active'
                            AND i.expires_at <= ? THEN 'expired'
                       ELSE lower(COALESCE(i.status, 'active'))
                   END AS effective_status,
                   i.masked_code, i.expires_at, i.issued_by,
                   COALESCE(
                       (SELECT MIN(a.occurred_at)
                        FROM admin_audit_events a
                        WHERE a.action='invitation.create'
                          AND json_extract(a.target_json, '$.id')=i.id),
                       i.expires_at
                   ) AS created_at,
                   i.revoked_at, i.revoked_by, i.redeemed_at,
                   i.notes, i.change_ticket
            FROM professor_invitations i
        """

    @staticmethod
    def _record(row: sqlite3.Row) -> InvitationRecord:
        return InvitationRecord(
            id=str(row["id"]),
            organization_id=str(row["organization_id"]),
            intended_email=str(row["intended_email"]),
            status=str(row["effective_status"]).upper(),
            masked_code=str(row["masked_code"]),
            expires_at=str(row["expires_at"]),
            issued_by=row["issued_by"],
            created_at=str(row["created_at"]),
            revoked_at=row["revoked_at"],
            revoked_by=row["revoked_by"],
            redeemed_at=row["redeemed_at"],
            notes=row["notes"],
            change_ticket=row["change_ticket"],
        )

    def get(
        self, invitation_id: str, *, conn: sqlite3.Connection | None = None,
        now: datetime | None = None,
    ) -> InvitationRecord | None:
        owned = conn is None
        connection = conn or self._db.connect()
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
        try:
            row = connection.execute(
                self._select_sql() + " WHERE i.id=?", (current, invitation_id)
            ).fetchone()
            return self._record(row) if row else None
        finally:
            if owned:
                connection.close()

    def list(
        self,
        *,
        search: str | None,
        organization_id: str | None,
        status: str | None,
        sort: str,
        cursor: str | None,
        limit: int,
    ) -> InvitationPage:
        descending = sort.startswith("-")
        sort_name = sort[1:] if descending else sort
        if sort_name not in _SORT_COLUMNS:
            raise AdminError(400, "ADMIN_SORT_INVALID", "Unsupported invitation sort")
        normalized_search = search.strip().casefold() if search and search.strip() else None
        normalized_sort = ("-" if descending else "") + sort_name
        fingerprint = _fingerprint(
            search=normalized_search,
            organization_id=organization_id,
            status=status,
            sort=normalized_sort,
        )
        offset = _decode_cursor(cursor, fingerprint)
        now = datetime.now(timezone.utc).isoformat()
        where: list[str] = []
        params: list[Any] = []
        if normalized_search:
            where.append("(lower(i.intended_email) LIKE ? OR lower(i.masked_code) LIKE ?)")
            needle = f"%{normalized_search}%"
            params.extend((needle, needle))
        if organization_id:
            where.append("i.organization_id=?")
            params.append(organization_id)
        if status:
            where.append(
                "(CASE WHEN lower(COALESCE(i.status, 'active'))='active' AND i.expires_at <= ? "
                "THEN 'expired' ELSE lower(COALESCE(i.status, 'active')) END)=?"
            )
            params.extend((now, status.casefold()))
        where_sql = " WHERE " + " AND ".join(where) if where else ""
        direction = "DESC" if descending else "ASC"

        conn = self._db.connect()
        try:
            total = conn.execute(
                "SELECT COUNT(*) FROM professor_invitations i" + where_sql, params
            ).fetchone()[0]
            rows = conn.execute(
                self._select_sql()
                + where_sql
                + f" ORDER BY {_SORT_COLUMNS[sort_name]} {direction}, i.id {direction} "
                "LIMIT ? OFFSET ?",
                [now, *params, limit + 1, offset],
            ).fetchall()
        finally:
            conn.close()
        has_next = len(rows) > limit
        return InvitationPage(
            items=[self._record(row) for row in rows[:limit]],
            total_count=int(total),
            next_cursor=_encode_cursor(offset + limit, fingerprint) if has_next else None,
        )

    def create(
        self,
        conn: sqlite3.Connection,
        *,
        invitation_id: str,
        secret_hash: str,
        masked_code: str,
        organization_id: str,
        intended_email: str,
        expires_at: str,
        issued_by: str,
        notes: str | None,
        change_ticket: str | None,
        created_at: str,
    ) -> InvitationRecord:
        organization = conn.execute(
            "SELECT 1 FROM organizations WHERE id=?", (organization_id,)
        ).fetchone()
        if organization is None:
            raise AdminError(404, "ADMIN_ORGANIZATION_NOT_FOUND", "Organization not found")
        conn.execute(
            """INSERT INTO professor_invitations
               (id, secret_hash, masked_code, organization_id, intended_email,
                status, expires_at, max_uses, use_count, issued_by, notes,
                change_ticket)
               VALUES (?, ?, ?, ?, ?, 'active', ?, 1, 0, ?, ?, ?)""",
            (
                invitation_id, secret_hash, masked_code, organization_id,
                intended_email, expires_at, issued_by, notes, change_ticket,
            ),
        )
        record = self.get(invitation_id, conn=conn, now=datetime.fromisoformat(created_at))
        assert record is not None
        return replace(record, created_at=created_at)

    def revoke(
        self,
        conn: sqlite3.Connection,
        *,
        invitation_id: str,
        revoked_by: str,
        now: datetime,
    ) -> InvitationRecord:
        current = self.get(invitation_id, conn=conn, now=now)
        if current is None:
            raise AdminError(404, "ADMIN_INVITATION_NOT_FOUND", "Invitation not found")
        if current.status != "ACTIVE":
            raise AdminError(409, "ADMIN_INVITATION_NOT_ACTIVE", "Invitation is not active")
        result = conn.execute(
            """UPDATE professor_invitations
               SET status='revoked', revoked_at=?, revoked_by=?
               WHERE id=? AND lower(status)='active' AND expires_at>?""",
            (now.isoformat(), revoked_by, invitation_id, now.isoformat()),
        )
        if result.rowcount != 1:
            raise AdminError(409, "ADMIN_INVITATION_NOT_ACTIVE", "Invitation is not active")
        updated = self.get(invitation_id, conn=conn, now=now)
        assert updated is not None
        return updated

    def resend(
        self,
        conn: sqlite3.Connection,
        *,
        invitation_id: str,
        secret_hash: str,
        masked_code: str,
        expires_at: str,
        now: datetime,
    ) -> InvitationRecord:
        current = self.get(invitation_id, conn=conn, now=now)
        if current is None:
            raise AdminError(404, "ADMIN_INVITATION_NOT_FOUND", "Invitation not found")
        if current.status != "ACTIVE":
            raise AdminError(409, "ADMIN_INVITATION_NOT_ACTIVE", "Invitation is not active")
        result = conn.execute(
            """UPDATE professor_invitations
               SET secret_hash=?, masked_code=?, expires_at=?
               WHERE id=? AND lower(status)='active' AND expires_at>?""",
            (secret_hash, masked_code, expires_at, invitation_id, now.isoformat()),
        )
        if result.rowcount != 1:
            raise AdminError(409, "ADMIN_INVITATION_NOT_ACTIVE", "Invitation is not active")
        updated = self.get(invitation_id, conn=conn, now=now)
        assert updated is not None
        return updated
