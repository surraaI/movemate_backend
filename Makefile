PYTHON ?= python3
PIP ?= $(PYTHON) -m pip
UVICORN ?= uvicorn
ALEMBIC ?= alembic
HOST ?= 0.0.0.0
PORT ?= 8000

.PHONY: help install run dev migrate revision downgrade current history seed-superadmin

help:
	@echo "Available commands:"
	@echo "  make install                        Install Python dependencies"
	@echo "  make run                            Run FastAPI app with reload"
	@echo "  make dev                            Alias for run"
	@echo "  make migrate                        Apply all Alembic migrations"
	@echo "  make revision msg='desc'            Create autogenerate migration"
	@echo "  make downgrade rev='-1'             Rollback to target revision"
	@echo "  make current                        Show current Alembic revision"
	@echo "  make history                        Show Alembic migration history"
	@echo "  make seed-superadmin                Seed SUPERADMIN from .env"

install:
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

run:
	$(UVICORN) app.main:app --host $(HOST) --port $(PORT) --reload

dev: run

migrate:
	$(ALEMBIC) upgrade head

revision:
	@if [ -z "$(msg)" ]; then echo "Usage: make revision msg='your migration message'"; exit 1; fi
	$(ALEMBIC) revision --autogenerate -m "$(msg)"

downgrade:
	$(ALEMBIC) downgrade $(if $(rev),$(rev),-1)

current:
	$(ALEMBIC) current

history:
	$(ALEMBIC) history

seed-superadmin:
	$(PYTHON) -c "from app.db.session import SessionLocal; from app.db.seed import seed_superadmin; db=SessionLocal(); user=seed_superadmin(db); print(user.email if user else 'SUPERADMIN_EMAIL/SUPERADMIN_PASSWORD not set'); db.close()"
