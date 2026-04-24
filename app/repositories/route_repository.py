from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.route import Route
from app.models.route_stop import RouteStop


class RouteRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, route: Route) -> Route:
        self.db.add(route)
        self.db.flush()
        self.db.refresh(route)
        return route

    def get_by_id(self, route_id: str, include_stops: bool = False) -> Route | None:
        query = select(Route).where(Route.id == route_id, Route.is_deleted.is_(False))
        if include_stops:
            query = query.options(selectinload(Route.route_stops).selectinload(RouteStop.stop))
        return self.db.scalar(query)

    def get_by_route_code(self, route_code: str) -> Route | None:
        return self.db.scalar(
            select(Route).where(Route.route_code == route_code, Route.is_deleted.is_(False))
        )

    def list_all(self, include_stops: bool = False) -> list[Route]:
        query = select(Route).where(Route.is_deleted.is_(False)).order_by(Route.route_code.asc())
        if include_stops:
            query = query.options(selectinload(Route.route_stops).selectinload(RouteStop.stop))
        return list(self.db.scalars(query).all())

    def save(self, route: Route) -> Route:
        self.db.add(route)
        self.db.flush()
        self.db.refresh(route)
        return route
