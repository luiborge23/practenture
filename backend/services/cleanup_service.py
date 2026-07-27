"""Service for scoped cleanup operations."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


class CleanupService:
    """Service for scoped cleanup operations."""
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    def _generate_plan_hash(self, selector: Dict[str, Any]) -> str:
        """Generate a hash of the cleanup plan selector."""
        selector_str = str(sorted(selector.items()))
        return hashlib.sha256(selector_str.encode()).hexdigest()[:16]
    
    def create_cleanup_plan(
        self,
        organization_id: Optional[str] = None,
        test_run_id: Optional[str] = None,
        owner_user_id: Optional[str] = None,
        is_test: bool = True
    ) -> Dict[str, Any]:
        """Create a cleanup plan with preview counts."""
        from database import db
        
        selector = {
            "organization_id": organization_id,
            "test_run_id": test_run_id,
            "owner_user_id": owner_user_id,
            "is_test": is_test
        }
        
        plan_hash = self._generate_plan_hash(selector)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        
        # Get preview counts
        table_counts = self._get_cleanup_preview(selector)
        total_rows = sum(table_counts.values())
        
        plan_id = f"cleanup_{secrets.token_hex(16)}"
        
        with db._get_conn() as conn:
            conn.execute(
                """
                    INSERT INTO cleanup_plans (
                        id, selector_json, plan_hash, preview_counts,
                        total_rows, status, created_by, expires_at
                    ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (
                    plan_id,
                    str(selector),
                    plan_hash,
                    str(table_counts),
                    total_rows,
                    owner_user_id or "system",
                    expires_at.isoformat()
                )
            )
            
            conn.commit()
        
        return {
            "plan_id": plan_id,
            "plan_hash": plan_hash,
            "preview": {
                "table_counts": table_counts,
                "total_rows": total_rows
            },
            "expires_at": expires_at
        }
    
    def _get_cleanup_preview(self, selector: Dict[str, Any]) -> Dict[str, int]:
        """Get preview counts for cleanup."""
        table_counts = {}
        
        with self.db._get_conn() as conn:
            # Count sessions
            query = "SELECT COUNT(*) FROM sessions WHERE 1=1"
            params = []
            
            if selector.get("organization_id"):
                query += " AND professor_user_id IN (SELECT user_id FROM memberships WHERE org_id = ?)"
                params.append(selector["organization_id"])
            
            result = conn.execute(query, params).fetchone()
            table_counts["sessions"] = result[0] if result else 0
            
            # Count decisions
            query = "SELECT COUNT(*) FROM decisions WHERE session_code IN (SELECT code FROM sessions WHERE 1=1)"
            params = []
            
            if selector.get("organization_id"):
                query += " AND professor_user_id IN (SELECT user_id FROM memberships WHERE org_id = ?)"
                params.append(selector["organization_id"])
            
            result = conn.execute(query, params).fetchone()
            table_counts["decisions"] = result[0] if result else 0
            
            # Count results
            query = "SELECT COUNT(*) FROM results WHERE session_code IN (SELECT code FROM sessions WHERE 1=1)"
            params = []
            
            if selector.get("organization_id"):
                query += " AND professor_user_id IN (SELECT user_id FROM memberships WHERE org_id = ?)"
                params.append(selector["organization_id"])
            
            result = conn.execute(query, params).fetchone()
            table_counts["results"] = result[0] if result else 0
            
            # Count team_states
            query = "SELECT COUNT(*) FROM team_states WHERE session_code IN (SELECT code FROM sessions WHERE 1=1)"
            params = []
            
            if selector.get("organization_id"):
                query += " AND professor_user_id IN (SELECT user_id FROM memberships WHERE org_id = ?)"
                params.append(selector["organization_id"])
            
            result = conn.execute(query, params).fetchone()
            table_counts["team_states"] = result[0] if result else 0
        
        return table_counts
    
    def get_cleanup_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Get a cleanup plan by ID."""
        with self.db._get_conn() as conn:
            row = conn.execute(
                """
                    SELECT id, selector_json, plan_hash, preview_counts,
                           total_rows, status, created_by, executed_by,
                           created_at, executed_at
                    FROM cleanup_plans WHERE id = ?
                """,
                (plan_id,)
            ).fetchone()
        
        if row is None:
            return None
        
        return dict(row)
    
    def execute_cleanup_plan(
        self,
        plan_id: str,
        executor_id: str,
        confirmation: str
    ) -> Dict[str, Any]:
        """Execute a cleanup plan."""
        from services.errors import (
            BackupRequiredError,
            CleanupPlanChangedError,
        )
        
        plan = self.get_cleanup_plan(plan_id)
        
        if plan is None:
            raise CleanupPlanChangedError("Cleanup plan not found")
        
        # Check if expired
        expires_at_str = plan["expires_at"]
        if isinstance(expires_at_str, str):
            from datetime import datetime
            expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
        else:
            expires_at = expires_at_str
        
        if datetime.now(timezone.utc) > expires_at:
            raise CleanupPlanChangedError("Cleanup plan has expired")
        
        # Check confirmation
        if confirmation != "DELETE TEST DATA":
            raise CleanupPlanChangedError("Confirmation phrase does not match")
        
        # Check for fresh backup
        backup_status = self._get_latest_backup_age()
        if backup_status["age_seconds"] > 3600:  # More than 1 hour
            raise BackupRequiredError("A recent verified backup is required")
        
        # Execute cleanup
        table_counts = eval(plan["preview_counts"])
        total_deleted = 0
        
        with self.db._get_conn() as conn:
            # Delete sessions and related data
            if plan["selector_json"].get("organization_id"):
                org_id = plan["selector_json"]["organization_id"]
                
                # Get session codes for this organization
                session_codes = [
                    row[0] for row in conn.execute(
                        """
                            SELECT s.code FROM sessions s
                            JOIN memberships m ON m.user_id = s.professor_user_id
                            WHERE m.org_id = ?
                        """,
                        (org_id,)
                    ).fetchall()
                ]
                
                # Delete related data
                for code in session_codes:
                    conn.execute("DELETE FROM decisions WHERE session_code = ?", (code,))
                    conn.execute("DELETE FROM results WHERE session_code = ?", (code,))
                    conn.execute("DELETE FROM team_states WHERE session_code = ?", (code,))
                
                # Delete sessions
                conn.execute("DELETE FROM sessions WHERE code IN ({})".format(
                    ",".join("?" * len(session_codes))
                ), session_codes)
                
                total_deleted = sum(table_counts.values())
            
            conn.commit()
        
        # Update plan status
        with self.db._get_conn() as conn:
            conn.execute(
                """
                    UPDATE cleanup_plans SET
                        status = 'completed',
                        executed_by = ?,
                        executed_at = ?
                    WHERE id = ?
                """,
                (executor_id, datetime.now(timezone.utc).isoformat(), plan_id)
            )
            
            conn.commit()
        
        return {
            "status": "completed",
            "plan_id": plan_id,
            "rows_deleted": total_deleted
        }
    
    def _get_latest_backup_age(self) -> Dict[str, Any]:
        """Get the age of the latest backup."""
        with self.db._get_conn() as conn:
            row = conn.execute(
                """
                    SELECT started_at FROM backup_runs
                    ORDER BY started_at DESC LIMIT 1
                """
            ).fetchone()
        
        if row is None:
            return {"age_seconds": 999999, "status": "no_backup"}
        
        started_at_str = row[0]
        if isinstance(started_at_str, str):
            from datetime import datetime
            started_at = datetime.fromisoformat(started_at_str.replace('Z', '+00:00'))
        else:
            started_at = started_at_str
        
        age_seconds = int((datetime.now(timezone.utc) - started_at).total_seconds())
        
        return {"age_seconds": age_seconds, "status": "ok"}
