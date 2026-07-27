"""Code-only auth permutation tests — verifies MFA code fix (C1-C4).

Tests all three code-only flows against EC2:
1. Professor login (password) — with and without MFA
2. Student login (password) — with and without MFA  
3. Student registration + auto-login
4. Professor code redemption flow

Usage: python test_code_only_mfa.py [BASE_URL]
"""
import os

import sys
import requests

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
        ["ssh", "-i", "~/.ssh/practenture", "-o", "StrictHostKeyChecking=no",
         "ec2-user@18.215.180.58",
         "docker exec practenture-backend env | grep PRACTENTURE_OWNER_PASSWORD"],
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
print(f"  Code-Only Auth Permutation Tests")
print(f"  Target: {BASE_URL}")
print(f"{'='*70}\n")


# ── Test 1: Professor login WITHOUT MFA (baseline) ──
print("┌─ Test 1: Professor Login (no MFA, baseline) ───────────────")
prof_password = os.environ.get("PRACTENTURE_PROFESSOR_PASSWORD", "practenture2026")  # Default professor password from env
status, body = login("password", username="professor", password=prof_password)
check("T1", "Login returns 200", status == 200, f"got {status}, body: {body}")
check("T1", "Has accessToken", status == 200 and bool(body.get("accessToken")), f"body: {body}")
check("T1", "Role is professor", body.get("role") == "professor", f"got {body.get('role')}")
check("T1", "mfaRequired is false or absent (MFA disabled)", body.get("mfaRequired") == False or "mfaRequired" not in body, f"got {body.get('mfaRequired')}, keys: {list(body.keys()) if isinstance(body, dict) else body}")
prof_token = body.get("accessToken") if status == 200 else None
print()


# ── Test 2: Professor login WITH wrong MFA code (should fail) ──
print("┌─ Test 2: Professor Login with wrong MFA code ──────────────")
status, body = login("password", username="professor", password=prof_password, mfa_code="000000")
check("T2", "Login with wrong MFA returns 401", status == 401, f"got {status}")
check("T2", "Error message present", status == 401 and ("Invalid MFA" in body.get("detail", "") or "Wrong username" in body.get("detail", "")), f"detail: {body}")
print()


# ── Test 3: Student login WITHOUT MFA (baseline) ──
print("┌─ Test 3: Student Login (no MFA, baseline) ─────────────────")
# First register a test student
reg_status, reg_body = api("POST", "/api/auth/register", {
    "student_id": "test_student_mfa",
    "name": "Test MFA Student",
    "password": "TestPass123!"
})
check("T3", "Student registration 201", reg_status == 201, f"got {reg_status}, body: {reg_body}")

status, body = login("password", username="test_student_mfa", password="TestPass123!")
check("T3", "Student login returns 200", status == 200, f"got {status}")
check("T3", "Role is student", body.get("role") == "student", f"got {body.get('role')}")
check("T3", "mfaRequired is false", body.get("mfaRequired") == False, f"got {body.get('mfaRequired')}")
print()


# ── Test 4: Student registration + auto-login flow ──
print("┌─ Test 4: Student Registration + Auto-Login ────────────────")
reg_status, reg_body = api("POST", "/api/auth/register", {
    "student_id": "test_student_auto",
    "name": "Test Auto Student",
    "password": "AutoPass123!"
})
check("T4", "Registration 201", reg_status == 201, f"got {reg_status}")

# Auto-login with same credentials
status, body = login("password", username="test_student_auto", password="AutoPass123!")
check("T4", "Auto-login returns 200", status == 200, f"got {status}")
check("T4", "Has refreshToken", status == 200 and bool(body.get("refreshToken")), f"body: {body}")
check("T4", "mfaRequired is false", body.get("mfaRequired") == False, f"got {body.get('mfaRequired')}")
print()


# ── Test 5: MFA enabled user — login without code returns mfaRequired ──
print("┌─ Test 5: MFA Required Flow (login without code) ───────────")
# Enable MFA for test student
if prof_token:
    mfa_setup_status, mfa_setup_body = api("POST", "/api/auth/mfa/setup", token=prof_token)
    check("T5", "MFA setup returns secret", mfa_setup_status == 200 and "secret" in mfa_setup_body,
          f"got {mfa_setup_status}, body keys: {list(mfa_setup_body.keys()) if isinstance(mfa_setup_body, dict) else mfa_setup_body}")
    
    # Now login as professor WITHOUT MFA code — should get mfaRequired=true
    status, body = login("password", username="professor", password=owner_password)
    check("T5", "Login without MFA code returns mfaRequired=true", 
          body.get("mfaRequired") == True, f"got {body.get('mfaRequired')}, body: {body}")
    check("T5", "accessToken is empty when MFA required", 
          body.get("accessToken") == "", f"got: {body.get('accessToken')}")
else:
    check("T5", "Skipped (no prof token)", False, "prof_token was None")
print()


# ── Test 6: Verify mfa_code field is accepted by backend (no 422) ──
print("┌─ Test 6: Backend accepts mfa_code field (no FastAPI 422) ──")
status, body = login("password", username="professor", password=owner_password, mfa_code="123456")
check("T6", "No 422 validation error", status != 422, f"got {status} — if 422, mfa_code field is rejected by FastAPI")
check("T6", "Returns 401 (wrong MFA) not 422", status == 401, f"got {status}, detail: {body.get('detail')}")
print()


# ── Test 7: Professor code redemption flow ──
print("┌─ Test 7: Professor Code Redemption Flow ───────────────────")
# Create a professor code first (using owner token)
prof_status, prof_body = api("POST", "/api/professor/create-code", {
    "university_name": "Test University"
}, token=prof_token)
if prof_status == 200 and "code" in prof_body:
    code = prof_body["code"]
    check("T7", "Professor code created", True, f"code: {code}")
    
    # Register new student
    api("POST", "/api/auth/register", {
        "student_id": "newprof_test",
        "name": "New Prof Test",
        "password": "ProfPass123!"
    })
    
    # Login as new student
    status, body = login("password", username="newprof_test", password="ProfPass123!")
    check("T7", "New student login returns 200", status == 200, f"got {status}")
    
    # Redeem professor code
    redeem_status, redeem_body = api("POST", "/api/professor/redeem", {
        "code": code
    }, token=body.get("accessToken"))
    check("T7", "Code redemption returns 200", redeem_status == 200, f"got {redeem_status}, body: {redeem_body}")
    check("T7", "Role upgraded to professor", redeem_body.get("role") == "professor", f"got {redeem_body.get('role')}")
    check("T7", "Redemption returns new accessToken", bool(redeem_body.get("accessToken")), f"body: {redeem_body}")
else:
    check("T7", "Skipped (code creation failed)", False, f"status={prof_status}, body={prof_body}")
print()


# ── Summary ──
print(f"\n{'='*70}")
print(f"  CODE-ONLY AUTH PERMUTATION SUMMARY")
print(f"{'='*70}")
print(f"  TOTAL: {passed} passed, {failed} failed")
if failures:
    print(f"\n  FAILURES:")
    for f in failures:
        print(f"    ❌ {f}")
else:
    print(f"\n  ✅ ALL TESTS PASSED — Code-only auth flow is working correctly.")
print(f"{'='*70}")
