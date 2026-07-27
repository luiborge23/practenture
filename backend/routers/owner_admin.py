"""Owner administration API router."""

from typing import Any, Dict, Optional
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth import _verify_token
import database as db_module
from datetime import datetime, timezone

router = APIRouter(tags=["owner"])


# ── Dependency: Require Owner role ───────────────────────────────────────────

_bearer_scheme = HTTPBearer(auto_error=False)


def require_owner(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> Dict[str, Any]:
    """Dependency to require Owner or Admin role for endpoints."""
    from fastapi import status

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    payload = _verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    role = payload.get("role")
    if role not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner or admin access required",
        )
    return payload


def _generate_id() -> str:
    """Generate a random ID."""
    return secrets.token_hex(8)


# ── Professor Invitation Endpoints ───────────────────────────────────────────

@router.post("/professor-invitations")
async def create_professor_invitation(
    request: Request,
    data: dict = None,
    owner=Depends(require_owner),
):
    """Create a new professor invitation."""
    if not data:
        raise HTTPException(status_code=400, detail="Request body required")
    
    org_id = data.get("organization_id") or data.get("organizationId")
    if not org_id:
        raise HTTPException(status_code=400, detail="organization_id required")
    
    intended_email = data.get("intended_email") or data.get("intendedEmail")
    if not intended_email:
        raise HTTPException(status_code=400, detail="intended_email required")
    
    notes = data.get("notes", "")
    max_uses = data.get("max_uses", 1)
    
    db = db_module.db
    invitation_id = _generate_id()
    secret = secrets.token_urlsafe(32)
    
    # Store in database
    db._get_conn().execute(
        """INSERT INTO professor_invitations 
           (id, secret_hash, masked_code, organization_id, intended_email, status, expires_at, max_uses, use_count, issued_by, notes)
           VALUES (?, ?, ?, ?, ?, 'active', datetime('now', '+7 days'), ?, 0, ?, ?)""",
        (invitation_id, secret, f"****{secret[-4:]}", org_id, intended_email, max_uses, owner.get("username"), notes),
    )
    db._get_conn().commit()
    
    return {
        "id": invitation_id,
        "code": secret,
        "maskedCode": f"****{secret[-4:]}",
        "organizationId": org_id,
        "intendedEmail": intended_email,
        "status": "active",
        "expiresAt": datetime.now(timezone.utc).isoformat(),
        "maxUses": max_uses,
    }


@router.get("/professor-invitations")
async def list_professor_invitations(
    request: Request,
    organization_id: str = None,
    status: str = None,
    owner=Depends(require_owner),
):
    """List professor invitations."""
    db = db_module.db
    conn = db._get_conn()
    
    query = "SELECT * FROM professor_invitations WHERE 1=1"
    params = []
    
    if organization_id:
        query += " AND organization_id = ?"
        params.append(organization_id)
    
    if status:
        query += " AND status = ?"
        params.append(status)
    
    query += " ORDER BY expires_at DESC LIMIT 100"
    
    rows = conn.execute(query, params).fetchall()
    
    return {
        "invitations": [
            {
                "id": row["id"],
                "maskedCode": row["masked_code"],
                "organizationId": row["organization_id"],
                "intendedEmail": row["intended_email"],
                "status": row["status"],
                "expiresAt": row["expires_at"],
                "maxUses": row["max_uses"],
                "useCount": row["use_count"],
                "issuedBy": row["issued_by"],
            }
            for row in rows
        ]
    }


@router.get("/professor-invitations/{invitation_id}")
async def get_professor_invitation(
    request: Request,
    invitation_id: str,
    owner=Depends(require_owner),
):
    """Get a professor invitation by ID."""
    db = db_module.db
    row = db._get_conn().execute(
        "SELECT * FROM professor_invitations WHERE id = ?", (invitation_id,)
    ).fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Invitation not found")
    
    return {
        "id": row["id"],
        "maskedCode": row["masked_code"],
        "organizationId": row["organization_id"],
        "intendedEmail": row["intended_email"],
        "status": row["status"],
        "expiresAt": row["expires_at"],
        "maxUses": row["max_uses"],
        "useCount": row["use_count"],
        "issuedBy": row["issued_by"],
        "notes": row["notes"],
    }


