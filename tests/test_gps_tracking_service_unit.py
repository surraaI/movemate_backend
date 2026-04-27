from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException

from app.models.gps_tracking import BusCurrentLocation
from app.schemas.gps_tracking import GPSUpdateRequest
from app.services.gps_tracking_service import GPSTrackingService


class GPSTrackingServiceUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = GPSTrackingService(db=None)  # type: ignore[arg-type]

    def test_haversine_calculates_reasonable_distance(self) -> None:
        distance = self.service._haversine_km(9.011, 38.79, 9.02, 38.8)
        self.assertGreater(distance, 1.0)
        self.assertLess(distance, 2.0)

    def test_validate_against_previous_rejects_out_of_order_timestamp(self) -> None:
        now = datetime.now(UTC)
        current = BusCurrentLocation(
            trip_id="trip-1",
            route_id="route-1",
            vehicle_id="BUS-001",
            latitude=9.011,
            longitude=38.79,
            speed_kph=30.0,
            heading_degrees=80,
            gps_timestamp=now,
        )
        payload = GPSUpdateRequest(
            latitude=9.012,
            longitude=38.792,
            timestamp=now - timedelta(seconds=5),
            speedKph=32.0,
        )
        with self.assertRaises(HTTPException):
            self.service._validate_against_previous(current, payload)


if __name__ == "__main__":
    unittest.main()
