from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import ChangePasswordRequest, UserOut, UserUpdate
from app.services import user_service

router = APIRouter()


@router.get("/me", response_model=UserOut)
def read_me(
    current: Annotated[User, Depends(get_current_user)],
) -> UserOut:
    return user_service.get_me(current)


@router.put("/me", response_model=UserOut)
def update_me(
    body: UserUpdate,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
) -> UserOut:
    return user_service.update_me(db, current, body)


@router.put("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    body: ChangePasswordRequest,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
) -> None:
    user_service.change_password(db, current, body)


@router.delete("/deactivate", status_code=status.HTTP_204_NO_CONTENT)
def deactivate(
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
) -> None:
    user_service.deactivate_account(db, current)
