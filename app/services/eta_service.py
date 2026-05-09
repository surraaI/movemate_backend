from __future__ import annotations

import csv
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.gps_tracking_repository import GPSTrackingRepository
from app.schemas.gps_tracking import ETAPredictionOut

DEFAULT_SPEED_KPH = 22.0
MIN_REASONABLE_SPEED_KPH = 8.0
MAX_REASONABLE_SPEED_KPH = 75.0


class ETAService:
    _historical_stats: dict[tuple[int, int], float] | None = None
    _historical_avg_speed: float | None = None

    def __init__(self, db: Session):
        self.db = db
        self.repo = GPSTrackingRepository(db)
        self._ensure_historical_loaded()

    def predict_trip_eta(self, trip_id: str, destination_stop_id: str | None = None) -> ETAPredictionOut:
        trip = self.repo.get_trip_by_id(trip_id)
        if trip is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found")

        current = self.repo.get_current_location_for_trip(trip_id)
        if current is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No live GPS location for this trip")

        route_stops = self.repo.list_route_stops(trip.route_id)
        if not route_stops:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route has no configured stops")

        destination = None
        if destination_stop_id:
            for stop in route_stops:
                if stop.stop_id == destination_stop_id:
                    destination = stop
                    break
            if destination is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Destination stop does not exist in this route",
                )
        else:
            destination = route_stops[-1]

        remaining_distance_km = self._haversine_km(
            current.latitude,
            current.longitude,
            destination.stop.latitude,
            destination.stop.longitude,
        )
        predicted_speed_kph = self._predict_speed_kph(current.gps_timestamp, current.speed_kph)
        eta_minutes = max(1, math.ceil((remaining_distance_km / predicted_speed_kph) * 60))
        estimated_arrival = datetime.now(UTC) + timedelta(minutes=eta_minutes)

        return ETAPredictionOut(
            trip_id=trip.trip_id,
            route_id=trip.route_id,
            destination_stop_id=destination.stop_id,
            destination_stop_name=destination.stop.name,
            remaining_distance_km=round(remaining_distance_km, 3),
            predicted_speed_kph=round(predicted_speed_kph, 2),
            eta_minutes=eta_minutes,
            estimated_arrival=estimated_arrival,
        )

    def _predict_speed_kph(self, gps_timestamp: datetime, live_speed_kph: float | None) -> float:
        now = gps_timestamp.astimezone(UTC) if gps_timestamp.tzinfo else gps_timestamp.replace(tzinfo=UTC)
        key = (now.weekday(), now.hour)
        historical_speed = self._historical_stats.get(key) if self._historical_stats else None
        if historical_speed is None:
            historical_speed = self._historical_avg_speed or DEFAULT_SPEED_KPH

        live_speed = None
        if live_speed_kph is not None and live_speed_kph > 0:
            live_speed = live_speed_kph

        if live_speed is None:
            predicted = historical_speed
        else:
            predicted = (0.6 * live_speed) + (0.4 * historical_speed)

        return min(MAX_REASONABLE_SPEED_KPH, max(MIN_REASONABLE_SPEED_KPH, predicted))

    @classmethod
    def _ensure_historical_loaded(cls) -> None:
        if cls._historical_stats is not None and cls._historical_avg_speed is not None:
            return

        dataset_path = Path(__file__).resolve().parents[2] / "ETA_datasets" / "final_data.csv"
        grouped_speeds: dict[tuple[int, int], list[float]] = {}
        all_speeds: list[float] = []

        try:
            with dataset_path.open("r", encoding="utf-8", newline="") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    day = cls._safe_int(row.get("DayofWeek"))
                    hour = cls._safe_int(row.get("Beginning Time"))
                    speed = cls._safe_float(row.get("Avg_Speed"))
                    if day is None or hour is None or speed is None:
                        continue
                    if speed <= 0:
                        continue
                    day = max(0, min(6, day))
                    hour = max(0, min(23, hour))
                    grouped_speeds.setdefault((day, hour), []).append(speed)
                    all_speeds.append(speed)
        except FileNotFoundError:
            cls._historical_stats = {}
            cls._historical_avg_speed = DEFAULT_SPEED_KPH
            return

        cls._historical_stats = {
            key: sum(values) / len(values) for key, values in grouped_speeds.items() if values
        }
        cls._historical_avg_speed = (sum(all_speeds) / len(all_speeds)) if all_speeds else DEFAULT_SPEED_KPH

    @staticmethod
    def _safe_int(value: str | None) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(float(value))
        except ValueError:
            return None

    @staticmethod
    def _safe_float(value: str | None) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except ValueError:
            return None

    @staticmethod
    def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        radius_km = 6371.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        a = (
            math.sin(delta_phi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return radius_km * c
