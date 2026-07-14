# BizSimAI

**Business Simulation Platform for the Modern Classroom**

BizSimAI is a real-time, team-based business simulation platform designed for MBA and undergraduate business courses. Professors create simulation sessions with configurable parameters (rounds, economy, AI opponents, scoring), and students form teams to make strategic decisions across multiple rounds, competing on investor scores and market position.

## Features

- **Dual Role System**: Professor dashboard for session management, student dashboard for decision-making
- **Real-Time Multiplayer**: WebSocket-powered live updates on rankings, submissions, and round progress
- **AI Competitors**: Configurable AI opponents with adjustable difficulty (Easy/Medium/Hard) to simulate market pressure
- **Investor Scorecard**: Multi-metric scoring (ROE, ROI, revenue growth, market share) with visual breakdown
- **Session Templates**: Pre-configured templates (Intro, Intermediate, Advanced) plus full custom mode
- **Cloud Backend**: FastAPI server with JWT auth, SQLite persistence, and WebSocket real-time sync
- **Local Demo Mode**: Full simulation engine runs offline — no server required for testing
- **Round Pacing**: Manual control or timed rounds with configurable deadlines and late submission policies
- **AI Coach**: In-app strategic guidance for students
- **Leaderboard**: Live rankings with trend indicators
- **Session Sharing**: Firebase-backed session sharing (Phase 5)

## Architecture

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│   iOS Client    │◄───────►│   FastAPI Server │◄───────►│   SQLite DB     │
│  (SwiftUI)      │ REST    │  (Python)        │         │  (data.db)      │
│                 │ WS      │                  │         │                 │
│ - Auth Screens  │         │ - REST API       │         │ - Sessions      │
│ - Dashboard     │         │ - WebSocket      │         │ - Teams         │
│ - Decision Form │         │ - Simulation     │         │ - Decisions     │
│ - Leaderboard   │         │   Engine         │         │ - Scores        │
└─────────────────┘         └──────────────────┘         └─────────────────┘
```

### iOS Client (Swift/SwiftUI)

- **Minimum Deployment**: iOS 18.0 / macOS 15.0
- **Architecture**: MVVM with `@Observable` (iOS 17+) and Combine
- **Networking**: `URLSession` with environment-aware base URLs (local dev vs production)
- **Real-Time**: `WebSocketTask` with exponential backoff reconnection (2s → 30s cap, max 10 attempts)
- **Game Engine**: Local `GameController` for simulation logic, decision scoring, and AI opponent behavior
- **Auth**: JWT token storage via Keychain, automatic refresh

### Backend (FastAPI/Python)

- **Framework**: FastAPI with async routing
- **Database**: In-memory SQLite with `data.db` file persistence
- **Auth**: Custom JWT implementation (no external auth dependencies)
- **Real-Time**: WebSocket manager with per-session room routing
- **Simulation**: Deterministic game engine with configurable market types and economy settings
- **Deployment**: Docker multi-stage build, Nginx reverse proxy, Heroku-ready

## Project Structure

```
BizSimAI/
├── BizSimAI/                    # iOS App (SwiftUI)
│   ├── BizSimAIApp.swift        # App entry point
│   ├── Views/                   # All SwiftUI views
│   │   ├── Launch/              # Splash screen
│   │   ├── Professor/           # Professor views (Login, Session List, Create Session)
│   │   ├── Student/             # Student views (Join Session, Dashboard, Decision Form)
│   │   └── Shared/              # Shared components (LoginView, etc.)
│   ├── ViewModels/              # MVVM ViewModels
│   │   ├── CreateSessionViewModel.swift
│   │   ├── SessionMonitorViewModel.swift
│   │   ├── TeamDashboardViewModel.swift
│   │   ├── LeaderboardViewModel.swift
│   │   └── JoinSessionViewModel.swift
│   ├── Services/                # Network and game services
│   │   ├── NetworkService.swift
│   │   ├── WebSocketManager.swift
│   │   ├── AuthManager.swift
│   │   └── SyncService.swift
│   ├── Engine/                  # Local game engine
│   │   └── GameController.swift
│   ├── Models/                  # Data models
│   ├── Assets.xcassets/         # App assets
│   └── Info.plist
├── BizSimAIUITests/             # XCUITest integration tests
├── backend/                     # FastAPI backend
│   ├── main.py                  # App entry point, middleware, router registration
│   ├── models.py                # Pydantic models
│   ├── database.py              # SQLite database layer
│   ├── simulation_engine.py     # Server-side game engine
│   ├── ws_manager.py            # WebSocket room management
│   ├── auth/                    # Auth providers (Google, Apple)
│   ├── routers/                 # API route modules
│   │   ├── auth.py              # Login, register, session creation
│   │   ├── sessions.py          # Session CRUD, status, join
│   │   ├── decisions.py         # Decision submission and validation
│   │   ├── leaderboard.py       # Rankings and scoring
│   │   ├── dashboard.py         # Session and team data
│   │   ├── grades.py            # Grade management
│   │   ├── announcements.py     # Professor announcements
│   │   └── websocket.py         # WebSocket endpoint routing
│   ├── templates/               # HTML templates (professor dashboard)
│   ├── test_e2e.py              # 29 E2E integration tests
│   ├── Dockerfile               # Multi-stage Docker build
│   ├── nginx.conf               # Nginx reverse proxy config
│   ├── docker-compose.yml       # Docker Compose for local dev
│   ├── deploy.sh                # Heroku deployment helper
│   ├── requirements.txt         # Python dependencies
│   └── .env.example             # Environment variable template
├── PRD.md                       # Product Requirements Document
├── PROGRESS.md                  # Project milestone tracker
├── MOP.md                       # Master Operations Plan
└── README.md                    # This file
```

## Quick Start

### Prerequisites

- Xcode 16+ (iOS 18 SDK)
- Python 3.12+
- Virtual environment tool (`uv` or `venv`)
- (Optional) Firebase project for Phase 5 features

### Running the Backend Locally

```bash
cd backend

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env from template
cp .env.example .env
# Edit .env with your settings (at minimum: BIZSIMAI_JWT_SECRET)

