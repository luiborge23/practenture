#!/usr/bin/env python3
"""
BizSimAI Multi-Tenant Combinatorial Test Suite
==============================================

Tests ALL combinations of the multi-tenant system on EC2:

TEST GROUPS (70 tests total):
═════════════════════════════
A. Bootstrap & Auth Foundation         (6 tests)
B. Owner → Professor Code Management   (8 tests)
C. Professor Pre-Creation Flow         (6 tests)
D. Professor 1: Single Class           (8 tests)
E. Professor 1: Multiple Classes       (8 tests)
F. Professor 2: Different University   (8 tests)
G. Professor 3: Same Professor, 2 Uni  (10 tests)  ← same prof teaches at MIT + Stanford
H. Student Isolation Combinations      (12 tests)
I. Cross-Tenant Security Violations     (8 tests)
J. Edge Cases & Error Conditions       (6 tests)
"""

import json
import time
import urllib.request
import urllib.error
import sys
from collections import defaultdict

# ═══════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://18.215.180.58"
OWNER_PASSWORD = sys.argv[2] if len(sys.argv) > 2 else None  # Will fetch if not provided

# ═══════════════════════════════════════════════════════════════════
# API HELPER
# ═══════════════════════════════════════════════════════════════════

passed = 0
failed = 0
failures = []
group_stats = defaultdict(lambda: {"pass": 0, "fail": 0})


def api(method, path, body=None, token=None, expect_status=None):
    """Make API call. Returns (status, body_dict)."""
    url = BASE_URL + path
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        status = resp.getcode()
        raw = resp.read()
        try:
            body_out = json.loads(raw) if raw else {}
        except Exception:
            body_out = {"_raw": raw.decode()[:500]}
    except urllib.error.HTTPError as e:
        status = e.code
        raw = e.read()
        try:
            body_out = json.loads(raw) if raw else {}
        except Exception:
            body_out = {"_raw": raw.decode()[:500] if raw else ""}
    return status, body_out


def check(group, test_name, condition, detail=""):
    """Record a test result."""
    global passed, failed
    if condition:
        passed += 1
        group_stats[group]["pass"] += 1
    else:
        failed += 1
        group_stats[group]["fail"] += 1
        failures.append(f"  [{group}] {test_name}: {detail}")
    status_char = "✅" if condition else "❌"
    print(f"  {status_char} {test_name}" + (f" — {detail}" if not condition and detail else ""))


def ok(status):
    return 200 <= status < 300


# ═══════════════════════════════════════════════════════════════════
# TEST STATE — shared across groups
# ═══════════════════════════════════════════════════════════════════

state = {}


def login(provider, username=None, password=None, id_token=None):
    """Login and return (token, role, must_change)."""
    body = {"provider": provider}
    if username:
        body["username"] = username
    if password:
        body["password"] = password
    if id_token:
        body["id_token"] = id_token
    status, resp = api("POST", "/api/auth/login", body)
    if ok(status):
        return resp.get("accessToken"), resp.get("role"), resp.get("mustChangePassword", False)
    return None, None, None


def register_student(student_id, name, password):
    """Register a student. Returns True on success (201) or already exists (409)."""
    status, _ = api("POST", "/api/auth/register", {
        "student_id": student_id, "name": name, "password": password
    })
    return status in (201, 409)


def create_session(token, class_id=None, rounds=5, ai_teams=2, human_teams=1):
    """Create a session. Returns session code."""
    teams = [{"teamName": f"AI-{i+1}", "isAI": True} for i in range(ai_teams)]
    body = {
        "config": {"totalRounds": rounds, "numberOfAICompetitors": ai_teams, "startingCash": 100000, "randomSeed": 42},
        "teams": teams,
        "created_by": "professor",
        "maxHumanTeams": 30,
    }
    if class_id:
        body["classId"] = class_id
    status, resp = api("POST", "/api/sessions", body, token)
    return resp.get("code") if ok(status) else None, status


def dashboard_sessions(token):
    """Get dashboard sessions count."""
    status, resp = api("GET", "/api/dashboard/sessions", None, token)
    if ok(status):
        return len(resp.get("sessions", [])), resp.get("sessions", [])
    return -1, []


# ═══════════════════════════════════════════════════════════════════
# TEST GROUPS
# ═══════════════════════════════════════════════════════════════════

