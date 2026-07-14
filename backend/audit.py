"""Audit logging for all authentication and authorization events.

SOTA: Every auth event is logged with actor, action, details, IP, timestamp.
This provides a per-tenant audit trail for security investigations.

Usage:
    from audit import log_event

    log_event(actor="prof_smith", action="login_success", details={"role": "professor"}, ip="1.2.3.4")
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Optional

from database import db


def log_event(
    actor: str,
    action: str,
    details: Optional[dict[str, Any]] = None,
    ip: str = "",
) -> None:
    """Log an audit event to the database.

    Args:
        actor: Username of the person performing the action
        action: Event type (login_success, login_failure, code_created, etc.)
        details: Optional dict of event-specific data
        ip: Request IP address
    """
    try:
        conn = db._get_conn()
        conn.execute(
            """INSERT INTO audit_logs (id, actor_username, action, details, ip_address, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()),
                actor,
                action,
                json.dumps(details) if details else "{}",
                ip,
                time.time(),
            ),
        )
        conn.commit()
    except Exception:
        # Audit logging should never break the request
        pass


def get_audit_logs(limit: int = 50, offset: int = 0, actor: str = "") -> list[dict]:
    """Retrieve audit logs (owner only)."""
    conn = db._get_conn()
    if actor:
        rows = conn.execute(
            """SELECT id, actor_username, action, details, ip_address, timestamp
               FROM audit_logs WHERE actor_username = ?
               ORDER BY timestamp DESC LIMIT ? OFFSET ?""",
            (actor, limit, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT id, actor_username, action, details, ip_address, timestamp
               FROM audit_logs ORDER BY timestamp DESC LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()

    return [
        {
            "id": r[0],
            "actor": r[1],
            "action": r[2],
            "details": json.loads(r[3]) if r[3] else {},
            "ip": r[4],
            "timestamp": r[5],
        }
        for r in rows
    ]
