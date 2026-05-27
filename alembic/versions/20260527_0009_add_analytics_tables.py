"""Add analytics snapshots and rerouting event logs.

Revision ID: 20260527_0009
Revises: 20260526_0008
Create Date: 2026-05-27 09:40:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260527_0009"
down_revision: Union[str, tuple[str, ...], None] = "20260526_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analytics_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("snapshot_type", sa.String(length=64), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("route_id", sa.String(length=36), nullable=True),
        sa.Column("stop_id", sa.String(length=36), nullable=True),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "snapshot_type",
            "period_start",
            "period_end",
            "route_id",
            "stop_id",
            name="uq_analytics_snapshots_scope",
        ),
    )
    op.create_index(op.f("ix_analytics_snapshots_snapshot_type"), "analytics_snapshots", ["snapshot_type"], unique=False)
    op.create_index(op.f("ix_analytics_snapshots_period_start"), "analytics_snapshots", ["period_start"], unique=False)
    op.create_index(op.f("ix_analytics_snapshots_period_end"), "analytics_snapshots", ["period_end"], unique=False)
    op.create_index(op.f("ix_analytics_snapshots_route_id"), "analytics_snapshots", ["route_id"], unique=False)
    op.create_index(op.f("ix_analytics_snapshots_stop_id"), "analytics_snapshots", ["stop_id"], unique=False)

    op.create_table(
        "analytics_rerouting_event_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("reroute_id", sa.String(length=36), nullable=True),
        sa.Column("route_id", sa.String(length=36), nullable=True),
        sa.Column("trip_id", sa.String(length=36), nullable=True),
        sa.Column("bus_id", sa.String(length=36), nullable=True),
        sa.Column("trigger_reason", sa.String(length=255), nullable=False),
        sa.Column("admin_approved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("approval_actor_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="detected"),
        sa.Column("outcome", sa.String(length=64), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scheduled_outcome_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metrics_payload", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_analytics_rerouting_event_logs_reroute_id"),
        "analytics_rerouting_event_logs",
        ["reroute_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analytics_rerouting_event_logs_route_id"),
        "analytics_rerouting_event_logs",
        ["route_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analytics_rerouting_event_logs_trip_id"),
        "analytics_rerouting_event_logs",
        ["trip_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analytics_rerouting_event_logs_bus_id"),
        "analytics_rerouting_event_logs",
        ["bus_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analytics_rerouting_event_logs_status"),
        "analytics_rerouting_event_logs",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analytics_rerouting_event_logs_detected_at"),
        "analytics_rerouting_event_logs",
        ["detected_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analytics_rerouting_event_logs_scheduled_outcome_check_at"),
        "analytics_rerouting_event_logs",
        ["scheduled_outcome_check_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_analytics_rerouting_event_logs_scheduled_outcome_check_at"),
        table_name="analytics_rerouting_event_logs",
    )
    op.drop_index(op.f("ix_analytics_rerouting_event_logs_detected_at"), table_name="analytics_rerouting_event_logs")
    op.drop_index(op.f("ix_analytics_rerouting_event_logs_status"), table_name="analytics_rerouting_event_logs")
    op.drop_index(op.f("ix_analytics_rerouting_event_logs_bus_id"), table_name="analytics_rerouting_event_logs")
    op.drop_index(op.f("ix_analytics_rerouting_event_logs_trip_id"), table_name="analytics_rerouting_event_logs")
    op.drop_index(op.f("ix_analytics_rerouting_event_logs_route_id"), table_name="analytics_rerouting_event_logs")
    op.drop_index(op.f("ix_analytics_rerouting_event_logs_reroute_id"), table_name="analytics_rerouting_event_logs")
    op.drop_table("analytics_rerouting_event_logs")

    op.drop_index(op.f("ix_analytics_snapshots_stop_id"), table_name="analytics_snapshots")
    op.drop_index(op.f("ix_analytics_snapshots_route_id"), table_name="analytics_snapshots")
    op.drop_index(op.f("ix_analytics_snapshots_period_end"), table_name="analytics_snapshots")
    op.drop_index(op.f("ix_analytics_snapshots_period_start"), table_name="analytics_snapshots")
    op.drop_index(op.f("ix_analytics_snapshots_snapshot_type"), table_name="analytics_snapshots")
    op.drop_table("analytics_snapshots")
