from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class CommuterProfile(Base):
    __tablename__ = "commuter_profiles"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True
    )
    preferred_route_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[User] = relationship("User", back_populates="commuter_profile")


class DriverProfile(Base):
    __tablename__ = "driver_profiles"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True
    )
    license_number: Mapped[str] = mapped_column(String(64), nullable=False)
    employee_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    assigned_vehicle_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    user: Mapped[User] = relationship("User", back_populates="driver_profile")


class AdminProfile(Base):
    __tablename__ = "admin_profiles"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True
    )
    department: Mapped[str] = mapped_column(String(128), nullable=False)
    permissions: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    user: Mapped[User] = relationship("User", back_populates="admin_profile")
