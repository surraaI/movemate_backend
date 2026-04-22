from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.route_stop import RouteStopAddRequest, RouteStopOut, RouteStopReorderRequest
from app.services.route_stop_service import RouteStopService

router = APIRouter()


def _to_out(route_stop) -> RouteStopOut:
    return RouteStopOut(
        stop_id=route_stop.stop.id,
        stop_name=route_stop.stop.name,
        latitude=route_stop.stop.latitude,
        longitude=route_stop.stop.longitude,
        sequence=route_stop.sequence,
        created_at=route_stop.created_at,
    )


@router.post("/{route_id}/stops", response_model=list[RouteStopOut], status_code=status.HTTP_201_CREATED)
def add_route_stop(
    route_id: str,
    payload: RouteStopAddRequest,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
) -> list[RouteStopOut]:
    items = RouteStopService(db).add_stop(route_id, payload)
    return [_to_out(item) for item in items]


@router.patch("/{route_id}/stops/reorder", response_model=list[RouteStopOut])
def reorder_route_stops(
    route_id: str,
    payload: RouteStopReorderRequest,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
) -> list[RouteStopOut]:
    items = RouteStopService(db).reorder_stops(route_id, payload)
    return [_to_out(item) for item in items]


@router.delete("/{route_id}/stops/{stop_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_route_stop(
    route_id: str,
    stop_id: str,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
) -> Response:
    RouteStopService(db).remove_stop(route_id, stop_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{route_id}/stops", response_model=list[RouteStopOut])
def list_route_stops(
    route_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> list[RouteStopOut]:
    items = RouteStopService(db).list_route_stops(route_id)
    return [_to_out(item) for item in items]
