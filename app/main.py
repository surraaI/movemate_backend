from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import settings
import app.models  # noqa: F401 — register ORM mappers for create_all
from app.db.base import Base
from app.db.session import engine
from app.workers.scheduler import start_scheduler


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield

@app.on_event("startup")
def startup_event():
    start_scheduler()

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        lifespan=lifespan,
    )
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()