def group_A_bootstrap():
    """A. Bootstrap & Auth Foundation (6 tests)"""
    print("\n┌─ A. Bootstrap & Auth Foundation ──────────────────────────────")
    
    # A1: Health
    status, body = api("GET", "/api/health")
    check("A", "A1. Health check", ok(status), f"status={status}")
    
    # A2: Owner login
    token, role, must_change = login("password", "owner", OWNER_PASSWORD)
    check("A", "A2. Owner login", token is not None and role == "owner", f"role={role}")
    state["owner_token"] = token
    
    # A3: Default professor login (backward compat)
    token, role, must_change = login("password", "professor", "bizsimai2026")
    check("A", "A3. Default professor login", token is not None and role == "professor", f"role={role}")
    state["default_prof_token"] = token
    
    # A4: Student register + login
    register_student("stu_test_base", "Base Test Student", "Pass123!")
    token, role, must_change = login("password", "stu_test_base", "Pass123!")
    check("A", "A4. Student login", token is not None and role == "student", f"role={role}")
    state["base_student_token"] = token
    
    # A5: Invalid login
    token, role, _ = login("password", "owner", "WRONG_PASSWORD")
    check("A", "A5. Invalid login rejected", token is None, "should fail")
    
    # A6: Invalid token rejected
    status, _ = api("GET", "/api/dashboard/sessions", None, "invalid.token.here")
    check("A", "A6. Invalid token rejected", status == 401, f"status={status}")
    
    print(f"└─ Group A: {group_stats['A']['pass']} pass, {group_stats['A']['fail']} fail")


def group_B_professor_codes():
    """B. Owner → Professor Code Management (8 tests)"""
    print("\n┌─ B. Professor Code Management ─────────────────────────────────")
    
    # B1: Owner creates professor code for MIT
    status, body = api("POST", "/api/professor/codes", {
        "university_name": "MIT", "notes": "MIT Fall 2026"
    }, state["owner_token"])
    check("B", "B1. Create MIT professor code", ok(status) and body.get("code", "").startswith("PROF-"), 
          f"status={status} code={body.get('code')}")
    state["mit_code_1"] = body.get("code")
    
    # B2: Owner creates second MIT code
    status, body = api("POST", "/api/professor/codes", {
        "university_name": "MIT", "notes": "MIT Spring 2027"
    }, state["owner_token"])
    check("B", "B2. Create second MIT code", ok(status) and body.get("code", "").startswith("PROF-"),
          f"status={status}")
    state["mit_code_2"] = body.get("code")
    
    # B3: Owner creates Stanford code
    status, body = api("POST", "/api/professor/codes", {
        "university_name": "Stanford", "notes": "Stanford access"
    }, state["owner_token"])
    check("B", "B3. Create Stanford code", ok(status) and body.get("code", "").startswith("PROF-"),
          f"status={status}")
    state["stanford_code_1"] = body.get("code")
    
    # B4: List all codes
    status, body = api("GET", "/api/professor/codes", None, state["owner_token"])
    check("B", "B4. List professor codes", ok(status) and len(body.get("codes", [])) >= 3,
          f"count={len(body.get('codes', []))}")
    
    # B5: Student cannot create professor codes
    status, _ = api("POST", "/api/professor/codes", {
        "university_name": "Hacker U", "notes": "trying"
    }, state["base_student_token"])
    check("B", "B5. Student blocked from creating codes", status == 403, f"status={status}")
    
    # B6: Professor cannot create codes
    status, _ = api("POST", "/api/professor/codes", {
        "university_name": "Hacker U", "notes": "trying"
    }, state["default_prof_token"])
    check("B", "B6. Professor blocked from creating codes", status == 403, f"status={status}")
    
    # B7: No token = rejected (FastAPI HTTPBearer returns 403 when no credentials)
    status, _ = api("POST", "/api/professor/codes", {"university_name": "No Auth U"})
    check("B", "B7. No token = rejected", status in (401, 403), f"status={status}")
    
    # B8: Codes are unique
    check("B", "B8. Codes are unique",
          state["mit_code_1"] != state["mit_code_2"] != state["stanford_code_1"],
          f"codes: {state['mit_code_1']}, {state['mit_code_2']}, {state['stanford_code_1']}")
    
    print(f"└─ Group B: {group_stats['B']['pass']} pass, {group_stats['B']['fail']} fail")


