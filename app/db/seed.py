from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models.enums import UserRole, UserStatus
from app.models.profile import AdminProfile
from app.models.user import User


def seed_superadmin(db: Session) -> User | None:
    """
    Create a bootstrap SUPERADMIN user if SUPERADMIN_EMAIL and SUPERADMIN_PASSWORD are set.
    Safe to run on every startup (idempotent).
    """
    if not settings.SUPERADMIN_EMAIL or not settings.SUPERADMIN_PASSWORD:
        return None

    email = settings.SUPERADMIN_EMAIL.strip().lower()
    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        return existing

    user = User(
        full_name=settings.SUPERADMIN_FULL_NAME.strip() or "Super Admin",
        email=email,
        password_hash=hash_password(settings.SUPERADMIN_PASSWORD),
        phone_number=settings.SUPERADMIN_PHONE_NUMBER.strip() or "N/A",
        role=UserRole.SUPERADMIN,
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    db.flush()

    db.add(
        AdminProfile(
            user_id=user.user_id,
            department="SYSTEM",
            permissions=json.dumps(["*"]),
        )
    )

    db.commit()
    db.refresh(user)
    return user

