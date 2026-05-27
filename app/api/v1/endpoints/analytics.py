from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.analytics import (
    DashboardSummaryOut,
    DemandHeatmapOut,
    DemandSpikesOut,
    ETAAccuracyBreakdownOut,
    ReroutingEffectivenessOut,
    RoutePerformanceOut,
    SystemHealthOut,
)
from app.services.analytics_service import AnalyticsService

router = APIRouter()


def _default_period(days: int = 7) -> tuple[datetime, datetime]:
    period_end = datetime.now(UTC)
    period_start = period_end - timedelta(days=days)
    return period_start, period_end


@router.get("/dashboard-summary", response_model=DashboardSummaryOut)
def dashboard_summary(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN))],
) -> DashboardSummaryOut:
    service = AnalyticsService(db)
    return DashboardSummaryOut(**service.get_dashboard_summary())


@router.get("/route-performance", response_model=RoutePerformanceOut)
def route_performance(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN))],
    period_start: datetime | None = Query(default=None),
    period_end: datetime | None = Query(default=None),
) -> RoutePerformanceOut:
    start, end = _default_period(7)
    result = AnalyticsService(db).get_route_performance(period_start or start, period_end or end)
    return RoutePerformanceOut(**result)


@router.get("/demand-heatmap", response_model=DemandHeatmapOut)
def demand_heatmap(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN))],
    period_start: datetime | None = Query(default=None),
    period_end: datetime | None = Query(default=None),
) -> DemandHeatmapOut:
    start, end = _default_period(7)
    result = AnalyticsService(db).get_demand_heatmap(period_start or start, period_end or end)
    return DemandHeatmapOut(**result)


@router.get("/demand-spikes", response_model=DemandSpikesOut)
def current_demand_spikes(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN))],
) -> DemandSpikesOut:
    result = AnalyticsService(db).get_current_demand_spikes(threshold_multiplier=1.4)
    return DemandSpikesOut(**result)


@router.get("/rerouting-history", response_model=ReroutingEffectivenessOut)
def rerouting_history(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN))],
    period_start: datetime | None = Query(default=None),
    period_end: datetime | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
) -> ReroutingEffectivenessOut:
    start, end = _default_period(30)
    result = AnalyticsService(db).get_rerouting_history(period_start or start, period_end or end, limit=limit)
    return ReroutingEffectivenessOut(**result)


@router.get("/eta-accuracy", response_model=ETAAccuracyBreakdownOut)
def eta_accuracy_breakdown(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN))],
    period_start: datetime | None = Query(default=None),
    period_end: datetime | None = Query(default=None),
) -> ETAAccuracyBreakdownOut:
    start, end = _default_period(7)
    result = AnalyticsService(db).get_eta_accuracy_breakdown(period_start or start, period_end or end)
    return ETAAccuracyBreakdownOut(**result)


@router.get("/system-health", response_model=SystemHealthOut)
def system_health_metrics(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN))],
    window_hours: int = Query(default=24, ge=1, le=168),
) -> SystemHealthOut:
    result = AnalyticsService(db).get_system_health_metrics(window_hours=window_hours)
    return SystemHealthOut(**result)
