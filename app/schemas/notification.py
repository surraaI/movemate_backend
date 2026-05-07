from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class NotificationCreate(BaseModel):
    user_id: UUID
    title: str
    message: str
    type: str


class NotificationOut(BaseModel):
    id: UUID
    title: str
    message: str
    status: str
    created_at: datetime

    model_config = {
        "from_attributes": True
    }