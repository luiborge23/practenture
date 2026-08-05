"""Fail-closed cleanup planning and atomic execution orchestration."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
import sqlite3
from uuid import uuid4

from .cleanup_repository import CleanupRepository, canonical_json
from .errors import AdminError
from .repository import StoredResponse
from .service import AdminMutationService, AuthenticatedSession


class CleanupService:
    PLAN_TTL = timedelta(minutes=15)

    def __init__(self, *, repository: CleanupRepository | None = None, mutations: AdminMutationService | None = None) -> None:
        self.repository = repository or CleanupRepository()
        self.mutations = mutations or AdminMutationService()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _signing_secret() -> bytes:
        # The cleanup manifest never leaves process memory. Reuse the deployment
        # JWT secret rather than accepting a permissive cleanup-specific default.
        secret = os.environ.get("PRACTENTURE_JWT_SECRET", "")
        if not secret:
            raise AdminError(503, "ADMIN_CLEANUP_UNAVAILABLE", "Cleanup is not configured")
        return secret.encode()

    def _hash(self, selector: dict, counts: dict, manifest: dict) -> str:
        payload = canonical_json({"manifest": manifest, "previewCounts": counts, "selector": selector}).encode()
        return hmac.new(self._signing_secret(), payload, hashlib.sha256).hexdigest()

    @staticmethod
    def confirmation_text(plan_id: str, plan_hash: str) -> str:
        return f"DELETE CLEANUP PLAN {plan_id} {plan_hash}"

    @staticmethod
    def _selector_values(selector: dict) -> tuple[list[str], list[str]]:
        return list(selector.get("sessionCodes", [])), list(selector.get("invitationIds", []))

    def _blocker_counts(self, selector: dict, now: datetime, conn: sqlite3.Connection | None = None) -> dict[str, int]:
        _, invitation_ids = self._selector_values(selector)
        blockers = self.repository.invitation_blocker_count(invitation_ids, now, conn)
        return {"invitations": blockers} if blockers else {}

    def _public(self, plan: dict, *, now: datetime | None = None) -> dict:
        result = dict(plan)
        # The selector is retained only in the server-side cleanup plan for
        # execution and exact-set drift verification. Public plan responses
        # expose aggregate counts, never the selected session/invitation IDs.
        result.pop("selector", None)
        result["confirmationText"] = self.confirmation_text(plan["id"], plan["planHash"])
        blocker_counts = self._blocker_counts(plan["selector"], now or self._now())
        if blocker_counts:
            result["blockerCounts"] = blocker_counts
        return result

    def create_plan(self, *, session: AuthenticatedSession, session_codes: list[str], invitation_ids: list[str]) -> dict:
        selector = {}
        if session_codes:
            selector["sessionCodes"] = session_codes
        if invitation_ids:
            selector["invitationIds"] = invitation_ids
        now = self._now()
        counts = self.repository.preview_counts(session_codes, invitation_ids)
        manifest = self.repository.manifest(session_codes, invitation_ids)
        plan_hash = self._hash(selector, counts, manifest)
        plan_id = f"cleanup_{uuid4()}"
        self.repository.insert_plan(plan_id=plan_id, selector=selector, plan_hash=plan_hash, counts=counts, owner_id=session.record.owner_user_id, created_at=now.isoformat(), expires_at=(now + self.PLAN_TTL).isoformat())
        plan = self.repository.get_plan(plan_id)
        if plan is None:
            raise RuntimeError("cleanup plan persistence failed")
        return {"plan": self._public(plan, now=now)}

    def get_plan(self, plan_id: str) -> dict:
        plan = self.repository.get_plan(plan_id)
        if plan is None:
            raise AdminError(404, "ADMIN_CLEANUP_PLAN_NOT_FOUND", "Cleanup plan was not found")
        return {"plan": self._public(plan)}

    def execute(self, *, session: AuthenticatedSession, plan_id: str, plan_hash: str, confirmation: str, idempotency_key: str | None, request_id: str):
        key = idempotency_key or ""
        if not key or len(key) > 255:
            raise AdminError(400, "ADMIN_IDEMPOTENCY_KEY_INVALID", "Idempotency-Key must be between 1 and 255 characters")
        initial = self.repository.get_plan(plan_id)
        if initial is None:
            raise AdminError(404, "ADMIN_CLEANUP_PLAN_NOT_FOUND", "Cleanup plan was not found")
        payload = {"confirmation": confirmation, "planHash": plan_hash}
        route = f"/api/admin/v2/operations/cleanup-plans/{plan_id}/execute"

        def mutation(conn: sqlite3.Connection) -> StoredResponse:
            plan = self.repository.get_plan(plan_id, conn)
            if plan is None:
                raise AdminError(404, "ADMIN_CLEANUP_PLAN_NOT_FOUND", "Cleanup plan was not found")
            expected = self.confirmation_text(plan_id, plan["planHash"])
            if not hmac.compare_digest(plan_hash, plan["planHash"]) or not hmac.compare_digest(confirmation, expected):
                raise AdminError(409, "ADMIN_CLEANUP_CONFIRMATION_MISMATCH", "Cleanup confirmation does not match this plan")
            now = self._now()
            try:
                expires = datetime.fromisoformat(plan["expiresAt"].replace("Z", "+00:00")).astimezone(timezone.utc)
            except (ValueError, TypeError):
                expires = now - timedelta(seconds=1)
            if plan["status"] != "pending" or expires <= now:
                raise AdminError(409, "ADMIN_CLEANUP_PLAN_UNAVAILABLE", "Cleanup plan is not pending and unexpired")
            blockers = self._blocker_counts(plan["selector"], now, conn)
            if blockers:
                raise AdminError(409, "ADMIN_CLEANUP_BLOCKED", "Cleanup plan contains ineligible targets")
            if not self.repository.verified_recent_backup(conn, now):
                raise AdminError(409, "ADMIN_BACKUP_REQUIRED", "A recent verified backup and restore drill are required")
            session_codes, invitation_ids = self._selector_values(plan["selector"])
            current = self.repository.preview_counts(session_codes, invitation_ids, conn)
            manifest = self.repository.manifest(session_codes, invitation_ids, conn)
            if current != plan["previewCounts"] or not hmac.compare_digest(self._hash(plan["selector"], current, manifest), plan["planHash"]):
                raise AdminError(409, "ADMIN_CLEANUP_PLAN_CHANGED", "Cleanup plan no longer matches current data")
            deleted = self.repository.delete_selected(conn, session_codes, invitation_ids)
            if deleted != current:
                raise RuntimeError("cleanup deleted counts did not match preview")
            completed = now.isoformat()
            self.repository.complete_plan(conn, plan_id, session.record.owner_user_id, completed)
            return StoredResponse(200, {"planId": plan_id, "status": "completed", "deletedCounts": deleted, "completedAt": completed}, {})

        return self.mutations.execute_high_risk(session=session, route=route, idempotency_key=key, request_payload=payload, request_id=request_id, target={"type": "cleanup_plan", "id": plan_id}, action="cleanup.execute", metadata={"planId": plan_id, "planHash": initial["planHash"]}, mutation=mutation)
