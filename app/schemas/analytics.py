from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class DashboardSummaryOut(BaseModel):
    active_buses: int
    todays_revenue: float
    eta_accuracy_percent: float
    system_health_score: float


class RoutePerformanceItem(BaseModel):
    route_id: str
    route_code: str
    route_name: str
    on_time_rate: float
    average_delay_minutes: float
    total_passengers: int
    total_trips: int


class RoutePerformanceOut(BaseModel):
    period_start: datetime
    period_end: datetime
    routes: list[RoutePerformanceItem]


class DemandHeatmapItem(BaseModel):
    stop_id: str
    stop_name: str
    hour_of_day: int
    demand_count: int


class DemandHeatmapOut(BaseModel):
    period_start: datetime
    period_end: datetime
    heatmap: list[DemandHeatmapItem]


class DemandSpikeItem(BaseModel):
    stop_id: str
    stop_name: str
    current_hour_count: int
    historical_hour_average: float
    spike_ratio: float


class DemandSpikesOut(BaseModel):
    detected_at: datetime
    spikes: list[DemandSpikeItem]


class ReroutingHistoryItem(BaseModel):
    reroute_id: str
    route_id: str
    trip_id: str
    bus_id: str
    trigger_reason: str
    suggested_at: datetime
    admin_approved: bool
    status: str
    outcome_recorded: bool
    actual_time_saving_minutes: float | None


class ReroutingEffectivenessOut(BaseModel):
    period_start: datetime
    period_end: datetime
    total_suggestions: int
    accepted_count: int
    acceptance_rate: float
    outcomes_recorded: int
    effectiveness_rate: float
    average_time_saving_minutes: float
    history: list[ReroutingHistoryItem]


class ETAAccuracyByRouteItem(BaseModel):
    route_id: str
    route_code: str
    route_name: str
    total_predictions: int
    mean_absolute_error_minutes: float
    accuracy_percent: float


class ETAAccuracyBreakdownOut(BaseModel):
    period_start: datetime
    period_end: datetime
    overall_accuracy_percent: float
    mean_absolute_error_minutes: float
    routes: list[ETAAccuracyByRouteItem]


class SystemHealthOut(BaseModel):
    window_start: datetime
    window_end: datetime
    gps_dropout_rate: float
    payment_failure_rate: float
    active_users: int
    system_health_score: float
