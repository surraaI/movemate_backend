from __future__ import annotations

import unittest
import uuid
from datetime import UTC, datetime
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.security import create_access_token, decode_token, hash_password, verify_password
from app.db.base import Base
from app.models.enums import UserRole, UserStatus
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services import auth_service, user_service
from app.services.admin_service import AdminService
from app.core.security import get_current_user


class AccountManagementUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        Base.metadata.create_all(bind=cls.engine)

    @classmethod
    def tearDownClass(cls) -> None:
        Base.metadata.drop_all(bind=cls.engine)
        cls.engine.dispose()

    def setUp(self) -> None:
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

    def _create_user(self, *, status: UserStatus = UserStatus.ACTIVE) -> tuple:
        db = self.SessionLocal()
        user = User(
            user_id=str(uuid.uuid4()),
            full_name="Test User",
            email="user@example.com",
            password_hash=hash_password("password123"),
            phone_number="+251900000000",
            role=UserRole.COMMUTER,
            status=status,
        )
        db.add(user)
        db.flush()
        refresh_token = RefreshToken(
            user_id=user.user_id,
            jti=str(uuid.uuid4()),
            expires_at=datetime.now(UTC),
        )
        db.add(refresh_token)
        db.commit()
        db.refresh(user)
        return db, user, refresh_token

    def test_delete_account_revokes_refresh_tokens(self) -> None:
        db, user, refresh_token = self._create_user()

        user_service.delete_account(db, user)

        db.refresh(user)
        db.refresh(refresh_token)
        self.assertEqual(user.status, UserStatus.INACTIVE)
        self.assertIsNotNone(refresh_token.revoked_at)

        db.close()

    def test_forgot_password_and_reset_password_round_trip(self) -> None:
        db, user, refresh_token = self._create_user()

        reset_token, expires_at = auth_service.forgot_password(db, user.email)
        payload = decode_token(reset_token)
        self.assertEqual(payload["type"], "password_reset")
        self.assertEqual(payload["sub"], user.user_id)
        self.assertGreater(expires_at, datetime.now(UTC))

        auth_service.reset_password(db, reset_token, "newpassword123")

        refreshed = db.get(User, user.user_id)
        self.assertIsNotNone(refreshed)
        self.assertTrue(verify_password("newpassword123", refreshed.password_hash))
        self.assertFalse(verify_password("password123", refreshed.password_hash))
        db.refresh(refresh_token)
        self.assertIsNotNone(refresh_token.revoked_at)

        db.close()

    def test_login_accepts_whitespace_and_case_variations_in_email(self) -> None:
        db, user, _refresh_token = self._create_user()

        pair = auth_service.login(db, "  USER@EXAMPLE.COM  ", "password123")

        self.assertTrue(pair.access_token)
        self.assertTrue(pair.refresh_token)
        refreshed = db.get(User, user.user_id)
        self.assertIsNotNone(refreshed)
        self.assertIsNotNone(refreshed.last_login)

        db.close()

    def test_admin_lookup_reports_existing_user_and_creation_flow(self) -> None:
        db, user, _refresh_token = self._create_user()

        result = AdminService.lookup_user_by_email(db, "USER@example.com")

        self.assertTrue(result["found"])
        self.assertEqual(result["email"], user.email)
        self.assertEqual(result["role"], UserRole.COMMUTER.value)
        self.assertEqual(result["password_flow"], "self_register")

        db.close()

    def test_create_driver_returns_temporary_password_and_email_status(self) -> None:
        db = self.SessionLocal()

        with patch("app.services.admin_service.EmailService.send_driver_temporary_password_email", return_value=True):
            user, temporary_password, email_sent = AdminService.create_driver(
                db,
                email="driver@example.com",
                password="ignored-password",
                full_name="Driver One",
                phone_number="+251900000002",
                license_number="LIC-12345",
                employee_id="EMP-12345",
                assigned_vehicle_id=None,
            )

        self.assertTrue(email_sent)
        self.assertTrue(verify_password(temporary_password, user.password_hash))
        self.assertEqual(user.email, "driver@example.com")
        self.assertEqual(user.role, UserRole.DRIVER)
        db.close()

    def test_create_driver_continues_when_email_send_fails(self) -> None:
        db = self.SessionLocal()

        with patch("app.services.admin_service.EmailService.send_driver_temporary_password_email", side_effect=RuntimeError("smtp down")):
            user, temporary_password, email_sent = AdminService.create_driver(
                db,
                email="driver2@example.com",
                password="ignored-password",
                full_name="Driver Two",
                phone_number="+251900000003",
                license_number="LIC-54321",
                employee_id="EMP-54321",
                assigned_vehicle_id=None,
            )

        self.assertFalse(email_sent)
        self.assertTrue(verify_password(temporary_password, user.password_hash))
        self.assertEqual(user.email, "driver2@example.com")
        db.close()

    def test_user_to_out_accepts_internal_email_addresses(self) -> None:
        db = self.SessionLocal()
        user = User(
            user_id=str(uuid.uuid4()),
            full_name="Internal User",
            email="driver@movemate.local",
            password_hash=hash_password("password123"),
            phone_number="+251900000001",
            role=UserRole.DRIVER,
            status=UserStatus.ACTIVE,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        user_out = user_service.user_to_out(user)

        self.assertEqual(user_out.email, "driver@movemate.local")
        db.close()

    def test_inactive_user_cannot_use_access_token(self) -> None:
        db, user, _refresh_token = self._create_user(status=UserStatus.INACTIVE)
        token = create_access_token(user.user_id, role=user.role.value)
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with self.assertRaises(HTTPException) as context:
            get_current_user(credentials, db)

        self.assertEqual(context.exception.status_code, 403)
        db.close()


if __name__ == "__main__":
    unittest.main()