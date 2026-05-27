from __future__ import annotations

import logging
import math
import json
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.event import Event, EventType
from app.models.enums import TripStatus, UserRole
from app.models.gps_tracking import ActiveTrip, BusCurrentLocation, BusLocationHistory, CommuterTripLocation
from app.models.route_stop import RouteStop
from app.models.ticket import Ticket
from app.models.user import User
from app.repositories.gps_tracking_repository import GPSTrackingRepository
from app.schemas.gps_tracking import (
    AdminFleetOut,
    BusLiveLocationOut,
    BusOccupancyOut,
    CommuterLocationUpdateRequest,
    GPSUpdateRequest,
    GPSUpdateResponse,
    RouteFleetOut,
    RouteBusOccupancyOut,
    TripEndRequest,
    TripOut,
    TripStartRequest,
)
from app.models.enums import OccupancyLevel

logger = logging.getLogger(__name__)

MAX_STALE_GPS_AGE_SECONDS = 180
MAX_FUTURE_GPS_SKEW_SECONDS = 20
MAX_REALISTIC_SPEED_KPH = 130.0
MAX_LOCATION_JUMP_KM = 5.0
DEFAULT_BUS_CAPACITY = 50
HIGH_OCCUPANCY_THRESHOLD = 0.8
MEDIUM_OCCUPANCY_THRESHOLD = 0.5


