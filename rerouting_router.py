from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from rerouting_module import ReroutingPipeline

router = APIRouter()


def get_rerouting_pipeline(request: Request) -> ReroutingPipeline:
    """Resolve the app-scoped rerouting pipeline."""

    pipeline = getattr(request.app.state, "rerouting_pipeline", None)
    if pipeline is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Rerouting pipeline is not ready")
    return pipeline


DbSession = Annotated[Session, Depends(get_db)]
ReroutingPipelineDep = Annotated[ReroutingPipeline, Depends(get_rerouting_pipeline)]
AdminUserDep = Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN))]
DriverUserDep = Annotated[User, Depends(require_roles(UserRole.DRIVER))]
PrivilegedDriverUserDep = Annotated[User, Depends(require_roles(UserRole.DRIVER, UserRole.ADMIN, UserRole.SUPERADMIN))]
AnySignedInUserDep = Annotated[User, Depends(require_roles(UserRole.COMMUTER, UserRole.DRIVER, UserRole.ADMIN, UserRole.SUPERADMIN))]


class RouteDetailsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    route_code: str
    route_name: str
    distance_km: float | None = None
    price: str


class RouteAssignmentRequest(BaseModel):
    bus_id: str
    route_id: str
    driver_id: str
    scheduled_start: datetime


class RouteAssignmentResponse(BaseModel):
    assignment_id: str
    route: RouteDetailsOut


class ModelStatusResponse(BaseModel):
    phase: int
    model_version: str | None
    accuracy: float | None
    rows_collected: int
    rows_needed_for_next_phase: int
    last_retrain_timestamp: str | None


class ManualRetrainResponse(BaseModel):
    job_id: str
    status: str
    rows_used: int | None = None
    accuracy_before: float | None = None
    accuracy_after: float | None = None
    promoted: bool | None = None
    model_version: str | None = None
    feature_importances: dict[str, float] | None = None


class TripStartRequest(BaseModel):
    bus_id: str
    driver_id: str
    assignment_id: str


class TripStartResponse(BaseModel):
    trip_id: str
    assigned_route_polyline: list[list[float]]


class TripGPSUpdateRequest(BaseModel):
    latitude: float
    longitude: float
    speed: float
    passenger_count: int
    stop_id: str | None = None


class TripGPSUpdateResponse(BaseModel):
    reroute_suggested: bool
    reroute_id: str | None = None
    new_route: list[list[float]] | None = None


class TripEndRequest(BaseModel):
    final_latitude: float
    final_longitude: float


class TripSummaryResponse(BaseModel):
    trip_id: str
    total_time_seconds: float
    total_distance_km: float
    avg_speed_kph: float
    stops_served: int
    final_latitude: float
    final_longitude: float


class RerouteFeedbackRequest(BaseModel):
    accepted: bool


class RerouteFeedbackResponse(BaseModel):
    acknowledged: bool


class RerouteOutcomeRequest(BaseModel):
    actual_time_saving: float


class RerouteOutcomeResponse(BaseModel):
    recorded: bool


class StopDemandWindow(BaseModel):
    time_window: str
    predicted_demand: float


class StopDemandResponse(BaseModel):
    stop_id: str
    predicted_demand_windows: list[StopDemandWindow]
    current_congestion_score: float
    estimated_wait_time_minutes: int


class TripLogOut(BaseModel):
    id: str
    trip_id: str
    bus_id: str
    route_id: str
    driver_id: str
    timestamp: datetime
    day_of_week: int
    time_range: str
    month: int
    latitude: float
    longitude: float
    speed: float | None = None
    mileage_covered: float
    passenger_count: int
    stop_id: str | None = None
    total_time_seconds: float
    congestion_score: float
    high_demand_segment: int


class RouteTripLogsResponse(BaseModel):
    items: list[TripLogOut]
    page: int
    page_size: int
    total: int


@router.post("/assign-route", response_model=RouteAssignmentResponse, status_code=status.HTTP_201_CREATED)
def assign_route(
    payload: RouteAssignmentRequest,
    db: DbSession,
    pipeline: ReroutingPipelineDep,
    _current_user: AdminUserDep,
) -> RouteAssignmentResponse:
    """Assign a fixed route to a bus before the trip starts."""

    return RouteAssignmentResponse(**pipeline.assign_route(db, payload.bus_id, payload.route_id, payload.driver_id, payload.scheduled_start))


