"""Unit tests for Owner administration schemas."""

import pytest
from datetime import datetime

from schemas.owner_admin import (
    ProfessorInvitationCreateRequest,
    ProfessorPreCreateRequest,
    CleanupPlanCreateRequest,
)


class TestProfessorInvitationCreateRequest:
    """Tests for ProfessorInvitationCreateRequest validation."""
    
    def test_valid_request_with_defaults(self):
        """Test valid request with default values."""
        req = ProfessorInvitationCreateRequest(
            organization_id="org-123",
            intended_email="prof@example.edu"
        )
        
        assert req.organization_id == "org-123"
        assert req.intended_email == "prof@example.edu"
        assert req.expires_in_hours == 48
        assert req.max_uses == 1
    
    def test_valid_request_with_custom_values(self):
        """Test valid request with custom values."""
        req = ProfessorInvitationCreateRequest(
            organization_id="org-123",
            intended_email="prof@example.edu",
            expires_in_hours=72,
            max_uses=5,
            notes="Test invitation",
            change_ticket="ONBOARD-001"
        )
        
        assert req.expires_in_hours == 72
        assert req.max_uses == 5
        assert req.notes == "Test invitation"
        assert req.change_ticket == "ONBOARD-001"
    
    def test_expires_in_hours_validation_min(self):
        """Test that expires_in_hours must be >= 1."""
        with pytest.raises(ValueError):
            ProfessorInvitationCreateRequest(
                organization_id="org-123",
                intended_email="prof@example.edu",
                expires_in_hours=0
            )
    
    def test_expires_in_hours_validation_max(self):
        """Test that expires_in_hours must be <= 168."""
        with pytest.raises(ValueError):
            ProfessorInvitationCreateRequest(
                organization_id="org-123",
                intended_email="prof@example.edu",
                expires_in_hours=169
            )
    
    def test_max_uses_validation(self):
        """Test that max_uses must be >= 1."""
        with pytest.raises(ValueError):
            ProfessorInvitationCreateRequest(
                organization_id="org-123",
                intended_email="prof@example.edu",
                max_uses=0
            )
    
    def test_invalid_email_format(self):
        """Test that invalid email format is rejected."""
        with pytest.raises(ValueError):
            ProfessorInvitationCreateRequest(
                organization_id="org-123",
                intended_email="not-an-email"
            )
    
    def test_valid_email_formats(self):
        """Test that various valid email formats are accepted."""
        valid_emails = [
            "prof@example.edu",
            "prof.name@university.edu",
            "prof123@test.org",
        ]
        
        for email in valid_emails:
            req = ProfessorInvitationCreateRequest(
                organization_id="org-123",
                intended_email=email
            )
            assert req.intended_email == email


class TestProfessorPreCreateRequest:
    """Tests for ProfessorPreCreateRequest validation."""
    
    def test_valid_request(self):
        """Test valid pre-create request."""
        req = ProfessorPreCreateRequest(
            username="new_prof",
            password="SecurePass123!",
            name="New Professor",
            email="new@example.edu",
            university_name="Test University"
        )
        
        assert req.username == "new_prof"
        assert req.password == "SecurePass123!"
        assert req.name == "New Professor"
        assert req.email == "new@example.edu"
        assert req.university_name == "Test University"
    
    def test_username_validation(self):
        """Test that username must match pattern."""
        with pytest.raises(ValueError):
            ProfessorPreCreateRequest(
                username="invalid_username!",
                password="SecurePass123!"
            )
    
    def test_optional_fields(self):
        """Test that optional fields can be omitted."""
        req = ProfessorPreCreateRequest(
            username="new_prof",
            password="SecurePass123!"
        )
        
        assert req.name is None
        assert req.email is None
        assert req.university_name == ""


class TestCleanupPlanCreateRequest:
    """Tests for CleanupPlanCreateRequest validation."""
    
    def test_valid_request_with_test_data(self):
        """Test valid request for test data cleanup."""
        req = CleanupPlanCreateRequest(
            organization_id="org-123",
            is_test=True
        )
        
        assert req.organization_id == "org-123"
        assert req.is_test is True
    
    def test_request_with_all_selectors(self):
        """Test request with all selector fields."""
        req = CleanupPlanCreateRequest(
            organization_id="org-123",
            test_run_id="run-456",
            owner_user_id="user-789",
            is_test=True
        )
        
        assert req.test_run_id == "run-456"
        assert req.owner_user_id == "user-789"
