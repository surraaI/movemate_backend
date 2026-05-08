import uuid
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.db.base import Base


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