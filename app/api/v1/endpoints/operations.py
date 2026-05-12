"""Example routes demonstrating role-based access control."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.route import RouteDetailOut
from app.schemas.user import UserOut
from app.services import user_service
from app.services.admin_service import AdminService
from app.services.route_service import RouteService, route_to_detail_out

router = APIRouter()


@router.post("/driver/gps-updates")
def post_gps_update(
    payload: dict[str, Any],
    _user: Annotated[User, Depends(require_roles(UserRole.DRIVER))],
) -> dict[str, str]:
    """Only DRIVER can submit live GPS updates (vehicle location)."""
    return {"status": "accepted"}


@router.get("/admin/users", response_model=list[UserOut])
def admin_list_users(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN))],
) -> list[UserOut]:
    """Admin dashboard: list all users with profiles (same payload shape as `/users/me`)."""
    users = AdminService.list_users_for_admin(db)
    return [user_service.user_to_out(u) for u in users]


@router.get("/admin/routes", response_model=list[RouteDetailOut])
def admin_list_routes(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN))],
) -> list[RouteDetailOut]:
    """Admin dashboard: list routes with stops (aligned with `GET /api/v1/routes`)."""
    routes = RouteService(db).list_routes()
    return [route_to_detail_out(r) for r in routes]


@router.get("/commuter/buses/track")
def commuter_track_buses(
    _user: Annotated[User, Depends(require_roles(UserRole.COMMUTER))],
) -> dict[str, str]:
    """COMMUTER role: track buses (placeholder)."""
    return {"status": "tracking"}


@router.post("/commuter/tickets/purchase")
def commuter_purchase_ticket(
    _user: Annotated[User, Depends(require_roles(UserRole.COMMUTER))],
) -> dict[str, str]:
    """COMMUTER role: purchase tickets (placeholder)."""
    return {"status": "pending_payment"}
