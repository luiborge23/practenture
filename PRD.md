# Practenture — Product Requirements Document

## TL;DR

Practenture is a **cloud-connected business simulation platform** for MBA/business classrooms. Professors create and manage simulation sessions from a web dashboard; students join via an iOS app, make quarterly business decisions (pricing, production, marketing, R&D, financing), and compete in real-time against AI and human opponents. The backend (FastAPI + SQLite) runs a deterministic simulation engine, while the iOS app provides the student-facing interface with live dashboards, announcements, and CSV export. The platform supports three authentication methods (password, Apple Sign-In, Google Sign-In) via JWT tokens, with real-time updates delivered through WebSockets.

---

## 1. Problem Statement

Traditional business simulations are either:
- **Local-only** (no real-time collaboration, no professor oversight)
- **Paper-based** (manual tracking, no engagement)
- **Expensive SaaS** (proprietary, locked-in curriculum)

Professors need a **lightweight, self-hostable** simulation tool that lets students compete in real-time, gives professors live oversight, and produces exportable grade data — all without expensive licensing.

---

## 2. What It Is

Practenture is a **four-component platform**:

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **iOS App** | SwiftUI + Combine (67 Swift files, 15,652 lines) | Student-facing: login, join sessions, submit decisions, view live dashboards |
| **Backend API** | FastAPI + SQLite + WebSockets | Server-side: session management, simulation engine, auth, real-time broadcast |
| **Professor Dashboard** | HTML/JS (served by FastAPI) | Professor-facing: create/manage sessions, monitor rounds, export grades |
| **Admin V2 Control Plane** | FastAPI + HTML/JS + opaque sessions | Administrator-facing: organizations, Professor access, users, operations, audit, backup/health, and MFA account security |

### Core Simulation Mechanics

Each student runs a virtual company competing against AI and other human teams. In each round (quarter), teams make decisions across **six business areas**:

1. **Pricing** — Set product price per unit
2. **Production** — Determine quantity to manufacture
3. **Marketing** — Allocate budget across channels
4. **R&D** — Invest in product improvement
5. **Financing** — Take loans, issue equity
6. **Inventory** — Manage stock levels

The **deterministic simulation engine** (`simulation_engine.py`) processes all decisions simultaneously and returns market outcomes: market share, revenue, profit, stock price, credit rating, and EPS.

---

## 3. Why It Exists

### For Professors
- **Create sessions in <2 minutes** with configurable parameters (rounds, teams, AI difficulty, market type)
- **Monitor live progress** via dashboard and real-time WebSocket updates
- **Export grades** as CSV for LMS integration
- **No cloud dependency** — self-hostable, works on any network

### For Students
- **Real-time competition** — see how decisions affect market position
- **Live feedback** — instant round results, leaderboards, announcements
- **Cross-platform** — iOS app for any iPhone/iPad
- **Multiple auth options** — Apple Sign-In, Google, or password

### For Institutions
- **Zero licensing cost** — open-source, self-hosted
- **No data privacy concerns** — runs on your infrastructure
- **Curriculum-aligned** — standard MBA business simulation framework

---

## 4. How It Works

### System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Practenture Platform                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐     HTTPS      ┌──────────────────────────┐   │
│  │              │  REST API      │                          │   │
│  │  iOS App     │ ◄────────────► │   FastAPI Backend        │   │
│  │  (SwiftUI)   │                │   (Port 8000)            │   │
│  │              │                │                          │   │
│  │  • Auth (JWT)│                │  ┌────────────────────┐  │   │
│  │  • Sessions  │                │  │ Simulation Engine  │  │   │
│  │  • Dashboard │                │  │ (deterministic)    │  │   │
│  │  • Export    │                │  └────────────────────┘  │   │
│  └──────────────┘                │                          │   │
│                                  │  ┌────────────────────┐  │   │
│                                  │  │  WebSocket Manager │  │   │
│                                  │  │  (real-time sync)  │  │   │
│                                  │  └────────────────────┘  │   │
│                                  │                          │   │
│                                  │  ┌────────────────────┐  │   │
│                                  │  │  SQLite Database   │  │   │
│                                  │  │  (in-memory / file)│  │   │
│                                  │  └────────────────────┘  │   │
│                                  └──────────────────────────┘   │
│                                                                  │
│  ┌──────────────┐     HTTPS      ┌──────────────────────────┐   │
│  │              │  REST API      │                          │   │
│  │ Prof. Web    │ ◄────────────► │   Professor Dashboard    │   │
│  │   Browser    │                │   (HTML/JS SPA)          │   │
│  │              │                │   /dashboard              │   │
│  └──────────────┘                └──────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Administrator Control Plane and Database Operations

