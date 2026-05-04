from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class NotificationCreate(BaseModel):
    user_id: UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class NotificationCreate(BaseModel):
    user_id: str
    title: str
    message: str
    type: str

class NotificationOut(BaseModel):
    id: UUID
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    message: str
    status: str
    created_at: datetime

    class Config:
        orm_mode = True
