"""SQLite persistence for Admin V2 invitations.

Only secret hashes are persisted. Read models deliberately do not select the
secret hash so it cannot accidentally enter list/detail responses or audit data.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import sqlite3
from typing import Any
from uuid import uuid4

from database import db
from .errors import AdminError
from .redaction import redact_secrets
from ses_suppression import recipient_suppression_hash

_SORT_COLUMNS = {
    "createdAt": "created_at",
    "expiresAt": "i.expires_at",
    "intendedEmail": "lower(i.intended_email)",
    "status": "effective_status",
}

# Accepted SES message IDs remain correlatable with feedback for one year.
SES_FEEDBACK_CORRELATION_RETENTION = timedelta(days=365)


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


@dataclass(frozen=True)
class EmailDeliveryRecord:
    id: str
    invitation_id: str
    recipient_email: str
    owner_id: str
    request_fingerprint: str
    state: str
    provider: str | None
    provider_message_id: str | None
    failed_code: str | None
    created_at: str
    updated_at: str


def hash_invitation_secret(secret: str) -> str:
    """Hash a high-entropy invitation secret for at-rest storage."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _redact_message_id(message_id: str | None) -> str | None:
    """Keep provider acceptance evidence useful without exposing its full value."""
    if not message_id:
        return None
    return f"ses:{message_id[:6]}...{message_id[-4:]}"


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
            where.append(
                "(lower(i.intended_email) LIKE ? OR lower(i.masked_code) LIKE ? "
                "OR lower(i.organization_id) LIKE ? OR lower(COALESCE(i.notes, '')) LIKE ? "
                "OR lower(COALESCE(i.change_ticket, '')) LIKE ?)"
            )
            needle = f"%{normalized_search}%"
            params.extend((needle, needle, needle, needle, needle))
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

    @staticmethod
    def _delivery(row: sqlite3.Row) -> EmailDeliveryRecord:
        return EmailDeliveryRecord(
            id=str(row["id"]), invitation_id=str(row["invitation_id"]),
            recipient_email=str(row["recipient_email"]), owner_id=str(row["owner_id"]),
            request_fingerprint=str(row["request_fingerprint"]), state=str(row["state"]),
            provider=row["provider"], provider_message_id=row["provider_message_id"],
            failed_code=row["failed_code"], created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def reserve_email_delivery(
        self, *, invitation_id: str, intended_email: str, secret: str, owner_id: str,
        idempotency_key: str, request_fingerprint: str, now: datetime,
    ) -> tuple[EmailDeliveryRecord, bool]:
        """Validate possession and atomically reserve exactly one SES call.

        The pending reservation is committed before the provider call because a
        database transaction cannot make an external call atomic. A duplicate
        key consequently cannot send a second email.
        """
        key_hash = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
        now_iso = now.astimezone(timezone.utc).isoformat()
        conn = self._db.connect()
        try:
            # A successful SES send must always have a feedback tombstone. Verify
            # this prerequisite before reserving the non-replayable provider call.
            try:
                suppression_hash = recipient_suppression_hash(intended_email, required=True)
            except RuntimeError as exc:
                raise AdminError(
                    503,
                    "ADMIN_EMAIL_SUPPRESSION_UNAVAILABLE",
                    "Email delivery is temporarily unavailable",
                ) from exc
            assert suppression_hash is not None
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT * FROM invitation_email_deliveries WHERE owner_id=? AND idempotency_key_hash=?",
                (owner_id, key_hash),
            ).fetchone()
            if existing is not None:
                delivery = self._delivery(existing)
                if not hmac.compare_digest(delivery.request_fingerprint, request_fingerprint):
                    raise AdminError(409, "ADMIN_IDEMPOTENCY_CONFLICT", "Idempotency key was already used for a different request")
                conn.commit()
                return delivery, False
            invitation = conn.execute(
                "SELECT secret_hash, intended_email, status, expires_at FROM professor_invitations WHERE id=?",
                (invitation_id,),
            ).fetchone()
            if invitation is None:
                raise AdminError(404, "ADMIN_INVITATION_NOT_FOUND", "Invitation not found")
            active = str(invitation[2]).casefold() == "active" and str(invitation[3]) > now_iso
            secret_matches = hmac.compare_digest(str(invitation[0]), hash_invitation_secret(secret))
            email_matches = hmac.compare_digest(str(invitation[1]), intended_email)
            if not active or not secret_matches or not email_matches:
                raise AdminError(409, "ADMIN_INVITATION_EMAIL_PROOF_INVALID", "The active invitation, email, or disclosed code is invalid")
            suppressed = conn.execute(
                "SELECT 1 FROM ses_recipient_suppressions WHERE recipient_hash=? AND active=1",
                (suppression_hash,),
            ).fetchone()
            if suppressed is not None:
                raise AdminError(409, "ADMIN_EMAIL_RECIPIENT_SUPPRESSED", "SES delivery is disabled for this recipient")
            delivery_id = f"idel_{uuid4()}"
            conn.execute(
                """INSERT INTO invitation_email_deliveries
                   (id, invitation_id, recipient_email, owner_id, idempotency_key_hash,
                    request_fingerprint, state, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
                (delivery_id, invitation_id, intended_email, owner_id, key_hash, request_fingerprint, now_iso, now_iso),
            )
            row = conn.execute("SELECT * FROM invitation_email_deliveries WHERE id=?", (delivery_id,)).fetchone()
            conn.commit()
            assert row is not None
            return self._delivery(row), True
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def finalize_email_delivery(
        self, *, delivery_id: str, accepted: bool, provider_message_id: str | None,
        failure_code: str | None, request_id: str, owner_id: str, now: datetime,
    ) -> EmailDeliveryRecord:
        """Persist provider acceptance/failure and immutable redacted audit evidence."""
        now_iso = now.astimezone(timezone.utc).isoformat()
        conn = self._db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            result = conn.execute(
                """UPDATE invitation_email_deliveries
                   SET state=?, provider=?, provider_message_id=?, failed_code=?, updated_at=?
                   WHERE id=? AND state='pending'""",
                ("accepted" if accepted else "failed", "ses" if accepted else None,
                 provider_message_id if accepted else None, failure_code if not accepted else None,
                 now_iso, delivery_id),
            )
            row = conn.execute("SELECT * FROM invitation_email_deliveries WHERE id=?", (delivery_id,)).fetchone()
            if row is None:
                raise RuntimeError("email delivery reservation disappeared")
            delivery = self._delivery(row)
            if result.rowcount == 1:
                if accepted:
                    try:
                        recipient_hash = recipient_suppression_hash(
                            delivery.recipient_email, required=True
                        )
                    except RuntimeError as exc:
                        raise AdminError(
                            503,
                            "ADMIN_EMAIL_SUPPRESSION_UNAVAILABLE",
                            "Email delivery is temporarily unavailable",
                        ) from exc
                    assert recipient_hash is not None
                    feedback_expires_at = (
                        now.astimezone(timezone.utc) + SES_FEEDBACK_CORRELATION_RETENTION
                    ).isoformat()
                    conn.execute(
                        """INSERT INTO ses_feedback_correlations
                           (provider, provider_message_id, recipient_hash, accepted_at,
                            feedback_expires_at)
                           VALUES ('ses', ?, ?, ?, ?)""",
                        (
                            provider_message_id,
                            recipient_hash,
                            now_iso,
                            feedback_expires_at,
                        ),
                    )
                metadata = redact_secrets({
                    "deliveryId": delivery.id, "invitationId": delivery.invitation_id,
                    "recipientEmail": delivery.recipient_email, "provider": delivery.provider,
                    "providerMessageId": _redact_message_id(delivery.provider_message_id),
                    "failedCode": delivery.failed_code,
                })
                conn.execute(
                    """INSERT INTO admin_audit_events
                       (id, request_id, actor_json, target_json, action, outcome, metadata_json, occurred_at)
                       VALUES (?, ?, ?, ?, 'invitation.email_delivery', ?, ?, ?)""",
                    (f"audit_{uuid4()}", request_id,
                     json.dumps({"id": owner_id, "role": "owner"}, separators=(",", ":")),
                     json.dumps({"type": "invitation", "id": delivery.invitation_id}, separators=(",", ":")),
                     "succeeded" if accepted else "failed", json.dumps(metadata, separators=(",", ":"), sort_keys=True), now_iso),
                )
            conn.commit()
            return delivery
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def redact_provider_message_id(message_id: str | None) -> str | None:
        return _redact_message_id(message_id)
