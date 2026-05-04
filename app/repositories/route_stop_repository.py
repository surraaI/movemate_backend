from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload

from app.models.route_stop import RouteStop


class RouteStopRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_route_and_stop(self, route_id: str, stop_id: str) -> RouteStop | None:
        return self.db.scalar(
            select(RouteStop).where(RouteStop.route_id == route_id, RouteStop.stop_id == stop_id)
        )

    def list_for_route(self, route_id: str) -> list[RouteStop]:
        query = (
            select(RouteStop)
            .options(joinedload(RouteStop.stop))
            .where(RouteStop.route_id == route_id)
            .order_by(RouteStop.sequence.asc())
        )
        return list(self.db.scalars(query).all())

    def create(self, route_stop: RouteStop) -> RouteStop:
        self.db.add(route_stop)
        self.db.flush()
        self.db.refresh(route_stop)
        return route_stop

    def shift_sequences_for_insert(self, route_id: str, sequence: int) -> None:
        rows = self.db.scalars(
            select(RouteStop)
            .where(RouteStop.route_id == route_id, RouteStop.sequence >= sequence)
            .order_by(RouteStop.sequence.desc())
        ).all()
        for row in rows:
            row.sequence += 1

    def shift_sequences_for_delete(self, route_id: str, sequence: int) -> None:
        rows = self.db.scalars(
            select(RouteStop)
            .where(RouteStop.route_id == route_id, RouteStop.sequence > sequence)
            .order_by(RouteStop.sequence.asc())
        ).all()
        for row in rows:
            row.sequence -= 1

    def delete(self, route_id: str, stop_id: str) -> int:
        result = self.db.execute(
            delete(RouteStop).where(RouteStop.route_id == route_id, RouteStop.stop_id == stop_id)
        )
        return int(result.rowcount or 0)
