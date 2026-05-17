from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, func, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.user import User


class EventType:
    """Enum-like container for event types."""
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    TRIP_START = "trip_start"
    TRIP_END = "trip_end"
    PAYMENT_START = "payment_start"
    PAYMENT_SUCCESS = "payment_success"
    PAYMENT_FAILED = "payment_failed"
    TICKET_CREATED = "ticket_created"
    GPS_UPDATE = "gps_update"


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.user_id"), nullable=True, index=True
    )
    route_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    trip_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    event_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User | None] = relationship("User")
