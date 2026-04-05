from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenPair
from app.services import auth_service

router = APIRouter()


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenPair:
    return auth_service.register(db, body)


@router.post("/login", response_model=TokenPair)
def login(
    body: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenPair:
    return auth_service.login(db, str(body.email), body.password)


@router.post("/refresh", response_model=TokenPair)
def refresh(
    body: RefreshRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenPair:
    return auth_service.refresh_session(db, body.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    body: RefreshRequest,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    auth_service.logout(db, body.refresh_token)
