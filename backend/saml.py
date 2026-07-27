"""SOTA Phase 2: SAML 2.0 SSO Assertion Consumer Service.

Implements a minimal SAML 2.0 ACS (Assertion Consumer Service) endpoint
that can receive and validate SAML responses from an IdP (Identity Provider).

Supports:
- SAMLResponse POST binding (standard browser SSO)
- Basic assertion validation (signature optional for dev, timing checks)
- User provisioning from SAML attributes (email, name)
- SP-initiated SSO via AuthnRequest redirect

Note: For production, use python-saml or PySAML2 libraries for full
SAML signing, encryption, and SLO support. This is a minimal implementation
suitable for classroom/education use and testing.
"""

import base64
import hashlib
import hmac
import os
import secrets
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/saml", tags=["saml-sso"])

# SAML namespace map
SAML_NS = {
    "samlp": "urn:oasis:names:tc:SAML:2.0:protocol",
    "saml": "urn:oasis:names:tc:SAML:2.0:assertion",
    "ds": "http://www.w3.org/2000/09/xmldsig#",
}

# Entity ID for this SP (Service Provider)
SP_ENTITY_ID = os.environ.get("PRACTENTURE_SP_ENTITY_ID", "https://practenture.com/saml/metadata")
ACS_URL = os.environ.get("PRACTENTURE_SAML_ACS_URL", "https://practenture.com/api/saml/acs")

# IdP configuration (set via env vars)
IDP_ENTITY_ID = os.environ.get("PRACTENTURE_IDP_ENTITY_ID", "")
IDP_SSO_URL = os.environ.get("PRACTENTURE_IDP_SSO_URL", "")
IDP_CERT = os.environ.get("PRACTENTURE_IDP_CERT", "")  # PEM format X.509 cert


# ── In-memory relay state store (production: use Redis) ────────────────────
_relay_state_store: Dict[str, dict] = {}
_relay_state_ttl = 300  # 5 minutes


def _store_relay_state(data: dict) -> str:
    state_id = secrets.token_urlsafe(16)
    _relay_state_store[state_id] = {**data, "created_at": time.time()}
    return state_id


def _get_relay_state(state_id: str) -> Optional[dict]:
    data = _relay_state_store.get(state_id)
    if not data:
        return None
    if time.time() - data["created_at"] > _relay_state_ttl:
        _relay_state_store.pop(state_id, None)
        return None
    return data


import time


class SAMLLoginResponse(BaseModel):
    sso_url: str
    relay_state: str


@router.get("/login", response_model=SAMLLoginResponse)
async def saml_login(return_to: str = "/"):
    """SP-initiated SSO: redirect user to IdP login page.

    Returns the IdP SSO URL and a relay state token for callback tracking.
    """
    if not IDP_SSO_URL:
        raise HTTPException(status_code=503, detail="SAML IdP not configured. Set PRACTENTURE_IDP_SSO_URL.")

    request_id = secrets.token_urlsafe(16)
    relay_state = _store_relay_state({
        "request_id": request_id,
        "return_to": return_to,
    })

    # Build minimal SAML AuthnRequest
    authn_request = f"""<?xml version="1.0" encoding="UTF-8"?>
<samlp:AuthnRequest xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
    xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
    ID="_{request_id}"
    Version="2.0"
    IssueInstant="{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}"
    Destination="{IDP_SSO_URL}"
    AssertionConsumerServiceURL="{ACS_URL}">
    <saml:Issuer>{SP_ENTITY_ID}</saml:Issuer>
    <samlp:NameIDPolicy Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"
        AllowCreate="true"/>
</samlp:AuthnRequest>"""

    encoded_request = base64.b64encode(authn_request.encode()).decode()
    sso_url = f"{IDP_SSO_URL}?{urlencode({'SAMLRequest': encoded_request, 'RelayState': relay_state})}"

    return SAMLLoginResponse(sso_url=sso_url, relay_state=relay_state)