@router.get("/routes/{route_id}/logs", response_model=RouteTripLogsResponse)
def list_route_logs(
    route_id: str,
    db: DbSession,
    pipeline: ReroutingPipelineDep,
    _current_user: AdminUserDep,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = 1,
    page_size: int = 50,
) -> RouteTripLogsResponse:
    """Return paginated trip logs for a route."""

    result = pipeline.list_route_logs(db, route_id, date_from, date_to, page, page_size)
    return RouteTripLogsResponse(**result)


@router.get("/model/status", response_model=ModelStatusResponse)
def model_status(
    db: DbSession,
    pipeline: ReroutingPipelineDep,
    _current_user: AdminUserDep,
) -> ModelStatusResponse:
    """Return the current rerouting phase and model lifecycle status."""

    return ModelStatusResponse(**pipeline.model_status(db))


@router.post("/model/retrain", response_model=ManualRetrainResponse)
def manual_retrain(
    db: DbSession,
    pipeline: ReroutingPipelineDep,
    _current_user: AdminUserDep,
) -> ManualRetrainResponse:
    """Trigger a manual rerun of the nightly retraining workflow."""

    return ManualRetrainResponse(**pipeline.manual_retrain())


# The driver-facing trip start lifecycle lives under the GPS tracking API.
# Rerouting reads the driver's active trip (created by GPS tracking) and should
# not expose a separate `trips/start` endpoint to avoid duplicate lifecycles.


@router.post("/trips/{trip_id}/gps", response_model=TripGPSUpdateResponse)
def submit_gps_update(
    trip_id: str,
    payload: TripGPSUpdateRequest,
    db: DbSession,
    pipeline: ReroutingPipelineDep,
    current_user: DriverUserDep,
) -> TripGPSUpdateResponse:
    """Log a GPS update, score the segment, and maybe suggest a reroute."""

    result = pipeline.log_gps_update(
        db,
        trip_id=trip_id,
        driver_id=current_user.user_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        speed=payload.speed,
        passenger_count=payload.passenger_count,
        stop_id=payload.stop_id,
    )
    return TripGPSUpdateResponse(**result)


@router.post("/trips/{trip_id}/end", response_model=TripSummaryResponse)
def end_trip(
    trip_id: str,
    payload: TripEndRequest,
    db: DbSession,
    pipeline: ReroutingPipelineDep,
    _current_user: PrivilegedDriverUserDep,
) -> TripSummaryResponse:
    """Close the trip and compute summary metrics."""

    return TripSummaryResponse(**pipeline.end_trip(db, trip_id, payload.final_latitude, payload.final_longitude))


@router.post("/reroutes/{reroute_id}/feedback", response_model=RerouteFeedbackResponse)
def reroute_feedback(
    reroute_id: str,
    payload: RerouteFeedbackRequest,
    db: DbSession,
    pipeline: ReroutingPipelineDep,
    _current_user: DriverUserDep,
) -> RerouteFeedbackResponse:
    """Record whether the driver accepted the reroute suggestion."""

    return RerouteFeedbackResponse(**pipeline.record_feedback(db, reroute_id, payload.accepted))


@router.post("/reroutes/{reroute_id}/outcome", response_model=RerouteOutcomeResponse)
def reroute_outcome(
    reroute_id: str,
    payload: RerouteOutcomeRequest,
    db: DbSession,
    pipeline: ReroutingPipelineDep,
    _current_user: DriverUserDep,
) -> RerouteOutcomeResponse:
    """Record the real outcome for an accepted reroute at trip end."""

    return RerouteOutcomeResponse(**pipeline.record_outcome(db, reroute_id, payload.actual_time_saving))


@router.get("/stops/{stop_id}/demand", response_model=StopDemandResponse)
def stop_demand(
    stop_id: str,
    db: DbSession,
    pipeline: ReroutingPipelineDep,
    _current_user: AnySignedInUserDep,
) -> StopDemandResponse:
    """Return short-horizon demand and congestion estimates for a stop."""

    return StopDemandResponse(**pipeline.stop_demand(db, stop_id))
