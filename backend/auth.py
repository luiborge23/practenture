"""JWT authentication for Practenture backend.

Supports:
- Owner login (super-admin, bootstraps on first run)
- Professor login (session management)
- Student login (team participation)
- Token verification middleware
- Apple/Google sign-in token exchange
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

import database as db_module
from auth_providers import verify_apple_id_token, verify_google_id_token

# ── JWT helpers (no external deps — pure Python implementation) ─────────────

import base64
import hmac as _hmac
import hashlib
import json as _json

_SECRET = os.environ.get("PRACTENTURE_JWT_SECRET")
if not _SECRET:
    raise RuntimeError(
        "PRACTENTURE_JWT_SECRET environment variable is required. "
        "Generate one with: python -c 'import secrets; print(secrets.token_hex(32))'"
    )
SECRET_KEY = _SECRET

try:
    _expiry = int(os.environ.get("PRACTENTURE_JWT_EXPIRY_HOURS", "24"))
except ValueError:
    _expiry = 24
# ── Token expiry settings ──────────────────────────────────────────────────
ACCESS_TOKEN_EXPIRE_MINUTES = _expiry * 60  # legacy: configurable via env
# SOTA Phase 2: Short-lived access (15 min) + long-lived refresh (7 days)
ACCESS_TOKEN_SOTA_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

ALGORITHM = "HS256"


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    s += "=" * padding
    return base64.urlsafe_b64decode(s)


def _create_token(payload: dict) -> str:
    header = _b64url_encode(_json.dumps({"alg": ALGORITHM, "typ": "JWT"}).encode())
    payload_b = _b64url_encode(_json.dumps(payload).encode())
    signing_input = f"{header}.{payload_b}"
    signature = _hmac.new(
        SECRET_KEY.encode(), signing_input.encode(), hashlib.sha256
    ).digest()
    signature_b = _b64url_encode(signature)
    return f"{signing_input}.{signature_b}"


def _create_access_token(payload: dict, *, issued_at: datetime | None = None) -> str:
    """Create an access token with a precise, timezone-safe issuance time.

    ``_create_token`` remains the low-level signer so legacy/test tokens without
    an ``iat`` claim can still be represented.  All production access-token
    issuance goes through this helper.
    """
    claims = dict(payload)
    now = issued_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    claims.setdefault("iat", now.astimezone(timezone.utc).timestamp())
    return _create_token(claims)


def _parse_utc_timestamp(value) -> datetime | None:
    """Parse JWT/SQLite timestamps as aware UTC datetimes."""
    if value is None or isinstance(value, bool):
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            try:
                return datetime.fromtimestamp(float(text), tz=timezone.utc)
            except ValueError:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.astimezone(timezone.utc)
    except (OverflowError, OSError, TypeError, ValueError):
        return None
    return None


def _is_suspended(user: Optional[Dict[str, Any]]) -> bool:
    """Return true only for an explicitly suspended persisted account.

    Historical rows without a status (or with NULL) remain active for backward
    compatibility. Normalizing case/whitespace keeps the lifecycle boundary
    fail-closed for equivalent explicit suspended values.
    """
    if not user:
        return False
    value = user.get("status")
    return isinstance(value, str) and value.strip().casefold() == "suspended"


def _require_not_suspended(user: Optional[Dict[str, Any]]) -> None:
    if _is_suspended(user):
        raise HTTPException(status_code=403, detail="Account is suspended")


def _verify_token(token: str) -> Optional[dict]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b, payload_b, signature_b = parts
        signing_input = f"{header_b}.{payload_b}"
        expected_sig = _hmac.new(
            SECRET_KEY.encode(), signing_input.encode(), hashlib.sha256
        ).digest()
        expected_sig_b = _b64url_encode(expected_sig)
        if not _hmac.compare_digest(signature_b, expected_sig_b):
            return None
        payload = _json.loads(_b64url_decode(payload_b))
        exp = payload.get("exp", 0)
        if datetime.now(timezone.utc).timestamp() > exp:
            return None

        # Password changes form a per-user access-token revocation boundary.
        # Missing users retain the historical behavior here; route-level code
        # may use non-persistent fixture/service subjects.  Existing users with
        # a boundary must present a parseable iat at or after that boundary.
        subject = payload.get("sub")
        user = db_module.db.get_user(str(subject)) if subject else None
        if _is_suspended(user):
            return None
        password_changed_at = _parse_utc_timestamp(
            user.get("password_changed_at") if user else None
        )
        if password_changed_at is not None:
            issued_at = _parse_utc_timestamp(payload.get("iat"))
            if issued_at is None or issued_at < password_changed_at:
                return None
        return payload
    except Exception:
        return None


# ── Pydantic models ────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    """Login request — supports password or Apple/Google ID token."""

    provider: str = Field(description="password, apple, or google")
    username: Optional[str] = None
    password: Optional[str] = None
    id_token: Optional[str] = None  # Apple/Google ID token
    mfa_code: Optional[str] = None  # TOTP code (required if MFA enabled)
    professor_code: Optional[str] = None  # PROF-XXXX-XXXX code required for new OAuth users
    provider_nonce: Optional[str] = None  # nonce bound into provider token

    model_config = {"extra": "ignore"}


class LoginResponse(BaseModel):
    access_token: str = Field(alias="accessToken")
    token_type: str = Field(default="bearer", alias="tokenType")
    role: str  # "owner", "professor", or "student"
    user_id: str = Field(alias="userId")
    must_change_password: bool = Field(default=False, alias="mustChangePassword")
    refresh_token: Optional[str] = Field(default=None, alias="refreshToken")
    mfa_required: bool = Field(default=False, alias="mfaRequired")
    professor_code_required: bool = Field(default=False, alias="professorCodeRequired")

    model_config = {"populate_by_name": True}


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(alias="refreshToken")


class RefreshTokenResponse(BaseModel):
    access_token: str = Field(alias="accessToken")
    refresh_token: str = Field(alias="refreshToken")
    token_type: str = Field(default="bearer", alias="tokenType")

    model_config = {"populate_by_name": True}


class RegisterRequest(BaseModel):
    """Student registration."""

    student_id: str
    name: str
    password: str


class ProfessorActivationRequest(BaseModel):
    professor_code: str = Field(alias="professorCode")
    username: str
    email: str
    name: str
    university_name: str = Field(default="", alias="universityName")
    password: str
    confirm_password: str = Field(alias="confirmPassword")
    model_config = {"populate_by_name": True, "extra": "forbid"}


class RegisterResponse(BaseModel):
    model_config = {"populate_by_name": True}

    student_id: str
    name: str
    message: str
    access_token: Optional[str] = Field(default=None, alias="accessToken")
    refresh_token: Optional[str] = Field(default=None, alias="refreshToken")


# ── Owner bootstrap ────────────────────────────────────────────────────────

def ensure_owner() -> None:
    """Bootstrap the owner account on first run. Creates user in SQLite if not exists."""
    from security import hash_password

    username = os.environ.get("PRACTENTURE_OWNER_USERNAME", "owner")
    password = os.environ.get("PRACTENTURE_OWNER_PASSWORD")

    if not password:
        # Auto-generate a random owner password on first run
        password = secrets.token_hex(16)
        # Write it back so it's stable across restarts (env var takes precedence)
        os.environ["PRACTENTURE_OWNER_PASSWORD"] = password

    h = hash_password(password)
    db_module.db.create_user(
        username=username, password_hash=h, role="owner", name="Owner"
    )


# ── Professor bootstrap ────────────────────────────────────────────────────

def ensure_professor() -> None:
    """Bootstrap the default professor account on first run.
    
    This creates a DEFAULT professor account for backwards compatibility.
    New professors should be pre-created by the owner via the admin API
    with a temporary password that must be changed on first login.
    
    SECURITY FIX: Uses PRACTENTURE_PROFESSOR_PASSWORD env var consistently.
    If not set, generates a random password and stores it in the DB for persistence.
    """
    from security import hash_password

    username = os.environ.get("PRACTENTURE_PROFESSOR_USERNAME", "professor")
    password = os.environ.get("PRACTENTURE_PROFESSOR_PASSWORD")

    if not password:
        # Generate a stable random password on first run and store it in DB
        # This ensures consistency across container restarts
        import secrets
        password = f"prof_{secrets.token_hex(12)}"

    h = hash_password(password)
    existing = db_module.db.get_user(username)
    if existing:
        # Update password hash to match current env var
        db_module.db.update_user_password(username, h)
    else:
        db_module.db.create_user(
            username=username, password_hash=h, role="professor", name=username
        )


# ── Auth dependencies ──────────────────────────────────────────────────────

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> Dict[str, Any]:
    """Dependency: extract and verify JWT token using standard 401 semantics."""
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
    return payload


def verify_professor(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Ensure user has professor role."""
    if user.get("role") not in ("professor", "owner"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Professor access required",
        )
    return user


