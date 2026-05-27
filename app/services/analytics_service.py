from __future__ import annotations

import json
import uuid
from collections import defaultdict
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import and_, func, or_, text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.analytics import AnalyticsReroutingEventLog, AnalyticsSnapshot
from app.models.enums import TripStatus, UserStatus
from app.models.eta_prediction import ETAPrediction
from app.models.gps_tracking import ActiveTrip, BusCurrentLocation, BusLocationHistory
from app.models.payment import Payment
from app.models.route import Route
from app.models.stop import Stop
from app.models.user import User
from app.models.enums import OccupancyLevel
from app.models.bus import Bus

ETA_ON_TIME_THRESHOLD_MINUTES = 5.0
TRIP_ON_TIME_THRESHOLD_MINUTES = 5.0
GPS_EXPECTED_INTERVAL_SECONDS = 30


class AnalyticsService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _ensure_aware(value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)

    @staticmethod
    def _start_of_day(value: datetime) -> datetime:
        aware = AnalyticsService._ensure_aware(value)
        return datetime.combine(aware.date(), time.min, tzinfo=UTC)

    @staticmethod
    def _safe_payload(raw_payload: str | None) -> dict:
        if not raw_payload:
            return {}
        try:
            payload = json.loads(raw_payload)
            return payload if isinstance(payload, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def _create_snapshot(
        self,
        *,
        snapshot_type: str,
        period_start: datetime,
        period_end: datetime,
        payload: dict,
        route_id: str | None = None,
        stop_id: str | None = None,
    ) -> None:
        row = AnalyticsSnapshot(
            snapshot_type=snapshot_type,
            period_start=self._ensure_aware(period_start),
            period_end=self._ensure_aware(period_end),
            route_id=route_id,
            stop_id=stop_id,
            payload=json.dumps(payload),
        )
        self.db.add(row)

    def _demand_events(self, period_start: datetime, period_end: datetime) -> list[dict]:
        from app.models.event import Event, EventType

        events = (
            self.db.query(Event)
            .filter(
                Event.occurred_at >= self._ensure_aware(period_start),
                Event.occurred_at < self._ensure_aware(period_end),
                Event.event_type.in_([EventType.TICKET_SCANNED, EventType.TICKET_VALIDATED, EventType.TICKET_CREATED]),
            )
            .all()
        )

        demand_rows: list[dict] = []
        for event in events:
            payload = self._safe_payload(event.event_metadata)
            stop_id = payload.get("stop_id") or payload.get("origin_stop_id")
            if not stop_id:
                continue
            occurred_at = self._ensure_aware(event.occurred_at)
            demand_rows.append(
                {
                    "stop_id": str(stop_id),
                    "route_id": event.route_id,
                    "occurred_at": occurred_at,
                }
            )
        return demand_rows

    def get_dashboard_summary(self) -> dict:
        now = self._utc_now()
        day_start = self._start_of_day(now)

        active_buses = (
            self.db.query(func.count(func.distinct(ActiveTrip.vehicle_id)))
            .filter(ActiveTrip.status == TripStatus.ACTIVE)
            .scalar()
            or 0
        )

        todays_revenue_raw = (
            self.db.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(Payment.status == "success", Payment.created_at >= day_start)
            .scalar()
            or 0
        )
        todays_revenue = float(todays_revenue_raw)

        eta = self.get_eta_accuracy_breakdown(day_start, now)
        health = self.get_system_health_metrics(window_hours=24)

        # Additional dashboard metrics
        total_buses = int(self.db.query(func.count(Bus.bus_id)).scalar() or 0)

        # Offline buses: buses without a recent location update (last 5 minutes)
        recent_threshold = now - timedelta(minutes=5)
        recent_locations_count = (
            self.db.query(func.count(func.distinct(BusCurrentLocation.vehicle_id)))
            .filter(BusCurrentLocation.updated_at >= recent_threshold)
            .scalar()
            or 0
        )
        offline_buses = max(total_buses - int(recent_locations_count), 0)

        # Average delay across all routes (weighted by trips) in seconds
        route_perf = self.get_route_performance(day_start, now)
        total_trips = sum(r.get("total_trips", 0) for r in route_perf.get("routes", []))
        weighted_delay_minutes = sum(
            (r.get("average_delay_minutes", 0.0) * r.get("total_trips", 0)) for r in route_perf.get("routes", [])
        )
        average_delay_seconds = (weighted_delay_minutes / total_trips * 60.0) if total_trips else 0.0

        # Tickets in the last hour
        one_hour_start = now - timedelta(hours=1)
        tickets_last_hour = len(self._demand_events(one_hour_start, now))

        # Bus utilization: percent of fleet currently on active trips
        bus_utilization = (int(active_buses) / total_buses * 100.0) if total_buses else 0.0

        return {
            "active_buses": int(active_buses),
            "todays_revenue": round(todays_revenue, 2),
            "eta_accuracy_percent": round(float(eta["overall_accuracy_percent"]), 2),
            "system_health_score": round(float(health["system_health_score"]), 2),
            "offline_buses": int(offline_buses),
            "average_delay_seconds": round(float(average_delay_seconds), 2),
            "tickets_last_hour": int(tickets_last_hour),
            "bus_utilization": round(float(bus_utilization), 2),
        }

    def get_route_performance(self, period_start: datetime, period_end: datetime) -> dict:
        period_start = self._ensure_aware(period_start)
        period_end = self._ensure_aware(period_end)

        route_map = {route.id: route for route in self.db.query(Route).all()}
        trip_rows = (
            self.db.query(ActiveTrip)
            .filter(
                ActiveTrip.started_at >= period_start,
                ActiveTrip.started_at < period_end,
                ActiveTrip.status == TripStatus.COMPLETED,
                ActiveTrip.ended_at.isnot(None),
            )
            .all()
        )

        passenger_counts: dict[str, int] = defaultdict(int)
        for row in self._demand_events(period_start, period_end):
            route_id = row.get("route_id")
            if route_id:
                passenger_counts[str(route_id)] += 1

        grouped: dict[str, dict] = {}
        for trip in trip_rows:
            route = route_map.get(trip.route_id)
            if route is None:
                continue

            started_at = self._ensure_aware(trip.started_at)
            ended_at = self._ensure_aware(trip.ended_at) if trip.ended_at else started_at
            actual_minutes = max((ended_at - started_at).total_seconds() / 60.0, 0.0)
            distance_km = float(route.distance_km or 0.0)
            expected_minutes = actual_minutes if distance_km <= 0 else max((distance_km / 22.0) * 60.0, 1.0)
            delay_minutes = max(actual_minutes - expected_minutes, 0.0)
            on_time = 1 if delay_minutes <= TRIP_ON_TIME_THRESHOLD_MINUTES else 0

            bucket = grouped.setdefault(
                route.id,
                {
                    "route_id": route.id,
                    "route_code": route.route_code,
                    "route_name": route.route_name,
                    "total_trips": 0,
                    "on_time_trips": 0,
                    "delay_sum": 0.0,
                    "total_passengers": passenger_counts.get(route.id, 0),
                },
            )
            bucket["total_trips"] += 1
            bucket["on_time_trips"] += on_time
            bucket["delay_sum"] += delay_minutes

        routes: list[dict] = []
        for bucket in grouped.values():
            total_trips = max(bucket["total_trips"], 1)
            routes.append(
                {
                    "route_id": bucket["route_id"],
                    "route_code": bucket["route_code"],
                    "route_name": bucket["route_name"],
                    "on_time_rate": round((bucket["on_time_trips"] / total_trips) * 100.0, 2),
                    "average_delay_minutes": round(bucket["delay_sum"] / total_trips, 2),
                    "total_passengers": int(bucket["total_passengers"]),
                    "total_trips": int(bucket["total_trips"]),
                }
            )

        routes.sort(key=lambda row: row["on_time_rate"], reverse=True)
        return {
            "period_start": period_start,
            "period_end": period_end,
            "routes": routes,
        }

    def get_demand_heatmap(self, period_start: datetime, period_end: datetime) -> dict:
        period_start = self._ensure_aware(period_start)
        period_end = self._ensure_aware(period_end)

        grouped: dict[tuple[str, int], int] = defaultdict(int)
        for row in self._demand_events(period_start, period_end):
            stop_id = str(row["stop_id"])
            hour_of_day = self._ensure_aware(row["occurred_at"]).hour
            grouped[(stop_id, hour_of_day)] += 1

        stop_ids = sorted({stop_id for stop_id, _ in grouped})
        stop_names = {}
        if stop_ids:
            stop_rows = self.db.query(Stop).filter(Stop.id.in_(stop_ids)).all()
            stop_names = {stop.id: stop.name for stop in stop_rows}

        heatmap = [
            {
                "stop_id": stop_id,
                "stop_name": stop_names.get(stop_id, "Unknown Stop"),
                "hour_of_day": hour_of_day,
                "demand_count": demand_count,
            }
            for (stop_id, hour_of_day), demand_count in grouped.items()
        ]
        heatmap.sort(key=lambda row: (row["hour_of_day"], row["stop_name"]))

        return {
            "period_start": period_start,
            "period_end": period_end,
            "heatmap": heatmap,
        }

    def get_current_demand_spikes(self, threshold_multiplier: float = 1.4, reference_days: int = 30) -> dict:
        now = self._utc_now()
        hour_start = now.replace(minute=0, second=0, microsecond=0)
        hour_end = hour_start + timedelta(hours=1)

        current_counts: dict[str, int] = defaultdict(int)
        current_route_counts: dict[tuple[str, str], int] = defaultdict(int)
        for row in self._demand_events(hour_start, min(now, hour_end)):
            current_counts[row["stop_id"]] += 1
            route_id = row.get("route_id")
            if route_id:
                current_route_counts[(row["stop_id"], str(route_id))] += 1

        history_start = hour_start - timedelta(days=reference_days)
        historical_by_day: dict[str, dict[datetime.date, int]] = defaultdict(lambda: defaultdict(int))
        for row in self._demand_events(history_start, hour_start):
            occurred_at = self._ensure_aware(row["occurred_at"])
            if occurred_at.hour != hour_start.hour:
                continue
            historical_by_day[row["stop_id"]][occurred_at.date()] += 1

        stop_ids = sorted(set(current_counts.keys()) | set(historical_by_day.keys()))
        stop_rows = self.db.query(Stop).filter(Stop.id.in_(stop_ids)).all() if stop_ids else []
        stop_name_map = {stop.id: stop.name for stop in stop_rows}

        spikes = []
        for stop_id in stop_ids:
            current = int(current_counts.get(stop_id, 0))
            historical_days = historical_by_day.get(stop_id, {})
            historical_avg = (
                sum(historical_days.values()) / max(len(historical_days), 1)
                if historical_days
                else 0.0
            )
            if historical_avg <= 0 and current < 5:
                continue

            ratio = (current / historical_avg) if historical_avg > 0 else float(current)
            if ratio >= threshold_multiplier:
                route_id = None
                route_candidates = [
                    (candidate_route_id, count)
                    for (candidate_stop_id, candidate_route_id), count in current_route_counts.items()
                    if candidate_stop_id == stop_id
                ]
                if route_candidates:
                    route_candidates.sort(key=lambda item: item[1], reverse=True)
                    route_id = route_candidates[0][0]

                spikes.append(
                    {
                        "stop_id": stop_id,
                        "route_id": route_id,
                        "stop_name": stop_name_map.get(stop_id, "Unknown Stop"),
                        "current_hour_count": current,
                        "historical_hour_average": round(historical_avg, 2),
                        "spike_ratio": round(ratio, 2),
                    }
                )

        spikes.sort(key=lambda row: row["spike_ratio"], reverse=True)
        return {
            "detected_at": now,
            "spikes": spikes,
        }

    def get_rerouting_history(self, period_start: datetime, period_end: datetime, limit: int = 200) -> dict:
        period_start = self._ensure_aware(period_start)
        period_end = self._ensure_aware(period_end)

        suggestions_sql = text(
            """
            SELECT
                rs.id AS reroute_id,
                rs.route_id,
                rs.trip_id,
                rs.bus_id,
                rs.trigger_reason,
                rs.suggested_at,
                rs.accepted,
                rs.status,
                rs.outcome_recorded,
                ro.actual_time_saving
            FROM reroute_suggestions rs
            LEFT JOIN reroute_outcomes ro ON ro.reroute_id = rs.id
            WHERE rs.suggested_at >= :period_start
              AND rs.suggested_at < :period_end
            ORDER BY rs.suggested_at DESC
            LIMIT :limit
            """
        )

        rows = self.db.execute(
            suggestions_sql,
            {
                "period_start": period_start,
                "period_end": period_end,
                "limit": int(limit),
            },
        ).mappings().all()

        history = []
        accepted_count = 0
        outcomes_recorded = 0
        total_time_saving = 0.0

        for row in rows:
            reroute_id = str(row["reroute_id"])
            analytics_log = (
                self.db.query(AnalyticsReroutingEventLog)
                .filter(AnalyticsReroutingEventLog.reroute_id == reroute_id)
                .order_by(AnalyticsReroutingEventLog.created_at.desc())
                .first()
            )
            admin_approved = bool(analytics_log.admin_approved) if analytics_log else bool(row["accepted"])
            outcome_recorded = bool(row["outcome_recorded"])
            actual_saving = float(row["actual_time_saving"]) if row["actual_time_saving"] is not None else None

            if bool(row["accepted"]):
                accepted_count += 1
            if outcome_recorded:
                outcomes_recorded += 1
            if actual_saving is not None:
                total_time_saving += max(actual_saving, 0.0)

            history.append(
                {
                    "reroute_id": reroute_id,
                    "route_id": str(row["route_id"]),
                    "trip_id": str(row["trip_id"]),
                    "bus_id": str(row["bus_id"]),
                    "trigger_reason": str(row["trigger_reason"]),
                    "suggested_at": self._ensure_aware(row["suggested_at"]),
                    "admin_approved": admin_approved,
                    "status": str(row["status"]),
                    "outcome_recorded": outcome_recorded,
                    "actual_time_saving_minutes": round(actual_saving, 2) if actual_saving is not None else None,
                }
            )

        total_suggestions = len(history)
        acceptance_rate = (accepted_count / total_suggestions) * 100.0 if total_suggestions else 0.0
        effectiveness_rate = (outcomes_recorded / max(accepted_count, 1)) * 100.0 if accepted_count else 0.0
        average_time_saving = total_time_saving / max(outcomes_recorded, 1) if outcomes_recorded else 0.0

        return {
            "period_start": period_start,
            "period_end": period_end,
            "total_suggestions": total_suggestions,
            "accepted_count": accepted_count,
            "acceptance_rate": round(acceptance_rate, 2),
            "outcomes_recorded": outcomes_recorded,
            "effectiveness_rate": round(effectiveness_rate, 2),
            "average_time_saving_minutes": round(average_time_saving, 2),
            "history": history,
        }

    def get_eta_accuracy_breakdown(self, period_start: datetime, period_end: datetime) -> dict:
        period_start = self._ensure_aware(period_start)
        period_end = self._ensure_aware(period_end)

        rows = (
            self.db.query(ETAPrediction, Route)
            .join(Route, Route.id == ETAPrediction.bus_id, isouter=False)
            .filter(
                ETAPrediction.created_at >= period_start,
                ETAPrediction.created_at < period_end,
                ETAPrediction.actual_time.isnot(None),
                ETAPrediction.predicted_time.isnot(None),
            )
            .all()
        )

        # Fallback join through buses.route_id when bus_id is not route_id.
        if not rows:
            fallback_rows = self.db.execute(
                text(
                    """
                    SELECT
                        ep.id,
                        ep.predicted_time,
                        ep.actual_time,
                        r.id AS route_id,
                        r.route_code,
                        r.route_name
                    FROM eta_predictions ep
                    JOIN buses b ON b.bus_id = ep.bus_id
                    JOIN routes r ON r.id = b.route_id
                    WHERE ep.created_at >= :period_start
                      AND ep.created_at < :period_end
                      AND ep.actual_time IS NOT NULL
                      AND ep.predicted_time IS NOT NULL
                    """
                ),
                {"period_start": period_start, "period_end": period_end},
            ).mappings().all()

            grouped: dict[str, dict] = {}
            for row in fallback_rows:
                route_id = str(row["route_id"])
                predicted = self._ensure_aware(row["predicted_time"])
                actual = self._ensure_aware(row["actual_time"])
                mae = abs((actual - predicted).total_seconds()) / 60.0
                bucket = grouped.setdefault(
                    route_id,
                    {
                        "route_id": route_id,
                        "route_code": str(row["route_code"]),
                        "route_name": str(row["route_name"]),
                        "errors": [],
                    },
                )
                bucket["errors"].append(mae)
        else:
            grouped = {}
            for prediction, route in rows:
                route_id = route.id
                predicted = self._ensure_aware(prediction.predicted_time)
                actual = self._ensure_aware(prediction.actual_time)
                mae = abs((actual - predicted).total_seconds()) / 60.0
                bucket = grouped.setdefault(
                    route_id,
                    {
                        "route_id": route_id,
                        "route_code": route.route_code,
                        "route_name": route.route_name,
                        "errors": [],
                    },
                )
                bucket["errors"].append(mae)

        route_items = []
        all_errors: list[float] = []
        for bucket in grouped.values():
            errors = bucket["errors"]
            total_predictions = len(errors)
            if total_predictions == 0:
                continue
            all_errors.extend(errors)
            accurate = sum(1 for error in errors if error <= ETA_ON_TIME_THRESHOLD_MINUTES)
            route_items.append(
                {
                    "route_id": bucket["route_id"],
                    "route_code": bucket["route_code"],
                    "route_name": bucket["route_name"],
                    "total_predictions": total_predictions,
                    "mean_absolute_error_minutes": round(sum(errors) / total_predictions, 2),
                    "accuracy_percent": round((accurate / total_predictions) * 100.0, 2),
                }
            )

        overall_accuracy = 0.0
        mean_abs_error = 0.0
        if all_errors:
            overall_accuracy = (sum(1 for err in all_errors if err <= ETA_ON_TIME_THRESHOLD_MINUTES) / len(all_errors)) * 100.0
            mean_abs_error = sum(all_errors) / len(all_errors)

        route_items.sort(key=lambda row: row["accuracy_percent"], reverse=True)
        return {
            "period_start": period_start,
            "period_end": period_end,
            "overall_accuracy_percent": round(overall_accuracy, 2),
            "mean_absolute_error_minutes": round(mean_abs_error, 2),
            "routes": route_items,
        }

    def get_system_health_metrics(self, window_hours: int = 24) -> dict:
        now = self._utc_now()
        window_start = now - timedelta(hours=window_hours)

        relevant_trips = (
            self.db.query(ActiveTrip)
            .filter(
                ActiveTrip.started_at <= now,
                or_(ActiveTrip.ended_at.is_(None), ActiveTrip.ended_at >= window_start),
            )
            .all()
        )

        gps_dropout_samples = []
        for trip in relevant_trips:
            trip_start = max(self._ensure_aware(trip.started_at), window_start)
            trip_end = min(self._ensure_aware(trip.ended_at) if trip.ended_at else now, now)
            duration_seconds = max((trip_end - trip_start).total_seconds(), 0.0)
            expected = max(int(duration_seconds // GPS_EXPECTED_INTERVAL_SECONDS), 1)
            actual = (
                self.db.query(func.count(BusLocationHistory.id))
                .filter(
                    BusLocationHistory.trip_id == trip.trip_id,
                    BusLocationHistory.gps_timestamp >= trip_start,
                    BusLocationHistory.gps_timestamp < trip_end,
                )
                .scalar()
                or 0
            )
            dropout = max(expected - int(actual), 0) / expected
            gps_dropout_samples.append(dropout)

        gps_dropout_rate = sum(gps_dropout_samples) / len(gps_dropout_samples) if gps_dropout_samples else 0.0

        payment_status_counts = (
            self.db.query(Payment.status, func.count(Payment.id))
            .filter(Payment.created_at >= window_start, Payment.created_at < now)
            .group_by(Payment.status)
            .all()
        )
        status_map = {status: int(count) for status, count in payment_status_counts}
        failed = status_map.get("failed", 0)
        succeeded = status_map.get("success", 0)
        total_processed = failed + succeeded
        payment_failure_rate = (failed / total_processed) if total_processed else 0.0

        active_users = (
            self.db.query(func.count(User.user_id))
            .filter(
                User.status == UserStatus.ACTIVE,
                User.last_login.isnot(None),
                User.last_login >= window_start,
            )
            .scalar()
            or 0
        )

        eta_metrics = self.get_eta_accuracy_breakdown(window_start, now)
        eta_accuracy_ratio = float(eta_metrics["overall_accuracy_percent"]) / 100.0

        health_score = 100.0
        health_score -= min(max(gps_dropout_rate, 0.0), 1.0) * 50.0
        health_score -= min(max(payment_failure_rate, 0.0), 1.0) * 30.0
        health_score -= (1.0 - min(max(eta_accuracy_ratio, 0.0), 1.0)) * 20.0
        health_score = max(0.0, min(100.0, health_score))

        return {
            "window_start": window_start,
            "window_end": now,
            "gps_dropout_rate": round(gps_dropout_rate, 4),
            "payment_failure_rate": round(payment_failure_rate, 4),
            "active_users": int(active_users),
            "system_health_score": round(health_score, 2),
        }

    def sync_rerouting_event_schedule(self, window_hours: int = 48) -> int:
        now = self._utc_now()
        from_time = now - timedelta(hours=window_hours)

        suggestions = self.db.execute(
            text(
                """
                SELECT id, route_id, trip_id, bus_id, trigger_reason, suggested_at, accepted, status
                FROM reroute_suggestions
                WHERE suggested_at >= :from_time
                ORDER BY suggested_at DESC
                """
            ),
            {"from_time": from_time},
        ).mappings().all()

        created = 0
        for suggestion in suggestions:
            reroute_id = str(suggestion["id"])
            existing = (
                self.db.query(AnalyticsReroutingEventLog)
                .filter(AnalyticsReroutingEventLog.reroute_id == reroute_id)
                .first()
            )
            suggested_at = self._ensure_aware(suggestion["suggested_at"])
            scheduled_check_at = suggested_at + timedelta(minutes=30)

            if existing is None:
                created += 1
                self.db.add(
                    AnalyticsReroutingEventLog(
                        reroute_id=reroute_id,
                        route_id=str(suggestion["route_id"]),
                        trip_id=str(suggestion["trip_id"]),
                        bus_id=str(suggestion["bus_id"]),
                        trigger_reason=str(suggestion["trigger_reason"]),
                        admin_approved=bool(suggestion["accepted"]),
                        status=str(suggestion["status"]),
                        outcome="pending",
                        detected_at=suggested_at,
                        scheduled_outcome_check_at=scheduled_check_at,
                    )
                )
            else:
                existing.admin_approved = bool(suggestion["accepted"])
                existing.status = str(suggestion["status"])
                if existing.scheduled_outcome_check_at is None:
                    existing.scheduled_outcome_check_at = scheduled_check_at

        self.db.commit()
        return created

    def run_due_outcome_checks(self) -> int:
        now = self._utc_now()
        due_logs = (
            self.db.query(AnalyticsReroutingEventLog)
            .filter(
                AnalyticsReroutingEventLog.reroute_id.isnot(None),
                AnalyticsReroutingEventLog.scheduled_outcome_check_at.isnot(None),
                AnalyticsReroutingEventLog.scheduled_outcome_check_at <= now,
                AnalyticsReroutingEventLog.outcome_checked_at.is_(None),
            )
            .all()
        )

        checked = 0
        for log in due_logs:
            row = self.db.execute(
                text(
                    """
                    SELECT actual_time_saving, accepted, timestamp
                    FROM reroute_outcomes
                    WHERE reroute_id = :reroute_id
                    ORDER BY timestamp DESC
                    LIMIT 1
                    """
                ),
                {"reroute_id": log.reroute_id},
            ).mappings().first()

            checked += 1
            log.outcome_checked_at = now
            if row is None:
                log.outcome = "no_outcome_reported"
                log.status = "pending_outcome"
                log.metrics_payload = json.dumps({"checked_at": now.isoformat(), "outcome_found": False})
            else:
                actual_time_saving = float(row["actual_time_saving"])
                log.outcome = "improved" if actual_time_saving > 0 else "no_gain"
                log.status = "completed"
                log.metrics_payload = json.dumps(
                    {
                        "checked_at": now.isoformat(),
                        "outcome_found": True,
                        "actual_time_saving": round(actual_time_saving, 2),
                        "accepted": bool(row["accepted"]),
                    }
                )

        self.db.commit()
        return checked

    def aggregate_demand_and_detect_spikes(self) -> dict:
        now = self._utc_now()
        hour_start = now.replace(minute=0, second=0, microsecond=0)

        heatmap = self.get_demand_heatmap(hour_start, now)
        spikes = self.get_current_demand_spikes()

        for item in heatmap["heatmap"]:
            self._create_snapshot(
                snapshot_type="demand_stop_hourly",
                period_start=hour_start,
                period_end=now,
                route_id=None,
                stop_id=item["stop_id"],
                payload=item,
            )

        for spike in spikes["spikes"]:
            trigger_result = self._trigger_rerouting_for_spike(spike)
            self.db.add(
                AnalyticsReroutingEventLog(
                    id=str(uuid.uuid4()),
                    reroute_id=trigger_result.get("reroute_id"),
                    route_id=spike.get("route_id"),
                    trip_id=trigger_result.get("trip_id"),
                    bus_id=trigger_result.get("bus_id"),
                    trigger_reason="demand_spike_40_percent",
                    admin_approved=False,
                    status=trigger_result.get("status", "trigger_requested"),
                    outcome=trigger_result.get("outcome", "pending"),
                    detected_at=now,
                    scheduled_outcome_check_at=now + timedelta(minutes=30),
                    metrics_payload=json.dumps({**spike, **trigger_result}),
                )
            )

        self.db.commit()
        return {"snapshots": len(heatmap["heatmap"]), "spikes": len(spikes["spikes"])}

    def _trigger_rerouting_for_spike(self, spike: dict) -> dict:
        route_id = spike.get("route_id")
        stop_id = spike.get("stop_id")
        if not route_id or not stop_id:
            return {"status": "trigger_requested", "outcome": "insufficient_route_context"}

        active_trip = (
            self.db.query(ActiveTrip)
            .filter(ActiveTrip.route_id == route_id, ActiveTrip.status == TripStatus.ACTIVE)
            .order_by(ActiveTrip.started_at.desc())
            .first()
        )
        if active_trip is None:
            return {"status": "trigger_requested", "outcome": "no_active_trip"}

        current_location = (
            self.db.query(BusCurrentLocation)
            .filter(BusCurrentLocation.trip_id == active_trip.trip_id)
            .first()
        )
        if current_location is None:
            return {
                "status": "trigger_requested",
                "outcome": "no_live_location",
                "trip_id": active_trip.trip_id,
                "bus_id": active_trip.vehicle_id,
            }

        try:
            from rerouting_module import ReroutingPipeline

            pipeline = ReroutingPipeline()
            reroute_result = pipeline.log_gps_update(
                self.db,
                trip_id=active_trip.trip_id,
                driver_id=active_trip.driver_id,
                latitude=float(current_location.latitude),
                longitude=float(current_location.longitude),
                speed=float(current_location.speed_kph or 0.0),
                passenger_count=max(int(spike.get("current_hour_count", 0)), 1),
                stop_id=str(stop_id),
            )
        except Exception as exc:
            return {
                "status": "trigger_requested",
                "outcome": "rerouting_trigger_failed",
                "trip_id": active_trip.trip_id,
                "bus_id": active_trip.vehicle_id,
                "error": str(exc),
            }

        return {
            "status": "triggered",
            "outcome": "reroute_suggested" if reroute_result.get("reroute_suggested") else "processed_no_suggestion",
            "trip_id": active_trip.trip_id,
            "bus_id": active_trip.vehicle_id,
            "reroute_id": reroute_result.get("reroute_id"),
        }

    def compute_eta_accuracy_snapshot_hourly(self) -> dict:
        now = self._utc_now()
        period_start = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
        period_end = period_start + timedelta(hours=1)

        eta_breakdown = self.get_eta_accuracy_breakdown(period_start, period_end)
        for route in eta_breakdown["routes"]:
            self._create_snapshot(
                snapshot_type="eta_accuracy_hourly",
                period_start=period_start,
                period_end=period_end,
                route_id=route["route_id"],
                payload=route,
            )

        self.db.commit()
        return {
            "routes": len(eta_breakdown["routes"]),
            "overall_accuracy_percent": eta_breakdown["overall_accuracy_percent"],
        }

    def generate_daily_route_summary(self, day: datetime | None = None) -> dict:
        base_day = self._ensure_aware(day) if day else self._utc_now() - timedelta(days=1)
        period_start = datetime.combine(base_day.date(), time.min, tzinfo=UTC)
        period_end = period_start + timedelta(days=1)

        route_perf = self.get_route_performance(period_start, period_end)
        for route in route_perf["routes"]:
            self._create_snapshot(
                snapshot_type="route_daily_summary",
                period_start=period_start,
                period_end=period_end,
                route_id=route["route_id"],
                payload=route,
            )

        health = self.get_system_health_metrics(window_hours=24)
        self._create_snapshot(
            snapshot_type="system_health_daily",
            period_start=period_start,
            period_end=period_end,
            payload=health,
        )

        self.db.commit()
        return {"routes": len(route_perf["routes"]), "summary_date": str(period_start.date())}

    @classmethod
    def run_15_minute_jobs(cls) -> dict:
        db = SessionLocal()
        try:
            service = cls(db)
            aggregate = service.aggregate_demand_and_detect_spikes()
            created = service.sync_rerouting_event_schedule()
            occupancy_flags = service.sync_high_occupancy_signals()
            due_checked = service.run_due_outcome_checks()
            return {
                "aggregate": aggregate,
                "scheduled_reroute_checks": created,
                "high_occupancy_flags": occupancy_flags,
                "checked_outcomes": due_checked,
            }
        finally:
            db.close()

    @classmethod
    def run_hourly_jobs(cls) -> dict:
        db = SessionLocal()
        try:
            service = cls(db)
            return service.compute_eta_accuracy_snapshot_hourly()
        finally:
            db.close()

    @classmethod
    def run_midnight_jobs(cls) -> dict:
        db = SessionLocal()
        try:
            service = cls(db)
            return service.generate_daily_route_summary()
        finally:
            db.close()

    def sync_high_occupancy_signals(self, lookback_minutes: int = 15) -> int:
        now = self._utc_now()
        window_start = now - timedelta(minutes=lookback_minutes)

        from app.models.gps_tracking import ActiveTrip
        from app.models.enums import TripStatus

        active_route_ids = [
            row[0]
            for row in (
                self.db.query(ActiveTrip.route_id)
                .filter(ActiveTrip.status == TripStatus.ACTIVE)
                .distinct()
                .all()
            )
            if row[0] is not None
        ]

        from app.services.gps_tracking_service import GPSTrackingService

        gps_service = GPSTrackingService(self.db)
        created = 0

        for route_id in active_route_ids:
            occupancy = gps_service.get_route_bus_occupancy(str(route_id))
            for bus in occupancy.active_buses:
                if bus.occupancy_level != OccupancyLevel.HIGH:
                    continue

                existing = (
                    self.db.query(AnalyticsReroutingEventLog)
                    .filter(
                        AnalyticsReroutingEventLog.route_id == str(route_id),
                        AnalyticsReroutingEventLog.bus_id == bus.bus_id,
                        AnalyticsReroutingEventLog.trigger_reason == "high_occupancy",
                        AnalyticsReroutingEventLog.detected_at >= window_start,
                    )
                    .first()
                )
                if existing is not None:
                    continue

                created += 1
                self.db.add(
                    AnalyticsReroutingEventLog(
                        id=str(uuid.uuid4()),
                        reroute_id=None,
                        route_id=str(route_id),
                        trip_id=bus.trip_id,
                        bus_id=bus.bus_id,
                        trigger_reason="high_occupancy",
                        admin_approved=False,
                        status="trigger_requested",
                        outcome="pending",
                        detected_at=now,
                        scheduled_outcome_check_at=now + timedelta(minutes=30),
                        metrics_payload=json.dumps(
                            {
                                "estimated_passengers": bus.estimated_passengers,
                                "bus_capacity": bus.bus_capacity,
                                "occupancy_percent": bus.occupancy_percent,
                                "occupancy_level": bus.occupancy_level.value,
                            }
                        ),
                    )
                )

        if created:
            self.db.commit()
        return created