@router.post("/professor-invitations/{invitation_id}/revoke")
async def revoke_professor_invitation(
    request: Request,
    invitation_id: str,
    owner=Depends(require_owner),
):
    """Revoke a professor invitation."""
    db = db_module.db
    conn = db._get_conn()
    
    # Check if exists and not already revoked
    row = conn.execute(
        "SELECT * FROM professor_invitations WHERE id = ?", (invitation_id,)
    ).fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Invitation not found")
    
    if row["status"] == "revoked":
        raise HTTPException(status_code=400, detail="Invitation already revoked")
    
    conn.execute(
        """UPDATE professor_invitations 
           SET status = 'revoked', revoked_at = datetime('now'), revoked_by = ?
           WHERE id = ?""",
        (owner.get("username"), invitation_id),
    )
    conn.commit()
    
    return {"status": "revoked", "invitationId": invitation_id}


@router.post("/professors/pre-create")
async def pre_create_professor(
    request: Request,
    data: dict = None,
    owner=Depends(require_owner),
):
    """Pre-create a professor account."""
    if not data:
        raise HTTPException(status_code=400, detail="Request body required")
    
    username = data.get("username")
    if not username:
        raise HTTPException(status_code=400, detail="username required")
    
    email = data.get("email") or username
    name = data.get("name", username)
    university_name = data.get("universityName", "")
    
    db = db_module.db
    
    # Check if user already exists
    existing = db.get_user(username)
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")
    
    # Create user with temporary password (must change on first login)
    import security
    temp_password = secrets.token_urlsafe(16)
    password_hash = security.hash_password(temp_password)
    
    db.create_user(
        username=username,
        password_hash=password_hash,
        role="professor",
        name=name,
        email=email,
        department=university_name,
        must_change_password=True,
    )
    
    return {
        "status": "created",
        "username": username,
        "email": email,
        "name": name,
        "universityName": university_name,
        "mustChangePassword": True,
        "temporaryPassword": temp_password,
    }


# ── Account Management Endpoints ─────────────────────────────────────────────

@router.get("/users")
async def list_users(
    request: Request,
    role: str = None,
    status: str = None,
    organization_id: str = None,
    cursor: str = None,
    owner=Depends(require_owner),
):
    """List users with optional filters."""
    db = db_module.db
    conn = db._get_conn()
    
    query = "SELECT * FROM users WHERE 1=1"
    params = []
    
    if role:
        query += " AND role = ?"
        params.append(role)
    
    if status:
        query += " AND status = ?"
        params.append(status)
    
    # Filter by organization via memberships
    if organization_id:
        query += " AND username IN (SELECT user_id FROM memberships WHERE org_id = ?)"
        params.append(organization_id)
    
    query += " ORDER BY created_at DESC LIMIT 50"
    
    rows = conn.execute(query, params).fetchall()
    
    return {
        "users": [
            {
                "username": row["username"],
                "role": row["role"],
                "name": row["name"],
                "email": row["email"],
                "status": row["status"],
                "createdAt": row["created_at"],
            }
            for row in rows
        ]
    }


@router.get("/users/{user_id}")
async def get_user(
    request: Request,
    user_id: str,
    owner=Depends(require_owner),
):
    """Get a user by ID."""
    db = db_module.db
    row = db._get_conn().execute(
        "SELECT * FROM users WHERE username = ?", (user_id,)
    ).fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "username": row["username"],
        "role": row["role"],
        "name": row["name"],
        "email": row["email"],
        "department": row["department"],
        "status": row["status"],
        "createdAt": row["created_at"],
    }


@router.post("/users/{user_id}/suspend")
async def suspend_user(
    request: Request,
    user_id: str,
    data: dict = None,
    owner=Depends(require_owner),
):
    """Suspend a user account."""
    db = db_module.db
    conn = db._get_conn()
    
    # Check if user exists
    row = conn.execute(
        "SELECT * FROM users WHERE username = ?", (user_id,)
    ).fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    
    reason = data.get("reason", "") if data else ""
    
    conn.execute(
        """UPDATE users 
           SET status = 'suspended', disabled_at = datetime('now'), 
               disabled_by = ?, disable_reason = ?
           WHERE username = ?""",
        (owner.get("username"), reason, user_id),
    )
    conn.commit()
    
    return {"status": "suspended", "userId": user_id}


@router.post("/users/{user_id}/reactivate")
async def reactivate_user(
    request: Request,
    user_id: str,
    data: dict = None,
    owner=Depends(require_owner),
):
    """Reactivate a suspended user account."""
    db = db_module.db
    conn = db._get_conn()
    
    # Check if user exists and is suspended
    row = conn.execute(
        "SELECT * FROM users WHERE username = ?", (user_id,)
    ).fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    
    if row["status"] != "suspended":
        raise HTTPException(status_code=400, detail="User is not suspended")
    
    conn.execute(
        "UPDATE users SET status = 'active', disabled_at = NULL, disabled_by = NULL WHERE username = ?",
        (user_id,),
    )
    conn.commit()
    
    return {"status": "reactivated", "userId": user_id}


