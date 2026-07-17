# BizSimAI Comprehensive E2E Test Results

**Date:** 2026-07-17T00:15:13.649966
**Backend:** http://18.215.180.58
**Total Tests:** 163
**Passed:** 163
**Failed:** 0
**Pass Rate:** 100.0%

## Summary by Category

| Category | Pass | Fail | Total |
|----------|------|------|-------|
| 1. Lifecycle | 47 | 0 | 47 |
| 2. Re-join | 10 | 0 | 10 |
| 3. Permutations | 61 | 0 | 61 |
| 4. Edge Cases | 15 | 0 | 15 |
| 5. Data Integrity | 12 | 0 | 12 |
| 6. Export | 8 | 0 | 8 |
| Cleanup | 6 | 0 | 6 |
| Setup | 4 | 0 | 4 |
| **TOTAL** | **163** | **0** | **163** |

## Detailed Test Results

### Setup

| Status | Test | Details |
|--------|------|---------|
| ✅ PASS | Professor login | role=professor, userId=professor |
| ✅ PASS | Student1 login | role=student, userId=student1 |
| ✅ PASS | Student2 registration | status=201 |
| ✅ PASS | Student2 login | role=student, userId=student2 |
### 1. Lifecycle

| Status | Test | Details |
|--------|------|---------|
| ✅ PASS | Create session | status=201 |
| ✅ PASS | Student1 joins session | status=200, body={'teamId': 'Team Alpha', 'teamName': 'Team Alpha', 'round': 1, 'state': 'active'} |
| ✅ PASS | Session is active after join | state=active, round=1 |
| ✅ PASS | Round 1 — submit decision | status=200 |
| ✅ PASS | Round 1 — process round | status=200 |
| ✅ PASS | Round 1 — all metrics present | all 14 metrics present |
| ✅ PASS | Round 1 — revenue channels sum | channels=13700.00 vs total=13700.00 |
| ✅ PASS | Round 1 — cost components sum | components=35187.50 vs total=35187.50 |
| ✅ PASS | Round 1 — units sum to demand totalSold | units=163 vs totalSold=163.0 |
| ✅ PASS | Round 1 — profit = revenue - costs | calc=-21487.50 vs reported=-21487.50 |
| ✅ PASS | Round 1 — creditRating is letter | creditRating=A+ |
| ✅ PASS | Round 1 — imageRating 0-100 | imageRating=53.28 |
| ✅ PASS | Round 2 — submit decision | status=200 |
| ✅ PASS | Round 2 — process round | status=200 |
| ✅ PASS | Round 2 — all metrics present | all 14 metrics present |
| ✅ PASS | Round 2 — revenue channels sum | channels=13130.00 vs total=13130.00 |
| ✅ PASS | Round 2 — cost components sum | components=35286.50 vs total=35286.50 |
| ✅ PASS | Round 2 — units sum to demand totalSold | units=156 vs totalSold=156.0 |
| ✅ PASS | Round 2 — profit = revenue - costs | calc=-22156.50 vs reported=-22156.50 |
| ✅ PASS | Round 2 — creditRating is letter | creditRating=A+ |
| ✅ PASS | Round 2 — imageRating 0-100 | imageRating=53.52 |
| ✅ PASS | Round 3 — submit decision | status=200 |
| ✅ PASS | Round 3 — process round | status=200 |
| ✅ PASS | Round 3 — all metrics present | all 14 metrics present |
| ✅ PASS | Round 3 — revenue channels sum | channels=10665.00 vs total=10665.00 |
| ✅ PASS | Round 3 — cost components sum | components=34876.25 vs total=34876.25 |
| ✅ PASS | Round 3 — units sum to demand totalSold | units=127 vs totalSold=127.0 |
| ✅ PASS | Round 3 — profit = revenue - costs | calc=-24211.25 vs reported=-24211.25 |
| ✅ PASS | Round 3 — creditRating is letter | creditRating=A+ |
| ✅ PASS | Round 3 — imageRating 0-100 | imageRating=53.88 |
| ✅ PASS | Round 4 — submit decision | status=200 |
| ✅ PASS | Round 4 — process round | status=200 |
| ✅ PASS | Round 4 — all metrics present | all 14 metrics present |
| ✅ PASS | Round 4 — revenue channels sum | channels=12780.00 vs total=12780.00 |
| ✅ PASS | Round 4 — cost components sum | components=35229.50 vs total=35229.50 |
| ✅ PASS | Round 4 — units sum to demand totalSold | units=152 vs totalSold=152.0 |
| ✅ PASS | Round 4 — profit = revenue - costs | calc=-22449.50 vs reported=-22449.50 |
| ✅ PASS | Round 4 — creditRating is letter | creditRating=A+ |
| ✅ PASS | Round 4 — imageRating 0-100 | imageRating=54.24 |
| ✅ PASS | Export grades CSV | status=200 |
| ✅ PASS | Grades CSV has header | header=['Team', 'Round', 'Revenue', 'Costs', 'Profit']... |
| ✅ PASS | Grades CSV has all 4 rounds for Team Alpha | found 4 rows |
| ✅ PASS | Grades CSV rounds are 1-4 | rounds=[1, 2, 3, 4] |
| ✅ PASS | Get leaderboard | status=200 |
| ✅ PASS | Leaderboard has entries | 3 entries |
| ✅ PASS | Leaderboard sorted by totalScore desc | scores=[46.83, 20.69, 20.68] |
| ✅ PASS | Leaderboard ranks are sequential | ranks=[1, 2, 3] |
### 2. Re-join

