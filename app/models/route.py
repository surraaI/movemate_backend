from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import RouteStatus

if TYPE_CHECKING:
    from app.models.route_stop import RouteStop


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    route_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    route_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[RouteStatus] = mapped_column(
        SAEnum(RouteStatus, native_enum=False, length=32), nullable=False, default=RouteStatus.ACTIVE
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    route_stops: Mapped[list[RouteStop]] = relationship(
        "RouteStop",
        back_populates="route",
        cascade="all, delete-orphan",
        order_by="RouteStop.sequence",
    )
