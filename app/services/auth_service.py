from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
import logging

import jwt
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    create_password_reset_token,
    decode_token,
    normalize_email,
    hash_password,
    verify_password,
)
from app.models.enums import UserRole, UserStatus
from app.models.profile import CommuterProfile
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import RegisterRequest, TokenPair
from app.services.email_service import EmailService


logger = logging.getLogger(__name__)


def _issue_tokens(db: Session, user: User) -> TokenPair:
    jti = str(uuid.uuid4())
    expires_at = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    row = RefreshToken(user_id=user.user_id, jti=jti, expires_at=expires_at)
    db.add(row)
    db.flush()
    access = create_access_token(user.user_id, role=user.role.value)
    refresh = create_refresh_token(user.user_id, jti)
    return TokenPair(access_token=access, refresh_token=refresh, token_type="bearer")


def register(db: Session, data: RegisterRequest) -> TokenPair:
    email = normalize_email(str(data.email))
    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        full_name=email.split("@", maxsplit=1)[0],
        email=email,
        password_hash=hash_password(data.password),
        phone_number="N/A",
        role=UserRole.COMMUTER,
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    db.flush()

    db.add(
        CommuterProfile(
            user_id=user.user_id,
            preferred_route_id=None,
            notes=None,
        )
    )

    db.commit()
    db.refresh(user)
    pair = _issue_tokens(db, user)
    db.commit()
    logger.info("User registered: %s — sending welcome email", user.email)
    try:
        EmailService.send_welcome_email(user.email, user.full_name)
        logger.info("Welcome email queued for %s", user.email)
    except Exception:
        logger.exception("Failed to send welcome email for %s", user.email)
    return pair


def login(db: Session, email: str, password: str) -> TokenPair:
    normalized_email = normalize_email(email)
    user = db.scalar(select(User).where(User.email == normalized_email))
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


def forgot_password(db: Session, email: str) -> tuple[str, datetime]:
    normalized_email = normalize_email(email)
    user = db.scalar(select(User).where(User.email == normalized_email))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    reset_token = create_password_reset_token(user.user_id)
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)
    logger.info("Password reset requested for %s; sending reset email", user.email)
    EmailService.send_password_reset_email(user.email, reset_token, expires_at)
    logger.info("Password reset email flow completed for %s", user.email)
    return reset_token, expires_at


def reset_password(db: Session, reset_token: str, new_password: str) -> None:
    try:
        payload = decode_token(reset_token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired reset token")

    if payload.get("type") != "password_reset":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid reset token")

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.password_hash = hash_password(new_password)
    for row in user.refresh_tokens:
        if row.revoked_at is None:
            row.revoked_at = datetime.now(UTC)
    db.commit()