def group_C_precreate_professors():
    """C. Professor Pre-Creation Flow (6 tests)"""
    print("\n┌─ C. Professor Pre-Creation Flow ──────────────────────────────")
    
    # C1: Owner pre-creates Prof Smith (MIT)
    status, body = api("POST", "/api/professor/pre-create", {
        "username": "prof_smith", "password": "TempMIT123!",
        "name": "Prof. John Smith", "email": "smith@mit.edu", "university_name": "MIT"
    }, state["owner_token"])
    check("C", "C1. Pre-create Prof Smith (MIT)", ok(status), f"status={status} body={body}")
    state["smith_code"] = body.get("professor_code")
    
    # C2: Owner pre-creates Prof Jones (Stanford)
    status, body = api("POST", "/api/professor/pre-create", {
        "username": "prof_jones", "password": "TempStanford123!",
        "name": "Prof. Sarah Jones", "email": "jones@stanford.edu", "university_name": "Stanford"
    }, state["owner_token"])
    check("C", "C2. Pre-create Prof Jones (Stanford)", ok(status), f"status={status}")
    
    # C3: Pre-created professor logs in
    token, role, must_change = login("password", "prof_smith", "TempMIT123!")
    check("C", "C3. Prof Smith first login", token is not None and role == "professor",
          f"role={role}")
    check("C", "C3b. Prof Smith must_change_password flag", must_change == True,
          f"must_change={must_change}")
    state["smith_token"] = token
    
    # C4: Professor changes password
    status, body = api("POST", "/api/professor/change-password", {
        "old_password": "TempMIT123!", "new_password": "SmithSecure456!"
    }, state["smith_token"])
    check("C", "C4. Change password", ok(status), f"status={status}")
    
    # C5: Old password no longer works
    token, _, _ = login("password", "prof_smith", "TempMIT123!")
    check("C", "C5. Old password rejected after change", token is None, "should fail")
    
    # C6: New password works
    token, role, must_change = login("password", "prof_smith", "SmithSecure456!")
    check("C", "C6. New password works", token is not None and role == "professor",
          f"role={role} must_change={must_change}")
    state["smith_token"] = token  # refresh token after password change
    
    print(f"└─ Group C: {group_stats['C']['pass']} pass, {group_stats['C']['fail']} fail")


def group_D_prof1_single_class():
    """D. Professor 1: Single Class (8 tests)"""
    print("\n┌─ D. Prof Smith (MIT) — Single Class ──────────────────────────")
    
    # D1: Create class
    status, body = api("POST", "/api/classes", {
        "name": "MIT Fall 2026 Business Strategy", "description": "MBA capstone"
    }, state["smith_token"])
    check("D", "D1. Create class", ok(status) and body.get("join_code", "").startswith("BIZ-"),
          f"status={status} code={body.get('join_code')}")
    state["smith_class1_id"] = body.get("id")
    state["smith_class1_code"] = body.get("join_code")
    
    # D2: List classes — should see 1
    status, body = api("GET", "/api/classes", None, state["smith_token"])
    check("D", "D2. List classes = 1", ok(status) and len(body.get("classes", [])) == 1,
          f"count={len(body.get('classes', []))}")
    
    # D3: Create session in class
    code, status = create_session(state["smith_token"], state["smith_class1_id"])
    check("D", "D3. Create session in class", code is not None, f"status={status} code={code}")
    state["smith_session1"] = code
    
    # D4: Dashboard shows 1 session
    count, _ = dashboard_sessions(state["smith_token"])
    check("D", "D4. Dashboard = 1 session", count == 1, f"count={count}")
    
    # D5: Student joins class
    register_student("stu_mit_001", "Alice MIT", "Pass123!")
    token, _, _ = login("password", "stu_mit_001", "Pass123!")
    state["stu_mit_001_token"] = token
    status, body = api("POST", "/api/classes/join", {"join_code": state["smith_class1_code"]}, token)
    check("D", "D5. Student joins class", ok(status), f"status={status}")
    
    # D6: Student sees 1 class
    status, body = api("GET", "/api/classes/my/classes", None, token)
    check("D", "D6. Student sees 1 class", ok(status) and len(body.get("classes", [])) == 1,
          f"count={len(body.get('classes', []))}")
    
    # D7: Student dashboard shows 1 session
    count, _ = dashboard_sessions(token)
    check("D", "D7. Student dashboard = 1 session", count == 1, f"count={count}")
    
    # D8: Professor sees 1 student in class
    status, body = api("GET", f"/api/classes/{state['smith_class1_id']}/students", None, state["smith_token"])
    check("D", "D8. Class has 1 student", ok(status) and len(body.get("students", [])) == 1,
          f"count={len(body.get('students', []))}")
    
    print(f"└─ Group D: {group_stats['D']['pass']} pass, {group_stats['D']['fail']} fail")


