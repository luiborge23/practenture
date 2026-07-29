"""Domain orchestration for Admin V2 user administration."""
from __future__ import annotations

from datetime import datetime, timezone
import secrets

from security import hash_password
from .errors import AdminError
from .repository import AdminMutationRepository, MutationExecution, StoredResponse
from .service import AdminMutationService, AuthenticatedSession, mutation_service
from .users_repository import UserRecord, UserRepository
from .users_schemas import (
    PageInfo, User, UserActionRequest, UserActionResponse, UserListResponse,
    UserPrecreateRequest, UserPrecreateResponse, UserResponse,
)

_ACTION_ROUTES = {
    "suspend": "POST /api/admin/v2/users/{userId}/suspend",
    "reactivate": "POST /api/admin/v2/users/{userId}/reactivate",
    "require-password-reset": "POST /api/admin/v2/users/{userId}/require-password-reset",
    "revoke-sessions": "POST /api/admin/v2/users/{userId}/revoke-sessions",
}


def _user(record: UserRecord) -> User:
    return User(
        id=record.id, username=record.username, role=record.role, status=record.status,
        name=record.name, email=record.email, provider=record.provider,
        organizationIds=record.organization_ids,
        mustChangePassword=record.must_change_password, lastLoginAt=record.last_login_at,
        createdBy=record.created_by, createdAt=record.created_at,
        disabledAt=record.disabled_at, disabledBy=record.disabled_by,
        disableReason=record.disable_reason,
    )


def _body(model) -> dict:
    return model.model_dump(by_alias=True, mode="json")


def _temporary_password() -> str:
    # Includes each legacy policy class without retaining the plaintext anywhere.
    return "T9!" + secrets.token_urlsafe(15)


class UserService:
    def __init__(self, repository: UserRepository | None = None, mutations: AdminMutationService | None = None, audit_mutations: AdminMutationRepository | None = None) -> None:
        self.repository = repository or UserRepository()
        self.mutations = mutations or mutation_service
        self.audit_mutations = audit_mutations or AdminMutationRepository()

    def list_users(self, *, search: str | None, role: str | None, status: str | None, organization_id: str | None, sort: str, cursor: str | None, limit: int) -> UserListResponse:
        page = self.repository.list(search=search, role=role, status=status, organization_id=organization_id, sort=sort, cursor=cursor, limit=limit)
        return UserListResponse(users=[_user(item) for item in page.items], pageInfo=PageInfo(nextCursor=page.next_cursor, hasNextPage=page.next_cursor is not None), totalCount=page.total_count)

    def get_user(self, user_id: str) -> UserResponse:
        record = self.repository.get(user_id)
        if record is None:
            raise AdminError(404, "ADMIN_USER_NOT_FOUND", "User not found")
        return UserResponse(user=_user(record))

    def precreate(self, *, session: AuthenticatedSession, payload: UserPrecreateRequest, request_id: str) -> MutationExecution:
        username = payload.username.strip()
        name = payload.name.strip()
        email = str(payload.email).strip().casefold()
        temporary_password = _temporary_password()
        password_hash = hash_password(temporary_password)

        def create(conn) -> StoredResponse:
            record = self.repository.create(conn, username=username, password_hash=password_hash, role=payload.role, name=name, email=email, organization_id=payload.organization_id, created_by=session.record.owner_user_id)
            response = UserPrecreateResponse(user=_user(record), temporaryPassword=temporary_password)
            return StoredResponse(201, _body(response), {"Location": f"/api/admin/v2/users/{username}"})

        # Deliberately non-idempotent: persisting an idempotent response would persist
        # the one-time temporary password. Uniqueness makes retries fail closed.
        return self.audit_mutations.execute(
            request_id=request_id,
            actor={"id": session.record.owner_user_id, "role": session.record.role},
            target={"type": "user", "id": username}, action="user.precreate",
            outcome="succeeded", metadata={"role": payload.role, "organizationId": payload.organization_id},
            mutation=create,
        )

    def action(self, *, session: AuthenticatedSession, user_id: str, action: str, payload: UserActionRequest, idempotency_key: str | None, request_id: str) -> MutationExecution:
        if action not in _ACTION_ROUTES:
            raise ValueError("unsupported user action")
        if action == "suspend" and user_id == session.record.owner_user_id:
            raise AdminError(409, "ADMIN_USER_SELF_SUSPEND_FORBIDDEN", "The current owner cannot suspend their own account")
        now = datetime.now(timezone.utc).isoformat()
        sessions_revoked = action in {"suspend", "require-password-reset", "revoke-sessions"}

        def mutate(conn) -> StoredResponse:
            if action == "suspend":
                record = self.repository.set_status(conn, user_id=user_id, status="suspended", actor_id=session.record.owner_user_id, reason=payload.reason, now=now)
                self.repository.revoke_sessions(conn, user_id, now=now, reason="account_suspended")
            elif action == "reactivate":
                record = self.repository.set_status(conn, user_id=user_id, status="active", actor_id=session.record.owner_user_id, reason=payload.reason, now=now)
            elif action == "require-password-reset":
                record = self.repository.require_password_reset(conn, user_id)
                self.repository.revoke_sessions(conn, user_id, now=now, reason="password_reset_required")
                record = self.repository.get(user_id, conn=conn)
                assert record is not None
            else:
                self.repository.revoke_sessions(conn, user_id, now=now, reason="admin_revoked")
                record = self.repository.get(user_id, conn=conn)
                assert record is not None
            response = UserActionResponse(user=_user(record), sessionsRevoked=sessions_revoked)
            return StoredResponse(200, _body(response), {})

        return self.mutations.execute_high_risk(
            session=session, route=_ACTION_ROUTES[action], idempotency_key=idempotency_key or "",
            request_payload={"userId": user_id, "action": action, "reason": payload.reason},
            request_id=request_id, target={"type": "user", "id": user_id},
            action=f"user.{action.replace('-', '_')}",
            metadata={"reason": payload.reason, "sessionsRevoked": sessions_revoked}, mutation=mutate,
        )


user_service = UserService()
