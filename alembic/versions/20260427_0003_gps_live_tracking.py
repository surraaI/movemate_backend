"""gps live tracking foundation

Revision ID: 20260427_0003
Revises: 20260421_0002
Create Date: 2026-04-27 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260427_0003"
down_revision = "20260421_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "active_trips",
        sa.Column("trip_id", sa.String(length=36), nullable=False),
        sa.Column("route_id", sa.String(length=36), nullable=False),
        sa.Column("driver_id", sa.String(length=36), nullable=False),
        sa.Column("vehicle_id", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "COMPLETED", "CANCELLED", name="tripstatus", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["driver_id"], ["users.user_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["route_id"], ["routes.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("trip_id"),
    )
    op.create_index(op.f("ix_active_trips_driver_id"), "active_trips", ["driver_id"], unique=False)
    op.create_index(op.f("ix_active_trips_route_id"), "active_trips", ["route_id"], unique=False)
    op.create_index(op.f("ix_active_trips_vehicle_id"), "active_trips", ["vehicle_id"], unique=False)

    op.create_table(
        "bus_current_locations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("trip_id", sa.String(length=36), nullable=False),
        sa.Column("route_id", sa.String(length=36), nullable=False),
        sa.Column("vehicle_id", sa.String(length=64), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("speed_kph", sa.Float(), nullable=True),
        sa.Column("heading_degrees", sa.Integer(), nullable=True),
        sa.Column("gps_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["route_id"], ["routes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["trip_id"], ["active_trips.trip_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trip_id", name="uq_bus_current_locations_trip_id"),
        sa.UniqueConstraint("vehicle_id", name="uq_bus_current_locations_vehicle_id"),
    )
    op.create_index(op.f("ix_bus_current_locations_gps_timestamp"), "bus_current_locations", ["gps_timestamp"], unique=False)
    op.create_index(op.f("ix_bus_current_locations_route_id"), "bus_current_locations", ["route_id"], unique=False)
    op.create_index(op.f("ix_bus_current_locations_trip_id"), "bus_current_locations", ["trip_id"], unique=False)
    op.create_index(op.f("ix_bus_current_locations_vehicle_id"), "bus_current_locations", ["vehicle_id"], unique=False)

    op.create_table(
        "bus_location_history",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("trip_id", sa.String(length=36), nullable=False),
        sa.Column("route_id", sa.String(length=36), nullable=False),
        sa.Column("vehicle_id", sa.String(length=64), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("speed_kph", sa.Float(), nullable=True),
        sa.Column("heading_degrees", sa.Integer(), nullable=True),
        sa.Column("gps_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["route_id"], ["routes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["trip_id"], ["active_trips.trip_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bus_location_history_gps_timestamp"), "bus_location_history", ["gps_timestamp"], unique=False)
    op.create_index(op.f("ix_bus_location_history_route_id"), "bus_location_history", ["route_id"], unique=False)
    op.create_index(op.f("ix_bus_location_history_trip_id"), "bus_location_history", ["trip_id"], unique=False)
    op.create_index(op.f("ix_bus_location_history_vehicle_id"), "bus_location_history", ["vehicle_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_bus_location_history_vehicle_id"), table_name="bus_location_history")
    op.drop_index(op.f("ix_bus_location_history_trip_id"), table_name="bus_location_history")
    op.drop_index(op.f("ix_bus_location_history_route_id"), table_name="bus_location_history")
    op.drop_index(op.f("ix_bus_location_history_gps_timestamp"), table_name="bus_location_history")
    op.drop_table("bus_location_history")

    op.drop_index(op.f("ix_bus_current_locations_vehicle_id"), table_name="bus_current_locations")
    op.drop_index(op.f("ix_bus_current_locations_trip_id"), table_name="bus_current_locations")
    op.drop_index(op.f("ix_bus_current_locations_route_id"), table_name="bus_current_locations")
    op.drop_index(op.f("ix_bus_current_locations_gps_timestamp"), table_name="bus_current_locations")
    op.drop_table("bus_current_locations")

    op.drop_index(op.f("ix_active_trips_vehicle_id"), table_name="active_trips")
    op.drop_index(op.f("ix_active_trips_route_id"), table_name="active_trips")
    op.drop_index(op.f("ix_active_trips_driver_id"), table_name="active_trips")
    op.drop_table("active_trips")
