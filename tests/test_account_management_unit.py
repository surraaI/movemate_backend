from __future__ import annotations

import unittest
import uuid
from datetime import UTC, datetime

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