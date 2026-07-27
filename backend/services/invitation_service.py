"""Service for managing professor invitations."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from services.errors import (
    InvitationExpiredError,
    InvitationRevokedError,
    InvitationConsumedError,
)


class InvitationService:
    """Service for managing professor invitations."""
    
    def __init__(self, invitation_repository):
        self.repo = invitation_repository
    
    def create_invitation(
        self,
        organization_id: str,
        intended_email: str,
        expires_in_hours: int = 48,
        max_uses: int = 1,
        issued_by: str = "",
        notes: Optional[str] = None,
        change_ticket: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new professor invitation.
        
        Returns the full secret (returned only once to the caller).
        """
        return self.repo.create_invitation(
            organization_id=organization_id,
            intended_email=intended_email,
            expires_in_hours=expires_in_hours,
            max_uses=max_uses,
            issued_by=issued_by,
            notes=notes,
            change_ticket=change_ticket
        )
    
    def get_invitation(self, invitation_id: str) -> Optional[Dict[str, Any]]:
        """Get an invitation by ID."""
        return self.repo.get_invitation(invitation_id)
    
    def list_invitations(
        self,
        organization_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List invitations with optional filters."""
        return self.repo.list_invitations(
            organization_id=organization_id,
            status=status,
            limit=limit,
            offset=offset
        )
    
    def count_invitations(self, organization_id: Optional[str] = None) -> int:
        """Count invitations with optional filter."""
        return self.repo.count_invitations(organization_id)
    
    def redeem_invitation(
        self,
        invitation_id: str,
        redeemed_by: str
    ) -> Dict[str, Any]:
        """Redeem an invitation for a user.
        
        This is an atomic operation that:
        1. Validates the invitation exists and is active
        2. Checks expiration
        3. Checks usage limits
        4. Updates the invitation status
        5. Returns the redemption result
        
        Raises exceptions for invalid states.
        """
        return self.repo.redeem_invitation(invitation_id, redeemed_by)
    
    def revoke_invitation(self, invitation_id: str, revoked_by: str) -> bool:
        """Revoke an invitation."""
        return self.repo.revoke_invitation(invitation_id, revoked_by)
    
    def delete_invitation(self, invitation_id: str) -> bool:
        """Delete an invitation (for cleanup purposes)."""
        return self.repo.delete_invitation(invitation_id)
    
    def validate_invitation_for_redeem(
        self,
        invitation_id: str
    ) -> Dict[str, Any]:
        """Validate an invitation can be redeemed without modifying it.
        
        Returns the invitation details if valid.
        Raises exceptions for invalid states.
        """
        from services.errors import (
            InvitationExpiredError,
            InvitationRevokedError,
            InvitationConsumedError,
        )
        
        invitation = self.repo.get_invitation(invitation_id)
        
        if invitation is None:
            raise InvitationExpiredError("Invitation not found")
        
        # Check status
        if invitation["status"] == "revoked":
            raise InvitationRevokedError("Invitation has been revoked")
        
        if invitation["status"] == "redeemed":
            raise InvitationConsumedError("Invitation has already been used")
        
        if invitation["status"] == "expired":
            raise InvitationExpiredError("Invitation has expired")
        
        # Check expiration
        expires_at = invitation["expires_at"]
        if isinstance(expires_at, str):
            from datetime import datetime
            expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        
        if datetime.now(timezone.utc) > expires_at:
            raise InvitationExpiredError("Invitation has expired")
        
        # Check usage limits
        if invitation["use_count"] >= invitation["max_uses"]:
            raise InvitationConsumedError("Invitation has reached maximum uses")
        
        return invitation
