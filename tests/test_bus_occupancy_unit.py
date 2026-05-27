from __future__ import annotations

import json
import unittest
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.api.v1.endpoints import admin as admin_endpoint
from app.api.v1.endpoints import gps_tracking as gps_endpoint
from app.core.deps import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.models.analytics import AnalyticsReroutingEventLog
from app.models.enums import OccupancyLevel, TripStatus, UserRole, UserStatus
from app.models.event import Event, EventType
from app.models.gps_tracking import ActiveTrip, BusCurrentLocation
from app.models.route import Route
from app.models.route_stop import RouteStop
from app.models.stop import Stop
from app.models.ticket import Ticket
from app.models.user import User
from app.services.analytics_service import AnalyticsService
from app.services.gps_tracking_service import GPSTrackingService


class BusOccupancyFeatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

        self.app = FastAPI()
        self.app.include_router(gps_endpoint.router, prefix="/api/v1/gps")
        self.app.include_router(admin_endpoint.router, prefix="/api/v1/admin")

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        self.app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(self.app)

        self.driver_user = User(
            user_id=str(uuid.uuid4()),
            full_name="Driver User",
            email="driver@example.com",
            password_hash="x",
            phone_number="+251900000000",
            role=UserRole.DRIVER,
            status=UserStatus.ACTIVE,
        )
        self.admin_user = User(
            user_id=str(uuid.uuid4()),
            full_name="Admin User",
            email="admin@example.com",
            password_hash="x",
            phone_number="+251900000001",
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
        )
        self.commuter_user = User(
            user_id=str(uuid.uuid4()),
            full_name="Commuter User",
            email="commuter@example.com",
            password_hash="x",
            phone_number="+251900000002",
            role=UserRole.COMMUTER,
            status=UserStatus.ACTIVE,
        )

        db = self.SessionLocal()
        db.add_all([self.driver_user, self.admin_user, self.commuter_user])

        self.route = Route(
            id="route-1",
            route_code="R-001",
            route_name="Main Line",
            price=25.0,
            distance_km=12.5,
        )
        db.add(self.route)

        self.stop_1 = Stop(id="stop-1", name="Stop One", latitude=9.01, longitude=38.79)
        self.stop_2 = Stop(id="stop-2", name="Stop Two", latitude=9.02, longitude=38.8)
        self.stop_3 = Stop(id="stop-3", name="Stop Three", latitude=9.03, longitude=38.81)
        db.add_all([self.stop_1, self.stop_2, self.stop_3])
        db.flush()

        db.add_all(
            [
                RouteStop(route_id=self.route.id, stop_id=self.stop_1.id, sequence=1),
                RouteStop(route_id=self.route.id, stop_id=self.stop_2.id, sequence=2),
                RouteStop(route_id=self.route.id, stop_id=self.stop_3.id, sequence=3),
            ]
        )

        self.bus = __import__("app.models.bus", fromlist=["Bus"]).Bus(bus_id="bus-1", route_id=self.route.id, status="ACTIVE")
        db.add(self.bus)

        self.trip = ActiveTrip(
            trip_id="trip-1",
            route_id=self.route.id,
            driver_id=self.driver_user.user_id,
            vehicle_id=self.bus.bus_id,
            status=TripStatus.ACTIVE,
            started_at=datetime.now(UTC),
        )
        db.add(self.trip)
        db.flush()

        db.add(
            BusCurrentLocation(
                trip_id=self.trip.trip_id,
                route_id=self.route.id,
                vehicle_id=self.bus.bus_id,
                latitude=9.0201,
                longitude=38.8001,
                speed_kph=18.0,
                heading_degrees=90,
                gps_timestamp=datetime.now(UTC),
            )
        )

        now = datetime.now(UTC)
        for index in range(45):
            ticket = Ticket(
                id=f"ticket-{index}",
                user_id=self.commuter_user.user_id,
                route_id=self.route.id,
                origin_stop_id=self.stop_1.id,
                fare=25,
                qr_code=None,
                created_at=now,
            )
            db.add(ticket)
            db.add(
                Event(
                    id=str(uuid.uuid4()),
                    event_type=EventType.TICKET_VALIDATED,
                    user_id=self.commuter_user.user_id,
                    route_id=self.route.id,
                    trip_id=self.trip.trip_id,
                    event_metadata=json.dumps({
                        "ticket_id": ticket.id,
                        "bus_id": self.bus.bus_id,
                        "validated_at": now.isoformat(),
                    }),
                    occurred_at=now,
                )
            )

        db.commit()
        db.close()

        self.trip_id = self.trip.trip_id
        self.admin_user_id = self.admin_user.user_id

        self.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            user_id=self.commuter_user.user_id,
            role=UserRole.COMMUTER,
        )

    def tearDown(self) -> None:
        self.client.close()
        self.app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_bus_current_location_includes_occupancy(self) -> None:
        response = self.client.get(f"/api/v1/gps/trips/{self.trip_id}/locations/current")
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertEqual(payload["occupancyLevel"], OccupancyLevel.HIGH.value)
        self.assertTrue(payload["isHighOccupancy"])
        self.assertEqual(payload["estimatedPassengers"], 45)
        self.assertEqual(payload["busCapacity"], 50)
        self.assertAlmostEqual(payload["occupancyPercent"], 90.0, places=2)

    def test_admin_route_occupancy_endpoint_reports_active_bus(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            user_id=self.admin_user_id,
            role=UserRole.ADMIN,
        )

        response = self.client.get("/api/v1/admin/routes/route-1/occupancy")
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertEqual(payload["routeId"], "route-1")
        self.assertEqual(len(payload["activeBuses"]), 1)
        bus = payload["activeBuses"][0]
        self.assertEqual(bus["occupancyLevel"], OccupancyLevel.HIGH.value)
        self.assertTrue(bus["isHighOccupancy"])

    def test_high_occupancy_is_flagged_for_analytics_triggers(self) -> None:
        db = self.SessionLocal()
        try:
            service = AnalyticsService(db)
            created = service.sync_high_occupancy_signals()
            self.assertEqual(created, 1)

            log = db.query(AnalyticsReroutingEventLog).one()
            self.assertEqual(log.trigger_reason, "high_occupancy")
            self.assertEqual(log.route_id, self.route.id)
            self.assertEqual(log.bus_id, self.bus.bus_id)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
