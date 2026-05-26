from __future__ import annotations

import unittest
import uuid
from datetime import UTC, datetime
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.api.payments import router as chapa_payments_router
from app.api.v1.endpoints import ticket as ticket_endpoint
from app.core.deps import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.models.enums import UserRole, UserStatus
from app.models.payment import Payment
from app.models.ticket import Ticket
from app.models.user import User


class PaymentCallbackUnitTests(unittest.TestCase):
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
        self.app.include_router(chapa_payments_router)

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        self.app.dependency_overrides[get_db] = override_get_db

        self.user = User(
            user_id=str(uuid.uuid4()),
            full_name="Commuter User",
            email="commuter@example.com",
            password_hash="x",
            phone_number="+251900000001",
            role=UserRole.COMMUTER,
            status=UserStatus.ACTIVE,
        )
        db = self.SessionLocal()
        db.add(self.user)
        db.commit()
        self.user_id = self.user.user_id
        db.close()

        self.app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()
        self.app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _seed_payment(self, tx_ref: str) -> None:
        db = self.SessionLocal()
        db.add(
            Payment(
                tx_ref=tx_ref,
                user_id=self.user_id,
                route_id=str(uuid.uuid4()),
                amount=25,
                status="pending",
            )
        )
        db.commit()
        db.close()

    def test_callback_alias_and_legacy_route_process_successful_payment(self) -> None:
        callback_paths = [
            "/api/v1/tickets/callback",
            "/api/payments/chapa/callback",
        ]

        for index, path in enumerate(callback_paths, start=1):
            tx_ref = f"tx-test-{index}"
            self._seed_payment(tx_ref)

            fake_ticket = Ticket(
                id=str(uuid.uuid4()),
                user_id=self.user_id,
                route_id=str(uuid.uuid4()),
                origin_stop_id=None,
                fare=25,
                qr_code=f"qrcodes/{tx_ref}.png",
                created_at=datetime.now(UTC),
            )

            with patch("app.services.ticket_service.verify_payment", return_value={"status": "success"}), patch(
                "app.services.ticket_service.purchase_ticket", return_value=fake_ticket
            ):
                response = self.client.get(path, params={"trx_ref": tx_ref})

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["message"], "Payment verified")
            self.assertEqual(response.json()["ticket"]["id"], fake_ticket.id)

            db = self.SessionLocal()
            payment = db.query(Payment).filter(Payment.tx_ref == tx_ref).first()
            self.assertIsNotNone(payment)
            self.assertEqual(payment.status, "success")
            db.close()


if __name__ == "__main__":
    unittest.main()