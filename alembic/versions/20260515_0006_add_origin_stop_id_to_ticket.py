"""Add origin_stop_id to Ticket model.

Revision ID: 20260515_0006
Revises: 20260515_0005
Create Date: 2026-05-15 17:11:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260515_0006'
down_revision = '20260515_0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('tickets', sa.Column('origin_stop_id', sa.String(36), nullable=True))
    op.create_index(op.f('ix_tickets_origin_stop_id'), 'tickets', ['origin_stop_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_tickets_origin_stop_id'), table_name='tickets')
    op.drop_column('tickets', 'origin_stop_id')
