Practenture — Master Strategy Blueprint
PRD + HLD + User Journey + What/Why/Value + Competitive Advantage + SWOT + GTM + Executive Summary
Document ID: 1nBYwiSsAYcEIF5kEdtlYicRLWLVYynV98PDXwBy51GA
Created: July 10, 2026 | Updated: July 31, 2026 | Author: Paul for Luis Borges | Status: LIVE at https://practenture.com
Folder: https://drive.google.com/drive/folders/1kwxGJ1MicrlmY1NcmDqe_KtnaWJDMHNl
Sources: System Arch Doc 1UFOSXm2GvBTKtOei_ThPkwqIolhRwpJIpX2e3l1ndVU + MOP Doc 10xj3NgeOU59FqoTWfwQRvmfcrj9but4PZt8LIaA5bcY + Drive folder + live codebase

═══════════════════════════════════════════════════════════════════════════════
1. EXECUTIVE SUMMARY
═══════════════════════════════════════════════════════════════════════════════

Practenture is a real-time, self-hostable business simulation platform for MBA/undergrad classrooms. Unlike Capsim (15-min rounds), Marketplace (5-min), Cesim (10-min), Practenture delivers true real-time feedback via WebSockets, enabling teachable moments as market dynamics unfold.

Mission: Turn professors from simulation administrators into coaches, and students from passive decision-submitters into strategic thinkers through immediate cause-and-effect.

Vision: Become the open-source standard for business education simulations — zero per-student fees, full data ownership, LMS-native, mobile-first.

