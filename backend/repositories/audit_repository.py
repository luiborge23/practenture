"""Repository for audit event operations."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class AuditRepository:
    """Repository for managing audit events."""
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    def _generate_request_id(self) -> str:
        """Generate a unique request ID."""
        return f"req_{secrets.token_hex(16)}"
    
    def _redact_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively redact sensitive fields from data."""
        if not isinstance(data, dict):
            return data
        
        sensitive_keys = {
            "password", "token", "secret", "code", "mfa", "key", "credential",
            "api_key", "api_secret", "access_token", "refresh_token",
            "jwt", "session_id", "auth"
        }
        
        result = {}
        for key, value in data.items():
            key_lower = key.lower()
            
            is_sensitive = any(sensitive in key_lower for sensitive in sensitive_keys)
            
            if isinstance(value, dict):
                result[key] = self._redact_sensitive_data(value)
            elif isinstance(value, list):
                result[key] = [self._redact_sensitive_data(item) if isinstance(item, dict) else "[redacted]" if is_sensitive else item for item in value]
            elif is_sensitive:
                result[key] = "[redacted]"
            else:
                result[key] = value
        
        return result
    
    def create_audit_event(
        self,
        actor_user_id: str,
        actor_role: str,
        action: str,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        source_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        reason: Optional[str] = None,
        outcome: str = "success",
        before_data: Optional[Dict[str, Any]] = None,
        after_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new audit event."""
        from database import db
        
        request_id = request_id or self._generate_request_id()
        
        before_json = str(self._redact_sensitive_data(before_data or {}))
        after_json = str(self._redact_sensitive_data(after_data or {}))
        metadata_json = str(self._redact_sensitive_data(metadata or {}))
        
        event_id = f"evt_{secrets.token_hex(16)}"
        
        with db._get_conn() as conn:
            conn.execute(
                """
                    INSERT INTO audit_events (
                        id, occurred_at, actor_user_id, actor_role,
                        action, target_type, target_id, organization_id,
                        request_id, source_ip, user_agent, reason,
                        outcome, before_json, after_json, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    datetime.now(timezone.utc).isoformat(),
                    actor_user_id,
                    actor_role,
                    action,
                    target_type,
                    target_id,
                    organization_id,
                    request_id,
                    source_ip,
                    user_agent,
                    reason,
                    outcome,
                    before_json,
                    after_json,
                    metadata_json
                )
            )
            
            conn.commit()
        
        return {
            "id": event_id,
            "request_id": request_id,
            "occurred_at": datetime.now(timezone.utc)
        }
    
    def get_audit_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get an audit event by ID."""
        with self.db._get_conn() as conn:
            row = conn.execute(
                """
                    SELECT id, occurred_at, actor_user_id, actor_role,
                           action, target_type, target_id, organization_id,
                           request_id, source_ip, reason, outcome
                    FROM audit_events WHERE id = ?
                """,
                (event_id,)
            ).fetchone()
        
        if row is None:
            return None
        
        return dict(row)
    
    def list_audit_events(
        self,
        action: Optional[str] = None,
        actor_id: Optional[str] = None,
        target_id: Optional[str] = None,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List audit events with optional filters."""
        query = """
            SELECT id, occurred_at, actor_user_id, actor_role,
                   action, target_type, target_id, organization_id,
                   request_id, source_ip, reason, outcome
            FROM audit_events
        """
        
        conditions = []
        params = []
        
        if action:
            conditions.append("action = ?")
            params.append(action)
        
        if actor_id:
            conditions.append("actor_user_id = ?")
            params.append(actor_id)
        
        if target_id:
            conditions.append("target_id = ?")
            params.append(target_id)
        
        if from_time:
            conditions.append("occurred_at >= ?")
            params.append(from_time.isoformat())
        
        if to_time:
            conditions.append("occurred_at <= ?")
            params.append(to_time.isoformat())
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY occurred_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        with self.db._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
        
        return [dict(row) for row in rows]
    
    def count_audit_events(
        self,
        action: Optional[str] = None,
        actor_id: Optional[str] = None
    ) -> int:
        """Count audit events with optional filters."""
        query = "SELECT COUNT(*) as count FROM audit_events"
        
        conditions = []
        params = []
        
        if action:
            conditions.append("action = ?")
            params.append(action)
        
        if actor_id:
            conditions.append("actor_user_id = ?")
            params.append(actor_id)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        with self.db._get_conn() as conn:
            row = conn.execute(query, params).fetchone()
        
        return row["count"] if row else 0
