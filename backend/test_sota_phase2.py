"""SOTA Phase 2: Tests for Refresh Tokens, MFA/TOTP, SAML SSO, SCIM 2.0, PostgreSQL RLS.

Tests are designed to run against the live EC2 server or local instance.
Usage: python test_sota_phase2.py [BASE_URL] [OWNER_PASSWORD]
"""

import os
import sys
import json
import time
import base64
import hashlib
import hmac
import struct
import secrets
import requests

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://18.215.180.58"
OWNER_PASSWORD = sys.argv[2] if len(sys.argv) > 2 else None

if not OWNER_PASSWORD:
    # Try to fetch from EC2
    try:
        import subprocess
        result = subprocess.run(
            ["ssh", "-i", os.path.expanduser("~/.ssh/bizsimai"),
             "-o", "StrictHostKeyChecking=no",
             "ec2-user@18.215.180.58",
             "docker exec bizsim-backend env | grep BIZSIMAI_OWNER_PASSWORD"],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.strip().split("\n"):
            if "=" in line:
                OWNER_PASSWORD = line.split("=", 1)[1]
                print(f"  ✅ Found owner password: {OWNER_PASSWORD[:4]}****")
                break
    except Exception:
        pass

if not OWNER_PASSWORD:
    OWNER_PASSWORD = "test-owner-password"


passed = 0
failed = 0
failures = []


def check(group, name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        failures.append(f"[{group}] {name}: {detail}")
        print(f"  ❌ {name} — {detail}")


def api(method, path, body=None, token=None, headers=None):
    url = f"{BASE_URL}{path}"
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    if headers:
        h.update(headers)
    try:
        if method == "GET":
            r = requests.get(url, headers=h, timeout=10)
        elif method == "POST":
            r = requests.post(url, json=body, headers=h, timeout=10)
        elif method == "PUT":
            r = requests.put(url, json=body, headers=h, timeout=10)
        elif method == "DELETE":
            r = requests.delete(url, headers=h, timeout=10)
        elif method == "PATCH":
            r = requests.patch(url, json=body, headers=h, timeout=10)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {"_text": r.text}
    except Exception as e:
        return 0, {"_error": str(e)}


def login(provider, username=None, password=None, id_token=None):
    body = {"provider": provider}
    if username:
        body["username"] = username
    if password:
        body["password"] = password
    if id_token:
        body["id_token"] = id_token
    status, body = api("POST", "/api/auth/login", body)
    if status == 200:
        return body.get("accessToken"), body.get("role"), body.get("mustChangePassword"), body.get("refreshToken")
    return None, None, None, None


def register_student(student_id, name, password):
    status, _ = api("POST", "/api/auth/register", {
        "student_id": student_id, "name": name, "password": password
    })
    return status == 201


def generate_totp_code(secret, offset=0):
    """Generate a TOTP code for testing (same algorithm as mfa.py)."""
    padding = 8 - len(secret) % 8
    if padding != 8:
        secret = secret + "=" * padding
    key = base64.b32decode(secret, casefold=True)
    step = (int(time.time()) // 30) + offset
    msg = struct.pack(">Q", step)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    offset_byte = h[-1] & 0x0F
    truncated = struct.unpack(">I", h[offset_byte:offset_byte + 4])[0] & 0x7FFFFFFF
    return str(truncated)[-6:].zfill(6)


# ═══════════════════════════════════════════════════════════════════════════════
# TEST SUITE
# ═══════════════════════════════════════════════════════════════════════════════

def test_refresh_tokens():
    """Group K: Refresh Token Rotation."""
    print("\n┌─ K. Refresh Token Rotation ───────────────────────────────────")
    
    # K1: Login returns refresh token
    token, role, _, refresh = login("password", "owner", OWNER_PASSWORD)
    check("K", "K1. Login returns refreshToken", refresh is not None, f"refresh={refresh}")
    
    if not refresh:
        print("└─ Group K: skipped (no refresh token)\n")
        return
    
    # K2: Refresh endpoint returns new access + refresh
    status, body = api("POST", "/api/auth/refresh", {"refreshToken": refresh})
    check("K", "K2. Refresh returns new tokens", status == 200 and "accessToken" in body and "refreshToken" in body, f"status={status}")
    
    if status != 200:
        print("└─ Group K: skipped (refresh failed)\n")
        return
    
    new_access = body.get("accessToken")
    new_refresh = body.get("refreshToken")
    
    # K3: New access token works
    status, body = api("POST", "/api/auth/verify", token=new_access)
    check("K", "K3. New access token works", status == 200, f"status={status}")
    
    # K4: Old refresh token is revoked (rotation)
    status, body = api("POST", "/api/auth/refresh", {"refreshToken": refresh})
    check("K", "K4. Old refresh token revoked (rotation)", status == 401, f"status={status}")
    
    # K5: New refresh token works
    status, body = api("POST", "/api/auth/refresh", {"refreshToken": new_refresh})
    check("K", "K5. New refresh token works", status == 200, f"status={status}")
    
    # K6: Invalid refresh token rejected
    status, body = api("POST", "/api/auth/refresh", {"refreshToken": "invalid-token-12345"})
    check("K", "K6. Invalid refresh token rejected", status == 401, f"status={status}")
    
    print(f"└─ Group K: {passed - sum(1 for f in failures if f.startswith('[K]'))} pass, {sum(1 for f in failures if f.startswith('[K]'))} fail\n")


def test_mfa_totp():
    """Group L: MFA/TOTP."""
    print("\n┌─ L. MFA/TOTP ────────────────────────────────────────────────")
    
    # Login as owner
    token, role, _, _ = login("password", "owner", OWNER_PASSWORD)
    if not token:
        print("└─ Group L: skipped (no owner token)\n")
        return
    
    # L1: MFA status (initially disabled)
    status, body = api("GET", "/api/auth/mfa/status", token=token)
    check("L", "L1. MFA status endpoint", status == 200 and "enabled" in body, f"status={status}")
    check("L", "L1b. MFA initially disabled", body.get("enabled") == False, f"body={body}")
    
    # L2: Setup MFA — returns secret + QR URL + backup codes
    status, body = api("POST", "/api/auth/mfa/setup", token=token)
    check("L", "L2. MFA setup returns secret", status == 200 and "secret" in body, f"status={status}")
    
    if status != 200:
        print("└─ Group L: skipped (setup failed)\n")
        return
    
    secret = body["secret"]
    qr_url = body.get("qr_code_url", "")
    backup_codes = body.get("backup_codes", [])
    
    check("L", "L2b. QR code URL contains otpauth", "otpauth" in qr_url, f"qr={qr_url[:50]}")
    check("L", "L2c. Backup codes returned", len(backup_codes) == 10, f"count={len(backup_codes)}")
    
    # L3: Verify with invalid TOTP code
    status, body = api("POST", "/api/auth/mfa/verify", {"code": "000000"}, token=token)
    check("L", "L3. Invalid TOTP code rejected", status == 400, f"status={status}")
    
    # L4: Verify with valid TOTP code
    valid_code = generate_totp_code(secret)
    status, body = api("POST", "/api/auth/mfa/verify", {"code": valid_code}, token=token)
    check("L", "L4. Valid TOTP code enables MFA", status == 200 and body.get("status") == "enabled", f"status={status}, body={body}")
    
    # L5: MFA status now enabled
    status, body = api("GET", "/api/auth/mfa/status", token=token)
    check("L", "L5. MFA status now enabled", body.get("enabled") == True, f"body={body}")
    
    # L6: Disable MFA
    status, body = api("POST", "/api/auth/mfa/disable", {}, token=token)
    check("L", "L6. MFA disabled", status == 200 and body.get("status") == "disabled", f"status={status}")
    
    # L7: MFA status disabled again
    status, body = api("GET", "/api/auth/mfa/status", token=token)
    check("L", "L7. MFA status disabled after disable", body.get("enabled") == False, f"body={body}")
    
    # L8: MFA setup requires auth (no token)
    status, body = api("POST", "/api/auth/mfa/setup")
    check("L", "L8. MFA setup requires auth", status in (401, 403), f"status={status}")
    
    print(f"└─ Group L: done\n")


def test_saml_sso():
    """Group M: SAML SSO."""
    print("\n┌─ M. SAML SSO ────────────────────────────────────────────────")
    
    # M1: SAML metadata endpoint
    status, body = api("GET", "/api/saml/metadata")
    check("M", "M1. SAML metadata endpoint", status == 200, f"status={status}")
    
    # M2: SAML login without IdP configured
    status, body = api("GET", "/api/saml/login")
    # Will be 503 if not configured, which is correct behavior
    check("M", "M2. SAML login endpoint responds", status in (200, 503), f"status={status}")
    
    # M3: SAML ACS without SAMLResponse
    status, body = api("POST", "/api/saml/acs", {})
    check("M", "M3. ACS rejects empty request", status == 400 or status == 422, f"status={status}")
    
    print(f"└─ Group M: done\n")


def test_scim():
    """Group N: SCIM 2.0 User Provisioning."""
    print("\n┌─ N. SCIM 2.0 ────────────────────────────────────────────────")
    
    # Login as owner for SCIM operations
    token, role, _, _ = login("password", "owner", OWNER_PASSWORD)
    if not token:
        print("└─ Group N: skipped (no owner token)\n")
        return
    
    scim_headers = {"Content-Type": "application/scim+json", "Authorization": f"Bearer {token}"}
    
    # N1: List users (initial — may be empty)
    status, body = api("GET", "/api/scim/v2/Users", headers=scim_headers)
    check("N", "N1. SCIM GET /Users", status == 200 and "Resources" in body, f"status={status}")
    
    # N2: Create a SCIM user
    test_user_id = f"scim_test_{int(time.time())}"
    status, body = api("POST", "/api/scim/v2/Users", {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "userName": test_user_id,
        "externalId": f"ext_{test_user_id}",
        "name": {"formatted": "SCIM Test User"},
        "emails": [{"value": f"{test_user_id}@test.edu", "primary": True}],
        "active": True,
    }, headers=scim_headers)
    check("N", "N2. SCIM POST /Users creates user", status == 201 and "id" in body, f"status={status}")
    
    # N3: Get the created user
    status, body = api("GET", f"/api/scim/v2/Users/{test_user_id}", headers=scim_headers)
    check("N", "N3. SCIM GET /Users/{id}", status == 200 and body.get("userName") == test_user_id, f"status={status}")
    
    # N4: Update the user
    status, body = api("PUT", f"/api/scim/v2/Users/{test_user_id}", {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "userName": test_user_id,
        "name": {"formatted": "Updated SCIM User"},
        "emails": [{"value": f"{test_user_id}@updated.edu", "primary": True}],
        "active": True,
    }, headers=scim_headers)
    check("N", "N4. SCIM PUT /Users/{id} updates", status == 200 and "Updated" in body.get("name", {}).get("formatted", ""), f"status={status}")
    
    # N5: Delete (deactivate) the user
    status, body = api("DELETE", f"/api/scim/v2/Users/{test_user_id}", headers=scim_headers)
    check("N", "N5. SCIM DELETE /Users/{id} deactivates", status == 204, f"status={status}")
    
    # N6: SCIM without auth token
    status, body = api("GET", "/api/scim/v2/Users", headers={"Content-Type": "application/scim+json"})
    check("N", "N6. SCIM without auth rejected", status == 401, f"status={status}")
    
    # N7: SCIM Groups endpoint (stub)
    status, body = api("GET", "/api/scim/v2/Groups", headers=scim_headers)
    check("N", "N7. SCIM GET /Groups", status == 200 and "Resources" in body, f"status={status}")
    
    print(f"└─ Group N: done\n")


def test_postgres_rls():
    """Group O: PostgreSQL RLS Migration Script."""
    print("\n┌─ O. PostgreSQL RLS Migration ────────────────────────────────")
    
    # Check that the migration SQL file exists
    rls_file = os.path.join(os.path.dirname(__file__), "postgres_rls_migration.sql")
    check("O", "O1. postgres_rls_migration.sql exists", os.path.exists(rls_file), f"path={rls_file}")
    
    # Check content of the migration script
    if os.path.exists(rls_file):
        with open(rls_file) as f:
            rls_content = f.read()
        
        check("O", "O2. RLS enables ROW LEVEL SECURITY", "ENABLE ROW LEVEL SECURITY" in rls_content, "")
        check("O", "O3. RLS has FORCE ROW LEVEL SECURITY", "FORCE ROW LEVEL SECURITY" in rls_content, "")
        check("O", "O4. RLS creates sessions policy", "sessions_tenant_isolation" in rls_content, "")
        check("O", "O5. RLS creates classes policy", "classes_tenant_isolation" in rls_content, "")
        check("O", "O6. RLS creates refresh_tokens policy", "refresh_tokens_isolation" in rls_content, "")
        check("O", "O7. RLS has current_tenant_id function", "current_tenant_id" in rls_content, "")
        check("O", "O8. RLS has is_owner function", "is_owner" in rls_content, "")
        check("O", "O9. RLS creates all Phase 2 tables", all(t in rls_content for t in ["refresh_tokens", "mfa_secrets", "scim_users"]), "")
        check("O", "O10. RLS has app role", "bizsimai_app" in rls_content, "")
    else:
        for i in range(2, 11):
            check("O", f"O{i}. RLS content check", False, "file not found")
    
    print(f"└─ Group O: done\n")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 78)
    print("  BizSimAI SOTA Phase 2 Test Suite")
    print(f"  Target: {BASE_URL}")
    print("=" * 78)

    # Health check first
    status, _ = api("GET", "/api/health")
    if status != 200:
        print(f"\n  ❌ Server not reachable at {BASE_URL}")
        sys.exit(1)
    print(f"\n  ✅ Server healthy at {BASE_URL}")

    test_refresh_tokens()
    test_mfa_totp()
    test_saml_sso()
    test_scim()
    test_postgres_rls()

    print("=" * 78)
    print("  SOTA PHASE 2 TEST SUMMARY")
    print("=" * 78)
    print(f"  TOTAL: {passed} passed, {failed} failed")
    if failures:
        print(f"\n  FAILURE DETAILS:")
        for f in failures:
            print(f"  {f}")
    print("=" * 78)
    
    sys.exit(0 if failed == 0 else 1)