Admin V2 is deployed at `/admin/v2/` as a separate privileged control plane for Professor invitation lifecycle, organization and account administration, database-health evidence, audited scoped cleanup, backup/restore status, and account security. It uses server-managed opaque sessions, CSRF protection, recent authentication, durable throttling, immutable audit events, and Administrator TOTP MFA. Routine operations use Admin-authorized APIs rather than direct SQL. Production and staging use separate databases and secrets. See [`docs/architecture/SYSTEM_ARCHITECTURE.md`](docs/architecture/SYSTEM_ARCHITECTURE.md), [`docs/architecture/ADMIN_DATABASE_LLD.md`](docs/architecture/ADMIN_DATABASE_LLD.md), and [`docs/architecture/ADMIN_MFA_LLD.md`](docs/architecture/ADMIN_MFA_LLD.md).

### Administrator MFA Journey

1. Administrator signs in to Admin V2 with the platform password.
2. **Account security** starts a pending TOTP enrollment after CSRF-protected password verification.
3. Administrator scans the QR code and confirms a fresh authenticator code.
4. Backend atomically enables MFA, records replay state, and returns ten recovery codes once.
5. Administrator stores those codes securely; only hashes remain in Practenture.
6. Future login returns a one-time challenge and creates the opaque Admin session only after a fresh TOTP or one-time recovery code succeeds.
7. Replay, concurrent use, password guessing, regeneration, disablement, and reauthentication are protected by transactional state checks and durable account-wide throttling.

### Data Flow: One Simulation Round

```
Professor creates session (POST /api/sessions)
       │
       ▼
Students join (POST /api/sessions/{code}/join)
       │
       ▼
Round begins (POST /api/sessions/{code}/start)
       │
       ▼
Students submit decisions (POST /api/sessions/{code}/submit_decision)
       │
       ▼
Professor triggers processing (POST /api/sessions/{code}/process_round)
       │
       ▼
Simulation Engine processes all decisions simultaneously
       │
       ▼
Results stored in database
       │
       ▼
WebSocket broadcast to all connected students
       │
       ▼
Students see live leaderboard + individual results
       │
       ▼
Next round begins (currentRound increments)
       │
       └──► Repeat until totalRounds complete
```

### Authentication Flow

```
Student opens iOS app
       │
       ▼
LaunchView checks Keychain for JWT
       │
       ▼
No token? → LoginView (3 modes: Professor, Student Apple, Student Google)
       │
       ▼
Student enters credentials / taps Apple Sign-In / taps Google
       │
       ▼
POST /api/auth/login with provider (password/apple/google)
       │
       ▼
Backend verifies credentials (password → database check)
                       (apple → JWKS verification)
                       (google → JWKS verification)
       │
       ▼
Returns JWT (HS256, 24h expiry) + role (professor/student)
       │
       ▼
iOS stores in Keychain, attaches to all future API requests
```

---

## 5. User Journeys

### Journey 1: Professor Creates & Runs a Session

```
1. Professor opens browser → navigates to /dashboard
2. Enters username/password → gets JWT
3. Dashboard shows "Create Session" form
4. Configures: name, rounds (default 5), teams (default 10),
   market type (conservative/moderate/aggressive),
   AI difficulty, starting cash, plant capacity
5. Clicks "Create" → session code generated (BIZ-XXXXXX)
6. Shares code with students
7. Students join via iOS app
8. Clicks "Start" → simulation begins
9. Monitors live dashboard: team submissions, standings
10. Clicks "Process Round" → engine computes results
11. Students see live leaderboard + individual results
12. Repeats steps 9-11 for all rounds
13. Clicks "End" → final results
14. Clicks "Export Grades" → CSV download
15. Uploads CSV to LMS
```