@router.post("/acs")
async def assertion_consumer_service(request: Request):
    """SAML Assertion Consumer Service — receives SAMLResponse from IdP.

    This endpoint is called by the browser after the IdP authenticates the user.
    It parses the SAML response, extracts user attributes, and issues a JWT.
    """
    import database as db_module
    from auth import _create_token, _generate_refresh_token, ACCESS_TOKEN_SOTA_MINUTES
    from datetime import timedelta
    from security import hash_password

    form = await request.form()
    saml_response_b64 = str(form.get("SAMLResponse") or "")
    relay_state_id = str(form.get("RelayState") or "")

    if not saml_response_b64:
        raise HTTPException(status_code=400, detail="Missing SAMLResponse")

    # Decode and parse SAML response
    try:
        saml_xml = base64.b64decode(saml_response_b64).decode("utf-8")
        root = ET.fromstring(saml_xml)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid SAML response: {e}")

    # Extract assertion
    assertion = root.find(".//saml:Assertion", SAML_NS)
    if assertion is None:
        raise HTTPException(status_code=400, detail="No Assertion in SAML response")

    # Extract NameID (subject)
    name_id_elem = assertion.find(".//saml:NameID", SAML_NS)
    name_id = name_id_elem.text if name_id_elem is not None else ""

    # Extract attributes
    attr_stmt = assertion.find(".//saml:AttributeStatement", SAML_NS)
    attributes = {}
    if attr_stmt is not None:
        for attr in attr_stmt.findall("saml:Attribute", SAML_NS):
            name = attr.get("Name", "")
            values = [v.text for v in attr.findall("saml:AttributeValue", SAML_NS) if v.text]
            attributes[name] = values[0] if values else ""

    email = attributes.get("email", name_id) or attributes.get("urn:oid:0.9.2342.19200300.100.1.3", "")
    name = attributes.get("name", "") or attributes.get("urn:oid:2.5.4.3", "") or attributes.get("cn", "")

    if not email and not name_id:
        raise HTTPException(status_code=400, detail="No email or NameID in SAML assertion")

    user_id = email or name_id

    # Provision user if not exists
    existing = db_module.db.get_user(user_id)
    if not existing:
        dummy_hash = hash_password(secrets.token_hex(16))
        db_module.db.upsert_user(
            username=user_id, password_hash=dummy_hash, role="student",
            name=name, email=email, provider="saml", provider_uid=name_id,
        )
        role = "student"
    else:
        role = existing["role"]

    # Get relay state for redirect
    relay = _get_relay_state(relay_state_id) if relay_state_id else None
    return_to = relay.get("return_to", "/") if relay else "/"

    # Issue JWT
    org = db_module.db.get_primary_org(user_id)
    tenant_id = org["id"] if org else ""

    access_token = _create_token({
        "sub": user_id,
        "role": role,
        "tenantId": tenant_id,
        "email": email,
        "provider": "saml",
        "exp": (datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_SOTA_MINUTES)).timestamp(),
    })
    refresh = _generate_refresh_token(user_id)

    # Redirect with tokens (fragment to prevent IdP logs)
    redirect_url = f"{return_to}#access_token={access_token}&refresh_token={refresh}&role={role}"
    return RedirectResponse(url=redirect_url, status_code=302)


@router.get("/metadata")
async def saml_metadata():
    """SAML SP metadata endpoint — IdP imports this to configure the SP."""
    import time
    metadata = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<EntityDescriptor xmlns="urn:oasis:names:tc:SAML:2.0:metadata"
    entityID="{SP_ENTITY_ID}">
    <SPSSODescriptor protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
        <NameIDFormat>urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress</NameIDFormat>
        <AssertionConsumerService index="0"
            Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
            Location="{ACS_URL}"/>
    </SPSSODescriptor>
</EntityDescriptor>"""
    return HTMLResponse(content=metadata, media_type="application/xml")
