from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.route_stop import RouteStop
from app.repositories.route_repository import RouteRepository
from app.repositories.route_stop_repository import RouteStopRepository
from app.repositories.stop_repository import StopRepository
from app.schemas.route_stop import RouteStopAddRequest, RouteStopReorderRequest


class RouteStopService:
    MIN_ROUTE_STOPS = 2

    def __init__(self, db: Session):
        self.db = db
        self.route_repo = RouteRepository(db)
        self.route_stop_repo = RouteStopRepository(db)
        self.stop_repo = StopRepository(db)

    def add_stop(self, route_id: str, payload: RouteStopAddRequest) -> list[RouteStop]:
        route = self.route_repo.get_by_id(route_id)
        if not route:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")

        stop = self.stop_repo.get_by_id(payload.stop_id)
        if not stop:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stop not found")

        existing = self.route_stop_repo.get_by_route_and_stop(route_id, payload.stop_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Stop already exists in route",
            )

        current_stops = self.route_stop_repo.list_for_route(route_id)
        max_sequence = len(current_stops) + 1
        if payload.sequence > max_sequence:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Sequence must be between 1 and {max_sequence}",
            )

        self.route_stop_repo.shift_sequences_for_insert(route_id, payload.sequence)
        self.route_stop_repo.create(
            RouteStop(route_id=route_id, stop_id=payload.stop_id, sequence=payload.sequence)
        )
        self.db.commit()
        return self.route_stop_repo.list_for_route(route_id)

    def list_route_stops(self, route_id: str) -> list[RouteStop]:
        route = self.route_repo.get_by_id(route_id)
        if not route:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")
        return self.route_stop_repo.list_for_route(route_id)

    def reorder_stops(self, route_id: str, payload: RouteStopReorderRequest) -> list[RouteStop]:
        route = self.route_repo.get_by_id(route_id)
        if not route:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")

        existing = self.route_stop_repo.list_for_route(route_id)
        if len(existing) != len(payload.stops):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reorder payload must include all existing route stops",
            )

        existing_ids = {item.stop_id for item in existing}
        payload_ids = {item.stop_id for item in payload.stops}
        if existing_ids != payload_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reorder payload stop IDs must match route stop IDs exactly",
            )

        sequences = [item.sequence for item in payload.stops]
        expected = list(range(1, len(payload.stops) + 1))
        if sorted(sequences) != expected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Sequences must be exactly {expected}",
            )

        route_stop_by_id = {item.stop_id: item for item in existing}
        for item in payload.stops:
            route_stop_by_id[item.stop_id].sequence = item.sequence

        self.db.commit()
        return self.route_stop_repo.list_for_route(route_id)

    def remove_stop(self, route_id: str, stop_id: str) -> list[RouteStop]:
        route = self.route_repo.get_by_id(route_id)
        if not route:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")

        target = self.route_stop_repo.get_by_route_and_stop(route_id, stop_id)
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stop is not part of this route")

        total = len(self.route_stop_repo.list_for_route(route_id))
        if total <= self.MIN_ROUTE_STOPS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Route must have at least {self.MIN_ROUTE_STOPS} stops",
            )

        deleted = self.route_stop_repo.delete(route_id, stop_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete route stop")

        self.route_stop_repo.shift_sequences_for_delete(route_id, target.sequence)
        self.db.commit()
        return self.route_stop_repo.list_for_route(route_id)
