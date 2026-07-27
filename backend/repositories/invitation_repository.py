"""Repository for professor invitation operations."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import bcrypt


class InvitationRepository:
    """Repository for managing professor invitations."""
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    def _generate_secret(self) -> str:
        """Generate a secure random secret for invitation."""
        return secrets.token_urlsafe(32)
    
    def _hash_secret(self, secret: str) -> str:
        """Hash a secret using bcrypt."""
        return bcrypt.hashpw(secret.encode(), bcrypt.gensalt()).decode()
    
    def _mask_code(self, secret: str) -> str:
        """Create a masked version of the code for display."""
        # Show first 4 and last 4 characters
        if len(secret) >= 8:
            return f"{secret[:4]}...{secret[-4:]}"
        return secret
    
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
        from database import db
        
        secret = self._generate_secret()
        secret_hash = self._hash_secret(secret)
        masked_code = self._mask_code(secret)
        
        expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)
        invitation_id = f"inv_{secrets.token_hex(8)}"
        
        with db._get_conn() as conn:
            conn.execute(
                """
                    INSERT INTO professor_invitations (
                        id, secret_hash, masked_code, organization_id,
                        intended_email, status, expires_at, max_uses,
                        use_count, issued_by, notes, change_ticket
                    ) VALUES (
                        ?, ?, ?, ?,
                        ?, 'active', ?, ?,
                        0, ?, ?, ?
                    )
                """,
                (
                    invitation_id,
                    secret_hash,
                    masked_code,
                    organization_id,
                    intended_email.lower().strip(),
                    expires_at.isoformat(),
                    max_uses,
                    issued_by,
                    notes,
                    change_ticket
                )
            )
            conn.commit()
        
        return {
            "invitation_id": invitation_id,
            "secret": secret,
            "masked_code": masked_code,
            "expires_at": expires_at
        }
    
    def get_invitation(self, invitation_id: str) -> Optional[Dict[str, Any]]:
        """Get an invitation by ID."""
        with self.db._get_conn() as conn:
            row = conn.execute(
                """
                    SELECT id, secret_hash, masked_code, organization_id,
                           intended_email, status, expires_at, max_uses,
                           use_count, issued_by, revoked_by, revoked_at,
                           notes, change_ticket, created_at, last_used_at
                    FROM professor_invitations WHERE id = ?
                """,
                (invitation_id,)
            ).fetchone()
        
        if row is None:
            return None
        
        return dict(row)
    
    def get_invitation_by_secret_hash(self, secret_hash: str) -> Optional[Dict[str, Any]]:
        """Get an invitation by its secret hash."""
        with self.db._get_conn() as conn:
            row = conn.execute(
                """
                    SELECT id, secret_hash, masked_code, organization_id,
                           intended_email, status, expires_at, max_uses,
                           use_count, issued_by, revoked_by, revoked_at,
                           notes, change_ticket, created_at, last_used_at
                    FROM professor_invitations WHERE secret_hash = ?
                """,
                (secret_hash,)
            ).fetchone()
        
        if row is None:
            return None
        
        return dict(row)
    
    def list_invitations(
        self,
        organization_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List invitations with optional filters."""
        query = """
            SELECT id, masked_code, organization_id, intended_email,
                   status, expires_at, max_uses, use_count,
                   issued_by, created_at
            FROM professor_invitations
        """
        
        conditions = []
        params = []
        
        if organization_id:
            conditions.append("organization_id = ?")
            params.append(organization_id)
        
        if status:
            conditions.append("status = ?")
            params.append(status)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        with self.db._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
        
        return [dict(row) for row in rows]
    
    def count_invitations(self, organization_id: Optional[str] = None) -> int:
        """Count invitations with optional filter."""
        query = "SELECT COUNT(*) as count FROM professor_invitations"
        
        if organization_id:
            query += " WHERE organization_id = ?"
        
        with self.db._get_conn() as conn:
            row = conn.execute(
                query,
                (organization_id,) if organization_id else ()
            ).fetchone()
        
        return row["count"] if row else 0
    
    def redeem_invitation(
        self,
        invitation_id: str,
        redeemed_by: str
    ) -> Dict[str, Any]:
        """Atomically redeem an invitation.
        
        Returns the redemption result with status and updated counts.
        Raises exceptions for invalid states.
        """
        from services.errors import (
            InvitationExpiredError,
            InvitationRevokedError,
            InvitationConsumedError,
        )
        
        with self.db._get_conn() as conn:
            # Get the invitation
            row = conn.execute(
                """
                    SELECT id, secret_hash, status, expires_at, max_uses,
                           use_count, organization_id
                    FROM professor_invitations WHERE id = ?
                """,
                (invitation_id,)
            ).fetchone()
            
            if row is None:
                raise InvitationExpiredError("Invitation not found")
            
            invitation = dict(row)
            
            # Parse expires_at
            expires_at_str = invitation["expires_at"]
            if isinstance(expires_at_str, str):
                from datetime import datetime
                expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
            else:
                expires_at = expires_at_str
            
            # Check if expired
            now = datetime.now(timezone.utc)
            if now > expires_at:
                conn.execute(
                    "UPDATE professor_invitations SET status = 'expired' WHERE id = ?",
                    (invitation_id,)
                )
                conn.commit()
                raise InvitationExpiredError("Invitation has expired")
            
            # Check if revoked
            if invitation["status"] == "revoked":
                raise InvitationRevokedError("Invitation has been revoked")
            
            # Check if already redeemed
            if invitation["status"] == "redeemed":
                raise InvitationConsumedError("Invitation has already been used")
            
            # Check if max uses reached
            if invitation["use_count"] >= invitation["max_uses"]:
                conn.execute(
                    "UPDATE professor_invitations SET status = 'expired' WHERE id = ?",
                    (invitation_id,)
                )
                conn.commit()
                raise InvitationConsumedError("Invitation has reached maximum uses")
            
            # Update the invitation
            conn.execute(
                """
                    UPDATE professor_invitations SET
                        status = 'redeemed',
                        use_count = use_count + 1,
                        last_used_at = ?
                    WHERE id = ?
                """,
                (now.isoformat(), invitation_id)
            )
            
            # Get updated row
            updated = conn.execute(
                "SELECT * FROM professor_invitations WHERE id = ?",
                (invitation_id,)
            ).fetchone()
            
            conn.commit()
        
        return dict(updated)
    
    def revoke_invitation(self, invitation_id: str, revoked_by: str) -> bool:
        """Revoke an invitation."""
        with self.db._get_conn() as conn:
            result = conn.execute(
                """
                    UPDATE professor_invitations SET
                        status = 'revoked',
                        revoked_by = ?,
                        revoked_at = ?
                    WHERE id = ? AND status IN ('active', 'redeemed')
                """,
                (revoked_by, datetime.now(timezone.utc).isoformat(), invitation_id)
            )
            
            conn.commit()
            return result.rowcount > 0
    
    def delete_invitation(self, invitation_id: str) -> bool:
        """Delete an invitation (for cleanup purposes)."""
        with self.db._get_conn() as conn:
            result = conn.execute(
                "DELETE FROM professor_invitations WHERE id = ?",
                (invitation_id,)
            )
            
            conn.commit()
            return result.rowcount > 0
