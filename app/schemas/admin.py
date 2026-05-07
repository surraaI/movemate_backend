from pydantic import BaseModel
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