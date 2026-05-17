import json
from datetime import datetime, timedelta
from sqlalchemy import func, extract

from app.models.user import User
from app.models.bus import Bus
from app.models.route import Route
from app.models.location import Location
from app.models.ticket import Ticket
from app.models.eta_prediction import ETAPrediction
from app.models.notification import Notification
from app.models.enums import UserRole, UserStatus
from app.models.profile import AdminProfile, DriverProfile
from app.core.security import hash_password


class AdminService:
    @staticmethod
    def _normalize_permissions(permissions: list[str]) -> list[str]:
        values = {permission.strip() for permission in permissions if permission and permission.strip()}
        return sorted(values)

    # 🔹 Dashboard stats
    @staticmethod
    def get_dashboard_stats(db):
        return {
            "total_users": db.query(User).count(),
            "total_buses": db.query(Bus).count(),
            "active_routes": db.query(Route).filter(Route.status == "ACTIVE").count(),
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
    
     # -------------------------
    # assign bus to route
    # -------------------------
    @staticmethod
    def assign_bus_to_route(db, bus_id: str, route_code: str):
        bus = db.query(Bus).filter(Bus.bus_id == bus_id).first()
        if not bus:
            return None, "Bus not found"

        route = db.query(Route).filter(Route.route_code == route_code).first()
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

    # 🔹 Demand analytics
    @staticmethod
    def demand_analytics(db):
        top_routes = (
            db.query(
                Ticket.route_id,
                func.count(Ticket.id).label("ticket_count")
            )
            .group_by(Ticket.route_id)
            .order_by(func.count(Ticket.id).desc())
            .all()
        )

        peak_hours = (
            db.query(
                extract("hour", Ticket.created_at).label("hour"),
                func.count(Ticket.id).label("ticket_count")
            )
            .group_by("hour")
            .order_by("hour")
            .all()
        )

        return {
            "top_routes": [
                {
                    "route_id": route_id,
                    "ticket_count": count
                }
                for route_id, count in top_routes
            ],
            "peak_hours": [
                {
                    "hour": int(hour) if hour is not None else 0,
                    "ticket_count": count
                }
                for hour, count in peak_hours
            ],
            "popular_stops": []
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
    ) -> User:
        existing = db.query(User).filter(User.email == email.lower()).first()
        if existing:
            raise ValueError("Email already registered")

        user = User(
            full_name=full_name.strip(),
            email=email.lower(),
            password_hash=hash_password(password),
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
        return user

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
        existing = db.query(User).filter(User.email == email.lower()).first()
        if existing:
            raise ValueError("Email already registered")

        normalized_permissions = AdminService._normalize_permissions(permissions)
        user = User(
            full_name=full_name.strip(),
            email=email.lower(),
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