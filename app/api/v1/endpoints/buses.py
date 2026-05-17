from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.deps import require_roles, get_current_user
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.bus import BusCreate, BusOut, BusUpdate
from app.services.bus_service import BusService

router = APIRouter()


@router.post("", response_model=BusOut, status_code=status.HTTP_201_CREATED)
def create_bus(
    payload: BusCreate,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
):
    return BusService(db).create_bus(payload)


@router.get("", response_model=list[BusOut])
def get_buses(
    db: Annotated[Session, Depends(get_db)],
):
    return BusService(db).get_buses()


@router.get("/{bus_id}", response_model=BusOut)
def get_bus(
    bus_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    return BusService(db).get_bus(bus_id)


@router.patch("/{bus_id}", response_model=BusOut)
def update_bus(
    bus_id: str,
    payload: BusUpdate,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
):
    return BusService(db).update_bus(bus_id, payload)


@router.delete("/{bus_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bus(
    bus_id: str,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
):
    BusService(db).delete_bus(bus_id)

    return Response(status_code=status.HTTP_204_NO_CONTENT)