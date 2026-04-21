from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StopCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(min_length=1, max_length=255)
    latitude: float
    longitude: float


class StopOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, serialize_by_alias=True)

    id: str
    name: str
    latitude: float
    longitude: float
    created_at: datetime = Field(serialization_alias="createdAt")
