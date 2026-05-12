"""add superadmin role

Revision ID: 285c7dfa8ff4
Revises: cc72c42fd90d
Create Date: 2026-05-08 11:37:38.246473

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '285c7dfa8ff4'
down_revision: Union[str, None] = 'cc72c42fd90d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
