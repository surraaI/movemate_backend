from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import require_roles, get_current_user
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.location import LocationCreate, LocationOut
from app.services.location_service import LocationService

router = APIRouter()


@router.post("", response_model=LocationOut, status_code=status.HTTP_201_CREATED)
def create_location(
    payload: LocationCreate,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
):
    return LocationService(db).create_location(payload)


@router.get("", response_model=list[LocationOut])
def get_locations(
    db: Annotated[Session, Depends(get_db)],
):
    return LocationService(db).get_locations()