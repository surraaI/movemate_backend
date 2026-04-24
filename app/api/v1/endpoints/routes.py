from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.route import RouteCreate, RouteDetailOut, RouteOut, RouteStatusUpdate, RouteUpdate
from app.schemas.route_stop import RouteStopOut
from app.services.route_service import RouteService

router = APIRouter()


def _to_route_detail(route) -> RouteDetailOut:
    stops = [
        RouteStopOut(
            stop_id=item.stop.id,
            stop_name=item.stop.name,
            latitude=item.stop.latitude,
            longitude=item.stop.longitude,
            sequence=item.sequence,
            created_at=item.created_at,
        )
        for item in route.route_stops
    ]
    return RouteDetailOut(
        id=route.id,
        route_code=route.route_code,
        route_name=route.route_name,
        status=route.status,
        is_deleted=route.is_deleted,
        created_at=route.created_at,
        updated_at=route.updated_at,
        stops=stops,
    )


@router.post("", response_model=RouteOut, status_code=status.HTTP_201_CREATED)
def create_route(
    payload: RouteCreate,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
) -> RouteOut:
    return RouteOut.model_validate(RouteService(db).create_route(payload))


@router.get("", response_model=list[RouteDetailOut])
def list_routes(
    db: Annotated[Session, Depends(get_db)],
) -> list[RouteDetailOut]:
    routes = RouteService(db).list_routes()
    return [_to_route_detail(route) for route in routes]


@router.get("/{route_id}", response_model=RouteDetailOut)
def get_route(
    route_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> RouteDetailOut:
    return _to_route_detail(RouteService(db).get_route(route_id))


@router.patch("/{route_id}", response_model=RouteOut)
def update_route(
    route_id: str,
    payload: RouteUpdate,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
) -> RouteOut:
    return RouteOut.model_validate(RouteService(db).update_route(route_id, payload))


@router.delete("/{route_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_route(
    route_id: str,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
) -> Response:
    RouteService(db).soft_delete_route(route_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{route_id}/status", response_model=RouteOut)
def update_route_status(
    route_id: str,
    payload: RouteStatusUpdate,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
) -> RouteOut:
    return RouteOut.model_validate(RouteService(db).update_status(route_id, payload))