| Status | Test | Details |
|--------|------|---------|
| ✅ PASS | Student1 joins first time | status=200 |
| ✅ PASS | Student1 re-joins same team (idempotent) | status=200, body={'teamId': 'Team Rejoin1', 'teamName': 'Team Rejoin1', 'round': 1, 'state': 'active'} |
| ✅ PASS | Student2 tries team taken by student1 → 409 | status=409, detail={"detail":"Team name already taken by another student"} |
| ✅ PASS | Student2 joins different team | status=200 |
| ✅ PASS | Student1 submits round 1 | status=200 |
| ✅ PASS | Student2 submits round 1 | status=200 |
| ✅ PASS | Process round 1 | status=200 |
| ✅ PASS | Re-join after round processed — round advanced | round=2 |
| ✅ PASS | Join non-existent session → 404 | status=404 |
| ✅ PASS | Join with invalid code → 404 | status=404 |
### 3. Permutations

| Status | Test | Details |
|--------|------|---------|
| ✅ PASS | Student1 joins permutation session | status=200 |
| ✅ PASS | Permutation 1: All minimums — submit | status=200 |
| ✅ PASS | Permutation 1: All minimums — process | status=200 |
| ✅ PASS | Perm 1: All minimums — revenue channels sum | channels=0.00 vs total=0.00 |
| ✅ PASS | Perm 1: All minimums — cost components sum | components=5265.00 vs total=5265.00 |
| ✅ PASS | Perm 1: All minimums — units sum to demand totalSold | units=0 vs totalSold=0.0 |
| ✅ PASS | Perm 1: All minimums — all metrics present | all 14 metrics present |
| ✅ PASS | Permutation 2: All maximums — submit | status=200 |
| ✅ PASS | Permutation 2: All maximums — process | status=200 |
| ✅ PASS | Perm 2: All maximums — revenue channels sum | channels=85750.00 vs total=85750.00 |
| ✅ PASS | Perm 2: All maximums — cost components sum | components=317235.50 vs total=317235.50 |
| ✅ PASS | Perm 2: All maximums — units sum to demand totalSold | units=421 vs totalSold=421.0 |
| ✅ PASS | Perm 2: All maximums — all metrics present | all 14 metrics present |
| ✅ PASS | Permutation 3: All defaults/midpoints — submit | status=200 |
| ✅ PASS | Permutation 3: All defaults/midpoints — process | status=200 |
| ✅ PASS | Perm 3: All defaults/midpoints — revenue channels sum | channels=27700.00 vs total=27700.00 |
| ✅ PASS | Perm 3: All defaults/midpoints — cost components sum | components=39540.50 vs total=39540.50 |
| ✅ PASS | Perm 3: All defaults/midpoints — units sum to demand totalSold | units=349 vs totalSold=349.0 |
| ✅ PASS | Perm 3: All defaults/midpoints — all metrics present | all 14 metrics present |
| ✅ PASS | Permutation 4: Superior materials + max styling + max models — submit | status=200 |
| ✅ PASS | Permutation 4: Superior materials + max styling + max models — process | status=200 |
| ✅ PASS | Perm 4: Superior materials + max styling + max models — revenue channels sum | channels=15085.00 vs total=15085.00 |
| ✅ PASS | Perm 4: Superior materials + max styling + max models — cost components sum | components=54258.50 vs total=54258.50 |
| ✅ PASS | Perm 4: Superior materials + max styling + max models — units sum to demand totalSold | units=188 vs totalSold=188.0 |
| ✅ PASS | Perm 4: Superior materials + max styling + max models — all metrics present | all 14 metrics present |
| ✅ PASS | Permutation 5: Celebrity endorsement + social media + influencer — submit | status=200 |
| ✅ PASS | Permutation 5: Celebrity endorsement + social media + influencer — process | status=200 |
| ✅ PASS | Perm 5: Celebrity endorsement + social media + influencer — revenue channels sum | channels=15060.00 vs total=15060.00 |
| ✅ PASS | Perm 5: Celebrity endorsement + social media + influencer — cost components sum | components=170359.50 vs total=170359.50 |
| ✅ PASS | Perm 5: Celebrity endorsement + social media + influencer — units sum to demand totalSold | units=188 vs totalSold=188.0 |
| ✅ PASS | Perm 5: Celebrity endorsement + social media + influencer — all metrics present | all 14 metrics present |
| ✅ PASS | Permutation 6: FBA + Amazon ads + high production — submit | status=200 |
| ✅ PASS | Permutation 6: FBA + Amazon ads + high production — process | status=200 |
| ✅ PASS | Perm 6: FBA + Amazon ads + high production — revenue channels sum | channels=41455.00 vs total=41455.00 |
| ✅ PASS | Perm 6: FBA + Amazon ads + high production — cost components sum | components=73628.25 vs total=73628.25 |
| ✅ PASS | Perm 6: FBA + Amazon ads + high production — units sum to demand totalSold | units=514 vs totalSold=514.0 |
| ✅ PASS | Perm 6: FBA + Amazon ads + high production — all metrics present | all 14 metrics present |
| ✅ PASS | Permutation 7: Max loan + shares issued + high dividends — submit | status=200 |
| ✅ PASS | Permutation 7: Max loan + shares issued + high dividends — process | status=200 |
| ✅ PASS | Perm 7: Max loan + shares issued + high dividends — revenue channels sum | channels=18375.00 vs total=18375.00 |
| ✅ PASS | Perm 7: Max loan + shares issued + high dividends — cost components sum | components=95801.25 vs total=95801.25 |
| ✅ PASS | Perm 7: Max loan + shares issued + high dividends — units sum to demand totalSold | units=236 vs totalSold=236.0 |
| ✅ PASS | Perm 7: Max loan + shares issued + high dividends — all metrics present | all 14 metrics present |
| ✅ PASS | Permutation 8: Max overtime + high wage + max training — submit | status=200 |
| ✅ PASS | Permutation 8: Max overtime + high wage + max training — process | status=200 |
| ✅ PASS | Perm 8: Max overtime + high wage + max training — revenue channels sum | channels=14835.00 vs total=14835.00 |
| ✅ PASS | Perm 8: Max overtime + high wage + max training — cost components sum | components=47233.50 vs total=47233.50 |
| ✅ PASS | Perm 8: Max overtime + high wage + max training — units sum to demand totalSold | units=191 vs totalSold=191.0 |
| ✅ PASS | Perm 8: Max overtime + high wage + max training — all metrics present | all 14 metrics present |
| ✅ PASS | Permutation 9: Zero advertising + zero CSR + zero social media — submit | status=200 |
| ✅ PASS | Permutation 9: Zero advertising + zero CSR + zero social media — process | status=200 |
| ✅ PASS | Perm 9: Zero advertising + zero CSR + zero social media — revenue channels sum | channels=14485.00 vs total=14485.00 |
| ✅ PASS | Perm 9: Zero advertising + zero CSR + zero social media — cost components sum | components=39929.00 vs total=39929.00 |
| ✅ PASS | Perm 9: Zero advertising + zero CSR + zero social media — units sum to demand totalSold | units=188 vs totalSold=188.0 |
| ✅ PASS | Perm 9: Zero advertising + zero CSR + zero social media — all metrics present | all 14 metrics present |
| ✅ PASS | Permutation 10: Balanced aggressive (high price, high production, high marketing) — submit | status=200 |
| ✅ PASS | Permutation 10: Balanced aggressive (high price, high production, high marketing) — process | status=200 |
| ✅ PASS | Perm 10: Balanced aggressive (high price, high production, high marketing) — revenue channels sum | channels=35550.00 vs total=35550.00 |
| ✅ PASS | Perm 10: Balanced aggressive (high price, high production, high marketing) — cost components sum | components=98325.50 vs total=98325.50 |
| ✅ PASS | Perm 10: Balanced aggressive (high price, high production, high marketing) — units sum to demand totalSold | units=212 vs totalSold=212.0 |
| ✅ PASS | Perm 10: Balanced aggressive (high price, high production, high marketing) — all metrics present | all 14 metrics present |
### 4. Edge Cases

