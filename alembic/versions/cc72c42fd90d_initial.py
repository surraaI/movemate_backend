"""initial

Revision ID: cc72c42fd90d
Revises: 20260427_0003
Create Date: 2026-05-07 11:45:38.638935

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cc72c42fd90d'
down_revision: Union[str, None] = '20260427_0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
