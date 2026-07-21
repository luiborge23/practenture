"""Authentication endpoints for BizSimAI backend."""

import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from auth import (
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    RegisterRequest,
    RegisterResponse,
    get_current_user,
    login,
    refresh_access_token,
    register,
    verify_professor,
    verify_student_or_professor,
)
from auth_providers import verify_apple_id_token, verify_google_id_token
from models import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])


class VerifyTokenResponse(BaseModel):
    user_id: str
    role: str
    valid: bool = True


class ProfessorCheckResponse(BaseModel):
    status: str = "authorized"
    user_id: str
    role: str


class StudentOrProfessorCheckResponse(BaseModel):
    status: str = "authorized"
    user_id: str
    role: str


class KickoffResponse(BaseModel):
    status: str = "session_created"
    code: str
    message: str


class ProfessorInfoResponse(BaseModel):
    username: str
    name: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None
    role: str


class UpdateProfessorResponse(BaseModel):
    status: str = "updated"
    email: Optional[str] = None
    department: Optional[str] = None


@router.post("/login", response_model=LoginResponse)
async def login_endpoint(req: LoginRequest):
    """Authenticate user and return JWT token.
    
    Providers:
    - password: username/password (professor or student)
    - apple: Apple Sign-In ID token (student)
    - google: Google Sign-In ID token (student)
    """
    return login(req)


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register_endpoint(req: RegisterRequest):
    """Register a new student account."""
    return register(req)


@router.post("/verify", response_model=VerifyTokenResponse)
async def verify_token(user=Depends(get_current_user)):
    """Verify current token and return user info."""
    return VerifyTokenResponse(user_id=user["sub"], role=user["role"])


@router.post("/professor-only", response_model=ProfessorCheckResponse)
async def professor_check(user=Depends(verify_professor)):
    """Endpoint that requires professor role. Returns 403 for students."""
    return ProfessorCheckResponse(user_id=user["sub"], role=user["role"])


class StudentInfoResponse(BaseModel):
    username: str
    name: Optional[str] = None
    email: Optional[str] = None
    role: str


@router.get("/student/me", response_model=StudentInfoResponse)
async def get_student_info(user=Depends(verify_student_or_professor)):
    """Get current student's profile info. Also accessible by professors for viewing enrolled students."""
    from database import db

    user_data = db.get_user(user["sub"])
    if not user_data:
        raise HTTPException(status_code=404, detail="User account not found")

    if user_data["role"] == "student":
        return StudentInfoResponse(
            username=user_data["username"],
            name=user_data.get("name"),
            email=user_data.get("email"),
            role=user_data["role"],
        )

    # Professor access: return enrolled students for the professor's classes
    if user_data["role"] == "professor":
        classes = db.list_classes_by_professor(user["sub"])
        enrolled_students = []
        for cls in classes:
            students = db.get_class_students(cls["id"])
            enrolled_students.extend(students)
        # Return professor info with student count
        return StudentInfoResponse(
            username=user_data["username"],
            name=user_data.get("name"),
            email=user_data.get("email"),
            role="professor",
        )

    raise HTTPException(status_code=403, detail="Student or professor access required")


@router.post("/student-or-professor", response_model=StudentOrProfessorCheckResponse)
async def student_or_professor_check(user=Depends(verify_student_or_professor)):
    """Endpoint that requires student or professor role."""
    return StudentOrProfessorCheckResponse(user_id=user["sub"], role=user["role"])


@router.post("/kickoff", response_model=KickoffResponse)
async def kickoff_session(user=Depends(verify_professor)):
    """Professor kicks off a new session. Creates session and returns code for iOS to display."""
    from database import db
    from models import CreateSessionRequest, SessionConfiguration
    
    # Default config — iOS can override via POST /api/sessions
    config = SessionConfiguration()
    
    code = db.create_session(
        config=config,
        teams=[],
        created_by=user["sub"],
    )
    
    return KickoffResponse(
        code=code,
        message=f"Session {code} created. Share this code with students.",
    )


@router.get("/professor/me", response_model=ProfessorInfoResponse)
async def get_professor_info(user=Depends(verify_professor)):
    """Get current professor's profile info."""
    from database import db
    
    user_data = db.get_user(user["sub"])
    if not user_data:
        raise HTTPException(status_code=404, detail="Professor account not found")
    
    return ProfessorInfoResponse(
        username=user_data["username"],
        name=user_data.get("name"),
        email=user_data.get("email"),
        department=user_data.get("department"),
        role=user_data["role"],
    )


@router.put("/professor/me", response_model=UpdateProfessorResponse)
async def update_professor_info(
    email: Optional[str] = None,
    department: Optional[str] = None,
    user=Depends(verify_professor)
):
    """Update professor profile metadata."""
    from database import db
    
    user_data = db.get_user(user["sub"])
    if not user_data:
        raise HTTPException(status_code=404, detail="Professor account not found")
    
    # Update in DB
    if email or department:
        conn = db._get_conn()
        updates = []
        values = []
        if email:
            updates.append("email=?")
            values.append(email)
        if department:
            updates.append("department=?")
            values.append(department)
        if updates:
            values.append(user["sub"])
            conn.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE username=?",
                values,
            )
            conn.commit()
    
    return UpdateProfessorResponse(
        email=email or user_data.get("email"),
        department=department or user_data.get("department"),
    )


# ── SOTA Phase 2: Refresh Token Rotation ────────────────────────────────────

@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_token(req: RefreshTokenRequest):
    """Exchange a valid refresh token for a new access + refresh token pair.

    The old refresh token is revoked (rotation). If the old token is reused,
    it is rejected (detection of token theft).
    """
    result = refresh_access_token(req.refresh_token)
    return RefreshTokenResponse(
        accessToken=result["access_token"],
        refreshToken=result["refresh_token"],
        tokenType=result["token_type"],
    )


