from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.enums import UserRole, UserStatus
from app.models.profile import AdminProfile, CommuterProfile, DriverProfile
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import RegisterRequest, TokenPair


def _issue_tokens(db: Session, user: User) -> TokenPair:
    jti = str(uuid.uuid4())
    expires_at = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    row = RefreshToken(user_id=user.user_id, jti=jti, expires_at=expires_at)
    db.add(row)
    db.flush()
    access = create_access_token(user.user_id)
    refresh = create_refresh_token(user.user_id, jti)
    return TokenPair(access_token=access, refresh_token=refresh, token_type="bearer")


def register(db: Session, data: RegisterRequest) -> TokenPair:
    existing = db.scalar(select(User).where(User.email == data.email))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        full_name=data.full_name,
        email=str(data.email).lower(),
        password_hash=hash_password(data.password),
        phone_number=data.phone_number,
        role=data.role,
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    db.flush()

    if data.role == UserRole.COMMUTER:
        db.add(
            CommuterProfile(
                user_id=user.user_id,
                preferred_route_id=data.commuter_preferred_route_id,
                notes=None,
            )
        )
    elif data.role == UserRole.DRIVER:
        db.add(
            DriverProfile(
                user_id=user.user_id,
                license_number=data.driver_license_number or "",
                employee_id=data.driver_employee_id or "",
                assigned_vehicle_id=data.driver_assigned_vehicle_id,
            )
        )
    elif data.role == UserRole.ADMIN:
        perms = data.admin_permissions if data.admin_permissions is not None else []
        db.add(
            AdminProfile(
                user_id=user.user_id,
                department=data.admin_department or "",
                permissions=json.dumps(perms),
            )
        )

    db.commit()
    db.refresh(user)
    pair = _issue_tokens(db, user)
    db.commit()
    return pair


def login(db: Session, email: str, password: str) -> TokenPair:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only active accounts can sign in",
        )

    user.last_login = datetime.now(UTC)
    pair = _issue_tokens(db, user)
    db.commit()
    return pair


def refresh_session(db: Session, refresh_token: str) -> TokenPair:
    try:
        payload = decode_token(refresh_token)
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    jti = payload.get("jti")
    user_id = payload.get("sub")
    if not jti or not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    row = db.scalar(select(RefreshToken).where(RefreshToken.jti == jti))
    if row is None or row.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked or unknown")
    exp = row.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=UTC)
    if exp < datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    user = db.get(User, user_id)
    if user is None or user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not active",
        )

    row.revoked_at = datetime.now(UTC)
    pair = _issue_tokens(db, user)
    db.commit()
    return pair


def logout(db: Session, refresh_token: str) -> None:
    try:
        payload = decode_token(refresh_token)
    except jwt.PyJWTError:
        return
    if payload.get("type") != "refresh":
        return
    jti = payload.get("jti")
    if not jti:
        return
    row = db.scalar(select(RefreshToken).where(RefreshToken.jti == jti))
    if row and row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        db.commit()
