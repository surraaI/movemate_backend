from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SAEnum, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import TripStatus

if TYPE_CHECKING:
    from app.models.route import Route
    from app.models.user import User


class ActiveTrip(Base):
    __tablename__ = "active_trips"

    trip_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    route_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("routes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    driver_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    vehicle_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[TripStatus] = mapped_column(
        SAEnum(TripStatus, native_enum=False, length=32), default=TripStatus.ACTIVE, nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    route: Mapped[Route] = relationship("Route")
    driver: Mapped[User] = relationship("User")
    current_location: Mapped[BusCurrentLocation | None] = relationship(
        "BusCurrentLocation", back_populates="trip", uselist=False, cascade="all, delete-orphan"
    )
    location_history: Mapped[list[BusLocationHistory]] = relationship(
        "BusLocationHistory", back_populates="trip", cascade="all, delete-orphan"
    )


class BusCurrentLocation(Base):
    __tablename__ = "bus_current_locations"
    __table_args__ = (
        UniqueConstraint("trip_id", name="uq_bus_current_locations_trip_id"),
        UniqueConstraint("vehicle_id", name="uq_bus_current_locations_vehicle_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    trip_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("active_trips.trip_id", ondelete="CASCADE"), nullable=False, index=True
    )
    route_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("routes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    vehicle_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    speed_kph: Mapped[float | None] = mapped_column(Float, nullable=True)
    heading_degrees: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gps_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    trip: Mapped[ActiveTrip] = relationship("ActiveTrip", back_populates="current_location")


class BusLocationHistory(Base):
    __tablename__ = "bus_location_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    trip_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("active_trips.trip_id", ondelete="CASCADE"), nullable=False, index=True
    )
    route_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("routes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    vehicle_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    speed_kph: Mapped[float | None] = mapped_column(Float, nullable=True)
    heading_degrees: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gps_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    trip: Mapped[ActiveTrip] = relationship("ActiveTrip", back_populates="location_history")
