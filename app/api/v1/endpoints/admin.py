from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.admin_service import AdminService
from app.schemas.admin import (
    DashboardStats,
    SystemHealth,
    AssignBusToRouteRequest,
    NotificationCreate
)
from app.core.security import require_admin

router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])


# 🔹 Dashboard
@router.get("/dashboard", response_model=DashboardStats)
def dashboard(db: Session = Depends(get_db), admin=Depends(require_admin)):
    return AdminService.get_dashboard_stats(db)


# 🔹 User management
@router.put("/users/{user_id}")
def manage_user(user_id: str, action: str, db: Session = Depends(get_db), admin=Depends(require_admin)):
    user = AdminService.change_user_status(db, user_id, action)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": "User updated successfully"}


# 🔹 Assign bus → route
@router.post("/assignments/bus-route")
def assign_bus(data: AssignBusToRouteRequest, db: Session = Depends(get_db), admin=Depends(require_admin)):
    result, error = AdminService.assign_bus_to_route(db, data.bus_id, data.route_id)

    if error:
        raise HTTPException(status_code=400, detail=error)

    return {"message": "Bus assigned successfully"}


# 🔹 View assignments
@router.get("/assignments/routes")
def route_assignments(db: Session = Depends(get_db), admin=Depends(require_admin)):
    return AdminService.get_route_assignments(db)


# 🔹 Live buses
@router.get("/buses/live")
def live_buses(db: Session = Depends(get_db), admin=Depends(require_admin)):
    return AdminService.get_live_buses(db)


# 🔹 Demand analytics
@router.get("/analytics/demand")
def demand(db: Session = Depends(get_db), admin=Depends(require_admin)):
    return AdminService.demand_analytics(db)


# 🔹 Advanced metrics
@router.get("/analytics/advanced")
def advanced(db: Session = Depends(get_db), admin=Depends(require_admin)):
    return AdminService.advanced_metrics(db)


# 🔹 Notifications
@router.post("/notifications")
def send_notification(data: NotificationCreate, db: Session = Depends(get_db), admin=Depends(require_admin)):
    return AdminService.create_notification(db, data.message, data.route_id)


@router.get("/notifications")
def get_notifications(db: Session = Depends(get_db), admin=Depends(require_admin)):
    return AdminService.get_notifications(db)


# 🔹 System health
@router.get("/health", response_model=SystemHealth)
def health(admin=Depends(require_admin)):
    return AdminService.system_health()