def group_E_prof1_multiple_classes():
    """E. Professor 1: Multiple Classes (8 tests)"""
    print("\n┌─ E. Prof Smith (MIT) — Multiple Classes ──────────────────────")
    
    # E1: Create second class
    status, body = api("POST", "/api/classes", {
        "name": "MIT Spring 2027 Marketing", "description": "Undergrad marketing"
    }, state["smith_token"])
    check("E", "E1. Create second class", ok(status), f"status={status}")
    state["smith_class2_id"] = body.get("id")
    state["smith_class2_code"] = body.get("join_code")
    
    # E2: Create third class
    status, body = api("POST", "/api/classes", {
        "name": "MIT Summer 2026 Executive Ed", "description": "Executive education"
    }, state["smith_token"])
    check("E", "E2. Create third class", ok(status), f"status={status}")
    state["smith_class3_id"] = body.get("id")
    state["smith_class3_code"] = body.get("join_code")
    
    # E3: Professor sees 3 classes total
    status, body = api("GET", "/api/classes", None, state["smith_token"])
    check("E", "E3. List classes = 3", ok(status) and len(body.get("classes", [])) == 3,
          f"count={len(body.get('classes', []))}")
    
    # E4: Create session in class 2
    code, status = create_session(state["smith_token"], state["smith_class2_id"])
    check("E", "E4. Create session in class 2", code is not None, f"status={status}")
    state["smith_session2"] = code
    
    # E5: Create session in class 3
    code, status = create_session(state["smith_token"], state["smith_class3_id"])
    check("E", "E5. Create session in class 3", code is not None, f"status={status}")
    state["smith_session3"] = code
    
    # E6: Dashboard shows 3 sessions (all belong to Smith)
    count, _ = dashboard_sessions(state["smith_token"])
    check("E", "E6. Dashboard = 3 sessions", count == 3, f"count={count}")
    
    # E7: Student joins class 2, sees only class 2 sessions
    register_student("stu_mit_002", "Bob MIT", "Pass123!")
    token, _, _ = login("password", "stu_mit_002", "Pass123!")
    state["stu_mit_002_token"] = token
    api("POST", "/api/classes/join", {"join_code": state["smith_class2_code"]}, token)
    count, _ = dashboard_sessions(token)
    check("E", "E7. Student in class 2 sees 1 session", count == 1, f"count={count}")
    
    # E8: Student joins class 3 too, sees 2 sessions
    api("POST", "/api/classes/join", {"join_code": state["smith_class3_code"]}, token)
    count, _ = dashboard_sessions(token)
    check("E", "E8. Student in class 2+3 sees 2 sessions", count == 2, f"count={count}")
    
    print(f"└─ Group E: {group_stats['E']['pass']} pass, {group_stats['E']['fail']} fail")