### Journey 2: Student Joins & Competes

```
1. Student opens Practenture iOS app
2. LaunchView shows LoginView (no token)
3. Taps "Student Login" → Apple Sign-In
4. iOS sends Apple ID token to /api/auth/login
5. Backend verifies via Apple JWKS → returns JWT
6. Dashboard shows "Enter Session Code"
7. Student types BIZ-XXXXXX → joins as Team Alpha
8. Sees team dashboard: market info, competitors, current round
9. Makes decisions: price, production, marketing, R&D, financing
10. Taps "Submit" → POST /api/sessions/{code}/submit_decision
11. Sees submission confirmation
12. Waits for professor to process round
13. WebSocket delivers round_complete message
14. Sees live leaderboard + individual results
15. Repeats for all rounds
16. Final round complete → sees final standings
17. Taps "Export Results" → CSV download
```

### Journey 3: Professor Monitors Live

```
1. Professor opens /dashboard → session detail
2. Sees real-time monitoring view:
   - Team list with submission status (✓ submitted / ✗ pending)
   - Live leaderboard (auto-updates via WebSocket)
   - Stock price charts per team
   - EPS, ROE, cumulative profit
3. Sees announcements from professor
4. Can send announcements to all students
5. Can view individual student decisions (audit trail)
6. Can export grades at any time (even mid-simulation)
```

---

## 6. API Surface

### Authentication
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/auth/login` | None | Login (password/apple/google) |
| POST | `/api/auth/register` | None | Student registration |
| POST | `/api/auth/verify` | JWT | Verify token validity |
| POST | `/api/auth/professor-only` | JWT+Prof | Professor role gate |

### Session Management
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/sessions` | Professor | Create session |
| GET | `/api/sessions` | None | List all sessions |
| GET | `/api/sessions/{code}` | None | Session details |
| POST | `/api/sessions/{code}/join` | None | Join as team |
| POST | `/api/sessions/{code}/start` | Professor | Start simulation |
| POST | `/api/sessions/{code}/end` | Professor | End + get results |
| GET | `/api/sessions/{code}/status` | None | Current state |
| GET | `/api/sessions/{code}/teams` | None | Team roster |

### Simulation
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/sessions/{code}/submit_decision` | Student/Prof | Submit round decision |
| GET | `/api/sessions/{code}/decisions/{round}` | None | View decisions |
| POST | `/api/sessions/{code}/process_round` | Professor | Process all decisions |

### Leaderboard & Results
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/sessions/{code}/leaderboard` | None | Live standings |
| GET | `/api/sessions/{code}/results` | None | Round results |

### Announcements
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/sessions/{code}/announcements` | Professor | Send announcement |
| GET | `/api/sessions/{code}/announcements` | None | Read announcements |

### Export
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/sessions/{code}/export/grades` | Professor | CSV grade export |
| GET | `/api/sessions/{code}/export/leaderboard` | Professor | CSV leaderboard export |

### Professor Dashboard
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/dashboard` | None | SPA (login or dashboard) |
| GET | `/api/dashboard/sessions` | JWT | Session list for dashboard |
| GET | `/api/dashboard/monitor/{code}` | JWT | Real-time monitoring data |

### Real-Time
| Path | Auth | Description |
|------|------|-------------|
| `ws://host/ws/{code}` | JWT (query param) | Live session updates |

---

## 7. Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Auth | JWT (HS256) | Simple, stateless, no session store needed |
| Token expiry | 24 hours | Balances security with usability |
| Database | SQLite | No external dependency, self-hostable, sufficient for classroom scale |
| Real-time | WebSockets | Live updates without polling overhead |
| Auth providers | Apple + Google + Password | Covers all student preferences |
| JWKS verification | 6-hour TTL cache | Reduces external API calls |
| Simulation | Deterministic engine | Reproducible results, no race conditions |
| Session codes | BIZ-XXXXXX (10 chars) | Easy to share verbally in class |
| Export | CSV | Universal LMS compatibility |

