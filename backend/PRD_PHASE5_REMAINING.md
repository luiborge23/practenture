# Practenture Phase 5 Remaining — PRD

**Date:** 2026-05-07
**Status:** Ready for Ralph Execution
**Priority:** Blocks classroom deployment

---

## Context

Phase 5 core (Auth + WebSocket) is complete. The following items remain before classroom deployment:

1. **Professor Web Dashboard** — HTML/JS UI for session management + grade export (NO backend yet — professors currently need the iOS app to manage sessions)
2. **iOS NetworkService/SyncService** — Auth + WebSocket integration (partially done, needs completion)
3. **Production JWT config** — env var support
4. **Apple/Google ID token verification** — JWKS integration
5. **Integration tests** — end-to-end backend + iOS tests

---

## User Stories

### US-001: Professor Web Dashboard — Session Management
**As a** professor,
**I want** to access a web dashboard at `http://host:8000/dashboard`,
**So that** I can create sessions, view active sessions, start/stop simulations, and monitor progress without needing the iOS app.

**Acceptance Criteria:**
- Login page with professor credentials
- Dashboard shows all active sessions with status
- "Create Session" form (name, rounds, teams, config)
- Session detail view with live leaderboard
- "Start Session" and "End Session" buttons
- "Advance Round" button
- Real-time updates via WebSocket (no page refresh needed)
- All backend URLs configurable via environment variable

**Technical Notes:**
- Use vanilla HTML/CSS/JS (no framework) to avoid build dependencies
- Template rendering via Jinja2 (already available with FastAPI/Starlette)
- WebSocket client in JS for real-time updates
- Place templates in `backend/templates/dashboard.html`

---

### US-002: Professor Web Dashboard — Grade Export
**As a** professor,
**I want** to export grades from the web dashboard,
**So that** I can download CSV files without using the iOS app.

**Acceptance Criteria:**
- "Export Grades" button on session detail view
- "Export Leaderboard" button on session detail view
- Downloads trigger browser download with correct filename
- Both endpoints already exist: `/api/sessions/{code}/export/grades` and `/api/sessions/{code}/export/leaderboard`

**Technical Notes:**
- Simple `<a href="...">` link or fetch + Blob download in JS
- No new backend endpoints needed

---

### US-003: iOS Auth Integration
**As a** student or professor using the iOS app,
**I want** the app to authenticate with the backend and store tokens,
**So that** I can join sessions across devices.

**Acceptance Criteria:**
- Login screen in iOS app (email/password or Apple Sign In)
- Token stored in Keychain (not UserDefaults)
- Token automatically attached to all NetworkService requests
- Token refresh handled transparently
- Logout clears Keychain token

**Technical Notes:**
- Add `AuthService.swift` for login/logout/token management
- Use `KeychainAccess` or `SecKeychain` directly
- Update `NetworkService.swift` to attach `Authorization: Bearer <token>` header
- Add `TokenStorage.swift` for Keychain operations

---

### US-004: iOS WebSocket Integration
**As a** student in an active session,
**I want** the app to receive live updates from the backend,
**So that** I see round results and leaderboard changes in real-time.

**Acceptance Criteria:**
- WebSocket connection established when joining a session
- Auto-reconnect on disconnect (max 3 attempts)
- UI updates automatically when `round_complete` or `leaderboard_update` received
- Connection status indicator (connected/disconnected/reconnecting)
- Graceful fallback to polling if WebSocket fails

**Technical Notes:**
- Add `WebSocketService.swift` using `URLSessionWebSocketTask`
- Ping/pong keepalive every 30 seconds
- Session-scoped: only connect to the joined session's room
- Update `SyncService.swift` to use WebSocketService

---

### ✅ US-005: Production JWT Configuration Production JWT Configuration
**As a** deployer of the backend,
**I want** the JWT secret to be configurable via environment variable,
**So that** I don't have to modify code to change secrets.

**Acceptance Criteria:**
- `PRACTENTURE_JWT_SECRET` env var for JWT signing key (required, error if missing)
- `PRACTENTURE_JWT_EXPIRY_HOURS` env var for token expiry (default: 24)
- `PRACTENTURE_CORS_ORIGINS` env var for CORS (default: `*`)
- `PRACTENTURE_HOST` env var for WebSocket host (default: `localhost`)
- `PRACTENTURE_PORT` env var for server port (default: `8000`)
- Health check reflects config values

**Technical Notes:**
- Use `os.environ.get()` in `auth.py` and `main.py`
- Validate required env vars on startup
- Log config (without secret) on startup for debugging

---

### ✅ US-006: Apple/Google ID Token Verification via JWKS Apple/Google ID Token Verification
**As a** student using Apple or Google Sign In,
**I want** my identity token to be verified against the provider's JWKS endpoint,
**So that** only valid tokens are accepted.

**Acceptance Criteria:**
- Apple ID token verification using Apple's JWKS endpoint
- Google ID token verification using Google's JWKS endpoint
- Token payload validated (issuer, audience, expiry)
- Returns same token format as password login for consistency

**Technical Notes:**
- Apple JWKS: `https://appleid.apple.com/auth/keys`
- Google JWKS: `https://www.googleapis.com/oauth2/v3/certs`
- Use `PyJWT` decode with `algorithms=["RS256"]` and `options={"verify_exp": True}`
- Cache JWKS keys (expire after 6 hours)
- Add `jose` or use `PyJWT` built-in JWKS support

---

### US-007: Integration Tests
**As a** developer,
**I want** integration tests for the Phase 5 features,
**So that** I can verify the backend works end-to-end.

**Acceptance Criteria:**
- Test session creation via REST API
- Test student login and token verification
- Test session join via REST API
- Test decision submission via REST API
- Test WebSocket connect and message broadcast
- Test grade CSV export
- Test professor dashboard HTML renders
- All tests pass (target: 40+ total tests)

---

## Implementation Order (Dependency-Driven)

1. **US-005: Production JWT Configuration** (1 day) — No dependencies, enables prod deployment
2. **US-006: Apple/Google ID Token Verification** (2 days) — Depends on US-005
3. **US-003: iOS Auth Integration** (2 days) — Depends on US-005 + US-006
4. **US-004: iOS WebSocket Integration** (2 days) — Depends on US-003
5. **US-001: Professor Web Dashboard** (3 days) — Independent, can run in parallel
6. **US-002: Grade Export from Dashboard** (0.5 days) — Depends on US-001
7. **US-007: Integration Tests** (1 day) — Depends on all above

**Total estimated effort: 11-12 days**

---

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| iOS WebSocket on background | High | Use URLSessionWebSocketTask with proper task management |
| Apple JWKS key rotation | Medium | Cache keys with TTL, handle key changes gracefully |
| Dashboard XSS via session names | Medium | Escape all HTML output in Jinja2 templates |
| CORS issues in production | Medium | Configurable CORS origins via env var |
