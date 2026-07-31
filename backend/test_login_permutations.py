#!/usr/bin/env python3
"""
Practenture Login Permutation Tests
Tests all login/auth permutations for professor and student roles against live EC2 backend.
"""
import requests
import json
import time
import uuid
import sys

BASE_URL = "http://18.215.180.58"
TIMEOUT = 15

# Test credentials
PROF_USER = "professor"
PROF_PASS = "Prof@2026X"
STU_USER = "STU001"
STU_PASS = "Stu1@2026X"

results = []


def record(name, status, body, expected=None):
    """Record a test result."""
    body_str = str(body)
    if len(body_str) > 200:
        body_str = body_str[:200] + "..."
    passed = True
    if expected is not None:
        if isinstance(expected, (list, tuple)):
            passed = status in expected
        else:
            passed = status == expected
    results.append({
        "name": name,
        "status": status,
        "body": body_str,
        "passed": passed,
        "expected": expected,
    })
    status_str = f"{'PASS' if passed else 'FAIL'}" if expected else "INFO"
    print(f"  [{status_str}] {name}: HTTP {status} | {body_str}")


def login(username, password, provider="password", extra=None):
    """Perform login and return (status_code, response_json, raw_response)."""
    payload = {
        "username": username,
        "password": password,
        "provider": provider,
    }
    if extra:
        payload.update(extra)
    try:
        r = requests.post(f"{BASE_URL}/api/auth/login", json=payload, timeout=TIMEOUT)
        try:
            return r.status_code, r.json(), r
        except Exception:
            return r.status_code, r.text, r
    except Exception as e:
        return -1, str(e), None


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def main():
    print("=" * 80)
    print("Practenture Login Permutation Tests")
    print(f"Backend: {BASE_URL}")
    print("=" * 80)

    # ---- Health check ----
    print("\n[0] Health Check")
    try:
        r = requests.get(f"{BASE_URL}/api/health", timeout=TIMEOUT)
        record("Health check", r.status_code, r.text if r.status_code != 200 else "OK", 200)
    except Exception as e:
        print(f"  [FAIL] Backend not reachable: {e}")
        sys.exit(1)

    # ---- PROFESSOR TESTS ----
    print("\n" + "=" * 80)
    print("PROFESSOR LOGIN PERMUTATIONS")
    print("=" * 80)

    # 1. Professor correct login
    print("\n[P1] Professor login with correct password")
    status, body, raw = login(PROF_USER, PROF_PASS)
    record("Prof correct login", status, body, 200)
    prof_token = body.get("access_token") if isinstance(body, dict) else None
    prof_refresh = body.get("refresh_token") if isinstance(body, dict) else None
    print(f"  → token: {prof_token[:40]}..." if prof_token else "  → no token!")

    # 2. Professor wrong password
    print("\n[P2] Professor login with wrong password")
    status, body, raw = login(PROF_USER, "wrongpassword")
    record("Prof wrong password", status, body, 401)

    # 3. Professor missing provider
    print("\n[P3] Professor login with missing provider")
    payload = {"username": PROF_USER, "password": PROF_PASS}
    r = requests.post(f"{BASE_URL}/api/auth/login", json=payload, timeout=TIMEOUT)
    record("Prof missing provider", r.status_code, r.text, [400, 422])

    # 4. Professor wrong provider (apple)
    print("\n[P4] Professor login with wrong provider (apple)")
    status, body, raw = login(PROF_USER, PROF_PASS, provider="apple")
    record("Prof wrong provider=apple", status, body, [400, 401, 422])

    # 4b. Professor wrong provider (google)
    print("\n[P4b] Professor login with wrong provider (google)")
    status, body, raw = login(PROF_USER, PROF_PASS, provider="google")
    record("Prof wrong provider=google", status, body, [400, 401, 422])

    # 5. Professor empty username
    print("\n[P5] Professor login with empty username")
    status, body, raw = login("", PROF_PASS)
    record("Prof empty username", status, body, [400, 422])

    # 6. Professor empty password
    print("\n[P6] Professor login with empty password")
    status, body, raw = login(PROF_USER, "")
    record("Prof empty password", status, body, [400, 422])

    # 7. Professor login with extra fields
    print("\n[P7] Professor login with extra fields")
    status, body, raw = login(PROF_USER, PROF_PASS, extra={"extra_field": "hello", "foo": 123})
    record("Prof extra fields", status, body, 200)

    # 8. Professor token verification
    print("\n[P8] Professor token verification")
    if prof_token:
        r = requests.post(f"{BASE_URL}/api/auth/verify", headers=auth_header(prof_token), timeout=TIMEOUT)
        record("Prof verify token", r.status_code, r.text, 200)
    else:
        record("Prof verify token", 0, "No token available", 200)

    # 9. Professor-only check
    print("\n[P9] Professor-only check")
    if prof_token:
        r = requests.post(f"{BASE_URL}/api/auth/professor-only", headers=auth_header(prof_token), timeout=TIMEOUT)
        record("Prof professor-only check", r.status_code, r.text, 200)
    else:
        record("Prof professor-only check", 0, "No token available", 200)

    # 10. Professor refresh token flow
    print("\n[P10] Professor refresh token flow")
    if prof_refresh:
        r = requests.post(f"{BASE_URL}/api/auth/refresh", json={"refreshToken": prof_refresh}, timeout=TIMEOUT)
        record("Prof refresh token", r.status_code, r.text, 200)
    else:
        record("Prof refresh token", 0, "No refresh token available", 200)

    # 11. Professor change-password flow
    print("\n[P11] Professor change-password flow")
    if prof_token:
        r = requests.post(
            f"{BASE_URL}/api/professor/change-password",
            headers=auth_header(prof_token),
            json={"oldPassword": PROF_PASS, "newPassword": PROF_PASS},  # change to same
            timeout=TIMEOUT,
        )
        record("Prof change-password", r.status_code, r.text, [200, 204])
    else:
        record("Prof change-password", 0, "No token available", [200, 204])

    # 12. Professor redeem code flow
    print("\n[P12] Professor redeem code flow")
    if prof_token:
        r = requests.post(
            f"{BASE_URL}/api/professor/redeem",
            headers=auth_header(prof_token),
            json={"professorCode": "TESTCODE123"},
            timeout=TIMEOUT,
        )
        record("Prof redeem code", r.status_code, r.text, [200, 400, 404])
    else:
        record("Prof redeem code", 0, "No token available", [200, 400, 404])

    # ---- STUDENT TESTS ----
    print("\n" + "=" * 80)
    print("STUDENT LOGIN PERMUTATIONS")
    print("=" * 80)

    # 1. Student correct login
    print("\n[S1] Student login with correct password")
    status, body, raw = login(STU_USER, STU_PASS)
    record("Student correct login", status, body, 200)
    stu_token = body.get("access_token") if isinstance(body, dict) else None
    stu_refresh = body.get("refresh_token") if isinstance(body, dict) else None
    print(f"  → token: {stu_token[:40]}..." if stu_token else "  → no token!")

    # 2. Student wrong password
    print("\n[S2] Student login with wrong password")
    status, body, raw = login(STU_USER, "wrongpassword")
    record("Student wrong password", status, body, 401)

    # 3. Student missing provider
    print("\n[S3] Student login with missing provider")
    payload = {"username": STU_USER, "password": STU_PASS}
    r = requests.post(f"{BASE_URL}/api/auth/login", json=payload, timeout=TIMEOUT)
    record("Student missing provider", r.status_code, r.text, [400, 422])

    # 4. Student wrong provider
    print("\n[S4] Student login with wrong provider (apple)")
    status, body, raw = login(STU_USER, STU_PASS, provider="apple")
    record("Student wrong provider=apple", status, body, [400, 401, 422])

    # 5. Student empty username
    print("\n[S5] Student login with empty username")
    status, body, raw = login("", STU_PASS)
    record("Student empty username", status, body, [400, 422])

    # 6. Student empty password
    print("\n[S6] Student login with empty password")
    status, body, raw = login(STU_USER, "")
    record("Student empty password", status, body, [400, 422])

    # 7. Student registration with valid data
    print("\n[S7] Student registration with valid data")
    unique = f"teststu_{uuid.uuid4().hex[:8]}"
    reg_payload = {
        "username": unique,
        "password": "TestPass123!",
        "role": "student",
        "name": "Test Student",
        "studentId": f"SID_{uuid.uuid4().hex[:6]}",
    }
    r = requests.post(f"{BASE_URL}/api/auth/register", json=reg_payload, timeout=TIMEOUT)
    record("Student valid registration", r.status_code, r.text, [200, 201])
    try:
        reg_body = r.json() if r.status_code in (200, 201) else {}
    except Exception:
        reg_body = {}

    # 8. Student registration with duplicate username
    print("\n[S8] Student registration with duplicate username")
    r = requests.post(f"{BASE_URL}/api/auth/register", json=reg_payload, timeout=TIMEOUT)
    record("Student dup registration", r.status_code, r.text, [409, 400])

    # 9. Student registration with weak password
    print("\n[S9] Student registration with weak password (<8 chars)")
    weak_payload = {
        "username": f"weak_{uuid.uuid4().hex[:8]}",
        "password": "short",
        "role": "student",
        "name": "Weak Student",
        "studentId": f"SID_{uuid.uuid4().hex[:6]}",
    }
    r = requests.post(f"{BASE_URL}/api/auth/register", json=weak_payload, timeout=TIMEOUT)
    record("Student weak password reg", r.status_code, r.text, [400, 422])

    # 10. Student registration with missing fields
    print("\n[S10] Student registration with missing fields")
    r = requests.post(f"{BASE_URL}/api/auth/register", json={"username": "incomplete"}, timeout=TIMEOUT)
    record("Student missing fields reg", r.status_code, r.text, [400, 422])

    # 11. Student token verification
    print("\n[S11] Student token verification")
    if stu_token:
        r = requests.post(f"{BASE_URL}/api/auth/verify", headers=auth_header(stu_token), timeout=TIMEOUT)
        record("Student verify token", r.status_code, r.text, 200)
    else:
        record("Student verify token", 0, "No token available", 200)

    # 12. Student-or-professor check
    print("\n[S12] Student-or-professor check")
    if stu_token:
        r = requests.post(f"{BASE_URL}/api/auth/student-or-professor", headers=auth_header(stu_token), timeout=TIMEOUT)
        record("Student student-or-prof check", r.status_code, r.text, 200)
    else:
        record("Student student-or-prof check", 0, "No token available", 200)

    # 13. Student refresh token flow
    print("\n[S13] Student refresh token flow")
    if stu_refresh:
        r = requests.post(f"{BASE_URL}/api/auth/refresh", json={"refreshToken": stu_refresh}, timeout=TIMEOUT)
        record("Student refresh token", r.status_code, r.text, 200)
    else:
        record("Student refresh token", 0, "No refresh token available", 200)

    # ---- EDGE CASES ----
    print("\n" + "=" * 80)
    print("EDGE CASES")
    print("=" * 80)

    # 1. SQL injection attempt
    print("\n[E1] Login with SQL injection attempt")
    status, body, raw = login("' OR 1=1 --", "anything")
    record("SQL injection in username", status, body, [400, 401, 422])

    # 2. Very long username (>1000 chars)
    print("\n[E2] Login with very long username (>1000 chars)")
    long_user = "A" * 1100
    status, body, raw = login(long_user, "password")
    record("Very long username", status, body, [400, 401, 422, 413])

    # 3. Special characters in password
    print("\n[E3] Login with special characters in password")
    status, body, raw = login(PROF_USER, 'P@$$w0rd!"#%&\'()*+,-./:;<=>?@[\\]^`{|}~')
    record("Special chars in password", status, body, 401)

    # 4. Unicode username
    print("\n[E4] Login with Unicode username")
    status, body, raw = login("ユーザー名🔑", "password")
    record("Unicode username", status, body, [400, 401, 422])

    # 5. Invalid JWT token
    print("\n[E5] Invalid JWT token → 401")
    fake_jwt = "not-a-jwt"
    r = requests.post(f"{BASE_URL}/api/auth/verify", headers=auth_header(fake_jwt), timeout=TIMEOUT)
    record("Invalid JWT token", r.status_code, r.text, 401)

    # 6. Malformed JWT token
    print("\n[E6] Malformed JWT token → 401")
    r = requests.post(f"{BASE_URL}/api/auth/verify", headers=auth_header("not.a.valid.jwt"), timeout=TIMEOUT)
    record("Malformed JWT token", r.status_code, r.text, 401)

    # 7. No Authorization header
    print("\n[E7] No Authorization header → 401")
    r = requests.post(f"{BASE_URL}/api/auth/verify", timeout=TIMEOUT)
    record("No auth header", r.status_code, r.text, 401)

    # 8. Empty Bearer token
    print("\n[E8] Empty Bearer token → 401")
    r = requests.post(f"{BASE_URL}/api/auth/verify", headers={"Authorization": "Bearer "}, timeout=TIMEOUT)
    record("Empty bearer token", r.status_code, r.text, 401)

    # 9. Bearer with random string
    print("\n[E9] Bearer with random string → 401")
    r = requests.post(f"{BASE_URL}/api/auth/verify", headers={"Authorization": "Bearer randomgarbage12345"}, timeout=TIMEOUT)
    record("Bearer random string", r.status_code, r.text, 401)

    # ---- SUMMARY ----
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = sum(1 for r in results if not r["passed"])
    info = sum(1 for r in results if r["expected"] is None)

    print(f"\n{'Test Name':<45} {'Status':<8} {'Result':<8} {'Expected'}")
    print("-" * 90)
    for r in results:
        exp_str = str(r["expected"]) if r["expected"] else "N/A"
        result_str = "PASS" if r["passed"] else ("FAIL" if r["expected"] else "INFO")
        print(f"{r['name']:<45} {r['status']:<8} {result_str:<8} {exp_str}")

    print("-" * 90)
    print(f"\nTotal: {total} | Passed: {passed} | Failed: {failed} | Info-only: {info}")
    print(f"Pass rate: {(passed/(total-info)*100):.1f}%" if (total - info) > 0 else "N/A")

    if failed > 0:
        print("\n⚠️  FAILED TESTS:")
        for r in results:
            if not r["passed"] and r["expected"]:
                print(f"  - {r['name']}: got {r['status']}, expected {r['expected']}")
                print(f"    Body: {r['body']}")

    print("\n✅ Done." if failed == 0 else "\n❌ Some tests failed.")


if __name__ == "__main__":
    main()
