"""Service for managing owner account operations."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.errors import (
    UserNotFoundError,
    AccountSuspendedError,
)


class OwnerAccountService:
    """Service for managing owner account operations."""
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get a user by ID."""
        with self.db._get_conn() as conn:
            row = conn.execute(
                """
                    SELECT username as id, username, role, status, name, email,
                           last_login_at, created_by
                    FROM users WHERE username = ?
                """,
                (user_id,)
            ).fetchone()
        
        if row is None:
            return None
        
        return dict(row)
    
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get a user by username."""
        with self.db._get_conn() as conn:
            row = conn.execute(
                """
                    SELECT username as id, username, role, status, name, email,
                           last_login_at, created_by
                    FROM users WHERE username = ?
                """,
                (username,)
            ).fetchone()
        
        if row is None:
            return None
        
        return dict(row)
    
    def list_users(
        self,
        role: Optional[str] = None,
        status: Optional[str] = None,
        organization_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List users with optional filters."""
        query = """
            SELECT username as id, username, role, status, name, email,
                   last_login_at, created_by
            FROM users
        """
        
        conditions = []
        params = []
        
        if role:
            conditions.append("role = ?")
            params.append(role)
        
        if status:
            conditions.append("status = ?")
            params.append(status)
        
        # Note: organization filtering requires joining with memberships
        # This is a simplified version without org join
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        with self.db._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
        
        return [dict(row) for row in rows]
    
    def suspend_user(
        self,
        user_id: str,
        suspended_by: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Suspend a user account."""
        with self.db._get_conn() as conn:
            # Check if user exists
            row = conn.execute(
                "SELECT username as id, username, role, status FROM users WHERE username = ?",
                (user_id,)
            ).fetchone()
            
            if row is None:
                raise UserNotFoundError(f"User {user_id} not found")
            
            user = dict(row)
            
            # Check if already suspended
            if user["status"] == "suspended":
                return {
                    "user_id": user_id,
                    "username": user["username"],
                    "status": "already_suspended"
                }
            
            # Update the user status
            conn.execute(
                """
                    UPDATE users SET
                        status = 'suspended',
                        disabled_at = ?,
                        disabled_by = ?,
                        disable_reason = ?
                    WHERE username = ?
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    suspended_by,
                    reason,
                    user_id
                )
            )
            
            conn.commit()
        
        return {
            "user_id": user_id,
            "username": user["username"],
            "status": "suspended"
        }
    
    def reactivate_user(
        self,
        user_id: str,
        reactivated_by: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Reactivate a suspended user account."""
        with self.db._get_conn() as conn:
            # Check if user exists
            row = conn.execute(
                "SELECT username as id, username, role, status FROM users WHERE username = ?",
                (user_id,)
            ).fetchone()
            
            if row is None:
                raise UserNotFoundError(f"User {user_id} not found")
            
            user = dict(row)
            
            # Check if already active
            if user["status"] == "active":
                return {
                    "user_id": user_id,
                    "username": user["username"],
                    "status": "already_active"
                }
            
            # Update the user status
            conn.execute(
                """
                    UPDATE users SET
                        status = 'active',
                        disabled_at = NULL,
                        disabled_by = NULL,
                        disable_reason = NULL
                    WHERE username = ?
                """,
                (user_id,)
            )
            
            conn.commit()
        
        return {
            "user_id": user_id,
            "username": user["username"],
            "status": "active"
        }
    
    def force_password_reset(
        self,
        user_id: str,
        requested_by: str
    ) -> Dict[str, Any]:
        """Force a user to change their password on next login."""
        with self.db._get_conn() as conn:
            # Check if user exists
            row = conn.execute(
                "SELECT username as id, username, role FROM users WHERE username = ?",
                (user_id,)
            ).fetchone()
            
            if row is None:
                raise UserNotFoundError(f"User {user_id} not found")
            
            user = dict(row)
            
            # Update must_change_password flag
            conn.execute(
                "UPDATE users SET must_change_password = 1 WHERE username = ?",
                (user_id,)
            )
            
            conn.commit()
        
        return {
            "user_id": user_id,
            "username": user["username"],
            "status": "password_reset_required"
        }
    
    def update_last_login(self, user_id: str) -> bool:
        """Update the last login timestamp for a user."""
        with self.db._get_conn() as conn:
            result = conn.execute(
                """
                    UPDATE users SET
                        last_login_at = ?
                    WHERE username = ?
                """,
                (datetime.now(timezone.utc).isoformat(), user_id)
            )
            
            conn.commit()
            return result.rowcount > 0
