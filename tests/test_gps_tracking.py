from __future__ import annotations

import unittest
import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.profile import DriverProfile
from app.models.route import Route
from app.models.user import User
from app.models.enums import UserRole, UserStatus


class GPSTrackingIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        Base.metadata.create_all(bind=cls.engine)

        def override_get_db():
            db = cls.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=cls.engine)
        cls.engine.dispose()

    def setUp(self) -> None:
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

        db: Session = self.SessionLocal()
        self.driver_id = str(uuid.uuid4())
        self.commuter_id = str(uuid.uuid4())
        self.admin_id = str(uuid.uuid4())
        self.driver = User(
            user_id=self.driver_id,
            full_name="Driver One",
            email="driver@movemate.local",
            password_hash=hash_password("password123"),
            phone_number="+251911000001",
            role=UserRole.DRIVER,
            status=UserStatus.ACTIVE,
        )
        self.commuter = User(
            user_id=self.commuter_id,
            full_name="Commuter One",
            email="commuter@movemate.local",
            password_hash=hash_password("password123"),
            phone_number="+251911000002",
            role=UserRole.COMMUTER,
            status=UserStatus.ACTIVE,
        )
        self.admin = User(
            user_id=self.admin_id,
            full_name="Admin One",
            email="admin@movemate.local",
            password_hash=hash_password("password123"),
            phone_number="+251911000003",
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
        )
        route = Route(route_code="R-TST", route_name="Test Route")
        db.add_all([self.driver, self.commuter, self.admin, route])
        db.flush()
        db.add(
            DriverProfile(
                user_id=self.driver.user_id,
                license_number="LIC-0001",
                employee_id="DRV-0001",
                assigned_vehicle_id="BUS-001",
            )
        )
        db.commit()
        self.route_id = route.id
        db.close()

        self.driver_headers = self._headers_for(self.driver_id)
        self.commuter_headers = self._headers_for(self.commuter_id)
        self.admin_headers = self._headers_for(self.admin_id)

    def _headers_for(self, user_id: str) -> dict[str, str]:
        token = create_access_token(user_id)
        return {"Authorization": f"Bearer {token}"}

    def test_driver_trip_start_update_and_end_flow(self) -> None:
        start = self.client.post(
            "/api/v1/gps/trips/start",
            headers=self.driver_headers,
            json={"routeId": self.route_id},
        )
        self.assertEqual(start.status_code, 201)
        trip_id = start.json()["tripId"]

        gps = self.client.post(
            f"/api/v1/gps/trips/{trip_id}/locations",
            headers=self.driver_headers,
            json={
                "latitude": 9.011,
                "longitude": 38.79,
                "timestamp": datetime.now(UTC).isoformat(),
                "speedKph": 32.1,
                "headingDegrees": 95,
            },
        )
        self.assertEqual(gps.status_code, 200)
        self.assertTrue(gps.json()["accepted"])

        current = self.client.get(
            f"/api/v1/gps/trips/{trip_id}/locations/current",
            headers=self.commuter_headers,
        )
        self.assertEqual(current.status_code, 200)
        self.assertEqual(current.json()["tripId"], trip_id)

        end = self.client.post(
            f"/api/v1/gps/trips/{trip_id}/end",
            headers=self.driver_headers,
            json={"endedAt": datetime.now(UTC).isoformat()},
        )
        self.assertEqual(end.status_code, 200)
        self.assertEqual(end.json()["status"], "COMPLETED")

    def test_reject_duplicate_and_unrealistic_updates(self) -> None:
        start = self.client.post(
            "/api/v1/gps/trips/start",
            headers=self.driver_headers,
            json={"routeId": self.route_id},
        )
        self.assertEqual(start.status_code, 201)
        trip_id = start.json()["tripId"]
        ts = datetime.now(UTC)

        first = self.client.post(
            f"/api/v1/gps/trips/{trip_id}/locations",
            headers=self.driver_headers,
            json={
                "latitude": 9.011,
                "longitude": 38.79,
                "timestamp": ts.isoformat(),
                "speedKph": 30.0,
            },
        )
        self.assertEqual(first.status_code, 200)

        duplicate = self.client.post(
            f"/api/v1/gps/trips/{trip_id}/locations",
            headers=self.driver_headers,
            json={
                "latitude": 9.011,
                "longitude": 38.79,
                "timestamp": ts.isoformat(),
                "speedKph": 30.0,
            },
        )
        self.assertIn(duplicate.status_code, (400, 409))

        unrealistic = self.client.post(
            f"/api/v1/gps/trips/{trip_id}/locations",
            headers=self.driver_headers,
            json={
                "latitude": 9.4,
                "longitude": 38.5,
                "timestamp": (ts + timedelta(seconds=40)).isoformat(),
                "speedKph": 40.0,
            },
        )
        self.assertEqual(unrealistic.status_code, 400)

    def test_admin_live_fleet_requires_admin_role(self) -> None:
        commuter_attempt = self.client.get("/api/v1/gps/fleet/live", headers=self.commuter_headers)
        self.assertEqual(commuter_attempt.status_code, 403)

        admin_attempt = self.client.get("/api/v1/gps/fleet/live", headers=self.admin_headers)
        self.assertEqual(admin_attempt.status_code, 200)
        self.assertIn("totalActiveTrips", admin_attempt.json())


if __name__ == "__main__":
    unittest.main()
