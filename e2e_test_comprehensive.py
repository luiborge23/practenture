#!/usr/bin/env python3
"""
Comprehensive E2E test suite for Practenture backend.
Tests against production backend at http://18.215.180.58
"""

import requests
import json
import time
import sys
import csv
import io
from datetime import datetime

BASE_URL = "http://18.215.180.58"
TIMEOUT = 30

# ── Results tracking ──────────────────────────────────────────────────────
results = []

def record(category, test_name, passed, detail=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    entry = {
        "category": category,
        "test": test_name,
        "passed": passed,
        "detail": detail,
        "timestamp": datetime.utcnow().isoformat(),
    }
    results.append(entry)
    print(f"  {status} | {test_name}" + (f" — {detail}" if detail else ""))

def category_header(name):
    print(f"\n{'='*60}")
    print(f"  CATEGORY: {name}")
    print(f"{'='*60}")

def summary():
    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    cats = {}
    for r in results:
        cat = r["category"]
        if cat not in cats:
            cats[cat] = {"pass": 0, "fail": 0}
        if r["passed"]:
            cats[cat]["pass"] += 1
        else:
            cats[cat]["fail"] += 1
    total_pass = sum(c["pass"] for c in cats.values())
    total_fail = sum(c["fail"] for c in cats.values())
    print(f"  {'Category':<40} {'Pass':>6} {'Fail':>6}")
    print(f"  {'-'*40} {'-'*6} {'-'*6}")
    for cat in sorted(cats.keys()):
        print(f"  {cat:<40} {cats[cat]['pass']:>6} {cats[cat]['fail']:>6}")
    print(f"  {'-'*40} {'-'*6} {'-'*6}")
    print(f"  {'TOTAL':<40} {total_pass:>6} {total_fail:>6}")
    return total_pass, total_fail

# ── Helper functions ───────────────────────────────────────────────────────
def login(username, password):
    """Login and return token + user info."""
    resp = requests.post(f"{BASE_URL}/api/auth/login",
                         json={"provider": "password", "username": username, "password": password},
                         timeout=TIMEOUT)
    return resp

def get_auth_headers(token):
    return {"Authorization": f"Bearer {token}"}

def create_session(prof_token, config=None, teams=None, max_human=30):
    """Create a session, return (code, session_id)."""
    if config is None:
        config = {
            "totalRounds": 4,
            "numberOfAICompetitors": 2,
            "randomSeed": 42,
            "startingCash": 500000,
            "initialEquity": 300000,
            "plantCapacity": 10000,
            "maxOvertimePercent": 25,
            "minWage": 12000,
            "maxWage": 40000,
            "minDividend": 0,
            "maxDividend": 5.0,
            "marketType": "moderate",
            "aiDifficulty": "medium",
            "scoringMetric": "investor_score",
            "fixedCostsPerRound": 5000,
            "baseCostPerUnit": 30,
            "baseMarketDemand": 10000,
            "sharesOutstanding": 10000,
            "baseInterestRate": 0.06,
        }
    body = {
        "config": config,
        "teams": teams or [],
        "created_by": "professor",
        "maxHumanTeams": max_human,
    }
    resp = requests.post(f"{BASE_URL}/api/sessions", json=body,
                         headers=get_auth_headers(prof_token), timeout=TIMEOUT)
    return resp

def join_session(code, student_token, student_id, team_name):
    """Student joins a session as a team."""
    resp = requests.put(f"{BASE_URL}/api/sessions/{code}/join",
                        json={"teamName": team_name, "studentId": student_id},
                        headers=get_auth_headers(student_token), timeout=TIMEOUT)
    return resp

def submit_decision(code, token, round_num, team_id, decision):
    """Submit a decision for a team."""
    body = {"round": round_num, "teamId": team_id, "decision": decision}
    resp = requests.post(f"{BASE_URL}/api/sessions/{code}/submit_decision",
                         json=body, headers=get_auth_headers(token), timeout=TIMEOUT)
    return resp

def process_round(code, prof_token):
    """Professor processes the current round."""
    resp = requests.post(f"{BASE_URL}/api/sessions/{code}/process_round",
                         headers=get_auth_headers(prof_token), timeout=TIMEOUT)
    return resp

def get_session(code, token):
    resp = requests.get(f"{BASE_URL}/api/sessions/{code}",
                        headers=get_auth_headers(token), timeout=TIMEOUT)
    return resp

def get_leaderboard(code, token):
    resp = requests.get(f"{BASE_URL}/api/sessions/{code}/leaderboard",
                        headers=get_auth_headers(token), timeout=TIMEOUT)
    return resp

def export_grades(code, prof_token):
    resp = requests.get(f"{BASE_URL}/api/sessions/{code}/export/grades",
                        headers=get_auth_headers(prof_token), timeout=TIMEOUT)
    return resp

def get_announcements(code, token):
    resp = requests.get(f"{BASE_URL}/api/sessions/{code}/announcements",
                        headers=get_auth_headers(token), timeout=TIMEOUT)
    return resp

def create_announcement(code, prof_token, message, author_name="Professor"):
    resp = requests.post(f"{BASE_URL}/api/sessions/{code}/announcements",
                         json={"message": message, "authorName": author_name},
                         headers=get_auth_headers(prof_token), timeout=TIMEOUT)
    return resp

def delete_session(code, prof_token):
    resp = requests.delete(f"{BASE_URL}/api/sessions/{code}",
                           headers=get_auth_headers(prof_token), timeout=TIMEOUT)
    return resp

def start_session(code, prof_token):
    resp = requests.post(f"{BASE_URL}/api/sessions/{code}/start",
                         headers=get_auth_headers(prof_token), timeout=TIMEOUT)
    return resp

def register_student(username, password, name, student_id):
    resp = requests.post(f"{BASE_URL}/api/auth/register",
                        json={"username": username, "password": password, "name": name, "student_id": student_id, "provider": "password"},
                        timeout=TIMEOUT)
    return resp

# ── Default decision ──────────────────────────────────────────────────────
def default_decision():
    return {
        "wholesalePrice": 80.0,
        "internetPrice": 90.0,
        "amazonPrice": 85.0,
        "privateLabelBidPrice": 45.0,
        "privateLabelMaxUnits": 50,
        "amazonAdBudget": 0.0,
        "materialsQuality": "standard",
        "stylingBudget": 3000.0,
        "modelsOffered": 3,
        "tqmInvestment": 2000.0,
        "advertisingBudget": 8000.0,
        "celebrityEndorsement": "none",
        "retailOutlets": 20,
        "mailInRebate": 0.0,
        "deliveryTime": "standard",
        "freeShippingThreshold": 100.0,
        "tiktokBudget": 0.0,
        "instagramBudget": 0.0,
        "youtubeBudget": 0.0,
        "influencerTier": "none",
        "baseWage": 25000.0,
        "incentivePay": 0.50,
        "trainingHours": 20.0,
        "bestPracticesInvestment": 1000.0,
        "productionQuantity": 200,
        "overtimePercent": 0.0,
        "csrInvestment": 2000.0,
        "dividendsPerShare": 0.50,
        "newLoanAmount": 0.0,
        "sharesBuyback": 0,
        "sharesIssued": 0,
        "fulfillmentMethod": "fbm",
    }

# ── Test permutation decisions ────────────────────────────────────────────
def perm_decision_min():
    d = default_decision()
    d.update({
        "wholesalePrice": 30, "internetPrice": 35, "amazonPrice": 30,
        "productionQuantity": 0, "advertisingBudget": 0, "baseWage": 15000,
        "dividendsPerShare": 0, "overtimePercent": 0, "materialsQuality": "standard",
        "stylingBudget": 0, "modelsOffered": 1, "tqmInvestment": 0,
        "csrInvestment": 0, "celebrityEndorsement": "none", "influencerTier": "none",
        "tiktokBudget": 0, "instagramBudget": 0, "youtubeBudget": 0,
        "retailOutlets": 5, "mailInRebate": 0, "freeShippingThreshold": 0,
        "fulfillmentMethod": "fbm", "sharesIssued": 0, "sharesBuyback": 0,
        "newLoanAmount": 0, "trainingHours": 0, "bestPracticesInvestment": 0,
        "amazonAdBudget": 0,
    })
    return d

def perm_decision_max():
    d = default_decision()
    d.update({
        "wholesalePrice": 200, "internetPrice": 250, "amazonPrice": 200,
        "productionQuantity": 600, "advertisingBudget": 30000, "baseWage": 40000,
        "dividendsPerShare": 5.0, "overtimePercent": 20, "materialsQuality": "superior",
        "stylingBudget": 15000, "modelsOffered": 8, "tqmInvestment": 10000,
        "csrInvestment": 10000, "celebrityEndorsement": "global", "influencerTier": "mega",
        "tiktokBudget": 15000, "instagramBudget": 15000, "youtubeBudget": 15000,
        "retailOutlets": 60, "mailInRebate": 15, "freeShippingThreshold": 200,
        "fulfillmentMethod": "fba", "sharesIssued": 2000, "sharesBuyback": 2000,
        "newLoanAmount": 50000, "trainingHours": 80, "bestPracticesInvestment": 10000,
        "amazonAdBudget": 15000,
    })
    return d

def perm_decision_mid():
    return default_decision()

def perm_decision_superior():
    d = default_decision()
    d.update({
        "materialsQuality": "superior", "stylingBudget": 15000, "modelsOffered": 8,
    })
    return d

def perm_decision_celebrity():
    d = default_decision()
    d.update({
        "celebrityEndorsement": "global", "influencerTier": "mega",
        "tiktokBudget": 15000, "instagramBudget": 15000, "youtubeBudget": 15000,
    })
    return d

def perm_decision_fba():
    d = default_decision()
    d.update({
        "fulfillmentMethod": "fba", "amazonAdBudget": 15000, "productionQuantity": 600,
    })
    return d

def perm_decision_loan():
    d = default_decision()
    d.update({
        "newLoanAmount": 50000, "sharesIssued": 2000, "dividendsPerShare": 5.0,
    })
    return d

def perm_decision_overtime():
    d = default_decision()
    d.update({
        "overtimePercent": 20, "baseWage": 40000, "trainingHours": 80,
    })
    return d

def perm_decision_zero_ads():
    d = default_decision()
    d.update({
        "advertisingBudget": 0, "csrInvestment": 0,
        "tiktokBudget": 0, "instagramBudget": 0, "youtubeBudget": 0,
    })
    return d

def perm_decision_aggressive():
    d = default_decision()
    d.update({
        "wholesalePrice": 200, "internetPrice": 250, "amazonPrice": 200,
        "productionQuantity": 600, "advertisingBudget": 30000,
        "stylingBudget": 15000, "modelsOffered": 8,
    })
    return d

PERMUTATIONS = [
    ("All minimums", perm_decision_min),
    ("All maximums", perm_decision_max),
    ("All defaults/midpoints", perm_decision_mid),
    ("Superior materials + max styling + max models", perm_decision_superior),
    ("Celebrity endorsement + social media + influencer", perm_decision_celebrity),
    ("FBA + Amazon ads + high production", perm_decision_fba),
    ("Max loan + shares issued + high dividends", perm_decision_loan),
    ("Max overtime + high wage + max training", perm_decision_overtime),
    ("Zero advertising + zero CSR + zero social media", perm_decision_zero_ads),
    ("Balanced aggressive (high price, high production, high marketing)", perm_decision_aggressive),
]

# ── Revenue/Cost/Unit integrity checks ────────────────────────────────────
def check_revenue_channels(r, category, test_name):
    """Verify revenue channels sum to total."""
    rev_channels = (r.get("wholesaleRevenue", 0) + r.get("internetRevenue", 0) +
                    r.get("amazonRevenue", 0) + r.get("privateLabelRevenue", 0))
    total_rev = r.get("revenue", 0)
    passed = abs(rev_channels - total_rev) < 1.0
    record(category, f"{test_name} — revenue channels sum",
           passed, f"channels={rev_channels:.2f} vs total={total_rev:.2f}")
    return passed

def check_cost_components(r, category, test_name):
    """Verify cost components sum to total."""
    cost_components = (r.get("productionCost", 0) + r.get("workforceCosts", 0) +
                       r.get("marketingCost", 0) + r.get("csrCosts", 0) +
                       r.get("endorsementCosts", 0) + r.get("rebateCosts", 0) +
                       r.get("deliveryCosts", 0) + r.get("storageCosts", 0) +
                       r.get("interestExpense", 0) + r.get("dividendsPaid", 0) +
                       r.get("socialMediaCosts", 0) + r.get("amazonFees", 0))
    total_costs = r.get("costs", 0)
    passed = abs(cost_components - total_costs) < 1.0
    record(category, f"{test_name} — cost components sum",
           passed, f"components={cost_components:.2f} vs total={total_costs:.2f}")
    return passed

def check_units(r, category, test_name):
    """Verify units sum to total sold."""
    demand = r.get("demand", {})
    units = (r.get("wholesaleUnitsSold", 0) + r.get("internetUnitsSold", 0) +
             r.get("amazonUnitsSold", 0) + r.get("privateLabelUnitsSold", 0))
    total_sold = demand.get("totalSold", 0)
    passed = units == total_sold
    record(category, f"{test_name} — units sum to demand totalSold",
           passed, f"units={units} vs totalSold={total_sold}")
    return passed

def check_metrics(r, category, test_name):
    """Verify all display metrics are present."""
    metrics = ["revenue", "costs", "profit", "cash", "marketShare",
               "sqRating", "eps", "roe", "stockPrice", "imageRating",
               "creditRating", "customerSatisfaction", "rejectionRate", "awarenessScore"]
    missing = [m for m in metrics if m not in r]
    passed = len(missing) == 0
    record(category, f"{test_name} — all metrics present",
           passed, f"missing: {missing}" if missing else "all 14 metrics present")
    return passed


# ═══════════════════════════════════════════════════════════════════════════
# MAIN TEST SCRIPT
# ═══════════════════════════════════════════════════════════════════════════

def main():
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  Practenture Comprehensive E2E Test Suite                   ║")
    print("║  Target: http://18.215.180.58 (production)              ║")
    print(f"║  Started: {datetime.utcnow().isoformat()}               ║")
    print("╚══════════════════════════════════════════════════════════╝")

    # ── Login ──────────────────────────────────────────────────────────────
    category_header("Setup — Authentication")

    prof_resp = login("professor", "HAzRlxWuyxqz6G5HMvZL6Q")
    if prof_resp.status_code != 200:
        print(f"  ❌ FAIL — Professor login failed: {prof_resp.status_code} {prof_resp.text}")
        sys.exit(1)
    prof_data = prof_resp.json()
    prof_token = prof_data.get("accessToken") or prof_data.get("access_token")
    prof_user_id = prof_data.get("userId") or prof_data.get("user_id")
    record("Setup", "Professor login", True, f"role={prof_data.get('role')}, userId={prof_user_id}")

    stu1_resp = login("student1", "Student1@2026")
    if stu1_resp.status_code != 200:
        print(f"  ❌ FAIL — Student1 login failed: {stu1_resp.status_code} {stu1_resp.text}")
        sys.exit(1)
    stu1_data = stu1_resp.json()
    stu1_token = stu1_data.get("accessToken") or stu1_data.get("access_token")
    stu1_user_id = stu1_data.get("userId") or stu1_data.get("user_id")
    record("Setup", "Student1 login", True, f"role={stu1_data.get('role')}, userId={stu1_user_id}")

    # Register student2
    stu2_resp = register_student("student2", "Student2@2026", "Student Two", "student2")
    if stu2_resp.status_code == 201:
        record("Setup", "Student2 registration", True, f"status={stu2_resp.status_code}")
    elif stu2_resp.status_code == 409:
        record("Setup", "Student2 registration (already exists)", True, f"status={stu2_resp.status_code}")
    else:
        record("Setup", "Student2 registration", False, f"status={stu2_resp.status_code} {stu2_resp.text}")

    stu2_login = login("student2", "Student2@2026")
    if stu2_login.status_code != 200:
        print(f"  ❌ FAIL — Student2 login failed: {stu2_login.status_code} {stu2_login.text}")
        sys.exit(1)
    stu2_data = stu2_login.json()
    stu2_token = stu2_data.get("accessToken") or stu2_data.get("access_token")
    stu2_user_id = stu2_data.get("userId") or stu2_data.get("user_id")
    record("Setup", "Student2 login", True, f"role={stu2_data.get('role')}, userId={stu2_user_id}")

    # ═════════════════════════════════════════════════════════════════════
    # CATEGORY 1: Full Multi-Round Lifecycle (4 rounds)
    # ═════════════════════════════════════════════════════════════════════
    category_header("1. Full Multi-Round Lifecycle (4 rounds)")

    # Create session
    create_resp = create_session(prof_token, config={
        "totalRounds": 4, "numberOfAICompetitors": 2, "randomSeed": 42,
        "startingCash": 500000, "initialEquity": 300000, "plantCapacity": 10000,
        "maxOvertimePercent": 25, "minWage": 12000, "maxWage": 40000,
        "minDividend": 0, "maxDividend": 5.0, "marketType": "moderate",
        "aiDifficulty": "medium", "scoringMetric": "investor_score",
        "fixedCostsPerRound": 5000, "baseCostPerUnit": 30,
        "baseMarketDemand": 10000, "sharesOutstanding": 10000, "baseInterestRate": 0.06,
    })
    record("1. Lifecycle", "Create session", create_resp.status_code == 201,
           f"status={create_resp.status_code}")
    session_code = create_resp.json()["code"]
    session_id = create_resp.json()["sessionId"]
    print(f"    Session code: {session_code}")

    # Student1 joins
    join_resp = join_session(session_code, stu1_token, stu1_user_id, "Team Alpha")
    record("1. Lifecycle", "Student1 joins session", join_resp.status_code == 200,
           f"status={join_resp.status_code}, body={join_resp.json() if join_resp.status_code == 200 else join_resp.text}")

    # Get session to verify team and state
    sess = get_session(session_code, prof_token).json()
    record("1. Lifecycle", "Session is active after join",
           sess["state"] in ("active",), f"state={sess['state']}, round={sess['currentRound']}")

    # Run 4 rounds
    for rnd in range(1, 5):
        test_prefix = f"Round {rnd}"

        # Submit decision
        dec = default_decision()
        sub_resp = submit_decision(session_code, stu1_token, rnd, "Team Alpha", dec)
        record("1. Lifecycle", f"{test_prefix} — submit decision",
               sub_resp.status_code == 200, f"status={sub_resp.status_code}")

        # Process round
        proc_resp = process_round(session_code, prof_token)
        record("1. Lifecycle", f"{test_prefix} — process round",
               proc_resp.status_code == 200, f"status={proc_resp.status_code}")

        if proc_resp.status_code == 200:
            proc_data = proc_resp.json()
            results_list = proc_data.get("results", [])

            # Find our team's result
            our_result = None
            for r in results_list:
                if r["teamId"] == "Team Alpha":
                    our_result = r
                    break

            if our_result:
                # Verify all metrics present
                check_metrics(our_result, "1. Lifecycle", test_prefix)

                # Verify revenue channels
                check_revenue_channels(our_result, "1. Lifecycle", test_prefix)

                # Verify cost components
                check_cost_components(our_result, "1. Lifecycle", test_prefix)

                # Verify units
                check_units(our_result, "1. Lifecycle", test_prefix)

                # Verify profit = revenue - costs (approximately)
                calc_profit = our_result["revenue"] - our_result["costs"]
                record("1. Lifecycle", f"{test_prefix} — profit = revenue - costs",
                       abs(calc_profit - our_result["profit"]) < 1.0,
                       f"calc={calc_profit:.2f} vs reported={our_result['profit']:.2f}")

                # Verify credit rating is a letter grade
                cr = our_result.get("creditRating", "")
                record("1. Lifecycle", f"{test_prefix} — creditRating is letter",
                       isinstance(cr, str) and len(cr) <= 3,
                       f"creditRating={cr}")

                # Verify imageRating in 0-100 range
                ir = our_result.get("imageRating", -1)
                record("1. Lifecycle", f"{test_prefix} — imageRating 0-100",
                       0 <= ir <= 100, f"imageRating={ir}")
            else:
                record("1. Lifecycle", f"{test_prefix} — Team Alpha result found",
                       False, "Team Alpha not in results")

    # Export grades CSV
    grades_resp = export_grades(session_code, prof_token)
    record("1. Lifecycle", "Export grades CSV",
           grades_resp.status_code == 200, f"status={grades_resp.status_code}")

    if grades_resp.status_code == 200:
        csv_text = grades_resp.text
        csv_reader = csv.reader(io.StringIO(csv_text))
        csv_rows = list(csv_reader)
        if len(csv_rows) > 0:
            header = csv_rows[0]
            record("1. Lifecycle", "Grades CSV has header",
                   "Team" in header and "Round" in header, f"header={header[:5]}...")

            # Count data rows for Team Alpha
            alpha_rows = [r for r in csv_rows[1:] if r and r[0] == "Team Alpha"]
            record("1. Lifecycle", "Grades CSV has all 4 rounds for Team Alpha",
                   len(alpha_rows) == 4, f"found {len(alpha_rows)} rows")

            # Verify rounds 1-4 present
            alpha_rounds = sorted([int(r[1]) for r in alpha_rows]) if alpha_rows else []
            record("1. Lifecycle", "Grades CSV rounds are 1-4",
                   alpha_rounds == [1, 2, 3, 4], f"rounds={alpha_rounds}")
        else:
            record("1. Lifecycle", "Grades CSV has content", False, "empty CSV")

    # Get leaderboard
    lb_resp = get_leaderboard(session_code, prof_token)
    record("1. Lifecycle", "Get leaderboard",
           lb_resp.status_code == 200, f"status={lb_resp.status_code}")

    if lb_resp.status_code == 200:
        lb_data = lb_resp.json()
        entries = lb_data.get("leaderboard", [])
        record("1. Lifecycle", "Leaderboard has entries",
               len(entries) > 0, f"{len(entries)} entries")

        # Verify sorted by totalScore descending
        scores = [e.get("totalScore", 0) for e in entries]
        sorted_scores = sorted(scores, reverse=True)
        record("1. Lifecycle", "Leaderboard sorted by totalScore desc",
               scores == sorted_scores, f"scores={scores}")

        # Verify ranks are sequential
        ranks = [e.get("rank", 0) for e in entries]
        record("1. Lifecycle", "Leaderboard ranks are sequential",
               ranks == list(range(1, len(ranks) + 1)),
               f"ranks={ranks}")

    # ═════════════════════════════════════════════════════════════════════
    # CATEGORY 2: Idempotent Re-join
    # ═════════════════════════════════════════════════════════════════════
    category_header("2. Idempotent Re-join")

    # Create new session for re-join tests
    rejoin_create = create_session(prof_token, config={
        "totalRounds": 4, "numberOfAICompetitors": 1, "randomSeed": 99,
        "startingCash": 500000, "initialEquity": 300000, "plantCapacity": 10000,
        "maxOvertimePercent": 25, "minWage": 12000, "maxWage": 40000,
        "minDividend": 0, "maxDividend": 5.0, "marketType": "moderate",
        "aiDifficulty": "medium", "scoringMetric": "investor_score",
        "fixedCostsPerRound": 5000, "baseCostPerUnit": 30,
        "baseMarketDemand": 10000, "sharesOutstanding": 10000, "baseInterestRate": 0.06,
    })
    rejoin_code = rejoin_create.json()["code"]
    print(f"    Re-join session code: {rejoin_code}")

    # Student1 joins first time
    j1 = join_session(rejoin_code, stu1_token, stu1_user_id, "Team Rejoin1")
    record("2. Re-join", "Student1 joins first time",
           j1.status_code == 200, f"status={j1.status_code}")

    # Student1 re-joins same team (idempotent)
    j2 = join_session(rejoin_code, stu1_token, stu1_user_id, "Team Rejoin1")
    record("2. Re-join", "Student1 re-joins same team (idempotent)",
           j2.status_code == 200, f"status={j2.status_code}, body={j2.json() if j2.status_code == 200 else j2.text}")

    # Student2 tries to join team already taken by student1 → 409
    j3 = join_session(rejoin_code, stu2_token, stu2_user_id, "Team Rejoin1")
    record("2. Re-join", "Student2 tries team taken by student1 → 409",
           j3.status_code == 409, f"status={j3.status_code}, detail={j3.text}")

    # Student2 joins a different team
    j4 = join_session(rejoin_code, stu2_token, stu2_user_id, "Team Rejoin2")
    record("2. Re-join", "Student2 joins different team",
           j4.status_code == 200, f"status={j4.status_code}")

    # Student1 submits + process round, then re-joins → verify round advanced
    sub_r1 = submit_decision(rejoin_code, stu1_token, 1, "Team Rejoin1", default_decision())
    record("2. Re-join", "Student1 submits round 1",
           sub_r1.status_code == 200, f"status={sub_r1.status_code}")

    sub_r2 = submit_decision(rejoin_code, stu2_token, 1, "Team Rejoin2", default_decision())
    record("2. Re-join", "Student2 submits round 1",
           sub_r2.status_code == 200, f"status={sub_r2.status_code}")

    proc_r1 = process_round(rejoin_code, prof_token)
    record("2. Re-join", "Process round 1",
           proc_r1.status_code == 200, f"status={proc_r1.status_code}")

    # Student1 re-joins after round processed
    j5 = join_session(rejoin_code, stu1_token, stu1_user_id, "Team Rejoin1")
    if j5.status_code == 200:
        round_after = j5.json().get("round", 0)
        record("2. Re-join", "Re-join after round processed — round advanced",
               round_after == 2, f"round={round_after}")
    else:
        record("2. Re-join", "Re-join after round processed", False, f"status={j5.status_code}")

    # Join non-existent session → 404
    j6 = join_session("FAKE123456", stu1_token, stu1_user_id, "Team X")
    record("2. Re-join", "Join non-existent session → 404",
           j6.status_code == 404, f"status={j6.status_code}")

    # Join with invalid code (empty/garbage) → 404
    j7 = join_session("INVALID", stu1_token, stu1_user_id, "Team Y")
    record("2. Re-join", "Join with invalid code → 404",
           j7.status_code == 404, f"status={j7.status_code}")

    # ═════════════════════════════════════════════════════════════════════
    # CATEGORY 3: Decision Parameter Permutations (10 rounds)
    # ═════════════════════════════════════════════════════════════════════
    category_header("3. Decision Parameter Permutations")

    # Create a session with 10 rounds for permutation tests
    perm_create = create_session(prof_token, config={
        "totalRounds": 10, "numberOfAICompetitors": 1, "randomSeed": 77,
        "startingCash": 500000, "initialEquity": 300000, "plantCapacity": 10000,
        "maxOvertimePercent": 25, "minWage": 12000, "maxWage": 40000,
        "minDividend": 0, "maxDividend": 5.0, "marketType": "moderate",
        "aiDifficulty": "medium", "scoringMetric": "investor_score",
        "fixedCostsPerRound": 5000, "baseCostPerUnit": 30,
        "baseMarketDemand": 10000, "sharesOutstanding": 10000, "baseInterestRate": 0.06,
    })
    perm_code = perm_create.json()["code"]
    print(f"    Permutation session code: {perm_code}")

    # Student1 joins
    pj = join_session(perm_code, stu1_token, stu1_user_id, "PermTeam")
    record("3. Permutations", "Student1 joins permutation session",
           pj.status_code == 200, f"status={pj.status_code}")

    for i, (perm_name, perm_fn) in enumerate(PERMUTATIONS):
        rnd = i + 1
        dec = perm_fn()

        # Submit
        ps = submit_decision(perm_code, stu1_token, rnd, "PermTeam", dec)
        record("3. Permutations", f"Permutation {rnd}: {perm_name} — submit",
               ps.status_code == 200, f"status={ps.status_code}")

        # Process
        pp = process_round(perm_code, prof_token)
        record("3. Permutations", f"Permutation {rnd}: {perm_name} — process",
               pp.status_code == 200, f"status={pp.status_code}")

        if pp.status_code == 200:
            proc_data = pp.json()
            results_list = proc_data.get("results", [])
            our_result = None
            for r in results_list:
                if r["teamId"] == "PermTeam":
                    our_result = r
                    break
            if our_result:
                # Revenue channels
                check_revenue_channels(our_result, "3. Permutations", f"Perm {rnd}: {perm_name}")
                # Cost components
                check_cost_components(our_result, "3. Permutations", f"Perm {rnd}: {perm_name}")
                # Units
                check_units(our_result, "3. Permutations", f"Perm {rnd}: {perm_name}")
                # Metrics
                check_metrics(our_result, "3. Permutations", f"Perm {rnd}: {perm_name}")

    # ═════════════════════════════════════════════════════════════════════
    # CATEGORY 4: Edge Cases & Security
    # ═════════════════════════════════════════════════════════════════════
    category_header("4. Edge Cases & Security")

    # Create session for edge case tests
    edge_create = create_session(prof_token, config={
        "totalRounds": 4, "numberOfAICompetitors": 1, "randomSeed": 55,
        "startingCash": 500000, "initialEquity": 300000, "plantCapacity": 10000,
        "maxOvertimePercent": 25, "minWage": 12000, "maxWage": 40000,
        "minDividend": 0, "maxDividend": 5.0, "marketType": "moderate",
        "aiDifficulty": "medium", "scoringMetric": "investor_score",
        "fixedCostsPerRound": 5000, "baseCostPerUnit": 30,
        "baseMarketDemand": 10000, "sharesOutstanding": 10000, "baseInterestRate": 0.06,
    })
    edge_code = edge_create.json()["code"]
    print(f"    Edge case session code: {edge_code}")

    # Student1 joins
    ej = join_session(edge_code, stu1_token, stu1_user_id, "EdgeTeam")
    record("4. Edge Cases", "Student1 joins edge session",
           ej.status_code == 200, f"status={ej.status_code}")

    # Double submit (same round, same team) → 409
    ds1 = submit_decision(edge_code, stu1_token, 1, "EdgeTeam", default_decision())
    ds2 = submit_decision(edge_code, stu1_token, 1, "EdgeTeam", default_decision())
    record("4. Edge Cases", "Double submit same round → 409",
           ds2.status_code == 409, f"first={ds1.status_code}, second={ds2.status_code}")

    # Process round 1 to advance
    ep1 = process_round(edge_code, prof_token)
    record("4. Edge Cases", "Process round 1 after double-submit test",
           ep1.status_code == 200, f"status={ep1.status_code}")

    # Submit for wrong round (round 5 when current is 2) → 400
    wr = submit_decision(edge_code, stu1_token, 5, "EdgeTeam", default_decision())
    record("4. Edge Cases", "Submit for wrong round → 400",
           wr.status_code == 400, f"status={wr.status_code}, detail={wr.text}")

    # Submit as professor → 403
    sp = submit_decision(edge_code, prof_token, 2, "EdgeTeam", default_decision())
    record("4. Edge Cases", "Submit as professor → 403",
           sp.status_code == 403, f"status={sp.status_code}")

    # Submit to non-existent team → 400
    nt = submit_decision(edge_code, stu1_token, 2, "NonExistentTeam", default_decision())
    record("4. Edge Cases", "Submit to non-existent team → 400",
           nt.status_code == 400, f"status={nt.status_code}")

    # Process round as student → 403
    ps_student = process_round(edge_code, stu1_token)
    record("4. Edge Cases", "Process round as student → 403",
           ps_student.status_code == 403, f"status={ps_student.status_code}")

    # Process round without submissions → 409
    # Create a fresh session with no submissions
    nosub_create = create_session(prof_token, config={
        "totalRounds": 4, "numberOfAICompetitors": 0, "randomSeed": 33,
        "startingCash": 500000, "initialEquity": 300000, "plantCapacity": 10000,
        "maxOvertimePercent": 25, "minWage": 12000, "maxWage": 40000,
        "minDividend": 0, "maxDividend": 5.0, "marketType": "moderate",
        "aiDifficulty": "medium", "scoringMetric": "investor_score",
        "fixedCostsPerRound": 5000, "baseCostPerUnit": 30,
        "baseMarketDemand": 10000, "sharesOutstanding": 10000, "baseInterestRate": 0.06,
    })
    nosub_code = nosub_create.json()["code"]
    nosub_join = join_session(nosub_code, stu1_token, stu1_user_id, "NoSubTeam")
    # Don't submit anything, try to process
    nosub_proc = process_round(nosub_code, prof_token)
    record("4. Edge Cases", "Process round without submissions → 409",
           nosub_proc.status_code == 409, f"status={nosub_proc.status_code}")

    # Process round twice — second should work for next round
    # Submit for round 2 on edge_code
    s2 = submit_decision(edge_code, stu1_token, 2, "EdgeTeam", default_decision())
    record("4. Edge Cases", "Submit round 2",
           s2.status_code == 200, f"status={s2.status_code}")

    p2a = process_round(edge_code, prof_token)
    record("4. Edge Cases", "Process round 2 (first)",
           p2a.status_code == 200, f"status={p2a.status_code}")

    # Try to process again without new submission → 409
    p2b = process_round(edge_code, prof_token)
    record("4. Edge Cases", "Process round 3 without submission → 409",
           p2b.status_code == 409, f"status={p2b.status_code}")

    # Get session without auth → 401
    no_auth = requests.get(f"{BASE_URL}/api/sessions/{edge_code}", timeout=TIMEOUT)
    record("4. Edge Cases", "Get session without auth → 401",
           no_auth.status_code == 401, f"status={no_auth.status_code}")

    # Delete session as student → 403
    del_student = delete_session(edge_code, stu1_token)
    record("4. Edge Cases", "Delete session as student → 403",
           del_student.status_code == 403, f"status={del_student.status_code}")

    # Student send announcement → 403
    sa = create_announcement(edge_code, stu1_token, "hack attempt")
    record("4. Edge Cases", "Student send announcement → 403",
           sa.status_code == 403, f"status={sa.status_code}")

    # Professor send announcement → 200/201
    pa = create_announcement(edge_code, prof_token, "Welcome to Practenture!")
    record("4. Edge Cases", "Professor send announcement → 200/201",
           pa.status_code in (200, 201), f"status={pa.status_code}")

    # ═════════════════════════════════════════════════════════════════════
    # CATEGORY 5: Data Integrity After Re-join
    # ═════════════════════════════════════════════════════════════════════
    category_header("5. Data Integrity After Re-join")

    # Create session for data integrity tests
    integrity_create = create_session(prof_token, config={
        "totalRounds": 4, "numberOfAICompetitors": 1, "randomSeed": 88,
        "startingCash": 500000, "initialEquity": 300000, "plantCapacity": 10000,
        "maxOvertimePercent": 25, "minWage": 12000, "maxWage": 40000,
        "minDividend": 0, "maxDividend": 5.0, "marketType": "moderate",
        "aiDifficulty": "medium", "scoringMetric": "investor_score",
        "fixedCostsPerRound": 5000, "baseCostPerUnit": 30,
        "baseMarketDemand": 10000, "sharesOutstanding": 10000, "baseInterestRate": 0.06,
    })
    integrity_code = integrity_create.json()["code"]
    print(f"    Data integrity session code: {integrity_code}")

    # Student1 joins
    ij = join_session(integrity_code, stu1_token, stu1_user_id, "IntegrityTeam")
    record("5. Data Integrity", "Student1 joins integrity session",
           ij.status_code == 200, f"status={ij.status_code}")

    # Play 2 rounds
    for rnd in range(1, 3):
        sd = submit_decision(integrity_code, stu1_token, rnd, "IntegrityTeam", default_decision())
        record("5. Data Integrity", f"Submit round {rnd}",
               sd.status_code == 200, f"status={sd.status_code}")

        pr = process_round(integrity_code, prof_token)
        record("5. Data Integrity", f"Process round {rnd}",
               pr.status_code == 200, f"status={pr.status_code}")

    # Capture results after 2 rounds
    sess_before = get_session(integrity_code, prof_token).json()
    lb_before = get_leaderboard(integrity_code, prof_token).json()

    # Get the team's last result
    lb_entries_before = lb_before.get("leaderboard", [])
    team_entry_before = None
    for e in lb_entries_before:
        if e["teamName"] == "IntegrityTeam":
            team_entry_before = e
            break

    # Simulate "leaving" — student logs in fresh (new token)
    stu1_relogin = login("student1", "Student1@2026")
    stu1_new_token = stu1_relogin.json().get("accessToken") or stu1_relogin.json().get("access_token")
    record("5. Data Integrity", "Student1 re-login (simulate leave/rejoin)",
           stu1_relogin.status_code == 200, f"status={stu1_relogin.status_code}")

    # Re-join same session
    rj = join_session(integrity_code, stu1_new_token, stu1_user_id, "IntegrityTeam")
    record("5. Data Integrity", "Student1 re-joins after re-login",
           rj.status_code == 200, f"status={rj.status_code}")

    if rj.status_code == 200:
        rj_data = rj.json()
        record("5. Data Integrity", "Re-join shows correct round (3)",
               rj_data.get("round") == 3, f"round={rj_data.get('round')}")

    # Verify session state unchanged
    sess_after = get_session(integrity_code, prof_token).json()
    record("5. Data Integrity", "Session round unchanged after rejoin",
           sess_after["currentRound"] == sess_before["currentRound"],
           f"before={sess_before['currentRound']}, after={sess_after['currentRound']}")

    # Verify leaderboard unchanged
    lb_after = get_leaderboard(integrity_code, prof_token).json()
    lb_entries_after = lb_after.get("leaderboard", [])

    record("5. Data Integrity", "Leaderboard entry count unchanged",
           len(lb_entries_before) == len(lb_entries_after),
           f"before={len(lb_entries_before)}, after={len(lb_entries_after)}")

    # Verify team financial state
    team_entry_after = None
    for e in lb_entries_after:
        if e["teamName"] == "IntegrityTeam":
            team_entry_after = e
            break

    if team_entry_before and team_entry_after:
        fields_to_check = ["totalScore", "eps", "roe", "stockPrice", "imageRating", "creditRating",
                           "cumulativeProfit", "marketShare"]
        all_match = True
        mismatches = []
        for f in fields_to_check:
            vb = team_entry_before.get(f)
            va = team_entry_after.get(f)
            if vb != va:
                all_match = False
                mismatches.append(f"{f}: before={vb}, after={va}")
        record("5. Data Integrity", "Team financial state restored after rejoin",
               all_match, f"mismatches: {mismatches}" if mismatches else "all fields match")

    # Verify rankings still correct
    scores_after = [e.get("totalScore", 0) for e in lb_entries_after]
    sorted_after = sorted(scores_after, reverse=True)
    record("5. Data Integrity", "Leaderboard still sorted after rejoin",
           scores_after == sorted_after, f"scores={scores_after}")

    # ═════════════════════════════════════════════════════════════════════
    # CATEGORY 6: Export & Reporting
    # ═════════════════════════════════════════════════════════════════════
    category_header("6. Export & Reporting")

    # Use the 4-round lifecycle session for export tests
    # Export grades CSV
    g_resp = export_grades(session_code, prof_token)
    record("6. Export", "Export grades CSV",
           g_resp.status_code == 200, f"status={g_resp.status_code}")

    if g_resp.status_code == 200:
        csv_text = g_resp.text
        csv_reader = csv.reader(io.StringIO(csv_text))
        csv_rows = list(csv_reader)

        # Verify header
        if len(csv_rows) > 0:
            header = csv_rows[0]
            expected_cols = ["Team", "Round", "Revenue", "Costs", "Profit", "EPS", "ROE", "Stock Price", "Total Score"]
            has_all = all(c in header for c in expected_cols)
            record("6. Export", "CSV header has all expected columns",
                   has_all, f"header has {len(header)} cols")

            # Verify all teams present (Team Alpha + AI teams)
            teams_in_csv = set()
            for row in csv_rows[1:]:
                if row:
                    teams_in_csv.add(row[0])
            record("6. Export", "CSV contains all teams",
                   "Team Alpha" in teams_in_csv, f"teams={teams_in_csv}")

            # Verify all rounds present
            rounds_in_csv = set()
            for row in csv_rows[1:]:
                if row and len(row) > 1:
                    try:
                        rounds_in_csv.add(int(row[1]))
                    except ValueError:
                        pass
            record("6. Export", "CSV contains all rounds 1-4",
                   rounds_in_csv == {1, 2, 3, 4}, f"rounds={sorted(rounds_in_csv)}")

    # Leaderboard sorted by totalScore descending
    lb_final = get_leaderboard(session_code, prof_token)
    if lb_final.status_code == 200:
        lb_data = lb_final.json()
        entries = lb_data.get("leaderboard", [])
        scores = [e.get("totalScore", 0) for e in entries]
        sorted_desc = sorted(scores, reverse=True)
        record("6. Export", "Leaderboard sorted by totalScore desc",
               scores == sorted_desc, f"scores={scores}")

        # Verify ranks
        ranks = [e.get("rank", 0) for e in entries]
        record("6. Export", "Leaderboard ranks sequential",
               ranks == list(range(1, len(ranks) + 1)), f"ranks={ranks}")

    # Get announcements
    ann_resp = get_announcements(session_code, prof_token)
    record("6. Export", "Get announcements",
           ann_resp.status_code == 200, f"status={ann_resp.status_code}")

    if ann_resp.status_code == 200:
        ann_list = ann_resp.json()
        record("6. Export", "Announcements is a list",
               isinstance(ann_list, list), f"type={type(ann_list).__name__}, count={len(ann_list)}")

    # ═════════════════════════════════════════════════════════════════════
    # CLEANUP — Delete test sessions
    # ═════════════════════════════════════════════════════════════════════
    category_header("Cleanup")
    for code, name in [
        (session_code, "Lifecycle"), (rejoin_code, "Re-join"),
        (perm_code, "Permutations"), (edge_code, "Edge cases"),
        (nosub_code, "No-submissions"), (integrity_code, "Data integrity"),
    ]:
        try:
            d = delete_session(code, prof_token)
            record("Cleanup", f"Delete {name} session ({code})",
                   d.status_code in (200, 204), f"status={d.status_code}")
        except Exception as e:
            record("Cleanup", f"Delete {name} session ({code})", False, str(e))

    # ── Final Summary ─────────────────────────────────────────────────────
    total_pass, total_fail = summary()

    # ── Write markdown report ─────────────────────────────────────────────
    md_lines = []
    md_lines.append("# Practenture Comprehensive E2E Test Results")
    md_lines.append("")
    md_lines.append(f"**Date:** {datetime.utcnow().isoformat()}")
    md_lines.append(f"**Backend:** {BASE_URL}")
    md_lines.append(f"**Total Tests:** {total_pass + total_fail}")
    md_lines.append(f"**Passed:** {total_pass}")
    md_lines.append(f"**Failed:** {total_fail}")
    md_lines.append(f"**Pass Rate:** {total_pass/(total_pass+total_fail)*100:.1f}%")
    md_lines.append("")

    # Summary table
    md_lines.append("## Summary by Category")
    md_lines.append("")
    md_lines.append("| Category | Pass | Fail | Total |")
    md_lines.append("|----------|------|------|-------|")
    cats = {}
    for r in results:
        cat = r["category"]
        if cat not in cats:
            cats[cat] = {"pass": 0, "fail": 0}
        if r["passed"]:
            cats[cat]["pass"] += 1
        else:
            cats[cat]["fail"] += 1
    for cat in sorted(cats.keys()):
        total = cats[cat]["pass"] + cats[cat]["fail"]
        md_lines.append(f"| {cat} | {cats[cat]['pass']} | {cats[cat]['fail']} | {total} |")
    md_lines.append(f"| **TOTAL** | **{total_pass}** | **{total_fail}** | **{total_pass+total_fail}** |")
    md_lines.append("")

    # Detailed results
    md_lines.append("## Detailed Test Results")
    md_lines.append("")
    current_cat = ""
    for r in results:
        if r["category"] != current_cat:
            current_cat = r["category"]
            md_lines.append(f"### {current_cat}")
            md_lines.append("")
            md_lines.append("| Status | Test | Details |")
            md_lines.append("|--------|------|---------|")
        status = "✅ PASS" if r["passed"] else "❌ FAIL"
        detail = r["detail"].replace("|", "\\|") if r["detail"] else ""
        test = r["test"].replace("|", "\\|")
        md_lines.append(f"| {status} | {test} | {detail} |")
    md_lines.append("")

    # Failed tests section
    failed = [r for r in results if not r["passed"]]
    if failed:
        md_lines.append("## Failed Tests")
        md_lines.append("")
        for r in failed:
            md_lines.append(f"- **{r['category']} → {r['test']}**: {r['detail']}")
        md_lines.append("")

    md_content = "\n".join(md_lines)
    output_path = "/Users/luisborges/2026/Practenture-ios/Practenture/docs/e2e-test-results.md"
    with open(output_path, "w") as f:
        f.write(md_content)
    print(f"\n📄 Results written to {output_path}")

    return total_fail

if __name__ == "__main__":
    fail_count = main()
    sys.exit(1 if fail_count > 0 else 0)
