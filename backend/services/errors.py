"""Stable error types for Owner administration API."""

from __future__ import annotations

from typing import Any, Dict, Optional


class OwnerError(Exception):
    """Base exception for Owner administration errors."""
    
    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code or "OWNER_ERROR"
        self.details = details or {}
        super().__init__(self.message)


class OwnerAuthorizationError(OwnerError):
    """Raised when authorization fails for an Owner operation."""
    
    def __init__(
        self,
        message: str = "Owner access required",
        code: Optional[str] = None
    ):
        super().__init__(message, code or "OWNER_AUTHORIZATION_ERROR")


class OwnerMfaRequiredError(OwnerError):
    """Raised when MFA is required but not provided."""
    
    def __init__(self, message: str = "MFA is required for this operation"):
        super().__init__(
            message,
            code="OWNER_MFA_REQUIRED"
        )


class RecentAuthRequiredError(OwnerError):
    """Raised when recent authentication is required."""
    
    def __init__(
        self,
        message: str = "Recent authentication is required for this operation"
    ):
        super().__init__(
            message,
            code="RECENT_AUTH_REQUIRED"
        )


class InvitationNotFoundError(OwnerError):
    """Raised when an invitation is not found."""
    
    def __init__(
        self,
        message: str = "Invitation not found",
        code: Optional[str] = None
    ):
        super().__init__(message, code or "INVITATION_NOT_FOUND")


class InvitationExpiredError(OwnerError):
    """Raised when an invitation has expired."""
    
    def __init__(
        self,
        message: str = "Invitation has expired"
    ):
        super().__init__(
            message,
            code="INVITATION_EXPIRED"
        )


class InvitationRevokedError(OwnerError):
    """Raised when an invitation has been revoked."""
    
    def __init__(
        self,
        message: str = "Invitation has been revoked"
    ):
        super().__init__(
            message,
            code="INVITATION_REVOKED"
        )


class InvitationConsumedError(OwnerError):
    """Raised when an invitation has been consumed."""
    
    def __init__(
        self,
        message: str = "Invitation has already been used"
    ):
        super().__init__(
            message,
            code="INVITATION_CONSUMED"
        )


class IdempotencyConflictError(OwnerError):
    """Raised when an idempotency key conflicts."""
    
    def __init__(
        self,
        message: str = "Request already processed with this idempotency key"
    ):
        super().__init__(
            message,
            code="IDEMPOTENCY_CONFLICT"
        )


class CleanupScopeInvalidError(OwnerError):
    """Raised when cleanup scope is invalid."""
    
    def __init__(
        self,
        message: str = "Cleanup scope is invalid"
    ):
        super().__init__(
            message,
            code="CLEANUP_SCOPE_INVALID"
        )


class BackupRequiredError(OwnerError):
    """Raised when a backup is required but not available."""
    
    def __init__(
        self,
        message: str = "A recent verified backup is required"
    ):
        super().__init__(
            message,
            code="BACKUP_REQUIRED"
        )


class CleanupPlanChangedError(OwnerError):
    """Raised when cleanup plan has changed since preview."""
    
    def __init__(
        self,
        message: str = "Cleanup plan has changed since preview"
    ):
        super().__init__(
            message,
            code="CLEANUP_PLAN_CHANGED"
        )


class DatabaseHealthFailedError(OwnerError):
    """Raised when database health check fails."""
    
    def __init__(
        self,
        message: str = "Database health check failed"
    ):
        super().__init__(
            message,
            code="DATABASE_HEALTH_FAILED"
        )


class AccountSuspendedError(OwnerError):
    """Raised when attempting to use a suspended account."""
    
    def __init__(
        self,
        message: str = "Account is suspended"
    ):
        super().__init__(
            message,
            code="ACCOUNT_SUSPENDED"
        )


class UserNotFoundError(OwnerError):
    """Raised when a user is not found."""
    
    def __init__(
        self,
        message: str = "User not found"
    ):
        super().__init__(
            message,
            code="USER_NOT_FOUND"
        )
