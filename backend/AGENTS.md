# BizSimAI Backend — AGENTS.md

## Project Overview
BizSimAI backend is a FastAPI + SQLite application for running a business simulation with real-time updates.

## Architecture
- **Framework:** FastAPI (async)
- **Database:** SQLite via SQLAlchemy (async)
- **Auth:** JWT (HS256, 24h expiry)
- **Real-time:** WebSockets (ws_manager.py)
- **Simulation Engine:** Server-side deterministic engine (simulation_engine.py)

## Key Files
```
backend/
  main.py                  — App entry point, CORS, lifespan
  models.py                — SQLAlchemy models
  database.py              — Engine, session, Base, seed data
  auth.py                  — JWT auth core + auth models
  ws_manager.py            — WebSocket connection manager
  simulation_engine.py     — Deterministic simulation engine
  requirements.txt         — Dependencies
  test_backend.py          — Original tests (18 tests)
  test_phase5.py           — Phase 5 tests (13 tests)
  routers/
    auth.py                — Auth endpoints
    websocket.py           — WebSocket endpoint
    sessions.py            — Session CRUD + start/end
    decisions.py           — Decision submission + round processing
    leaderboard.py         — Leaderboard endpoint
    announcements.py       — Announcements CRUD
```

## API Endpoints

### Auth
| Method | Path | Auth Required | Description |
|--------|------|---------------|-------------|
| POST | /api/auth/login | No | Login (password/apple/google) |
| POST | /api/auth/register | No | Student registration |
| POST | /api/auth/verify | JWT | Verify token |
| POST | /api/auth/professor-only | JWT + Professor | Professor check |
| POST | /api/auth/student-or-professor | JWT + Student/Prof | Student/professor check |

### Sessions
| Method | Path | Auth Required | Description |
|--------|------|---------------|-------------|
| POST | /api/sessions | Professor | Create session |
| GET | /api/sessions | None | List sessions |
| GET | /api/sessions/{code} | None | Get session details |
| POST | /api/sessions/{code}/join | None | Join session as team |
| POST | /api/sessions/{code}/start | Professor | Start session |
| POST | /api/sessions/{code}/end | Professor | End session + get results |
| GET | /api/sessions/{code}/status | None | Session status |
| GET | /api/sessions/{code}/teams | None | Get teams |

### Decisions
| Method | Path | Auth Required | Description |
|--------|------|---------------|-------------|
| POST | /api/sessions/{code}/decisions | Student/Prof | Submit decision |
| GET | /api/sessions/{code}/decisions/{round}/{teamId} | None | Get decisions |
| POST | /api/sessions/{code}/process-round | Professor | Process round |

### Leaderboard
| Method | Path | Auth Required | Description |
|--------|------|---------------|-------------|
| GET | /api/sessions/{code}/leaderboard | None | Get leaderboard |

### Announcements
| Method | Path | Auth Required | Description |
|--------|------|---------------|-------------|
| POST | /api/sessions/{code}/announcements | Professor | Create announcement |
| GET | /api/sessions/{code}/announcements | None | Get announcements |

### WebSocket
| Path | Auth Required | Description |
|------|---------------|-------------|
| ws://host/ws/{code}?token=JWT | JWT | Real-time session updates |

## Running Tests
```bash
python -m pytest test_backend.py test_phase5.py -v
```
All 31 tests should pass.

## Running the Server
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## Environment Variables
- `SECRET_KEY` — JWT signing key (auto-generated if not set)
- `DATABASE_URL` — SQLite path (default: data.db)
- `PROFESSOR_USERNAME` — Default professor username (default: professor)
- `PROFESSOR_PASSWORD` — Default professor password (default: bizsimai2026)

## iOS Integration Notes
- All API endpoints use `/api/` prefix
- Auth tokens passed via `Authorization: Bearer <token>` header
- WebSocket connections use query param `?token=<jwt>`
- Session codes are 10 chars: `BIZ-XXXXXX` format
- All responses are JSON
