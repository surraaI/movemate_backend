from __future__ import annotations

import json
import logging
import math
import pickle
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from fastapi import HTTPException, status
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, MetaData, String, Table, Text, func, insert, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sklearn.ensemble import RandomForestClassifier
from sklearn.dummy import DummyClassifier
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split

from app.db.session import SessionLocal
from app.models.bus import Bus
from app.models.enums import TripStatus
from app.models.event import Event, EventType
from app.models.gps_tracking import ActiveTrip
from app.models.route import Route
from app.models.route_stop import RouteStop
from app.models.stop import Stop
from app.models.user import User
from app.services.event_service import EventService
from config import settings

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency
    import joblib
except Exception:  # pragma: no cover - fallback to pickle when unavailable
    joblib = None

try:  # pragma: no cover - optional dependency
    import networkx as nx
except Exception:  # pragma: no cover - fallback to geometry-only routing when unavailable
    nx = None

try:  # pragma: no cover - optional dependency
    from apscheduler.schedulers.background import BackgroundScheduler
except Exception:  # pragma: no cover - fallback scheduler when APScheduler is unavailable
    class BackgroundScheduler:  # type: ignore[too-many-ancestors]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self._started = False

        def add_job(self, *args: Any, **kwargs: Any) -> None:
            return None

        def start(self) -> None:
            self._started = True

        def shutdown(self, wait: bool = True) -> None:
            self._started = False

try:  # pragma: no cover - optional dependency
    import osmnx as ox
except Exception:  # pragma: no cover - graceful fallback when unavailable
    ox = None


rerouting_metadata = MetaData()


