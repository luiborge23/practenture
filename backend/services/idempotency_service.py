"""Service for managing idempotency keys."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional


class IdempotencyService:
    """Service for managing idempotency keys."""
    
    def __init__(self, db_connection):
        self.db = db_connection
        self.key_ttl_seconds = 3600  # 1 hour
    
    def generate_idempotency_key(self) -> str:
        """Generate a unique idempotency key."""
        return f"idem_{secrets.token_hex(16)}"
    
    def create_idempotency_record(
        self,
        idempotency_key: str,
        user_id: str,
        request_hash: str,
        request_data: Dict[str, Any],
        response_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create an idempotency record."""
        from database import db
        
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.key_ttl_seconds)
        
        with db._get_conn() as conn:
            conn.execute(
                """
                    INSERT INTO idempotency_keys (
                        key, user_id, request_hash, request_data,
                        response_data, expires_at, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    idempotency_key,
                    user_id,
                    request_hash,
                    str(request_data),
                    str(response_data) if response_data else None,
                    expires_at.isoformat(),
                    datetime.now(timezone.utc).isoformat()
                )
            )
            
            conn.commit()
        
        return {
            "key": idempotency_key,
            "expires_at": expires_at
        }
    
    def get_idempotency_record(
        self,
        idempotency_key: str
    ) -> Optional[Dict[str, Any]]:
        """Get an idempotency record by key."""
        with self.db._get_conn() as conn:
            row = conn.execute(
                """
                    SELECT key, user_id, request_hash, request_data,
                           response_data, expires_at, created_at
                    FROM idempotency_keys WHERE key = ?
                """,
                (idempotency_key,)
            ).fetchone()
        
        if row is None:
            return None
        
        return dict(row)
    
    def check_idempotency(
        self,
        idempotency_key: str,
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Check if a request with this idempotency key was already processed."""
        record = self.get_idempotency_record(idempotency_key)
        
        if record is None:
            return None
        
        # Check if expired
        expires_at_str = record["expires_at"]
        if isinstance(expires_at_str, str):
            from datetime import datetime
            expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
        else:
            expires_at = expires_at_str
        
        if datetime.now(timezone.utc) > expires_at:
            # Clean up expired record
            self.delete_idempotency_record(idempotency_key)
            return None
        
        # Check if it's for the same user
        if record["user_id"] != user_id:
            return None
        
        # Return the response data if available
        if record.get("response_data"):
            return {"response": eval(record["response_data"])}
        
        return None
    
    def delete_idempotency_record(self, idempotency_key: str) -> bool:
        """Delete an idempotency record."""
        with self.db._get_conn() as conn:
            result = conn.execute(
                "DELETE FROM idempotency_keys WHERE key = ?",
                (idempotency_key,)
            )
            
            conn.commit()
            return result.rowcount > 0
    
    def cleanup_expired_records(self) -> int:
        """Clean up expired idempotency records."""
        with self.db._get_conn() as conn:
            result = conn.execute(
                """
                    DELETE FROM idempotency_keys
                    WHERE expires_at < ?
                """,
                (datetime.now(timezone.utc).isoformat(),)
            )
            
            conn.commit()
            return result.rowcount
