"""Domain orchestration for Admin V2 overview and organizations."""

from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import uuid4

from .errors import AdminError
from .organizations_repository import (
    OrganizationRecord,
    OrganizationRepository,
    slugify,
)
from .organizations_schemas import (
    Organization,
    OrganizationCreateRequest,
    OrganizationListResponse,
    OrganizationPatchRequest,
    OrganizationResponse,
    OrganizationStatus,
    OverviewMetrics,
    OverviewResponse,
    PageInfo,
)
from .repository import MutationExecution, StoredResponse
from .service import AdminMutationService, AuthenticatedSession, mutation_service


_CREATE_ROUTE = "POST /api/admin/v2/organizations"
_UPDATE_ROUTE = "PATCH /api/admin/v2/organizations/{organizationId}"


def _organization(record: OrganizationRecord) -> Organization:
    return Organization(
        id=record.id,
        name=record.name,
        universityName=record.university_name,
        slug=record.slug,
        status=cast(OrganizationStatus, record.status),
        createdBy=record.created_by,
        createdAt=datetime.fromisoformat(record.created_at),
        version=record.version,
        professorCount=record.professor_count,
        studentCount=record.student_count,
        sessionCount=record.session_count,
        activeSessionCount=record.active_session_count,
    )


def _body(model) -> dict:
    return model.model_dump(by_alias=True, mode="json")


def _etag(version: str) -> str:
    return f'"{version}"'


def _expected_version(if_match: str | None) -> str:
    if not if_match:
        raise AdminError(
            428,
            "ADMIN_PRECONDITION_REQUIRED",
            "If-Match organization version is required",
        )
    value = if_match.strip()
    if value.startswith("W/"):
        raise AdminError(400, "ADMIN_VERSION_INVALID", "A strong If-Match value is required")
    if len(value) >= 2 and value[0] == value[-1] == '"':
        value = value[1:-1]
    if not value or value == "*" or "," in value:
        raise AdminError(400, "ADMIN_VERSION_INVALID", "If-Match value is invalid")
    return value


class OrganizationService:
    def __init__(
        self,
        repository: OrganizationRepository | None = None,
        mutations: AdminMutationService | None = None,
    ) -> None:
        self.repository = repository or OrganizationRepository()
        self.mutations = mutations or mutation_service

    def get_overview(self) -> OverviewResponse:
        record = self.repository.overview()
        return OverviewResponse(
            overview=OverviewMetrics(
                organizationCount=record.organization_count,
                activeOrganizationCount=record.active_organization_count,
                userCount=record.user_count,
                professorCount=record.professor_count,
                studentCount=record.student_count,
                sessionCount=record.session_count,
                activeSessionCount=record.active_session_count,
            )
        )

    def list_organizations(
        self,
        *,
        search: str | None,
        status: str | None,
        sort: str,
        cursor: str | None,
        limit: int,
    ) -> OrganizationListResponse:
        page = self.repository.list(
            search=search,
            status=status,
            sort=sort,
            cursor=cursor,
            limit=limit,
        )
        return OrganizationListResponse(
            organizations=[_organization(item) for item in page.items],
            pageInfo=PageInfo(
                nextCursor=page.next_cursor,
                hasNextPage=page.next_cursor is not None,
            ),
            totalCount=page.total_count,
        )

    def get_organization(self, organization_id: str) -> OrganizationResponse:
        record = self.repository.get(organization_id)
        if record is None:
            raise AdminError(404, "ADMIN_ORGANIZATION_NOT_FOUND", "Organization not found")
        return OrganizationResponse(organization=_organization(record))

    def create_organization(
        self,
        *,
        session: AuthenticatedSession,
        payload: OrganizationCreateRequest,
        idempotency_key: str | None,
        request_id: str,
    ) -> MutationExecution:
        name = payload.name.strip()
        if not name:
            raise AdminError(400, "ADMIN_VALIDATION_ERROR", "Organization name is required")
        university_name = (
            payload.university_name.strip() if payload.university_name else None
        )
        requested_slug = payload.slug or slugify(name)
        organization_id = f"org_{uuid4()}"
        request_payload = {
            "name": name,
            "universityName": university_name,
            "slug": requested_slug,
            "status": payload.status,
        }

        def create(conn) -> StoredResponse:
            created = self.repository.create(
                conn,
                organization_id=organization_id,
                name=name,
                university_name=university_name,
                slug=requested_slug,
                status=payload.status,
                created_by=session.record.owner_user_id,
            )
            response = OrganizationResponse(organization=_organization(created))
            return StoredResponse(
                status_code=201,
                body=_body(response),
                headers={
                    "Location": f"/api/admin/v2/organizations/{organization_id}",
                    "ETag": _etag(created.version),
                },
            )

        return self.mutations.execute_high_risk(
            session=session,
            route=_CREATE_ROUTE,
            idempotency_key=idempotency_key or "",
            request_payload=request_payload,
            request_id=request_id,
            target={"type": "organization", "id": organization_id},
            action="organization.create",
            metadata={"name": name, "slug": requested_slug, "status": payload.status},
            mutation=create,
        )

    def update_organization(
        self,
        *,
        session: AuthenticatedSession,
        organization_id: str,
        payload: OrganizationPatchRequest,
        if_match: str | None,
        idempotency_key: str | None,
        request_id: str,
    ) -> MutationExecution:
        expected_version = _expected_version(if_match)
        changes = payload.model_dump(exclude_unset=True, by_alias=False)
        if "name" in changes:
            changes["name"] = changes["name"].strip()
            if not changes["name"]:
                raise AdminError(400, "ADMIN_VALIDATION_ERROR", "Organization name is required")
        if changes.get("university_name") is not None:
            changes["university_name"] = changes["university_name"].strip() or None
        request_payload = {
            "organizationId": organization_id,
            "ifMatch": expected_version,
            "changes": changes,
        }

        def update(conn) -> StoredResponse:
            updated = self.repository.update(
                conn,
                organization_id=organization_id,
                expected_version=expected_version,
                changes=changes,
            )
            response = OrganizationResponse(organization=_organization(updated))
            return StoredResponse(
                status_code=200,
                body=_body(response),
                headers={"ETag": _etag(updated.version)},
            )

        return self.mutations.execute_high_risk(
            session=session,
            route=_UPDATE_ROUTE,
            idempotency_key=idempotency_key or "",
            request_payload=request_payload,
            request_id=request_id,
            target={"type": "organization", "id": organization_id},
            action="organization.update",
            metadata={"organizationId": organization_id, "changedFields": sorted(changes)},
            mutation=update,
        )


organization_service = OrganizationService()