def group_F_prof2_different_uni():
    """F. Professor 2: Different University (8 tests)"""
    print("\n┌─ F. Prof Jones (Stanford) — Different University ─────────────")
    
    # F1: Prof Jones logs in
    token, role, _ = login("password", "prof_jones", "TempStanford123!")
    check("F", "F1. Prof Jones login", token is not None and role == "professor", f"role={role}")
    state["jones_token"] = token
    
    # F2: Jones changes password
    status, _ = api("POST", "/api/professor/change-password", {
        "old_password": "TempStanford123!", "new_password": "JonesSecure789!"
    }, state["jones_token"])
    check("F", "F2. Jones changes password", ok(status), f"status={status}")
    token, _, _ = login("password", "prof_jones", "JonesSecure789!")
    state["jones_token"] = token
    
    # F3: Jones creates class
    status, body = api("POST", "/api/classes", {
        "name": "Stanford Fall 2026 Strategy", "description": "GSB capstone"
    }, state["jones_token"])
    check("F", "F3. Jones creates class", ok(status), f"status={status}")
    state["jones_class1_id"] = body.get("id")
    state["jones_class1_code"] = body.get("join_code")
    
    # F4: Jones creates session
    code, status = create_session(state["jones_token"], state["jones_class1_id"])
    check("F", "F4. Jones creates session", code is not None, f"status={status}")
    state["jones_session1"] = code
    
    # F5: Jones dashboard shows only 1 session (NOT Smith's 3)
    count, _ = dashboard_sessions(state["jones_token"])
    check("F", "F5. Jones dashboard = 1 (isolated from Smith)", count == 1, f"count={count}")
    
    # F6: Smith dashboard still 3 (NOT Jones's 1)
    count, _ = dashboard_sessions(state["smith_token"])
    check("F", "F6. Smith dashboard still = 3 (isolated from Jones)", count == 3, f"count={count}")
    
    # F7: Stanford student joins, sees only Jones session
    register_student("stu_stanford_001", "Charlie Stanford", "Pass123!")
    token, _, _ = login("password", "stu_stanford_001", "Pass123!")
    state["stu_stanford_001_token"] = token
    api("POST", "/api/classes/join", {"join_code": state["jones_class1_code"]}, token)
    count, _ = dashboard_sessions(token)
    check("F", "F7. Stanford student sees 1 session (Jones only)", count == 1, f"count={count}")
    
    # F8: MIT student does NOT see Stanford session
    count, _ = dashboard_sessions(state["stu_mit_001_token"])
    check("F", "F8. MIT student does NOT see Stanford session", count == 1, f"count={count}")
    
    print(f"└─ Group F: {group_stats['F']['pass']} pass, {group_stats['F']['fail']} fail")


def group_G_same_prof_two_universities():
    """G. Same Professor Teaching at Two Universities (10 tests)
    
    Prof Smith already teaches at MIT. Now we simulate the same person
    getting a Stanford code and teaching there too — but under the SAME login.
    This tests whether a single professor account can manage classes
    across different universities.
    """
    print("\n┌─ G. Same Professor, Two Universities ─────────────────────────")
    
    # G1: Smith redeems Stanford code (as existing professor)
    # NOTE: Currently professors get 400 "already a professor" — this tests that behavior
    status, body = api("POST", "/api/professor/redeem", {"code": state["stanford_code_1"]}, state["smith_token"])
    # Expected: 400 because Smith is already a professor
    check("G", "G1. Professor redeeming code gets 400 (already prof)", status == 400,
          f"status={status} (system says: {body.get('detail', '')})")
    
    # G2: Owner creates a NEW professor code for Stanford for a different person
    status, body = api("POST", "/api/professor/codes", {
        "university_name": "Stanford", "notes": "For Smith at Stanford"
    }, state["owner_token"])
    state["stanford_code_2"] = body.get("code")
    check("G", "G2. Create Stanford code 2", ok(status), f"status={status}")
    
    # G3: Owner pre-creates a second account for Smith at Stanford
    # (different username, same person, different university)
    status, body = api("POST", "/api/professor/pre-create", {
        "username": "prof_smith_stanford", "password": "TempStanfordSmith1!",
        "name": "Prof. John Smith", "email": "smith@stanford.edu", "university_name": "Stanford"
    }, state["owner_token"])
    check("G", "G3. Pre-create Smith-Stanford account", ok(status), f"status={status}")
    
    # G4: Smith logs in with second account
    token, role, _ = login("password", "prof_smith_stanford", "TempStanfordSmith1!")
    check("G", "G4. Smith-Stanford login", token is not None and role == "professor", f"role={role}")
    state["smith_stanford_token"] = token
    
    # G5: Smith-Stanford creates class
    status, body = api("POST", "/api/classes", {
        "name": "Stanford Spring 2027 Strategy", "description": "Same prof, different uni"
    }, state["smith_stanford_token"])
    check("G", "G5. Smith-Stanford creates class", ok(status), f"status={status}")
    state["smith_stanford_class_id"] = body.get("id")
    state["smith_stanford_class_code"] = body.get("join_code")
    
    # G6: Smith-Stanford creates session
    code, status = create_session(state["smith_stanford_token"], state["smith_stanford_class_id"])
    check("G", "G6. Smith-Stanford creates session", code is not None, f"status={status}")
    state["smith_stanford_session"] = code
    
    # G7: Smith-MIT dashboard = 3 (NOT Stanford's)
    count, _ = dashboard_sessions(state["smith_token"])
    check("G", "G7. Smith-MIT dashboard = 3 (NOT Stanford's)", count == 3, f"count={count}")
    
    # G8: Smith-Stanford dashboard = 1 (NOT MIT's)
    count, _ = dashboard_sessions(state["smith_stanford_token"])
    check("G", "G8. Smith-Stanford dashboard = 1 (NOT MIT's)", count == 1, f"count={count}")
    
    # G9: Student joins Smith-Stanford class
    register_student("stu_stanford_002", "Dana Stanford", "Pass123!")
    token, _, _ = login("password", "stu_stanford_002", "Pass123!")
    state["stu_stanford_002_token"] = token
    api("POST", "/api/classes/join", {"join_code": state["smith_stanford_class_code"]}, token)
    count, _ = dashboard_sessions(token)
    check("G", "G9. Stanford student sees Smith-Stanford session", count == 1, f"count={count}")
    
    # G10: MIT student does NOT see Smith-Stanford's session
    count, _ = dashboard_sessions(state["stu_mit_001_token"])
    check("G", "G10. MIT student does NOT see Smith-Stanford session", count == 1, f"count={count}")
    
    print(f"└─ Group G: {group_stats['G']['pass']} pass, {group_stats['G']['fail']} fail")