class GPSTrackingService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = GPSTrackingRepository(db)

    def start_trip(self, driver: User, payload: TripStartRequest) -> TripOut:
        driver_record = driver
        if not hasattr(driver_record, "driver_profile") or driver_record.driver_profile is None:
            driver_record = self.db.get(User, driver.user_id)
        if driver_record is None or driver_record.driver_profile is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Driver profile required")

        route = self.repo.get_route(payload.route_id)
        if route is None or route.is_deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")

        existing_active = self.repo.get_active_trip_for_driver(driver_record.user_id)
        if existing_active is not None:
            # Defensive self-heal for legacy/inconsistent rows marked ACTIVE but already ended.
            if existing_active.ended_at is not None:
                existing_active.status = TripStatus.COMPLETED
                self.repo.save_trip(existing_active)
                self.db.commit()
            else:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Driver already has active trip")

        vehicle_id = (payload.vehicle_id or driver_record.driver_profile.assigned_vehicle_id or "").strip()
        if not vehicle_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vehicle ID is required for active tracking",
            )

        started_at = payload.started_at or datetime.now(UTC)
        trip = ActiveTrip(
            route_id=route.id,
            driver_id=driver_record.user_id,
            vehicle_id=vehicle_id,
            started_at=started_at,
            status=TripStatus.ACTIVE,
        )
        created = self.repo.create_trip(trip)
        self.db.commit()
        logger.info("Trip started", extra={"trip_id": created.trip_id, "driver_id": driver_record.user_id})
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

    def submit_commuter_location(self, user: User, trip_id: str, payload: CommuterLocationUpdateRequest) -> GPSUpdateResponse:
        trip = self.repo.get_trip_by_id(trip_id)
        if trip is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found")
        if trip.status != TripStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Trip is not active")
        if payload.latitude == 0 and payload.longitude == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Suspicious coordinates rejected")

        now = datetime.now(UTC)
        if payload.timestamp < now - timedelta(seconds=MAX_STALE_GPS_AGE_SECONDS):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Stale GPS update rejected")
        if payload.timestamp > now + timedelta(seconds=MAX_FUTURE_GPS_SKEW_SECONDS):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Future GPS timestamp rejected")

        existing = self.repo.get_commuter_location_for_user_trip(user.user_id, trip_id)
        row = CommuterTripLocation(
            user_id=user.user_id,
            trip_id=trip.trip_id,
            latitude=payload.latitude,
            longitude=payload.longitude,
            gps_timestamp=payload.timestamp,
        )
        saved = self.repo.upsert_commuter_location(existing, row)
        self.db.commit()
        logger.debug(
            "Commuter GPS stored",
            extra={"trip_id": trip_id, "user_id": user.user_id},
        )
        return GPSUpdateResponse(trip_id=trip_id, accepted=True, stored_at=saved.received_at)

    def get_bus_current_location(self, trip_id: str) -> BusLiveLocationOut:
        trip = self.repo.get_trip_by_id(trip_id)
        if trip is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found")
        current = self.repo.get_current_location_for_trip(trip_id)
        if current is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No GPS updates yet")
        occupancy = self._compute_current_occupancy(trip, current)
        return self._to_live_location(current, occupancy)

    def get_route_active_buses(self, route_id: str) -> RouteFleetOut:
        route = self.repo.get_route(route_id)
        if route is None or route.is_deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")
        # Ensure we query active buses by the route primary key (id)
        live = [self._to_live_location(item, self._compute_current_occupancy(item.trip, item)) for item in self.repo.list_active_buses_for_route(route.id)]
        return RouteFleetOut(route_id=route_id, active_buses=live)

    def get_route_bus_occupancy(self, route_id: str) -> RouteBusOccupancyOut:
        route = self.repo.get_route(route_id)
        if route is None or route.is_deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")

        buses = []
        for current in self.repo.list_active_buses_for_route(route.id):
            occupancy = self._compute_current_occupancy(current.trip, current)
            buses.append(
                BusOccupancyOut(
                    trip_id=current.trip_id,
                    bus_id=current.vehicle_id,
                    route_id=current.route_id,
                    estimated_passengers=occupancy["estimated_passengers"],
                    bus_capacity=occupancy["bus_capacity"],
                    occupancy_percent=occupancy["occupancy_percent"],
                    occupancy_level=occupancy["occupancy_level"],
                    is_high_occupancy=occupancy["is_high_occupancy"],
                )
            )
        return RouteBusOccupancyOut(route_id=route_id, active_buses=buses)

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

    def _to_live_location(self, current: BusCurrentLocation, occupancy: dict | None = None) -> BusLiveLocationOut:
        occupancy = occupancy or self._empty_occupancy()
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
            estimated_passengers=occupancy["estimated_passengers"],
            bus_capacity=occupancy["bus_capacity"],
            occupancy_percent=occupancy["occupancy_percent"],
            occupancy_level=occupancy["occupancy_level"],
            is_high_occupancy=occupancy["is_high_occupancy"],
        )

    def _empty_occupancy(self) -> dict:
        return {
            "estimated_passengers": 0,
            "bus_capacity": DEFAULT_BUS_CAPACITY,
            "occupancy_percent": 0.0,
            "occupancy_level": OccupancyLevel.LOW,
            "is_high_occupancy": False,
        }

    def _compute_current_occupancy(self, trip: ActiveTrip, current: BusCurrentLocation) -> dict:
        route_stops = self.repo.list_route_stops(trip.route_id)
        if not route_stops:
            return self._empty_occupancy()

        stop_index_map = {route_stop.stop_id: route_stop.sequence for route_stop in route_stops}
        current_sequence = self._infer_current_route_sequence(current, route_stops)

        now = datetime.now(UTC)
        route_start = trip.started_at if trip.started_at.tzinfo is not None else trip.started_at.replace(tzinfo=UTC)

        validation_events = (
            self.db.query(Event)
            .filter(
                Event.event_type == EventType.TICKET_VALIDATED,
                Event.route_id == trip.route_id,
                Event.occurred_at >= route_start,
                Event.occurred_at <= now,
            )
            .all()
        )
        scan_events = (
            self.db.query(Event)
            .filter(
                Event.event_type == EventType.TICKET_SCANNED,
                Event.route_id == trip.route_id,
                Event.occurred_at >= route_start,
                Event.occurred_at <= now,
            )
            .all()
        )

        boarding_stop_by_ticket_id: dict[str, str] = {}
        for scan_event in scan_events:
            metadata = scan_event.event_metadata or ""
            if not metadata:
                continue
            try:
                payload = json.loads(metadata)
            except Exception:
                continue
            ticket_id = payload.get("ticket_id")
            stop_id = payload.get("stop_id")
            if ticket_id and stop_id:
                boarding_stop_by_ticket_id[str(ticket_id)] = str(stop_id)

        estimated_passengers = 0
        for validation_event in validation_events:
            metadata = validation_event.event_metadata or ""
            try:
                payload = json.loads(metadata)
            except Exception:
                payload = {}

            ticket_id = payload.get("ticket_id")
            if not ticket_id:
                continue

            ticket = self.db.query(Ticket).filter(Ticket.id == str(ticket_id)).first()
            if ticket is None:
                continue
            if ticket.is_expired:
                continue

            boarding_stop_id = ticket.origin_stop_id or boarding_stop_by_ticket_id.get(str(ticket_id))
            if boarding_stop_id is None:
                continue

            boarding_sequence = stop_index_map.get(boarding_stop_id)
            if boarding_sequence is None:
                continue

            if boarding_sequence <= current_sequence:
                estimated_passengers += 1

        bus_capacity = DEFAULT_BUS_CAPACITY
        occupancy_percent = (estimated_passengers / bus_capacity * 100.0) if bus_capacity else 0.0
        if occupancy_percent > HIGH_OCCUPANCY_THRESHOLD * 100.0:
            occupancy_level = OccupancyLevel.HIGH
        elif occupancy_percent >= MEDIUM_OCCUPANCY_THRESHOLD * 100.0:
            occupancy_level = OccupancyLevel.MEDIUM
        else:
            occupancy_level = OccupancyLevel.LOW

        return {
            "estimated_passengers": estimated_passengers,
            "bus_capacity": bus_capacity,
            "occupancy_percent": round(occupancy_percent, 2),
            "occupancy_level": occupancy_level,
            "is_high_occupancy": occupancy_level == OccupancyLevel.HIGH,
        }

    def _infer_current_route_sequence(self, current: BusCurrentLocation, route_stops: list[RouteStop]) -> int:
        if not route_stops:
            return 0

        closest_stop = min(
            route_stops,
            key=lambda route_stop: self._haversine_km(
                current.latitude,
                current.longitude,
                float(route_stop.stop.latitude),
                float(route_stop.stop.longitude),
            ),
        )
        return int(closest_stop.sequence)

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
