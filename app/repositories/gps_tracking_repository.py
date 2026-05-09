from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.enums import TripStatus
from app.models.gps_tracking import ActiveTrip, BusCurrentLocation, BusLocationHistory
from app.models.route import Route
from app.models.route_stop import RouteStop


class GPSTrackingRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_route(self, route_id: str) -> Route | None:
        return self.db.get(Route, route_id)

    def get_active_trip_for_driver(self, driver_id: str) -> ActiveTrip | None:
        query = select(ActiveTrip).where(
            ActiveTrip.driver_id == driver_id,
            ActiveTrip.status == TripStatus.ACTIVE,
        )
        return self.db.scalar(query)

    def get_trip_by_id(self, trip_id: str) -> ActiveTrip | None:
        return self.db.get(ActiveTrip, trip_id)

    def create_trip(self, trip: ActiveTrip) -> ActiveTrip:
        self.db.add(trip)
        self.db.flush()
        self.db.refresh(trip)
        return trip

    def save_trip(self, trip: ActiveTrip) -> ActiveTrip:
        self.db.add(trip)
        self.db.flush()
        self.db.refresh(trip)
        return trip

    def get_current_location_for_trip(self, trip_id: str) -> BusCurrentLocation | None:
        return self.db.scalar(select(BusCurrentLocation).where(BusCurrentLocation.trip_id == trip_id))

    def upsert_current_location(
        self,
        existing: BusCurrentLocation | None,
        payload: BusCurrentLocation,
    ) -> BusCurrentLocation:
        if existing is None:
            self.db.add(payload)
            self.db.flush()
            self.db.refresh(payload)
            return payload

        existing.latitude = payload.latitude
        existing.longitude = payload.longitude
        existing.speed_kph = payload.speed_kph
        existing.heading_degrees = payload.heading_degrees
        existing.gps_timestamp = payload.gps_timestamp
        self.db.add(existing)
        self.db.flush()
        self.db.refresh(existing)
        return existing

    def add_history_location(self, payload: BusLocationHistory) -> BusLocationHistory:
        self.db.add(payload)
        self.db.flush()
        self.db.refresh(payload)
        return payload

    def list_active_buses_for_route(self, route_id: str) -> list[BusCurrentLocation]:
        query = (
            select(BusCurrentLocation)
            .join(ActiveTrip, ActiveTrip.trip_id == BusCurrentLocation.trip_id)
            .where(ActiveTrip.status == TripStatus.ACTIVE, BusCurrentLocation.route_id == route_id)
            .order_by(BusCurrentLocation.gps_timestamp.desc())
        )
        return list(self.db.scalars(query).all())

    def list_live_fleet(self) -> list[BusCurrentLocation]:
        query = (
            select(BusCurrentLocation)
            .join(ActiveTrip, ActiveTrip.trip_id == BusCurrentLocation.trip_id)
            .where(ActiveTrip.status == TripStatus.ACTIVE)
            .order_by(BusCurrentLocation.updated_at.desc())
        )
        return list(self.db.scalars(query).all())

    def list_route_stops(self, route_id: str) -> list[RouteStop]:
        query = (
            select(RouteStop)
            .options(joinedload(RouteStop.stop))
            .where(RouteStop.route_id == route_id)
            .order_by(RouteStop.sequence.asc())
        )
        return list(self.db.scalars(query).all())
