"""SOTA Phase 2: SCIM 2.0 User Provisioning.

Implements SCIM (System for Cross-domain Identity Management) 2.0 endpoints
for automated user provisioning from enterprise IdPs (Azure AD, Okta, OneLogin).

Supports:
- GET /Users — list all SCIM-provisioned users
- POST /Users — create a new user via SCIM
- GET /Users/{id} — get a specific user
- PUT /Users/{id} — update a user
- DELETE /Users/{id} — deactivate a user
- GET /Groups — list groups (stub for IdP compatibility)
- POST /Users/.search — search users

Authentication: Bearer token with SCIM permissions (owner role).
Content-Type: application/scim+json
"""

import json
import secrets
import hmac
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/scim/v2", tags=["scim"])

SCIM_CONTENT_TYPE = "application/scim+json"


def _scim_user_resource(user_id: str, external_id: str, active: bool,
                        name: str = "", email: str = "") -> dict:
    """Build a SCIM 2.0 User resource representation."""
    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "id": user_id,
        "externalId": external_id,
        "userName": user_id,
        "name": {"formatted": name},
        "emails": [{"value": email, "primary": True}] if email else [],
        "active": active,
        "meta": {
            "resourceType": "User",
            "created": datetime.now(timezone.utc).isoformat(),
            "lastModified": datetime.now(timezone.utc).isoformat(),
            "location": f"/api/scim/v2/Users/{user_id}",
        },
    }


def _scim_list_response(resources: list, start_index: int = 1, count: int = 100) -> dict:
    return {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
        "totalResults": len(resources),
        "startIndex": start_index,
        "itemsPerPage": count,
        "Resources": resources,
    }


@router.get("/Users")
async def list_users(request: Request):
    """SCIM GET /Users — list all SCIM-provisioned users."""
    # Auth: require owner-level SCIM token
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not _verify_scim_token(token):
        raise HTTPException(status_code=401, detail="Invalid SCIM bearer token")

    from database import db
    scim_users = db.scim_list_users()
    resources = []
    for su in scim_users:
        user_data = db.get_user(su["user_id"])
        if user_data:
            resources.append(_scim_user_resource(
                user_id=su["user_id"],
                external_id=su["external_id"],
                active=bool(su["active"]),
                name=user_data.get("name", ""),
                email=user_data.get("email", ""),
            ))
    return JSONResponse(content=_scim_list_response(resources), media_type=SCIM_CONTENT_TYPE)


@router.post("/Users")
async def create_user(request: Request):
    """SCIM POST /Users — create a new user."""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not _verify_scim_token(token):
        raise HTTPException(status_code=401, detail="Invalid SCIM bearer token")

    body = await request.json()
    from database import db
    from security import hash_password

    user_name = body.get("userName", "")
    external_id = body.get("externalId", user_name)
    name = body.get("name", {}).get("formatted", "")
    emails = body.get("emails", [])
    email = emails[0].get("value", "") if emails else ""
    active = body.get("active", True)

    if not user_name:
        raise HTTPException(status_code=400, detail="userName is required")

    # Check if already exists
    existing = db.scim_get_user_by_external(external_id) if external_id else None
    if existing:
        raise HTTPException(status_code=409, detail="User already exists")

    # Create the user account
    dummy_hash = hash_password(secrets.token_hex(16))
    db.upsert_user(
        username=user_name, password_hash=dummy_hash, role="student",
        name=name, email=email, provider="scim", provider_uid=external_id,
    )
    db.scim_create_user(user_id=user_name, external_id=external_id)

    resource = _scim_user_resource(user_name, external_id, active, name, email)
    return JSONResponse(content=resource, media_type=SCIM_CONTENT_TYPE, status_code=201)


@router.get("/Users/{user_id}")
async def get_user(user_id: str, request: Request):
    """SCIM GET /Users/{id} — get a specific user."""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not _verify_scim_token(token):
        raise HTTPException(status_code=401, detail="Invalid SCIM bearer token")

    from database import db
    user_data = db.get_user(user_id)
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")

    scim_users = db.scim_list_users()
    scim_entry = next((s for s in scim_users if s["user_id"] == user_id), None)
    external_id = scim_entry["external_id"] if scim_entry else user_id
    active = scim_entry["active"] if scim_entry else True

    resource = _scim_user_resource(user_id, external_id, bool(active),
                                    user_data.get("name", ""), user_data.get("email", ""))
    return JSONResponse(content=resource, media_type=SCIM_CONTENT_TYPE)


@router.put("/Users/{user_id}")
async def update_user(user_id: str, request: Request):
    """SCIM PUT /Users/{id} — update a user."""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not _verify_scim_token(token):
        raise HTTPException(status_code=401, detail="Invalid SCIM bearer token")

    body = await request.json()
    from database import db

    user_data = db.get_user(user_id)
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")

    active = body.get("active", True)
    db.scim_update_status(user_id, active)

    name = body.get("name", {}).get("formatted", user_data.get("name", ""))
    email = body.get("emails", [{}])[0].get("value", user_data.get("email", ""))

    # Update user profile
    conn = db._get_conn()
    conn.execute("UPDATE users SET name=?, email=? WHERE username=?", (name, email, user_id))
    conn.commit()

    resource = _scim_user_resource(user_id, body.get("externalId", user_id), active, name, email)
    return JSONResponse(content=resource, media_type=SCIM_CONTENT_TYPE)


@router.delete("/Users/{user_id}")
async def delete_user(user_id: str, request: Request):
    """SCIM DELETE /Users/{id} — deactivate a user."""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not _verify_scim_token(token):
        raise HTTPException(status_code=401, detail="Invalid SCIM bearer token")

    from database import db
    user_data = db.get_user(user_id)
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")

    db.scim_update_status(user_id, False)
    return JSONResponse(content={}, status_code=204)


@router.get("/Groups")
async def list_groups(request: Request):
    """SCIM GET /Groups — stub for IdP compatibility."""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not _verify_scim_token(token):
        raise HTTPException(status_code=401, detail="Invalid SCIM bearer token")

    return JSONResponse(content=_scim_list_response([]), media_type=SCIM_CONTENT_TYPE)


@router.post("/Users/.search")
async def search_users(request: Request):
    """SCIM POST /Users/.search — search users with filter."""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not _verify_scim_token(token):
        raise HTTPException(status_code=401, detail="Invalid SCIM bearer token")

    from database import db
    scim_users = db.scim_list_users()
    resources = []
    for su in scim_users:
        user_data = db.get_user(su["user_id"])
        if user_data:
            resources.append(_scim_user_resource(
                user_id=su["user_id"],
                external_id=su["external_id"],
                active=bool(su["active"]),
                name=user_data.get("name", ""),
                email=user_data.get("email", ""),
            ))
    return JSONResponse(content=_scim_list_response(resources), media_type=SCIM_CONTENT_TYPE)


def _verify_scim_token(token: str) -> bool:
    """Verify SCIM bearer token. Uses the same JWT secret as the main app.

    In production, a dedicated SCIM token should be issued per tenant.
    """
    if not token:
        return False

    import os
    scim_token = os.environ.get("BIZSIMAI_SCIM_TOKEN")
    if scim_token and hmac.compare_digest(token, scim_token):
        return True

    # Fall back to JWT verification (owner role only)
    from auth import _verify_token
    payload = _verify_token(token)
    return payload is not None and payload.get("role") == "owner"
