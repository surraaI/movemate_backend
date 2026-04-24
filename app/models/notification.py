import uuid
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, String, Text

from app.db.base import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.user_id"))
    type = Column(String, nullable=False)
    title = Column(Text, nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String, default="SENT")  # SENT, FAILED, READ
    created_at = Column(DateTime, default=datetime.utcnow)
    read_at = Column(DateTime, nullable=True)