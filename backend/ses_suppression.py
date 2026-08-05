"""Privacy-preserving recipient suppression helpers for SES delivery."""
from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3


def normalize_recipient(email: str) -> str:
    return email.strip().casefold()


def recipient_suppression_hash(email: str, *, required: bool = False) -> str | None:
    raw = os.environ.get("PRACTENTURE_EMAIL_SUPPRESSION_KEY", "").strip()
    if not raw:
        if required:
            raise RuntimeError("email suppression key is not configured")
        return None
    try:
        key = bytes.fromhex(raw)
    except ValueError as exc:
        raise RuntimeError("email suppression key must be hexadecimal") from exc
    if len(key) < 32:
        raise RuntimeError("email suppression key must contain at least 32 bytes")
    return hmac.new(key, normalize_recipient(email).encode("utf-8"), hashlib.sha256).hexdigest()


def upsert_recipient_suppression(
    conn: sqlite3.Connection, *, recipient_hash: str, reason: str, observed_at: str
) -> None:
    """Record terminal SES feedback without requiring recipient plaintext."""
    conn.execute(
        """INSERT INTO ses_recipient_suppressions
               (recipient_hash, reason, first_observed_at, last_observed_at, active)
           VALUES (?, ?, ?, ?, 1)
           ON CONFLICT(recipient_hash) DO UPDATE SET
               reason=excluded.reason, last_observed_at=excluded.last_observed_at, active=1""",
        (recipient_hash, reason, observed_at, observed_at),
    )
