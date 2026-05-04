from __future__ import annotations

import logging
import math
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.enums import TripStatus, UserRole
from app.models.gps_tracking import ActiveTrip, BusCurrentLocation, BusLocationHistory
from app.models.user import User
from app.repositories.gps_tracking_repository import GPSTrackingRepository
from app.schemas.gps_tracking import (
    AdminFleetOut,
    BusLiveLocationOut,
    GPSUpdateRequest,
    GPSUpdateResponse,
    RouteFleetOut,
    TripEndRequest,
    TripOut,
    TripStartRequest,
)

logger = logging.getLogger(__name__)

MAX_STALE_GPS_AGE_SECONDS = 180
MAX_FUTURE_GPS_SKEW_SECONDS = 20
MAX_REALISTIC_SPEED_KPH = 130.0
MAX_LOCATION_JUMP_KM = 5.0


class GPSTrackingService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = GPSTrackingRepository(db)

    def start_trip(self, driver: User, payload: TripStartRequest) -> TripOut:
        if driver.driver_profile is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Driver profile required")

        route = self.repo.get_route(payload.route_id)
        if route is None or route.is_deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")

        existing_active = self.repo.get_active_trip_for_driver(driver.user_id)
        if existing_active is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Driver already has active trip")

        vehicle_id = (payload.vehicle_id or driver.driver_profile.assigned_vehicle_id or "").strip()
        if not vehicle_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vehicle ID is required for active tracking",
            )

        started_at = payload.started_at or datetime.now(UTC)
        trip = ActiveTrip(
            route_id=route.id,
            driver_id=driver.user_id,
            vehicle_id=vehicle_id,
            started_at=started_at,
            status=TripStatus.ACTIVE,
        )
        created = self.repo.create_trip(trip)
        self.db.commit()
        logger.info("Trip started", extra={"trip_id": created.trip_id, "driver_id": driver.user_id})
        return TripOut.model_validate(created)

    def end_trip(self, actor: User, trip_id: str, payload: TripEndRequest) -> TripOut:
        trip = self.repo.get_trip_by_id(trip_id)
        if trip is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found")
        if trip.status != TripStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Trip is already closed")
        if actor.role != UserRole.ADMIN and trip.driver_id != actor.user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to end this trip")

        ended_at = payload.ended_at or datetime.now(UTC)
        started_at = trip.started_at if trip.started_at.tzinfo is not None else trip.started_at.replace(tzinfo=UTC)
        if ended_at < started_at:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="endedAt cannot be before startedAt")

        trip.status = TripStatus.COMPLETED
        trip.ended_at = ended_at
        updated = self.repo.save_trip(trip)
        self.db.commit()
        logger.info("Trip ended", extra={"trip_id": updated.trip_id, "actor_id": actor.user_id})
        return TripOut.model_validate(updated)

    def submit_gps_update(self, driver: User, trip_id: str, payload: GPSUpdateRequest) -> GPSUpdateResponse:
        trip = self.repo.get_trip_by_id(trip_id)
        if trip is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found")
        if trip.driver_id != driver.user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Trip does not belong to driver")
        if trip.status != TripStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Trip is not active")
        if payload.latitude == 0 and payload.longitude == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Suspicious coordinates rejected")

        now = datetime.now(UTC)
        if payload.timestamp < now - timedelta(seconds=MAX_STALE_GPS_AGE_SECONDS):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Stale GPS update rejected")
        if payload.timestamp > now + timedelta(seconds=MAX_FUTURE_GPS_SKEW_SECONDS):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Future GPS timestamp rejected")

        current = self.repo.get_current_location_for_trip(trip_id)
        self._validate_against_previous(current, payload)

        history_row = BusLocationHistory(
            trip_id=trip.trip_id,
            route_id=trip.route_id,
            vehicle_id=trip.vehicle_id,
            latitude=payload.latitude,
            longitude=payload.longitude,
            speed_kph=payload.speed_kph,
            heading_degrees=payload.heading_degrees,
            gps_timestamp=payload.timestamp,
        )
        self.repo.add_history_location(history_row)

        current_row = BusCurrentLocation(
            trip_id=trip.trip_id,
            route_id=trip.route_id,
            vehicle_id=trip.vehicle_id,
            latitude=payload.latitude,
            longitude=payload.longitude,
            speed_kph=payload.speed_kph,
            heading_degrees=payload.heading_degrees,
            gps_timestamp=payload.timestamp,
        )
        updated_current = self.repo.upsert_current_location(current, current_row)
        self.db.commit()
        logger.debug(
            "GPS update stored",
            extra={"trip_id": trip_id, "driver_id": driver.user_id, "vehicle_id": trip.vehicle_id},
        )
        return GPSUpdateResponse(trip_id=trip_id, accepted=True, stored_at=updated_current.received_at)

    def get_bus_current_location(self, trip_id: str) -> BusLiveLocationOut:
        trip = self.repo.get_trip_by_id(trip_id)
        if trip is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found")
        current = self.repo.get_current_location_for_trip(trip_id)
        if current is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No GPS updates yet")
        return self._to_live_location(current)

    def get_route_active_buses(self, route_id: str) -> RouteFleetOut:
        route = self.repo.get_route(route_id)
        if route is None or route.is_deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")
        live = [self._to_live_location(item) for item in self.repo.list_active_buses_for_route(route_id)]
        return RouteFleetOut(route_id=route_id, active_buses=live)

    def get_live_fleet(self) -> AdminFleetOut:
        live = [self._to_live_location(item) for item in self.repo.list_live_fleet()]
        return AdminFleetOut(total_active_trips=len(live), buses=live)

    def _validate_against_previous(
        self, current: BusCurrentLocation | None, payload: GPSUpdateRequest
    ) -> None:
        if current is None:
            return
        if (
            abs(current.latitude - payload.latitude) < 1e-6
            and abs(current.longitude - payload.longitude) < 1e-6
            and current.gps_timestamp == payload.timestamp
        ):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Duplicate GPS update")

        previous_ts = current.gps_timestamp
        if previous_ts.tzinfo is None:
            previous_ts = previous_ts.replace(tzinfo=UTC)
        if payload.timestamp <= previous_ts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Out-of-order GPS timestamp rejected",
            )

        distance_km = self._haversine_km(
            current.latitude,
            current.longitude,
            payload.latitude,
            payload.longitude,
        )
        delta_hours = (payload.timestamp - previous_ts).total_seconds() / 3600
        if delta_hours <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid GPS timestamp delta")

        implied_speed_kph = distance_km / delta_hours
        if implied_speed_kph > MAX_REALISTIC_SPEED_KPH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unrealistic speed detected in GPS update",
            )
        if distance_km > MAX_LOCATION_JUMP_KM and delta_hours < (3 / 60):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Suspicious GPS jump rejected",
            )

    def _to_live_location(self, current: BusCurrentLocation) -> BusLiveLocationOut:
        return BusLiveLocationOut(
            trip_id=current.trip_id,
            route_id=current.route_id,
            vehicle_id=current.vehicle_id,
            latitude=current.latitude,
            longitude=current.longitude,
            speed_kph=current.speed_kph,
            heading_degrees=current.heading_degrees,
            gps_timestamp=current.gps_timestamp,
            received_at=current.received_at,
        )

    @staticmethod
    def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        radius_km = 6371.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        a = (
            math.sin(delta_phi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return radius_km * c
