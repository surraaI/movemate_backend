from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
import app.models  # noqa: F401

from app.db.base import Base
from app.db.session import engine
from app.workers.scheduler import start_scheduler
from app.db.session import SessionLocal
from app.db.seed import seed_superadmin
from app.services.eta_model_loader import ensure_eta_model_downloaded


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    ensure_eta_model_downloaded()

    db = SessionLocal()
    try:
        seed_superadmin(db)
    finally:
        db.close()

    start_scheduler()

    yield
    # Shutdown (optional cleanup here)

    # Shutdown logic (optional)
    print("Application shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        lifespan=lifespan,
    )
    
    origins = [
        "http://localhost:54028",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,   # or ["*"] for all
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()