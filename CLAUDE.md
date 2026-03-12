# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Run
```bash
uvicorn app.main:app --reload
```

### Database Migrations
```bash
# Apply migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"

# Rollback one migration
alembic downgrade -1
```

### Tests
```bash
pytest
pytest tests/test_specific_file.py::test_function  # single test
pytest -v  # verbose
```

### Seed demo data
```bash
python3 scripts/seed_demo_data.py
```

## Architecture

### Stack
- **FastAPI** backend with **SQLAlchemy 2.0** ORM and **Alembic** migrations
- **PostgreSQL** (Neon cloud) as the database
- **JWT** authentication via `python-jose`, passwords hashed with `bcrypt`/`passlib`
- CORS configured for `https://appointment-app-eosin.vercel.app` and `http://localhost:3000`

### Layer Pattern
```
models/ (SQLAlchemy ORM)
  → schemas/ (Pydantic validation)
    → crud/ (DB operations)
      → api/v1/endpoints/ (FastAPI routers)
```

All endpoints live under `/api/v1`. Routers are registered in `app/main.py`. Dependency injection (DB session, current user) lives in `app/api/deps.py`.

### Roles & Auth
Two roles: `CLIENT` and `PROVIDER`. JWT bearer tokens. Role checks are enforced in endpoint logic — clients can only manage their own appointments; providers manage schedules and transition appointment status.

### Appointment State Machine
```
PENDING → CONFIRMED (provider only)
PENDING → CANCELLED (either party)
CONFIRMED → COMPLETED (provider only)
CONFIRMED → CANCELLED (either party)
```
CANCELLED and COMPLETED are terminal.

### Key Business Rules
- Appointments cannot be booked in the past
- Duration: 15–480 minutes
- No overlapping appointments per provider (enforced in `crud_appointment.py`)
- Availability is slot-based (default 30-min slots, 9 AM–5 PM)
- Clients can only modify PENDING appointments

### Environment Variables
Configure in `.env`:
```
SECRET_KEY=
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
DATABASE_URL=postgresql://...
ALLOWED_ORIGINS=["https://...", "http://localhost:3000"]
```
