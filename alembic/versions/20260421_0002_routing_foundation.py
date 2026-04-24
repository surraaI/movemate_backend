"""routing foundation

Revision ID: 20260421_0002
Revises: 20260415_0001
Create Date: 2026-04-21 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260421_0002"
down_revision = "20260415_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "routes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("route_code", sa.String(length=64), nullable=False),
        sa.Column("route_name", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "INACTIVE", name="routestatus", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_routes_route_code"), "routes", ["route_code"], unique=True)

    op.create_table(
        "stops",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_stops_name"), "stops", ["name"], unique=True)

    op.create_table(
        "route_stops",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("route_id", sa.String(length=36), nullable=False),
        sa.Column("stop_id", sa.String(length=36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["route_id"], ["routes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stop_id"], ["stops.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("route_id", "sequence", name="uq_route_stops_route_sequence"),
        sa.UniqueConstraint("route_id", "stop_id", name="uq_route_stops_route_stop"),
    )

    stop_table = sa.table(
        "stops",
        sa.column("id", sa.String),
        sa.column("name", sa.String),
        sa.column("latitude", sa.Float),
        sa.column("longitude", sa.Float),
    )
    route_table = sa.table(
        "routes",
        sa.column("id", sa.String),
        sa.column("route_code", sa.String),
        sa.column("route_name", sa.String),
        sa.column("status", sa.String),
    )
    route_stop_table = sa.table(
        "route_stops",
        sa.column("id", sa.String),
        sa.column("route_id", sa.String),
        sa.column("stop_id", sa.String),
        sa.column("sequence", sa.Integer),
    )

    op.bulk_insert(
        stop_table,
        [
            {"id": "8e12b291-8d79-43eb-b1e6-42097dd3f2b1", "name": "Megenagna", "latitude": 9.0108, "longitude": 38.7974},
            {"id": "19613ab9-1ff4-4e84-878f-1b85e77f5fd9", "name": "Gurd Shola", "latitude": 9.0196, "longitude": 38.8097},
            {"id": "67b6f0f7-71f0-49de-bdb6-56958bb3f58a", "name": "Kara", "latitude": 9.0415, "longitude": 38.8432},
            {"id": "a768629e-42ca-485a-8b31-b3a17f2e6fce", "name": "Kore Mekanisa", "latitude": 8.9843, "longitude": 38.7448},
            {"id": "6c1a8f7d-dad2-40c8-96ec-a396f550c4ca", "name": "Lideta", "latitude": 9.0047, "longitude": 38.7347},
            {"id": "24a2dd87-52a2-4930-a703-d2b2d6865ae5", "name": "Merkato", "latitude": 9.0355, "longitude": 38.7469},
        ],
    )

    op.bulk_insert(
        route_table,
        [
            {
                "id": "28f11f72-00b5-4552-885d-0f421f04e75f",
                "route_code": "R-001",
                "route_name": "Megenagna to Kara",
                "status": "ACTIVE",
            },
            {
                "id": "32ef7535-d44e-4f3f-a48d-55cd3614d76e",
                "route_code": "R-002",
                "route_name": "Kore Mekanisa to Merkato",
                "status": "ACTIVE",
            },
        ],
    )

    op.bulk_insert(
        route_stop_table,
        [
            {"id": "d99ba6e4-a19f-4460-8b9f-3bbf5f371ef2", "route_id": "28f11f72-00b5-4552-885d-0f421f04e75f", "stop_id": "8e12b291-8d79-43eb-b1e6-42097dd3f2b1", "sequence": 1},
            {"id": "c6adbd45-f5e2-421f-8a0f-3d04cd920f49", "route_id": "28f11f72-00b5-4552-885d-0f421f04e75f", "stop_id": "19613ab9-1ff4-4e84-878f-1b85e77f5fd9", "sequence": 2},
            {"id": "0b3fdcf0-2ddf-4481-a6ea-3d2e8c8f1989", "route_id": "28f11f72-00b5-4552-885d-0f421f04e75f", "stop_id": "67b6f0f7-71f0-49de-bdb6-56958bb3f58a", "sequence": 3},
            {"id": "a5fe445c-1429-4f9e-a36c-707541e65535", "route_id": "32ef7535-d44e-4f3f-a48d-55cd3614d76e", "stop_id": "a768629e-42ca-485a-8b31-b3a17f2e6fce", "sequence": 1},
            {"id": "cc6f5bf9-3211-479e-afac-0855cbf39f53", "route_id": "32ef7535-d44e-4f3f-a48d-55cd3614d76e", "stop_id": "6c1a8f7d-dad2-40c8-96ec-a396f550c4ca", "sequence": 2},
            {"id": "2cee6a9b-f546-4d95-9ff7-3624f477e6f5", "route_id": "32ef7535-d44e-4f3f-a48d-55cd3614d76e", "stop_id": "24a2dd87-52a2-4930-a703-d2b2d6865ae5", "sequence": 3},
        ],
    )


def downgrade() -> None:
    op.drop_table("route_stops")
    op.drop_index(op.f("ix_stops_name"), table_name="stops")
    op.drop_table("stops")
    op.drop_index(op.f("ix_routes_route_code"), table_name="routes")
    op.drop_table("routes")