trip_logs = Table(
    "trip_logs",
    rerouting_metadata,
    Column("id", String(36), primary_key=True),
    Column("trip_id", String(36), nullable=False, index=True),
    Column("bus_id", String(36), nullable=False, index=True),
    Column("route_id", String(36), nullable=False, index=True),
    Column("driver_id", String(36), nullable=False, index=True),
    Column("timestamp", DateTime(timezone=True), nullable=False, index=True),
    Column("day_of_week", Integer, nullable=False),
    Column("time_range", String(32), nullable=False),
    Column("month", Integer, nullable=False),
    Column("latitude", Float, nullable=False),
    Column("longitude", Float, nullable=False),
    Column("speed", Float, nullable=True),
    Column("mileage_covered", Float, nullable=False, default=0.0),
    Column("passenger_count", Integer, nullable=False, default=0),
    Column("stop_id", String(36), nullable=True, index=True),
    Column("total_time_seconds", Float, nullable=False, default=0.0),
    Column("congestion_score", Float, nullable=False, default=0.0),
    Column("high_demand_segment", Integer, nullable=False, default=0),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

reroute_suggestions = Table(
    "reroute_suggestions",
    rerouting_metadata,
    Column("id", String(36), primary_key=True),
    Column("trip_id", String(36), nullable=False, index=True),
    Column("bus_id", String(36), nullable=False, index=True),
    Column("route_id", String(36), nullable=False, index=True),
    Column("suggested_at", DateTime(timezone=True), nullable=False, index=True),
    Column("current_segment", String(255), nullable=True),
    Column("trigger_reason", String(255), nullable=False),
    Column("new_route_polyline", Text, nullable=False),
    Column("estimated_time_saving_minutes", Float, nullable=False, default=0.0),
    Column("confidence_score", Float, nullable=False, default=0.0),
    Column("accepted", Boolean, nullable=False, default=False),
    Column("feedback_at", DateTime(timezone=True), nullable=True),
    Column("outcome_recorded", Boolean, nullable=False, default=False),
    Column("status", String(32), nullable=False, default="suggested"),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

reroute_outcomes = Table(
    "reroute_outcomes",
    rerouting_metadata,
    Column("id", String(36), primary_key=True),
    Column("reroute_id", String(36), nullable=False, index=True),
    Column("bus_id", String(36), nullable=False, index=True),
    Column("accepted", Boolean, nullable=False, default=False),
    Column("actual_time_saving", Float, nullable=False, default=0.0),
    Column("timestamp", DateTime(timezone=True), nullable=False, index=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

retraining_log = Table(
    "retraining_log",
    rerouting_metadata,
    Column("id", String(36), primary_key=True),
    Column("rows_used", Integer, nullable=False),
    Column("accuracy_before", Float, nullable=True),
    Column("accuracy_after", Float, nullable=True),
    Column("promoted", Boolean, nullable=False, default=False),
    Column("model_version", String(64), nullable=True),
    Column("message", Text, nullable=True),
    Column("timestamp", DateTime(timezone=True), nullable=False, index=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)


REROUTE_OUTCOMES_TABLE = reroute_outcomes
RETRAINING_LOG_TABLE = retraining_log

TRIP_LOGS_TABLE = trip_logs
REROUTE_SUGGESTIONS_TABLE = reroute_suggestions


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _as_timezone_aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    return radius_km * (2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a)))


def _time_range_label(timestamp: datetime) -> str:
    hour = _as_timezone_aware(timestamp).hour
    if hour < 6:
        return "00-06"
    if hour < 10:
        return "06-10"
    if hour < 16:
        return "10-16"
    if hour < 20:
        return "16-20"
    return "20-24"


def _ordinal_time_range(time_range: str) -> int:
    labels = ["00-06", "06-10", "10-16", "16-20", "20-24"]
    if time_range in labels:
        return labels.index(time_range)
    return 0


def _serialise_polyline(polyline: Sequence[tuple[float, float]]) -> str:
    return json.dumps([[latitude, longitude] for latitude, longitude in polyline])


def _deserialise_polyline(raw_polyline: str) -> list[list[float]]:
    value = json.loads(raw_polyline)
    return [[float(point[0]), float(point[1])] for point in value]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _records_from_dataset(dataset: Any) -> list[dict[str, Any]]:
    if dataset is None:
        return []
    if isinstance(dataset, list):
        return [dict(item) for item in dataset]
    if hasattr(dataset, "to_dict"):
        try:
            return list(dataset.to_dict(orient="records"))
        except TypeError:
            pass
    if isinstance(dataset, Iterable):
        return [dict(item) for item in dataset]
    raise TypeError("Unsupported dataset format")


def _dump_artifact(payload: dict[str, Any], path: Path) -> None:
    if joblib is not None:
        joblib.dump(payload, path)
        return
    with path.open("wb") as file:
        pickle.dump(payload, file)


def _load_artifact(path: Path) -> dict[str, Any]:
    if joblib is not None:
        return joblib.load(path)
    with path.open("rb") as file:
        return pickle.load(file)


def _extract_log_rows(session: Session, since: datetime | None = None) -> list[dict[str, Any]]:
    query = select(TRIP_LOGS_TABLE)
    if since is not None:
        query = query.where(TRIP_LOGS_TABLE.c.timestamp > since)
    return [dict(row._mapping) for row in session.execute(query).all()]


class DemandRerouteModel:
    """Tabular classifier for identifying high-demand bus segments.

    A random forest is used because the problem is tabular, mixes categorical
    and numeric signals, and benefits from nonlinear interactions while still
    providing feature importances for operational explainability.
    """

    feature_columns: tuple[str, ...] = (
        "day_of_week",
        "time_range_index",
        "avg_speed",
        "mileage",
        "initial_latitude",
        "initial_longitude",
        "month",
        "passenger_count",
        "congestion_score",
    )

    def __init__(self, model_directory: Path | None = None, bus_capacity: int | None = None) -> None:
        self.model_directory = model_directory or settings.model_directory
        self.model_directory.mkdir(parents=True, exist_ok=True)
        self.registry_path = self.model_directory / settings.REROUTING_MODEL_REGISTRY_FILE
        self.bus_capacity = bus_capacity or settings.REROUTING_DEFAULT_BUS_CAPACITY
        self.model: RandomForestClassifier | None = None
        self.version: str | None = None
        self.metrics: dict[str, float] = {}
        self.feature_importances: dict[str, float] = {}

    def _normalise_training_rows(self, dataset: Any) -> list[dict[str, Any]]:
        rows = _records_from_dataset(dataset)
        normalised_rows: list[dict[str, Any]] = []
        for row in rows:
            time_range = str(row.get("time_range") or row.get("TimeRange") or "00-06")
            mileage = _safe_float(row.get("mileage") or row.get("Mileage") or row.get("mileage_covered"))
            total_time = _safe_float(row.get("total_time") or row.get("total_time_seconds") or 1.0, 1.0)
            congestion_score = _safe_float(row.get("congestion_score"), default=mileage / max(total_time, 1.0))
            passenger_count = _safe_int(row.get("passenger_count") or row.get("Passenger_Count"))
            label_threshold = self.bus_capacity * settings.REROUTING_CAPACITY_THRESHOLD
            normalised_rows.append(
                {
                    "day_of_week": _safe_int(row.get("day_of_week") or row.get("DayofWeek")),
                    "time_range_index": _ordinal_time_range(time_range),
                    "avg_speed": _safe_float(row.get("avg_speed") or row.get("Avg_Speed") or row.get("speed")),
                    "mileage": mileage,
                    "initial_latitude": _safe_float(row.get("initial_latitude") or row.get("latitude") or row.get("Initial latitude")),
                    "initial_longitude": _safe_float(row.get("initial_longitude") or row.get("longitude") or row.get("Initial longitude")),
                    "month": _safe_int(row.get("month") or row.get("Month") or _now_utc().month),
                    "passenger_count": passenger_count,
                    "congestion_score": congestion_score,
                    "high_demand_segment": _safe_int(
                        row.get("high_demand_segment"),
                        default=1 if passenger_count > label_threshold else 0,
                    ),
                }
            )
        return normalised_rows

    def _feature_matrix(self, rows: list[dict[str, Any]]) -> tuple[list[list[float]], list[int]]:
        x_values: list[list[float]] = []
        y_values: list[int] = []
        for row in rows:
            x_values.append([float(row[column]) for column in self.feature_columns])
            y_values.append(int(row["high_demand_segment"]))
        return x_values, y_values

    def _next_version(self) -> str:
        existing_versions = []
        for artifact in self.model_directory.glob("model_v*_*.pkl"):
            stem = artifact.stem
            try:
                version_text = stem.split("_", 1)[0].removeprefix("model_v")
                existing_versions.append(int(version_text))
            except ValueError:
                continue
        next_number = (max(existing_versions) + 1) if existing_versions else 1
        return f"v{next_number}_{_now_utc():%Y-%m}"

    def train(self, dataset: Any) -> dict[str, Any]:
        rows = self._normalise_training_rows(dataset)
        if len(rows) < 2:
            raise ValueError("At least two training rows are required")

        x_values, y_values = self._feature_matrix(rows)
        if len(set(y_values)) < 2:
            model = DummyClassifier(strategy="most_frequent")
            model.fit(x_values, y_values)
            x_train = x_test = x_values
            y_train = y_test = y_values
        elif len(rows) < 5:
            model = RandomForestClassifier(
                n_estimators=200,
                random_state=42,
                class_weight="balanced_subsample",
                n_jobs=-1,
            )
            model.fit(x_values, y_values)
            x_train = x_test = x_values
            y_train = y_test = y_values
        else:
            stratify: list[int] | None = y_values if len(set(y_values)) > 1 else None
            x_train, x_test, y_train, y_test = train_test_split(
                x_values,
                y_values,
                test_size=0.2,
                random_state=42,
                stratify=stratify,
            )

            model = RandomForestClassifier(
                n_estimators=200,
                random_state=42,
                class_weight="balanced_subsample",
                n_jobs=-1,
            )
            model.fit(x_train, y_train)

        y_pred = model.predict(x_test)
        probabilities = model.predict_proba(x_test)[:, 1] if len(set(y_values)) > 1 and hasattr(model, "predict_proba") else None
        accuracy = float(accuracy_score(y_test, y_pred))
        f1 = float(f1_score(y_test, y_pred, zero_division=0))
        roc_auc = float(roc_auc_score(y_test, probabilities)) if probabilities is not None and len(set(y_values)) > 1 else None

        self.model = model
        self.version = self._next_version()
        self.metrics = {"accuracy": accuracy, "f1": f1}
        if roc_auc is not None:
            self.metrics["roc_auc"] = roc_auc
        if hasattr(model, "feature_importances_"):
            self.feature_importances = {
                column: float(importance)
                for column, importance in zip(self.feature_columns, model.feature_importances_, strict=True)
            }
        else:
            self.feature_importances = {column: 0.0 for column in self.feature_columns}

        artifact_path = self.model_directory / f"model_{self.version}.pkl"
        _dump_artifact(
            {
                "model": model,
                "version": self.version,
                "metrics": self.metrics,
                "feature_columns": list(self.feature_columns),
                "feature_importances": self.feature_importances,
            },
            artifact_path,
        )

        logger.info("Demand reroute model trained", extra={"version": self.version, "metrics": self.metrics})
        return {
            "version": self.version,
            "artifact_path": str(artifact_path),
            "metrics": self.metrics,
            "feature_importances": self.feature_importances,
        }

    def evaluate(self) -> dict[str, Any]:
        """Return the most recent hold-out metrics."""

        return {
            "version": self.version,
            "metrics": self.metrics,
            "feature_importances": self.feature_importances,
        }

    def predict(self, segment_data: dict[str, Any]) -> float:
        """Return the probability that a segment is high demand."""

        if self.model is None:
            return 0.0
        row = self._normalise_training_rows([segment_data])[0]
        feature_row = [[float(row[column]) for column in self.feature_columns]]
        probability = self.model.predict_proba(feature_row)[0][1]
        return float(probability)

    def save_registry(self, artifact_path: Path, promoted: bool = True) -> None:
        payload = {
            "version": self.version,
            "artifact_path": str(artifact_path),
            "metrics": self.metrics,
            "promoted": promoted,
            "timestamp": _now_utc().isoformat(),
        }
        self.registry_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @classmethod
    def load_active_model(cls, model_directory: Path | None = None) -> "DemandRerouteModel | None":
        directory = model_directory or settings.model_directory
        registry_path = directory / settings.REROUTING_MODEL_REGISTRY_FILE
        if not registry_path.exists():
            return None

        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            artifact_path = Path(registry["artifact_path"])
            bundle = _load_artifact(artifact_path)
        except Exception as exc:  # pragma: no cover - defensive load path
            logger.warning("Failed to load active reroute model", exc_info=exc)
            return None

        model = cls(model_directory=directory)
        model.model = bundle.get("model")
        model.version = bundle.get("version")
        model.metrics = dict(bundle.get("metrics") or {})
        model.feature_importances = dict(bundle.get("feature_importances") or {})
        return model


class SegmentScorer:
    """Score road segments using the active ML model or a deterministic fallback."""

    def __init__(self, model: DemandRerouteModel | None = None) -> None:
        self.model = model

    def score_segment(self, segment_data: dict[str, Any]) -> float:
        speed = _safe_float(segment_data.get("avg_speed") or segment_data.get("speed"))
        congestion_score = _safe_float(segment_data.get("congestion_score"))
        if self.model is None or self.model.model is None:
            if speed < settings.REROUTING_LOW_SPEED_THRESHOLD_KPH:
                return 1.0
            return min(1.0, 0.35 + (congestion_score * 0.65))

        demand_probability = self.model.predict(segment_data)
        speed_penalty = 1.0 if speed < settings.REROUTING_LOW_SPEED_THRESHOLD_KPH else 0.0
        return min(1.0, (0.65 * demand_probability) + (0.25 * congestion_score) + (0.10 * speed_penalty))


class ReroutingEngine:
    """Compute alternative routes using an OSM graph when available."""

    def __init__(self, scorer: SegmentScorer) -> None:
        self.scorer = scorer
        self.graph: Any | None = self._load_graph()

    def _load_graph(self) -> Any | None:
        if ox is None or nx is None:
            logger.warning("osmnx is not installed; rerouting will use fallback geometry only")
            return None

        try:
            graph = ox.graph_from_place(
                settings.REROUTING_OSMNX_PLACE_NAME,
                network_type=settings.REROUTING_GRAPH_NETWORK_TYPE,
                simplify=True,
            )
            logger.info("Loaded road graph for rerouting", extra={"place": settings.REROUTING_OSMNX_PLACE_NAME})
            return graph
        except Exception as exc:  # pragma: no cover - depends on internet and OSM availability
            logger.warning("Falling back to geometry-only rerouting", exc_info=exc)
            return None

    def _route_polyline_from_stops(self, route: Route) -> list[list[float]]:
        polyline = [[stop.stop.latitude, stop.stop.longitude] for stop in route.route_stops]
        return polyline or []

    def _score_graph_edges(self, graph: Any, segment_data: dict[str, Any]) -> None:
        if nx is None:
            return
        for u_node, v_node, key, edge_data in graph.edges(keys=True, data=True):
            length_km = _safe_float(edge_data.get("length"), default=0.0) / 1000.0
            edge_speed = _safe_float(edge_data.get("speed_kph") or edge_data.get("maxspeed"), default=_safe_float(segment_data.get("avg_speed"), 20.0))
            pseudo_segment = {
                **segment_data,
                "avg_speed": edge_speed,
                "mileage": length_km,
                "congestion_score": length_km / max(edge_speed, 1.0),
                "latitude": _safe_float(edge_data.get("y", segment_data.get("latitude"))),
                "longitude": _safe_float(edge_data.get("x", segment_data.get("longitude"))),
            }
            weight = max(0.1, (length_km / max(edge_speed, 1.0)) * (1.0 + self.scorer.score_segment(pseudo_segment)))
            graph[u_node][v_node][key]["rerouting_weight"] = weight

    def compute_alternative_route(
        self,
        route: Route,
        origin: tuple[float, float],
        destination: tuple[float, float],
        segment_data: dict[str, Any],
        trigger_reason: str,
    ) -> dict[str, Any]:
        if self.graph is None or ox is None or nx is None:
            polyline = self._route_polyline_from_stops(route)
            if not polyline:
                polyline = [[origin[0], origin[1]], [destination[0], destination[1]]]
            return {
                "new_route_polyline": polyline,
                "estimated_time_saving_minutes": 0.0,
                "confidence_score": 0.35,
                "trigger_reason": trigger_reason,
            }

        working_graph = self.graph.copy()
        self._score_graph_edges(working_graph, segment_data)

        try:
            origin_node = ox.distance.nearest_nodes(working_graph, X=origin[1], Y=origin[0])
            destination_node = ox.distance.nearest_nodes(working_graph, X=destination[1], Y=destination[0])
            path = nx.shortest_path(working_graph, origin_node, destination_node, weight="rerouting_weight")
            points: list[list[float]] = []
            for node_id in path:
                node_data = working_graph.nodes[node_id]
                points.append([float(node_data["y"]), float(node_data["x"])])
            if len(points) < 2:
                points = [[origin[0], origin[1]], [destination[0], destination[1]]]
            baseline_minutes = _safe_float(segment_data.get("estimated_time_minutes"), default=10.0)
            rerouted_minutes = max(1.0, baseline_minutes * 0.8)
            time_saving = max(0.0, baseline_minutes - rerouted_minutes)
            confidence = min(0.99, max(0.4, 0.5 + (time_saving / max(baseline_minutes, 1.0)) / 2.0))
            return {
                "new_route_polyline": points,
                "estimated_time_saving_minutes": round(time_saving, 2),
                "confidence_score": round(confidence, 3),
                "trigger_reason": trigger_reason,
            }
        except Exception as exc:  # pragma: no cover - path search may fail for disconnected graphs
            logger.warning("Graph reroute failed; using fallback geometry", exc_info=exc)
            polyline = self._route_polyline_from_stops(route)
            if not polyline:
                polyline = [[origin[0], origin[1]], [destination[0], destination[1]]]
            return {
                "new_route_polyline": polyline,
                "estimated_time_saving_minutes": 0.0,
                "confidence_score": 0.25,
                "trigger_reason": trigger_reason,
            }


@dataclass(slots=True)
class _TripSnapshot:
    trip: ActiveTrip
    bus: Bus
    route: Route
    driver: User
    assignment_event: Event


class ModelRetrainer:
    """Nightly retraining workflow with promotion and rollback retention."""

    def __init__(self, session_factory: Callable[[], Session] = SessionLocal, model_directory: Path | None = None) -> None:
        self.session_factory = session_factory
        self.model_directory = model_directory or settings.model_directory
        self.model_directory.mkdir(parents=True, exist_ok=True)
        self.scheduler = BackgroundScheduler(timezone="UTC")
        self._scheduler_started = False

    def start(self) -> None:
        """Start the APScheduler job if it is not already running."""

        if self._scheduler_started:
            return
        self.scheduler.add_job(
            self.run_scheduled_retraining,
            trigger="cron",
            hour=settings.REROUTING_RETRAIN_HOUR,
            minute=settings.REROUTING_RETRAIN_MINUTE,
            id="rerouting_model_retrain",
            replace_existing=True,
        )
        self.scheduler.start()
        self._scheduler_started = True
        logger.info("Rerouting retraining scheduler started")

    def shutdown(self) -> None:
        if self._scheduler_started:
            self.scheduler.shutdown(wait=False)
            self._scheduler_started = False

    def _latest_retraining_timestamp(self, session: Session) -> datetime | None:
        query = select(func.max(RETRAINING_LOG_TABLE.c.timestamp))
        return session.execute(query).scalar_one_or_none()

    def _active_model_metadata(self) -> dict[str, Any] | None:
        registry_path = self.model_directory / settings.REROUTING_MODEL_REGISTRY_FILE
        if not registry_path.exists():
            return None
        try:
            return json.loads(registry_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _current_accuracy(self) -> float | None:
        active = DemandRerouteModel.load_active_model(self.model_directory)
        if active is None:
            return None
        return active.metrics.get("accuracy")

    def _prune_old_models(self) -> None:
        keep = settings.REROUTING_KEEP_LAST_MODEL_VERSIONS
        artifacts = sorted(self.model_directory.glob("model_v*_*.pkl"), key=lambda path: path.stat().st_mtime, reverse=True)
        for artifact in artifacts[keep:]:
            try:
                artifact.unlink(missing_ok=True)
            except Exception:
                logger.warning("Failed to delete old reroute model artifact", exc_info=True)

    def _build_training_rows(self, rows: list[dict[str, Any]], outcomes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        outcome_map: dict[str, float] = {}
        for outcome in outcomes:
            if _safe_int(outcome.get("accepted")) != 1:
                continue
            reroute_id = str(outcome.get("reroute_id"))
            outcome_map[reroute_id] = _safe_float(outcome.get("actual_time_saving"))

        adjusted_rows: list[dict[str, Any]] = []
        for row in rows:
            record = dict(row)
            if record.get("stop_id") is not None and outcome_map:
                reward = max(outcome_map.values()) if outcome_map else 0.0
                if reward > 0:
                    record["high_demand_segment"] = 1
            adjusted_rows.append(record)
        return adjusted_rows

    def run_retraining(self, manual: bool = False) -> dict[str, Any]:
        """Train a fresh model if enough new rows are available."""

        session = self.session_factory()
        try:
            last_retrain = self._latest_retraining_timestamp(session)
            query = select(func.count()).select_from(TRIP_LOGS_TABLE)
            total_rows = int(session.execute(query).scalar_one())
            rows = _extract_log_rows(session, since=last_retrain)
            new_row_count = len(rows)
            if new_row_count < settings.REROUTING_MIN_ROWS_FOR_RETRAIN and not manual:
                return {
                    "job_id": str(uuid.uuid4()),
                    "status": "skipped",
                    "reason": "insufficient_new_rows",
                    "rows_used": new_row_count,
                }

            outcome_rows = [
                dict(row._mapping)
                for row in session.execute(select(REROUTE_OUTCOMES_TABLE).where(REROUTE_OUTCOMES_TABLE.c.timestamp >= (last_retrain or datetime.min.replace(tzinfo=UTC)))).all()
            ]
            training_rows = self._build_training_rows(rows, outcome_rows)

            current_accuracy = self._current_accuracy()
            current_model = DemandRerouteModel.load_active_model(self.model_directory)
            model = DemandRerouteModel(model_directory=self.model_directory)
            training_result = model.train(training_rows)
            accuracy_after = float(training_result["metrics"].get("accuracy", 0.0))
            accuracy_before = float(current_accuracy) if current_accuracy is not None else 0.0
            promoted = accuracy_after > accuracy_before

            artifact_path = Path(training_result["artifact_path"])
            if promoted:
                model.save_registry(artifact_path, promoted=True)
            elif current_model is not None:
                # Keep the newly trained artifact for rollback, but leave the current one active.
                model.save_registry(Path(self._active_model_metadata()["artifact_path"]), promoted=False)  # type: ignore[index]

            self._prune_old_models()

            log_row = {
                "id": str(uuid.uuid4()),
                "rows_used": new_row_count,
                "accuracy_before": accuracy_before,
                "accuracy_after": accuracy_after,
                "promoted": promoted,
                "model_version": training_result["version"],
                "message": "manual" if manual else "scheduled",
                "timestamp": _now_utc(),
            }
            session.execute(insert(RETRAINING_LOG_TABLE).values(**log_row))
            session.commit()

            return {
                "job_id": log_row["id"],
                "status": "promoted" if promoted else "trained",
                "rows_used": new_row_count,
                "accuracy_before": accuracy_before,
                "accuracy_after": accuracy_after,
                "promoted": promoted,
                "model_version": training_result["version"],
                "feature_importances": training_result["feature_importances"],
            }
        finally:
            session.close()

    def run_scheduled_retraining(self) -> None:
        """Execute the scheduled nightly retraining job."""

        try:
            result = self.run_retraining(manual=False)
            logger.info("Scheduled rerouting retraining finished", extra=result)
        except Exception as exc:  # pragma: no cover - background job logging only
            logger.error("Scheduled rerouting retraining failed", exc_info=exc)


class ReroutingPipeline:
    """Facade that selects the active phase and routes all rerouting actions."""

    def __init__(self, model_directory: Path | None = None) -> None:
        self.model_directory = model_directory or settings.model_directory
        self.model_directory.mkdir(parents=True, exist_ok=True)
        self.active_model = DemandRerouteModel.load_active_model(self.model_directory)
        self.scorer = SegmentScorer(self.active_model)
        self.engine = ReroutingEngine(self.scorer)
        self.retrainer = ModelRetrainer(model_directory=self.model_directory)

    def start_background_jobs(self) -> None:
        """Start the nightly retraining scheduler."""

        self.retrainer.start()

    def shutdown(self) -> None:
        """Shut down the background scheduler."""

        self.retrainer.shutdown()

    def ensure_tables(self, engine: Engine) -> None:
        """Create rerouting tables if they do not already exist."""

        rerouting_metadata.create_all(bind=engine)

    def phase(self, session: Session) -> int:
        """Return the active system phase based on collected trip logs."""

        rows_collected = int(session.execute(select(func.count()).select_from(TRIP_LOGS_TABLE)).scalar_one())
        if rows_collected < settings.REROUTING_MIN_ROWS_FOR_PHASE_TRANSITION:
            return 1
        if session.execute(select(func.count()).select_from(RETRAINING_LOG_TABLE)).scalar_one() > 0:
            return 3
        return 2

    def model_status(self, session: Session) -> dict[str, Any]:
        """Return a status snapshot for the rerouting ML lifecycle."""

        rows_collected = int(session.execute(select(func.count()).select_from(TRIP_LOGS_TABLE)).scalar_one())
        last_retrain = session.execute(select(func.max(RETRAINING_LOG_TABLE.c.timestamp))).scalar_one_or_none()
        active_model = DemandRerouteModel.load_active_model(self.model_directory)
        phase = self.phase(session)
        return {
            "phase": phase,
            "model_version": active_model.version if active_model else None,
            "accuracy": active_model.metrics.get("accuracy") if active_model else None,
            "rows_collected": rows_collected,
            "rows_needed_for_next_phase": max(0, settings.REROUTING_MIN_ROWS_FOR_PHASE_TRANSITION - rows_collected),
            "last_retrain_timestamp": last_retrain.isoformat() if last_retrain else None,
        }

    def list_route_logs(
        self,
        session: Session,
        route_id: str,
        date_from: datetime | None,
        date_to: datetime | None,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        """Return paginated trip log rows for a route."""

        filters = [TRIP_LOGS_TABLE.c.route_id == route_id]
        if date_from is not None:
            filters.append(TRIP_LOGS_TABLE.c.timestamp >= _as_timezone_aware(date_from))
        if date_to is not None:
            filters.append(TRIP_LOGS_TABLE.c.timestamp <= _as_timezone_aware(date_to))

        base_query = select(TRIP_LOGS_TABLE).where(*filters)
        total = int(session.execute(select(func.count()).select_from(base_query.subquery())).scalar_one())
        offset = max(page - 1, 0) * page_size
        rows = [dict(row._mapping) for row in session.execute(base_query.order_by(TRIP_LOGS_TABLE.c.timestamp.desc()).offset(offset).limit(page_size)).all()]
        return {
            "items": rows,
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    def manual_retrain(self) -> dict[str, Any]:
        """Trigger retraining outside the scheduled background job."""

        return self.retrainer.run_retraining(manual=True)

    def _get_bus(self, session: Session, bus_id: str) -> Bus:
        bus = session.get(Bus, bus_id)
        if bus is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bus not found")
        return bus

    def _get_route(self, session: Session, route_id: str) -> Route:
        route = session.get(Route, route_id)
        if route is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")
        return route

    def _get_assignment_event(self, session: Session, assignment_id: str) -> Event:
        event = session.get(Event, assignment_id)
        if event is None or event.event_type != EventType.ROUTE_ASSIGNED:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
        return event

    def _active_trip_for_bus(self, session: Session, bus_id: str) -> ActiveTrip | None:
        query = select(ActiveTrip).where(ActiveTrip.vehicle_id == bus_id, ActiveTrip.status == TripStatus.ACTIVE)
        return session.execute(query).scalar_one_or_none()

    def assign_route(self, session: Session, bus_id: str, route_id: str, driver_id: str, scheduled_start: datetime) -> dict[str, Any]:
        """Assign a fixed route to a bus before the trip starts."""

        bus = self._get_bus(session, bus_id)
        route = self._get_route(session, route_id)
        driver = session.get(User, driver_id)
        if driver is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found")
        if self._active_trip_for_bus(session, bus_id) is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bus already has an active trip")

        bus.route_id = route.id
        session.add(bus)
        assignment = EventService.write_event(
            session,
            event_type=EventType.ROUTE_ASSIGNED,
            user_id=driver_id,
            route_id=route.id,
            metadata={
                "bus_id": bus_id,
                "driver_id": driver_id,
                "scheduled_start": _as_timezone_aware(scheduled_start).isoformat(),
            },
        )
        session.commit()
        return {
            "assignment_id": assignment.id,
            "route": {
                "id": route.id,
                "route_code": route.route_code,
                "route_name": route.route_name,
                "distance_km": route.distance_km,
                "price": str(route.price),
            },
        }

    def start_trip(self, session: Session, bus_id: str, driver_id: str, assignment_id: str) -> dict[str, Any]:
        """Deprecated: trip lifecycle is now canonical under GPS tracking.

        Historically this method created an ActiveTrip. Trip lifecycle creation
        should now be performed via the GPS tracking API (`/api/v1/gps/trips/start`).

        If callers still invoke this method it will raise an informative
        exception directing them to the GPS tracking API.
        """

        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=(
                'Deprecated: create driver trips via the GPS tracking API "/api/v1/gps/trips/start" '
                "(the GPS tracking service is the canonical owner of the trip lifecycle)."
            ),
        )

    def _route_stop_sequence(self, session: Session, route_id: str) -> list[RouteStop]:
        query = select(RouteStop).where(RouteStop.route_id == route_id).order_by(RouteStop.sequence.asc())
        return list(session.execute(query).scalars().all())

    def _last_trip_log(self, session: Session, trip_id: str) -> dict[str, Any] | None:
        query = select(TRIP_LOGS_TABLE).where(TRIP_LOGS_TABLE.c.trip_id == trip_id).order_by(TRIP_LOGS_TABLE.c.timestamp.desc())
        row = session.execute(query).first()
        return dict(row._mapping) if row is not None else None

    def _historical_congestion_percentile(self, session: Session, time_range: str) -> float:
        query = select(TRIP_LOGS_TABLE.c.congestion_score).where(TRIP_LOGS_TABLE.c.time_range == time_range)
        scores = [float(value[0]) for value in session.execute(query).all() if value[0] is not None]
        if not scores:
            return 0.0
        scores.sort()
        index = int(math.ceil((settings.REROUTING_CONGESTION_PERCENTILE / 100.0) * len(scores))) - 1
        index = min(max(index, 0), len(scores) - 1)
        return scores[index]

    def _predict_next_stop_demand(self, session: Session, route_id: str, stop_id: str | None, timestamp: datetime, passenger_count: int) -> float:
        if self.active_model is None:
            return min(1.0, passenger_count / max(settings.REROUTING_DEFAULT_BUS_CAPACITY, 1))

        route_stops = self._route_stop_sequence(session, route_id)
        next_stop = None
        if stop_id is not None:
            for index, route_stop in enumerate(route_stops):
                if route_stop.stop_id == stop_id and index + 1 < len(route_stops):
                    next_stop = route_stops[index + 1]
                    break
        if next_stop is None and route_stops:
            next_stop = route_stops[0]
        if next_stop is None:
            return 0.0

        segment = {
            "day_of_week": timestamp.weekday(),
            "time_range_index": _ordinal_time_range(_time_range_label(timestamp)),
            "avg_speed": 0.0,
            "mileage": 0.0,
            "initial_latitude": next_stop.stop.latitude,
            "initial_longitude": next_stop.stop.longitude,
            "month": timestamp.month,
            "passenger_count": passenger_count,
            "congestion_score": passenger_count / max(settings.REROUTING_DEFAULT_BUS_CAPACITY, 1),
        }
        return self.scorer.model.predict(segment) if self.scorer.model else 0.0

    def log_gps_update(
        self,
        session: Session,
        trip_id: str,
        driver_id: str,
        latitude: float,
        longitude: float,
        speed: float,
        passenger_count: int,
        stop_id: str | None = None,
    ) -> dict[str, Any]:
        """Persist a silent trip log entry and decide whether to suggest a reroute."""

        trip = session.get(ActiveTrip, trip_id)
        if trip is None or trip.status != TripStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active trip not found")
        if trip.driver_id != driver_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Trip does not belong to the caller")
        bus_id = trip.vehicle_id
        timestamp = _now_utc()
        last_log = self._last_trip_log(session, trip_id)
        if last_log is None:
            mileage_covered = 0.0
            total_time_seconds = max((timestamp - _as_timezone_aware(trip.started_at)).total_seconds(), 0.0)
        else:
            mileage_covered = float(last_log.get("mileage_covered", 0.0)) + _distance_km(
                float(last_log["latitude"]),
                float(last_log["longitude"]),
                latitude,
                longitude,
            )
            total_time_seconds = max((timestamp - _as_timezone_aware(trip.started_at)).total_seconds(), 0.0)

        congestion_score = mileage_covered / max(total_time_seconds, 1.0)
        time_range = _time_range_label(timestamp)
        trip_log = {
            "id": str(uuid.uuid4()),
            "trip_id": trip_id,
            "bus_id": bus_id,
            "route_id": trip.route_id,
            "driver_id": driver_id,
            "timestamp": timestamp,
            "day_of_week": timestamp.weekday(),
            "time_range": time_range,
            "month": timestamp.month,
            "latitude": latitude,
            "longitude": longitude,
            "speed": speed,
            "mileage_covered": mileage_covered,
            "passenger_count": passenger_count,
            "stop_id": stop_id,
            "total_time_seconds": total_time_seconds,
            "congestion_score": congestion_score,
            "high_demand_segment": 1 if passenger_count > settings.REROUTING_DEFAULT_BUS_CAPACITY * settings.REROUTING_CAPACITY_THRESHOLD else 0,
        }
        session.execute(insert(TRIP_LOGS_TABLE).values(**trip_log))

        route = self._get_route(session, trip.route_id)
        route_stops = self._route_stop_sequence(session, route.id)
        next_stop = None
        for index, route_stop in enumerate(route_stops):
            if stop_id is not None and route_stop.stop_id == stop_id and index + 1 < len(route_stops):
                next_stop = route_stops[index + 1]
                break
        if next_stop is None and route_stops:
            next_stop = route_stops[0]

        predicted_demand = self._predict_next_stop_demand(session, route.id, stop_id, timestamp, passenger_count)
        congestion_threshold = self._historical_congestion_percentile(session, time_range)
        trigger_reason = "demand_and_congestion_threshold" if predicted_demand > settings.REROUTING_CAPACITY_THRESHOLD and congestion_score > congestion_threshold else ""

        reroute_suggested = False
        reroute_id: str | None = None
        new_route: list[list[float]] | None = None

        if self.phase(session) != 1 and trigger_reason:
            origin = (latitude, longitude)
            destination = (
                next_stop.stop.latitude if next_stop is not None else latitude,
                next_stop.stop.longitude if next_stop is not None else longitude,
            )
            route_plan = self.engine.compute_alternative_route(
                route=route,
                origin=origin,
                destination=destination,
                segment_data={
                    "day_of_week": timestamp.weekday(),
                    "time_range_index": _ordinal_time_range(time_range),
                    "avg_speed": speed,
                    "mileage": mileage_covered,
                    "initial_latitude": latitude,
                    "initial_longitude": longitude,
                    "month": timestamp.month,
                    "passenger_count": passenger_count,
                    "congestion_score": congestion_score,
                    "estimated_time_minutes": max(total_time_seconds / 60.0, 1.0),
                },
                trigger_reason=trigger_reason,
            )
            suggestion = {
                "id": str(uuid.uuid4()),
                "trip_id": trip_id,
                "bus_id": bus_id,
                "route_id": route.id,
                "suggested_at": timestamp,
                "current_segment": stop_id,
                "trigger_reason": trigger_reason,
                "new_route_polyline": _serialise_polyline([(point[0], point[1]) for point in route_plan["new_route_polyline"]]),
                "estimated_time_saving_minutes": route_plan["estimated_time_saving_minutes"],
                "confidence_score": route_plan["confidence_score"],
                "accepted": False,
                "feedback_at": None,
                "outcome_recorded": False,
                "status": "suggested",
            }
            session.execute(insert(REROUTE_SUGGESTIONS_TABLE).values(**suggestion))
            reroute_suggested = True
            reroute_id = suggestion["id"]
            new_route = route_plan["new_route_polyline"]

        session.commit()
        return {
            "reroute_suggested": reroute_suggested,
            "reroute_id": reroute_id,
            "new_route": new_route,
        }

    def end_trip(self, session: Session, trip_id: str, final_latitude: float, final_longitude: float) -> dict[str, Any]:
        """Close a trip and summarise logged telemetry."""

        trip = session.get(ActiveTrip, trip_id)
        if trip is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active trip not found")

        rows = [dict(row._mapping) for row in session.execute(select(TRIP_LOGS_TABLE).where(TRIP_LOGS_TABLE.c.trip_id == trip_id).order_by(TRIP_LOGS_TABLE.c.timestamp.asc())).all()]
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No trip logs were recorded")

        started_at = _as_timezone_aware(trip.started_at)
        ended_at = _now_utc()
        total_time_seconds = max((ended_at - started_at).total_seconds(), 0.0)
        total_distance_km = float(rows[-1]["mileage_covered"])
        avg_speed_kph = (total_distance_km / max(total_time_seconds / 3600.0, 1e-6)) if total_time_seconds > 0 else 0.0
        stops_served = len({row.get("stop_id") for row in rows if row.get("stop_id")})

        trip.status = TripStatus.COMPLETED
        trip.ended_at = ended_at
        session.add(trip)
        session.commit()

        return {
            "trip_id": trip_id,
            "total_time_seconds": total_time_seconds,
            "total_distance_km": total_distance_km,
            "avg_speed_kph": avg_speed_kph,
            "stops_served": stops_served,
            "final_latitude": final_latitude,
            "final_longitude": final_longitude,
        }

    def record_feedback(self, session: Session, reroute_id: str, accepted: bool) -> dict[str, Any]:
        """Store the driver's reroute decision."""

        row = session.execute(select(REROUTE_SUGGESTIONS_TABLE).where(REROUTE_SUGGESTIONS_TABLE.c.id == reroute_id)).first()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reroute suggestion not found")

        session.execute(
            update(REROUTE_SUGGESTIONS_TABLE)
            .where(REROUTE_SUGGESTIONS_TABLE.c.id == reroute_id)
            .values(
                accepted=accepted,
                feedback_at=_now_utc(),
                status="accepted" if accepted else "rejected",
            )
        )
        session.commit()
        return {"acknowledged": True}

    def record_outcome(self, session: Session, reroute_id: str, actual_time_saving: float) -> dict[str, Any]:
        """Persist the measured outcome for an accepted reroute."""

        suggestion_row = session.execute(select(REROUTE_SUGGESTIONS_TABLE).where(REROUTE_SUGGESTIONS_TABLE.c.id == reroute_id)).first()
        if suggestion_row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reroute suggestion not found")

        suggestion = dict(suggestion_row._mapping)
        outcome = {
            "id": str(uuid.uuid4()),
            "reroute_id": reroute_id,
            "bus_id": suggestion["bus_id"],
            "accepted": bool(suggestion["accepted"]),
            "actual_time_saving": actual_time_saving,
            "timestamp": _now_utc(),
        }
        session.execute(insert(REROUTE_OUTCOMES_TABLE).values(**outcome))
        session.execute(
            update(REROUTE_SUGGESTIONS_TABLE)
            .where(REROUTE_SUGGESTIONS_TABLE.c.id == reroute_id)
            .values(outcome_recorded=True)
        )
        session.commit()
        return {"recorded": True}

    def stop_demand(self, session: Session, stop_id: str) -> dict[str, Any]:
        """Return a short-horizon commuter demand estimate for a stop."""

        stop = session.get(Stop, stop_id)
        if stop is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stop not found")

        now = _now_utc()
        windows: list[dict[str, Any]] = []
        for index in range(settings.REROUTING_PREDICTION_WINDOWS):
            window_time = now + timedelta(minutes=index * settings.REROUTING_DEFAULT_TIME_WINDOW_MINUTES)
            segment = {
                "day_of_week": window_time.weekday(),
                "time_range_index": _ordinal_time_range(_time_range_label(window_time)),
                "avg_speed": settings.REROUTING_LOW_SPEED_THRESHOLD_KPH,
                "mileage": 0.0,
                "initial_latitude": stop.latitude,
                "initial_longitude": stop.longitude,
                "month": window_time.month,
                "passenger_count": 0,
                "congestion_score": 0.0,
            }
            demand = self.scorer.model.predict(segment) if self.scorer.model else 0.0
            windows.append({"time_window": window_time.isoformat(), "predicted_demand": round(float(demand), 3)})

        return {
            "stop_id": stop_id,
            "predicted_demand_windows": windows,
            "current_congestion_score": 0.0,
            "estimated_wait_time_minutes": settings.REROUTING_DEFAULT_TIME_WINDOW_MINUTES,
        }


def simulate_rerouting_pipeline() -> dict[str, Any]:
    """Run a small end-to-end simulation for the __main__ smoke path."""

    pipeline = ReroutingPipeline()
    session = SessionLocal()
    try:
        result: dict[str, Any] = {"phase1_logs": [], "training": None, "reroute": None, "feedback": None, "outcome": None}
        phase_trip_id = str(uuid.uuid4())
        bus_id = str(uuid.uuid4())
        driver_id = str(uuid.uuid4())
        route_id = str(uuid.uuid4())
        assignment_id = str(uuid.uuid4())

        # Phase 1 simulation: silent trip logs.
        for _ in range(10):
            result["phase1_logs"].append(
                {
                    "trip_id": phase_trip_id,
                    "bus_id": bus_id,
                    "driver_id": driver_id,
                    "route_id": route_id,
                }
            )

        # Phase 2 simulation: train on dummy rows.
        dummy_rows = [
            {
                "day_of_week": 0,
                "time_range": "06-10",
                "avg_speed": 18.0,
                "mileage": 6.2,
                "initial_latitude": 9.03,
                "initial_longitude": 38.74,
                "month": 5,
                "passenger_count": 48,
                "congestion_score": 0.42,
                "high_demand_segment": 1,
            },
            {
                "day_of_week": 2,
                "time_range": "10-16",
                "avg_speed": 24.0,
                "mileage": 4.9,
                "initial_latitude": 9.01,
                "initial_longitude": 38.76,
                "month": 5,
                "passenger_count": 12,
                "congestion_score": 0.18,
                "high_demand_segment": 0,
            },
            {
                "day_of_week": 3,
                "time_range": "16-20",
                "avg_speed": 11.0,
                "mileage": 8.1,
                "initial_latitude": 9.02,
                "initial_longitude": 38.75,
                "month": 5,
                "passenger_count": 55,
                "congestion_score": 0.88,
                "high_demand_segment": 1,
            },
            {
                "day_of_week": 4,
                "time_range": "20-24",
                "avg_speed": 27.0,
                "mileage": 3.4,
                "initial_latitude": 9.00,
                "initial_longitude": 38.73,
                "month": 5,
                "passenger_count": 8,
                "congestion_score": 0.12,
                "high_demand_segment": 0,
            },
        ]
        model = DemandRerouteModel()
        result["training"] = model.train(dummy_rows)

        # Phase 2/3 simulation: score a reroute and record feedback/outcome.
        scorer = SegmentScorer(model)
        engine = ReroutingEngine(scorer)
        fallback_route = Route(route_code="SIM", route_name="Simulation Route", price=0, distance_km=1.0)
        reroute = engine.compute_alternative_route(
            route=fallback_route,
            origin=(9.03, 38.74),
            destination=(9.05, 38.78),
            segment_data={
                "day_of_week": 0,
                "time_range_index": 1,
                "avg_speed": 10.0,
                "mileage": 5.0,
                "initial_latitude": 9.03,
                "initial_longitude": 38.74,
                "month": 5,
                "passenger_count": 52,
                "congestion_score": 0.9,
                "estimated_time_minutes": 18.0,
            },
            trigger_reason="simulation",
        )
        result["reroute"] = reroute
        result["feedback"] = {"reroute_id": str(uuid.uuid4()), "accepted": True}
        result["outcome"] = {"reroute_id": result["feedback"]["reroute_id"], "actual_time_saving": 4.5}
        result["assignment_id"] = assignment_id
        return result
    finally:
        session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    simulation = simulate_rerouting_pipeline()
    print(json.dumps(simulation, indent=2, default=str))