| Status | Test | Details |
|--------|------|---------|
| ✅ PASS | Student1 joins edge session | status=200 |
| ✅ PASS | Double submit same round → 409 | first=200, second=409 |
| ✅ PASS | Process round 1 after double-submit test | status=200 |
| ✅ PASS | Submit for wrong round → 400 | status=400, detail={"detail":"Current round is 2, cannot submit for round 5"} |
| ✅ PASS | Submit as professor → 403 | status=403 |
| ✅ PASS | Submit to non-existent team → 400 | status=400 |
| ✅ PASS | Process round as student → 403 | status=403 |
| ✅ PASS | Process round without submissions → 409 | status=409 |
| ✅ PASS | Submit round 2 | status=200 |
| ✅ PASS | Process round 2 (first) | status=200 |
| ✅ PASS | Process round 3 without submission → 409 | status=409 |
| ✅ PASS | Get session without auth → 401 | status=401 |
| ✅ PASS | Delete session as student → 403 | status=403 |
| ✅ PASS | Student send announcement → 403 | status=403 |
| ✅ PASS | Professor send announcement → 200/201 | status=200 |
### 5. Data Integrity

| Status | Test | Details |
|--------|------|---------|
| ✅ PASS | Student1 joins integrity session | status=200 |
| ✅ PASS | Submit round 1 | status=200 |
| ✅ PASS | Process round 1 | status=200 |
| ✅ PASS | Submit round 2 | status=200 |
| ✅ PASS | Process round 2 | status=200 |
| ✅ PASS | Student1 re-login (simulate leave/rejoin) | status=200 |
| ✅ PASS | Student1 re-joins after re-login | status=200 |
| ✅ PASS | Re-join shows correct round (3) | round=3 |
| ✅ PASS | Session round unchanged after rejoin | before=3, after=3 |
| ✅ PASS | Leaderboard entry count unchanged | before=2, after=2 |
| ✅ PASS | Team financial state restored after rejoin | all fields match |
| ✅ PASS | Leaderboard still sorted after rejoin | scores=[48.46, 21.07] |
### 6. Export

