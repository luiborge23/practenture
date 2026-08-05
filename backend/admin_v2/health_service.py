"""Aggregation and stable status policy for Admin V2 operational health."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from typing import Any, Literal

from .health_repository import EXPECTED_MIGRATION_VERSION, HealthEvidence, OperationsHealthRepository
from .health_schemas import (
    HealthCheckResponse,
    HealthEngineResponse,
    HealthSummaryResponse,
    OperationsHealthResponse,
)


class OperationsHealthService:
    def __init__(self, repository: OperationsHealthRepository | None = None) -> None:
        self.repository = repository or OperationsHealthRepository()

    def get_health(
        self,
        *,
        request_id: str,
        now: datetime | None = None,
    ) -> OperationsHealthResponse:
        checked_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        try:
            evidence = self.repository.collect()
        except Exception:
            check = self._check(
                "DATABASE_CONNECTIVITY",
                "fail",
                "critical",
                affected_count=1,
                details={"transactionProbe": "failed"},
            )
            return OperationsHealthResponse(
                status="unhealthy",
                checkedAt=checked_at,
                requestId=request_id,
                engine=HealthEngineResponse(
                    version=None,
                    migrationVersion=None,
                    expectedMigrationVersion=EXPECTED_MIGRATION_VERSION,
                ),
                summary=HealthSummaryResponse(passed=0, warnings=0, failed=1),
                checks=[check],
            )

        checks = [
            self._check(
                "DATABASE_CONNECTIVITY",
                "pass",
                "info",
                details={"transactionProbe": "passed"},
            ),
            self._migration_check(evidence),
            self._count_check(
                "SQLITE_QUICK_CHECK",
                len(evidence.quick_check_errors),
                evidence.quick_check_errors,
                critical=True,
            ),
            self._count_check(
                "SQLITE_FOREIGN_KEY_CHECK",
                evidence.foreign_keys.count,
                evidence.foreign_keys.sample_ids,
                critical=True,
            ),
            self._count_check(
                "LOGICAL_ORPHAN_CHECK",
                evidence.logical_orphans.count,
                evidence.logical_orphans.sample_ids,
                critical=True,
            ),
            self._count_check(
                "DOMAIN_INVARIANT_CHECK",
                evidence.domain_violations.count,
                evidence.domain_violations.sample_ids,
                critical=True,
            ),
            self._backup_check(evidence.last_backup, checked_at),
            self._restore_check(evidence.last_restore_drill, checked_at),
            self._storage_check(evidence),
        ]
        failed = sum(check.status == "fail" for check in checks)
        warnings = sum(check.status == "warn" for check in checks)
        passed = len(checks) - failed - warnings
        status = "unhealthy" if failed else "degraded" if warnings else "healthy"
        return OperationsHealthResponse(
            status=status,
            checkedAt=checked_at,
            requestId=request_id,
            engine=HealthEngineResponse(
                version=evidence.engine_version,
                migrationVersion=evidence.migration_version,
                expectedMigrationVersion=EXPECTED_MIGRATION_VERSION,
            ),
            summary=HealthSummaryResponse(
                passed=passed, warnings=warnings, failed=failed
            ),
            checks=checks,
        )

    def _migration_check(self, evidence: HealthEvidence) -> HealthCheckResponse:
        matches = evidence.migration_version == EXPECTED_MIGRATION_VERSION
        return self._check(
            "MIGRATION_VERSION",
            "pass" if matches else "fail",
            "info" if matches else "critical",
            affected_count=0 if matches else 1,
            details={
                "current": evidence.migration_version,
                "expected": EXPECTED_MIGRATION_VERSION,
            },
        )

    def _count_check(
        self,
        code: str,
        count: int,
        samples: tuple[str, ...],
        *,
        critical: bool,
    ) -> HealthCheckResponse:
        failed = count > 0
        return self._check(
            code,
            "fail" if failed and critical else "warn" if failed else "pass",
            "critical" if failed and critical else "warning" if failed else "info",
            affected_count=count,
            sample_ids=[self._redact_sample(value) for value in samples],
        )

    def _backup_check(
        self, row: dict[str, Any] | None, checked_at: datetime
    ) -> HealthCheckResponse:
        max_age = self._positive_int("ADMIN_HEALTH_MAX_BACKUP_AGE_SECONDS", 86_400)
        if row is None:
            return self._check(
                "BACKUP_FRESHNESS", "warn", "warning", affected_count=1,
                details={"state": "notRecorded", "maxAgeSeconds": max_age},
            )
        status = str(row.get("status") or "").casefold()
        integrity_verified = self._verified_backup_integrity(
            row.get("integrity_result")
        )
        timestamp = self._parse_timestamp(row.get("ended_at") or row.get("started_at"))
        age = self._age_seconds(timestamp, checked_at)
        verified = (
            status in {"completed", "success", "succeeded"}
            and integrity_verified
        )
        if not verified:
            return self._check(
                "BACKUP_FRESHNESS", "fail", "critical", affected_count=1,
                sample_ids=[self._redact_sample(str(row.get("id") or "unknown"))],
                details={"state": "unverified", "ageSeconds": age, "maxAgeSeconds": max_age},
            )
        fresh = age is not None and age <= max_age
        return self._check(
            "BACKUP_FRESHNESS", "pass" if fresh else "warn",
            "info" if fresh else "warning", affected_count=0 if fresh else 1,
            details={"state": "fresh" if fresh else "stale", "ageSeconds": age, "maxAgeSeconds": max_age},
        )

    @staticmethod
    def _verified_backup_integrity(value: Any) -> bool:
        """Accept legacy ``ok`` evidence and the current structured verifier result."""
        if not isinstance(value, str) or not value.strip():
            return False
        if value.strip().casefold() == "ok":
            return True
        try:
            evidence = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return False
        return (
            isinstance(evidence, dict)
            and evidence.get("quickCheck") == "ok"
            and evidence.get("integrityCheck") == "ok"
            and evidence.get("foreignKeyViolations") == 0
        )

    def _restore_check(
        self, row: dict[str, Any] | None, checked_at: datetime
    ) -> HealthCheckResponse:
        max_age = self._positive_int("ADMIN_HEALTH_MAX_RESTORE_AGE_SECONDS", 2_592_000)
        if row is None:
            return self._check(
                "RESTORE_DRILL_FRESHNESS", "warn", "warning", affected_count=1,
                details={"state": "notRecorded", "maxAgeSeconds": max_age},
            )
        status = str(row.get("status") or "").casefold()
        timestamp = self._parse_timestamp(row.get("ended_at") or row.get("started_at"))
        age = self._age_seconds(timestamp, checked_at)
        passed = status in {"passed", "completed", "success", "succeeded"}
        if not passed:
            return self._check(
                "RESTORE_DRILL_FRESHNESS", "fail", "critical", affected_count=1,
                sample_ids=[self._redact_sample(str(row.get("id") or "unknown"))],
                details={"state": "failed", "ageSeconds": age, "maxAgeSeconds": max_age},
            )
        fresh = age is not None and age <= max_age
        return self._check(
            "RESTORE_DRILL_FRESHNESS", "pass" if fresh else "warn",
            "info" if fresh else "warning", affected_count=0 if fresh else 1,
            details={"state": "fresh" if fresh else "stale", "ageSeconds": age, "maxAgeSeconds": max_age},
        )

    def _storage_check(self, evidence: HealthEvidence) -> HealthCheckResponse:
        storage = evidence.storage
        free_percent = (
            (storage.free_bytes / storage.total_bytes) * 100
            if storage.total_bytes > 0 else None
        )
        min_free = self._positive_int("ADMIN_HEALTH_MIN_FREE_BYTES", 268_435_456)
        max_wal = self._positive_int("ADMIN_HEALTH_MAX_WAL_BYTES", 268_435_456)
        critical = storage.total_bytes > 0 and (
            storage.free_bytes < min_free or (free_percent is not None and free_percent < 5)
        )
        warning = not critical and (
            storage.wal_bytes > max_wal
            or (free_percent is not None and free_percent < 10)
            or storage.total_bytes == 0
        )
        return self._check(
            "SQLITE_STORAGE",
            "fail" if critical else "warn" if warning else "pass",
            "critical" if critical else "warning" if warning else "info",
            affected_count=1 if critical or warning else 0,
            details={
                "databaseBytes": storage.database_bytes,
                "walBytes": storage.wal_bytes,
                "freeBytes": storage.free_bytes,
                "freePercent": round(free_percent, 2) if free_percent is not None else None,
                "minimumFreeBytes": min_free,
                "maximumWalBytes": max_wal,
            },
        )

    @staticmethod
    def _check(
        code: str,
        status: Literal["pass", "warn", "fail"],
        severity: Literal["info", "warning", "critical"],
        *,
        affected_count: int = 0,
        sample_ids: list[str] | None = None,
        details: dict[str, Any] | None = None,
    ) -> HealthCheckResponse:
        return HealthCheckResponse(
            code=code,
            status=status,
            severity=severity,
            affectedCount=affected_count,
            sampleIds=sample_ids or [],
            details=details or {},
        )

    @staticmethod
    def _redact_sample(value: str) -> str:
        return "id_" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime | None:
        if value is None:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _age_seconds(value: datetime | None, now: datetime) -> int | None:
        if value is None:
            return None
        return max(0, int((now - value).total_seconds()))

    @staticmethod
    def _positive_int(name: str, default: int) -> int:
        try:
            value = int(os.environ.get(name, str(default)))
            return value if value > 0 else default
        except ValueError:
            return default


operations_health_service = OperationsHealthService()
