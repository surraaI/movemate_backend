from __future__ import annotations

import unittest
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.api.v1.endpoints import ticket as ticket_endpoint
from app.core.deps import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.models.enums import UserRole, UserStatus
from app.models.ticket import Ticket
from app.models.user import User


class TicketValidationUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

        self.app = FastAPI()
        self.app.include_router(ticket_endpoint.router, prefix="/api/v1/tickets")

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        self.app.dependency_overrides[get_db] = override_get_db

        self.driver_user = User(
            user_id=str(uuid.uuid4()),
            full_name="Driver User",
            email="driver@example.com",
            password_hash="x",
            phone_number="+251900000000",
            role=UserRole.DRIVER,
            status=UserStatus.ACTIVE,
        )
        self.commuter_user = User(
            user_id=str(uuid.uuid4()),
            full_name="Commuter User",
            email="commuter@example.com",
            password_hash="x",
            phone_number="+251900000001",
            role=UserRole.COMMUTER,
            status=UserStatus.ACTIVE,
        )

        db = self.SessionLocal()
        db.add_all([self.driver_user, self.commuter_user])
        db.commit()
        self.driver_user_id = self.driver_user.user_id
        self.commuter_user_id = self.commuter_user.user_id
        db.close()

        self.auth_user_id = self.driver_user_id
        self.auth_role = UserRole.DRIVER
        self.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            user_id=self.auth_user_id,
            role=self.auth_role,
        )

        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()
        self.app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _create_ticket(self, *, created_at: datetime) -> Ticket:
        ticket = Ticket(
            id=str(uuid.uuid4()),
            user_id=self.commuter_user_id,
            route_id=str(uuid.uuid4()),
            origin_stop_id=None,
            fare=25,
            qr_code="qr-ticket-001",
            created_at=created_at,
        )
        db = self.SessionLocal()
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        db.close()
        return ticket

    def test_driver_can_validate_ticket_once_and_ticket_qr_becomes_invalid(self) -> None:
        ticket = self._create_ticket(created_at=datetime.now(UTC))

        response = self.client.post(
            "/api/v1/tickets/validate",
            json={"qr_code": ticket.qr_code, "bus_id": "bus-1"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["valid"])
        self.assertEqual(response.json()["ticket_id"], ticket.id)

        db = self.SessionLocal()
        validated_ticket = db.get(Ticket, ticket.id)
        self.assertIsNotNone(validated_ticket)
        self.assertIsNone(validated_ticket.qr_code)
        db.close()

        second_response = self.client.post(
            "/api/v1/tickets/validate",
            json={"qr_code": ticket.qr_code, "bus_id": "bus-1"},
        )
        self.assertEqual(second_response.status_code, 404)

        self.auth_user_id = self.commuter_user.user_id
        self.auth_role = UserRole.COMMUTER
        qr_response = self.client.get(f"/api/v1/tickets/{ticket.id}/qr")
        self.assertEqual(qr_response.status_code, 404)

    def test_expired_ticket_cannot_be_validated(self) -> None:
        expired_ticket = self._create_ticket(created_at=datetime.now(UTC) - timedelta(hours=25))

        response = self.client.post(
            "/api/v1/tickets/validate",
            json={"qr_code": expired_ticket.qr_code, "bus_id": "bus-1"},
        )
        self.assertEqual(response.status_code, 410)


if __name__ == "__main__":
    unittest.main()