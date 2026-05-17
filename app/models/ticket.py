from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
if TYPE_CHECKING:
    from app.models.user import User


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
