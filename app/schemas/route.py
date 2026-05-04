from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RouteStatus
from app.schemas.route_stop import RouteStopOut


class RouteCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    route_code: str = Field(alias="routeCode", min_length=1, max_length=64)
    route_name: str = Field(alias="routeName", min_length=1, max_length=255)


class RouteUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    route_name: str | None = Field(default=None, alias="routeName", min_length=1, max_length=255)


class RouteStatusUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: RouteStatus


class RouteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, serialize_by_alias=True)

    id: str
    route_code: str = Field(serialization_alias="routeCode")
    route_name: str = Field(serialization_alias="routeName")
    status: RouteStatus
    is_deleted: bool = Field(serialization_alias="isDeleted")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class RouteDetailOut(RouteOut):
    stops: list[RouteStopOut] = Field(default_factory=list)
