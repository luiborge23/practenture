"""Authentication endpoints for BizSimAI backend."""

import os

from fastapi import APIRouter, Depends, HTTPException
from auth import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    get_current_user,
    login,
    register,
    verify_professor,
    verify_student_or_professor,
)
from auth_providers import verify_apple_id_token, verify_google_id_token

router = APIRouter(prefix="/api/auth", tags=["authentication"])


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


@router.post("/verify")
async def verify_token(user=Depends(get_current_user)):
    """Verify current token and return user info."""
    return {
        "user_id": user["sub"],
        "role": user["role"],
        "valid": True,
    }


@router.post("/professor-only")
async def professor_check(user=Depends(verify_professor)):
    """Endpoint that requires professor role. Returns 403 for students."""
    return {
        "status": "authorized",
        "user_id": user["sub"],
        "role": user["role"],
    }


@router.post("/student-or-professor")
async def student_or_professor_check(user=Depends(verify_student_or_professor)):
    """Endpoint that requires student or professor role."""
    return {
        "status": "authorized",
        "user_id": user["sub"],
        "role": user["role"],
    }