---

## 8. Configuration

| Environment Variable | Default | Purpose |
|---------------------|---------|---------|
| `PRACTENTURE_JWT_SECRET` | *(required)* | JWT signing key |
| `PRACTENTURE_JWT_EXPIRY_HOURS` | `24` | Token lifetime |
| `PRACTENTURE_CORS_ORIGINS` | deployment configuration | Explicit allowed browser origins; wildcard is not approved for production |
| `PRACTENTURE_HOST` | `0.0.0.0` | Bind address |
| `PRACTENTURE_PORT` | `8005` | Backend container HTTP port |
| `PRACTENTURE_PROFESSOR_USERNAME` | deployment secret | Bootstrap professor username; never document production values |
| `PRACTENTURE_PROFESSOR_PASSWORD` | deployment secret | Generated/managed outside Git; no production default |

---

## 9. Current Status

### ✅ Completed
- JWT authentication (password + Apple + Google)
- Session CRUD (create, start, end, join)
- Decision submission + round processing
- Deterministic simulation engine (6 business areas: pricing, production, marketing, R&D, financing, inventory)
- WebSocket real-time broadcast with heartbeat & reconnection
- Professor web dashboard API (session management, monitoring, grading, announcements)
- Grade CSV export (grades + leaderboard)
- Leaderboard endpoint (real-time)
- Announcement system (professor-to-student)
- iOS app — 15,652 lines of Swift, 67 files, **BUILD SUCCEEDED — zero errors, zero warnings** (Swift 6 fully compliant)
  - 3-mode login (Apple Sign-In, Google, Professor password)
  - Student: Team Dashboard, Decision Input (all 6 categories), Round Results, Leaderboard, Announcements, AI Coach, Performance History, Waiting Room, Join Session
  - Professor: Session List, Create Session, Session Monitor, Round Controls, Grade Mapping, Session Results, Team Management, Announcements, Leaderboard
  - Shared: Login, Settings, About, Coaching Bubbles, Metric Cards, Round Charts, Status Badges, Leaderboard Rows
  - NetworkService with retry logic & auth header injection
  - SyncService with offline-first queue & conflict resolution
  - WebSocketManager with session-based rooms, heartbeat, auto-reconnect
  - All Swift 6 concurrency issues resolved (actor isolation, captured `self`, unused variables)
- Backend — FastAPI with persistent production SQLite, deterministic simulation, WebSockets, Professor workflows, and Admin V2 control plane
- Full backend/release suite: 502 tests passing for the deployed Administrator MFA baseline
- Exact-SHA CI: all five jobs passing, including mandatory iOS Golden Formula parity, with zero GitHub Check annotations
- Production E2E: health, Professor flows, Admin V2 enrollment, and fresh Administrator TOTP login verified

### 🔄 In Progress
- None — all build errors resolved. Project is in a fully clean build state.

### ⏭ Next planned work
- Maintain recovery-code custody and monitor redacted Administrator authentication/audit events.
- Keep documentation, API manifests, client contracts, rollback evidence, and exact-SHA CI qualification synchronized with every future change.
- Prioritize additional product roadmap work separately; there is no unresolved Administrator MFA implementation or deployment blocker.

---

## 10. File Structure

