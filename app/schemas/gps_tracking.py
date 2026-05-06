from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import TripStatus


class TripStartRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    route_id: str = Field(alias="routeId", min_length=1, max_length=36)
    vehicle_id: str | None = Field(default=None, alias="vehicleId", min_length=1, max_length=64)
    started_at: datetime | None = Field(default=None, alias="startedAt")

    @field_validator("started_at")
    @classmethod
    def validate_started_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None:
            raise ValueError("startedAt must include timezone information")
        return value.astimezone(UTC)


class TripEndRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ended_at: datetime | None = Field(default=None, alias="endedAt")

    @field_validator("ended_at")
    @classmethod
    def validate_ended_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None:
            raise ValueError("endedAt must include timezone information")
        return value.astimezone(UTC)


class GPSUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    timestamp: datetime
    speed_kph: float | None = Field(default=None, alias="speedKph", ge=0.0, le=180.0)
    heading_degrees: int | None = Field(default=None, alias="headingDegrees", ge=0, le=359)
    accuracy_meters: float | None = Field(default=None, alias="accuracyMeters", ge=0.0, le=150.0)

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamp must include timezone information")
        return value.astimezone(UTC)

    @field_validator("latitude", "longitude")
    @classmethod
    def validate_non_zero_pairs(cls, value: float) -> float:
        return round(value, 6)


class GPSUpdateResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    trip_id: str = Field(serialization_alias="tripId")
    accepted: bool
    stored_at: datetime = Field(serialization_alias="storedAt")


class TripOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, serialize_by_alias=True)

    trip_id: str = Field(serialization_alias="tripId")
    route_id: str = Field(serialization_alias="routeId")
    driver_id: str = Field(serialization_alias="driverId")
    vehicle_id: str = Field(serialization_alias="vehicleId")
    status: TripStatus
    started_at: datetime = Field(serialization_alias="startedAt")
    ended_at: datetime | None = Field(default=None, serialization_alias="endedAt")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class BusLiveLocationOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    trip_id: str = Field(serialization_alias="tripId")
    route_id: str = Field(serialization_alias="routeId")
    vehicle_id: str = Field(serialization_alias="vehicleId")
    latitude: float
    longitude: float
    speed_kph: float | None = Field(default=None, serialization_alias="speedKph")
    heading_degrees: int | None = Field(default=None, serialization_alias="headingDegrees")
    gps_timestamp: datetime = Field(serialization_alias="gpsTimestamp")
    received_at: datetime = Field(serialization_alias="receivedAt")


class RouteFleetOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    route_id: str = Field(serialization_alias="routeId")
    active_buses: list[BusLiveLocationOut] = Field(default_factory=list, serialization_alias="activeBuses")


class AdminFleetOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    total_active_trips: int = Field(serialization_alias="totalActiveTrips")
    buses: list[BusLiveLocationOut]


class ETAPredictionOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    trip_id: str = Field(serialization_alias="tripId")
    route_id: str = Field(serialization_alias="routeId")
    destination_stop_id: str = Field(serialization_alias="destinationStopId")
    destination_stop_name: str = Field(serialization_alias="destinationStopName")
    remaining_distance_km: float = Field(serialization_alias="remainingDistanceKm")
    predicted_speed_kph: float = Field(serialization_alias="predictedSpeedKph")
    eta_minutes: int = Field(serialization_alias="etaMinutes")
    estimated_arrival: datetime = Field(serialization_alias="estimatedArrival")
