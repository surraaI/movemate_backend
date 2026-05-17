from datetime import datetime

from fastapi import HTTPException

from app.models.bus import Bus
from app.models.location import Location


class LocationService:
    def __init__(self, db):
        self.db = db

    def create_location(self, payload):
        bus = (
            self.db.query(Bus)
            .filter(Bus.bus_id == payload.bus_id)
            .first()
        )

        if not bus:
            raise HTTPException(
                status_code=404,
                detail="Bus not found"
            )

        location = Location(
            bus_id=payload.bus_id,
            latitude=payload.latitude,
            longitude=payload.longitude,
            timestamp=datetime.utcnow(),
        )

        self.db.add(location)
        self.db.commit()
        self.db.refresh(location)

        return location

    def get_locations(self):
        return (
            self.db.query(Location)
            .order_by(Location.timestamp.desc())
            .all()
        )