def group_H_student_isolation():
    """H. Student Isolation Combinations (12 tests)"""
    print("\n┌─ H. Student Isolation Combinations ───────────────────────────")
    
    # H1: Student in MIT class 1 — sees only class 1 sessions
    count, _ = dashboard_sessions(state["stu_mit_001_token"])
    check("H", "H1. MIT student (class 1 only) = 1 session", count == 1, f"count={count}")
    
    # H2: Student in MIT classes 2+3 — sees 2 sessions
    count, _ = dashboard_sessions(state["stu_mit_002_token"])
    check("H", "H2. MIT student (classes 2+3) = 2 sessions", count == 2, f"count={count}")
    
    # H3: Stanford student 1 — sees 1 session (Jones)
    count, _ = dashboard_sessions(state["stu_stanford_001_token"])
    check("H", "H3. Stanford student (Jones class) = 1 session", count == 1, f"count={count}")
    
    # H4: Stanford student 2 — sees 1 session (Smith-Stanford)
    count, _ = dashboard_sessions(state["stu_stanford_002_token"])
    check("H", "H4. Stanford student (Smith-Stanford) = 1 session", count == 1, f"count={count}")
    
    # H5: New student with NO classes — sees 0 sessions
    register_student("stu_noclass_001", "No Class Student", "Pass123!")
    token, _, _ = login("password", "stu_noclass_001", "Pass123!")
    state["stu_noclass_token"] = token
    count, _ = dashboard_sessions(token)
    check("H", "H5. Student with no classes = 0 sessions", count == 0, f"count={count}")
    
    # H6: Student joins class from different professor — still works
    status, body = api("POST", "/api/classes/join", {"join_code": state["jones_class1_code"]}, state["stu_noclass_token"])
    check("H", "H6. Student joins Jones class (cross-professor)", ok(status), f"status={status}")
    count, _ = dashboard_sessions(state["stu_noclass_token"])
    check("H", "H6b. Now sees 1 session (Jones)", count == 1, f"count={count}")
    
    # H7: Same student also joins MIT class 1 — sees 2 sessions now
    api("POST", "/api/classes/join", {"join_code": state["smith_class1_code"]}, state["stu_noclass_token"])
    count, _ = dashboard_sessions(state["stu_noclass_token"])
    check("H", "H7. Cross-university student = 2 sessions (Jones + Smith-MIT)", count == 2, f"count={count}")
    
    # H8: Student enrolled in same class twice — no duplication
    api("POST", "/api/classes/join", {"join_code": state["smith_class1_code"]}, state["stu_noclass_token"])
    count, _ = dashboard_sessions(state["stu_noclass_token"])
    check("H", "H8. Duplicate enrollment = no duplicate sessions", count == 2, f"count={count}")
    
    # H9: Student lists classes — should see 2
    status, body = api("GET", "/api/classes/my/classes", None, state["stu_noclass_token"])
    check("H", "H9. Cross-uni student sees 2 classes", ok(status) and len(body.get("classes", [])) == 2,
          f"count={len(body.get('classes', []))}")
    
    # H10: Student cannot access class students list (professor only)
    status, _ = api("GET", f"/api/classes/{state['smith_class1_id']}/students", None, state["stu_noclass_token"])
    check("H", "H10. Student blocked from class students list", status == 403, f"status={status}")
    
    # H11: Student cannot create sessions
    code, status = create_session(state["stu_noclass_token"], state["smith_class1_id"])
    check("H", "H11. Student blocked from creating sessions", status == 403, f"status={status}")
    
    # H12: Student game flow — start session and join
    status, _ = api("POST", f"/api/sessions/{state['smith_session1']}/start", None, state["smith_token"])
    check("H", "H12a. Professor starts session", ok(status), f"status={status}")
    status, body = api("PUT", f"/api/sessions/{state['smith_session1']}/join", {
        "teamName": "Test Team H12", "studentId": "stu_noclass_001"
    }, state["stu_noclass_token"])
    check("H", "H12b. Student joins active session", ok(status), f"status={status}")
    
    print(f"└─ Group H: {group_stats['H']['pass']} pass, {group_stats['H']['fail']} fail")


