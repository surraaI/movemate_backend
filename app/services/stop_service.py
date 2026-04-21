from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.stop import Stop
from app.repositories.stop_repository import StopRepository
from app.schemas.stop import StopCreate


class StopService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = StopRepository(db)

    def create_stop(self, payload: StopCreate) -> Stop:
        existing = self.repo.get_by_name(payload.name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Stop with this name already exists",
            )

        stop = Stop(name=payload.name, latitude=payload.latitude, longitude=payload.longitude)
        created = self.repo.create(stop)
        self.db.commit()
        return created

    def list_stops(self) -> list[Stop]:
        return self.repo.list_all()

    def get_stop(self, stop_id: str) -> Stop:
        stop = self.repo.get_by_id(stop_id)
        if not stop:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stop not found")
        return stop