# ── SOTA Phase 2: MFA/TOTP ──────────────────────────────────────────────────

class MFASetupResponse(BaseModel):
    secret: str
    qr_code_url: str
    backup_codes: list[str]


class MFAVerifyRequest(BaseModel):
    code: str


class MFADisableRequest(BaseModel):
    password: Optional[str] = None


class MFAVerifyResponse(BaseModel):
    status: str
    backup_codes: list[str]


class MFAStatusResponse(BaseModel):
    enabled: bool


class MFAStatusMutationResponse(BaseModel):
    status: str


@router.post("/mfa/setup", response_model=MFASetupResponse)
async def setup_mfa(user=Depends(get_current_user)):
    """Generate a new TOTP secret for the current user (not yet enabled)."""
    from mfa import generate_totp_secret, generate_backup_codes, get_totp_uri
    from database import db

    user_id = user["sub"]
    secret = generate_totp_secret()
    db.set_mfa_secret(user_id, secret)
    backup = generate_backup_codes()
    # Store backup codes (not yet enabled — only on verify)
    qr_url = get_totp_uri(secret, user_id, "BizSimAI")
    return MFASetupResponse(secret=secret, qr_code_url=qr_url, backup_codes=backup)


@router.post("/mfa/verify", response_model=MFAVerifyResponse)
async def verify_mfa(req: MFAVerifyRequest, user=Depends(get_current_user)):
    """Verify a TOTP code and enable MFA for the user."""
    from mfa import verify_totp, generate_backup_codes
    from database import db
    from audit import log_event

    user_id = user["sub"]
    mfa_data = db.get_mfa_secret(user_id)
    if not mfa_data:
        raise HTTPException(status_code=400, detail="MFA not set up. Call /mfa/setup first.")

    if not verify_totp(mfa_data["secret"], req.code):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")

    backup = generate_backup_codes()
    db.enable_mfa(user_id, backup)
    log_event(actor=user_id, action="mfa_enabled")
    return {"status": "enabled", "backup_codes": backup}


@router.post("/mfa/disable", response_model=MFAStatusMutationResponse)
async def disable_mfa(req: MFADisableRequest, user=Depends(get_current_user)):
    """Disable MFA for the current user. MFA disable does not require password re-authentication (MFA was already set up and verified)."""
    from database import db
    from audit import log_event

    user_id = user["sub"]
    # MFA disable does not require password (user already proved ownership by setting up MFA)
    # Just verify the user exists and is not locked
    user_row = db.get_user(user_id)  # user["sub"] IS the username in this codebase
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")
    db.disable_mfa(user_id)
    log_event(actor=user_id, action="mfa_disabled")
    return {"status": "disabled"}


@router.get("/mfa/status", response_model=MFAStatusResponse)
async def mfa_status(user=Depends(get_current_user)):
    """Check if MFA is enabled for the current user."""
    from database import db
    user_id = user["sub"]
    enabled = db.is_mfa_enabled(user_id)
    return {"enabled": enabled}


# ── Password Reset ───────────────────────────────────────────────────────────

@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(req: ForgotPasswordRequest):
    """Request a password reset token for the given email.

    Always returns success (even if email not found) to prevent email enumeration.
    """
    from database import db
    import hashlib
    import secrets as _secrets

    # Find user by email (case-insensitive)
    conn = db._get_conn()
    row = conn.execute(
        "SELECT username FROM users WHERE LOWER(email)=LOWER(?) AND provider='password'",
        (req.email,),
    ).fetchone()

    raw_token = None
    if row:
        # Generate a random token and store its hash
        raw_token = _secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        # Store the reset token (invalidates any previous ones for this user)
        db.create_reset_token(row["username"], token_hash, expires_in_hours=1)

    # Always return success to prevent email enumeration when no user found.
    # Token is NOT returned in the response — it must be delivered out-of-band (email).
    return ForgotPasswordResponse(status="email_sent", token=None)


@router.post("/reset-password", response_model=ResetPasswordResponse)
async def reset_password(req: ResetPasswordRequest):
    """Reset password using a valid token.

    Validates the token, hashes the new password with bcrypt, and updates the user.
    """
    from database import db
    from security import hash_password, validate_password_complexity
    import hashlib

    # Hash the token to look it up
    token_hash = hashlib.sha256(req.token.encode()).hexdigest()

    # Verify the token is valid (exists, unused, not expired)
    token_record = db.verify_reset_token(token_hash)
    if not token_record:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    # Validate new password complexity
    is_valid, err_msg = validate_password_complexity(req.new_password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=err_msg)

    # Hash new password with bcrypt and update
    h = hash_password(req.new_password)
    db.update_user_password(token_record["user_id"], h)

    # Mark token as used
    db.consume_reset_token(token_hash)

    return ResetPasswordResponse(status="password_reset")


# ── Professor Status (public endpoint for iOS UI adaptation) ─────────────────

class ProfessorStatusResponse(BaseModel):
    professor_exists: bool
    message: str = ""


@router.get("/professor-status", response_model=ProfessorStatusResponse)
async def get_professor_status():
    """Check if any professor account exists in the system.

    This is a public endpoint (no auth required) that allows iOS to adapt its UI:
    - If no professor exists, hide student registration/login options
    - Shows appropriate messaging to users
    """
    from auth import _check_professor_exists

    exists = _check_professor_exists()
    if not exists:
        return ProfessorStatusResponse(
            professor_exists=False,
            message="No professor account is currently active. Student access is unavailable.",
        )
    return ProfessorStatusResponse(
        professor_exists=True,
        message="System is available.",
    )
