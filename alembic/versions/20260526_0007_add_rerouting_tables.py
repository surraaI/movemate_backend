"""Add rerouting tables for trip logging and retraining.

Revision ID: 20260526_0007
Revises: add_price_to_routes, 20260515_0006
Create Date: 2026-05-26 08:45:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260526_0007'
down_revision: Union[str, tuple[str, ...], None] = ('add_price_to_routes', '20260515_0006')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'trip_logs',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('trip_id', sa.String(36), nullable=False),
        sa.Column('bus_id', sa.String(36), nullable=False),
        sa.Column('route_id', sa.String(36), nullable=False),
        sa.Column('driver_id', sa.String(36), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('day_of_week', sa.Integer(), nullable=False),
        sa.Column('time_range', sa.String(32), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('speed', sa.Float(), nullable=True),
        sa.Column('mileage_covered', sa.Float(), nullable=False, server_default='0'),
        sa.Column('passenger_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('stop_id', sa.String(36), nullable=True),
        sa.Column('total_time_seconds', sa.Float(), nullable=False, server_default='0'),
        sa.Column('congestion_score', sa.Float(), nullable=False, server_default='0'),
        sa.Column('high_demand_segment', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['trip_id'], ['active_trips.trip_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['bus_id'], ['buses.bus_id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['route_id'], ['routes.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['driver_id'], ['users.user_id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_trip_logs_trip_id'), 'trip_logs', ['trip_id'], unique=False)
    op.create_index(op.f('ix_trip_logs_bus_id'), 'trip_logs', ['bus_id'], unique=False)
    op.create_index(op.f('ix_trip_logs_route_id'), 'trip_logs', ['route_id'], unique=False)
    op.create_index(op.f('ix_trip_logs_driver_id'), 'trip_logs', ['driver_id'], unique=False)
    op.create_index(op.f('ix_trip_logs_timestamp'), 'trip_logs', ['timestamp'], unique=False)
    op.create_index(op.f('ix_trip_logs_stop_id'), 'trip_logs', ['stop_id'], unique=False)

    op.create_table(
        'reroute_suggestions',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('trip_id', sa.String(36), nullable=False),
        sa.Column('bus_id', sa.String(36), nullable=False),
        sa.Column('route_id', sa.String(36), nullable=False),
        sa.Column('suggested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('current_segment', sa.String(255), nullable=True),
        sa.Column('trigger_reason', sa.String(255), nullable=False),
        sa.Column('new_route_polyline', sa.Text(), nullable=False),
        sa.Column('estimated_time_saving_minutes', sa.Float(), nullable=False, server_default='0'),
        sa.Column('confidence_score', sa.Float(), nullable=False, server_default='0'),
        sa.Column('accepted', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('feedback_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('outcome_recorded', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('status', sa.String(32), nullable=False, server_default='suggested'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['trip_id'], ['active_trips.trip_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['bus_id'], ['buses.bus_id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['route_id'], ['routes.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_reroute_suggestions_trip_id'), 'reroute_suggestions', ['trip_id'], unique=False)
    op.create_index(op.f('ix_reroute_suggestions_bus_id'), 'reroute_suggestions', ['bus_id'], unique=False)
    op.create_index(op.f('ix_reroute_suggestions_route_id'), 'reroute_suggestions', ['route_id'], unique=False)
    op.create_index(op.f('ix_reroute_suggestions_suggested_at'), 'reroute_suggestions', ['suggested_at'], unique=False)

    op.create_table(
        'reroute_outcomes',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('reroute_id', sa.String(36), nullable=False),
        sa.Column('bus_id', sa.String(36), nullable=False),
        sa.Column('accepted', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('actual_time_saving', sa.Float(), nullable=False, server_default='0'),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['reroute_id'], ['reroute_suggestions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['bus_id'], ['buses.bus_id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_reroute_outcomes_reroute_id'), 'reroute_outcomes', ['reroute_id'], unique=False)
    op.create_index(op.f('ix_reroute_outcomes_bus_id'), 'reroute_outcomes', ['bus_id'], unique=False)
    op.create_index(op.f('ix_reroute_outcomes_timestamp'), 'reroute_outcomes', ['timestamp'], unique=False)

    op.create_table(
        'retraining_log',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('rows_used', sa.Integer(), nullable=False),
        sa.Column('accuracy_before', sa.Float(), nullable=True),
        sa.Column('accuracy_after', sa.Float(), nullable=True),
        sa.Column('promoted', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('model_version', sa.String(64), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_retraining_log_timestamp'), 'retraining_log', ['timestamp'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_retraining_log_timestamp'), table_name='retraining_log')
    op.drop_table('retraining_log')

    op.drop_index(op.f('ix_reroute_outcomes_timestamp'), table_name='reroute_outcomes')
    op.drop_index(op.f('ix_reroute_outcomes_bus_id'), table_name='reroute_outcomes')
    op.drop_index(op.f('ix_reroute_outcomes_reroute_id'), table_name='reroute_outcomes')
    op.drop_table('reroute_outcomes')

    op.drop_index(op.f('ix_reroute_suggestions_suggested_at'), table_name='reroute_suggestions')
    op.drop_index(op.f('ix_reroute_suggestions_route_id'), table_name='reroute_suggestions')
    op.drop_index(op.f('ix_reroute_suggestions_bus_id'), table_name='reroute_suggestions')
    op.drop_index(op.f('ix_reroute_suggestions_trip_id'), table_name='reroute_suggestions')
    op.drop_table('reroute_suggestions')

    op.drop_index(op.f('ix_trip_logs_stop_id'), table_name='trip_logs')
    op.drop_index(op.f('ix_trip_logs_timestamp'), table_name='trip_logs')
    op.drop_index(op.f('ix_trip_logs_driver_id'), table_name='trip_logs')
    op.drop_index(op.f('ix_trip_logs_route_id'), table_name='trip_logs')
    op.drop_index(op.f('ix_trip_logs_bus_id'), table_name='trip_logs')
    op.drop_index(op.f('ix_trip_logs_trip_id'), table_name='trip_logs')
    op.drop_table('trip_logs')
