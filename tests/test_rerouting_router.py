from __future__ import annotations

import unittest
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.deps import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.models.enums import UserRole, UserStatus
from app.models.event import Event, EventType
from app.models.stop import Stop
from app.models.ticket import Ticket
from app.models.user import User
from app.api.v1.endpoints import ticket as ticket_endpoint
from rerouting_router import router as rerouting_router


class FakeReroutingPipeline:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []

    def _record(self, name: str, *args, **kwargs):
        self.calls.append((name, args, kwargs))

    def assign_route(self, db: Session, bus_id: str, route_id: str, driver_id: str, scheduled_start: datetime) -> dict:
        self._record("assign_route", db, bus_id, route_id, driver_id, scheduled_start)
        return {
            "assignment_id": "assignment-1",
            "route": {
                "id": route_id,
                "route_code": "R-001",
                "route_name": "Main Line",
                "distance_km": 12.5,
                "price": "15.00",
            },
        }

    def list_route_logs(self, db: Session, route_id: str, date_from, date_to, page: int, page_size: int) -> dict:
        self._record("list_route_logs", db, route_id, date_from, date_to, page, page_size)
        return {
            "items": [
                {
                    "id": str(uuid.uuid4()),
                    "trip_id": "trip-1",
                    "bus_id": "bus-1",
                    "route_id": route_id,
                    "driver_id": "driver-1",
                    "timestamp": datetime.now(UTC),
                    "day_of_week": 1,
                    "time_range": "06-10",
                    "month": 5,
                    "latitude": 9.0,
                    "longitude": 38.7,
                    "speed": 18.5,
                    "mileage_covered": 3.2,
                    "passenger_count": 8,
                    "stop_id": None,
                    "total_time_seconds": 900.0,
                    "congestion_score": 0.21,
                    "high_demand_segment": 0,
                }
            ],
            "page": page,
            "page_size": page_size,
            "total": 1,
        }

    def model_status(self, db: Session) -> dict:
        self._record("model_status", db)
        return {
            "phase": 2,
            "model_version": "v1_2026-05",
            "accuracy": 0.91,
            "rows_collected": 5200,
            "rows_needed_for_next_phase": 0,
            "last_retrain_timestamp": datetime.now(UTC).isoformat(),
        }

    def manual_retrain(self) -> dict:
        self._record("manual_retrain")
        return {
            "job_id": "job-1",
            "status": "promoted",
            "rows_used": 600,
            "accuracy_before": 0.81,
            "accuracy_after": 0.89,
            "promoted": True,
            "model_version": "v2_2026-05",
            "feature_importances": {"passenger_count": 0.4},
        }

    def start_trip(self, db: Session, bus_id: str, driver_id: str, assignment_id: str) -> dict:
        self._record("start_trip", db, bus_id, driver_id, assignment_id)
        return {
            "trip_id": "trip-1",
            "assigned_route_polyline": [[9.0, 38.7], [9.05, 38.75]],
        }

    def log_gps_update(self, db: Session, trip_id: str, driver_id: str, latitude: float, longitude: float, speed: float, passenger_count: int, stop_id: str | None = None) -> dict:
        self._record("log_gps_update", db, trip_id, driver_id, latitude, longitude, speed, passenger_count, stop_id)
        return {
            "reroute_suggested": True,
            "reroute_id": "reroute-1",
            "new_route": [[9.0, 38.7], [9.1, 38.8]],
        }

    def end_trip(self, db: Session, trip_id: str, final_latitude: float, final_longitude: float) -> dict:
        self._record("end_trip", db, trip_id, final_latitude, final_longitude)
        return {
            "trip_id": trip_id,
            "total_time_seconds": 1800.0,
            "total_distance_km": 5.4,
            "avg_speed_kph": 10.8,
            "stops_served": 2,
            "final_latitude": final_latitude,
            "final_longitude": final_longitude,
        }

    def record_feedback(self, db: Session, reroute_id: str, accepted: bool) -> dict:
        self._record("record_feedback", db, reroute_id, accepted)
        return {"acknowledged": True}

    def record_outcome(self, db: Session, reroute_id: str, actual_time_saving: float) -> dict:
        self._record("record_outcome", db, reroute_id, actual_time_saving)
        return {"recorded": True}

    def stop_demand(self, db: Session, stop_id: str) -> dict:
        self._record("stop_demand", db, stop_id)
        return {
            "stop_id": stop_id,
            "predicted_demand_windows": [
                {"time_window": datetime.now(UTC).isoformat(), "predicted_demand": 0.62},
            ],
            "current_congestion_score": 0.33,
            "estimated_wait_time_minutes": 12,
        }


class ReroutingRouterEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        return None

    @classmethod
    def tearDownClass(cls) -> None:
        return None

    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

        self.app = FastAPI()
        self.app.include_router(rerouting_router, prefix="/api/v1/rerouting")
        self.app.include_router(ticket_endpoint.router, prefix="/api/v1/tickets")

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        self.app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(self.app)

        self.pipeline = FakeReroutingPipeline()
        self.app.state.rerouting_pipeline = self.pipeline

        self.current_user = User(
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
        db.add_all([self.current_user, self.admin_user, self.commuter_user])
        db.commit()

        self.current_user_id = self.current_user.user_id
        self.admin_user_id = self.admin_user.user_id
        self.commuter_user_id = self.commuter_user.user_id

        self.ticket_id = str(uuid.uuid4())
        self.ticket_route_id = str(uuid.uuid4())
        self.ticket = Ticket(
            id=self.ticket_id,
            user_id=self.commuter_user_id,
            route_id=self.ticket_route_id,
            origin_stop_id=None,
            fare=25,
            qr_code="qr-test-001",
        )
        db.add(self.ticket)
        db.add(
            Stop(
                id="stop-1",
                name="Stop One",
                latitude=9.01,
                longitude=38.79,
            )
        )
        db.commit()
        db.close()

        self.auth_user_id = self.current_user_id
        self.auth_role = UserRole.DRIVER
        self.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            user_id=self.auth_user_id,
            role=self.auth_role,
        )

    def tearDown(self) -> None:
        self.client.close()
        self.app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_admin_rerouting_endpoints_use_pipeline(self) -> None:
        self.auth_user_id = self.admin_user_id
        self.auth_role = UserRole.ADMIN

        assign_response = self.client.post(
            "/api/v1/rerouting/assign-route",
            json={
                "bus_id": "bus-1",
                "route_id": "route-1",
                "driver_id": self.admin_user_id,
                "scheduled_start": datetime.now(UTC).isoformat(),
            },
        )
        self.assertEqual(assign_response.status_code, 201)
        self.assertEqual(assign_response.json()["assignment_id"], "assignment-1")

        logs_response = self.client.get(
            "/api/v1/rerouting/routes/route-1/logs",
            params={"page": 1, "page_size": 10},
        )
        self.assertEqual(logs_response.status_code, 200)
        self.assertEqual(logs_response.json()["total"], 1)
        self.assertEqual(logs_response.json()["items"][0]["route_id"], "route-1")

        status_response = self.client.get("/api/v1/rerouting/model/status")
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["phase"], 2)

        retrain_response = self.client.post("/api/v1/rerouting/model/retrain")
        self.assertEqual(retrain_response.status_code, 200)
        self.assertEqual(retrain_response.json()["job_id"], "job-1")

    def test_driver_rerouting_trip_flow(self) -> None:
        self.auth_user_id = self.current_user_id
        self.auth_role = UserRole.DRIVER

        start_response = self.client.post(
            "/api/v1/rerouting/trips/start",
            json={
                "bus_id": "bus-1",
                "driver_id": self.current_user_id,
                "assignment_id": "assignment-1",
            },
        )
        self.assertEqual(start_response.status_code, 201)
        self.assertEqual(start_response.json()["trip_id"], "trip-1")

        gps_response = self.client.post(
            "/api/v1/rerouting/trips/trip-1/gps",
            json={
                "latitude": 9.01,
                "longitude": 38.79,
                "speed": 11.0,
                "passenger_count": 50,
                "stop_id": "stop-1",
            },
        )
        self.assertEqual(gps_response.status_code, 200)
        self.assertTrue(gps_response.json()["reroute_suggested"])

        feedback_response = self.client.post(
            "/api/v1/rerouting/reroutes/reroute-1/feedback",
            json={"accepted": True},
        )
        self.assertEqual(feedback_response.status_code, 200)
        self.assertTrue(feedback_response.json()["acknowledged"])

        outcome_response = self.client.post(
            "/api/v1/rerouting/reroutes/reroute-1/outcome",
            json={"actual_time_saving": 4.5},
        )
        self.assertEqual(outcome_response.status_code, 200)
        self.assertTrue(outcome_response.json()["recorded"])

        end_response = self.client.post(
            "/api/v1/rerouting/trips/trip-1/end",
            json={
                "final_latitude": 9.05,
                "final_longitude": 38.81,
            },
        )
        self.assertEqual(end_response.status_code, 200)
        self.assertEqual(end_response.json()["stops_served"], 2)

    def test_stop_demand_and_ticket_scan_endpoints(self) -> None:
        self.auth_user_id = self.commuter_user_id
        self.auth_role = UserRole.COMMUTER

        demand_response = self.client.get("/api/v1/rerouting/stops/stop-1/demand")
        self.assertEqual(demand_response.status_code, 200)
        self.assertEqual(demand_response.json()["stop_id"], "stop-1")

        scan_response = self.client.post(
            "/api/v1/tickets/scan",
            json={
                "ticket_id": self.ticket_id,
                "bus_id": "bus-1",
                "stop_id": "stop-1",
                "direction": "outbound",
            },
        )
        self.assertEqual(scan_response.status_code, 200)
        self.assertTrue(scan_response.json()["acknowledged"])

        db = self.SessionLocal()
        event = db.query(Event).filter(Event.event_type == EventType.TICKET_SCANNED).one()
        self.assertEqual(event.route_id, self.ticket_route_id)
        self.assertIsNotNone(event.event_metadata)
        db.close()


if __name__ == "__main__":
    unittest.main()