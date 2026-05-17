"""Add events table for activity tracking and analytics.

Revision ID: 20260515_0005
Revises: 20260513_0004
Create Date: 2026-05-15 17:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260515_0005'
down_revision = '20260513_0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'events',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('event_type', sa.String(64), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=True),
        sa.Column('route_id', sa.String(36), nullable=True),
        sa.Column('trip_id', sa.String(36), nullable=True),
        sa.Column('event_metadata', sa.Text(), nullable=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_events_event_type'), 'events', ['event_type'], unique=False)
    op.create_index(op.f('ix_events_user_id'), 'events', ['user_id'], unique=False)
    op.create_index(op.f('ix_events_route_id'), 'events', ['route_id'], unique=False)
    op.create_index(op.f('ix_events_occurred_at'), 'events', ['occurred_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_events_occurred_at'), table_name='events')
    op.drop_index(op.f('ix_events_route_id'), table_name='events')
    op.drop_index(op.f('ix_events_user_id'), table_name='events')
    op.drop_index(op.f('ix_events_event_type'), table_name='events')
    op.drop_table('events')
