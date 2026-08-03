"""Authentication endpoints for Practenture backend."""

import os
import secrets
from typing import NoReturn, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field

from auth import (
    LoginRequest,
    LoginResponse,
    ProfessorActivationRequest,
    RefreshTokenRequest,
    RefreshTokenResponse,
    RegisterRequest,
    RegisterResponse,
    get_current_user,
    login,
    activate_password_professor,
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


class AccountDeletionRequirementsResponse(BaseModel):
    provider: str
    reauthentication: str
    mfaRequired: bool
    confirmationPhrase: str = "DELETE"
    challengeId: Optional[str] = None
    challenge: Optional[str] = None
    challengeExpiresAt: Optional[float] = None
    operationToken: str


class DeleteAccountRequest(BaseModel):
    confirmation: str
    password: Optional[str] = None
    mfa_code: Optional[str] = Field(default=None, alias="mfaCode")
    provider_token: Optional[str] = Field(default=None, alias="providerToken")
    provider_nonce: Optional[str] = Field(default=None, alias="providerNonce")
    provider_authorization_code: Optional[str] = Field(
        default=None, alias="providerAuthorizationCode"
    )
    challenge_id: Optional[str] = Field(default=None, alias="challengeId")
    operation_token: Optional[str] = Field(default=None, alias="operationToken")


class AccountDeletionStatusRequest(BaseModel):
    operation_token: str = Field(alias="operationToken")


class AccountDeletionStatusResponse(BaseModel):
    status: str


@router.post("/login", response_model=LoginResponse)
async def login_endpoint(req: LoginRequest):
    """Authenticate user and return JWT token.
    
    Providers:
    - password: username/password (professor or student)
    - apple: Apple Sign-In ID token (returning linked identity or invited professor enrollment)
    - google: Google Sign-In ID token (returning linked identity or invited professor enrollment)
    """
    return login(req)


@router.post("/password/activate-professor", response_model=LoginResponse, status_code=201)
async def activate_professor_endpoint(req: ProfessorActivationRequest):
    """Create a new password professor by atomically consuming a one-time invitation."""
    return activate_password_professor(req)


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
    
    organization_id = db.get_single_organization_id(user["sub"])
    if organization_id is None:
        raise HTTPException(
            status_code=403,
            detail="A professor must belong to exactly one organization to use kickoff",
        )
    code = db.create_session(
        config=config,
        teams=[],
        created_by=user["sub"],
        professor_user_id=user["sub"],
        organization_id=organization_id,
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


@router.get(
    "/account/deletion-requirements",
    response_model=AccountDeletionRequirementsResponse,
)
def account_deletion_requirements(
    request: Request,
    user=Depends(get_current_user),
):
    """Return the identity proof required before destructive self-deletion."""
    from database import db

    account = db.get_user(user["sub"])
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    provider = str(account.get("provider") or "password").strip().casefold()
    if provider not in {"apple", "google"}:
        provider = "password"
    from account_deletion_security import create_deletion_challenge

    challenge = create_deletion_challenge(
        db,
        user_id=user["sub"],
        provider=provider,
    )
    return AccountDeletionRequirementsResponse(
        provider=provider,
        reauthentication=provider,
        mfaRequired=db.is_mfa_enabled(user["sub"]),
        challengeId=challenge["challengeId"],
        challenge=challenge["challenge"],
        challengeExpiresAt=challenge["expiresAt"],
        operationToken=challenge["operationToken"],
    )


@router.post(
    "/account/deletion-status",
    response_model=AccountDeletionStatusResponse,
)
def deletion_status(request: AccountDeletionStatusRequest):
    """Resolve an opaque receipt after a potentially lost deletion response."""
    from account_deletion_security import account_deletion_status
    from database import db

    resolved = account_deletion_status(db, operation_token=request.operation_token)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Deletion receipt not found.")
    return AccountDeletionStatusResponse(status=resolved)


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
def delete_current_account(
    deletion: DeleteAccountRequest,
    http_request: Request,
    user=Depends(get_current_user),
):
    """Delete locally and durably enqueue provider revocation in one transaction."""
    from account_deletion import AccountDeletionError, delete_account
    from account_deletion_security import (
        DeletionSecurityError,
        clear_deletion_failures,
        reserve_deletion_attempt,
    )
    from database import db

    client_signal = "|".join(
        (
            http_request.client.host if http_request.client else "unknown",
            http_request.headers.get("user-agent", "unknown")[:200],
        )
    )

    def fail(
        status_code: int, code: str, message: str, *, count: bool = True
    ) -> NoReturn:
        raise HTTPException(
            status_code=status_code,
            detail={"code": code, "message": message},
        )

    try:
        reserve_deletion_attempt(
            db,
            user_id=user["sub"],
            client_signal=client_signal,
        )
    except DeletionSecurityError as error:
        fail(429, error.code, error.message, count=False)

    account = db.get_user(user["sub"])
    if not account:
        fail(404, "not_found", "Account not found.", count=False)
    assert account is not None
    provider = str(account.get("provider") or "password").strip().casefold()
    verified_provider = None
    verified_subject = None
    provider_issued_at = None
    provider_revocation_payload = None
    if provider in {"apple", "google"}:
        provider_token = deletion.provider_token
        if not provider_token:
            fail(
                403,
                "provider_reauthentication_required",
                f"Reauthenticate with {provider.title()} to delete this account.",
            )
        audience = os.environ.get(
            "PRACTENTURE_APPLE_AUDIENCE"
            if provider == "apple"
            else "PRACTENTURE_GOOGLE_AUDIENCE"
        )
        payload = (
            verify_apple_id_token(provider_token, audience)
            if provider == "apple"
            else verify_google_id_token(provider_token, audience)
        )
        if not payload:
            fail(403, "provider_token_invalid", "The provider token is invalid.")
        assert payload is not None
        if provider == "apple" and not deletion.provider_nonce:
            fail(403, "provider_nonce_required", "Apple reauthentication is incomplete.")
        verified_provider = provider
        verified_subject = str(payload.get("sub") or "")
        try:
            provider_issued_at = (
                float(payload["iat"]) if payload.get("iat") is not None else None
            )
        except (TypeError, ValueError):
            fail(403, "provider_token_invalid", "The provider token is invalid.")
        if not verified_subject or not secrets.compare_digest(
            str(account.get("provider_uid") or ""), verified_subject
        ):
            fail(
                403,
                "provider_identity_mismatch",
                "The reauthenticated identity does not match this account.",
            )
        if provider == "apple":
            from apple_token_revocation import (
                AppleRevocationError,
                exchange_apple_authorization_code,
            )

            if not deletion.provider_authorization_code:
                fail(
                    403,
                    "apple_authorization_code_required",
                    "Apple reauthentication did not return an authorization code.",
                )
            try:
                provider_revocation_payload = exchange_apple_authorization_code(
                    deletion.provider_authorization_code
                )
            except AppleRevocationError as error:
                fail(503, "apple_exchange_failed", str(error), count=False)
            exchanged_id_token = provider_revocation_payload.get("id_token")
            exchanged_payload = (
                verify_apple_id_token(str(exchanged_id_token), audience)
                if exchanged_id_token
                else None
            )
            if (
                not exchanged_payload
                or not secrets.compare_digest(
                    str(exchanged_payload.get("sub") or ""), verified_subject
                )
                or not secrets.compare_digest(
                    str(exchanged_payload.get("nonce") or ""),
                    deletion.provider_nonce or "",
                )
            ):
                fail(
                    403,
                    "apple_authorization_code_mismatch",
                    "The Apple authorization code does not match this deletion request.",
                )

    try:
        delete_account(
            db,
            user_id=user["sub"],
            confirmation=deletion.confirmation,
            password=deletion.password,
            mfa_code=deletion.mfa_code,
            verified_provider=verified_provider,
            verified_provider_subject=verified_subject,
            challenge_id=deletion.challenge_id,
            operation_token=deletion.operation_token,
            provider_nonce=deletion.provider_nonce,
            provider_issued_at=provider_issued_at,
            provider_revocation_payload=provider_revocation_payload,
        )
    except AccountDeletionError as error:
        status_code = {
            "not_found": 404,
            "owner_not_supported": 403,
            "confirmation_required": 409,
            "password_reauthentication_required": 403,
            "provider_reauthentication_required": 403,
            "provider_identity_mismatch": 403,
            "mfa_reauthentication_required": 403,
            "mfa_reauthentication_invalid": 403,
            "active_sessions_require_resolution": 409,
            "deletion_challenge_required": 403,
            "deletion_challenge_invalid": 403,
            "deletion_challenge_replayed": 403,
            "provider_nonce_mismatch": 403,
            "provider_token_not_fresh": 403,
        }.get(error.code, 400)
        fail(
            status_code,
            error.code,
            error.message,
            count=error.code not in {"owner_not_supported", "active_sessions_require_resolution"},
        )
    clear_deletion_failures(
        db,
        user_id=user["sub"],
        client_signal=client_signal,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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


class MFASetupRequest(BaseModel):
    password: str


class MFAVerifyRequest(BaseModel):
    code: str


class MFADisableRequest(BaseModel):
    password: Optional[str] = None
    mfa_code: Optional[str] = None


class MFAVerifyResponse(BaseModel):
    status: str
    backup_codes: list[str]


class MFAStatusResponse(BaseModel):
    enabled: bool


class MFAStatusMutationResponse(BaseModel):
    status: str


@router.post("/mfa/setup", response_model=MFASetupResponse)
async def setup_mfa(req: MFASetupRequest, user=Depends(get_current_user)):
    """Begin MFA enrollment after current-password reauthentication."""
    from mfa import generate_totp_secret, get_totp_uri
    from database import db
    from security import verify_password

    user_id = user["sub"]
    user_row = db.get_user(user_id)
    if not user_row or not verify_password(req.password, str(user_row.get("password_hash") or "")):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    if db.is_mfa_enabled(user_id):
        raise HTTPException(status_code=409, detail="MFA is already enabled")
    secret = generate_totp_secret()
    db.set_mfa_secret(user_id, secret)
    qr_url = get_totp_uri(secret, user_id, "Practenture")
    # Recovery codes become valid and are returned only after TOTP confirmation.
    return MFASetupResponse(secret=secret, qr_code_url=qr_url, backup_codes=[])


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
    """Disable MFA only after password and current second-factor reauthentication."""
    from database import db
    from audit import log_event
    from security import verify_password

    user_id = user["sub"]
    user_row = db.get_user(user_id)
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")
    if not req.password or not verify_password(req.password, str(user_row.get("password_hash") or "")):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    result = db.verify_mfa_code(user_id, req.mfa_code)
    if result != "accepted":
        raise HTTPException(status_code=401, detail="Invalid or already used MFA code")
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
def forgot_password(req: ForgotPasswordRequest):
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
    token_hash = None
    if row:
        # Generate a random token and store its hash
        raw_token = _secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        # Store the reset token (invalidates any previous ones for this user)
        db.create_reset_token(row["username"], token_hash, expires_in_hours=1)

        # Keep account discovery opaque: callers always receive the same response.
        # If delivery fails, invalidate the undisclosed credential immediately.
        try:
            from password_reset_email import send_password_reset_code

            send_password_reset_code(recipient=req.email.strip().lower(), code=raw_token)
        except Exception:
            with db._lock:
                conn.execute(
                    "UPDATE password_reset_tokens SET used=1 WHERE token_hash=?",
                    (token_hash,),
                )
                conn.commit()

    # Always return success to prevent email enumeration when no user found.
    # Token is NOT returned in the response — it must be delivered out-of-band (email).
    return ForgotPasswordResponse(status="email_sent", token=None)


@router.post("/reset-password", response_model=ResetPasswordResponse)
async def reset_password(req: ResetPasswordRequest):
    """Reset password using a valid token.

    Validates password policy, hashes the password with bcrypt, then atomically
    consumes the token, updates the password, and revokes active credentials.
    """
    import hashlib

    from database import db
    from security import hash_password, validate_password_complexity

    # Preserve the legacy error precedence (invalid token before password policy)
    # as a read-only preflight. The transactional method below independently
    # revalidates and conditionally consumes the token, so this check conveys no
    # authority and cannot reintroduce the former consumption race.
    token_hash = hashlib.sha256(req.token.encode()).hexdigest()
    if not db.verify_reset_token(token_hash):
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    # Validate new password complexity
    is_valid, err_msg = validate_password_complexity(req.new_password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=err_msg)

    # Hash before acquiring SQLite's write lock; the database method performs all
    # persistence changes on one dedicated BEGIN IMMEDIATE transaction.
    h = hash_password(req.new_password)
    if not db.complete_password_reset(req.token, h):
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

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
