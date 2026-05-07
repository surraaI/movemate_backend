from pydantic import BaseModel, ConfigDict, EmailStr, Field
from typing import Optional


# 🔹 Dashboard
class DashboardStats(BaseModel):
    total_users: int
    total_buses: int
    active_routes: int


# 🔹 System health
class SystemHealth(BaseModel):
    status: str
    message: str


# 🔹 Assignment
class AssignBusToRouteRequest(BaseModel):
    bus_id: str
    route_id: str


# 🔹 Notification
class NotificationCreate(BaseModel):
    message: str
    route_id: Optional[str] = None


# 🔹 Analytics
class DemandAnalytics(BaseModel):
    top_routes: list
    peak_hours: list
    popular_stops: list


class AdvancedMetrics(BaseModel):
    active_buses: int
    offline_buses: int
    average_delay_seconds: float
    tickets_last_hour: int
    bus_utilization: float


class DriverCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(alias="fullName", min_length=1, max_length=255)
    phone_number: str = Field(alias="phoneNumber", min_length=5, max_length=32)
    license_number: str = Field(alias="licenseNumber", min_length=1, max_length=64)
    employee_id: str = Field(alias="employeeId", min_length=1, max_length=64)
    assigned_vehicle_id: str | None = Field(default=None, alias="assignedVehicleId")


class AdminCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(alias="fullName", min_length=1, max_length=255)
    phone_number: str = Field(alias="phoneNumber", min_length=5, max_length=32)
    department: str = Field(min_length=1, max_length=128)
    permissions: list[str] = Field(default_factory=list)


class UserCreatedResponse(BaseModel):
    user_id: str = Field(serialization_alias="userId")
    role: str
    email: EmailStr