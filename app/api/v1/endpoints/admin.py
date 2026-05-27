from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.services.admin_service import AdminService
from app.services.event_service import EventService
from app.schemas.admin import (
    DashboardStats,
    DriverCreatedResponse,
    SystemHealth,
    AssignBusToRouteRequest,
    RouteOccupancyOut,
    NotificationCreate,
    AdminCreateRequest,
    DriverCreateRequest,
    UserCreatedResponse,
    UserLookupResponse,
)
from app.schemas.user import UserUpdate, UserOut
from app.schemas.event import ActivityTrendOut
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


@router.get("/users/lookup", response_model=UserLookupResponse)
def lookup_user_by_email(
    email: str = Query(..., min_length=3),
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN)),
) -> UserLookupResponse:
    return UserLookupResponse(**AdminService.lookup_user_by_email(db, email))


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN)),
) -> None:
    try:
        deleted = AdminService.delete_user(db, user_id, acting_user=current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))

    if deleted is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    body: UserUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN)),
) -> UserOut:
    updated = AdminService.update_user(db, user_id, body)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserOut.model_validate(updated)


@router.delete("/users/{user_id}/hard", status_code=status.HTTP_204_NO_CONTENT)
def hard_delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.SUPERADMIN)),
) -> Response:
    ok = AdminService.hard_delete_user(db, user_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found or could not be deleted")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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


@router.get("/routes/{route_id}/occupancy", response_model=RouteOccupancyOut)
def route_occupancy(
    route_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN)),
) -> RouteOccupancyOut:
    from app.services.gps_tracking_service import GPSTrackingService

    return GPSTrackingService(db).get_route_bus_occupancy(route_id)


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


# 🔹 Activity trends (time-windowed analytics)
@router.get("/analytics/activity-trends", response_model=ActivityTrendOut)
def activity_trends(
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN)),
    days_back: int = Query(7, description="Number of days to look back (default: 7)"),
    granularity: str = Query("day", description="Aggregation granularity: 'hour', 'day', 'week'"),
):
    """
    Get activity trends over a time window.
    
    Query Parameters:
    - days_back: How many days back to analyze (default: 7)
    - granularity: 'hour', 'day', or 'week' (default: 'day')
    
    Returns aggregated event counts and metrics for the period.
    """
    if granularity not in ["hour", "day", "week"]:
        raise HTTPException(status_code=400, detail="Granularity must be 'hour', 'day', or 'week'")
    
    if days_back < 1 or days_back > 365:
        raise HTTPException(status_code=400, detail="days_back must be between 1 and 365")
    
    to_time = datetime.utcnow()
    from_time = to_time - timedelta(days=days_back)
    
    trends = EventService.get_activity_trends(db, from_time, to_time, granularity)
    
    return ActivityTrendOut(**trends)


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
@router.post("/users/driver", response_model=DriverCreatedResponse, status_code=status.HTTP_201_CREATED)
def create_driver_user(
    body: DriverCreateRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN)),
) -> DriverCreatedResponse:
    try:
        user, temporary_password, email_sent = AdminService.create_driver(
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
    return DriverCreatedResponse(
        user_id=user.user_id,
        role=user.role.value,
        email=user.email,
        temporary_password=temporary_password,
        email_sent=email_sent,
    )