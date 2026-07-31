"""Real, fail-closed SQLite online backups for the Admin V2 operations API."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

from database import Database, db

from .backups_repository import BackupRepository
from .errors import AdminError
from .repository import AdminMutationRepository, StoredResponse
from .service import AdminMutationService, AuthenticatedSession


class BackupService:
    """Create verified artifacts and transactionally record their safe metadata."""

    def __init__(
        self,
        *,
        repository: BackupRepository | None = None,
        mutations: AdminMutationService | None = None,
        database: Database = db,
        backup_root: str | Path | None = None,
    ) -> None:
        self.repository = repository or BackupRepository(database)
        self.mutations = mutations or AdminMutationService()
        self.database = database
        configured = backup_root if backup_root is not None else os.environ.get(
            "PRACTENTURE_BACKUP_ROOT"
        )
        self._backup_root = Path(configured).expanduser() if configured else None

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def list_backups(self, limit: int, cursor: str | None) -> dict[str, Any]:
        items, total, next_cursor = self.repository.list_backups(limit, cursor)
        return {
            "items": items,
            "totalCount": total,
            "pageInfo": {
                "nextCursor": next_cursor,
                "hasNextPage": next_cursor is not None,
            },
        }

    def list_restore_drills(self, limit: int, cursor: str | None) -> dict[str, Any]:
        items, total, next_cursor = self.repository.list_restore_drills(limit, cursor)
        return {
            "items": items,
            "totalCount": total,
            "pageInfo": {
                "nextCursor": next_cursor,
                "hasNextPage": next_cursor is not None,
            },
        }

    def _configured_root(self) -> Path:
        if self._backup_root is None:
            raise AdminError(
                503,
                "ADMIN_BACKUP_NOT_CONFIGURED",
                "Backup storage is not configured",
            )
        try:
            self._backup_root.mkdir(mode=0o700, parents=True, exist_ok=True)
            root = self._backup_root.resolve(strict=True)
        except OSError as exc:
            raise AdminError(
                503,
                "ADMIN_BACKUP_NOT_CONFIGURED",
                "Backup storage is not available",
            ) from exc
        if not root.is_dir():
            raise AdminError(
                503,
                "ADMIN_BACKUP_NOT_CONFIGURED",
                "Backup storage is not available",
            )
        return root

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as artifact:
            for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _quote_identifier(identifier: str) -> str:
        return '"' + identifier.replace('"', '""') + '"'

    def _verify_backup(self, path: Path) -> dict[str, Any]:
        """Open the artifact independently and run all required SQLite checks."""
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            quick_rows = [str(row[0]) for row in connection.execute("PRAGMA quick_check")]
            integrity_rows = [
                str(row[0]) for row in connection.execute("PRAGMA integrity_check")
            ]
            foreign_key_rows = connection.execute("PRAGMA foreign_key_check").fetchall()
            if quick_rows != ["ok"] or integrity_rows != ["ok"] or foreign_key_rows:
                raise RuntimeError("SQLite verification rejected the backup artifact")

            table_names = [
                str(row[0])
                for row in connection.execute(
                    """SELECT name FROM sqlite_master
                       WHERE type='table' AND name NOT LIKE 'sqlite_%'
                       ORDER BY name"""
                ).fetchall()
            ]
            table_counts = {
                name: int(
                    connection.execute(
                        f"SELECT COUNT(*) FROM {self._quote_identifier(name)}"
                    ).fetchone()[0]
                )
                for name in table_names
            }
            return {
                "quickCheck": "ok",
                "integrityCheck": "ok",
                "foreignKeyViolations": 0,
                "tableCounts": table_counts,
            }
        finally:
            connection.close()

    @staticmethod
    def _reserve_artifact(path: Path) -> None:
        """Atomically reserve a regular owner-only file, never following a symlink."""
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags, 0o600)
        os.close(descriptor)

    def _write_online_backup(self, artifact: Path) -> str | None:
        """Use SQLite's online backup API, never byte-copying a live database."""
        source = self.database.connect()
        destination: sqlite3.Connection | None = None
        try:
            version_row = None
            table_exists = source.execute(
                """SELECT 1 FROM sqlite_master
                   WHERE type='table' AND name='alembic_version'"""
            ).fetchone()
            if table_exists:
                version_row = source.execute(
                    "SELECT version_num FROM alembic_version LIMIT 1"
                ).fetchone()
            migration_version = str(version_row[0]) if version_row else None

            destination = sqlite3.connect(str(artifact))
            source.backup(destination)
            destination.commit()
            return migration_version
        finally:
            if destination is not None:
                destination.close()
            source.close()

    def create_backup(
        self,
        *,
        session: AuthenticatedSession,
        label: str | None,
        idempotency_key: str | None,
        request_id: str,
    ):
        # Fail before any filesystem side effect while preserving the shared
        # idempotency mechanism's established public error contract.
        key = idempotency_key or ""
        if not key or len(key) > 255:
            raise AdminError(
                400,
                "ADMIN_IDEMPOTENCY_KEY_INVALID",
                "Idempotency-Key must be between 1 and 255 characters",
            )
        root = self._configured_root()
        backup_id = f"backup_{uuid4()}"
        drill_id = f"drill_{uuid4()}"
        object_key = f"{backup_id}.sqlite3"
        artifact = (root / object_key).resolve()
        try:
            artifact.relative_to(root)
        except ValueError as exc:
            raise AdminError(500, "ADMIN_BACKUP_FAILED", "Backup could not be created") from exc
        if artifact.exists():
            raise AdminError(409, "ADMIN_BACKUP_COLLISION", "Backup identifier collision")

        started_at = self._now_iso()
        created_artifact: Path | None = None

        def mutation(conn: sqlite3.Connection) -> StoredResponse:
            nonlocal created_artifact
            created_artifact = artifact
            self._reserve_artifact(artifact)
            migration_version = self._write_online_backup(artifact)
            artifact.chmod(0o600)
            database_size = artifact.stat().st_size
            if database_size <= 0:
                raise RuntimeError("SQLite backup artifact is empty")
            sha256 = self._sha256(artifact)
            verification = self._verify_backup(artifact)
            ended_at = self._now_iso()
            persisted_result = dict(verification)
            if label is not None:
                persisted_result["label"] = label
            verification_json = json.dumps(
                persisted_result, sort_keys=True, separators=(",", ":")
            )
            self.repository.insert_verified_backup(
                conn,
                backup_id=backup_id,
                drill_id=drill_id,
                started_at=started_at,
                ended_at=ended_at,
                object_key=object_key,
                sha256=sha256,
                database_size=database_size,
                migration_version=migration_version,
                verification_json=verification_json,
            )
            backup = {
                "id": backup_id,
                "status": "succeeded",
                "startedAt": started_at,
                "endedAt": ended_at,
                "objectKey": object_key,
                "sha256": sha256,
                "databaseSize": database_size,
                "migrationVersion": migration_version,
                "label": label,
                "verification": verification,
                "restoreDrillId": drill_id,
            }
            return StoredResponse(
                status_code=201,
                body={"backup": backup},
                headers={
                    "Location": f"/api/admin/v2/operations/backups/{backup_id}",
                    "Cache-Control": "no-store",
                },
            )

        try:
            return self.mutations.execute_high_risk(
                session=session,
                route="POST /api/admin/v2/operations/backups",
                idempotency_key=key,
                request_payload={"label": label},
                request_id=request_id,
                target={"type": "backup", "id": backup_id},
                action="backup.create",
                metadata={"backupId": backup_id, "verificationRequired": True},
                mutation=mutation,
            )
        except AdminError:
            if created_artifact is not None:
                created_artifact.unlink(missing_ok=True)
            raise
        except (OSError, sqlite3.Error, RuntimeError) as exc:
            if created_artifact is not None:
                try:
                    created_artifact.unlink(missing_ok=True)
                except OSError:
                    pass
            raise AdminError(
                500, "ADMIN_BACKUP_FAILED", "Backup could not be created"
            ) from exc


backup_service = BackupService()