def verify_student_or_professor(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Allow either professor or student."""
    if user.get("role") not in ("professor", "student", "owner"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authentication required",
        )
    return user


# ── Login / Register ───────────────────────────────────────────────────────

def login(req: LoginRequest) -> LoginResponse:
    """Authenticate and return JWT token."""
    from rate_limiter import check_login_rate, record_login_failure, record_login_success
    from audit import log_event

    if req.provider == "password":
        if not req.username or not req.password:
            raise HTTPException(status_code=400, detail="Username and password required")

        # Rate limit check
        locked, retry_after = check_login_rate(req.username)
        if locked:
            raise HTTPException(
                status_code=429,
                detail=f"Too many failed attempts. Try again in {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)},
            )

        # Check owner
        owner_username = os.environ.get("PRACTENTURE_OWNER_USERNAME", "owner")
        if req.username == owner_username:
            user = db_module.db.verify_user(req.username, req.password)
            if user and user["role"] == "owner":
                _require_not_suspended(user)
                # MFA check (if enabled)
                if db_module.db.is_mfa_enabled(req.username):
                    if not req.mfa_code:
                        return {"mfaRequired": True, "accessToken": "", "tokenType": "bearer", "role": "owner", "userId": req.username, "mustChangePassword": False}
                    from mfa import verify_totp
                    mfa_data = db_module.db.get_mfa_secret(req.username)
                    if not mfa_data or not verify_totp(mfa_data["secret"], req.mfa_code):
                        raise HTTPException(status_code=401, detail="Invalid MFA code")
                record_login_success(req.username)
                log_event(actor=req.username, action="login_success", details={"role": "owner"})
                token = _create_access_token({
                    "sub": req.username,
                    "role": "owner",
                    "tenantId": "platform",
                    "exp": (datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_SOTA_MINUTES)).timestamp(),
                })
                refresh = _generate_refresh_token(req.username)
                resp = LoginResponse(accessToken=token, tokenType="bearer", role="owner", userId=req.username, refreshToken=refresh)
                resp_dict = resp.model_dump(by_alias=True)
                resp_dict["mustChangePassword"] = False
                return resp_dict

        # Check professor (any professor, not just the default one)
        user = db_module.db.verify_user(req.username, req.password)
        if user and user["role"] == "professor":
            _require_not_suspended(user)
            # MFA check (if enabled)
            if db_module.db.is_mfa_enabled(req.username):
                if not req.mfa_code:
                    return {"mfaRequired": True, "accessToken": "", "tokenType": "bearer", "role": "professor", "userId": req.username, "mustChangePassword": False}
                from mfa import verify_totp
                mfa_data = db_module.db.get_mfa_secret(req.username)
                if not mfa_data or not verify_totp(mfa_data["secret"], req.mfa_code):
                    raise HTTPException(status_code=401, detail="Invalid MFA code")
            record_login_success(req.username)
            # Derive tenantId from primary organization (if exists)
            org = db_module.db.get_primary_org(req.username)
            tenant_id = org["id"] if org else ""
            log_event(actor=req.username, action="login_success", details={"role": "professor", "tenantId": tenant_id})
            token = _create_access_token({
                "sub": req.username,
                "role": "professor",
                "name": user.get("name", ""),
                "tenantId": tenant_id,
                "exp": (datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_SOTA_MINUTES)).timestamp(),
            })
            refresh = _generate_refresh_token(req.username)
            resp = LoginResponse(accessToken=token, tokenType="bearer", role="professor", userId=req.username, refreshToken=refresh)
            resp_dict = resp.model_dump(by_alias=True)
            resp_dict["mustChangePassword"] = bool(user.get("must_change_password", 0))
            return resp_dict

        # Check student
        if user and user["role"] == "student":
            _require_not_suspended(user)
            # Check if professor still exists — students can't use the app without a professor
            prof_exists = _check_professor_exists()
            if not prof_exists:
                raise HTTPException(
                    status_code=403,
                    detail="Student access is currently unavailable. Please contact your professor or try again later.",
                )
            # MFA check (if enabled)
            if db_module.db.is_mfa_enabled(user["username"]):
                if not req.mfa_code:
                    return {"mfaRequired": True, "accessToken": "", "tokenType": "bearer", "role": "student", "userId": user["username"], "mustChangePassword": False}
                from mfa import verify_totp
                mfa_data = db_module.db.get_mfa_secret(user["username"])
                if not mfa_data or not verify_totp(mfa_data["secret"], req.mfa_code):
                    raise HTTPException(status_code=401, detail="Invalid MFA code")
            record_login_success(req.username)
            log_event(actor=req.username, action="login_success", details={"role": "student"})
            token = _create_access_token({
                "sub": user["username"],
                "role": "student",
                "name": user.get("name", ""),
                "tenantId": "",
                "exp": (datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_SOTA_MINUTES)).timestamp(),
            })
            refresh = _generate_refresh_token(user["username"])
            resp = LoginResponse(accessToken=token, tokenType="bearer", role="student", userId=user["username"], refreshToken=refresh)
            resp_dict = resp.model_dump(by_alias=True)
            resp_dict["mustChangePassword"] = bool(user.get("must_change_password", 0))
            return resp_dict

        # Failed login — check if user exists to give a distinct error message
        user_record = db_module.db.get_user(req.username)
        if not user_record:
            record_login_failure(req.username)
            log_event(actor=req.username, action="login_failure", details={"reason": "user_not_found"})
            raise HTTPException(status_code=401, detail="User not found. Please check your credentials and contact IT if the problem persists.")
        else:
            record_login_failure(req.username)
            log_event(actor=req.username, action="login_failure", details={"reason": "wrong_password"})
            raise HTTPException(status_code=401, detail="Wrong username or password. Please try again.")

    elif req.provider in ("apple", "google"):
        if not req.id_token:
            raise HTTPException(status_code=400, detail="id_token required")
        apple_aud = os.environ.get("PRACTENTURE_APPLE_AUDIENCE")
        google_aud = os.environ.get("PRACTENTURE_GOOGLE_AUDIENCE")
        payload = (verify_apple_id_token(req.id_token, apple_aud) if req.provider == "apple"
                   else verify_google_id_token(req.id_token, google_aud))
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid provider token")
        if req.provider_nonce:
            token_nonce = str(payload.get("nonce") or "")
            if not token_nonce or not _hmac.compare_digest(token_nonce, req.provider_nonce):
                raise HTTPException(status_code=401, detail="Provider nonce mismatch")

        from auth_enrollment import find_social_user, enroll_social_professor
        from security import hash_password
        from audit import log_event
        subject = str(payload.get("sub") or "")
        if not subject:
            raise HTTPException(status_code=401, detail="Provider token has no stable subject")
        email = str(payload.get("email") or "")
        name = str(payload.get("name") or "")
        existing_user = find_social_user(req.provider, subject)
        if existing_user:
            user = existing_user
            _require_not_suspended(user)
        else:
            if not req.professor_code:
                return LoginResponse(accessToken="", tokenType="bearer", role="professor",
                    userId="", mustChangePassword=False, refreshToken=None,
                    mfaRequired=False, professorCodeRequired=True).model_dump(by_alias=True)
            try:
                user = enroll_social_professor(
                    provider=req.provider, subject=subject, email=email, name=name,
                    code=req.professor_code,
                    password_hash=hash_password(secrets.token_hex(24)),
                )
            except ValueError as exc:
                raise HTTPException(status_code=409 if "used" in str(exc).lower() else 401, detail=str(exc))
        user_id = user["username"]
        role = user["role"]
        org = db_module.db.get_primary_org(user_id)
        tenant_id = org["id"] if org else ""
        token = _create_access_token({"sub": user_id, "role": role, "tenantId": tenant_id,
            "email": user.get("email") or email,
            "exp": (datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_SOTA_MINUTES)).timestamp()})
        refresh = _generate_refresh_token(user_id)
        log_event(actor=user_id, action="login_success", details={"role": role, "provider": req.provider})
        return LoginResponse(accessToken=token, tokenType="bearer", role=role,
            userId=user_id, refreshToken=refresh, mustChangePassword=bool(user.get("must_change_password", 0)),
            professorCodeRequired=False).model_dump(by_alias=True)

    raise HTTPException(status_code=400, detail=f"Unsupported provider: {req.provider}")


def activate_password_professor(req: ProfessorActivationRequest) -> LoginResponse:
    """Atomically consume a PROF invitation and create a password professor."""
    from security import hash_password, validate_password_complexity
    from auth_enrollment import activate_password_professor as persist_activation
    if req.password != req.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    valid, message = validate_password_complexity(req.password)
    if not valid:
        raise HTTPException(status_code=400, detail=message)
    try:
        user = persist_activation(code=req.professor_code, username=req.username, email=req.email,
            name=req.name, university_name=req.university_name, password_hash=hash_password(req.password))
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(status_code=409 if "exists" in detail or "used" in detail else 400, detail=detail)
    org = db_module.db.get_primary_org(user["username"])
    tenant_id = org["id"] if org else ""
    token = _create_access_token({"sub": user["username"], "role": "professor", "name": user["name"],
        "tenantId": tenant_id,
        "exp": (datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_SOTA_MINUTES)).timestamp()})
    refresh = _generate_refresh_token(user["username"])
    return LoginResponse(accessToken=token, role="professor", userId=user["username"], refreshToken=refresh)


def register(req: RegisterRequest) -> RegisterResponse:
    """Register a new student."""
    from security import hash_password, validate_password_complexity

    # Validate password complexity
    is_valid, err_msg = validate_password_complexity(req.password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=err_msg)

    # Check if professor exists — students can only register when a professor is active
    prof_exists = _check_professor_exists()
    if not prof_exists:
        raise HTTPException(
            status_code=403,
            detail="Registration is currently unavailable. Please contact your professor or try again later.",
        )

    if db_module.db.get_user_by_student_id(req.student_id):
        raise HTTPException(status_code=409, detail="Student ID already registered")

    import hashlib
    h = hash_password(req.password)

    success = db_module.db.register_student(
        student_id=req.student_id, name=req.name, password=h
    )
    if not success:
        raise HTTPException(status_code=409, detail="Registration failed")

    # Auto-login: generate tokens so iOS can skip the second API call
    token = _create_access_token({
        "sub": req.student_id,
        "role": "student",
        "name": req.name,
        "tenantId": "",
        "exp": (datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_SOTA_MINUTES)).timestamp(),
    })
    refresh = _generate_refresh_token(req.student_id)

    return RegisterResponse(
        student_id=req.student_id,
        name=req.name,
        message="Registration successful",
        access_token=token,
        refresh_token=refresh,
    )


# ── Professor existence check ────────────────────────────────────────────────

def _check_professor_exists() -> bool:
    """Check if any professor account exists in the database."""
    with db_module.db._get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM users WHERE role='professor' LIMIT 1"
        ).fetchone()
    return row is not None


# ── SOTA Phase 2: Refresh Token Rotation ────────────────────────────────────

def _hash_token(token: str) -> str:
    """Hash a refresh token for storage (never store raw tokens)."""
    return hashlib.sha256(token.encode()).hexdigest()


def _generate_refresh_token(user_id: str, rotated_from: Optional[str] = None) -> str:
    """Generate a new refresh token, store its hash, return the raw token."""
    raw_token = secrets.token_urlsafe(48)
    token_hash = _hash_token(raw_token)
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)).timestamp()
    db_module.db.store_refresh_token(
        token_hash=token_hash,
        user_id=user_id,
        issued_at=now.timestamp(),
        expires_at=expires_at,
        rotated_from=rotated_from,
    )
    return raw_token


def refresh_access_token(refresh_token_str: str) -> dict:
    """Verify a refresh token, rotate it, and return new access + refresh tokens.

    Returns dict with access_token, refresh_token, token_type.
    Raises HTTPException on failure.
    """
    token_hash = _hash_token(refresh_token_str)
    record = db_module.db.verify_refresh_token(token_hash)

    if not record:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user_id = record["user_id"]

    # Resolve lifecycle state before any destructive rotation. A suspended
    # refresh attempt must not consume the presented token or mint replacements.
    user = db_module.db.get_user(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    _require_not_suspended(user)

    # Revoke the old refresh token (rotation)
    db_module.db.revoke_refresh_token(token_hash)

    role = user["role"]
    org = db_module.db.get_primary_org(user_id)
    tenant_id = org["id"] if org else ""

    # Create new short-lived access token
    access_token = _create_access_token({
        "sub": user_id,
        "role": role,
        "name": user.get("name", ""),
        "tenantId": tenant_id,
        "exp": (datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_SOTA_MINUTES)).timestamp(),
    })

    # Create new refresh token (rotated from old)
    new_refresh = _generate_refresh_token(user_id, rotated_from=token_hash)

    return {
        "access_token": access_token,
        "refresh_token": new_refresh,
        "token_type": "bearer",
    }