@router.post("/users/{user_id}/force-password-reset")
async def force_password_reset(
    request: Request,
    user_id: str,
    owner=Depends(require_owner),
):
    """Force a user to change their password."""
    db = db_module.db
    conn = db._get_conn()
    
    # Check if user exists
    row = conn.execute(
        "SELECT * FROM users WHERE username = ?", (user_id,)
    ).fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    
    conn.execute(
        "UPDATE users SET must_change_password = 1 WHERE username = ?",
        (user_id,),
    )
    conn.commit()
    
    return {"status": "password-reset-required", "userId": user_id}


# ── System Health Endpoints ──────────────────────────────────────────────────

@router.get("/system/database-health")
async def get_database_health(
    request: Request,
    owner=Depends(require_owner),
):
    """Get database health report."""
    db = db_module.db
    conn = db._get_conn()
    
    # Get table counts
    tables = ["users", "sessions", "decisions", "results", "announcements"]
    counts = {}
    
    for table in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        counts[table] = count
    
    # Get database size
    db_path = db_module.get_db_path()
    import os
    db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0
    
    return {
        "status": "healthy",
        "databasePath": db_path,
        "databaseSize": db_size,
        "tableCounts": counts,
    }


@router.get("/system/backup-status")
async def get_backup_status(
    request: Request,
    owner=Depends(require_owner),
):
    """Get backup status."""
    db = db_module.db
    conn = db._get_conn()
    
    # Get recent backup runs
    rows = conn.execute(
        "SELECT * FROM backup_runs ORDER BY started_at DESC LIMIT 10"
    ).fetchall()
    
    return {
        "backups": [
            {
                "id": row["id"],
                "startedAt": row["started_at"],
                "endedAt": row["ended_at"],
                "status": row["status"],
                "objectKey": row["object_key"],
                "checksum": row["checksum"],
                "databaseSize": row["database_size"],
            }
            for row in rows
        ]
    }


# ── Cleanup Endpoints ────────────────────────────────────────────────────────

@router.post("/cleanup-plans")
async def create_cleanup_plan(
    request: Request,
    data: dict = None,
    owner=Depends(require_owner),
):
    """Create a cleanup plan."""
    if not data:
        raise HTTPException(status_code=400, detail="Request body required")
    
    selector = data.get("selector", {})
    expires_at = data.get("expires_at") or datetime.now(timezone.utc).isoformat()
    
    db = db_module.db
    plan_id = _generate_id()
    
    # Calculate preview counts
    import json
    selector_json = json.dumps(selector)
    
    conn = db._get_conn()
    
    # Count rows that would be affected
    total_rows = 0
    if "sessions" in selector:
        total_rows += conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    
    plan_hash = secrets.token_hex(16)
    
    conn.execute(
        """INSERT INTO cleanup_plans 
           (id, selector_json, plan_hash, preview_counts, total_rows, status, created_by, expires_at)
           VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)""",
        (plan_id, selector_json, plan_hash, "{}", total_rows, owner.get("username"), expires_at),
    )
    conn.commit()
    
    return {
        "id": plan_id,
        "planHash": plan_hash,
        "totalRows": total_rows,
        "status": "pending",
    }


@router.get("/cleanup-plans/{plan_id}")
async def get_cleanup_plan(
    request: Request,
    plan_id: str,
    owner=Depends(require_owner),
):
    """Get a cleanup plan by ID."""
    db = db_module.db
    row = db._get_conn().execute(
        "SELECT * FROM cleanup_plans WHERE id = ?", (plan_id,)
    ).fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Cleanup plan not found")
    
    return {
        "id": row["id"],
        "planHash": row["plan_hash"],
        "totalRows": row["total_rows"],
        "status": row["status"],
        "createdAt": row["created_at"],
        "executedAt": row["executed_at"],
    }


