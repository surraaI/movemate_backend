"""add price and distance_km to routes table

Revision ID: add_price_to_routes
Revises: 28d3e7981bfd
Create Date: 2026-05-17 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_price_to_routes'
down_revision: Union[str, None] = '28d3e7981bfd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add price column
    op.add_column('routes', sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'))
    # Add distance_km column
    op.add_column('routes', sa.Column('distance_km', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('routes', 'distance_km')
    op.drop_column('routes', 'price')
