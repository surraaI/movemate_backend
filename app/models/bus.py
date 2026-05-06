from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.route import Route
    from app.models.location import Location


class Bus(Base):
    __tablename__ = "buses"

    bus_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    route_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("routes.route_id"), nullable=True
    )

    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")

    # 🔹 Relationships
    route: Mapped[Route | None] = relationship("Route", back_populates="buses")
    locations: Mapped[list[Location]] = relationship(
        "Location", back_populates="bus", cascade="all, delete-orphan"
    )