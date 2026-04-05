"""Example routes demonstrating role-based access control."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.core.deps import require_roles
from app.models.enums import UserRole
from app.models.user import User

router = APIRouter()


@router.post("/driver/gps-updates")
def post_gps_update(
    payload: dict[str, Any],
    _user: Annotated[User, Depends(require_roles(UserRole.DRIVER))],
) -> dict[str, str]:
    """Only DRIVER can submit live GPS updates (vehicle location)."""
    return {"status": "accepted"}


@router.post("/admin/users")
def admin_list_users_stub(
    _user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
) -> dict[str, str]:
    """Only ADMIN can manage users (placeholder for future user admin APIs)."""
    return {"status": "ok"}


@router.post("/admin/routes")
def admin_manage_routes_stub(
    _user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
) -> dict[str, str]:
    """Only ADMIN can manage routes."""
    return {"status": "ok"}


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