| Status | Test | Details |
|--------|------|---------|
| ✅ PASS | Export grades CSV | status=200 |
| ✅ PASS | CSV header has all expected columns | header has 30 cols |
| ✅ PASS | CSV contains all teams | teams={'Team Alpha', 'AI-Quality-2', 'AI-Aggressive-1'} |
| ✅ PASS | CSV contains all rounds 1-4 | rounds=[1, 2, 3, 4] |
| ✅ PASS | Leaderboard sorted by totalScore desc | scores=[46.83, 20.69, 20.68] |
| ✅ PASS | Leaderboard ranks sequential | ranks=[1, 2, 3] |
| ✅ PASS | Get announcements | status=200 |
| ✅ PASS | Announcements is a list | type=list, count=0 |
### Cleanup

| Status | Test | Details |
|--------|------|---------|
| ✅ PASS | Delete Lifecycle session (BIZ-DADF) | status=204 |
| ✅ PASS | Delete Re-join session (BIZ-8SK4) | status=204 |
| ✅ PASS | Delete Permutations session (BIZ-VEAT) | status=204 |
| ✅ PASS | Delete Edge cases session (BIZ-PZT6) | status=204 |
| ✅ PASS | Delete No-submissions session (BIZ-7DDB) | status=204 |
| ✅ PASS | Delete Data integrity session (BIZ-WKYX) | status=204 |