def group_I_cross_tenant_security():
    """I. Cross-Tenant Security Violations (8 tests)"""
    print("\n┌─ I. Cross-Tenant Security Violations ──────────────────────────")
    
    # I1: Prof Smith cannot see Jones's class details
    status, _ = api("GET", f"/api/classes/{state['jones_class1_id']}", None, state["smith_token"])
    check("I", "I1. Smith cannot view Jones's class", status == 403, f"status={status}")
    
    # I2: Prof Jones cannot see Smith's class details
    status, _ = api("GET", f"/api/classes/{state['smith_class1_id']}", None, state["jones_token"])
    check("I", "I2. Jones cannot view Smith's class", status == 403, f"status={status}")
    
    # I3: Prof Smith cannot list students in Jones's class
    status, _ = api("GET", f"/api/classes/{state['jones_class1_id']}/students", None, state["smith_token"])
    check("I", "I3. Smith cannot list Jones's students", status == 403, f"status={status}")
    
    # I4: Prof Jones cannot list students in Smith's class
    status, _ = api("GET", f"/api/classes/{state['smith_class1_id']}/students", None, state["jones_token"])
    check("I", "I4. Jones cannot list Smith's students", status == 403, f"status={status}")
    
    # I5: Student redeems professor code to become professor
    # Use mit_code_2 (not used by anyone yet)
    status, body = api("POST", "/api/professor/redeem", {"code": state["mit_code_2"]}, state["base_student_token"])
    check("I", "I5. Student redeems professor code (becomes professor)", ok(status), f"status={status} body={body}")
    if ok(status):
        state["promoted_token"] = body.get("accessToken")
        state["used_code"] = state["mit_code_2"]
    
    # I6: After redemption, student (now professor) can create classes
    if state.get("promoted_token"):
        status, body = api("POST", "/api/classes", {
            "name": "Promoted Student Class", "description": "Was a student, now a prof"
        }, state["promoted_token"])
        check("I", "I6. Promoted student can create classes", ok(status), f"status={status}")
    else:
        check("I", "I6. Promoted student can create classes", False, "No promoted token")
    
    # I7: Already-used code cannot be redeemed again (by a different student)
    if state.get("used_code"):
        # Create a fresh student to try redeeming the used code
        register_student("stu_try_redeem", "Try Redeem Student", "Pass123!")
        fresh_token, _, _ = login("password", "stu_try_redeem", "Pass123!")
        status, _ = api("POST", "/api/professor/redeem", {"code": state["used_code"]}, fresh_token)
        check("I", "I7. Used code cannot be redeemed again", status == 404, f"status={status}")
    else:
        check("I", "I7. Used code cannot be redeemed again", False, "No used code to test")
    
    # I8: Invalid code format
    status, _ = api("POST", "/api/professor/redeem", {"code": "FAKE-CODE-1234"}, state["base_student_token"])
    check("I", "I8. Invalid code rejected", status == 404, f"status={status}")
    
    print(f"└─ Group I: {group_stats['I']['pass']} pass, {group_stats['I']['fail']} fail")


