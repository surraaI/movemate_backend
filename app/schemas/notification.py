from pydantic import BaseModel, ConfigDict
from datetime import datetime




class NotificationCreate(BaseModel):
    user_id: str
    title: str
    message: str
    type: str

class NotificationOut(BaseModel):
    id: str
    model_config = ConfigDict(from_attributes=True)
    title: str
    message: str
    created_at: datetime
