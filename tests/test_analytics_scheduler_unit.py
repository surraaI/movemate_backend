from __future__ import annotations

import unittest
from unittest.mock import patch

from app.workers import scheduler


class AnalyticsSchedulerUnitTests(unittest.TestCase):
    def test_run_analytics_15_min_jobs_invokes_service(self) -> None:
        with patch("app.workers.scheduler.AnalyticsService.run_15_minute_jobs", return_value={"ok": True}) as run_mock:
            scheduler.run_analytics_15_min_jobs()
            run_mock.assert_called_once()

    def test_run_analytics_hourly_jobs_handles_exceptions(self) -> None:
        with patch("app.workers.scheduler.AnalyticsService.run_hourly_jobs", side_effect=RuntimeError("boom")), patch(
            "app.workers.scheduler.logger"
        ) as logger_mock:
            scheduler.run_analytics_hourly_jobs()
            logger_mock.error.assert_called_once()

    def test_run_analytics_midnight_jobs_invokes_service(self) -> None:
        with patch("app.workers.scheduler.AnalyticsService.run_midnight_jobs", return_value={"ok": True}) as run_mock:
            scheduler.run_analytics_midnight_jobs()
            run_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
