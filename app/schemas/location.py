from datetime import datetime

from pydantic import BaseModel


class LocationCreate(BaseModel):
    bus_id: str
    latitude: float
    longitude: float


class LocationOut(BaseModel):
    location_id: str
    bus_id: str
    latitude: float
    longitude: float
    timestamp: datetime

    class Config:
        from_attributes = True