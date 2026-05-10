from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
if TYPE_CHECKING:
    from app.models.user import User


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    user_id = Column(
        String,
        ForeignKey("users.user_id"),
        nullable=False
    )

    type = Column(String, nullable=False)
    title = Column(Text, nullable=False)
    message = Column(Text, nullable=False)

    status = Column(String, default="SENT")

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    read_at = Column(DateTime(timezone=True), nullable=True)
