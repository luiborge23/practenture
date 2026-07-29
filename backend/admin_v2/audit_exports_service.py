"""Secure synchronous creation of bounded, redacted Admin V2 audit artifacts."""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

from admin_v2.errors import AdminError
from admin_v2.redaction import redact_secrets
from admin_v2.repository import MutationExecution, StoredResponse
from admin_v2.service import AuthenticatedSession, AdminMutationService, mutation_service

from .audit_exports_repository import AdminAuditExportRepository, AuditExportRecord
from .audit_exports_schemas import AuditExportRequest, AuditExportResponse


MAX_EXPORT_ROWS = 1_000
MAX_EXPORT_BYTES = 5 * 1024 * 1024
EXPORT_TTL = timedelta(minutes=15)
EXPORT_ROOT_ENV = "PRACTENTURE_ADMIN_AUDIT_EXPORT_ROOT"
EXPORT_ROUTE = "/audit-events/exports"
CSV_COLUMNS = (
    "eventId",
    "requestId",
    "actor",
    "target",
    "action",
    "outcome",
    "metadata",
    "occurredAt",
)


class AdminAuditExportService:
    def __init__(
        self,
        repository: AdminAuditExportRepository | None = None,
        mutations: AdminMutationService | None = None,
    ) -> None:
        self.repository = repository or AdminAuditExportRepository()
        self.mutations = mutations or mutation_service

    @staticmethod
    def _root() -> Path:
        configured = os.environ.get(EXPORT_ROOT_ENV, "").strip()
        if not configured:
            raise AdminError(
                503,
                "ADMIN_AUDIT_EXPORT_UNAVAILABLE",
                "Audit export storage is not configured",
            )
        candidate = Path(configured).expanduser()
        if not candidate.is_absolute():
            raise AdminError(
                503,
                "ADMIN_AUDIT_EXPORT_UNAVAILABLE",
                "Audit export storage is not configured",
            )
        try:
            candidate.mkdir(mode=0o700, parents=True, exist_ok=True)
            root = candidate.resolve(strict=True)
            os.chmod(root, 0o700)
        except OSError as exc:
            raise AdminError(
                503,
                "ADMIN_AUDIT_EXPORT_UNAVAILABLE",
                "Audit export storage is unavailable",
            ) from exc
        if not root.is_dir():
            raise AdminError(
                503,
                "ADMIN_AUDIT_EXPORT_UNAVAILABLE",
                "Audit export storage is unavailable",
            )
        return root

    @staticmethod
    def _parse_json(raw: str) -> Any:
        try:
            return redact_secrets(json.loads(raw))
        except (TypeError, json.JSONDecodeError) as exc:
            raise AdminError(
                500,
                "ADMIN_AUDIT_DATA_INVALID",
                "Stored audit event is invalid",
            ) from exc

    @classmethod
    def _event(cls, record: AuditExportRecord) -> dict[str, Any]:
        scalar_values = (
            record.event_id,
            record.request_id,
            record.action,
            record.outcome,
            record.occurred_at,
        )
        if any(not isinstance(value, str) or len(value) > 4_096 for value in scalar_values):
            raise AdminError(
                500,
                "ADMIN_AUDIT_DATA_INVALID",
                "Stored audit event is invalid",
            )
        try:
            occurred_at = datetime.fromisoformat(record.occurred_at)
        except ValueError as exc:
            raise AdminError(
                500,
                "ADMIN_AUDIT_DATA_INVALID",
                "Stored audit event is invalid",
            ) from exc
        if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
            raise AdminError(
                500,
                "ADMIN_AUDIT_DATA_INVALID",
                "Stored audit event is invalid",
            )
        return {
            "eventId": record.event_id,
            "requestId": record.request_id,
            "actor": cls._parse_json(record.actor_json),
            "target": cls._parse_json(record.target_json),
            "action": record.action,
            "outcome": record.outcome,
            "metadata": cls._parse_json(record.metadata_json),
            "occurredAt": occurred_at.astimezone(timezone.utc).isoformat(),
        }

    @staticmethod
    def _check_size(raw: bytes) -> bytes:
        if len(raw) > MAX_EXPORT_BYTES:
            raise AdminError(
                413,
                "ADMIN_AUDIT_EXPORT_SIZE_LIMIT",
                "Audit export exceeds the maximum artifact size",
            )
        return raw

    @classmethod
    def _json_bytes(cls, events: list[dict[str, Any]]) -> bytes:
        raw = json.dumps(
            {"auditEvents": events},
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return cls._check_size(raw)

    @staticmethod
    def _csv_safe(value: str) -> str:
        stripped = value.lstrip(" \t\r\n")
        if stripped.startswith(("=", "+", "-", "@")):
            return "'" + value
        return value

    @classmethod
    def _csv_bytes(cls, events: list[dict[str, Any]]) -> bytes:
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for event in events:
            row: dict[str, str] = {}
            for key in CSV_COLUMNS:
                value = event[key]
                if isinstance(value, (dict, list)):
                    text = json.dumps(
                        value,
                        ensure_ascii=False,
                        allow_nan=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                else:
                    text = str(value)
                row[key] = cls._csv_safe(text)
            writer.writerow(row)  # type: ignore[arg-type]
            if len(stream.getvalue().encode("utf-8")) > MAX_EXPORT_BYTES:
                raise AdminError(
                    413,
                    "ADMIN_AUDIT_EXPORT_SIZE_LIMIT",
                    "Audit export exceeds the maximum artifact size",
                )
        return cls._check_size(stream.getvalue().encode("utf-8"))

    @staticmethod
    def _write_atomic(root: Path, file_name: str, raw: bytes) -> Path:
        final_path = root / file_name
        temporary = root / f".{file_name}.{uuid4().hex}.tmp"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor: int | None = None
        try:
            descriptor = os.open(temporary, flags, 0o600)
            with os.fdopen(descriptor, "wb") as file_handle:
                descriptor = None
                file_handle.write(raw)
                file_handle.flush()
                os.fsync(file_handle.fileno())
            os.replace(temporary, final_path)
            os.chmod(final_path, 0o600)
            return final_path
        except OSError as exc:
            if descriptor is not None:
                os.close(descriptor)
            temporary.unlink(missing_ok=True)
            final_path.unlink(missing_ok=True)
            raise AdminError(
                500,
                "ADMIN_AUDIT_EXPORT_WRITE_FAILED",
                "Audit export artifact could not be created",
            ) from exc

    @staticmethod
    def _cleanup_expired(root: Path, cutoff: datetime) -> None:
        """Opportunistically remove a bounded number of expired export artifacts."""
        removed = 0
        try:
            entries = root.iterdir()
            for path in entries:
                if removed >= 25:
                    break
                try:
                    if (
                        path.is_file()
                        and not path.is_symlink()
                        and path.suffix in {".json", ".csv", ".tmp"}
                        and datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) <= cutoff
                    ):
                        path.unlink(missing_ok=True)
                        removed += 1
                except OSError:
                    continue
        except OSError:
            return

    def create(
        self,
        *,
        session: AuthenticatedSession,
        request: AuditExportRequest,
        idempotency_key: str,
        request_id: str,
    ) -> MutationExecution:
        now = datetime.now(timezone.utc)
        expires_at = now + EXPORT_TTL
        artifact_id = f"aexp_{uuid4().hex}"
        extension = request.format
        file_name = f"{artifact_id}.{extension}"
        created_path: Path | None = None
        audit_metadata: dict[str, Any] = {"format": request.format}

        def mutation(conn: sqlite3.Connection) -> StoredResponse:
            nonlocal created_path
            records = self.repository.list_for_export(
                conn,
                filters=request.filters,
                row_limit=MAX_EXPORT_ROWS,
            )
            if len(records) > MAX_EXPORT_ROWS:
                raise AdminError(
                    413,
                    "ADMIN_AUDIT_EXPORT_ROW_LIMIT",
                    "Audit export exceeds the maximum row count",
                )
            events = [self._event(record) for record in records]
            raw = self._json_bytes(events) if request.format == "json" else self._csv_bytes(events)
            root = self._root()
            self._cleanup_expired(root, now - EXPORT_TTL)
            created_path = self._write_atomic(root, file_name, raw)
            digest = hashlib.sha256(raw).hexdigest()
            response = AuditExportResponse(
                artifactId=artifact_id,
                format=request.format,
                fileName=file_name,
                rowCount=len(events),
                byteSize=len(raw),
                sha256=digest,
                createdAt=now,
                expiresAt=expires_at,
            )
            audit_metadata.update(
                {
                    "artifactId": artifact_id,
                    "rowCount": len(events),
                    "byteSize": len(raw),
                    "sha256": digest,
                    "expiresAt": expires_at.isoformat(),
                }
            )
            return StoredResponse(
                status_code=201,
                body=response.model_dump(mode="json", by_alias=True),
                headers={"Cache-Control": "no-store"},
            )

        try:
            return self.mutations.execute_high_risk(
                session=session,
                route=EXPORT_ROUTE,
                idempotency_key=idempotency_key,
                request_payload=request.model_dump(mode="json", by_alias=True),
                request_id=request_id,
                target={"type": "audit_export", "id": artifact_id},
                action="admin.audit_export.created",
                metadata=audit_metadata,
                mutation=mutation,
            )
        except BaseException:
            if created_path is not None:
                try:
                    created_path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise


audit_export_service = AdminAuditExportService()
