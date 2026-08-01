# Practenture Backend

FastAPI backend for Practenture real-time business simulation platform.

## Setup

```bash
cd backend
pip install -r requirements.txt
```

## Run

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## API Endpoints

### Health Check
- `GET /api/health` — Health check

### Sessions
- `POST /api/sessions` — Create a new session. Returns `{sessionId, code}`.
- `GET /api/sessions/{code}` — Get session by 8-char code (public access).
- `PUT /api/sessions/{code}/join` — Student joins with `{teamName, studentId}`.
- `GET /api/sessions/{code}/teams` — List all teams in session.
- `POST /api/sessions/{code}/start` — Professor starts the session.
- `GET /api/sessions/{code}/status` — Quick status (round, state, submissions).
- `POST /api/sessions/{code}/end` — Manually end session.

### Decisions
- `POST /api/sessions/{code}/submit_decision` — Submit team decision for current round.
- `GET /api/sessions/{code}/decisions/{round}` — Get all decisions for a round.
- `POST /api/sessions/{code}/process_round` — Professor triggers round processing.

### Results
- `GET /api/sessions/{code}/results` — Get all round results.

### Leaderboard
- `GET /api/sessions/{code}/leaderboard` — Sorted by investor score.

### Announcements
- `POST /api/sessions/{code}/announcements` — Professor sends announcement.
- `GET /api/sessions/{code}/announcements` — Get all session announcements.

### Advance
- `POST /api/sessions/{code}/advance` — Process current + auto-advance to next.

## Architecture

```
backend/
├── main.py                # FastAPI app, CORS, error handling
├── models.py              # Pydantic models (mirrors iOS)
├── database.py            # In-memory store (dict-based)
├── simulation_engine.py   # Pure Python simulation engine
├── routers/               # API route modules
│   ├── sessions.py        # Session CRUD
│   ├── decisions.py       # Decision submission + round processing
│   ├── announcements.py   # Announcements
│   └── leaderboard.py     # Leaderboard
├── requirements.txt
└── test_backend.py        # pytest tests
```

## Configuration

- **CORS**: All origins allowed in dev. Configure via environment in production.
- **Session codes**: Auto-generated 8-char format (`BIZ-XXXXXX`).
- **Database**: In-memory dict store. Swap `database.py` for Redis backend later.
- **AUTH**: Currently open (classroom tool). JWT support in `requirements.txt` ready.

## Tests

```bash
python3.11 -m venv .venv
.venv/bin/python -m ensurepip --upgrade
.venv/bin/python -m pip install -r requirements-dev.txt
../scripts/test_backend.sh
```

The wrapper removes inherited `PYTHONPATH` entries before invoking the project
interpreter and treats every Python warning category as a test failure.

## iOS Integration

Set `BACKEND_URL` in iOS app to `http://<host>:8000`.

The API uses simple JSON — no auth needed for classroom use.
Session codes are 8-character strings students use to join sessions.
