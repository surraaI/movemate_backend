import json
import logging
import secrets
import string
from datetime import datetime, timedelta
from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session, joinedload

from app.models.event import Event
from app.models.gps_tracking import ActiveTrip, BusCurrentLocation, BusLocationHistory, CommuterTripLocation
from app.models.user import User
from app.models.bus import Bus
from app.models.route import Route
from app.models.location import Location
from app.models.ticket import Ticket
from app.models.eta_prediction import ETAPrediction
from app.models.notification import Notification
from app.models.payment import Payment
from app.models.enums import UserRole, UserStatus, RouteStatus
from app.models.profile import AdminProfile, CommuterProfile, DriverProfile
from app.models.refresh_token import RefreshToken
from app.core.security import hash_password, normalize_email
from app.services.email_service import EmailService


logger = logging.getLogger(__name__)


class AdminService:
    @staticmethod
    def _generate_temporary_password(length: int = 12) -> str:
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))

    @staticmethod
    def list_users_for_admin(db: Session) -> list[User]:
        return (
            db.query(User)
            .options(
                joinedload(User.commuter_profile),
                joinedload(User.driver_profile),
                joinedload(User.admin_profile),
            )
            .order_by(User.created_at.desc())
            .all()
        )

    @staticmethod
    def _normalize_permissions(permissions: list[str]) -> list[str]:
        values = {permission.strip() for permission in permissions if permission and permission.strip()}
        return sorted(values)

    @staticmethod
    def _infer_password_flow(user: User) -> str:
        if user.role == UserRole.SUPERADMIN:
            return "seed_superadmin"
        if user.role == UserRole.COMMUTER:
            return "self_register"
        if user.role == UserRole.DRIVER:
            return "admin_create_driver"
        if user.role == UserRole.ADMIN:
            return "admin_create_admin"
        return "unknown"

    @staticmethod
    def lookup_user_by_email(db: Session, email: str) -> dict:
        normalized_email = normalize_email(email)
        user = db.query(User).filter(User.email == normalized_email).first()

        if user is None:
            return {
                "email": normalized_email,
                "found": False,
                "user_id": None,
                "role": None,
                "status": None,
                "created_at": None,
                "last_login": None,
                "password_flow": None,
            }

        created_at = user.created_at.isoformat() if user.created_at else None
        last_login = user.last_login.isoformat() if user.last_login else None
        return {
            "email": user.email,
            "found": True,
            "user_id": user.user_id,
            "role": user.role.value,
            "status": user.status.value,
            "created_at": created_at,
            "last_login": last_login,
            "password_flow": AdminService._infer_password_flow(user),
        }

    # 🔹 Dashboard stats
    @staticmethod
    def get_dashboard_stats(db):
        return {
            "total_users": db.query(User).count(),
            "total_buses": db.query(Bus).count(),
            # compare against the RouteStatus enum value
            "active_routes": db.query(Route).filter(Route.status == RouteStatus.ACTIVE).count(),
        }

    # 🔹 Change user status
    @staticmethod
    def change_user_status(db, user_id: str, action: str):
        user = db.query(User).filter(User.user_id == user_id).first()

        if not user:
            return None

        if action == "activate":
            user.status = UserStatus.ACTIVE
        elif action == "deactivate":
            user.status = UserStatus.INACTIVE
        elif action == "suspend":
            user.status = UserStatus.SUSPENDED
        else:
            return None

        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def delete_user(db: Session, user_id: str, *, acting_user: User | None = None) -> User | None:
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            return None

        if user.role == UserRole.SUPERADMIN and (acting_user is None or acting_user.role != UserRole.SUPERADMIN):
            raise ValueError("Superadmin accounts can only be deleted by another superadmin")

        try:
            AdminService._hard_delete_user_records(db, user)
            db.commit()
        except Exception:
            db.rollback()
            raise
        return user
    
     # -------------------------
    # assign bus to route
    # -------------------------
    @staticmethod
    def assign_bus_to_route(db, bus_id: str, route_id: str):
        bus = db.query(Bus).filter(Bus.bus_id == bus_id).first()
        if not bus:
            return None, "Bus not found"

        # Route model uses `id` as the primary key
        route = db.query(Route).filter(Route.id == route_id).first()
        if not route:
            return None, "Route not found"

        if route.status != "ACTIVE":
            return None, "Cannot assign to inactive route"

        bus.route_id = route.id   # IMPORTANT FIX

        db.commit()
        db.refresh(bus)

        return bus, None

    # -------------------------
    # route assignments
    # -------------------------
    @staticmethod
    def get_route_assignments(db):
        routes = db.query(Route).filter(Route.is_deleted == False).all()

        result = []

        for route in routes:
            # buses reference route.id in the Bus.route_id foreign key
            buses = db.query(Bus).filter(Bus.route_id == route.id).all()

            result.append({
                "route_id": route.id,
                "route_code": route.route_code,
                "route_name": route.route_name,
                "status": route.status,
                "buses": [{"bus_id": b.bus_id} for b in buses]
            })

        return result
    
    
    


    # 🔹 Real-time buses
    @staticmethod
    def get_live_buses(db):
        subquery = (
            db.query(
                Location.bus_id,
                func.max(Location.timestamp).label("latest_time")
            )
            .group_by(Location.bus_id)
            .subquery()
        )

        results = (
            db.query(Location, Bus)
            .join(Bus, Bus.bus_id == Location.bus_id)
            .join(subquery,
                  (Location.bus_id == subquery.c.bus_id) &
                  (Location.timestamp == subquery.c.latest_time))
            .all()
        )

        buses = []

        for loc, bus in results:
            status = "ACTIVE" if loc.timestamp >= datetime.utcnow() - timedelta(minutes=2) else "OFFLINE"

            buses.append({
                "bus_id": bus.bus_id,
                "route_id": bus.route_id,
                "latitude": loc.latitude,
                "longitude": loc.longitude,
                "status": status,
                "last_update": loc.timestamp
            })

        return buses

    # -------------------------
    # update user by admin
    # -------------------------
    @staticmethod
    def update_user(db: Session, user_id: str, data) -> User | None:
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            return None

        if getattr(data, "full_name", None) is not None:
            user.full_name = data.full_name
        if getattr(data, "phone_number", None) is not None:
            user.phone_number = data.phone_number

        if user.role == UserRole.COMMUTER and user.commuter_profile:
            if getattr(data, "commuter_preferred_route_id", None) is not None:
                user.commuter_profile.preferred_route_id = data.commuter_preferred_route_id
            if getattr(data, "commuter_notes", None) is not None:
                user.commuter_profile.notes = data.commuter_notes
        elif user.role == UserRole.DRIVER and user.driver_profile:
            if getattr(data, "driver_license_number", None) is not None:
                user.driver_profile.license_number = data.driver_license_number
            if getattr(data, "driver_employee_id", None) is not None:
                user.driver_profile.employee_id = data.driver_employee_id
            if getattr(data, "driver_assigned_vehicle_id", None) is not None:
                user.driver_profile.assigned_vehicle_id = data.driver_assigned_vehicle_id
        elif user.role == UserRole.ADMIN and user.admin_profile:
            if getattr(data, "admin_department", None) is not None:
                user.admin_profile.department = data.admin_department
            if getattr(data, "admin_permissions", None) is not None:
                user.admin_profile.permissions = json.dumps(data.admin_permissions)

        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    # -------------------------
    # hard delete user
    # -------------------------
    @staticmethod
    def hard_delete_user(db: Session, user_id: str) -> bool:
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            return False

        try:
            AdminService._hard_delete_user_records(db, user)
            db.commit()
            return True
        except Exception:
            db.rollback()
            return False

    @staticmethod
    def _hard_delete_user_records(db: Session, user: User) -> None:
        user_id = user.user_id

        db.query(RefreshToken).filter(RefreshToken.user_id == user_id).delete(synchronize_session=False)
        db.query(Notification).filter(Notification.user_id == user_id).delete(synchronize_session=False)
        db.query(Payment).filter(Payment.user_id == user_id).delete(synchronize_session=False)
        db.query(Ticket).filter(Ticket.user_id == user_id).delete(synchronize_session=False)
        db.query(Event).filter(Event.user_id == user_id).delete(synchronize_session=False)
        db.query(CommuterTripLocation).filter(CommuterTripLocation.user_id == user_id).delete(synchronize_session=False)
        trip_ids = select(ActiveTrip.trip_id).where(ActiveTrip.driver_id == user_id)
        db.query(BusCurrentLocation).filter(BusCurrentLocation.trip_id.in_(trip_ids)).delete(synchronize_session=False)
        db.query(BusLocationHistory).filter(BusLocationHistory.trip_id.in_(trip_ids)).delete(synchronize_session=False)
        db.query(ActiveTrip).filter(ActiveTrip.driver_id == user_id).delete(synchronize_session=False)
        db.query(AdminProfile).filter(AdminProfile.user_id == user_id).delete(synchronize_session=False)
        db.query(DriverProfile).filter(DriverProfile.user_id == user_id).delete(synchronize_session=False)
        db.query(CommuterProfile).filter(CommuterProfile.user_id == user_id).delete(synchronize_session=False)

        db.delete(user)

    # 🔹 Demand analytics
    @staticmethod
    def demand_analytics(db):
        # Top routes by ticket count
        raw_routes = (
            db.query(Ticket.route_id, func.count(Ticket.id).label("cnt"))
            .group_by(Ticket.route_id)
            .order_by(func.count(Ticket.id).desc())
            .all()
        )

        top_routes = [
            {"route_id": r[0], "count": int(r[1])} for r in raw_routes
        ]

        # Peak hours (hour of day)
        raw_hours = (
            db.query(
                extract("hour", Ticket.created_at).label("hour"),
                func.count(Ticket.id).label("cnt")
            )
            .group_by("hour")
            .order_by(func.count(Ticket.id).desc())
            .all()
        )

        peak_hours = [{"hour": int(h[0]), "count": int(h[1])} for h in raw_hours]

        # Ticket model currently does not store origin_stop_id — return empty for now
        popular_stops = []

        return {
            "top_routes": top_routes[:5],
            "peak_hours": peak_hours[:5],
            "popular_stops": popular_stops
        }
    # 🔹 Advanced metrics
    @staticmethod
    def advanced_metrics(db):
        now = datetime.utcnow()
        last_hour = now - timedelta(hours=1)

        active_buses = (
            db.query(Location.bus_id)
            .filter(Location.timestamp >= last_hour)
            .distinct()
            .count()
        )

        total_buses = db.query(Location.bus_id).distinct().count()
        offline_buses = total_buses - active_buses

        eta_records = db.query(ETAPrediction).all()

        total_delay = 0
        count = 0

        for r in eta_records:
            if r.actual_time and r.predicted_time:
                total_delay += (r.actual_time - r.predicted_time).total_seconds()
                count += 1

        avg_delay = total_delay / count if count else 0

        tickets_last_hour = (
            db.query(Ticket)
            .filter(Ticket.created_at >= last_hour)
            .count()
        )

        utilization = tickets_last_hour / total_buses if total_buses else 0

        return {
            "active_buses": active_buses,
            "offline_buses": offline_buses,
            "average_delay_seconds": avg_delay,
            "tickets_last_hour": tickets_last_hour,
            "bus_utilization": utilization
        }

    

    # 🔹 System health
    @staticmethod
    def system_health():
        return {
            "status": "OK",
            "message": "System running normally"
        }

    @staticmethod
    def create_driver(
        db,
        *,
        email: str,
        password: str,
        full_name: str,
        phone_number: str,
        license_number: str,
        employee_id: str,
        assigned_vehicle_id: str | None,
    ) -> tuple[User, str, bool]:
        normalized_email = normalize_email(email)
        existing = db.query(User).filter(User.email == normalized_email).first()
        if existing:
            raise ValueError("Email already registered")

        temporary_password = AdminService._generate_temporary_password()
        logger.info("Creating driver account for %s; temporary password generated and will be emailed", normalized_email)

        user = User(
            full_name=full_name.strip(),
            email=normalized_email,
            password_hash=hash_password(temporary_password),
            phone_number=phone_number.strip(),
            role=UserRole.DRIVER,
            status=UserStatus.ACTIVE,
        )
        db.add(user)
        db.flush()

        db.add(
            DriverProfile(
                user_id=user.user_id,
                license_number=license_number.strip(),
                employee_id=employee_id.strip(),
                assigned_vehicle_id=assigned_vehicle_id.strip() if assigned_vehicle_id else None,
            )
        )
        db.commit()
        db.refresh(user)
        email_sent = False
        try:
            email_sent = EmailService.send_driver_temporary_password_email(user.email, temporary_password)
        except Exception:
            logger.exception("Failed to send driver onboarding email for %s", user.email)
        logger.info("Driver onboarding email flow completed for %s", user.email)
        return user, temporary_password, email_sent

    @staticmethod
    def create_admin(
        db,
        *,
        email: str,
        password: str,
        full_name: str,
        phone_number: str,
        department: str,
        permissions: list[str],
    ) -> User:
        normalized_email = normalize_email(email)
        existing = db.query(User).filter(User.email == normalized_email).first()
        if existing:
            raise ValueError("Email already registered")

        normalized_permissions = AdminService._normalize_permissions(permissions)
        user = User(
            full_name=full_name.strip(),
            email=normalized_email,
            password_hash=hash_password(password),
            phone_number=phone_number.strip(),
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
        )
        db.add(user)
        db.flush()

        db.add(
            AdminProfile(
                user_id=user.user_id,
                department=department.strip(),
                permissions=json.dumps(normalized_permissions),
            )
        )
        db.commit()
        db.refresh(user)
        return user