@router.post("/cleanup-plans/{plan_id}/execute")
async def execute_cleanup_plan(
    request: Request,
    plan_id: str,
    data: dict = None,
    owner=Depends(require_owner),
):
    """Execute a cleanup plan."""
    db = db_module.db
    conn = db._get_conn()
    
    # Check if plan exists
    row = conn.execute(
        "SELECT * FROM cleanup_plans WHERE id = ?", (plan_id,)
    ).fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Cleanup plan not found")
    
    if row["status"] != "pending":
        raise HTTPException(status_code=400, detail="Plan already executed")
    
    # Execute cleanup
    import json
    selector = json.loads(row["selector_json"])
    
    deleted_count = 0
    
    if "sessions" in selector:
        # Delete sessions and related data
        conn.execute("DELETE FROM decisions WHERE session_code IN (SELECT code FROM sessions)")
        conn.execute("DELETE FROM results WHERE session_code IN (SELECT code FROM sessions)")
        conn.execute("DELETE FROM announcements WHERE session_id IN (SELECT session_id FROM sessions)")
        deleted_count += conn.execute("DELETE FROM sessions").fetchone()[0]
    
    # Update plan status
    conn.execute(
        """UPDATE cleanup_plans 
           SET status = 'completed', executed_at = datetime('now'), executed_by = ?
           WHERE id = ?""",
        (owner.get("username"), plan_id),
    )
    conn.commit()
    
    return {
        "status": "completed",
        "planId": plan_id,
        "deletedCount": deleted_count,
    }


# ── Audit Endpoints ──────────────────────────────────────────────────────────

@router.get("/audit-events")
async def list_audit_events(
    request: Request,
    action: str = None,
    actor_id: str = None,
    target_id: str = None,
    from_time: str = None,
    to_time: str = None,
    cursor: str = None,
    owner=Depends(require_owner),
):
    """List audit events with optional filters."""
    db = db_module.db
    conn = db._get_conn()
    
    query = "SELECT * FROM audit_events WHERE 1=1"
    params = []
    
    if action:
        query += " AND action = ?"
        params.append(action)
    
    if actor_id:
        query += " AND actor_user_id = ?"
        params.append(actor_id)
    
    if target_id:
        query += " AND target_id = ?"
        params.append(target_id)
    
    if from_time:
        query += " AND occurred_at >= ?"
        params.append(from_time)
    
    if to_time:
        query += " AND occurred_at <= ?"
        params.append(to_time)
    
    query += " ORDER BY occurred_at DESC LIMIT 100"
    
    rows = conn.execute(query, params).fetchall()
    
    return {
        "events": [
            {
                "id": row["id"],
                "occurredAt": row["occurred_at"],
                "actorUserId": row["actor_user_id"],
                "actorRole": row["actor_role"],
                "action": row["action"],
                "targetType": row["target_type"],
                "targetId": row["target_id"],
                "organizationId": row["organization_id"],
                "outcome": row["outcome"],
            }
            for row in rows
        ]
    }


@router.get("/audit-events/{event_id}")
async def get_audit_event(
    request: Request,
    event_id: str,
    owner=Depends(require_owner),
):
    """Get an audit event by ID."""
    db = db_module.db
    row = db._get_conn().execute(
        "SELECT * FROM audit_events WHERE id = ?", (event_id,)
    ).fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Audit event not found")
    
    return {
        "id": row["id"],
        "occurredAt": row["occurred_at"],
        "actorUserId": row["actor_user_id"],
        "actorRole": row["actor_role"],
        "action": row["action"],
        "targetType": row["target_type"],
        "targetId": row["target_id"],
        "organizationId": row["organization_id"],
        "outcome": row["outcome"],
        "beforeJson": row["before_json"],
        "afterJson": row["after_json"],
    }

# ── Owner Console Authentication ────────────────────────────────────────────

@router.post("/login")
async def owner_login(request: Request):
    """Authenticate an owner and set the secure admin-session cookie."""
    from fastapi.responses import JSONResponse
    from auth import LoginRequest as AuthLoginRequest
    from routers.auth import login_endpoint

    try:
        data = await request.json()
        auth_request = AuthLoginRequest(
            provider="password",
            username=data.get("username"),
            password=data.get("password"),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid login request") from exc

    result = await login_endpoint(auth_request)
    payload = result.model_dump(by_alias=True) if hasattr(result, "model_dump") else dict(result)
    if payload.get("role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner or admin access required")

    token = payload.get("accessToken") or payload.get("access_token")
    response = JSONResponse(payload)
    response.set_cookie(
        key="practenture_admin_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=24 * 60 * 60,
        path="/",
    )
    return response


@router.post("/logout")
async def owner_logout():
    from fastapi.responses import JSONResponse
    response = JSONResponse({"status": "logged_out"})
    response.delete_cookie("practenture_admin_token", path="/")
    return response
