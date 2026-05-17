"""commuter trip GPS for ETA with bus position

Revision ID: 20260513_0004
Revises: 18627572dfbd, 285c7dfa8ff4
Create Date: 2026-05-13 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260513_0004"
down_revision: Union[str, tuple[str, ...], None] = ("18627572dfbd", "285c7dfa8ff4")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
    op.create_index(op.f("ix_commuter_trip_locations_gps_timestamp"), "commuter_trip_locations", ["gps_timestamp"], unique=False)
    op.create_index(op.f("ix_commuter_trip_locations_trip_id"), "commuter_trip_locations", ["trip_id"], unique=False)
    op.create_index(op.f("ix_commuter_trip_locations_user_id"), "commuter_trip_locations", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_commuter_trip_locations_user_id"), table_name="commuter_trip_locations")
    op.drop_index(op.f("ix_commuter_trip_locations_trip_id"), table_name="commuter_trip_locations")
    op.drop_index(op.f("ix_commuter_trip_locations_gps_timestamp"), table_name="commuter_trip_locations")
    op.drop_table("commuter_trip_locations")
