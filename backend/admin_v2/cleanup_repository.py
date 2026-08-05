"""SQLite persistence for bounded cleanup plans; never imports legacy cleanup code."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import sqlite3
from typing import Any

from database import Database, db

SESSION_COUNT_KEYS = (
    "sessions",
    "decisions",
    "results",
    "teamStates",
    "announcements",
    "createRequests",
)
INVITATION_COUNT_KEYS = ("invitations", "invitationEmailDeliveries")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))


class CleanupRepository:
    def __init__(self, database: Database = db) -> None:
        self.database = database

    @staticmethod
    def _placeholders(values: list[str]) -> str:
        return ",".join("?" for _ in values)

    def preview_counts(
        self, session_codes: list[str], invitation_ids: list[str] | None = None, conn: sqlite3.Connection | None = None
    ) -> dict[str, int]:
        invitation_ids = invitation_ids or []
        owned = conn is None
        connection = conn or self.database.connect()
        try:
            counts: dict[str, int] = {}
            if session_codes:
                marks = self._placeholders(session_codes)
                counts.update({
                    "sessions": int(connection.execute(f"SELECT COUNT(*) FROM sessions WHERE code IN ({marks})", session_codes).fetchone()[0]),
                    "decisions": int(connection.execute(f"SELECT COUNT(*) FROM decisions WHERE session_code IN ({marks})", session_codes).fetchone()[0]),
                    "results": int(connection.execute(f"SELECT COUNT(*) FROM results WHERE session_code IN ({marks})", session_codes).fetchone()[0]),
                    "teamStates": int(connection.execute(f"SELECT COUNT(*) FROM team_states WHERE session_code IN ({marks})", session_codes).fetchone()[0]),
                    "announcements": int(connection.execute(f"SELECT COUNT(*) FROM announcements WHERE session_id IN (SELECT session_id FROM sessions WHERE code IN ({marks}))", session_codes).fetchone()[0]),
                    "createRequests": int(connection.execute(f"SELECT COUNT(*) FROM session_create_requests WHERE session_code IN ({marks})", session_codes).fetchone()[0]),
                })
            if invitation_ids:
                marks = self._placeholders(invitation_ids)
                counts.update({
                    "invitations": int(connection.execute(f"SELECT COUNT(*) FROM professor_invitations WHERE id IN ({marks})", invitation_ids).fetchone()[0]),
                    "invitationEmailDeliveries": int(connection.execute(f"SELECT COUNT(*) FROM invitation_email_deliveries WHERE invitation_id IN ({marks})", invitation_ids).fetchone()[0]),
                })
            return counts
        finally:
            if owned:
                connection.close()

    @staticmethod
    def _utc(value: object) -> datetime | None:
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
        except (TypeError, ValueError):
            return None

    def invitation_blocker_count(self, invitation_ids: list[str], now: datetime, conn: sqlite3.Connection | None = None) -> int:
        if not invitation_ids:
            return 0
        owned = conn is None
        connection = conn or self.database.connect()
        try:
            marks = self._placeholders(invitation_ids)
            rows = connection.execute(
                f"SELECT id,status,expires_at FROM professor_invitations WHERE id IN ({marks})", invitation_ids
            ).fetchall()
            by_id = {str(row["id"]): row for row in rows}
            blockers = 0
            for invitation_id in invitation_ids:
                row = by_id.get(invitation_id)
                expires = self._utc(row["expires_at"]) if row is not None else None
                status = str(row["status"] or "").casefold() if row is not None else ""
                if row is None or (
                    status not in {"expired", "revoked", "redeemed"}
                    and (expires is None or expires > now)
                ):
                    blockers += 1
            return blockers
        finally:
            if owned:
                connection.close()

    def manifest(self, session_codes: list[str], invitation_ids: list[str], conn: sqlite3.Connection | None = None) -> dict[str, list[dict[str, object]]]:
        """Return internal-only stable identities used exclusively as HMAC input."""
        owned = conn is None
        connection = conn or self.database.connect()
        try:
            result: dict[str, list[dict[str, object]]] = {"sessions": [], "invitations": [], "deliveries": []}
            if session_codes:
                marks = self._placeholders(session_codes)
                for table, sql, columns in (
                    ("sessions", f"SELECT * FROM sessions WHERE code IN ({marks})", session_codes),
                    ("decisions", f"SELECT * FROM decisions WHERE session_code IN ({marks})", session_codes),
                    ("results", f"SELECT * FROM results WHERE session_code IN ({marks})", session_codes),
                    ("teamStates", f"SELECT * FROM team_states WHERE session_code IN ({marks})", session_codes),
                    ("announcements", f"SELECT * FROM announcements WHERE session_id IN (SELECT session_id FROM sessions WHERE code IN ({marks}))", session_codes),
                    ("createRequests", f"SELECT * FROM session_create_requests WHERE session_code IN ({marks})", session_codes),
                ):
                    result["sessions"].extend({"type": table, "row": dict(row)} for row in connection.execute(sql, columns).fetchall())
            if invitation_ids:
                marks = self._placeholders(invitation_ids)
                result["invitations"] = [
                    dict(row) for row in connection.execute(
                        f"SELECT id,status,expires_at,max_uses,use_count,revoked_at,revoked_by,redeemed_at,redeemed_by,created_at,last_used_at FROM professor_invitations WHERE id IN ({marks})", invitation_ids
                    ).fetchall()
                ]
                result["deliveries"] = [
                    dict(row) for row in connection.execute(
                        f"SELECT id,invitation_id,owner_id,idempotency_key_hash,request_fingerprint,state,provider,provider_message_id,failed_code,created_at,updated_at FROM invitation_email_deliveries WHERE invitation_id IN ({marks})", invitation_ids
                    ).fetchall()
                ]
            for rows in result.values():
                rows.sort(key=canonical_json)
            return result
        finally:
            if owned:
                connection.close()

    def insert_plan(self, *, plan_id: str, selector: dict, plan_hash: str, counts: dict, owner_id: str, created_at: str, expires_at: str) -> None:
        conn = self.database.connect()
        try:
            conn.execute("INSERT INTO cleanup_plans(id,selector_json,plan_hash,preview_counts,total_rows,status,created_by,expires_at,created_at) VALUES(?,?,?,?,?,'pending',?,?,?)", (plan_id, canonical_json(selector), plan_hash, canonical_json(counts), sum(counts.values()), owner_id, expires_at, created_at))
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _row_to_plan(row: sqlite3.Row | None) -> dict | None:
        if row is None:
            return None
        return {"id": row["id"], "selector": json.loads(row["selector_json"]), "planHash": row["plan_hash"], "previewCounts": json.loads(row["preview_counts"]), "totalRows": int(row["total_rows"]), "status": row["status"], "createdBy": row["created_by"], "executedBy": row["executed_by"], "expiresAt": row["expires_at"], "createdAt": row["created_at"], "executedAt": row["executed_at"]}

    def get_plan(self, plan_id: str, conn: sqlite3.Connection | None = None) -> dict | None:
        owned = conn is None
        connection = conn or self.database.connect()
        try:
            return self._row_to_plan(connection.execute("SELECT * FROM cleanup_plans WHERE id=?", (plan_id,)).fetchone())
        finally:
            if owned:
                connection.close()

    @staticmethod
    def verified_recent_backup(conn: sqlite3.Connection, now: datetime) -> bool:
        row = conn.execute("SELECT id,started_at,ended_at,status,checksum,database_size,integrity_result FROM backup_runs WHERE status='succeeded' ORDER BY COALESCE(ended_at,started_at) DESC LIMIT 1").fetchone()
        if row is None:
            return False
        checksum = str(row["checksum"] or "")
        if len(checksum) != 64 or any(char not in "0123456789abcdef" for char in checksum) or not isinstance(row["database_size"], int) or row["database_size"] <= 0 or not row["ended_at"]:
            return False
        try:
            ended = datetime.fromisoformat(str(row["ended_at"]).replace("Z", "+00:00")).astimezone(timezone.utc)
            result = json.loads(row["integrity_result"])
        except (ValueError, TypeError, json.JSONDecodeError):
            return False
        if ended > now or now - ended > timedelta(hours=1):
            return False
        if result.get("quickCheck") != "ok" or result.get("integrityCheck") != "ok" or result.get("foreignKeyViolations") != 0:
            return False
        return conn.execute("SELECT 1 FROM restore_drills WHERE backup_id=? AND status='succeeded' LIMIT 1", (row["id"],)).fetchone() is not None

    def delete_selected(self, conn: sqlite3.Connection, session_codes: list[str], invitation_ids: list[str] | None = None) -> dict[str, int]:
        invitation_ids = invitation_ids or []
        deleted: dict[str, int] = {}
        if session_codes:
            marks = self._placeholders(session_codes)
            deleted["announcements"] = conn.execute(f"DELETE FROM announcements WHERE session_id IN (SELECT session_id FROM sessions WHERE code IN ({marks}))", session_codes).rowcount
            deleted["decisions"] = conn.execute(f"DELETE FROM decisions WHERE session_code IN ({marks})", session_codes).rowcount
            deleted["results"] = conn.execute(f"DELETE FROM results WHERE session_code IN ({marks})", session_codes).rowcount
            deleted["teamStates"] = conn.execute(f"DELETE FROM team_states WHERE session_code IN ({marks})", session_codes).rowcount
            deleted["createRequests"] = conn.execute(f"DELETE FROM session_create_requests WHERE session_code IN ({marks})", session_codes).rowcount
            deleted["sessions"] = conn.execute(f"DELETE FROM sessions WHERE code IN ({marks})", session_codes).rowcount
        if invitation_ids:
            marks = self._placeholders(invitation_ids)
            deleted["invitationEmailDeliveries"] = conn.execute(f"DELETE FROM invitation_email_deliveries WHERE invitation_id IN ({marks})", invitation_ids).rowcount
            deleted["invitations"] = conn.execute(f"DELETE FROM professor_invitations WHERE id IN ({marks})", invitation_ids).rowcount
        return {key: int(deleted[key]) for key in (*SESSION_COUNT_KEYS, *INVITATION_COUNT_KEYS) if key in deleted}

    @staticmethod
    def complete_plan(conn: sqlite3.Connection, plan_id: str, owner_id: str, completed_at: str) -> None:
        updated = conn.execute("UPDATE cleanup_plans SET status='completed',executed_by=?,executed_at=? WHERE id=? AND status='pending'", (owner_id, completed_at, plan_id))
        if updated.rowcount != 1:
            raise RuntimeError("cleanup plan completion failed")
