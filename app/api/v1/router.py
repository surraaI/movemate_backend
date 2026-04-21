from fastapi import APIRouter

from app.api.v1.endpoints import auth, health, operations, users, notification

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(operations.router, prefix="/operations", tags=["operations"])
api_router.include_router(notification.router, prefix="/notifications", tags=["Notifications"])

