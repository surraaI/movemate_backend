"""add bus tables manually

Revision ID: 18627572dfbd
Revises: cc72c42fd90d
Create Date: 2026-05-10 19:11:55.361904

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '18627572dfbd'
down_revision: Union[str, None] = 'cc72c42fd90d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "buses",
        sa.Column("bus_id", sa.String(length=36), primary_key=True),
        sa.Column("route_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
    )

    op.create_table(
        "locations",
        sa.Column("location_id", sa.String(length=36), primary_key=True),
        sa.Column("bus_id", sa.String(length=36), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "eta_predictions",
        sa.Column("eta_id", sa.String(length=36), primary_key=True),
        sa.Column("bus_id", sa.String(length=36), nullable=False),
        sa.Column("stop_id", sa.String(length=36), nullable=False),
        sa.Column("predicted_arrival", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delay_minutes", sa.Integer(), nullable=False, server_default="0"),
    )

def downgrade() -> None:
    op.drop_table("eta_predictions")
    op.drop_table("locations")
    op.drop_table("buses")
