"""create all tables with events and origin_stop_id

Revision ID: 28d3e7981bfd
Revises: 
Create Date: 2026-05-15 23:08:57.630742

"""
from typing import Sequence, Union

from alembic import op

from app.db.base import Base
import app.models  # noqa: F401 - ensure all models are registered on Base.metadata


# revision identifiers, used by Alembic.
revision: str = '28d3e7981bfd'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
