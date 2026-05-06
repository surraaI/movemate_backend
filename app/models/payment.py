from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from app.db.base import Base
from datetime import datetime
import uuid


class Payment(Base):
    __tablename__ = "payments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tx_ref = Column(String, unique=True, index=True)
    user_id = Column(String, ForeignKey("users.id"))
    route_id = Column(String)
    amount = Column(Integer)
    status = Column(String, default="pending")  # pending, success, failed
    created_at = Column(DateTime, default=datetime.utcnow)