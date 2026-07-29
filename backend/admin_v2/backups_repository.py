"""SQLite persistence for Admin V2 backup and restore-drill metadata."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from database import db


class BackupRepository:
    """Read existing migration-owned backup tables and write via caller transactions."""

    def __init__(self, database=db) -> None:
        self._db = database

    @staticmethod
    def _decode_result(raw: str | None) -> dict[str, Any]:
        if not raw:
            return {}
        try:
            value = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
        return value if isinstance(value, dict) else {}

    @classmethod
    def _map_backup(cls, row: sqlite3.Row) -> dict[str, Any]:
        verification_data = cls._decode_result(row[8])
        label = verification_data.pop("label", None)
        has_verification = all(
            key in verification_data
            for key in (
                "quickCheck",
                "integrityCheck",
                "foreignKeyViolations",
                "tableCounts",
            )
        )
        verification = None
        if has_verification:
            verification = {
                "quickCheck": str(verification_data["quickCheck"]),
                "integrityCheck": str(verification_data["integrityCheck"]),
                "foreignKeyViolations": int(verification_data["foreignKeyViolations"]),
                "tableCounts": {
                    str(name): int(count)
                    for name, count in verification_data["tableCounts"].items()
                },
            }
        return {
            "id": row[0],
            "status": row[1],
            "startedAt": row[2],
            "endedAt": row[3],
            "objectKey": row[4],
            "sha256": row[5],
            "databaseSize": int(row[6]) if row[6] is not None else None,
            "migrationVersion": row[7],
            "label": label,
            "verification": verification,
            "restoreDrillId": row[9],
        }

    def list_backups(self, limit: int) -> tuple[list[dict[str, Any]], int]:
        conn = self._db.connect()
        try:
            rows = conn.execute(
                """SELECT b.id, b.status, b.started_at, b.ended_at, b.object_key,
                          b.checksum, b.database_size, b.migration_version,
                          b.integrity_result,
                          (SELECT r.id FROM restore_drills r WHERE r.backup_id=b.id
                           ORDER BY r.started_at DESC, r.id DESC LIMIT 1)
                   FROM backup_runs b
                   ORDER BY b.started_at DESC, b.id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            total = int(conn.execute("SELECT COUNT(*) FROM backup_runs").fetchone()[0])
        finally:
            conn.close()
        return [self._map_backup(row) for row in rows], total

    def list_restore_drills(self, limit: int) -> tuple[list[dict[str, Any]], int]:
        conn = self._db.connect()
        try:
            rows = conn.execute(
                """SELECT id, backup_id, started_at, ended_at, status, error_message
                   FROM restore_drills
                   ORDER BY started_at DESC, id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            total = int(conn.execute("SELECT COUNT(*) FROM restore_drills").fetchone()[0])
        finally:
            conn.close()
        items = [
            {
                "id": row[0],
                "backupId": row[1],
                "startedAt": row[2],
                "endedAt": row[3],
                "status": row[4],
                # Historical raw errors may contain local paths or secrets. Never
                # expose them through this operational endpoint.
                "errorMessage": "Backup verification failed" if row[5] else None,
            }
            for row in rows
        ]
        return items, total

    @staticmethod
    def insert_verified_backup(
        conn: sqlite3.Connection,
        *,
        backup_id: str,
        drill_id: str,
        started_at: str,
        ended_at: str,
        object_key: str,
        sha256: str,
        database_size: int,
        migration_version: str | None,
        verification_json: str,
    ) -> None:
        conn.execute(
            """INSERT INTO backup_runs (
                   id, started_at, ended_at, status, object_key, checksum,
                   database_size, migration_version, integrity_result
               ) VALUES (?, ?, ?, 'succeeded', ?, ?, ?, ?, ?)""",
            (
                backup_id,
                started_at,
                ended_at,
                object_key,
                sha256,
                database_size,
                migration_version,
                verification_json,
            ),
        )
        conn.execute(
            """INSERT INTO restore_drills (
                   id, backup_id, started_at, ended_at, status, error_message
               ) VALUES (?, ?, ?, ?, 'succeeded', NULL)""",
            (drill_id, backup_id, started_at, ended_at),
        )
