from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RouteStopAddRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    stop_id: str = Field(alias="stopId")
    sequence: int = Field(ge=1)


class RouteStopReorderItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    stop_id: str = Field(alias="stopId")
    sequence: int = Field(ge=1)


class RouteStopReorderRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    stops: list[RouteStopReorderItem] = Field(min_length=1)

    @field_validator("stops")
    @classmethod
    def validate_unique_stop_ids(cls, stops: list[RouteStopReorderItem]) -> list[RouteStopReorderItem]:
        ids = [item.stop_id for item in stops]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate stop IDs are not allowed in reorder payload")
        return stops


class RouteStopOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, serialize_by_alias=True)

    stop_id: str = Field(serialization_alias="stopId")
    stop_name: str = Field(serialization_alias="stopName")
    latitude: float
    longitude: float
    sequence: int
    created_at: datetime = Field(serialization_alias="createdAt")
