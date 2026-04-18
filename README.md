# MoveMate Backend (FastAPI)

Production-ready backend for **MoveMate: AI-Powered Public Bus Tracking and Arrival Time Prediction System**.

## Step 1 (in progress): Project setup

### Python

This repo targets **Python 3.12** (you have `Python 3.12.7` installed).

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

### App layout

The backend code lives under `app/`:

```text
app/
  api/          # HTTP layer (routers, dependencies)
  core/         # configuration, security, logging
  db/           # DB engine/session + migrations glue
  models/       # SQLAlchemy ORM models
  schemas/      # Pydantic v2 models (request/response)
  services/     # business logic (use-cases)
```

## Database and Alembic setup

1. Create `.env` from the example and set a real remote Postgres URL:

```bash
cp .env.example .env
```

Use this format for `DATABASE_URL`:

```bash
DATABASE_URL="postgresql+psycopg://<USER>:<PASSWORD>@<HOST>:<PORT>/<DB_NAME>?sslmode=require"
```

2. Install dependencies (includes Alembic + psycopg driver):

```bash
pip install -r requirements.txt
```

3. Run migrations:

```bash
alembic upgrade head
```

4. (Optional) create a new migration after model changes:

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```
