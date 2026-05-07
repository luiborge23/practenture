# BizSimAI Phase 5 — Implementation Plan

## Status: Phase 5 Auth + WebSocket Complete ✅

### Completed Items

- [x] **Production JWT Configuration** — `BIZSIMAI_JWT_SECRET`, `BIZSIMAI_JWT_EXPIRY_HOURS`, CORS, HOST, PORT env vars
- [x] **Apple/Google ID Token Verification** — JWKS caching (6hr TTL), token validation, same format as password login
- [x] **iOS Auth Integration** — `AuthManager.swift` (JWT, Apple Sign-In, Google Sign-In), `AuthState.swift` (Observable)
- [x] **WebSocket Reconnection** — `ReconnectableWSClient` (exponential backoff, session join flow)
- [x] **Session Join Flow** — `SessionJoinSheet` (PIN entry, professor verification, student join)
- [x] **Professor-Only Endpoint** — `/api/auth/professor-only` returns 403 for students
- [x] **LaunchView Auth Check** — Shows LoginView sheet when not authenticated, Welcome back message when authenticated
- [x] **LoginView** — Three modes: Professor Login, Student Login, Student Register
- [x] **Logout** — Logout button in LaunchView when authenticated

### Remaining Items (US-016+)

- [ ] **Student Dashboard Update** — Show session info, leaderboard, grade progress
- [ ] **Professor Dashboard** — Web-based dashboard for session management
- [ ] **Announcements** — Real-time announcement push to students
- [ ] **Grade CSV Export** — Professor exports student grades
- [ ] **Integration Tests** — End-to-end test suite
- [ ] **Production Deployment** — Docker, nginx, systemd, SSL

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  BizSimAI iOS App (SwiftUI)                         │
│                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │  AuthManager│  │ LaunchView   │  │ LoginView │ │
│  │  (JWT)      │  │ (Entry Point)│  │ (3 modes) │ │
│  └──────┬──────┘  └──────┬───────┘  └─────┬─────┘ │
│         │                │                 │       │
│         ▼                ▼                 ▼       │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │ AppleSignIn │  │ AuthState    │  │ Session   │ │
│  │ /Google     │  │ (Observable) │  │ Join      │ │
│  └─────────────┘  └──────────────┘  └───────────┘ │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│  BizSimAI Backend (FastAPI)                         │
│                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │ /api/auth   │  │ /api/sessions│  │ /ws/      │ │
│  │ (JWT)       │  │ (CRUD)       │  │ Websocket │ │
│  └──────┬──────┘  └──────────────┘  └───────────┘ │
│         │                                          │
│         ▼                                          │
│  ┌─────────────┐  ┌──────────────┐                 │
│  │ Apple/Google│  │ Firestore    │                 │
│  │ JWKS Verify │  │ (MongoDB)    │                 │
│  └─────────────┘  └──────────────┘                 │
└─────────────────────────────────────────────────────┘
```

---

## Key Files

| File | Purpose |
|------|---------|
| `AuthManager.swift` | JWT token management, Apple/Google login |
| `AuthState.swift` | Observable auth state |
| `LoginView.swift` | Three-mode login/register UI |
| `LaunchView.swift` | Entry point with auth check |
| `SessionJoinSheet.swift` | Session PIN entry/join |
| `ReconnectableWSClient.swift` | WebSocket with reconnect |
| `backend/routers/auth.py` | Auth endpoints + professor-only |
| `backend/auth/providers.py` | Apple/Google JWKS verification |
| `backend/auth.py` | JWT creation/verification |
| `backend/main.py` | FastAPI app + CORS config |

---

## Testing

Run backend tests:
```bash
cd backend
python -m pytest test_backend.py -v
```

Run iOS build:
```bash
xcodebuild -project BizSimAI.xcodeproj -scheme BizSimAI -sdk iphonesimulator -destination 'platform=iOS Simulator,name=iPhone 16' build
```

---

## Environment Variables

```bash
export BIZSIMAI_JWT_SECRET=<your-secret>
export BIZSIMAI_JWT_EXPIRY_HOURS=24
export BIZSIMAI_CORS_ORIGINS="*"
export BIZSIMAI_HOST="0.0.0.0"
export BIZSIMAI_PORT=8000
```

---

## Next Steps

1. **Student Dashboard Update** — Connect session data to dashboard
2. **Professor Dashboard** — Build web dashboard for session management
3. **Announcements** — Real-time announcement system
4. **Grade CSV Export** — Professor exports student grades
5. **Integration Tests** — End-to-end test coverage
6. **Production Deployment** — Docker, nginx, SSL
