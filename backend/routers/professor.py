"""Professor management endpoints — admin creates codes, users redeem them."""

import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user, verify_professor
from database import db
from models import (
    ProfessorCodeCreateRequest,
    ProfessorCodeResponse,
    ProfessorCodeListResponse,
    RedeemCodeRequest,
    RedeemCodeResponse,
    PreCreateProfessorRequest,
    PreCreateProfessorResponse,
    ChangePasswordRequest,
    ChangePasswordResponse,
)

router = APIRouter(prefix="/api/professor", tags=["professor"])


def _generate_prof_code() -> str:
    """Generate a professor access code: PROF-XXXX-XXXX."""
    chars = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    part1 = "".join(secrets.choice(chars) for _ in range(4))
    part2 = "".join(secrets.choice(chars) for _ in range(4))
    return f"PROF-{part1}-{part2}"


# ── Admin endpoints (owner only) ────────────────────────────────────────────

@router.post("/codes", response_model=ProfessorCodeResponse, status_code=201)
async def create_professor_code(req: ProfessorCodeCreateRequest, user=Depends(get_current_user)):
    """Admin/owner generates a one-time professor access code."""
    if user.get("role") != "owner":
        raise HTTPException(status_code=403, detail="Owner access required")

    code = _generate_prof_code()
    while not db.create_professor_code(code, req.university_name, req.notes):
        code = _generate_prof_code()

    return ProfessorCodeResponse(
        code=code,
        university_name=req.university_name,
        notes=req.notes,
        used=False,
        used_by=None,
    )


@router.get("/codes", response_model=ProfessorCodeListResponse)
async def list_professor_codes(user=Depends(get_current_user)):
    """Admin/owner lists all professor codes."""
    if user.get("role") != "owner":
        raise HTTPException(status_code=403, detail="Owner access required")

    codes = db.list_professor_codes()
    return ProfessorCodeListResponse(codes=[
        ProfessorCodeResponse(
            code=c["code"],
            university_name=c.get("university_name", ""),
            notes=c.get("notes", ""),
            used=bool(c.get("used", 0)),
            used_by=c.get("used_by"),
        ) for c in codes
    ])


@router.post("/pre-create", response_model=PreCreateProfessorResponse, status_code=201)
async def pre_create_professor(req: PreCreateProfessorRequest, user=Depends(get_current_user)):
    """Admin/owner pre-creates a professor account with a temporary password.

    The professor must change the password on first login.
    Also generates a professor code in case they want to link Google/Apple later.
    """
    from security import hash_password, validate_password_complexity
    from audit import log_event

    if user.get("role") != "owner":
        raise HTTPException(status_code=403, detail="Owner access required")

    # Validate password complexity
    is_valid, err_msg = validate_password_complexity(req.password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=err_msg)

    h = hash_password(req.password)

    # Create user with must_change_password=1
    existing = db.get_user(req.username)
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")

    # Insert directly via upsert with must_change_password
    db.upsert_user(
        username=req.username,
        password_hash=h,
        role="professor",
        name=req.name,
        email=req.email,
        provider="password",
        must_change_password=1,
    )

    # Also create a professor code so they can link Google/Apple later
    code = _generate_prof_code()
    while not db.create_professor_code(code, req.university_name, f"Pre-created for {req.username}"):
        code = _generate_prof_code()

    # Auto-create organization + membership for this professor
    org = db.get_or_create_organization(req.university_name, created_by=user["sub"])
    db.add_membership(req.username, org["id"], role="professor")

    log_event(actor=user["sub"], action="professor_pre_created", details={"new_professor": req.username, "university": req.university_name})

    return PreCreateProfessorResponse(
        username=req.username,
        professor_code=code,
        message="Professor account created. They must change their password on first login.",
    )


# ── Student/pending user redeems code to become professor ──────────────────

@router.post("/redeem", response_model=RedeemCodeResponse)
async def redeem_professor_code(req: RedeemCodeRequest, user=Depends(get_current_user)):
    """User redeems a professor access code to become a professor.

    Works for both password users and Google/Apple users.
    """
    from audit import log_event
    from auth import _create_token, ACCESS_TOKEN_EXPIRE_MINUTES
    from datetime import datetime, timedelta, timezone

    if user.get("role") == "professor":
        raise HTTPException(status_code=400, detail="You are already a professor")
    if user.get("role") == "owner":
        raise HTTPException(status_code=400, detail="Owner cannot redeem professor code")

    code_info = db.validate_professor_code(req.code)
    if not code_info:
        raise HTTPException(status_code=404, detail="Invalid, already used, or expired code")

    success = db.redeem_professor_code(req.code, user["sub"])
    if not success:
        raise HTTPException(status_code=500, detail="Failed to redeem code")

    # Create org + membership for the redeemed professor
    university_name = code_info.get("university_name", "")
    if university_name:
        org = db.get_or_create_organization(university_name, created_by=user["sub"])
        db.add_membership(user["sub"], org["id"], role="professor")

    # Return a NEW token with professor role + tenantId
    org = db.get_primary_org(user["sub"])
    tenant_id = org["id"] if org else ""

    token = _create_token({
        "sub": user["sub"],
        "role": "professor",
        "tenantId": tenant_id,
        "exp": (datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp(),
    })

    log_event(actor=user["sub"], action="code_redeemed", details={"code": req.code[:8] + "...", "university": university_name})

    return {"status": "promoted", "role": "professor", "accessToken": token, "tokenType": "bearer"}


# ── Password change ────────────────────────────────────────────────────────

@router.post("/change-password", response_model=ChangePasswordResponse)
async def change_password(req: ChangePasswordRequest, user=Depends(get_current_user)):
    """Change password for the current user (professor or student).

    Used for first-login password change when must_change_password=1.
    """
    from security import hash_password, validate_password_complexity
    from audit import log_event

    # Verify old password
    existing = db.verify_user(user["sub"], req.old_password)
    if not existing:
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    # Validate new password complexity
    is_valid, err_msg = validate_password_complexity(req.new_password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=err_msg)

    # Hash new password with bcrypt and update
    h = hash_password(req.new_password)
    db.update_user_password(user["sub"], h)

    # Clear must_change_password flag
    with db._get_conn() as conn:
        conn.execute(
            "UPDATE users SET must_change_password=0 WHERE username=?",
            (user["sub"],),
        )

    log_event(actor=user["sub"], action="password_changed")

    return ChangePasswordResponse(status="changed")


# ── Audit log endpoint (owner only) ──────────────────────────────────────────

@router.get("/audit")
async def get_audit_logs(
    limit: int = 50,
    offset: int = 0,
    actor: str = "",
    user=Depends(get_current_user),
):
    """Owner retrieves audit logs with optional actor filter and pagination."""
    from audit import get_audit_logs as fetch_logs

    if user.get("role") != "owner":
        raise HTTPException(status_code=403, detail="Owner access required")

    logs = fetch_logs(limit=limit, offset=offset, actor=actor)
    return {"logs": logs, "count": len(logs)}
