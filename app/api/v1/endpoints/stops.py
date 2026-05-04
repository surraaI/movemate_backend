from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.stop import StopCreate, StopOut
from app.services.stop_service import StopService

router = APIRouter()


@router.post("", response_model=StopOut, status_code=status.HTTP_201_CREATED)
def create_stop(
    payload: StopCreate,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
) -> StopOut:
    return StopOut.model_validate(StopService(db).create_stop(payload))


@router.get("", response_model=list[StopOut])
def list_stops(
    db: Annotated[Session, Depends(get_db)],
) -> list[StopOut]:
    return [StopOut.model_validate(stop) for stop in StopService(db).list_stops()]


@router.get("/{stop_id}", response_model=StopOut)
def get_stop(
    stop_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> StopOut:
    return StopOut.model_validate(StopService(db).get_stop(stop_id))
