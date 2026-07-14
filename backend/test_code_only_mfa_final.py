"""Code-only auth permutation tests — verifies MFA code fix (C1-C4).

Tests all three code-only flows against EC2:
1. Professor login (password) — with and without MFA
2. Student login (password) — with and without MFA  
3. Student registration + auto-login
4. Full MFA flow (setup → enable → login with code)

Usage: python test_code_only_mfa_final.py [BASE_URL]
"""

import sys
import requests
import time

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://18.215.180.58"

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


def api(method, path, body=None, token=None):
    url = f"{BASE_URL}{path}"
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    try:
        if method == "GET":
            r = requests.get(url, headers=h, timeout=10)
        elif method == "POST":
            r = requests.post(url, json=body, headers=h, timeout=10)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {"_text": r.text}
    except Exception as e:
        return 0, {"_error": str(e)}


def login(provider, username=None, password=None, id_token=None, mfa_code=None):
    body = {"provider": provider}
    if username:
        body["username"] = username
    if password:
        body["password"] = password
    if id_token:
        body["id_token"] = id_token
    if mfa_code:
        body["mfa_code"] = mfa_code
    status, body = api("POST", "/api/auth/login", body)
    return status, body


# ── Get owner password from EC2 ──
owner_password = None
try:
    import subprocess
    result = subprocess.run(
        ["ssh", "-i", "~/.ssh/bizsimai", "-o", "StrictHostKeyChecking=no",
         "ec2-user@18.215.180.58",
         "docker exec bizsim-backend env | grep BIZSIMAI_OWNER_PASSWORD"],
        capture_output=True, text=True, timeout=10
    )
    for line in result.stdout.strip().split("\n"):
        if "=" in line:
            owner_password = line.split("=", 1)[1]
            print(f"✅ Found owner password: {owner_password[:4]}****")
            break
except Exception as e:
    print(f"⚠️ Could not fetch owner password: {e}")

if not owner_password:
    print("❌ FATAL: Cannot connect to EC2. Aborting.")
    sys.exit(1)


print(f"\n{'='*70}")
print(f"  Code-Only Auth Permutation Tests (FINAL)")
print(f"  Target: {BASE_URL}")
print(f"{'='*70}\n")


# ── Test 1: Professor login WITHOUT MFA (baseline) ──
print("┌─ Test 1: Professor Login (no MFA, baseline) ───────────────")
prof_password = "bizsimai2026"
status, body = login("password", username="professor", password=prof_password)
check("T1", "Login returns 200", status == 200, f"got {status}, body: {body}")
check("T1", "Has accessToken", status == 200 and bool(body.get("accessToken")), f"body: {body}")
check("T1", "Role is professor", body.get("role") == "professor", f"got {body.get('role')}")
check("T1", "mfaRequired field present and false", body.get("mfaRequired") == False, f"got {body.get('mfaRequired')}, keys: {list(body.keys()) if isinstance(body, dict) else body}")
prof_token = body.get("accessToken") if status == 200 else None
print()


# ── Test 2: MFA code field accepted (no FastAPI 422) ──
print("┌─ Test 2: Backend accepts mfa_code field (no FastAPI 422) ──")
status, body = login("password", username="professor", password=prof_password, mfa_code="123456")
check("T2", "No 422 validation error", status != 422, f"got {status} — if 422, mfa_code field is rejected by FastAPI")
check("T2", "Returns 200 (MFA disabled, code ignored)", status == 200, f"got {status} — correct because professor MFA is disabled")
check("T2", "mfaRequired in response", "mfaRequired" in body, f"keys: {list(body.keys()) if isinstance(body, dict) else body}")
print()


# ── Test 3: Student login (baseline) ──
print("┌─ Test 3: Student Login (no MFA, baseline) ─────────────────")
# Use unique student ID to avoid 409 from previous runs
test_student = f"test_mfa_{int(time.time())}"
reg_status, reg_body = api("POST", "/api/auth/register", {
    "student_id": test_student,
    "name": f"Test MFA Student {int(time.time())}",
    "password": "TestPass123!"
})
check("T3", "Student registration 201 or 409 (exists)", reg_status in (201, 409), f"got {reg_status}")

status, body = login("password", username=test_student, password="TestPass123!")
check("T3", "Student login returns 200", status == 200, f"got {status}")
check("T3", "Role is student", body.get("role") == "student", f"got {body.get('role')}")
check("T3", "mfaRequired field present and false", body.get("mfaRequired") == False, f"got {body.get('mfaRequired')}")
student_token = body.get("accessToken") if status == 200 else None
print()


# ── Test 4: Full MFA flow — setup, enable, login with code ──
print("┌─ Test 4: Full MFA Flow (setup → enable → login with code) ─")

# Step 4a: Setup MFA for test student
mfa_setup_status, mfa_setup_body = api("POST", "/api/auth/mfa/setup", token=student_token)
check("T4a", "MFA setup returns 200 with secret", mfa_setup_status == 200 and "secret" in mfa_setup_body,
      f"got {mfa_setup_status}, body keys: {list(mfa_setup_body.keys()) if isinstance(mfa_setup_body, dict) else mfa_setup_body}")
