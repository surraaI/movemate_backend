from __future__ import annotations

import unittest
from datetime import UTC, datetime

from app.services.eta_service import ETAService


class ETAServiceUnitTests(unittest.TestCase):
    def tearDown(self) -> None:
        ETAService._eta_model_bundle = None

    def test_model_prediction_is_used_before_rule_based_fallback(self) -> None:
        class FakeVectorizer:
            def transform(self, rows):
                self.rows = rows
                return [[0.0]]

        class FakeModel:
            def predict(self, rows):
                return [1.5]

        ETAService._eta_model_bundle = {
            "model": FakeModel(),
            "vectorizer": FakeVectorizer(),
        }

        eta_minutes, predicted_speed_kph = ETAService._predict_eta_with_model(
            gps_timestamp=datetime(2026, 5, 24, 10, 15, tzinfo=UTC),
            current_latitude=9.0,
            current_longitude=38.7,
            destination_latitude=9.05,
            destination_longitude=38.85,
            remaining_distance_km=12.0,
        )

        self.assertEqual(eta_minutes, 90)
        self.assertAlmostEqual(predicted_speed_kph, 8.0)

    def test_model_prediction_falls_back_when_bundle_load_fails(self) -> None:
        original = ETAService._get_eta_model_bundle
        try:
            ETAService._get_eta_model_bundle = classmethod(lambda cls: None)  # type: ignore[method-assign]
            eta_minutes, predicted_speed_kph = ETAService._predict_eta_with_model(
                gps_timestamp=datetime(2026, 5, 24, 10, 15, tzinfo=UTC),
                current_latitude=9.0,
                current_longitude=38.7,
                destination_latitude=9.05,
                destination_longitude=38.85,
                remaining_distance_km=12.0,
            )
            self.assertIsNone(eta_minutes)
            self.assertIsNone(predicted_speed_kph)
        finally:
            ETAService._get_eta_model_bundle = original


if __name__ == "__main__":
    unittest.main()