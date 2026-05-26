from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.payments import router as chapa_payments_router
from app.api.v1.router import api_router
from app.core.config import settings
import app.models  # noqa: F401

from app.db.base import Base
from app.db.session import engine
from app.workers.scheduler import start_scheduler
from app.db.session import SessionLocal
from app.db.seed import seed_superadmin
from rerouting_module import ReroutingPipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    Base.metadata.create_all(bind=engine)
    app.state.rerouting_pipeline = ReroutingPipeline()
    app.state.rerouting_pipeline.ensure_tables(engine)

    db = SessionLocal()
    try:
        seed_superadmin(db)
    finally:
        db.close()

    app.state.rerouting_pipeline.start_background_jobs()
    start_scheduler()

    yield
    # Shutdown (optional cleanup here)

    # Shutdown logic (optional)
    pipeline = getattr(app.state, "rerouting_pipeline", None)
    if pipeline is not None:
        pipeline.shutdown()
    print("Application shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        lifespan=lifespan,
    )
    
    origins = [
        "http://localhost:54028",
        "http://127.0.0.1:5173",
        "https://admin-one-blue.vercel.app",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,   # or ["*"] for all
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api/v1")
    app.include_router(chapa_payments_router)

    return app


app = create_app()