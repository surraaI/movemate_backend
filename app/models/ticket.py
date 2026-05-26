from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.event import Event, EventType
from app.services.event_service import EventService

if TYPE_CHECKING:
    from app.models.user import User
    from sqlalchemy.orm import Session


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.user_id"), nullable=False, index=True
    )
    route_id: Mapped[str] = mapped_column(String(36), nullable=False)
    origin_stop_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    fare: Mapped[int] = mapped_column(Integer, nullable=False)
    qr_code: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    server_default=func.now(),
    nullable=False
)

    user: Mapped[User] = relationship("User")

    @property
    def expires_at(self) -> datetime:
        return self.created_at + timedelta(hours=24)

    @property
    def is_expired(self) -> bool:
        return datetime.now(UTC) >= self.expires_at

    @staticmethod
    def scan(
        db: "Session",
        ticket: "Ticket",
        bus_id: str,
        stop_id: str,
        direction: str,
        timestamp: datetime | None = None,
    ) -> Event:
        """Record a ticket scan as a demand signal for the rerouting pipeline."""

        scanned_at = timestamp or datetime.now(UTC)
        event = EventService.write_event(
            db,
            event_type=EventType.TICKET_SCANNED,
            user_id=ticket.user_id,
            route_id=ticket.route_id,
            metadata={
                "stop_id": stop_id,
                "bus_id": bus_id,
                "route_id": ticket.route_id,
                "timestamp": scanned_at.isoformat(),
                "direction": direction,
            },
            occurred_at=scanned_at,
        )
        db.commit()
        return event
