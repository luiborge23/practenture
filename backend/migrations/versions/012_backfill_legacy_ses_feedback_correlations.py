"""Backfill privacy-preserving feedback correlation for legacy SES acceptance."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from ses_suppression import (
    SES_FEEDBACK_CORRELATION_RETENTION,
    recipient_suppression_hash,
)

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _accepted_at(value: object) -> datetime:
    """Parse a required acceptance timestamp and canonicalize it to UTC."""
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError("eligible SES delivery has an invalid acceptance timestamp")
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("timestamp is not timezone-aware")
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError) as exc:
        raise RuntimeError(
            "eligible SES delivery has an invalid acceptance timestamp"
        ) from exc


def _recipient_hash(value: object) -> str:
    """Return a keyed recipient hash or fail before recording invalid evidence."""
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError("eligible SES delivery has an invalid recipient")
    recipient_hash = recipient_suppression_hash(value, required=True)
    if recipient_hash is None:  # Defensive: required=True must never return None.
        raise RuntimeError("email suppression key is not configured")
    return recipient_hash


def upgrade() -> None:
    conn = op.get_bind()
    deliveries = conn.execute(sa.text("""
        SELECT recipient_email, provider_message_id, updated_at
        FROM invitation_email_deliveries
        WHERE state = 'accepted'
          AND provider = 'ses'
          AND provider_message_id IS NOT NULL
          AND length(trim(provider_message_id)) > 0
        ORDER BY id
    """)).fetchall()

    for delivery in deliveries:
        accepted = _accepted_at(delivery.updated_at)
        accepted_at = accepted.isoformat()
        feedback_expires_at = (
            accepted + SES_FEEDBACK_CORRELATION_RETENTION
        ).isoformat()
        recipient_hash = _recipient_hash(delivery.recipient_email)

        expected = (
            "ses",
            delivery.provider_message_id,
            recipient_hash,
            accepted_at,
            feedback_expires_at,
        )
        existing = conn.execute(sa.text("""
            SELECT provider, provider_message_id, recipient_hash, accepted_at,
                   feedback_expires_at
            FROM ses_feedback_correlations
            WHERE provider = 'ses' AND provider_message_id = :message_id
        """), {"message_id": delivery.provider_message_id}).fetchone()
        if existing is not None:
            if tuple(existing) != expected:
                raise RuntimeError(
                    "existing SES feedback correlation does not match legacy delivery"
                )
            continue

        conn.execute(sa.text("""
            INSERT INTO ses_feedback_correlations
                (provider, provider_message_id, recipient_hash, accepted_at,
                 feedback_expires_at)
            VALUES (:provider, :message_id, :recipient_hash, :accepted_at,
                    :feedback_expires_at)
        """), {
            "provider": expected[0],
            "message_id": expected[1],
            "recipient_hash": expected[2],
            "accepted_at": expected[3],
            "feedback_expires_at": expected[4],
        })


def downgrade() -> None:
    # Correlations are retention evidence and intentionally survive rollback.
    pass