```
Practenture-ios/
├── Practenture/                          # iOS Xcode project
│   ├── Practenture/                      # Swift source
│   │   ├── AuthManager.swift          # JWT + Apple/Google auth
│   │   ├── NetworkService.swift       # HTTP client + models
│   │   ├── LoginView.swift            # Three-mode login UI
│   │   ├── LaunchView.swift           # Auth-gated entry
│   │   ├── SessionMonitorView.swift   # Professor monitor
│   │   ├── TeamDashboardView.swift    # Student dashboard
│   │   ├── Engine/                    # Simulation engine (iOS local)
│   │   └── Views/Professor/           # Professor-specific views
│   ├── Practenture.xcodeproj/
│   ├── backend/                       # FastAPI backend
│   │   ├── main.py                    # App entry + CORS
│   │   ├── models.py                  # SQLAlchemy models
│   │   ├── database.py                # DB setup + seed
│   │   ├── auth.py                    # JWT core
│   │   ├── auth_providers.py          # Apple/Google JWKS
│   │   ├── ws_manager.py              # WebSocket manager
│   │   ├── simulation_engine.py       # Deterministic engine
│   │   ├── routers/
│   │   │   ├── auth.py                # Auth endpoints
│   │   │   ├── sessions.py            # Session CRUD
│   │   │   ├── decisions.py           # Decision + round processing
│   │   │   ├── leaderboard.py         # Leaderboard
│   │   │   ├── announcements.py       # Announcements
│   │   │   ├── websocket.py           # WS endpoint
│   │   │   └── dashboard.py           # Prof dashboard API
│   │   └── templates/                 # HTML dashboard SPA
│   ├── prd.json                       # Story-level PRD
│   ├── PROGRESS.md                    # Progress log
│   ├── PRD.md                         # This document
│   ├── IMPLEMENTATION_PLAN.md         # Phase plan
│   └── PROFESSOR_API_ANALYSIS.md      # iOS API contract
├── progress.txt                       # Detailed progress log
├── update_mop_phase5.py              # MOP Google Doc updater
└── COMPREHENSIVE_CODE_REVIEW.md       # Code review results
```

---

## 11. Testing

### Backend Tests (42 passing, 16 e2e failing due to test harness issues)
```bash
cd backend && PRACTENTURE_JWT_SECRET=<your-secret> python3 -m pytest test_backend.py test_phase5.py -v
```

| Suite | Tests | Status |
|-------|-------|--------|
| `test_backend.py` | 18 | ✅ All pass |
| `test_phase5.py` | 13 | ✅ All pass |
| `test_e2e.py` | 27 | ⚠️ 11 pass, 16 fail (auth header issue in test helpers — not backend bugs) |
| **Total** | **58** | **42 pass, 16 fail** |

### iOS Build
```bash
xcodebuild -project Practenture.xcodeproj -scheme Practenture \
  -sdk iphonesimulator \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro' build
```
**Status**: ✅ **BUILD SUCCEEDED — zero errors, zero warnings** (Swift 6 fully compliant, 15,652 lines of Swift across 67 files, all concurrency issues resolved)

### Manual E2E Verified
- ✅ Professor login → valid JWT
- ✅ Session creation → BIZ-XXXXXX code
- ✅ Session start → teamsSubmitted=0
- ✅ Process round → 0 results (no submissions)
- ✅ Session end → status=ended
- ✅ Leaderboard endpoint → empty (no rounds played)
- ✅ Results endpoint → empty (no rounds played)
- ✅ Grade export → "No results available" (expected)
- ✅ Dashboard sessions → returns all sessions
- ✅ Announcements → create + retrieve working
- ✅ iOS build succeeds on iPhone 17 Pro simulator
- ✅ 3-mode login (Apple, Google, Professor) — all flows implemented

### Current Release Verification
- ✅ Full local backend and release suite: 502 passed
- ✅ Exact-SHA GitHub Actions: all five required jobs passed
- ✅ Mandatory iOS Golden Formula parity passed
- ✅ GitHub Check annotations: zero
- ✅ Administrator MFA enrollment and fresh TOTP login verified in production
- ✅ Public HTTPS, source revision, backup/restore, rollback image, database integrity, and foreign-key checks passed

---

*Document created: 2026-05-23*
*Last updated: 2026-07-31 — Admin V2 and Administrator MFA are implemented, exact-SHA CI-qualified, deployed, enrolled, and verified through a fresh production TOTP login. See the linked HLD, database LLD, MFA LLD, and operations runbook for authoritative technical and operational detail.*
