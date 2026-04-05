import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import UserRole, UserStatus


class CommuterProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, serialize_by_alias=True)

    preferred_route_id: str | None = Field(default=None, serialization_alias="preferredRouteId")
    notes: str | None = None


class DriverProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, serialize_by_alias=True)

    license_number: str = Field(serialization_alias="licenseNumber")
    employee_id: str = Field(serialization_alias="employeeId")
    assigned_vehicle_id: str | None = Field(default=None, serialization_alias="assignedVehicleId")


class AdminProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, serialize_by_alias=True)

    department: str
    permissions: list[str]

    @field_validator("permissions", mode="before")
    @classmethod
    def parse_permissions(cls, v: object) -> list[str]:
        if isinstance(v, list):
            return [str(x) for x in v]
        if isinstance(v, str):
            try:
                data = json.loads(v)
                if isinstance(data, list):
                    return [str(x) for x in data]
            except json.JSONDecodeError:
                pass
            return []
        return []


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, serialize_by_alias=True)

    user_id: str = Field(serialization_alias="userId")
    full_name: str = Field(serialization_alias="fullName")
    email: EmailStr
    phone_number: str = Field(serialization_alias="phoneNumber")
    role: UserRole
    status: UserStatus
    created_at: datetime = Field(serialization_alias="createdAt")
    last_login: datetime | None = Field(default=None, serialization_alias="lastLogin")
    commuter_profile: CommuterProfileOut | None = Field(default=None, serialization_alias="commuterProfile")
    driver_profile: DriverProfileOut | None = Field(default=None, serialization_alias="driverProfile")
    admin_profile: AdminProfileOut | None = Field(default=None, serialization_alias="adminProfile")


class UserUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    full_name: str | None = Field(default=None, alias="fullName", min_length=1, max_length=255)
    phone_number: str | None = Field(default=None, alias="phoneNumber", min_length=5, max_length=32)
    commuter_preferred_route_id: str | None = Field(default=None, alias="commuterPreferredRouteId")
    commuter_notes: str | None = Field(default=None, alias="commuterNotes")
    driver_license_number: str | None = Field(default=None, alias="driverLicenseNumber")
    driver_employee_id: str | None = Field(default=None, alias="driverEmployeeId")
    driver_assigned_vehicle_id: str | None = Field(default=None, alias="driverAssignedVehicleId")
    admin_department: str | None = Field(default=None, alias="adminDepartment")
    admin_permissions: list[str] | None = Field(default=None, alias="adminPermissions")


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    current_password: str = Field(alias="currentPassword", min_length=1, max_length=128)
    new_password: str = Field(alias="newPassword", min_length=8, max_length=128)
