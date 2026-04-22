from fastapi import APIRouter

from app.api.v1.endpoints import auth, health, notification, operations, route_stops, routes, stops, users

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(operations.router, prefix="/operations", tags=["operations"])
api_router.include_router(notification.router, prefix="/notifications", tags=["Notifications"])
api_router.include_router(stops.router, prefix="/stops", tags=["stops"])
api_router.include_router(routes.router, prefix="/routes", tags=["routes"])
api_router.include_router(route_stops.router, prefix="/routes", tags=["route-stops"])
