# Database Migrations

This directory contains versioned Alembic migrations for the Practenture database.

## Usage

### Create a new migration
```bash
cd backend
.venv/bin/alembic revision -m "description of changes"
```

### Apply migrations
```bash
.venv/bin/alembic upgrade head
```

### Downgrade migrations
```bash
.venv/bin/alembic downgrade -1
```

### Check migration status
```bash
.venv/bin/alembic current
```

## Migration Naming Convention

Migrations are named with a 3-digit prefix followed by a description:
- `001_initial_schema.py`
- `002_owner_admin_baseline.py`
- `003_user_account_status.py`

## Environment

Migrations use the `DATABASE_URL` environment variable. For testing, set:
```bash
export DATABASE_URL=sqlite+aiosqlite:///:memory:
```

For production/staging, use the appropriate database URL.
