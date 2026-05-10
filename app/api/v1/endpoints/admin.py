from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_roles, get_current_user
from app.db.session import get_db
from app.models.enums import UserRole
from app.services.admin_service import AdminService
from app.schemas.admin import (
    DashboardStats,
    SystemHealth,
    AssignBusToRouteRequest,
    NotificationCreate,
    AdminCreateRequest,
    DriverCreateRequest,
    UserCreatedResponse,
)
from app.models.user import User

router = APIRouter(tags=["Admin Dashboard"])


# 🔹 Dashboard
@router.get("/dashboard", response_model=DashboardStats)
def dashboard(
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN)),

):
    return AdminService.get_dashboard_stats(db)


# 🔹 User management
@router.put("/users/{user_id}")
def manage_user(
    user_id: str,
    action: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN)),

):
    user = AdminService.change_user_status(db, user_id, action)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": "User updated successfully"}


# 🔹 Assign bus → route
@router.post("/assignments/bus-route")
def assign_bus(
    data: AssignBusToRouteRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN)),

):
    result, error = AdminService.assign_bus_to_route(db, data.bus_id, data.route_id)

    if error:
        raise HTTPException(status_code=400, detail=error)

    return {"message": "Bus assigned successfully"}


# 🔹 View assignments
@router.get("/assignments/routes")
def route_assignments(
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN)),

):
    return AdminService.get_route_assignments(db)


# 🔹 Live buses
@router.get("/buses/live")
def live_buses(
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN)),

):
    return AdminService.get_live_buses(db)


# 🔹 Demand analytics
@router.get("/analytics/demand")
def demand(
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN)),

):
    return AdminService.demand_analytics(db)


# 🔹 Advanced metrics
@router.get("/analytics/advanced")
def advanced(
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN)),

):
    return AdminService.advanced_metrics(db)


# 🔹 Notifications
@router.post("/notifications")
def send_notification(
    data: NotificationCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN)),

):
    return AdminService.create_notification(db, data.message, data.route_id)


@router.get("/notifications")
def get_notifications(
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN)),

):
    return AdminService.get_notifications(db)


# 🔹 System health
@router.get("/health", response_model=SystemHealth)
def health(
    _user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN)),

):
    return AdminService.system_health()


# 🔹 Superadmin: create admins
@router.post("/users/admin", response_model=UserCreatedResponse, status_code=status.HTTP_201_CREATED)
def create_admin_user(
    body: AdminCreateRequest,
    db: Session = Depends(get_db),
        _user: User = Depends(require_roles(UserRole.SUPERADMIN)),

) -> UserCreatedResponse:
    try:
        user = AdminService.create_admin(
            db,
            email=str(body.email),
            password=body.password,
            full_name=body.full_name,
            phone_number=body.phone_number,
            department=body.department,
            permissions=body.permissions,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return UserCreatedResponse(user_id=user.user_id, role=user.role.value, email=user.email)


# 🔹 Admin/Superadmin: create drivers
@router.post("/users/driver", response_model=UserCreatedResponse, status_code=status.HTTP_201_CREATED)
def create_driver_user(
    body: DriverCreateRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN)),

) -> UserCreatedResponse:
    try:
        user = AdminService.create_driver(
            db,
            email=str(body.email),
            password=body.password,
            full_name=body.full_name,
            phone_number=body.phone_number,
            license_number=body.license_number,
            employee_id=body.employee_id,
            assigned_vehicle_id=body.assigned_vehicle_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return UserCreatedResponse(user_id=user.user_id, role=user.role.value, email=user.email)