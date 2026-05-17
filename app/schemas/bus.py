from pydantic import BaseModel
from typing import Optional


class BusCreate(BaseModel):
    bus_id: str
    route_id: Optional[str] = None
    status: str = "ACTIVE"


class BusUpdate(BaseModel):
    route_id: Optional[str] = None
    status: Optional[str] = None


class BusOut(BaseModel):
    bus_id: str
    route_id: Optional[str]
    status: str

    class Config:
        from_attributes = True