Current Status — LIVE & Production Ready (July 31, 2026):
• Backend: FastAPI with persistent SQLite production storage and a PostgreSQL scale path, Docker multi-stage non-root runtime, Nginx reverse proxy, AWS EC2 t3.micro in us-east-1, and healthy public /api/health at https://practenture.com.
• iOS App: 83 Swift files, 19,303 lines, Swift 6 fully compliant, BUILD SUCCEEDED zero errors/warnings on iPhone 17 Pro sim, SwiftUI+Combine, @Observable, offline-first SyncService with queue & conflict resolution, NetworkService retry + auth injection + token refresh coalescing, WebSocketManager with heartbeat 30s + auto-reconnect exponential backoff.
• Auth: JWT HS256 24h expiry, Keychain storage, 3 providers — password (bcrypt), Apple Sign-In (RSA RS256 JWKS https://appleid.apple.com/auth/keys, 6h TTL cache, verify_aud=False when no audience configured — RCA fixed), Google Sign-In (JWKS https://www.googleapis.com/oauth2/v3/certs), professor-only gate 403.
• Features: Session CRUD BIZ-XXXXXX (10-char, easy verbal share), join/ start/ pause/ resume/ end, decision submission across 6 areas (pricing, production, marketing, R&D, financing, inventory) with 25+ sub-variables, deterministic engine with seeded RNG + 5% noise, round results + leaderboard real-time, announcements, CSV exports (grades + leaderboard), PDF reports via UIGraphicsPDFRenderer, Analytics dashboard (6 overview cards, round trends Chart API, team comparison, strategy distribution), i18n 8 languages (en, es, fr, de, ja, zh-Hans, ko, pt), AI competitors (LowCostLeader, Differentiator, BestCost, Adaptive — counter-plays player), push notifications (APNs + FCM), MFA TOTP, multi-tenant, Alembic migrations.
• Deployment: ./ec2-deploy.sh deploy is the only approved production promotion path; it verifies deterministic release manifests, backup/restore evidence, migrations, atomic release symlinks, immutable rollback images, internal container health, public TLS health, and exact source/image revision.
• Administrator control plane: Admin V2 is deployed at /admin/v2/ with opaque Secure/HttpOnly/SameSite=Strict sessions, CSRF, recent authentication, durable account-wide throttling, immutable redacted audits, organization/user/Professor-access operations, health/backup evidence, and scoped cleanup.
• Administrator MFA: production TOTP enrollment and fresh login verified; pending enrollment requires possession confirmation, seeds are encrypted, recovery codes are one-time and stored only as hashes, and TOTP/recovery replay checks are transactional.
• Qualified release: exact SHA 1abb1aaee2dd49b59790a4b3c232cacdb3e2848a passed 502 local backend/release tests and all five CI jobs, including iOS Golden Formula parity, with zero GitHub Check annotations before transactional deployment.

Market Opportunity:
• Business Simulation Games: $12.4B in 2025 → $26.8B by 2034, CAGR 8.9%, North America 38.2% ($4.7B).
• Simulation Learning (overall): $17.2B 2025 → $56.8B 2035, CAGR 14.2%, 2026 est $19.6B.
• Simulation Learning in Higher Ed: +$3.23B growth 2025-2030, CAGR 23.3%.
• EdTech total: $187B 2025 → $437.5B 2033.
→ SAM: US has ~1,600 business schools, ~400k MBA students/yr, ~2M undergrad business majors. At $0 self-hosted + $5k/yr managed cloud institutional pricing vs competitors $30-60/student, TAM for US higher-ed simulation alone ~$50-80M substitutable.

Competitive Edge in 1 line: Only platform that is real-time + self-hostable zero-fee + native iOS + professor intervention tools (pause/highlight/announce/difficulty adjust) + full LMS CSV.

Ask: This blueprint is the PRD+HLD+GTM source of truth for investor/partner/university pilot conversation.

═══════════════════════════════════════════════════════════════════════════════
2. WHAT — PRODUCT DEFINITION
═══════════════════════════════════════════════════════════════════════════════

Practenture = iOS student app + FastAPI backend + professor web console + simulation engine + analytics + adaptive AI.

Component 1 — Student Interface (iOS):
• SwiftUI + Combine, 83 files 19.3k lines, iOS 17 min target 18, iPhone 15/16/17 Pro.
• Auth: LoginView 3-mode (Professor, Student Apple, Student Google), LaunchView auth-gated Keychain check, welcome back state, logout clears Keychain.
• Session: JoinSessionView code entry BIZ-XXXXXX, team assignment Alpha/Beta/Gamma/Delta auto, role specialization (CEO/CMO/CFO/COO) optional, 3-min tutorial.
• Decisions (per round, 6 areas, 25+ fields):
  Pricing: wholesalePrice $20-150, internetPrice $15-140, privateLabelBid $18-130, amazonPrice $20-145, amazonAdBudget $0-50k
  Product: materialsQuality 0.0-1.0 (Economy/Standard/Superior), stylingBudget $0-30k, numModels 1-8, tqmInvestment $0-20k
  Marketing: marketingInvestment $0-100k, advertisingBudget $0-100k, celebrityType none/athlete/musician/actor/social_influencer/ceo (1.0-1.18x), retailOutlets 0-50, mail-in rebate $0-20, delivery Standard/Rush, freeShippingThreshold, socialMediaBudget tiktok/instagram/youtube $0-25k each, influencerTier none/nano/micro/macro
  Workforce: baseWage $10-40/h, incentivePay $0-10/h, trainingBudget / trainingHours 0-40h, bestPractices $0-15k
  Production: productionQuantity 1k-50k, overtimePercent 0-30% (maxOvertime 25% default), capacity plantCapacity 100-10k default 10000
  Finance: csrInvestment $0-20k, dividendsPerShare $0-5, newLoanAmount $0-500k, sharesBuyback 0-100k, sharesIssued 0-200k, rdInvestment $0+, fulfillmentMethod fbm/fba/own_store, internetPromotion 0-1
• Results: RoundResultsView revenue/profit/net, marketShare, stockPrice, S/Q rating 0-10, creditRating, investorScore, EPS, ROE, cumulativeProfit, cash, inventory, equity, debt, sharesOutstanding, productionCost, marketingCost, unitCost, demand per channel, scorecard (epsScore/roeScore/stockPriceScore/imageScore/creditScore/totalScore).
• Live: TeamDashboardView with BackendState live sync (team count, submission count, backendCurrentRound), online indicator, announcements StudentAnnouncementsView relative time, leaderboard StudentLeaderboardView + ProfessorLeaderboardView, performance history charts, waiting room.
• AI Coach: AICoachView contextual suggestions adaptive to performance.
• Export: PDFExporter.swift 174 lines UIGraphicsPDFRenderer, CSVExportViewModel.
• Services: NetworkService (xcconfig-fed Info.plist HTTPS origin with matching code fallback, authoritative-response cache bypass, bounded timeout, JSONEncoder snake_case, refreshToken coalescing NSLock+Task, 401→refresh), SyncService (FirebaseSyncAdapter+LocalSyncAdapter protocol), WebSocketManager (session rooms, JWT query parameter).
• Analytics: AnalyticsDashboardView 380 lines — class overview 6 cards, round trends Chart API, team comparison, strategy distribution bar chart, tab selector Trends/Teams/Strategies, predictive modeling ready.
• i18n: I18NManager 140 lines, 8 locales, L10n enum 60+ keys, SettingsView language picker, notification locale change.

Component 2 — Professor Console:
• Web Dashboard: FastAPI-served SPA dashboard.html via Jinja2Templates at /dashboard, auth gate verify_professor, sessions list summary (code/id/state/currentRound/totalRounds/teamsCount/aiTeamsCount/createdBy/totalSubmissions/lastRound/totalTeams), monitor view team roster member names online status submission progress ✓/✗, live leaderboard auto-update WebSocket, stock charts, EPS/ROE/profit, audit trail decisions, pause/resume, announce, highlight team, difficulty adjust, grade export CSV, analytics tab.
• iOS Professor: SessionListView (Search/Filter), CreateSessionView totalRounds 1-10 rec 5-8, teams 4-8 rec 4-6, AI difficulty Easy/Med/Hard, seed for reproducibility, SessionMonitorViewModel polling 10s interval + processRoundWithBackend + endSessionWithBackend fallback local engine, RoundControlView, TeamManagementView, GradeMappingView, SessionResultsView CSV real data, AnnouncementsView send via NetworkService.sendAnnouncement.

Component 3 — Simulation Engine (deterministic, pure Python, mirrors Swift):
• Constants: PRICE_ELASTICITY 1.5, SQ_WEIGHT 1.2, STORAGE_COST_PER_UNIT $1.50, BASE_REJECTION_RATE 12%, BASE_WAGE_BASELINE $25k, NOISE_AMPLITUDE 5%, BASE_STOCK_TARGET 25.0, TARGET_GROWTH_RATE 6% per round, OUTLETS_WEIGHT 0.3, MARKETING_DIVISOR 2000, MARKETING_MULTIPLIER 5.0, FBA_FEE 15%, FBM 10%, INITIAL_STOCK $50.
• Functions: _add_noise RNG, _clamp, _compute_rejection_rate TQM/training (-1.1% per $100k TQM max 9%, -0.9% per $50k training max 5%, min 1%), _compute_sq_rating materials*5 + models/10*2 max2 + styling/500k*3 max3 clamp 0-10, _compute_reputation sq/10*4 + TQM/200k*2 + CSR/100k*2 + marketing/300k*2 clamp 0-10, _compute_attractiveness (own/comp)^elasticity + noise.
• Demand models: compute_wholesale_demand base 10k * price_attr*sq_attr*(1+marketing+social+outlet), compute_internet_demand base 5k * similar * (1+marketing*0.5+social)*promotion 1+0.3*factor, compute_amazon_demand base 5k * similar * channel bonus FBA, compute_private_label_demand base 2k allocate unsold.
• Costs: compute_production_cost labor $8*wageFactor, material $3+quality*7, overtimeFactor 1+overtime%*0.5, trainingReduction min(training/500k*0.15,0.15), unitCost = (mat+lab)*overtime*(1-trainingRed), total = unit*qty; compute_marketing_cost marketing+advertising*celebrityMult+socialTotal; compute_creditscore D/E, interest coverage, cash ratio 0-100; etc.
• Round processing: Simultaneous — collect decisions map, team_states, process_round(config,teams,decisions,round_num,team_states) → engine_results list RoundResult + new_team_states dict → db.store_results + update_team_state.
• AI: AICompetitor.swift 418 lines — 4 strategies: LowCostLeader predictable moderate risk minimal adaptation, Differentiator, BestCost, Adaptive studies last player move counter-strategy (if high price → undercut decent quality, if low → go premium differentiate, if moderate → match compete other factors), end-game aggressive final rounds, higher R&D/marketing/workforce, 3 difficulties Easy/Med/Hard (Easy Best-Cost/Low-Cost, Med all 4 balanced, Hard Adaptive/Best-Cost aggressive high adaptation).

Component 4 — Backend API:
• 1,777+ lines across 10+ modules, dual-mode: DATABASE_URL empty/sqlite→in-memory fallback Database class (for classroom scale no ext dep), else PostgreSQL async SQLAlchemy + Alembic.
• Routers: auth, sessions, decisions, leaderboard, announcements, websocket, dashboard, grades, push.
• Analytics Service: aggregation, report generation.
• Push: APNs, FCM, unified service, templates, models_db.
• MFA: TOTP 2FA, enforcement middleware, recovery codes.
• Multi-tenant: tenant_manager + customization.
• Auth providers abstraction: Apple/Google JWKS + Auth0/Clerk/Firebase Auth integrations implemented not yet wired.

Component 5 — Realtime:
• ws_manager.py per-session connection groups, JWT-auth room, ping/pong keepalive.
• iOS ReconnectableWSClient exponential backoff.
• FirebaseRealtimeSync live listeners session/teams/announcements/results.

═══════════════════════════════════════════════════════════════════════════════
3. WHY — PROBLEM & VALUE
═══════════════════════════════════════════════════════════════════════════════

Problems with Status Quo:
1. Latency Learning Gap — Traditional 8-15 min round delays disconnect action from consequence. Students forget strategy by results time. Learning science: feedback loop >60s degrades retention 40%.
2. One-Size-Fits-All — Fixed difficulty bored advanced / overwhelms struggling. No adaptive.
3. Professor as Administrator — Setup, logistics, manual grading vs teaching. 2-3h prep per simulation (Capsim).
4. Limited Realism — Batch prevents observing market dynamics competitor reactions. Feels static spreadsheet.
5. Assessment Lag — Feedback days later, teachable moment lost. No AACSB/ABET mapping out of box.
6. Expensive SaaS — Capsim $55/student, Marketplace $40, Cesim $45, Hubro $35, StratX $60+. Vendor lock-in, no self-host, data privacy concerns FERPA.
7. Poor Mobile — Web-only, not native. Students live on phones.

Value Proposition:
For Professors (Sarah Mitchell persona, Business Admin Prof, moderate tech):
• Create session <2 mins (vs 30 mins Capsim) with templates, share code, start.
• Live monitor submission ✓/✗, leaderboard auto, stock charts, EPS/ROE/profit, audit trail.
• Intervention tools — pause for discussion, highlight interesting decision, announce all/specific, adjust difficulty on-the-fly (market volatility, AI aggressiveness).
• Export grades CSV Canvas/Blackboard/Moodle, anytime mid-sim, competency reports AACSB/ABET, PDF performance report.
• Zero licensing, self-hostable, FERPA friendly, runs your infra.

For Students (Alex Chen persona, Junior Business, high mobile comfort, wants win + strategic understanding):
• Real-time competition — immediate market response seconds not minutes.
• Live feedback — round results, leaderboard, announcements via WebSocket.
• AI Coach adaptive suggestions, test decision feature.
• Native iOS experience offline-first queue + auto-reconnect, not clunky web.
• Apple/Google SSO no password friction, Keychain auto-login.

For Institutions:
• Zero licensing cost open-source, self-hosted, no data privacy concerns, FERPA/GDPR compliant self-host.
• Curriculum-aligned standard MBA framework 6 areas.
• Low infra — t3.micro enough for 30 teams, SQLite sufficient classroom, PostgreSQL path for scale.
• LMS integration via CSV today, LTI 1.3 tomorrow.
• Research data export raw decisions/results for scholarship.

Educational Impact (Why Now):
• Gen Z expects real-time interactive (TikTok, gaming).
• Business education shift from lecture to experiential (Kolb).
• MBA enrollment rebound + corporate training growth.
• AI enables adaptive difficulty previously impossible.

═══════════════════════════════════════════════════════════════════════════════
4. PRD — PRODUCT REQUIREMENTS DOCUMENT
═══════════════════════════════════════════════════════════════════════════════

4.1 Goals:
• P0: Professor can create session, share code, monitor, process rounds, export grades <5 mins total orchestration.
• P0: Student can auth (Apple/Google/password) <10s, join via BIZ-XXXXXX <30s, submit decisions per round <3 mins, see results real-time.
• P0: System supports 30 human teams + 20 AI competitors per session, 8 rounds typical, 50-min class timeline 0-5 setup/team formation/tutorial, 5-45 gameplay 6-8 rounds, 45-50 debrief.
• P1: Real-time WS <2s latency, 100% decision reliability, offline queue.
• P1: Analytics dashboard class overview, round trends, team comparison, strategy distribution.
• P1: Export grades accuracy 100%, LMS compatible.
• P2: Adaptive difficulty AI, intervention tools, i18n 8 languages, PDF reports, push notifications.

4.2 Non-Goals (v1.0):
• Android app (iOS only v1, Android Phase 2)
• Web student app (future — iOS first)
• PostgreSQL required (SQLite OK v1)
• Real-world data integration live (Phase 2)
• Custom simulation scenario builder (Phase 6)
• Multi-classroom management bulk import (Phase 7)

4.3 Personas:
• Professor Sarah Mitchell — Business Admin Prof moderate LMS user, goals run classroom sims monitor progress grade fairly export, pain joining troubleshooting lack real-time visibility manual grading. Workflow: Create→Share→Monitor→Manage (announce/advance/pause)→Review→Export→End. Success metrics: session creation <30s achieved, student join >95% in test, real-time <2s achieved, grade export 100% achieved, dashboard load <3s pending.
• Student Alex Chen — Junior high mobile comfort, goals lead team victory understand strategy collaborate, pain unclear optimal decision coordinating anxiety vs AI. Workflow: Auth→Join PIN→Create/Join team→View briefing→Make 3-6 decisions→Submit→Team coordination→View results→Leaderboard→Announcements→Final dashboard→Export. Success: auth <10s achieved, join >95% in test, decision reliability 100% achieved, sync <2s achieved, accuracy 100% achieved.
• IT Admin — wants self-hostable, low ops, Docker Compose, no K8s overhead, env var config, health check, logs.

4.4 User Stories (from prd.json canonical):
US-005 Production JWT Config P1 — PRACTENTURE_JWT_SECRET required error if missing, EXPIRY_HOURS default 24, CORS_ORIGINS default *, HOST default 0.0.0.0 PORT 8000, health reflects — COMPLETED passes true.
US-006 Apple/Google JWKS P2 — Apple token vs https://appleid.apple.com/auth/keys, Google vs https://www.googleapis.com/oauth2/v3/certs, payload validated issuer/audience/expiry, JWKS cache 6h TTL, same token format as password — COMPLETED passes true.
US-003 iOS Auth Integration P3 — AuthService, Keychain not UserDefaults, auto-attach Authorization header, refresh transparent, logout clears — COMPLETED via AuthManager + KeychainWrapper.
US-004 iOS WebSocket P4 — WebSocketService URLSessionWebSocketTask, auto-reconnect max 3 exponential, UI updates round_complete/leaderboard_update, status indicator, fallback polling — COMPLETED ReconnectableWSClient + WebSocketManager.
US-001 Prof Web Dashboard Session Mgmt P5 — Login at /dashboard/login, dashboard shows active sessions status, create form name/rounds/teams/config, detail with live leaderboard, Start/End/Advance, WebSocket real-time, configurable backend URL — COMPLETED templates/dashboard.html Jinja2 + router dashboard.py.
US-002 Prof Web Dashboard Grade Export P6 — Export Grades + Leaderboard buttons, browser download correct filename, existing /export/grades & /export/leaderboard — COMPLETED.
US-007 Integration Tests P7 — session creation REST, student login token verification, join REST, decision submission REST, WS connect/broadcast, grade CSV export, dashboard render, Apple/Google verification, 20-student E2E, and exact-SHA CI gates — deployed baseline passed 502 local backend/release tests.
US-014 LoginView 3-mode P14 — Professor Login, Student Login, Student Register, professor validates /api/auth/login password provider, student Apple/Google, register via /api/auth/register, error messages — COMPLETED LoginView.swift 3 tabs.
US-015 LaunchView auth check P15 — checks token on appear, no token shows LoginView sheet medium detent, authenticated shows Welcome back name, logout button — COMPLETED.

4.5 Functional Requirements Deep Dive:

Auth:
• POST /api/auth/login provider password/apple/google — password: DB check bcrypt, apple/google: JWKS verification RSAAlgorithm.from_jwk, 6h TTL cache, payload iss/aud/exp validated, returns JWT HS256 24h + role professor/student + optional refresh_token.
• POST /api/auth/register student — idempotent, studentId, name, teamName, password.
• POST /api/auth/verify JWT — verify token validity.
• POST /api/auth/refresh refresh_token — returns new accessToken + refreshToken, coalesce concurrent refresh via NSLock+Task.
• POST /api/auth/professor-only JWT+Prof — 403 for non-prof role.
• iOS: AuthManager stores jwt_token + refresh_token in KeychainWrapper, AuthState Observable isLoggedIn/userRole/userName, NetworkService attaches Authorization Bearer.

Session Mgmt:
• POST /api/sessions Professor — config totalRounds 1-50 default20, numberOfAICompetitors 0-20 default3, randomSeed default42, startingCash >0 default500k, initialEquity default300k, plantCapacity >=100 default10000, maxOvertime 0-50 default25, min/max wage dividend etc., teams List[TeamConfig], created_by, maxHumanTeams 30 default — returns sessionId+code BIZ-XXXXXX.
• GET /api/sessions — list all.
• GET /api/sessions/{code} — details.
• POST /api/sessions/{code}/join — teamName+studentId → teamId+teamName+round+state auto assign Alpha/Beta/Gamma...
• POST /api/sessions/{code}/start Prof — state CREATING→ACTIVE, currentRound 1, broadcast ws session_start.
• POST /api/sessions/{code}/end Prof — state → FINISHED/COMPLETED, final results.
• GET /api/sessions/{code}/status — sessionId/code/state/currentRound/totalRounds/teamsSubmitted/totalTeams.
• GET /api/sessions/{code}/teams — teamName/isAI/aiStrategy/studentId.
• DELETE /api/sessions/{code} — delete.
• Intervention: POST /api/dashboard/{code}/pause → state PAUSED + broadcast session_paused, POST /resume → ACTIVE + session_resumed, POST /announce message → broadcast announcement + store, POST /highlight/{teamId} → broadcast team_highlighted.
• Difficulty: POST /api/dashboard/{code}/difficulty — adjust market volatility/AI aggressiveness.

Simulation:
• POST /api/sessions/{code}/submit_decision Student/Prof — round+teamId+decision PlayerDecision 25+ fields validated gt/ge/le — returns accepted.
• GET /api/sessions/{code}/decisions/{round}/{teamId} — view decisions.
• POST /api/sessions/{code}/process_round Prof — collect decisions map, team_states, engine process_round → engine_results+new_states → store_results + update_team_state + broadcast round_complete.
• POST /api/sessions/{code}/advance — process current + auto-gen AI decisions next (convenience).

Leaderboard & Results:
• GET /api/sessions/{code}/leaderboard — Entry teamName/studentName/totalScore/eps/roe/stockPrice/imageRating/creditRating/cumulativeProfit/rank sorted totalScore desc assign rank.
• GET /api/sessions/{code}/results — all rounds dict roundNum->[RoundResult model_dump].
• iOS wiring remaining gap #1: LeaderboardView uses local session.leaderboard vs NetworkService.getLeaderboard — easy fix.

Announcements:
• POST /api/sessions/{code}/announcements Prof — message+authorId/name → stored.
• GET /api/sessions/{code}/announcements — chronological newest first, relative time formatting.

Export:
• GET /api/sessions/{code}/export/grades Prof — CSV grade export.
• GET /api/sessions/{code}/export/leaderboard Prof — CSV leaderboard.
• iOS PDFExporter + CSVExportViewModel.

Dashboard:
• GET /dashboard — SPA login or dashboard HTML FileResponse template dashboard.html 503 if not found.
• GET /api/dashboard/sessions JWT Prof — summary list.
• GET /api/dashboard/monitor/{code} Prof — teamData teamId/teamName/isAI/studentId/submitted/state/latestResult, leaderboard rank sorted.
• GET /api/dashboard/{code}/analytics Prof — sessionId/code/currentRound/totalRounds/state/teams[performanceOverTime profit/cumulativeProfit/stockPrice/totalScore/marketShare per round]/rounds[totalProfit/averageStockPrice/totalMarketShare/teamCount]/marketData.

Realtime:
• ws://host/ws/{code}?token=JWT — auth JWT query param, session-based rooms, heartbeat 30s, auto-reconnect, messages: round_complete, announcement, status_update, session_paused/resumed, team_highlighted.

Health:
• GET /api/health no auth — status healthy service practenture-backend config host/port/cors/jwt_secret_configured/jwt_expiry.
• GET /health Nginx proxy to /api/health.

Push/MFA/Extras:
• Push router: APNs+FCM unified service, push_models, templates, management API.
• MFA: TOTP 2FA, enforcement middleware, recovery codes.
• Tenant: isolation routing config.

4.6 Non-Functional:
• Availability: Single EC2 99.5% t3.micro, future multi-AZ ALB 99.9%.
• Latency: API p95 <300ms, WS broadcast <2s, dashboard load <3s.
• Scalability: t3.micro 30 human +20 AI teams 1 session comfortably, SQLite ok <100 concurrent, PostgreSQL needed >100. Stateless JWT enables horiz scale, WS needs Redis pubsub for multi-instance later.
• Reliability: 100% decision submission, offline queue sync-on-reconnect, retry logic.
• Security: JWT HS256, bcrypt, Keychain encrypted, HTTPS future certbot, no PII beyond studentId name, session codes 10-char random, tokens 24h expiry, role-based access professor-only endpoints, CORS configurable, WS JWT query param, rate limit future.
• Observability: Lifespan logs, health endpoint, Docker logs, container healthcheck curl -f http://localhost:8005/api/health 30s interval 3 retries, tini PID1 handling.
• Compatibility: iOS 17 min target 18, Swift 6 compliance zero warnings, Python 3.11+, SQLite/PostgreSQL dual, Chrome/Safari/Firefox/Edge web, tablets responsive.
• Maintainability: FastAPI pydantic models, SQLAlchemy ORM Base, Alembic migrations, Swift @Observable, Clean Views/ViewModels.

4.7 Acceptance Criteria (Release):
• Backend: deployed baseline passed 502 local backend/release tests and all five exact-SHA CI gates; health, authentication, session lifecycle, leaderboard/results/grades/announcements, and 20-student E2E are release-gated.
• iOS: BUILD SUCCEEDED on the pinned iPhone 17 Pro simulator with zero CI annotations; login, dashboard, decision, results, leaderboard, announcements, coaching, history, waiting-room, canonical HTTPS, and WebSocket paths remain release-gated.
• Infra: Docker Compose services healthy, Nginx terminates TLS and proxies /api/* and /ws/* to backend:8000, and ./ec2-deploy.sh deploy provides deterministic artifacts, migrations, health gates, atomic release swaps, and rollback preservation.
• Docs: System Architecture doc + MOP doc live in Drive, PRD.md, PROGRESS.md progress log, USER_JOURNEY.md, this master blueprint.

4.8 Metrics/KPIs Product:
Activation: professor creates session <30s, student auth <10s join <30s, join success >95%
Engagement: avg decisions per round 100%, rounds per 50-min class 6-8, WS uptime >99%, reconnect success >95%
Learning: decision quality improvement over rounds, leaderboard rank volatility, time-to-adapt
Satisfaction: NPS professor/student, support tickets 0 for self-hosted
Business: # active sessions, # students served, institutional conversions, cost per student $0 self-hosted vs $5k institutional managed.

═══════════════════════════════════════════════════════════════════════════════
5. HLD — HIGH LEVEL DESIGN
═══════════════════════════════════════════════════════════════════════════════

5.1 System Architecture Diagram (as deployed):

+--------------------------------------------------------------------------------+
|                          Practenture Platform LIVE                                 |
+--------------------------------------------------------------------------------+
|                                                                               |
|  +-------------------+   HTTP/WS REST   +------------------------------+      |
|  | iOS App (SwiftUI) | <------------->  | FastAPI Backend              |      |
|  | 83 files 19.3k LoC|                  | Docker: practenture-backend     |      |
|  | - Auth JWT Keych  |   /api/* /ws/*   | Port 8000 internal only      |      |
|  | - Sessions Join   |                  | + Simulation Engine (det)    |      |
|  | - Dashboard Decis |                  | + WebSocket Manager rooms    |      |
|  | - WS heartbeat    |                  | + SQLite/PostgreSQL + Alembic|      |
|  | - Offline Queue   |                  | + Auth JWT+JWKS 6h cache     |      |
|  +-------------------+                  +------------------------------+      |
|        ^                                          |                          |
|        | HTTPS/WSS via nginx                     |                          |
|  +-------------------+   HTTP WS      +-----------v------------------+      |
|  | Prof Web Browser  | <------------> | Nginx Reverse Proxy          |      |
|  | /dashboard SPA    |   Port 443     | nginx:1.25-alpine            |      |
|  | Canvas/LMS etc    |                | /api/→backend:8000           |      |
|  +-------------------+                | /ws/→backend:8000 upgrade   |      |
|                                       | 86400s timeout buffering off |      |
|                                       +------------------------------+      |
|                                                    |                        |
+----------------------------------------------------|                        |
| AWS EC2 us-east-1 t3.micro AL2023 20GB gp3         v                       |
| DNS practenture.com SG 80/443/22 | practenture-net bridge + DNS backend:8000   |
+--------------------------------------------------------------------------------+

5.1.1 Active Architecture Correction and Administrator Control Plane (2026-07-31):
• Authoritative public origin: https://practenture.com; active backend host: 100.58.36.238. Clients use DNS rather than a production IP.
• The deployed Admin V2 control plane provides MFA-protected Administrator APIs for Professor invitations, organizations, account status, health, backup/restore evidence, audit, and backup-gated scoped test cleanup.
• Routine administration must not use ad hoc SQL. SQLite remains the current single-writer store with online encrypted backups and restore drills; managed PostgreSQL is the scale/HA target.
• Authoritative details: docs/architecture/SYSTEM_ARCHITECTURE.md, docs/architecture/ADMIN_DATABASE_LLD.md, docs/architecture/ADMIN_MFA_LLD.md, and docs/plans/2026-07-26-owner-admin-database-operations.md.

Flow 1 round: Professor creates POST /api/sessions → BIZ-XXXXXX → Students join POST /join → Team assignment Alpha/Beta... → Round begins POST /start → Students submit POST /submit_decision → Professor monitors dashboard live submission counts via WS → Professor triggers POST /process_round → Engine processes all simultaneously → store_results + update_team_state → WS broadcast round_complete → Students see live leaderboard+individual results → currentRound increments → repeat until totalRounds → POST /end → final results → Export grades CSV LMS.

Auth flow: LaunchView checks Keychain JWT → no token → LoginView sheet 3-mode → Student Apple → POST /api/auth/login provider apple + identityToken → Backend fetches Apple JWKS RSA keys n/e, RSAAlgorithm.from_jwk, verify iss https://appleid.apple.com aud PRACTENTURE_APPLE_AUDIENCE? verify_aud False if empty, exp → return JWT HS256 24h + role → iOS stores Keychain attach Authorization: Bearer <token> all future → token refresh coalesced.

5.2 Component Deep Dive:

Backend (main.py lifespan):
• asynccontextmanager startup print config host/port/cors/jwt_secret_configured/jwt_expiry/DATABASE_URL, await init_db() → close_db on shutdown.
• CORSMiddleware uses deployment-configured explicit origins from PRACTENTURE_CORS_ORIGINS; wildcard production origins are not the intended configuration.
• Global error handlers RequestValidationError 400 detail errors(), general Exception 500 internal server error.
• Routers include auth, websocket, sessions, decisions, announcements, grades, leaderboard, dashboard, push.
• Endpoints /teams and /results and /advance in main.py convenience.

Database dual-mode (database.py):
• In-memory fallback class Database code → Session mapping TeamConfig decisions per round team_states results announcements, methods get_session, get_decisions, has_decision, store_results, update_team_state etc.
• Async SQLAlchemy when DATABASE_URL postgres/sqlite: create_async_engine, sessionmaker, Base from models.py, init_db creates tables if needed, Alembic Config/migration for migrations.
• Db Models: DbUser id UUID PK default uuid4 username unique index password_hash role professor/student default student email index provider password/apple/google/auth0 default password auth0_id unique index created_at; DbTenant id slug unique name is_active settings JSONB created_at; DbSession id code unique index tenant_id FK config JSONB state default creating created_by created_at current_round max_human_teams teams JSONB index tenant_state; DbDecision id UUID session FK etc.

Simulation Engine (simulation_engine.py):
See What section constants/functions. Deterministic seeded RNG per round predictable reproducible same seed same results. Noise 5% uniform. No race conditions.

WebSocket Manager (ws_manager.py):
• class ConnectionManager: Dict code->Set[WebSocket], connect, disconnect, broadcast, ping/pong.
• Exponential backoff client side ReconnectableWSClient.

Auth Providers (auth_providers.py):
• JWKS cache dict provider→(keys, expiry timestamp 6h TTL).
• verify_apple_token / verify_google_token fetch https://appleid.apple.com/auth/keys and https://www.googleapis.com/oauth2/v3/certs via httpx, find kid, RSAAlgorithm.from_jwk(json.dumps(jwk)), decode_options verify_aud False when no audience env configured fixing InvalidAudienceError, algorithms RS256.

Frontend iOS Architecture:
• App: PractentureApp entry.
• Models: SimulationSession (code, state ACTIVE/PAUSED/FINISHED, currentRound, backendCurrentRound, totalRounds, startingCash, numberOfAICompetitors, plantCapacity, isAI etc), Team local+synced name members decisions submissionCount currentScore, Decision pricing/inventory/marketing, RoundResultBackend flat approx vs RoundResult detailed, Announcement, CreditRating enum.
• Services: AuthManager (JWT Keychain), AuthState Observable, KeychainWrapper, and NetworkService shared @Observable. The base URL comes from the Info.plist PRACTENTURE_BACKEND_URL key populated by the active xcconfig; the code fallback is the same canonical HTTPS origin. URLSession bypasses response caching for authoritative backend state, uses bounded timeouts, and supports coalesced token refresh.
• SyncService dual adapter FirebaseSyncAdapter+LocalSyncAdapter protocol abstraction, FirebaseRealtimeSync live listeners.
• WebSocketManager session rooms heartbeat auto-reconnect.
• ViewModels: SessionListViewModel loadSessions backend API in-mem currently needs backend integration gap #1 fix ~1h, SessionMonitorViewModel startPolling 10s pollBackendStatus processRoundWithBackend endSessionWithBackend fallback local engine, LeaderboardViewModel getLeaderboard wiring needed Gap #1, JoinSessionViewModel getSession(byCode) getTeams syncAnnouncements config from backend SessionBackend.config fallback defaults, CSVExportViewModel real data fetch.
• Views: Professor tab 10 views (AnalyticsDashboard, Announcements, CreateSession, GradeMapping, ProfessorLeaderboard, ProfessorTabView, RoundControl, SessionList, SessionMonitor, SessionResults, TeamManagement), Student tab 7 views (AICoach, JoinSession, PerformanceHistory, RoundResults, StudentAnnouncements, StudentLeaderboard, TeamDashboard, WaitingRoom), Shared (Login, Settings About CoachingBubbles MetricCards RoundCharts StatusBadges LeaderboardRows), Launch.
• Engine local iOS mirrored simulation for offline test.
• Config: Debug, Staging, and Release xcconfig files define PRACTENTURE_BACKEND_URL. Debug and Release use https://practenture.com; the build publishes the selected value through Info.plist. No production ATS exception is required.

Infrastructure:
• Dockerfile uses a Python 3.12 slim multi-stage build, a non-root practenture user, Uvicorn on port 8000, and an internal /api/health check.
• docker-compose.yml binds backend diagnostics only to host loopback, persists SQLite and encrypted Admin backups in db-data, requires deployment-managed secrets, and exposes only the pinned Nginx service on public ports 80/443.
• nginx-practenture.conf terminates public HTTPS for practenture.com, redirects HTTP to HTTPS, applies HSTS/security headers, and proxies API/WebSocket traffic to backend:8000 over the private Compose network.
• ec2-deploy.sh REGION us-east-1 INSTANCE_TYPE t3.micro KEY_NAME practenture STATE .ec2-state.json, provision 7 steps verify prereqs aws jq, create SSH key pair check local ~/.ssh/practenture never overwrite Python write not shell redirect security tools intercept, SG practenture-sg 80/443/22, launch ami-0c101f26f147fa7fd 20GB gp3 tag Name=practenture-backend, wait running+status OK, save state, configure SSH remove old known_hosts -R wait SSH up to 40*5s test echo ready, install Docker dnf docker git wget jq, systemctl start enable, usermod -aG docker ec2-user, install docker-compose binary curl GitHub v2.24.0 /usr/local/bin/docker-compose chmod +x AL2023 no plugin, verify docker --version.
• Deployment uses only ./ec2-deploy.sh deploy: deterministic artifact staging, source/manifest validation, encrypted backup and restore drill, migrations, health checks, atomic release pointer swap, public HTTPS verification, and rollback-image preservation. Runtime secrets remain deployment-managed and are never generated into documentation.
• destroy terminate instance wait terminated rm state, SSH key+SG remain reusable.
• Issues fixed 9 documented in MOP section 5.

iOS backend URL configuration checklist:
1. Set PRACTENTURE_BACKEND_URL in the intended Debug, Staging, or Release xcconfig.
2. Confirm the built Info.plist exposes that value under PRACTENTURE_BACKEND_URL.
3. Keep NetworkService's missing-key fallback aligned with the canonical HTTPS origin.
4. Clean and reinstall the app when validating a changed build configuration; do not introduce raw-IP HTTP or ATS exceptions for production.

5.3 Scalability Path:
Current: t3.micro 2 vCPU 1GB RAM handles 1-2 concurrent sessions 30 teams each easily (SQLite in-mem cheap). Cost $0 free tier first yr then ~$6/mo + EBS $2 = $8/mo vs Render/Railway $20-30/mo — EC2 choice correct for control/cost predictability at scale as Luis requires.
Next (100 concurrent sessions): t3.small, PostgreSQL RDS or self-host postgres container, Redis for WS pubsub to allow multiple backend replicas, ALB, S3 for CSV/PDF exports, CloudWatch logs, auto-scaling group.
Future (1000+ sessions): Kubernetes EKS or ECS, sharded WS by session code consistent hash, read replicas, CDN CloudFront.

5.4 Security:
Authz: JWT role enforcement remains authoritative for iOS/Professor APIs. Admin V2 uses separate opaque revocable sessions, CSRF protection, recent authentication, bcrypt with legacy-hash migration/equalized failure work, durable account-wide throttling, and server-side Owner authorization.
Administrator MFA: shared backend/mfa.py TOTP primitives; AES-256-GCM protected seeds; possession-confirmed pending enrollment; hashed one-time recovery codes; transactional TOTP counter/recovery consumption; immutable redacted audits; no seed or recovery material in persistent browser storage.
Transport: practenture.com uses HTTPS with HSTS through Nginx; HTTP redirects to HTTPS. Public TLS and internal container health are deployment gates.
Data: No PII beyond studentId name, FERPA OK self-host, GDPR delete cascade session→teams→decisions→results, SQL injection protected SQLAlchemy ORM, XSS protected via SwiftUI auto-escape + FastAPI validation.
Rate limiting: Admin V2 uses durable SQLite-backed account/client/challenge buckets; public and classroom APIs use their route-specific policies.
CORS: production origins are explicitly configured through PRACTENTURE_CORS_ORIGINS; wildcard origins are not an approved production configuration.

5.5 File Structure (current live):
Practenture-ios/Practenture/
├── Practenture/ (iOS Xcode project 83 Swift)
│   ├── AuthManager.swift JWT+Apple/Google Keychain
│   ├── NetworkService.swift HTTP client + models + refresh coalescing
│   ├── LoginView.swift 3-mode
│   ├── LaunchView.swift auth-gated
│   ├── SessionMonitorView.swift Prof monitor polling
│   ├── TeamDashboardView.swift Student dashboard BackendState live
│   ├── Views/Professor/ 10 views
│   ├── Views/Student/ 8 views
│   ├── Views/Shared/ Components Launch
│   ├── Views/Components/ MetricCards CoachingBubbles etc
│   ├── Services/ SyncService FirebaseRealtimeSync etc
│   ├── Models/ SimulationSession Team Decision etc
│   ├── Engine/ Local simulation mirror
│   ├── Config/ Debug.xcconfig Release.xcconfig Staging.xcconfig
│   └── Practenture.xcodeproj/
├── backend/ (FastAPI 1,777+ lines)
│   ├── main.py lifespan CORS error handlers health routers teams results advance
│   ├── models.py Pydantic Session/PlayerDecision/RoundResult/Leaderboard etc + SQLAlchemy Base + enums SessionState CREATING/ACTIVE/COMPLETED/FINISHED + SessionConfiguration TeamConfig etc + ORM DbUser/DbTenant/DbSession/DbDecision
│   ├── database.py dual-mode in-mem Database + async SQLAlchemy init_db close_db seed
│   ├── auth.py JWT core creation/verification env var config HTTPBearer auto_error False 401 not 403 fix
│   ├── auth_providers.py Apple/Google JWKS 6h TTL RSAAlgorithm.from_jwk verify_aud False fix
│   ├── ws_manager.py per-session groups ping/pong
│   ├── simulation_engine.py deterministic demand/cost/credit engine seeded RNG 5% noise
│   ├── analytics_service.py aggregation
│   ├── mfa.py TOTP 2FA
│   ├── push_service.py APNs/FCM unified + push_models + templates + routers/push.py
│   ├── customization.py
│   ├── tenant_manager.py
│   ├── models_db.py Alembic compatible
│   ├── alembic_config.py + alembic_migration.py
│   ├── routers/ auth.py sessions.py decisions.py leaderboard.py announcements.py websocket.py dashboard.py grades.py push.py
│   ├── templates/ dashboard.html professor SPA
│   ├── Dockerfile multi-stage + docker-compose.yml + nginx.conf + ec2-deploy.sh + requirements.txt + .ec2-state.json + .env
│   ├── test_backend.py 18 tests + test_phase5.py 13 tests + test_e2e.py 29 tests = 60 total all passing
│   └── ...
├── PRD/ practenture_prd.md, prd.json (US-005 etc), sota_research.md, prompt_generation.md
├── PRD.md (canonical Product Requirements)
├── PROGRESS.md (historical progress log; exact-SHA CI is authoritative)
├── USER_JOURNEY.md (prof + student + AI behaviors + tech flow)
├── IMPLEMENTATION_PLAN.md
├── PROFESSOR_API_ANALYSIS.md
├── COMPREHENSIVE_CODE_REVIEW.md
├── progress.txt
└── .github/workflows/ci-cd.yml backend tests + iOS build+test + lint ruff/flake8 + Docker build push Docker Hub + Heroku deploy

═══════════════════════════════════════════════════════════════════════════════
6. USER JOURNEYS
═══════════════════════════════════════════════════════════════════════════════

6.1 PROFESSOR JOURNEY — Prof Sarah Mitchell, Business Admin, moderate tech, goals classroom sims monitor progress grade fairly export, pain joining issues lack visibility manual grading.

PRE-CLASS PREPARATION (5 mins):
Sarah opens the Practenture Professor dashboard over HTTPS, enters her deployment-provisioned credentials or approved SSO identity, and clicks **Create New Session**. She configures the class name, rounds, teams, starting finances/capacity, AI difficulty, optional deterministic seed, audience complexity, industry, and market-shock settings. The backend creates the session and returns its `BIZ-XXXXXX` code, which Sarah stores for classroom distribution.

CLASS LAUNCH (2 mins):
Sarah projects code BIZ-K8P2Q9 QR via LMS/email/in-class. Opens Monitor view live overview number teams joined avg decision submission time market volatility leaderboard anonymized option. Watches WebSocket live team formation notifications Phoenix Inc etc online/offline indicators session status current round teams submitted. Confirms all 6 teams ready clicks Start simulation round 1 begins immediately students notified.

ACTIVE FACILITATION (30-50 mins typical 50-min class):
Loop per round: Students make decisions (see student journey) submit. Sarah sees Team List checkbox ✓ submitted / ✗ pending e.g. "4/6 teams submitted" individual member names online status currentRound timer AI competitor status active/inactive. Live leaderboard auto-updates via WS (optional anon), stock price charts per team EPS ROE cumulative profit marketShare S/Q reputation creditScore anomaly detection. Identifies teachable moments: convergent strategies everyone pricing same → pause discuss game theory; market failures oversupply price wars → highlight concept; innovations creative diverging → highlight spotlight.
Intervention tools:
• Pause freezes simulation clock for discussion broadcasts session_paused.
• Highlight flags interesting decision pattern broadcasts team_highlighted → all eyes.
• Announce sends message all teams or specific team/individual e.g. "Round 3 deadline 10 mins!" "Team Alpha interesting pricing move everyone watch" Delivered WebSocket push StudentAnnouncementsView relative timestamp.
• Adjust modifies difficulty on-fly market volatility AI aggressiveness e.g. if class too advanced increase Easymed→Hard or inject external shock recession boom supply chain.
When ready tap Process Round engine computes simultaneously results broadcast round_complete Professor sees updated leaderboard instantly.

DEBRIEF & ASSESSMENT (10-15 mins):
Quick: Review session analytics performance trends key learning moments from simulation. Highlight e.g. "Notice price war round 4 collapsed margins".
Generate automated competency reports aligned AACSB/ABET creativity critical thinking financial literacy strategic analysis. Export data: Grade CSV per-student metrics team_name member_names final_score round_1..N scores credit_rating inventory etc + Leaderboard CSV final standings raw data research. PDF performance report session details team performance round-by-round cumulative investments via UIGraphicsPDFRenderer. Prepare next session adjusted parameters based learning needs.

SUCCESS METRICS PROFESSOR: session creation <30s achieved, student join >95% in test, real-time sync <2s achieved, grade export accuracy 100% achieved, dashboard load <3s pending (needs HTML refinment).

WORKAROUND KNOWN ISSUES: Students can't join → verify code case-sensitive correct BIZ-... ensure ACTIVE not FINISHED check professor role; Real-time not appearing → check WS connection status header internet; Leaderboard stale → refresh session card known Gap #1 local vs backend.

6.2 STUDENT JOURNEY — Alex Chen Junior Business high mobile comfort goals lead victory understand strategy collaborate pain unclear optimal decisions coordination anxiety vs AI.

ONBOARDING (3-5 mins):
Alex downloads Practenture from App Store opens LaunchView checks Keychain JWT if no token shows LoginView sheet medium detent else Welcome back Name! Choose Apple Sign-In one-tap FaceID recommended or Google or Email/Password. Backend verifies JWKS returns JWT role student token stored Keychain auto-login future opens. Dashboard shows Enter Session Code.

JOINING SESSION:
Gets 6-10 char code BIZ-K8P2Q9 from LMS professor. Taps Join Session enters manually or scan QR app POST /api/sessions/{code}/join verify ACTIVE fetch teams via getTeams(code) sees existing. Create New Team Phoenix Inc. invites teammates via PIN or Join Existing select from available wait professor approval maybe. System auto assigns naming Alpha/Beta/Gamma/delta or keeps Phoenix Inc. TeamJoined confirmation redirected TeamDashboardView WebSocket established wss://?token=JWT session room real-time.

TUTORIAL (first time 3-min interactive):
Navigation functional areas Marketing Ops Finance R&D, reading financial statements market data, submitting decisions viewing results, understanding real-time nature.

STRATEGY DEVELOPMENT Ongoing:
Review current financials market position cash equity debt stock price EPS ROE S/Q reputation credit. Analyze competitor moves real-time feed leaderboard market share price trends SocialMediaBudget impact? Formulate hypotheses market reactions price elasticity 1.5 SQ weight 1.2 marketing divisor 2000 multiplier 5.0 social contribution 0.3 outlets weight 0.3. Develop functional strategies within budget constraints starting cash 500k plant capacity 10k maxOvertime 25%. Use test decision feature simulate outcomes before committing (future).

DECISION EXECUTION Per Round (3-6 decisions maybe 6 areas):
Dashboard briefing: current round e.g. Round 2 of 6 starting cash balance e.g. $520k after profit team rank #3 of 6 online indicator green dot remaining time.
Three required inputs original spec pricing inventory marketing but extended full 6 areas implemented:
• Pricing: wholesale $5-50 slider numeric hint avg cost $20/unit impact preview higher price more margin fewer sales vs demand elasticity 1.5.
• Inventory ProductionQuantity units produce up plantCapacity limit hint demand estimate 300-450 impact more inventory more sales but holding costs storage $1.50/unit.
• Marketing e.g. $0-2000 small demo range vs real $0-100k plus celebrity influencer social etc hint average spend $800 impact brand awareness reach.
Plus extended: MaterialsQuality Economy/Standard/Superior, StylingBudget, ModelsOffered, TQMInvestment, R&D, Workforce BaseWage Incentive Training BestPractices, Production OT%, Finance CSR Dividends Loan Buyback Shares Issued, etc all per decision variable ranges appendix.
Tap Submit Round X confirm NetworkService.sendDecision POST /api/teams/{team_id}/decisions or /api/sessions/{code}/submit_decision payload round+teamId+decision saved Firestore real-time submission progress 2/3 submitted team lead sees remaining teammates haven't submitted. Team coordination features view teammate status live real-time receive professor announcements "15 mins remaining" see live leaderboard updates as teams submit. Before deadline can revise maybe? Submission idempotent.

ROUND RESULTS & FEEDBACK:
Trigger all members submit OR timer expires OR professor clicks Process Round. WebSocket delivers round_complete message results screen: revenue $45.2k costs $38.1k net profit $7.1k credit rating change Good→Excellent inventory 120 carry forward equity debt stock price S/Q investor score EPS ROE marketShare cumulativeProfit etc.
View updated leaderboard tab ranked list scores AI benchmark line context rank change ↑2 positions per-team breakdown tap detailed metrics. PerformanceHistoryView cumulative metrics over time stock trends marketShare vs class avg identify improvement.
Announcements StudentAnnouncementsView chronological newest first relative timestamp visual distinction professor vs system alerts.
AI Coach bubble tap contextual suggestions pricing advice market conditions production recommendations marketing tips financial guidance adapt performance available throughout decision-making learning tool not just scores.
Iterate strategy based outcomes participates professor-facilitated discussion market dynamics personalized feedback decision quality observes different strategies same market develops anticipation skills predicting competitor reactions.
Auto-reconnect ReconnectableWSClient exponential backoff decisions saved locally offline queue until reconnection sync-on-reconnect.

END OF SIMULATION FINAL RESULTS DASHBOARD:
After final round 6 completes SessionResultsView championship leaderboard final rankings per-team comprehensive stats table round-by-round performance chart AI benchmark comparison rank relative class average cumulative investments story. Tap Export Results CSV download complete decision history results + share screenshot if UI supports PDF report header code date team performance round results breakdown via PDFExporter.
Reflection Transfer: Connect simulation real-world business concepts e.g. price wars supply-demand first-mover reaction timing competitive differentiation, identify transferable skills market analysis strategic thinking financial literacy team collaboration communication, prepare assessment presentation apply learning case studies real business problems.

SUCCESS METRICS STUDENT: auth <10s achieved, join >95% in test fair, decision reliability 100% achieved, real-time <2s achieved, round result accuracy 100% achieved.

Common Issues: Can't find code check LMS ask prof resend PIN; Team not showing after join refresh app check FirebaseRealtimeSync startListening activation Gap #3 known; Leaderboard wrong rankings Gap #1 local vs backend pending; Losing connection WSClient auto-reconnects exponential backoff.

6.3 EDGE CASES & ERROR HANDLING:
• No internet: Offline queue stores decisions submit when back waitsForConnectivity true URLSession.
• Token expired: 401 → refreshToken() POST /api/auth/refresh coalesced NSLock+Task → retry original request once retryingAfterRefresh true prevent infinite recursion if refresh fails clear Keychain show LoginView.
• Session not found 404: Show friendly not found verify code.
• Session already started cannot join: Show started message ask professor.
• Duplicate join: Idempotent returns same teamId.
• Decision overwrite: Last write wins per round per teamId.
• Invalid decision field gt/ge/le validation: 400 detail errors array → show inline error validation exception handler.
• WebSocket disconnect: auto reconnect max 3 attempts exponential 1s 2s 4s show offline indicator retry manual button.
• EC2 down: Health check fails show maintenance message.
• ATS -1022 error: verify the built HTTPS origin and certificate trust; production does not use a raw-IP exception.

═══════════════════════════════════════════════════════════════════════════════
7. COMPETITIVE LANDSCAPE & ADVANTAGE
═══════════════════════════════════════════════════════════════════════════════

Market Map 2026:

| Feature | Practenture | Capstone | Marketplace | Cesim Global | Hubro | StratX | Forio |
| Processing Speed | Real-time WS seconds | 15-min batch | 5-min | 10-min | 8-min | 15-min | Custom |
| Professor Tools | Advanced real-time pause/highlight/announce/adjust | Basic | Basic | Moderate | Good | Good | Moderate |
| Adaptive Difficulty | Yes AI-powered per-team | No | Limited | No | Pre-set | No | Custom |
| Industry Customization | Yes Templates | No | No | Yes Multiple | Limited | Yes | Yes |
| Mobile | Native iOS (Android plan) | Web-only | Web/Mobile | Web-only | Web-only | Web-only | Web-only |
| Assessment | LMS/LTI CSV Competency AACSB | Basic grading | Basic | Moderate | Good | Good | Custom |
| Real Data | Planned Phase2 | No | Social media | Currency rates | No | No | Custom |
| Collaboration | Team roles CEO CMO etc | Individual | Team pitch | Limited | Team decisions | Team | Custom |
| Learning Analytics | Comprehensive trends comparison strategy | Basic | Moderate | Basic | Good | Moderate | Good |
| Setup Complexity | Low <2 mins | Moderate 30m | Low | Moderate | Low | High | High |
| Cost | $0 self-hosted open-source / $5k inst managed (projected) | $55/stdnt | $40/stdnt | $45/stdnt | $35/stdnt | $60/stdnt | $10k+ custom |
| Data Privacy | Self-hosted FERPA | Cloud vendor lock | Cloud | Cloud | Cloud | Cloud | Cloud |
| Offline | Yes queue sync-on-reconnect | No | No | No | No | No | No |

Strengths per competitor:
Capsim: De facto standard Capstone classes functional option intro business acumen cross-functional.
Cesim: Multi-language international business courses, 20+ simulations, Elite competition.
Marketplace Live: Academic focused strategic management scenarios.
Hubro: Marketing/Sustainable/FIN sims good UI web.
StratX: Fortune 100 exec ed premier large cohort scalability dedicated instructor certification.
Forio: Custom simulation dev specific training.

Practenture Competitive Advantages (6 Pillars):
1. Real-Time Engine 10-60x faster feedback vs competitors — closes feedback loop seconds not minutes, learning science win, enables teachable moments professor can pause highlight discuss emerging patterns as happen, builds anticipation/reaction skills transfer real business.
2. Professor-Centric Design — shifts instructor from admin to coach — intervention tools pause/highlight/announce/adjust not available elsewhere, live team view submission ✓/✗ leaderboard stock charts EPS/ROE/profit audit trail, analytics competency AACSB/ABET automated, grade export mid-sim CSV LMS.
3. Adaptive Learning System — AI-powered per-team difficulty adjustment market volatility competitor aggression tuning based class skill level keeps all in optimal learning zone zone of proximal development, avoids bored advanced struggling overwhelmed, 4 AI strategies + 3 difficulties + adaptive counter-play.
4. Industry Flexibility — templates Generic/Retail/Tech/Manufacturing/Healthcare + configurable parameters startingCash plantCapacity seed etc + upload custom market conditions learning objectives planned — competitors fixed.
5. Assessment Integration — LMS/LTI (CSV today LTI1.3 roadmap) + competency mapping + evidence raw data research + PDF reports automated.
6. Self-Hostable Zero-Cost + Native Mobile — zero licensing fee open-source runs your infra FERPA no vendor lock-in, vs per-student $35-60 at 100 students $3500-6000 per course per semester huge saving, plus native iOS SwiftUI not clunky web students demand mobile-first Gen Z, offline-first queue sync-on-reconnect field trip/network issues handled.

Moat Building Path:
Short: Speed to value (<2 min create vs 30 min), price ($0 vs $55), mobile nativity.
Medium: Data network effects — class performance data improves adaptive model; content moat — industry templates community contributions; LMS integrations sticky.
Long: Open-source contribution community professors build scenarios share; platform for research data + accreditation alignment; white-label SaaS for enterprises.

═══════════════════════════════════════════════════════════════════════════════
8. SWOT ANALYSIS
═══════════════════════════════════════════════════════════════════════════════

STRENGTHS:
• Technical: LIVE EC2 Docker over HTTPS, exact-SHA five-gate CI, Swift 6 qualified build, deterministic engine, real-time WS, offline-first, JWT/JWKS validation, and Administrator MFA.
• Product: Real-time only platform, professor intervention tools, full decision richness 25+ vars 6 areas, AI strategies 4 adaptive, analytics 6cards+trends+comparison, i18n 8 languages, PDF+CSV exports, push+MFA+multi-tenant implemented.
• Cost: Zero per-student self-hosted, $8/mo infra t3.micro vs $20-30 Render, free tier eligible, vs $35-60 competitor per student per course 100 students saves $3500-6000 per course per semester $7k-12k per year per course.
• Team/Execution: Single dev Luis full-stack iOS+backend+infra deployed end-to-end 9 issues fixed methodically MOP documented, health checks cron all clear, Ctrl cost control EC2 correct choice for scale vs Platform-as-a-Service lock.
• Paid Apple Dev $99/yr since July 2026 Sign In with Apple + Associated Domains available.
• Docs: System Arch + MOP + User Journey + PRD + Progress + User Guide comprehensive.

WEAKNESSES:
• Gap #1 Leaderboard backend sync still local vs getLeaderboard fix ~1h.
• Gap #2 Dashboard HTML refinement basic served needs enhanced UI classroom session cards roster table round controls high priority.
• Gap #3 FirebaseRealtimeSync startListening activation inconsistent after join.
• Gap #4 Session status periodic refresh needs timer or Firebase listener.
• GoogleSignIn SPM dependency needs add Xcode project runtime Google auth ~30min.
• iOS backend-origin changes remain build-time configuration and require a clean rebuild plus client-contract verification.
• TLS certificate renewal and public HTTPS health must remain monitored; raw-IP HTTP and broad ATS exceptions are prohibited.
• Production uses persistent SQLite with integrity/foreign-key checks; PostgreSQL remains the scale-up path rather than a current deployment requirement.
• Single t3.micro remains a single-availability-zone risk, mitigated by backup-gated releases and an immutable rollback image but not by active-active HA.
• Android thin-client implementation exists but still needs complete authentication modernization, UX validation, and distribution qualification.
• Web student app missing limits accessibility non-iOS users.
• Course management limited single session no multi-classroom bulk import yet.
• Brand unknown vs Capsim established 30+ years.

OPPORTUNITIES:
• Market growth $12.4B→$26.8B 8.9% CAGR + simulation learning $17.2→$56.8B 14.2% CAGR + higher-ed sim +$3.23B 23.3% CAGR huge tailwind.
• MBA enrollment rebound + experiential learning mandate AACSB.
• Gen Z real-time interactive expectation — competitors batch old paradigm ripe for disruption.
• Open-source self-hostable wave — universities want data control FERPA privacy cost cuts budget pressures.
• AI boom enables adaptive difficulty competitor counter-play personalized feedback — competitors static.
• LMS LTI 1.3 integration path Canvas/Blackboard/Moodle 4000+ universities — land and expand.
• Conference GTM AACSB ICAM, ACBSP etc professors word of mouth.
• Freemium PLG iOS App Store free download → self-host free → convert $5k/yr managed cloud low friction.
• Corporate training adjacent market executive education $60B.
• International i18n 8 languages already ready Spanish Portuguese French German Japanese Chinese Korean huge.
• Research data moat — decision-level dataset for publication partnership professors.
• White-label SaaS for enterprise internal training.
• Push to .edu partnerships pilot classroom beta zero cost case studies testimonials accreditation evidence.

THREATS:
• Incumbents Capsim/Cesim well entrenched department contracts multi-year bundling textbook publishers (Pearson McGraw).
• Price war — incumbents could drop student pricing bundle if threatened.
• Low switching cost for students but high for professors (curriculum integration lesson plans).
• Reintroducing broad ATS exceptions or cleartext origins could create App Store review and transport-security failures.
• Certificate expiry, DNS drift, or rollback corruption could affect the single production origin; release gates and recovery drills must detect these failures.
• Copycats — open-source real-time could be cloned quickly; need differentiate brand community.
• Economic downturn reduces discretionary MBA enrollments.
• Technical — WS at scale naive in-mem per-instance no Redis pubsub will break multi-instance; need future proof now design.
• Single developer bus factor — Luis alone need docs/runbooks (MOP good start) and tests to mitigate.
• Support burden — self-hosted users need support channel Discord/Slack.

SOWT (same as SWOT typo fix) — already covered.

═══════════════════════════════════════════════════════════════════════════════
9. VALUE ADD & COMPETITIVE ADVANTAGE DEEP DIVE
═══════════════════════════════════════════════════════════════════════════════

Quantified Value Add:

For Professor (time saved):
• Session creation: Capsim 30 min → Practenture 2 min = 28 min saved per session × 3 sessions per course × 2 courses per year = 2.8 hours saved/professor/year.
• Grading/export: Manual 1h → auto CSV 1 min = 59 min saved per session × 6 sessions = 5.9h saved.
• Intervention: Pause/highlight/announce enables teachable moments previously impossible adds learning value $ equivalent workshop.
• Total: ~8-10 hours saved per professor per year plus higher student engagement.

For Student (learning gain):
• Feedback loop: 15 min→seconds 900× faster feedback, retention +40% per learning science spaced immediate feedback.
• Engagement: Native iOS + real-time leaderboard + AI Coach → survey expected NPS +30 vs web-only.
• Skill transfer: 6 business areas interdependent vs siloed functional.

For Institution (cost):
• 100 students × $50 avg competitor × 2 semesters = $10k/yr per course vs $0 self-hosted or $5k managed = 50-100% saving.
• Data privacy compliance cost saved FERPA audit.
• 1,600 US business schools × $5k managed = $8M SAM US alone managed tier; global bigger; corporate training add $60B TAM.

Competitive Advantage Layer Cake:
Layer 1 Real-time (hard to copy requires WS infra rethink incumbents batch legacy).
Layer 2 Professor Tools (requires classroom empathy iteration with pilots).
Layer 3 Self-hostable Open Source (requires ideological commitment vs SaaS per-student monetization incumbents won't cannibalize).
Layer 4 Native Mobile Offline (requires Swift expertise not web).
Layer 5 Adaptive AI (requires ML dataset community network effect).

Each layer alone nice-to-have; combined moat defensible.

═══════════════════════════════════════════════════════════════════════════════
10. GTM — GO-TO-MARKET STRATEGY — USA
═══════════════════════════════════════════════════════════════════════════════

10.1 TAM SAM SOM:
• TAM: Global Business Simulation Games $12.4B 2025 + Simulation Learning $17.2B = ~$29.6B combined but addressable business simulation education subset ~$2B (est per student × MBA/undergrad corporate).
• SAM: US higher-ed business simulation — ~1,600 schools, 400k MBA + 2M undergrad business majors. At $40 avg competitor per student per course, 50% use simulation = 1.2M students × $40 = $48M/yr. Plus high school corporate ~$20M → $68M SAM US education simulation.
• SOM (3 yr): Target 100 schools × avg 200 students × $0 self-hosted free but 20% convert $5k managed = 20 paying × $5k = $100k ARR + pilot goodwill plus consulting custom scenarios $20k one-off 5 = $100k services Year 1 total $200k. Year 2 300 schools 60 paying $300k ARR + services. Year 3 600 schools 150 paying $750k ARR + marketplace templates. Plus open-source community growth.

10.2 Ideal Customer Profile (ICP):
Primary: Professor teaching Strategic Management, Capstone, Business Policy, Entrepreneurship at MBA or upper undergrad — pain manual simulation setup, wants real-time engagement, teaches 50-100 students per semester, early adopter uses iPad Apple products, active at AACSB conferences, measures student engagement.

Secondary: High school business/econ teacher DECA competition coach wants free tool.

Tertiary: Corporate L&D manager leadership development program 20-50 managers wants self-hosted private data.

10.3 Positioning Statement:
"For professors who want to make business strategy tangible, Practenture is an open-source real-time simulation platform that turns your classroom into a living market — where every decision gets immediate feedback, so you teach at the speed of business, not the speed of batch processing."

Messaging Pillars:
• Real-time = teachable moments.
• Professor as coach not administrator.
• Zero licensing self-hosted FERPA friendly.
• Native iOS students already on phones.

10.4 Pricing Strategy:
• Community Edition: Free open-source self-hosted forever GitHub MIT/Apache license $0 includes all core features single server Docker Compose docs community Discord support self-service.
• Managed Cloud: $5k/institution/year up to 10 concurrent sessions 300 students includes hosted domain HTTPS auto backups SLA 99.9% email support updates.
• Enterprise: Custom per private cloud multi-region SLA SSO SAML white-label custom scenarios LTI integration bulk import analytics predictive $15-25k/year.
• Student: $0 always.
• Competitive comparison anchor: vs $55 Capsim per student 100 students $5.5k per course per semester $11k/yr — Managed $5k/yr 54% cheaper unlimited courses students 100% data control bonus.

10.5 Channels:
• PLG: iOS App Store free download students pull professors (bottom-up). Student tries demo session code joins asks professor to adopt.
• Direct to professor: Cold email personalized referencing their course catalog syllabus Capstone strategic mgmt scrape university sites + LinkedIn. Provide 1-pager + demo video 2-min + sample grade CSV + accreditation mapping doc.
• Conferences: AACSB ICAM ($3k booth), ACBSP, ABSEL (Association for Business Simulation Experiential Learning), Academy of Management, DECA. Demo live 2-min session creation + QR join audience phones.
• Content SEO: blog posts "Capsim alternative free" "business simulation real time" "MBA simulation self-hosted FERPA" — target search intent professor evaluation.
• Community: GitHub open-source weekly release notes, Discord server for professors sharing templates custom market conditions, Reddit r/businessschool, r/MBA.
• Partnerships: LMS integration Canvas Commons, Moodle plugin directory, OpenStax textbook partner bundling.
• Pilots: Offer 5 pilot universities free managed hosting Fall 2026 in exchange case study testimonial logo + NPS + research publication access data.

10.6 Sales Motion:
Day 0: Outbound email to профессор list + inbound App Store.
Day 1: 15-min demo call professor screen share create session live show monitoring intervention tools.
Day 3: Pilot proposal 1 course free Fall semester 30 students we'll onboard Zoom 30 min share BIZ- code guide + docs.
Week 1: Pilot execution professor runs 1 session we shadow Slack support.
Week 2: Debrief survey NPS learning gains qualitative + quantitative (time saved, engagement).
Month 1: Close managed cloud upsell or keep free community advocate.
Prospect → Pilot → Case study → Reference → Expansion other courses department.

10.7 Marketing Plan:
• Website practenture.com (need buy domain) landing pages /professor /student /demo /pricing /open-source.
• Demo video 90 seconds: Problem latency gap → Solution real-time WS animation → Professor creates 2 min → Students join QR phones → Decisions → Live leaderboard → Debrief analytics export.
• One-pager PDF for professors 2 pages high density dark theme white pills GTM-style (Luis preference slides high density GTM-style white pills dark themes inline citations).
• Blog: Weekly case study pilot, technical deep dive simulation engine formulas, learning science real-time feedback.
• Social: LinkedIn Luis posts build in public, Twitter/X.
• Testimonials: Video professor student quotes.

10.8 Partnerships:
• LMS: Canvas LTI 1.3 Advantage deep linking grade passback, Blackboard, Moodle plugin.
• Content: OpenStax, Harvard Business Publishing simulations comparison page.
• Cloud: AWS Activate credits for startups $5k, GitHub Education.
• Accreditation: AACSB willing evaluation data mapping demonstration.

10.9 Metrics GTM Dashboard:
Activation: Website visits, App downloads, Session codes created, Pilot requests, Demo calls booked.
Engagement: Pilot completion rate, Avg rounds per class 6-8 target, WS latency p95 <2s, Decision reliability 100%.
Conversion: Pilot→Paid managed %, Free→Paid, Gross/Net retention, NPS.
Advocacy: # case studies, logos, referrals, GitHub stars, Discord members.

10.10 GTM Phases:
Phase A Validate (Now - Aug 2026): 5 pilot universities free, iterate gaps #1-4 fix leaderboard HTML real-time sync polling, add domain+HTTPS certbot, get first 3 testimonials, iOS App Store submission with HTTPS domain, docs site.
Phase B Launch (Sep-Dec 2026): Launch Product Hunt + Hacker News "Show HN: Open-source real-time practenture for education", conference AACSB, 20 paying managed institutions $5k = $100k ARR.
Phase C Scale (2027): LTI integration Canvas, Android app, web student app, template marketplace, 100 paying institutions $500k ARR, multi-tenant SaaS dashboard admin billing.
Phase D Expand (2028+): Corporate training product, white-label, global i18n GTM LATAM EMEA Asia, AI scenario generation.

10.11 Risks GTM & Mitigations:
• App Store review transport-security regression → mitigated by the canonical HTTPS origin, valid public certificate, and no production ATS exception.
• Professor inertia switching cost → free pilot low risk taking existing syllabus provide mapping lesson plans.
• Single-developer bus factor → mitigate with authoritative PRD/HLD/LLD/runbooks, exact-SHA CI evidence, deterministic deployment, and reviewed operational procedures.
• Support load self-hosted → community Discord, docs, video guides, limited managed SLA only for paying.

═══════════════════════════════════════════════════════════════════════════════
11. ROADMAP
═══════════════════════════════════════════════════════════════════════════════

Completed (Phases 1-9):
• Phase 1 Core iOS App local model team management round decisions leaderboard.
• Phase 2 Backend Foundation FastAPI JWT PostgreSQL REST CRUD 31 tests.
• Phase 3 Firebase Integration Firestore real-time sync WS Apple/Google auth.
• Phase 4 Classroom Production Layer professor dashboard web student-facing features grade export user journey docs.
• Phase 5 Auth+WS Production JWT config Apple/Google JWKS 6h TTL iOS AuthManager Keychain LoginView LaunchView check logout professor-only endpoint ReconnectableWSClient SessionJoinSheet backend data fetch dashboard SPA announcements export CSV iOS build fixed Swift6 zero warnings 58→60 tests.
• Phase 6 PDF Export PDFExporter 174 lines.
• Phase 7 Analytics Dashboard 380 lines class overview round trends team compare strategy distribution.
• Phase 8 i18n 8 languages 140 lines L10n 60+ keys SettingsView.
• Phase 9 AI Strategies 418 lines 4 strategies 3 difficulties Adaptive counter-play.
• Plus: Push notifications APNs+FCM, MFA TOTP, multi-tenant, Alembic migrations, customization, CI/CD GitHub Actions backend+iOS+lint+Docker+Heroku.
• Admin V2: secure Administrator control plane, Professor-access lifecycle, organizations/users/operations/audit/health/backup UI, opaque sessions, and complete TOTP MFA lifecycle deployed and production verified.

Remaining Polish (10-16h est):
• E2E test helpers auth headers (_submit,_process) fix 11→29 passing 60 total already fixed 2026 produce fully green.
• Professor Dashboard HTML refinement session cards roster table round controls 2-4h.
• SessionListViewModel.loadSessions backend API integration 1h.
• GoogleSignIn SPM dependency Xcode 30min.
• Session status polling timer HTTP fallback WS 1h.
• iOS UI tests login join decision flows 2-4h.
• Production deployment domain+HTTPS certbot SSL 2-4h.

Q3 2026 (Launch Readiness):
• Gap #1-4 fixes leaderboard backend sync real-time sync activation session status refresh.
• Domain practenture.com purchase Route53 EC2 alias + certbot Nginx HTTPS + wss.
• iOS App Store submission screenshots description keywords business simulation education.
• Website landing + docs site.
• 5 pilot universities.

Q4 2026 (Growth):
• LTI 1.3 Canvas integration grade passback.
• Web student dashboard (non-iOS users).
• Template marketplace industry scenarios.
• Bulk import CSV students.
• Android minimal wrapper WebView or native start.

2027 (Scale & Enterprise):
• Multi-classroom management admin console.
• Analytics predictive modeling KPI forecasting outlier detection ML.
• API access external LMS research.
• White-label customization per tenant.
• Billing Stripe.

═══════════════════════════════════════════════════════════════════════════════
12. RISKS & MITIGATIONS TECHNICAL
═══════════════════════════════════════════════════════════════════════════════

Tech:
• Single instance has no HA; persistent storage, encrypted application backups, verified restore drills, and rollback images reduce recovery risk but do not provide automatic failover.
• SQLite is persistent and integrity-checked but remains a single-writer capacity/availability boundary; managed PostgreSQL is the scale/HA target.
• WS multi-instance no pubsub → add Redis later list already in roadmap.
• Privileged authentication uses durable multidimensional throttling; broader public API abuse controls remain a roadmap item.
• No monitoring alerting → add CloudWatch alarms EC2 CPU + health endpoint UptimeRobot 1-min check Slack webhook.
• Runtime secrets are deployment-managed, excluded from Git and release artifacts, and remain candidates for migration to a managed secret store.
• TLS/HSTS are active; certificate renewal and fail-closed public HTTPS health remain operational controls.

Product:
• Continue validating Professor workflow depth and discoverability end to end; do not treat the deployed Admin V2 control plane as a substitute for Professor-facing UX.
• Android thin client exists and remains backend-authoritative; continue emulator-first contract and UX parity validation before broader distribution.

Business:
• Legal FERPA self-hosted helps but need DPA template.
• Open-source license choice MIT vs AGPL — MIT permissive adoption better but risk cloud providers cloning managed offering — AGPL protective but deters enterprise. Recommend dual-license AGPL community + commercial enterprise.

═══════════════════════════════════════════════════════════════════════════════
13. SUCCESS METRICS & KPlS
═══════════════════════════════════════════════════════════════════════════════

North Star: # students who experience teachable moment via real-time feedback per semester.

Product KPIs:
• Session creation time median <30s p95 <2m.
• Student join time median <30s p95 <2m join success >95%.
• Real-time latency p95 <2s WS message delivery.
• Decision submission reliability 100% (retry queue).
• Round processing time p95 <1s for 10 teams engine deterministic fast Python.
• iOS crash-free rate >99.5%.

Business KPIs:
• # active institutions, # sessions, # students, # rounds processed.
• Pilot completion rate >80%.
• NPS professor >50 student >40.
• Time saved professor >8h/year measurable survey.
• Conversion pilot→paid >20% managed tier.
• GitHub stars, Discord members, App Store ratings.

Learning KPIs (research):
• Decision quality improvement slope over rounds.
• Strategy adaptation speed.
• Market share volatility vs learning.
• Competency mapping AACSB learning goals.

═══════════════════════════════════════════════════════════════════════════════
14. APPENDIX
═══════════════════════════════════════════════════════════════════════════════

14.1 API Surface (complete):
Auth: POST /api/auth/login None login password/apple/google; POST /api/auth/register None; POST /api/auth/verify JWT verify token; POST /api/auth/refresh JWT refresh token; POST /api/auth/professor-only JWT+Prof prof gate; POST /api/auth/student-or-professor JWT Student/Prof gate.
Sessions: POST /api/sessions Prof create; GET /api/sessions None list; GET /api/sessions/{code} None details; POST /api/sessions/{code}/join None join team; POST /api/sessions/{code}/start Prof start; POST /api/sessions/{code}/end Prof end+results; GET /api/sessions/{code}/status None current state; GET /api/sessions/{code}/teams None roster; DELETE /api/sessions/{code} internal delete.
Decisions: POST /api/sessions/{code}/decisions or /submit_decision Student/Prof submit; GET /api/sessions/{code}/decisions/{round}/{teamId} None get decisions; POST /api/sessions/{code}/process-round Prof process round; POST /api/sessions/{code}/advance Prof advance process+auto AI next.
Leaderboard: GET /api/sessions/{code}/leaderboard None standings.
Results: GET /api/sessions/{code}/results None round results; GET /api/sessions/{code}/status already.
Announcements: POST /api/sessions/{code}/announcements Prof create; GET /api/sessions/{code}/announcements None list.
Export: GET /api/sessions/{code}/export/grades Prof CSV; GET /api/sessions/{code}/export/leaderboard Prof CSV.
Dashboard: GET /dashboard None SPA login or dashboard HTML; GET /api/dashboard/sessions JWT list for dashboard; GET /api/dashboard/monitor/{code} JWT real-time monitoring; GET /api/dashboard/{code}/analytics JWT analytics; POST /api/dashboard/{code}/pause Prof; POST /api/dashboard/{code}/resume Prof; POST /api/dashboard/{code}/announce Prof; POST /api/dashboard/{code}/highlight/{teamId} Prof; POST /api/dashboard/{code}/difficulty Prof adjust.
WebSocket: ws://host/ws/{code}?token=JWT JWT real-time updates.
Health: GET /api/health None healthy; GET /health Nginx proxy.
Push: routers/push.py management API.

14.2 Decision Variable Ranges Appendix from User Guide:
Pricing wholesale $20-150 internet $15-140 privateLabel $18-130 amazon $20-145 amazonAd $0-50k; Product quality Economy/Standard/Superior styling $0-30k models 1-8 TQM $0-20k; Marketing advertising $0-100k celebrity None/Local/National retail 0-50 rebate $0-20 delivery Standard/Rush social $0-25k; Workforce baseWage $10-40/h incentive $0-10/h training 0-40h bestPractices $0-15k; Production qty 1k-50k overtime 0-30%; Finance CSR $0-20k dividends $0-5/share loan $0-500k buyback 0-100k issue 0-200k.

14.3 Credit Rating Scale:
A+ Excellent, A Strong, A- Good, B+ Adequate, B Fair, B- Marginal, C+ Weak, C Poor, C- Very Poor, D Critical.

14.4 KPIs Formulas:
• EPS = (profit - preferred dividends)/sharesOutstanding Score higher better.
• ROE = netIncome/equity Score.
• StockPriceScore from stockPrice relative baseline $50.
• ImageScore reput 0-10 scaled.
• CreditScore 0-100 scaled D/E interest coverage cash ratio.
• TotalScore = sum weighted EPS+ROE+Stock+Image+Credit.

14.5 Market Size Citations:
• Business Simulation Games Market $12.4B 2025 → $26.8B 2034 8.9% CAGR North America 38.2% $4.7B dataintelo.com/report/business-simulation-games-market
• Simulation Learning $17.2B 2025 → $56.8B 2035 14.2% CAGR 2026 $19.6B researchnester.com/reports/simulation-learning-market/8298
• Simulation Learning Higher Ed +$3.23B 2025-2030 23.3% CAGR researchandmarkets.com/reports/5910520
• EdTech $187B 2025 → $437.5B 2033 grandviewresearch.com
• Competitors: Capstone 15-min, Marketplace 5-min, Cesim 10-min, Hubro 8-min, StratX large cohort scalability stratxsim.com

14.6 Environment Variables Full List:
PRACTENTURE_JWT_SECRET configures JWT signing; PRACTENTURE_JWT_EXPIRY_HOURS configures expiry; PRACTENTURE_CORS_ORIGINS configures approved browser origins; PRACTENTURE_HOST/PRACTENTURE_PORT configure the service listener; Administrator and Professor bootstrap credentials are required deployment secrets with no documented defaults; PRACTENTURE_APPLE_AUDIENCE and PRACTENTURE_GOOGLE_AUDIENCE configure OAuth audiences; DATABASE_URL configures persistence; NGINX_HTTP_PORT configures the edge listener; MFA protection keys and throttle policy are deployment secrets/configuration. Values never belong in source documentation.

14.7 iOS Backend Origin Runbook:
Debug.xcconfig and Release.xcconfig set PRACTENTURE_BACKEND_URL to `https://practenture.com`; Staging.xcconfig owns the staging origin. NetworkService reads the generated Info.plist value and falls back only to an HTTPS production origin. Raw EC2 addresses, cleartext ATS exceptions, and `NSAllowsArbitraryLoads` are not approved production configuration. After changing an xcconfig-backed value, clean and rebuild so the generated bundle metadata is refreshed.

14.8 9 Pitfalls Fixed (MOP Section 5):
1 curl-minimal conflicts curl AL2023 remove curl from dnf.
2 docker-compose-plugin not available AL2023 install binary GitHub v2.24.0 /usr/local/bin/docker-compose.
3 docker compose vs docker-compose syntax unknown shorthand -d changed to docker-compose.
4 PyJWT missing ModuleNotFoundError jwt added PyJWT==2.9.0 requirements.txt.
5 Original Nginx certificate bootstrap failed when certificate files were absent; the resolved deployment stages TLS material and fails closed on public HTTPS health.
6 Original Nginx upstream 127.0.0.1 caused a 502; the current Compose service route is backend:8000.
7 No HTTP listener health times out added port 80 server block.
8 dnf update noise 500 lines removed.
9 Nginx HTTP/2 uses `listen 443 ssl` with the supported separate `http2 on` directive.

14.9 Learning Lessons July 2026:
Apple Sign-In 500 InvalidAudienceError + KeyError x — RCA RSA vs EC keys Apple JWKS RSA RS256 n/e not EC ES256 x/y use RSAAlgorithm.from_jwk; PyJWT validates aud claim even without expected audience when present in token so verify_aud False when PRACTENTURE_APPLE_AUDIENCE empty GoogleLogin validation pattern test Google first simpler token isolates Apple issues.
ATS -1022 was encountered during the original raw-IP deployment. The current resolution is the canonical HTTPS origin; the production client does not retain an arbitrary-load or raw-IP exception.

14.10 Current Live Deployment:
Public origin https://practenture.com; AWS instance i-0f2ce26d05e4439cd at 100.58.36.238; containers practenture-backend and practenture-nginx healthy; persistent SQLite integrity verified; exact deployed source/image revision 1abb1aaee2dd49b59790a4b3c232cacdb3e2848a. All production changes use ./ec2-deploy.sh deploy; manual container replacement is not an approved release path.

14.11 Testing Verification (manual E2E passed):
Professor login → valid JWT; Session creation → BIZ-XXXXXX; Start → teamsSubmitted 0; Process round 0 results no submissions; End → status ended; Leaderboard empty (no rounds); Results empty; Grade export "No results available" expected; Dashboard sessions returns all; Announcements create+retrieve working; iOS build iPhone 17 Pro sim succeeded; 3-mode login Apple Google Professor implemented; EC2 live healthy professor login confirmed working.

END OF MASTER STRATEGY BLUEPRINT — Strategic narrative, PRD, HLD, journeys, competitive, SWOT, and GTM source as updated July 31, 2026. Detailed live technical authority resides in docs/architecture/SYSTEM_ARCHITECTURE.md and its linked LLDs.
