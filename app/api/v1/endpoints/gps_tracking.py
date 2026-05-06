from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.gps_tracking import (
    AdminFleetOut,
    BusLiveLocationOut,
    ETAPredictionOut,
    GPSUpdateRequest,
    GPSUpdateResponse,
    RouteFleetOut,
    TripEndRequest,
    TripOut,
    TripStartRequest,
)
from app.services.eta_service import ETAService
from app.services.gps_tracking_service import GPSTrackingService

router = APIRouter()


@router.post("/trips/start", response_model=TripOut, status_code=status.HTTP_201_CREATED)
def start_trip(
    payload: TripStartRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(UserRole.DRIVER))],
) -> TripOut:
    return GPSTrackingService(db).start_trip(current_user, payload)


@router.post("/trips/{trip_id}/end", response_model=TripOut)
def end_trip(
    trip_id: str,
    payload: TripEndRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(UserRole.DRIVER, UserRole.ADMIN))],
) -> TripOut:
    return GPSTrackingService(db).end_trip(current_user, trip_id, payload)


@router.post("/trips/{trip_id}/locations", response_model=GPSUpdateResponse)
def submit_gps_update(
    trip_id: str,
    payload: GPSUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(UserRole.DRIVER))],
) -> GPSUpdateResponse:
    return GPSTrackingService(db).submit_gps_update(current_user, trip_id, payload)


@router.get(
    "/trips/{trip_id}/locations/current",
    response_model=BusLiveLocationOut,
)
def get_bus_current_location(
    trip_id: str,
    db: Annotated[Session, Depends(get_db)],
    _current_user: Annotated[User, Depends(require_roles(UserRole.COMMUTER, UserRole.ADMIN, UserRole.DRIVER))],
) -> BusLiveLocationOut:
    return GPSTrackingService(db).get_bus_current_location(trip_id)


@router.get("/routes/{route_id}/active-buses", response_model=RouteFleetOut)
def get_active_buses_for_route(
    route_id: str,
    db: Annotated[Session, Depends(get_db)],
    _current_user: Annotated[User, Depends(require_roles(UserRole.COMMUTER, UserRole.ADMIN, UserRole.DRIVER))],
) -> RouteFleetOut:
    return GPSTrackingService(db).get_route_active_buses(route_id)


@router.get("/fleet/live", response_model=AdminFleetOut)
def get_live_fleet_data(
    db: Annotated[Session, Depends(get_db)],
    _current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
) -> AdminFleetOut:
    return GPSTrackingService(db).get_live_fleet()


@router.get("/trips/{trip_id}/eta", response_model=ETAPredictionOut)
def get_trip_eta(
    trip_id: str,
    db: Annotated[Session, Depends(get_db)],
    _current_user: Annotated[User, Depends(require_roles(UserRole.COMMUTER, UserRole.ADMIN, UserRole.DRIVER))],
    destination_stop_id: Annotated[str | None, Query(alias="destinationStopId")] = None,
) -> ETAPredictionOut:
    return ETAService(db).predict_trip_eta(trip_id, destination_stop_id)
