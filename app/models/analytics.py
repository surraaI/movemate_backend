from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class AnalyticsSnapshot(Base):
    __tablename__ = "analytics_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_type",
            "period_start",
            "period_end",
            "route_id",
            "stop_id",
            name="uq_analytics_snapshots_scope",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    snapshot_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    route_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    stop_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AnalyticsReroutingEventLog(Base):
    __tablename__ = "analytics_rerouting_event_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    reroute_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    route_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    trip_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    bus_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    trigger_reason: Mapped[str] = mapped_column(String(255), nullable=False)
    admin_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approval_actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="detected", index=True)
    outcome: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    scheduled_outcome_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    outcome_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metrics_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
