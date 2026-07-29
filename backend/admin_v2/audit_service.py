"""Owner-facing orchestration for immutable, redacted audit reads."""

from __future__ import annotations

from datetime import datetime, timezone
import json

from admin_v2.errors import AdminError
from admin_v2.redaction import redact_secrets

from .audit_repository import (
    AdminAuditRepository,
    AuditFilters,
    AuditRecord,
    InvalidAuditCursor,
)
from .audit_schemas import (
    AuditEvent,
    AuditEventDetailResponse,
    AuditEventListResponse,
    AuditPage,
)


class AdminAuditService:
    def __init__(self, repository: AdminAuditRepository | None = None) -> None:
        self.repository = repository or AdminAuditRepository()

    @staticmethod
    def _utc(value: datetime | None) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise AdminError(
                400,
                "ADMIN_AUDIT_TIME_RANGE_INVALID",
                "Audit time bounds must include a timezone",
            )
        return value.astimezone(timezone.utc).isoformat()

    @staticmethod
    def _json(value: str):
        try:
            parsed = json.loads(value)
        except (TypeError, json.JSONDecodeError) as exc:
            raise AdminError(
                500,
                "ADMIN_AUDIT_DATA_INVALID",
                "Stored audit event is invalid",
            ) from exc
        return redact_secrets(parsed)

    @classmethod
    def _event(cls, record: AuditRecord) -> AuditEvent:
        try:
            occurred_at = datetime.fromisoformat(record.occurred_at)
        except (TypeError, ValueError) as exc:
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
        return AuditEvent(
            eventId=record.event_id,
            requestId=record.request_id,
            actor=cls._json(record.actor_json),
            target=cls._json(record.target_json),
            action=record.action,
            outcome=record.outcome,
            metadata=cls._json(record.metadata_json),
            occurredAt=occurred_at,
        )

    def list_events(
        self,
        *,
        search: str | None,
        action: str | None,
        outcome: str | None,
        actor_id: str | None,
        target_type: str | None,
        target_id: str | None,
        occurred_from: datetime | None,
        occurred_to: datetime | None,
        sort: str,
        direction: str,
        limit: int,
        cursor: str | None,
    ) -> AuditEventListResponse:
        start = self._utc(occurred_from)
        end = self._utc(occurred_to)
        if start is not None and end is not None and start > end:
            raise AdminError(
                400,
                "ADMIN_AUDIT_TIME_RANGE_INVALID",
                "Audit start time must not be after end time",
            )
        filters = AuditFilters(
            search=search,
            action=action,
            outcome=outcome,
            actor_id=actor_id,
            target_type=target_type,
            target_id=target_id,
            occurred_from=start,
            occurred_to=end,
        )
        try:
            page = self.repository.list_events(
                filters=filters,
                sort=sort,
                direction=direction,
                limit=limit,
                cursor=cursor,
            )
        except InvalidAuditCursor as exc:
            raise AdminError(
                400,
                "ADMIN_AUDIT_CURSOR_INVALID",
                "Audit cursor is invalid or does not match the query",
            ) from exc
        return AuditEventListResponse(
            items=tuple(self._event(record) for record in page.records),
            page=AuditPage(
                limit=limit,
                hasMore=page.has_more,
                nextCursor=page.next_cursor,
            ),
        )

    def get_event(self, event_id: str) -> AuditEventDetailResponse:
        record = self.repository.get_event(event_id)
        if record is None:
            raise AdminError(404, "ADMIN_AUDIT_EVENT_NOT_FOUND", "Audit event not found")
        return AuditEventDetailResponse(auditEvent=self._event(record))


audit_service = AdminAuditService()
