from typing import Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models.enums import UserRole


class TokenPair(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    access_token: str = Field(serialization_alias="accessToken")
    refresh_token: str = Field(serialization_alias="refreshToken")
    token_type: str = Field(default="bearer", serialization_alias="tokenType")


class LoginRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RefreshRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    refresh_token: str = Field(alias="refreshToken", min_length=1)


class RegisterRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    full_name: str = Field(alias="fullName", min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    phone_number: str = Field(alias="phoneNumber", min_length=5, max_length=32)
    role: UserRole

    commuter_preferred_route_id: str | None = Field(default=None, alias="commuterPreferredRouteId")
    driver_license_number: str | None = Field(default=None, alias="driverLicenseNumber")
    driver_employee_id: str | None = Field(default=None, alias="driverEmployeeId")
    driver_assigned_vehicle_id: str | None = Field(default=None, alias="driverAssignedVehicleId")
    admin_department: str | None = Field(default=None, alias="adminDepartment")
    admin_permissions: list[str] | None = Field(default=None, alias="adminPermissions")

    @field_validator("phone_number")
    @classmethod
    def strip_phone(cls, v: str) -> str:
        return v.strip()

    @model_validator(mode="after")
    def validate_role_fields(self) -> Self:
        if self.role == UserRole.DRIVER:
            if not self.driver_license_number or not self.driver_employee_id:
                raise ValueError("driverLicenseNumber and driverEmployeeId are required for DRIVER role")
        if self.role == UserRole.ADMIN:
            if not self.admin_department:
                raise ValueError("adminDepartment is required for ADMIN role")
        return self
