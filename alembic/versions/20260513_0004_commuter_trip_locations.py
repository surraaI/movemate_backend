"""commuter trip GPS for ETA with bus position

Revision ID: 20260513_0004
Revises: 28d3e7981bfd
Create Date: 2026-05-13 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260513_0004"
down_revision: Union[str, tuple[str, ...], None] = "28d3e7981bfd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("commuter_trip_locations"):
        op.create_table(
            "commuter_trip_locations",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("trip_id", sa.String(length=36), nullable=False),
            sa.Column("latitude", sa.Float(), nullable=False),
            sa.Column("longitude", sa.Float(), nullable=False),
            sa.Column("gps_timestamp", sa.DateTime(timezone=True), nullable=False),
            sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["trip_id"], ["active_trips.trip_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "trip_id", name="uq_commuter_trip_locations_user_trip"),
        )

    existing_indexes = {index["name"] for index in inspector.get_indexes("commuter_trip_locations")}
    gps_index = op.f("ix_commuter_trip_locations_gps_timestamp")
    trip_index = op.f("ix_commuter_trip_locations_trip_id")
    user_index = op.f("ix_commuter_trip_locations_user_id")

    if gps_index not in existing_indexes:
        op.create_index(gps_index, "commuter_trip_locations", ["gps_timestamp"], unique=False)
    if trip_index not in existing_indexes:
        op.create_index(trip_index, "commuter_trip_locations", ["trip_id"], unique=False)
    if user_index not in existing_indexes:
        op.create_index(user_index, "commuter_trip_locations", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_commuter_trip_locations_user_id"), table_name="commuter_trip_locations")
    op.drop_index(op.f("ix_commuter_trip_locations_trip_id"), table_name="commuter_trip_locations")
    op.drop_index(op.f("ix_commuter_trip_locations_gps_timestamp"), table_name="commuter_trip_locations")
    op.drop_table("commuter_trip_locations")
