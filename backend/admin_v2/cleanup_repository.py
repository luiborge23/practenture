"""SQLite persistence for bounded cleanup plans; never imports legacy cleanup code."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import json
import sqlite3
from typing import Any
from database import Database, db

COUNT_KEYS = ("sessions", "decisions", "results", "teamStates", "announcements")

def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))

class CleanupRepository:
    def __init__(self, database: Database = db) -> None:
        self.database = database

    @staticmethod
    def _placeholders(codes: list[str]) -> str:
        return ",".join("?" for _ in codes)

    def preview_counts(self, codes: list[str], conn: sqlite3.Connection | None = None) -> dict[str, int]:
        owned = conn is None
        connection = conn or self.database.connect()
        marks = self._placeholders(codes)
        try:
            return {
                "sessions": int(connection.execute(f"SELECT COUNT(*) FROM sessions WHERE code IN ({marks})", codes).fetchone()[0]),
                "decisions": int(connection.execute(f"SELECT COUNT(*) FROM decisions WHERE session_code IN ({marks})", codes).fetchone()[0]),
                "results": int(connection.execute(f"SELECT COUNT(*) FROM results WHERE session_code IN ({marks})", codes).fetchone()[0]),
                "teamStates": int(connection.execute(f"SELECT COUNT(*) FROM team_states WHERE session_code IN ({marks})", codes).fetchone()[0]),
                "announcements": int(connection.execute(f"SELECT COUNT(*) FROM announcements WHERE session_id IN (SELECT session_id FROM sessions WHERE code IN ({marks}))", codes).fetchone()[0]),
            }
        finally:
            if owned: connection.close()

    def insert_plan(self, *, plan_id: str, selector: dict, plan_hash: str, counts: dict, owner_id: str, created_at: str, expires_at: str) -> None:
        conn = self.database.connect()
        try:
            conn.execute("INSERT INTO cleanup_plans(id,selector_json,plan_hash,preview_counts,total_rows,status,created_by,expires_at,created_at) VALUES(?,?,?,?,?,'pending',?,?,?)", (plan_id, canonical_json(selector), plan_hash, canonical_json(counts), sum(counts.values()), owner_id, expires_at, created_at))
            conn.commit()
        finally: conn.close()

    @staticmethod
    def _row_to_plan(row: sqlite3.Row | None) -> dict | None:
        if row is None: return None
        return {"id":row["id"], "selector":json.loads(row["selector_json"]), "planHash":row["plan_hash"], "previewCounts":json.loads(row["preview_counts"]), "totalRows":int(row["total_rows"]), "status":row["status"], "createdBy":row["created_by"], "executedBy":row["executed_by"], "expiresAt":row["expires_at"], "createdAt":row["created_at"], "executedAt":row["executed_at"]}

    def get_plan(self, plan_id: str, conn: sqlite3.Connection | None = None) -> dict | None:
        owned=conn is None; connection=conn or self.database.connect()
        try: return self._row_to_plan(connection.execute("SELECT * FROM cleanup_plans WHERE id=?", (plan_id,)).fetchone())
        finally:
            if owned: connection.close()

    @staticmethod
    def verified_recent_backup(conn: sqlite3.Connection, now: datetime) -> bool:
        row=conn.execute("SELECT id,started_at,ended_at,status,checksum,database_size,integrity_result FROM backup_runs WHERE status='succeeded' ORDER BY COALESCE(ended_at,started_at) DESC LIMIT 1").fetchone()
        if row is None:
            return False
        checksum = str(row["checksum"] or "")
        if (
            len(checksum) != 64
            or any(char not in "0123456789abcdef" for char in checksum)
            or not isinstance(row["database_size"], int)
            or row["database_size"] <= 0
            or not row["ended_at"]
        ):
            return False
        try:
            ended=datetime.fromisoformat(str(row["ended_at"]).replace("Z","+00:00")).astimezone(timezone.utc)
            result=json.loads(row["integrity_result"])
        except (ValueError, TypeError, json.JSONDecodeError): return False
        if ended > now or now-ended > timedelta(hours=1): return False
        if result.get("quickCheck") != "ok" or result.get("integrityCheck") != "ok" or result.get("foreignKeyViolations") != 0: return False
        return conn.execute("SELECT 1 FROM restore_drills WHERE backup_id=? AND status='succeeded' LIMIT 1", (row["id"],)).fetchone() is not None

    def delete_selected(self, conn: sqlite3.Connection, codes: list[str]) -> dict[str, int]:
        marks=self._placeholders(codes)
        deleted={}
        deleted["announcements"]=conn.execute(f"DELETE FROM announcements WHERE session_id IN (SELECT session_id FROM sessions WHERE code IN ({marks}))", codes).rowcount
        deleted["decisions"]=conn.execute(f"DELETE FROM decisions WHERE session_code IN ({marks})", codes).rowcount
        deleted["results"]=conn.execute(f"DELETE FROM results WHERE session_code IN ({marks})", codes).rowcount
        deleted["teamStates"]=conn.execute(f"DELETE FROM team_states WHERE session_code IN ({marks})", codes).rowcount
        deleted["sessions"]=conn.execute(f"DELETE FROM sessions WHERE code IN ({marks})", codes).rowcount
        return {key:int(deleted[key]) for key in COUNT_KEYS}

    @staticmethod
    def complete_plan(conn: sqlite3.Connection, plan_id: str, owner_id: str, completed_at: str) -> None:
        updated=conn.execute("UPDATE cleanup_plans SET status='completed',executed_by=?,executed_at=? WHERE id=? AND status='pending'", (owner_id,completed_at,plan_id))
        if updated.rowcount != 1: raise RuntimeError("cleanup plan completion failed")