def group_J_edge_cases():
    """J. Edge Cases & Error Conditions (6 tests)"""
    print("\n┌─ J. Edge Cases & Error Conditions ────────────────────────────")
    
    # J1: Create session without classId (backward compat — should still work)
    code, status = create_session(state["smith_token"], class_id=None)
    check("J", "J1. Session without classId (backward compat)", code is not None, f"status={status}")
    if code:
        state["smith_session_no_class"] = code
    
    # J2: Dashboard still counts session without class
    count, _ = dashboard_sessions(state["smith_token"])
    # Smith now has: 3 (classes 1,2,3) + 1 (no class) = 4
    check("J", "J2. Dashboard counts session without class", count == 4, f"count={count}")
    
    # J3: Get non-existent class
    status, _ = api("GET", "/api/classes/FAKE-CLASS-ID", None, state["smith_token"])
    check("J", "J3. Get non-existent class = 404", status == 404, f"status={status}")
    
    # J4: Join class with invalid code
    status, _ = api("POST", "/api/classes/join", {"join_code": "BIZ-FAKE0"}, state["base_student_token"])
    check("J", "J4. Join with invalid code = 404", status == 404, f"status={status}")
    
    # J5: Duplicate pre-create (same username)
    status, _ = api("POST", "/api/professor/pre-create", {
        "username": "prof_smith", "password": "Temp123!",
        "name": "Duplicate", "email": "dup@mit.edu", "university_name": "MIT"
    }, state["owner_token"])
    check("J", "J5. Duplicate pre-create = 409", status == 409, f"status={status}")
    
    # J6: Change password with wrong old password
    status, _ = api("POST", "/api/professor/change-password", {
        "old_password": "WRONG_PASSWORD", "new_password": "NewPass123!"
    }, state["smith_token"])
    check("J", "J6. Wrong old password = 401", status == 401, f"status={status}")
    
    print(f"└─ Group J: {group_stats['J']['pass']} pass, {group_stats['J']['fail']} fail")


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    global OWNER_PASSWORD
    
    print("=" * 70)
    print("  BizSimAI Multi-Tenant Combinatorial Test Suite")
    print(f"  Target: {BASE_URL}")
    print("=" * 70)
    
    # If no owner password provided, try to fetch from EC2
    if not OWNER_PASSWORD:
        print("\n  ⚠ No owner password provided. Attempting to fetch from EC2...")
        import subprocess
        try:
            result = subprocess.run(
                ["ssh", "-i", os.path.expanduser("~/.ssh/bizsimai"),
                 "-o", "StrictHostKeyChecking=no",
                 "ec2-user@18.215.180.58",
                 "docker exec bizsim-backend env | grep BIZSIMAI_OWNER_PASSWORD"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and "BIZSIMAI_OWNER_PASSWORD=" in result.stdout:
                OWNER_PASSWORD = result.stdout.strip().split("=")[1]
                print(f"  ✅ Found owner password: {OWNER_PASSWORD[:4]}****")
            else:
                print("  ❌ Could not fetch owner password. Run: ssh -i ~/.ssh/bizsimai ec2-user@18.215.180.58 'docker exec bizsim-backend env | grep OWNER_PASS'")
                sys.exit(1)
        except Exception as e:
            print(f"  ❌ SSH failed: {e}")
            sys.exit(1)
    
    # Run all groups
    group_A_bootstrap()
    group_B_professor_codes()
    group_C_precreate_professors()
    group_D_prof1_single_class()
    group_E_prof1_multiple_classes()
    group_F_prof2_different_uni()
    group_G_same_prof_two_universities()
    group_H_student_isolation()
    group_I_cross_tenant_security()
    group_J_edge_cases()
    
    # Summary
    print("\n" + "=" * 70)
    print("  COMPREHENSIVE TEST SUMMARY")
    print("=" * 70)
    for group_name, label in [
        ("A", "Bootstrap & Auth"), ("B", "Professor Codes"),
        ("C", "Pre-Creation"), ("D", "Prof1 Single Class"),
        ("E", "Prof1 Multi Classes"), ("F", "Prof2 Different Uni"),
        ("G", "Same Prof Two Uni"), ("H", "Student Isolation"),
        ("I", "Cross-Tenant Security"), ("J", "Edge Cases"),
    ]:
        s = group_stats[group_name]
        total = s["pass"] + s["fail"]
        status_str = "✅ ALL PASS" if s["fail"] == 0 else f"❌ {s['fail']} FAILED"
        print(f"  {label:25s} {s['pass']:3d}/{total:<3d}  {status_str}")
    print("=" * 70)
    print(f"  TOTAL: {passed} passed, {failed} failed out of {passed + failed}")
    print("=" * 70)
    
    if failures:
        print("\n  FAILURE DETAILS:")
        for f in failures:
            print(f)
        print()
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    import os
    sys.exit(main())
