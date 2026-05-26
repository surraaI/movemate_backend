"""Add ticket validation timestamp.

Revision ID: 20260526_0008
Revises: 20260526_0007
Create Date: 2026-05-26 12:10:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260526_0008'
down_revision: Union[str, tuple[str, ...], None] = '20260526_0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tickets', sa.Column('validated_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_tickets_validated_at'), 'tickets', ['validated_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_tickets_validated_at'), table_name='tickets')
    op.drop_column('tickets', 'validated_at')