from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.route_service import RouteService
from app.schemas.route import RouteCreate, RouteUpdate, RouteStatusUpdate, RouteOut
from app.models.user import User
from app.schemas.route import RouteCreate, RouteDetailOut, RouteOut, RouteStatusUpdate, RouteUpdate
from app.schemas.route_stop import RouteStopOut
from app.services.route_service import RouteService
from app.core.deps import require_roles
from app.models.enums import UserRole
from app.services.route_service import RouteService, route_to_detail_out

router = APIRouter(prefix="/routes", tags=["Routes"])


@router.post("", response_model=RouteOut, status_code=status.HTTP_201_CREATED)
def create_route(
    payload: RouteCreate,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN))],
) -> RouteOut:
    return RouteOut.model_validate(RouteService(db).create_route(payload))


@router.get("", response_model=list[RouteDetailOut])
def list_routes(
    db: Annotated[Session, Depends(get_db)],
) -> list[RouteDetailOut]:
    routes = RouteService(db).list_routes()
    return [route_to_detail_out(route) for route in routes]


@router.get("/{route_id}", response_model=RouteDetailOut)
def get_route(
    route_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> RouteDetailOut:
    return route_to_detail_out(RouteService(db).get_route(route_id))


# -------------------------
# UPDATE
# -------------------------
@router.patch("/{route_code}", response_model=RouteOut)
def update_route(
    route_code: str,
    payload: RouteUpdate,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN))],
) -> RouteOut:
    return RouteOut.model_validate(RouteService(db).update_route(route_code, payload))


@router.delete("/{route_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_route(
    route_id: str,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN))],
) -> Response:
    RouteService(db).soft_delete_route(route_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{route_id}/status", response_model=RouteOut)
def update_route_status(
    route_id: str,
    payload: RouteStatusUpdate,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN))],
) -> RouteOut:
    return RouteOut.model_validate(RouteService(db).update_status(route_id, payload))
