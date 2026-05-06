from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime




class NotificationCreate(BaseModel):
    user_id: str
    title: str
    message: str
    type: str

class NotificationOut(BaseModel):
    id: UUID
    model_config = ConfigDict(from_attributes=True)
    title: str
    message: str
    created_at: datetime

    class Config:
        orm_mode = True