# Run the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API is available at `http://localhost:8000`. Swagger docs at `http://localhost:8000/docs`.

### Running iOS App (Local Dev)

The iOS app uses an environment-aware base URL:

- **Debug/Simulator**: `http://192.168.4.67:8000` (update in `NetworkService.swift` to match your Mac's IP)
- **Release/Production**: `https://bizsim-backend.herokuapp.com`

To find your Mac's IP on the local network:
```bash
ipconfig getifaddr en0    # Wi-Fi
ipconfig getifaddr en0    # Ethernet
```

Update the `BASE_URL` in `BizSimAI/Services/NetworkService.swift` if needed.

### Running iOS App (Demo Mode)

No backend required. Students can tap "Start Demo Session" on the Join Session screen to run the full simulation locally.

### Running Tests

**Backend E2E tests** (29 passing):
```bash
cd backend
python3 -m pytest test_e2e.py -v
```

**iOS UI Tests**:
```bash
xcodebuild test \
  -project BizSimAI.xcodeproj \
  -scheme BizSimAI \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro,OS=18.0' \
  -only-testing:BizSimAIUITests
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BIZSIMAI_JWT_SECRET` | *(required)* | Secret key for JWT token signing |
| `BIZSIMAI_JWT_EXPIRY_HOURS` | `24` | JWT token lifetime |
| `BIZSIMAI_HOST` | `0.0.0.0` | Bind address |
| `BIZSIMAI_PORT` | `8000` | Server port |
| `BIZSIMAI_CORS_ORIGINS` | `*` | Comma-separated CORS origins |
| `BIZSIMAI_GOOGLE_CLIENT_ID` | | Google Sign-In client ID |
| `BIZSIMAI_GOOGLE_CLIENT_SECRET` | | Google Sign-In client secret |

### Session Templates

| Template | Rounds | Starting Cash | Market | AI Difficulty |
|----------|--------|---------------|--------|---------------|
| `Intro` | 5 | $100,000 | Moderate | Easy |
| `Intermediate` | 10 | $150,000 | Competitive | Medium |
| `Advanced` | 15 | $200,000 | Aggressive | Hard |
| `Custom` | 3-20 | $50K-$500K | Any | Any |

### Default Credentials

| Role | Username | Password |
|------|----------|----------|
| Professor | `professor` | `bizsimai2026` |

## Deployment

### Docker

```bash
cd backend
docker-compose up --build
```

Server available at `http://localhost:8000` with Nginx reverse proxy and SSL termination.

### Heroku

```bash
cd backend
./deploy.sh deploy
```

The deploy script handles building, pushing to Heroku, and setting environment variables.

### Production Checklist

- [ ] Set `BIZSIMAI_JWT_SECRET` to a strong random value
- [ ] Configure CORS origins for your production domain
- [ ] Set up Google Sign-In credentials
- [ ] Configure SSL certificate (via Nginx or Heroku)
- [ ] Set up database backup strategy
- [ ] Configure monitoring and error tracking
- [ ] Update iOS base URL to production endpoint

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/professor/login` | Professor login |
| POST | `/api/auth/student/register` | Student registration |
| POST | `/api/auth/student/login` | Student login |
| POST | `/api/auth/google/callback` | Google Sign-In callback |

### Sessions

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/sessions` | Create session |
| GET | `/api/sessions` | List professor's sessions |
| GET | `/api/sessions/{code}` | Get session by code |
| GET | `/api/sessions/{code}/status` | Get session status (for join flow) |
| POST | `/api/sessions/{code}/join` | Join a session as a student |
| DELETE | `/api/sessions/{code}` | Delete session |

### Decisions

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/sessions/{code}/decisions` | Submit team decisions |
| GET | `/api/sessions/{code}/decisions` | Get team's submitted decisions |

### Leaderboard

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/sessions/{code}/leaderboard` | Get session leaderboard |

### Dashboard

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dashboard/session/{code}` | Get session data for dashboard |
| GET | `/api/dashboard/teams/{code}` | Get teams data |
| GET | `/api/dashboard/announcements/{code}` | Get announcements |

### WebSocket

| Endpoint | Description |
|----------|-------------|
| `ws://{host}/ws/{session_code}` | Real-time session updates |

## Scoring System

Teams are scored on multiple metrics each round:

| Metric | Weight | Description |
|--------|--------|-------------|
| Revenue | 20% | Total revenue generated |
| Profit Margin | 20% | Profit as % of revenue |
| Market Share | 20% | % of total market captured |
| ROI | 20% | Return on invested capital |
| Investor Score | 20% | Composite investor confidence score |

Final ranking is the weighted sum of all metrics, normalized to 0-100.

## Known Limitations

- In-memory SQLite database (no PostgreSQL/production DB)
- No automated migration system
- JWT auth is custom (no Auth0/Clerk integration)
- iOS app requires manual IP configuration for local dev
- No CI/CD pipeline configured
- Professor dashboard HTML is rendered server-side (no separate web app)

## Roadmap

- [x] Phase 1: Core simulation engine
- [x] Phase 2: Professor session management
- [x] Phase 3: Student decision flow
- [x] Phase 4: Leaderboard and real-time updates
- [x] Phase 5: Firebase session sharing, Apple Auth
- [ ] Phase 6: PDF report generation
- [ ] Phase 7: Analytics dashboard
- [ ] Phase 8: Multi-language support
- [ ] Phase 9: Advanced AI strategies

## License

Proprietary — All rights reserved.
