from __future__ import annotations

import json
import unittest
from datetime import UTC, datetime
from unittest.mock import patch

from app.models.analytics import AnalyticsReroutingEventLog
from app.services.analytics_service import AnalyticsService


class _FakeDB:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.commits = 0

    def add(self, row: object) -> None:
        self.added.append(row)

    def commit(self) -> None:
        self.commits += 1


class AnalyticsServiceUnitTests(unittest.TestCase):
    def test_aggregate_demand_and_detect_spikes_creates_snapshots_and_logs(self) -> None:
        db = _FakeDB()
        service = AnalyticsService(db)  # type: ignore[arg-type]

        now = datetime(2026, 5, 27, 10, 15, tzinfo=UTC)
        heatmap_payload = {
            "period_start": datetime(2026, 5, 27, 10, 0, tzinfo=UTC),
            "period_end": now,
            "heatmap": [
                {
                    "stop_id": "stop-1",
                    "stop_name": "Piassa",
                    "hour_of_day": 10,
                    "demand_count": 18,
                }
            ],
        }
        spikes_payload = {
            "detected_at": now,
            "spikes": [
                {
                    "stop_id": "stop-1",
                    "route_id": "route-1",
                    "stop_name": "Piassa",
                    "current_hour_count": 18,
                    "historical_hour_average": 10.0,
                    "spike_ratio": 1.8,
                }
            ],
        }

        with patch.object(service, "_utc_now", return_value=now), patch.object(
            service, "get_demand_heatmap", return_value=heatmap_payload
        ), patch.object(service, "get_current_demand_spikes", return_value=spikes_payload), patch.object(
            service,
            "_trigger_rerouting_for_spike",
            return_value={
                "status": "triggered",
                "outcome": "reroute_suggested",
                "trip_id": "trip-1",
                "bus_id": "bus-1",
                "reroute_id": "reroute-1",
            },
        ), patch.object(service, "_create_snapshot") as snapshot_mock:
            result = service.aggregate_demand_and_detect_spikes()

        self.assertEqual(result, {"snapshots": 1, "spikes": 1})
        self.assertEqual(snapshot_mock.call_count, 1)
        self.assertEqual(db.commits, 1)
        self.assertEqual(len(db.added), 1)

        log = db.added[0]
        self.assertIsInstance(log, AnalyticsReroutingEventLog)
        self.assertEqual(log.reroute_id, "reroute-1")
        self.assertEqual(log.status, "triggered")
        payload = json.loads(log.metrics_payload or "{}")
        self.assertEqual(payload.get("spike_ratio"), 1.8)
        self.assertEqual(payload.get("outcome"), "reroute_suggested")

    def test_safe_payload_returns_empty_dict_for_invalid_json(self) -> None:
        self.assertEqual(AnalyticsService._safe_payload(None), {})
        self.assertEqual(AnalyticsService._safe_payload("not-json"), {})
        self.assertEqual(AnalyticsService._safe_payload("[1,2,3]"), {})


if __name__ == "__main__":
    unittest.main()
