"""JWT authentication for BizSimAI backend.

Supports:
- Professor login (admin role)
- Student login (student role)
- Token verification middleware
- Apple/Google sign-in token exchange
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from auth_providers import verify_apple_id_token, verify_google_id_token

# ── JWT helpers (no external deps — pure Python implementation) ─────────────

# For production, replace with python-jose[cryptography].
# This is a minimal implementation sufficient for classroom deployment.

import os

# ── Production configuration via environment variables ──────────────────────

_SECRET = os.environ.get("BIZSIMAI_JWT_SECRET")
if not _SECRET:
    raise RuntimeError(
        "BIZSIMAI_JWT_SECRET environment variable is required. "
        "Generate one with: python -c 'import secrets; print(secrets.token_hex(32))'"
    )
SECRET_KEY = _SECRET

try:
    _expiry = int(os.environ.get("BIZSIMAI_JWT_EXPIRY_HOURS", "24"))
except ValueError:
    _expiry = 24
ACCESS_TOKEN_EXPIRE_MINUTES = _expiry * 60

ALGORITHM = "HS256"

# Simple base64url encoding (no padding)
import base64


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    s += "=" * padding
    return base64.urlsafe_b64decode(s)


def _create_token(payload: dict) -> str:
    import hmac, hashlib, json

    header = _b64url_encode(json.dumps({"alg": ALGORITHM, "typ": "JWT"}).encode())
    payload_b = _b64url_encode(json.dumps(payload).encode())
    signing_input = f"{header}.{payload_b}"
    signature = hmac.new(
        SECRET_KEY.encode(), signing_input.encode(), hashlib.sha256
    ).digest()
    signature_b = _b64url_encode(signature)
    return f"{signing_input}.{signature_b}"


def _verify_token(token: str) -> Optional[dict]:
    import hmac, hashlib, json

    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b, payload_b, signature_b = parts
        signing_input = f"{header_b}.{payload_b}"
        expected_sig = hmac.new(
            SECRET_KEY.encode(), signing_input.encode(), hashlib.sha256
        ).digest()
        expected_sig_b = _b64url_encode(expected_sig)
        if signature_b != expected_sig_b:
            return None
        payload = json.loads(_b64url_decode(payload_b))
        # Check expiry
        exp = payload.get("exp", 0)
        if datetime.now(timezone.utc).timestamp() > exp:
            return None
        return payload
    except Exception:
        return None


# ── Pydantic models ────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    """Login request — supports professor password or Apple/Google ID token."""

    provider: str = Field(description="password, apple, or google")
    username: Optional[str] = None
    password: Optional[str] = None
    id_token: Optional[str] = None  # Apple/Google ID token


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str  # "professor" or "student"
    user_id: str


class RegisterRequest(BaseModel):
    """Student registration."""

    student_id: str
    name: str
    password: str  # In prod: hash with bcrypt


class RegisterResponse(BaseModel):
    student_id: str
    name: str
    message: str


# ── In-memory user store (replace with DB in prod) ─────────────────────────

# Default professor credentials (overridable via env vars)
DEFAULT_PROFESSOR = {
    "username": os.environ.get("BIZSIMAI_PROFESSOR_USERNAME", "professor"),
    "password": os.environ.get("BIZSIMAI_PROFESSOR_PASSWORD", "bizsimai2026"),
    "role": "professor",
}

# Simulated student store
_student_store: Dict[str, Dict[str, Any]] = {}


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())) -> Dict[str, Any]:
    """Dependency: extract and verify JWT token."""
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
    if user.get("role") != "professor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Professor access required",
        )
    return user


def verify_student_or_professor(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Allow either professor or student."""
    if user.get("role") not in ("professor", "student"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authentication required",
        )
    return user


def login(req: LoginRequest) -> LoginResponse:
    """Authenticate and return JWT token."""
    if req.provider == "password":
        if req.username == DEFAULT_PROFESSOR["username"] and req.password == DEFAULT_PROFESSOR["password"]:
            token = _create_token({
                "sub": req.username,
                "role": "professor",
                "exp": (datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp(),
            })
            return LoginResponse(access_token=token, role="professor", user_id=req.username)
        # Check student store
        for sid, info in _student_store.items():
            if info["name"] == req.username and info["password"] == req.password:
                token = _create_token({
                    "sub": sid,
                    "role": "student",
                    "exp": (datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp(),
                })
                return LoginResponse(access_token=token, role="student", user_id=sid)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    elif req.provider in ("apple", "google"):
        if not req.id_token:
            raise HTTPException(status_code=400, detail="id_token required")

        # ── Actual provider verification ──────────────────────────────────
        apple_aud = os.environ.get("BIZSIMAI_APPLE_AUDIENCE")
        google_aud = os.environ.get("BIZSIMAI_GOOGLE_AUDIENCE")

        if req.provider == "apple":
            payload = verify_apple_id_token(req.id_token, apple_aud)
        else:
            payload = verify_google_id_token(req.id_token, google_aud)

        if not payload:
            raise HTTPException(status_code=401, detail="Invalid provider token")

        # Extract user info from verified payload
        user_id = payload.get("sub") or payload.get("email") or f"{req.provider}_unknown"
        email = payload.get("email")

        token = _create_token({
            "sub": user_id,
            "role": "student",
            "email": email,
            "exp": (datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp(),
        })
        return LoginResponse(access_token=token, role="student", user_id=user_id)

    raise HTTPException(status_code=400, detail=f"Unsupported provider: {req.provider}")


def register(req: RegisterRequest) -> RegisterResponse:
    """Register a new student."""
    if req.student_id in _student_store:
        raise HTTPException(status_code=409, detail="Student ID already registered")
    _student_store[req.student_id] = {
        "name": req.name,
        "password": req.password,  # In prod: hash with bcrypt
    }
    return RegisterResponse(
        student_id=req.student_id,
        name=req.name,
        message="Registration successful",
    )
