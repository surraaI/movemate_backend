from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from app.db.base import Base
from datetime import datetime
import uuid


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"))
    route_id = Column(String)
    fare = Column(Integer)
    qr_code = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)