"""Unit tests for InvitationService."""

import pytest
from datetime import datetime, timedelta, timezone

from services.invitation_service import InvitationService


class TestInvitationService:
    """Tests for the InvitationService."""
    
    @pytest.fixture
    def invitation_service(self):
        """Create an InvitationService with a test database."""
        from services.invitation_service import InvitationService
        from repositories.invitation_repository import InvitationRepository
        from database import db
        
        # Initialize the test database with required tables
        db._init_db()
        
        return InvitationService(InvitationRepository(db))
    
    def test_create_invitation(self, invitation_service):
        """Test creating a new invitation."""
        result = invitation_service.create_invitation(
            organization_id="org-123",
            intended_email="prof@example.edu"
        )
        
        assert "invitation_id" in result
        assert "secret" in result
        assert len(result["secret"]) >= 32
    
    def test_get_invitation(self, invitation_service):
        """Test getting an invitation by ID."""
        # Create an invitation
        create_result = invitation_service.create_invitation(
            organization_id="org-123",
            intended_email="prof@example.edu"
        )
        
        # Get the invitation
        result = invitation_service.get_invitation(create_result["invitation_id"])
        
        assert result is not None
        assert "masked_code" in result
        assert result["masked_code"] is not None
    
    def test_list_invitations(self, invitation_service):
        """Test listing invitations."""
        # Create multiple invitations
        for i in range(3):
            invitation_service.create_invitation(
                organization_id="org-123",
                intended_email=f"prof{i}@example.edu"
            )
        
        # List invitations
        result = invitation_service.list_invitations()
        
        assert len(result) == 3
    
    def test_redeem_invitation(self, invitation_service):
        """Test redeeming an invitation."""
        # Create an invitation
        create_result = invitation_service.create_invitation(
            organization_id="org-123",
            intended_email="prof@example.edu"
        )
        
        # Redeem the invitation
        result = invitation_service.redeem_invitation(
            invitation_id=create_result["invitation_id"],
            redeemed_by="new_prof"
        )
        
        assert result is not None
        assert "id" in result
    
    def test_redeem_expired_invitation(self, invitation_service):
        """Test redeeming an expired invitation."""
        # Create an invitation with very short expiry
        create_result = invitation_service.create_invitation(
            organization_id="org-123",
            intended_email="prof@example.edu",
            expires_in_hours=0  # Already expired
        )
        
        # Try to redeem - should fail
        with pytest.raises(Exception):
            invitation_service.redeem_invitation(
                invitation_id=create_result["invitation_id"],
                redeemed_by="new_prof"
            )
    
    def test_redeem_revoked_invitation(self, invitation_service):
        """Test redeeming a revoked invitation."""
        # Create an invitation
        create_result = invitation_service.create_invitation(
            organization_id="org-123",
            intended_email="prof@example.edu"
        )
        
        # Revoke the invitation
        invitation_service.revoke_invitation(create_result["invitation_id"], "owner-001")
        
        # Try to redeem - should fail
        with pytest.raises(Exception):
            invitation_service.redeem_invitation(
                invitation_id=create_result["invitation_id"],
                redeemed_by="new_prof"
            )
    
    def test_redeem_consumed_invitation(self, invitation_service):
        """Test redeeming an already consumed invitation."""
        # Create an invitation with max_uses=1
        create_result = invitation_service.create_invitation(
            organization_id="org-123",
            intended_email="prof@example.edu",
            max_uses=1
        )
        
        # Redeem the invitation first time
        invitation_service.redeem_invitation(
            invitation_id=create_result["invitation_id"],
            redeemed_by="new_prof1"
        )
        
        # Try to redeem again - should fail
        with pytest.raises(Exception):
            invitation_service.redeem_invitation(
                invitation_id=create_result["invitation_id"],
                redeemed_by="new_prof2"
            )
    
    def test_revoke_invitation(self, invitation_service):
        """Test revoking an invitation."""
        # Create an invitation
        create_result = invitation_service.create_invitation(
            organization_id="org-123",
            intended_email="prof@example.edu"
        )
        
        # Revoke the invitation
        result = invitation_service.revoke_invitation(create_result["invitation_id"], "owner-001")
        
        assert result is True
    
    def test_count_invitations(self, invitation_service):
        """Test counting invitations."""
        # Create multiple invitations
        for i in range(5):
            invitation_service.create_invitation(
                organization_id="org-123",
                intended_email=f"prof{i}@example.edu"
            )
        
        # Count invitations
        result = invitation_service.count_invitations()
        
        assert result == 5
