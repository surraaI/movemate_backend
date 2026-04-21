# MoveMate Backend (FastAPI)

Backend service for **MoveMate: AI-powered public bus tracking and ETA prediction**.

## Quick Start

### 1) Python and virtual environment

This repo targets **Python 3.12** (`Python 3.12.7` recommended).

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2) Environment configuration

Create your local environment file:

```bash
cp .env.example .env
```

Set `DATABASE_URL` in `.env` with this format:

```bash
DATABASE_URL="postgresql+psycopg://<USER>:<PASSWORD>@<HOST>:<PORT>/<DB_NAME>?sslmode=require"
```

### 3) Run database migrations

```bash
alembic upgrade head
```

### 4) Start the API server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Docs:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Project Structure

```text
app/
  api/            # HTTP routers and dependencies
  core/           # app config and security helpers
  db/             # SQLAlchemy base, engine, sessions
  models/         # ORM entities
  repositories/   # data access layer
  schemas/        # Pydantic request/response models
  services/       # business logic layer
```

## Routing Foundation (Relational Graph Design)

The routing module is implemented with a graph-inspired relational design:

- `Stop` = node (`name`, `latitude`, `longitude`)
- `Route` = route metadata (`route_code`, `route_name`, `status`, `is_deleted`)
- `RouteStop` = ordered edge list (`route_id`, `stop_id`, `sequence`)

Key guarantees:
- stop name uniqueness
- route code uniqueness
- unique stop sequence per route
- no duplicate stop in same route
- sequence shifting on insert/remove
- minimum stop count enforcement for route integrity

## Main API Groups

- `auth` and `users` for authentication and profile operations
- `notifications` for user notifications
- `stops` for stop creation and lookup
- `routes` for route lifecycle (create/list/detail/update/status/soft-delete)
- `routes/{route_id}/stops` for ordered stop management (add/reorder/remove/list)

## Migration Workflow

After model changes:

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```
