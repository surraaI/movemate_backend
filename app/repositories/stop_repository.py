from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.stop import Stop


class StopRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, stop: Stop) -> Stop:
        self.db.add(stop)
        self.db.flush()
        self.db.refresh(stop)
        return stop

    def get_by_id(self, stop_id: str) -> Stop | None:
        return self.db.get(Stop, stop_id)

    def get_by_name(self, name: str) -> Stop | None:
        return self.db.scalar(select(Stop).where(Stop.name == name))

    def list_all(self) -> list[Stop]:
        return list(self.db.scalars(select(Stop).order_by(Stop.name.asc())).all())