mfa_secret = mfa_setup_body.get("secret", "") if isinstance(mfa_setup_body, dict) else ""
backup_codes = mfa_setup_body.get("backupCodes", []) if isinstance(mfa_setup_body, dict) else []
check("T4a", "Backup codes returned", len(backup_codes) > 0, f"got {len(backup_codes)} codes")

# Step 4b: Enable MFA with a dummy code (backend accepts any 6-digit for setup)
# The backend's MFA enable endpoint validates the code against the secret
mfa_enable_status, mfa_enable_body = api("POST", "/api/auth/mfa/enable", {
    "code": "123456"  # Dummy code — backend will validate against secret
}, token=student_token)

# Check if MFA is now enabled
mfa_status, mfa_status_body = api("GET", "/api/auth/mfa/status", token=student_token)
check("T4b", "MFA status check works", mfa_status == 200, f"got {mfa_status}, body: {mfa_status_body}")
mfa_enabled = mfa_status_body.get("enabled", False) if isinstance(mfa_status_body, dict) else False
check("T4b", "MFA enabled after setup", mfa_enabled, f"enabled={mfa_enabled}, body: {mfa_status_body}")

if mfa_enabled:
    # Step 4c: Login WITHOUT MFA code — should get mfaRequired=true
    status, body = login("password", username=test_student, password="TestPass123!")
    check("T4c", "Login without MFA code returns mfaRequired=true", 
          body.get("mfaRequired") == True, f"got {body.get('mfaRequired')}, body: {body}")
    check("T4c", "accessToken is empty when MFA required", 
          body.get("accessToken") == "", f"got: {body.get('accessToken')}")
    
    # Step 4d: Login WITH correct MFA code — should succeed
    # We need a real TOTP code. Use the backup code or generate one.
    # The backend uses pyotp — we can use the secret to generate a valid code
    import base64, struct, time as _time
    
    # Decode the secret (base32)
    try:
        import pyotp
        totp = pyotp.TOTP(mfa_secret)
        valid_code = totp.now()
        
        status, body = login("password", username=test_student, password="TestPass123!", mfa_code=valid_code)
        check("T4d", "Login WITH valid MFA code returns 200", status == 200, f"got {status}, body: {body}")
        check("T4d", "Has accessToken after MFA verification", status == 200 and bool(body.get("accessToken")), f"body: {body}")
        check("T4d", "Role is student after MFA login", body.get("role") == "student", f"got {body.get('role')}")
    except ImportError:
        check("T4d", "Skipped (pyotp not available for TOTP generation)", False, "Cannot generate valid TOTP code")
else:
    check("T4c", "Skipped (MFA not enabled)", False, f"MFA status: {mfa_status_body}")
    check("T4d", "Skipped (MFA not enabled)", False, f"MFA status: {mfa_status_body}")

print()


# ── Test 5: MFA code validation — wrong code rejected ──
print("┌─ Test 5: MFA Code Validation (wrong code rejected) ───────")
if mfa_enabled and student_token:
    status, body = login("password", username=test_student, password="TestPass123!", mfa_code="000000")
    check("T5", "Wrong MFA code returns 401", status == 401, f"got {status}")
    check("T5", "Error message says Invalid MFA", status == 401 and "Invalid MFA" in body.get("detail", ""), f"detail: {body}")
else:
    check("T5", "Skipped (MFA not enabled)", False, f"MFA status: {mfa_status_body if 'mfa_status_body' in dir() else 'unknown'}")
print()


# ── Test 6: Professor code redemption flow ──
print("┌─ Test 6: Professor Code Redemption Flow ───────────────────")
# Check what professor endpoints exist
prof_endpoints_status, prof_endpoints_body = api("GET", "/api/professor/", token=prof_token)
check("T6", "Professor endpoints accessible", prof_endpoints_status in (200, 405), f"got {prof_endpoints_status}, body: {prof_endpoints_body}")

# Try to find the correct endpoint for creating professor codes
for path in ["/api/professor/code", "/api/professor/create-code", "/api/admin/code"]:
    status, body = api("POST", path, {"university_name": "Test University"}, token=prof_token)
    if status == 200:
        check("T6", f"Code creation works at {path}", True, f"status={status}")
        code = body.get("code", "")
        check("T6", "Code returned", bool(code), f"code: {code}")
        break
else:
    check("T6", "Code creation endpoint not found (404 on all paths)", False, 
          "Tried /api/professor/code, /api/professor/create-code, /api/admin/code")
print()


# ── Summary ──
print(f"\n{'='*70}")
print(f"  CODE-ONLY AUTH PERMUTATION SUMMARY (FINAL)")
print(f"{'='*70}")
print(f"  TOTAL: {passed} passed, {failed} failed")
if failures:
    print(f"\n  FAILURES:")
    for f in failures:
        print(f"    ❌ {f}")
else:
    print(f"\n  ✅ ALL TESTS PASSED — Code-only auth flow is working correctly.")
print(f"{'='*70}")
