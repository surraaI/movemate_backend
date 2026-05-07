from __future__ import annotations

import csv
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path

import joblib
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.repositories.gps_tracking_repository import GPSTrackingRepository
from app.schemas.gps_tracking import ETAPredictionOut

DEFAULT_SPEED_KPH = 22.0
MIN_REASONABLE_SPEED_KPH = 8.0
MAX_REASONABLE_SPEED_KPH = 75.0
MIN_REASONABLE_ETA_MINUTES = 1
MAX_REASONABLE_ETA_MINUTES = 240


class ETAService:
    _historical_stats: dict[tuple[int, int], float] | None = None
    _historical_avg_speed: float | None = None
    _eta_model_bundle: dict | None = None
    _eta_model_load_attempted: bool = False

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
        eta_minutes = self._predict_eta_minutes_with_fallback(
            gps_timestamp=current.gps_timestamp,
            remaining_distance_km=remaining_distance_km,
            live_speed_kph=current.speed_kph,
            predicted_speed_kph=predicted_speed_kph,
            current_latitude=current.latitude,
            current_longitude=current.longitude,
            destination_latitude=destination.stop.latitude,
            destination_longitude=destination.stop.longitude,
        )
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

    def _predict_eta_minutes_with_fallback(
        self,
        *,
        gps_timestamp: datetime,
        remaining_distance_km: float,
        live_speed_kph: float | None,
        predicted_speed_kph: float,
        current_latitude: float,
        current_longitude: float,
        destination_latitude: float,
        destination_longitude: float,
    ) -> int:
        model_minutes = self._predict_eta_minutes_ml(
            gps_timestamp=gps_timestamp,
            remaining_distance_km=remaining_distance_km,
            live_speed_kph=live_speed_kph,
            current_latitude=current_latitude,
            current_longitude=current_longitude,
            destination_latitude=destination_latitude,
            destination_longitude=destination_longitude,
        )
        if model_minutes is not None:
            return max(MIN_REASONABLE_ETA_MINUTES, min(MAX_REASONABLE_ETA_MINUTES, math.ceil(model_minutes)))

        # Fallback to deterministic rule-based ETA when model is unavailable.
        baseline_eta = (remaining_distance_km / predicted_speed_kph) * 60
        return max(
            MIN_REASONABLE_ETA_MINUTES,
            min(MAX_REASONABLE_ETA_MINUTES, math.ceil(baseline_eta)),
        )

    @classmethod
    def _predict_eta_minutes_ml(
        cls,
        *,
        gps_timestamp: datetime,
        remaining_distance_km: float,
        live_speed_kph: float | None,
        current_latitude: float,
        current_longitude: float,
        destination_latitude: float,
        destination_longitude: float,
    ) -> float | None:
        model_bundle = cls._load_eta_model_bundle()
        if model_bundle is None:
            return None

        model = model_bundle.get("model")
        if model is None:
            return None
        vectorizer = model_bundle.get("vectorizer")

        timestamp = gps_timestamp.astimezone(UTC) if gps_timestamp.tzinfo else gps_timestamp.replace(tzinfo=UTC)
        candidate_speed = live_speed_kph if live_speed_kph is not None and live_speed_kph > 0 else DEFAULT_SPEED_KPH
        features = {
            "day_of_week": timestamp.weekday(),
            "beginning_hour": timestamp.hour,
            "mileage_km": max(0.0, remaining_distance_km),
            "initial_latitude": current_latitude,
            "initial_longitude": current_longitude,
            "final_latitude": destination_latitude,
            "final_longitude": destination_longitude,
            "month": timestamp.month,
            "avg_speed_kph": candidate_speed,
        }

        try:
            model_input = vectorizer.transform([features]) if vectorizer is not None else [features]
            prediction = model.predict(model_input)[0]
        except Exception:
            return None
        if prediction is None or prediction <= 0:
            return None
        return float(prediction)

    @classmethod
    def _load_eta_model_bundle(cls) -> dict | None:
        if cls._eta_model_load_attempted:
            return cls._eta_model_bundle

        cls._eta_model_load_attempted = True
        model_path = Path(settings.ETA_MODEL_PATH)
        if not model_path.is_absolute():
            model_path = Path(__file__).resolve().parents[2] / model_path
        if not model_path.exists():
            cls._eta_model_bundle = None
            return None

        try:
            loaded = joblib.load(model_path)
        except Exception:
            cls._eta_model_bundle = None
            return None

        cls._eta_model_bundle = loaded if isinstance(loaded, dict) else {"model": loaded}
        return cls._eta_model_bundle

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
