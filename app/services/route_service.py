from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.enums import RouteStatus
from app.models.route import Route
from app.repositories.route_repository import RouteRepository
from app.repositories.route_stop_repository import RouteStopRepository
from app.schemas.route import RouteCreate, RouteStatusUpdate, RouteUpdate


class RouteService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = RouteRepository(db)
        self.route_stop_repo = RouteStopRepository(db)

    def create_route(self, payload: RouteCreate) -> Route:
        existing = self.repo.get_by_route_code(payload.route_code)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Route code already exists",
            )
        route = Route(route_code=payload.route_code, route_name=payload.route_name)
        created = self.repo.create(route)
        self.db.commit()
        return created

    def list_routes(self) -> list[Route]:
        return self.repo.list_all(include_stops=True)

    def get_route(self, route_id: str) -> Route:
        route = self.repo.get_by_id(route_id, include_stops=True)
        if not route:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")
        return route

    def update_route(self, route_id: str, payload: RouteUpdate) -> Route:
        route = self.repo.get_by_id(route_id)
        if not route:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")

        if payload.route_name is not None:
            route.route_name = payload.route_name

        updated = self.repo.save(route)
        self.db.commit()
        return updated

    def update_status(self, route_id: str, payload: RouteStatusUpdate) -> Route:
        route = self.repo.get_by_id(route_id)
        if not route:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")

        if payload.status == RouteStatus.ACTIVE:
            total_stops = len(self.route_stop_repo.list_for_route(route_id))
            if total_stops < 2:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Active routes must have at least 2 stops",
                )

        route.status = payload.status
        updated = self.repo.save(route)
        self.db.commit()
        return updated

    def soft_delete_route(self, route_id: str) -> None:
        route = self.repo.get_by_id(route_id)
        if not route:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")
        route.is_deleted = True
        self.repo.save(route)
        self.db.commit()
