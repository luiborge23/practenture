# Practenture Backend Setup

## Prerequisites

- Python 3.9 (system `python3` at `/usr/bin/python3`)
- pip (installed via `ensurepip` if missing)

## Quick Start

```bash
cd /Users/luisborges/2026/Practenture-ios/Practenture/backend

# Create virtual environment (one-time)
/usr/bin/python3 -m venv venv
source venv/bin/activate

# Install dependencies (one-time)
pip install -r requirements.txt

# Run backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PYTHONPATH` | Must be unset to avoid venv contamination | (unset) |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/sessions` | Create session |
| PUT | `/api/sessions/{code}/join` | Join session |
| POST | `/api/decisions` | Submit decision |

## Testing

```bash
# Run all tests
pytest test_backend.py test_phase5.py -v
```

## Troubleshooting

### "No module named pydantic_core"
- Ensure Python 3.9 is used: `/usr/bin/python3 -m venv venv`
- Reinstall dependencies: `pip install -r requirements.txt`

### "Address already in use"
- Kill existing process: `lsof -ti:8000 | xargs kill`
