from fastapi import HTTPException

from app.models.bus import Bus


class BusService:
    def __init__(self, db):
        self.db = db

    def create_bus(self, payload):
        existing = (
            self.db.query(Bus)
            .filter(Bus.bus_id == payload.bus_id)
            .first()
        )

        if existing:
            raise HTTPException(
                status_code=400,
                detail="Bus already exists"
            )

        bus = Bus(
            bus_id=payload.bus_id,
            route_id=payload.route_id,
            status=payload.status,
        )

        self.db.add(bus)
        self.db.commit()
        self.db.refresh(bus)

        return bus

    def get_buses(self):
        return self.db.query(Bus).all()

    def get_bus(self, bus_id: str):
        bus = (
            self.db.query(Bus)
            .filter(Bus.bus_id == bus_id)
            .first()
        )

        if not bus:
            raise HTTPException(
                status_code=404,
                detail="Bus not found"
            )

        return bus

    def update_bus(self, bus_id: str, payload):
        bus = self.get_bus(bus_id)

        if payload.route_id is not None:
            bus.route_id = payload.route_id

        if payload.status is not None:
            bus.status = payload.status

        self.db.commit()
        self.db.refresh(bus)

        return bus

    def delete_bus(self, bus_id: str):
        bus = self.get_bus(bus_id)

        self.db.delete(bus)
        self.db.commit()