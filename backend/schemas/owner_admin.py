"""Pydantic models for Owner administration API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ── Invitation Schemas ───────────────────────────────────────────────────────

class ProfessorInvitationCreateRequest(BaseModel):
    """Request to create a new professor invitation."""
    model_config = {"populate_by_name": True}
    
    organization_id: str
    intended_email: str = Field(..., pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    expires_in_hours: int = Field(default=48, ge=1, le=168)
    max_uses: int = Field(default=1, ge=1)
    notes: Optional[str] = None
    change_ticket: Optional[str] = Field(default=None, alias="changeTicket")


class ProfessorInvitationCreateResponse(BaseModel):
    """Response with the full secret (returned only once)."""
    invitation_id: str = Field(alias="invitationId")
    secret: str
    masked_code: str = Field(alias="maskedCode")
    expires_at: datetime = Field(alias="expiresAt")


class ProfessorInvitationListResponse(BaseModel):
    """Response for listing invitations."""
    invitations: List[Dict[str, Any]]
    count: int


class ProfessorInvitationResponse(BaseModel):
    """Detailed invitation response."""
    id: str = Field(alias="id")
    masked_code: str = Field(alias="maskedCode")
    organization_id: str = Field(alias="organizationId")
    intended_email: str = Field(alias="intendedEmail")
    status: str
    expires_at: datetime = Field(alias="expiresAt")
    max_uses: int = Field(alias="maxUses")
    use_count: int = Field(alias="useCount")
    issued_by: str = Field(alias="issuedBy")
    created_at: datetime = Field(alias="createdAt")
    last_used_at: Optional[datetime] = Field(default=None, alias="lastUsedAt")


class ProfessorInvitationRevokeResponse(BaseModel):
    """Response for revoking an invitation."""
    status: str = "revoked"
    invitation_id: str = Field(alias="invitationId")


# ── Professor Pre-create Schemas ─────────────────────────────────────────────

class ProfessorPreCreateRequest(BaseModel):
    """Request to pre-create a professor account."""
    model_config = {"populate_by_name": True}
    
    username: str = Field(..., pattern=r"^[a-zA-Z0-9_-]+$")
    password: str
    name: Optional[str] = None
    email: Optional[str] = None
    university_name: str = Field(default="", alias="universityName")


class ProfessorPreCreateResponse(BaseModel):
    """Response for pre-creating a professor."""
    status: str = "created"
    username: str
    professor_code: str = Field(alias="professorCode")
    message: str


# ── Account Management Schemas ───────────────────────────────────────────────

class UserListResponse(BaseModel):
    """Response for listing users."""
    users: List[Dict[str, Any]]
    count: int
    next_cursor: Optional[str] = Field(default=None, alias="nextCursor")


class UserResponse(BaseModel):
    """Detailed user response."""
    id: str = Field(alias="id")
    username: str
    role: str
    status: str
    name: Optional[str] = None
    email: Optional[str] = None
    last_login_at: Optional[datetime] = Field(default=None, alias="lastLoginAt")
    created_by: Optional[str] = Field(default=None, alias="createdBy")


class AccountSuspendRequest(BaseModel):
    """Request to suspend an account."""
    reason: Optional[str] = None


class AccountSuspendResponse(BaseModel):
    """Response for suspending an account."""
    status: str = "suspended"
    user_id: str = Field(alias="userId")


class AccountReactivateRequest(BaseModel):
    """Request to reactivate an account."""
    reason: Optional[str] = None


class AccountReactivateResponse(BaseModel):
    """Response for reactivating an account."""
    status: str = "reactivated"
    user_id: str = Field(alias="userId")


class ForcePasswordResetResponse(BaseModel):
    """Response for forcing password reset."""
    status: str = "password_reset_required"
    user_id: str = Field(alias="userId")


# ── System Health Schemas ────────────────────────────────────────────────────

class IntegrityCheck(BaseModel):
    """Database integrity check result."""
    status: str
    error_count: int = Field(default=0, alias="errorCount")


class RelationsCheck(BaseModel):
    """Foreign key and orphan check result."""
    orphan_count: int = Field(default=0, alias="orphanCount")
    violations: List[Dict[str, Any]] = Field(default_factory=list)


class DomainCheck(BaseModel):
    """Domain invariant check result."""
    violation_count: int = Field(default=0, alias="violationCount")
    violations: List[Dict[str, Any]] = Field(default_factory=list)


class BackupStatus(BaseModel):
    """Backup status information."""
    age_seconds: int = Field(default=0, alias="ageSeconds")
    last_backup_at: Optional[datetime] = Field(default=None, alias="lastBackupAt")
    restore_test_status: str = Field(default="unknown", alias="restoreTestStatus")


class DatabaseHealthResponse(BaseModel):
    """Complete database health report."""
    status: str
    checked_at: datetime = Field(alias="checkedAt")
    engine: str
    migration_version: str = Field(alias="migrationVersion")
    integrity: IntegrityCheck
    relations: RelationsCheck
    domain: DomainCheck
    backup: BackupStatus
    request_id: str = Field(alias="requestId")


class BackupStatusResponse(BaseModel):
    """Backup status only response."""
    age_seconds: int = Field(default=0, alias="ageSeconds")
    last_backup_at: Optional[datetime] = Field(default=None, alias="lastBackupAt")
    restore_test_status: str = Field(default="unknown", alias="restoreTestStatus")


# ── Cleanup Schemas ──────────────────────────────────────────────────────────

class CleanupPlanCreateRequest(BaseModel):
    """Request to create a cleanup plan."""
    model_config = {"populate_by_name": True}
    
    organization_id: Optional[str] = Field(default=None, alias="organizationId")
    test_run_id: Optional[str] = Field(default=None, alias="testRunId")
    owner_user_id: Optional[str] = Field(default=None, alias="ownerUserId")
    is_test: bool = Field(default=True, alias="isTest")


class CleanupPlanPreview(BaseModel):
    """Preview of what will be deleted."""
    table_counts: Dict[str, int] = Field(default_factory=dict, alias="tableCounts")
    total_rows: int = Field(default=0, alias="totalRows")


class CleanupPlanCreateResponse(BaseModel):
    """Response for creating a cleanup plan."""
    plan_id: str = Field(alias="planId")
    plan_hash: str = Field(alias="planHash")
    preview: CleanupPlanPreview
    expires_at: datetime = Field(alias="expiresAt")


class CleanupPlanExecuteRequest(BaseModel):
    """Request to execute a cleanup plan."""
    confirmation: str = Field(..., description="Typed confirmation phrase")
    idempotency_key: str = Field(alias="idempotencyKey")


class CleanupPlanExecuteResponse(BaseModel):
    """Response for executing a cleanup plan."""
    status: str = "completed"
    plan_id: str = Field(alias="planId")
    rows_deleted: int = Field(alias="rowsDeleted")


class CleanupPlanResponse(BaseModel):
    """Detailed cleanup plan response."""
    id: str = Field(alias="id")
    selector_json: Dict[str, Any] = Field(alias="selectorJson")
    plan_hash: str = Field(alias="planHash")
    preview: CleanupPlanPreview
    status: str
    created_by: str = Field(alias="createdBy")
    executed_by: Optional[str] = Field(default=None, alias="executedBy")
    created_at: datetime = Field(alias="createdAt")
    executed_at: Optional[datetime] = Field(default=None, alias="executedAt")


# ── Audit Schemas ────────────────────────────────────────────────────────────

class AuditEventResponse(BaseModel):
    """Single audit event response."""
    id: str = Field(alias="id")
    occurred_at: datetime = Field(alias="occurredAt")
    actor_user_id: str = Field(alias="actorUserId")
    actor_role: str = Field(alias="actorRole")
    action: str
    target_type: Optional[str] = Field(default=None, alias="targetType")
    target_id: Optional[str] = Field(default=None, alias="targetId")
    organization_id: Optional[str] = Field(default=None, alias="organizationId")
    request_id: str = Field(alias="requestId")
    source_ip: Optional[str] = Field(default=None, alias="sourceIp")
    reason: Optional[str] = None
    outcome: str


class AuditListResponse(BaseModel):
    """Response for listing audit events."""
    events: List[AuditEventResponse]
    count: int
    next_cursor: Optional[str] = Field(default=None, alias="nextCursor")


# ── Error Codes ──────────────────────────────────────────────────────────────

class OwnerErrorCodes:
    """Stable error codes for Owner API."""
    
    # Authentication and Authorization
    OWNER_MFA_REQUIRED = "OWNER_MFA_REQUIRED"
    RECENT_AUTH_REQUIRED = "RECENT_AUTH_REQUIRED"
    
    # Invitation Errors
    INVITATION_EXPIRED = "INVITATION_EXPIRED"
    INVITATION_REVOKED = "INVITATION_REVOKED"
    INVITATION_CONSUMED = "INVITATION_CONSUMED"
    INVITATION_NOT_FOUND = "INVITATION_NOT_FOUND"
    
    # Idempotency
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    
    # Cleanup Errors
    CLEANUP_SCOPE_INVALID = "CLEANUP_SCOPE_INVALID"
    BACKUP_REQUIRED = "BACKUP_REQUIRED"
    CLEANUP_PLAN_CHANGED = "CLEANUP_PLAN_CHANGED"
    
    # Database Health
    DATABASE_HEALTH_FAILED = "DATABASE_HEALTH_FAILED"
    
    # Account Errors
    ACCOUNT_SUSPENDED = "ACCOUNT_SUSPENDED"
    USER_NOT_FOUND = "USER_NOT_FOUND"
