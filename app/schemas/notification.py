from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

class NotificationCreate(BaseModel):
    user_id: str
    title: str
    message: str
    type: str

class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    user_id: str
    title: str
    message: str
    status: str
    type: str
    created_at: datetime
    read_at: Optional[datetime] = None
