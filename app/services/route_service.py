from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.route import Route
from app.repositories.route_repository import RouteRepository
from app.repositories.route_stop_repository import RouteStopRepository
from app.schemas.route import RouteCreate, RouteStatusUpdate, RouteUpdate
from app.models.enums import RouteStatus
from app.schemas.route import RouteCreate, RouteUpdate, RouteStatusUpdate


class RouteService:
    def __init__(self, db: Session):
        self.db = db

    # -------------------------
    # helper
    # -------------------------
    def _get_by_code(self, route_code: str) -> Route:
        route = (
            self.db.query(Route)
            .filter(Route.route_code == route_code, Route.is_deleted == False)
            .first()
        )
        if not route:
            raise HTTPException(status_code=404, detail="Route not found")
        return route

    # -------------------------
    # create
    # -------------------------
    def create_route(self, payload: RouteCreate) -> Route:
        existing = (
            self.db.query(Route)
            .filter(Route.route_code == payload.route_code)
            .first()
        )

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Route code already exists",
            )

        route = Route(
            route_code=payload.route_code,
            route_name=payload.route_name,
        )

        self.db.add(route)
        self.db.commit()
        self.db.refresh(route)
        return route

    # -------------------------
    # list
    # -------------------------
    def list_routes(self) -> list[Route]:
        return (
            self.db.query(Route)
            .filter(Route.is_deleted == False)
            .all()
        )

    # -------------------------
    # get
    # -------------------------
    def get_route(self, route_code: str) -> Route:
        return self._get_by_code(route_code)

    # -------------------------
    # update
    # -------------------------
    def update_route(self, route_code: str, payload: RouteUpdate) -> Route:
        route = self._get_by_code(route_code)

        if payload.route_name:
            route.route_name = payload.route_name

        self.db.commit()
        self.db.refresh(route)
        return route

    # -------------------------
    # update status
    # -------------------------
    def update_status(self, route_code: str, payload: RouteStatusUpdate) -> Route:
        route = self._get_by_code(route_code)

        route.status = payload.status

        self.db.commit()
        self.db.refresh(route)
        return route

    # -------------------------
    # soft delete
    # -------------------------
    def soft_delete_route(self, route_code: str) -> None:
        route = self._get_by_code(route_code)
        route.is_deleted = True

        self.db.commit()